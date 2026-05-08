#!/usr/bin/env -S python3 -u
"""metrics_cli.py - flow-metrics CLI 진입점.

W01 (`metrics.py`) 가 기록한 ``<workDir>/metrics.jsonl`` jsonl 파일들을
집계해 사람이 읽기 쉬운 표 형식으로 출력하는 3종 서브커맨드를 제공한다.

서브커맨드:
    summarize <registryKey>
        ``.claude-organic/runs/<registryKey>/*/*/metrics.jsonl`` 글롭으로
        해당 워크플로우 한 번의 모든 jsonl 줄을 모아 단계/토큰/도구/회귀
        요약 표를 출력.
    compare <key1> <key2>
        두 registryKey 의 summarize 결과를 diff (key2 - key1) 표로 출력.
    regression [--last N]
        ``.claude-organic/runs/`` 하위 최근 N (기본 10) 개 워크플로우의
        regression.pattern 빈도와 top-3 의 signal_summary 예시를 출력.

설계 노트:
    - 표준 라이브러리만 사용 (argparse, json, glob, pathlib, sys, ...).
    - W01 ``metrics.py`` 의 ``schema_for`` / ``known_event_types`` 를
      재사용한다 — 스키마/이벤트 타입 카탈로그 중복 정의 금지.
    - 백엔드 API (W06) 가 import 해서 쓸 수 있도록 모듈 함수 인터페이스를
      별도로 노출 — ``aggregate_run / aggregate_recent /
      regression_counts / diff_runs``. CLI 진입점은 이 함수들의 thin
      wrapper.
    - 출력은 마크다운 파이프 표 (compatible with terminal + 마크다운 렌더).

CLI 사용 예시::

    $ flow-metrics summarize 20260505-183053
    $ flow-metrics compare 20260504-115242 20260505-183053
    $ flow-metrics regression --last 10
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Optional

# 같은 engine/ 디렉터리의 flow 패키지를 import 하기 위한 sys.path 보정
# (다른 엔진 스크립트들과 동일 패턴 — skill_recommender.py 등)
_engine_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

# W01 모듈 재사용 (이벤트 카탈로그/스키마 단일 진실 공급원)
from flow.metrics import known_event_types  # noqa: E402,F401
from flow.metrics import schema_for  # noqa: E402,F401

# ---------------------------------------------------------------------------
# 경로 상수
# ---------------------------------------------------------------------------

# 본 모듈 위치: <ROOT>/.claude-organic/engine/flow/metrics_cli.py
# → ROOT = parents[3]
_ROOT: Path = Path(__file__).resolve().parents[3]
_RUNS_DIR: Path = _ROOT / ".claude-organic" / "runs"

# regression.pattern.kind 5종 분류 (그 외는 "other" 로 묶음)
_REGRESSION_KINDS: tuple[str, ...] = (
    "worker_false_success",
    "hook_deny",
    "empty_bash_card",
    "stage_header_leak",
    "other",
)

# 단계 표시 순서 (가나다순 대신 의미적 흐름순)
_STEP_ORDER: tuple[str, ...] = ("INIT", "PLAN", "WORK", "REPORT", "DONE")


# ---------------------------------------------------------------------------
# 저수준 헬퍼: jsonl 로딩
# ---------------------------------------------------------------------------


def _iter_metrics_files(registry_key: str) -> list[Path]:
    """registryKey 에 해당하는 모든 metrics.jsonl 파일 경로를 반환한다.

    Args:
        registry_key: ``YYYYMMDD-HHMMSS`` 형식.

    Returns:
        존재하는 파일 경로 리스트 (정렬됨). 워크플로우 한 번에는 보통
        1개지만 chain 등 다중 command 시 여러 개일 수 있음.
    """
    # T-448 폴드 구조: <key>/metrics.jsonl
    pattern = str(_RUNS_DIR / registry_key / "metrics.jsonl")
    paths = sorted(Path(p) for p in glob.glob(pattern))
    return paths


def _load_events(paths: Iterable[Path]) -> list[dict[str, Any]]:
    """파일 경로 리스트의 jsonl 줄을 모두 읽어 dict 리스트로 반환한다.

    Args:
        paths: metrics.jsonl 파일 경로들.

    Returns:
        파싱된 이벤트 dict 리스트. JSON 파싱 실패 줄은 건너뛴다 (무결성
        보다 가용성 우선 — 깨진 한 줄 때문에 전체가 실패하지 않도록).
    """
    events: list[dict[str, Any]] = []
    for p in paths:
        try:
            with open(p, encoding="utf-8") as fp:
                for ln in fp:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        events.append(json.loads(ln))
                    except json.JSONDecodeError:
                        # 깨진 줄은 무시하고 진행 (집계 우선)
                        continue
        except OSError:
            continue
    return events


def _list_recent_keys(last: int) -> list[str]:
    """최근 N 개 registryKey 를 mtime 내림차순으로 반환한다.

    Args:
        last: 가져올 개수.

    Returns:
        registryKey 문자열 리스트 (가장 최근이 0번째). runs 디렉터리가
        없으면 빈 리스트.
    """
    if not _RUNS_DIR.is_dir():
        return []
    keys: list[tuple[float, str]] = []
    for child in _RUNS_DIR.iterdir():
        if not child.is_dir():
            continue
        # registryKey 디렉터리만 (예: 20260505-183053). bg / chain_launcher.log 같은 파일/잡종 제외.
        name = child.name
        if len(name) != 15 or name[8] != "-":
            continue
        try:
            mtime = child.stat().st_mtime
        except OSError:
            continue
        keys.append((mtime, name))
    keys.sort(reverse=True)
    return [k for _, k in keys[: max(0, int(last))]]


# ---------------------------------------------------------------------------
# 모듈 함수 API (W06 백엔드가 import 함)
# ---------------------------------------------------------------------------


def _classify_regression_kind(kind: Any) -> str:
    """regression.pattern.kind 를 5종 분류로 정규화한다."""
    if isinstance(kind, str) and kind in _REGRESSION_KINDS:
        return kind
    return "other"


def aggregate_run(registry_key: str) -> dict[str, Any]:
    """단일 registryKey 의 모든 metrics.jsonl 을 집계하여 dict 로 반환한다.

    Args:
        registry_key: 집계 대상 registryKey.

    Returns:
        다음 키를 갖는 dict::

            {
              "registry_key": "...",
              "files": [str, ...],          # 집계된 metrics.jsonl 경로
              "total_events": int,
              "step_durations": {step: {"avg_ms": float, "count": int, "fail": int}},
              "tokens": {"input": int, "output": int,
                         "cache_creation": int, "cache_read": int,
                         "effective": float},
              "tool_calls_allowed": {tool_name: int},
              "tool_deny": int,
              "subagent_spawn": {agent_kind: int},
              "regression": {kind: int},
              "step_end_fail": int,
            }

        파일이 하나도 없으면 ``files=[]``, ``total_events=0`` 인 빈 dict 반환.
    """
    paths = _iter_metrics_files(registry_key)
    events = _load_events(paths)

    step_durations_acc: dict[str, list[int]] = defaultdict(list)
    step_fail: Counter[str] = Counter()
    tokens = {
        "input": 0,
        "output": 0,
        "cache_creation": 0,
        "cache_read": 0,
        "effective": 0.0,
    }
    tool_calls_allowed: Counter[str] = Counter()
    tool_deny_count = 0
    subagent_spawn: Counter[str] = Counter()
    regression_counts_local: Counter[str] = Counter()
    step_end_fail = 0

    for ev in events:
        et = ev.get("event_type")
        payload = ev.get("payload") or {}
        if et == "step.end":
            step = str(payload.get("step", "?"))
            dur = payload.get("duration_ms")
            if isinstance(dur, (int, float)):
                step_durations_acc[step].append(int(dur))
            outcome = str(payload.get("outcome", ""))
            if outcome == "fail":
                step_end_fail += 1
                step_fail[step] += 1
        elif et == "usage.snapshot":
            tokens["input"] += int(payload.get("input_tokens", 0) or 0)
            tokens["output"] += int(payload.get("output_tokens", 0) or 0)
            tokens["cache_creation"] += int(
                payload.get("cache_creation_tokens", 0) or 0
            )
            tokens["cache_read"] += int(payload.get("cache_read_tokens", 0) or 0)
            eff = payload.get("effective_tokens", 0) or 0
            try:
                tokens["effective"] += float(eff)
            except (TypeError, ValueError):
                pass
        elif et == "tool.call":
            if bool(payload.get("allowed", False)):
                tool_calls_allowed[str(payload.get("tool_name", "?"))] += 1
        elif et == "tool.deny":
            tool_deny_count += 1
        elif et == "subagent.spawn":
            subagent_spawn[str(payload.get("agent_kind", "?"))] += 1
        elif et == "regression.pattern":
            regression_counts_local[
                _classify_regression_kind(payload.get("kind"))
            ] += 1

    step_durations: dict[str, dict[str, Any]] = {}
    for step, durs in step_durations_acc.items():
        step_durations[step] = {
            "avg_ms": (sum(durs) / len(durs)) if durs else 0.0,
            "count": len(durs),
            "fail": int(step_fail.get(step, 0)),
        }

    return {
        "registry_key": registry_key,
        "files": [str(p) for p in paths],
        "total_events": len(events),
        "step_durations": step_durations,
        "tokens": tokens,
        "tool_calls_allowed": dict(tool_calls_allowed),
        "tool_deny": tool_deny_count,
        "subagent_spawn": dict(subagent_spawn),
        "regression": dict(regression_counts_local),
        "step_end_fail": step_end_fail,
    }


def aggregate_recent(last: int = 20) -> list[dict[str, Any]]:
    """최근 N 개 워크플로우의 summary dict 리스트를 반환한다.

    Args:
        last: 가져올 개수 (기본 20).

    Returns:
        ``aggregate_run()`` 결과 dict 의 리스트. 가장 최근이 0번째.
    """
    return [aggregate_run(k) for k in _list_recent_keys(last)]


def regression_counts(last: int = 10) -> dict[str, Any]:
    """최근 N 개 워크플로우의 regression.pattern 빈도를 집계한다.

    Args:
        last: 집계 범위 (기본 10).

    Returns:
        다음 형식의 dict::

            {
              "scanned_keys": [str, ...],
              "counts": {kind: int},  # 5종 + other
              "examples": {kind: [signal_summary, ...]},  # 가장 빈번한 top-3
            }
    """
    keys = _list_recent_keys(last)
    counts: Counter[str] = Counter({k: 0 for k in _REGRESSION_KINDS})
    examples: dict[str, list[str]] = defaultdict(list)
    for key in keys:
        events = _load_events(_iter_metrics_files(key))
        for ev in events:
            if ev.get("event_type") != "regression.pattern":
                continue
            payload = ev.get("payload") or {}
            kind = _classify_regression_kind(payload.get("kind"))
            counts[kind] += 1
            sig = payload.get("signal_summary")
            if isinstance(sig, str) and sig:
                # 메모리 절약 — kind 당 최대 5개만 보관
                if len(examples[kind]) < 5:
                    examples[kind].append(sig)

    return {
        "scanned_keys": keys,
        "counts": dict(counts),
        "examples": {k: list(v) for k, v in examples.items()},
    }


def diff_runs(key1: str, key2: str) -> dict[str, Any]:
    """두 registryKey 의 summarize 결과를 비교한 diff dict 를 반환한다.

    diff 의미는 ``key2 - key1`` 로 통일 (양수 = key2 가 큼, 음수 = 작음).

    Args:
        key1: 비교 기준 (이전).
        key2: 비교 대상 (이후).

    Returns:
        다음 형식의 dict::

            {
              "key1": "...", "key2": "...",
              "step_duration_diff": {step: avg_ms_diff},
              "tokens_diff": {input/output/cache_creation/cache_read/effective},
              "tool_calls_diff": {tool_name: count_diff},
              "tool_deny_diff": int,
              "subagent_spawn_diff": {agent_kind: count_diff},
              "regression_diff": {kind: count_diff},
              "step_end_fail_diff": int,
              "summaries": {key1: aggregate_run(...), key2: aggregate_run(...)},
            }
    """
    a = aggregate_run(key1)
    b = aggregate_run(key2)

    # step duration diff (avg_ms 기준)
    steps = set(a["step_durations"].keys()) | set(b["step_durations"].keys())
    step_diff: dict[str, float] = {}
    for s in steps:
        av = a["step_durations"].get(s, {}).get("avg_ms", 0.0)
        bv = b["step_durations"].get(s, {}).get("avg_ms", 0.0)
        step_diff[s] = float(bv) - float(av)

    tokens_diff: dict[str, float] = {}
    for k, av in a["tokens"].items():
        tokens_diff[k] = float(b["tokens"].get(k, 0)) - float(av)

    # 도구 호출 합집합 diff
    tools = set(a["tool_calls_allowed"].keys()) | set(b["tool_calls_allowed"].keys())
    tool_diff = {
        t: int(b["tool_calls_allowed"].get(t, 0))
        - int(a["tool_calls_allowed"].get(t, 0))
        for t in tools
    }

    sub_kinds = set(a["subagent_spawn"].keys()) | set(b["subagent_spawn"].keys())
    sub_diff = {
        k: int(b["subagent_spawn"].get(k, 0)) - int(a["subagent_spawn"].get(k, 0))
        for k in sub_kinds
    }

    reg_kinds = set(a["regression"].keys()) | set(b["regression"].keys())
    reg_diff = {
        k: int(b["regression"].get(k, 0)) - int(a["regression"].get(k, 0))
        for k in reg_kinds
    }

    return {
        "key1": key1,
        "key2": key2,
        "step_duration_diff": step_diff,
        "tokens_diff": tokens_diff,
        "tool_calls_diff": tool_diff,
        "tool_deny_diff": int(b["tool_deny"]) - int(a["tool_deny"]),
        "subagent_spawn_diff": sub_diff,
        "regression_diff": reg_diff,
        "step_end_fail_diff": int(b["step_end_fail"]) - int(a["step_end_fail"]),
        "summaries": {key1: a, key2: b},
    }


# ---------------------------------------------------------------------------
# 출력 포맷터 (마크다운 파이프 표)
# ---------------------------------------------------------------------------


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    """마크다운 파이프 테이블 문자열을 생성한다.

    Args:
        headers: 헤더 셀 리스트.
        rows: 각 행의 셀 문자열 리스트. 셀은 모두 str 가정 (호출측 책임).

    Returns:
        ``| h1 | h2 |\\n|---|---|\\n| r1 | r2 |\\n...`` 형식 문자열.
    """
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return "\n".join([head, sep, body]) if rows else "\n".join([head, sep])


def _sorted_steps(step_durations: dict[str, dict[str, Any]]) -> list[str]:
    """단계 키를 의미적 흐름 순 → 알파벳 순으로 정렬한다."""
    known = [s for s in _STEP_ORDER if s in step_durations]
    rest = sorted(s for s in step_durations.keys() if s not in _STEP_ORDER)
    return known + rest


def format_summary(summary: dict[str, Any]) -> str:
    """``aggregate_run()`` 결과를 사람이 읽기 쉬운 마크다운 문자열로 변환한다."""
    lines: list[str] = []
    rkey = summary.get("registry_key", "?")
    lines.append(f"# Workflow Summary — `{rkey}`")
    lines.append("")
    files = summary.get("files", [])
    lines.append(f"- 집계 metrics.jsonl: {len(files)} 개")
    for f in files:
        lines.append(f"  - {f}")
    lines.append(f"- 총 이벤트 수: {summary.get('total_events', 0)}")
    lines.append(f"- step.end fail: {summary.get('step_end_fail', 0)}")
    lines.append(f"- tool.deny 합계: {summary.get('tool_deny', 0)}")
    lines.append("")

    # 단계별 평균 duration
    lines.append("## 단계별 평균 duration (ms)")
    sd = summary.get("step_durations", {})
    if sd:
        rows = []
        for s in _sorted_steps(sd):
            v = sd[s]
            rows.append(
                [
                    s,
                    f"{v.get('avg_ms', 0.0):.1f}",
                    str(v.get("count", 0)),
                    str(v.get("fail", 0)),
                ]
            )
        lines.append(_md_table(["step", "avg_ms", "count", "fail"], rows))
    else:
        lines.append("_(step.end 이벤트 없음)_")
    lines.append("")

    # 토큰 합계
    lines.append("## 토큰 합계")
    t = summary.get("tokens", {})
    rows = [
        ["input", str(int(t.get("input", 0)))],
        ["output", str(int(t.get("output", 0)))],
        ["cache_creation", str(int(t.get("cache_creation", 0)))],
        ["cache_read", str(int(t.get("cache_read", 0)))],
        ["effective", f"{float(t.get('effective', 0.0)):.1f}"],
    ]
    lines.append(_md_table(["category", "tokens"], rows))
    lines.append("")

    # 도구 호출 카운트 (allowed=true)
    lines.append("## 도구 호출 카운트 (allowed)")
    tc = summary.get("tool_calls_allowed", {})
    if tc:
        rows = [[k, str(v)] for k, v in sorted(tc.items(), key=lambda x: -x[1])]
        lines.append(_md_table(["tool_name", "count"], rows))
    else:
        lines.append("_(tool.call allowed 이벤트 없음)_")
    lines.append("")

    # subagent.spawn
    lines.append("## subagent.spawn 카운트")
    sp = summary.get("subagent_spawn", {})
    if sp:
        rows = [[k, str(v)] for k, v in sorted(sp.items(), key=lambda x: -x[1])]
        lines.append(_md_table(["agent_kind", "count"], rows))
    else:
        lines.append("_(subagent.spawn 이벤트 없음)_")
    lines.append("")

    # regression.pattern
    lines.append("## regression.pattern 카운트")
    rg = summary.get("regression", {})
    if rg:
        rows = [
            [k, str(v)]
            for k, v in sorted(rg.items(), key=lambda x: -x[1])
        ]
        lines.append(_md_table(["kind", "count"], rows))
    else:
        lines.append("_(regression.pattern 이벤트 없음)_")
    lines.append("")

    return "\n".join(lines)


def format_compare(diff: dict[str, Any]) -> str:
    """``diff_runs()`` 결과를 마크다운 비교 표 문자열로 변환한다."""
    lines: list[str] = []
    k1, k2 = diff["key1"], diff["key2"]
    lines.append(f"# Workflow Compare — `{k1}` vs `{k2}` (diff = key2 - key1)")
    lines.append("")

    # step duration diff
    lines.append("## 단계별 avg_ms diff")
    sd = diff.get("step_duration_diff", {})
    if sd:
        rows = []
        for s in _sorted_steps({k: {} for k in sd.keys()}):
            v = sd[s]
            sign = "+" if v >= 0 else ""
            rows.append([s, f"{sign}{v:.1f}"])
        lines.append(_md_table(["step", "diff_ms"], rows))
    else:
        lines.append("_(양쪽 모두 step.end 이벤트 없음)_")
    lines.append("")

    # tokens diff
    lines.append("## 토큰 합계 diff")
    rows = []
    for k, v in diff.get("tokens_diff", {}).items():
        sign = "+" if v >= 0 else ""
        # input/output/cache_* 는 정수 의미, effective 는 실수
        if k == "effective":
            rows.append([k, f"{sign}{v:.1f}"])
        else:
            rows.append([k, f"{sign}{int(v)}"])
    lines.append(_md_table(["category", "diff"], rows))
    lines.append("")

    # tool calls diff
    lines.append("## 도구 호출 카운트 diff (allowed)")
    tc = diff.get("tool_calls_diff", {})
    if tc:
        rows = []
        for k, v in sorted(tc.items(), key=lambda x: -abs(x[1])):
            sign = "+" if v >= 0 else ""
            rows.append([k, f"{sign}{int(v)}"])
        lines.append(_md_table(["tool_name", "diff"], rows))
    else:
        lines.append("_(양쪽 모두 tool.call allowed 이벤트 없음)_")
    lines.append("")

    # tool.deny diff + subagent + regression
    rows = [
        ["tool.deny", _signed(diff.get("tool_deny_diff", 0))],
        ["step.end fail", _signed(diff.get("step_end_fail_diff", 0))],
    ]
    for k, v in diff.get("subagent_spawn_diff", {}).items():
        rows.append([f"subagent.spawn[{k}]", _signed(v)])
    for k, v in diff.get("regression_diff", {}).items():
        rows.append([f"regression[{k}]", _signed(v)])
    lines.append("## 기타 카운트 diff")
    lines.append(_md_table(["metric", "diff"], rows))
    lines.append("")

    return "\n".join(lines)


def _signed(v: Any) -> str:
    """+/- 부호 포함 정수 문자열."""
    try:
        n = int(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{'+' if n >= 0 else ''}{n}"


def format_regression(report: dict[str, Any]) -> str:
    """``regression_counts()`` 결과를 마크다운 표로 변환한다."""
    lines: list[str] = []
    keys = report.get("scanned_keys", [])
    lines.append(f"# Regression Patterns — 최근 {len(keys)} 개 워크플로우")
    lines.append("")
    if keys:
        lines.append("- 스캔 대상 registryKey:")
        for k in keys:
            lines.append(f"  - {k}")
    else:
        lines.append("_(스캔 가능한 워크플로우가 없음)_")
    lines.append("")

    counts = report.get("counts", {})
    examples = report.get("examples", {})

    # 빈도 표
    lines.append("## kind 별 빈도")
    rows = [
        [k, str(counts.get(k, 0))]
        for k in sorted(counts.keys(), key=lambda x: -counts.get(x, 0))
    ]
    lines.append(_md_table(["kind", "count"], rows))
    lines.append("")

    # top-3 examples
    top3 = sorted(counts.items(), key=lambda x: -x[1])[:3]
    lines.append("## top-3 signal_summary 예시")
    if not any(c for _, c in top3):
        lines.append("_(regression.pattern 이벤트 없음)_")
    else:
        for kind, cnt in top3:
            if cnt <= 0:
                continue
            ex_list = examples.get(kind, [])
            ex = ex_list[0] if ex_list else "_(signal_summary 없음)_"
            lines.append(f"- **{kind}** (count={cnt}): {ex}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------


def _cmd_summarize(args: argparse.Namespace) -> int:
    summary = aggregate_run(args.registry_key)
    if not summary["files"]:
        print(
            f"[flow-metrics] no metrics.jsonl found for registry_key={args.registry_key}",
            file=sys.stderr,
        )
        print(
            f"  (검색 패턴: {_RUNS_DIR}/{args.registry_key}/metrics.jsonl)",
            file=sys.stderr,
        )
        return 2
    print(format_summary(summary))
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    diff = diff_runs(args.key1, args.key2)
    a = diff["summaries"][args.key1]
    b = diff["summaries"][args.key2]
    missing = []
    if not a["files"]:
        missing.append(args.key1)
    if not b["files"]:
        missing.append(args.key2)
    if missing:
        print(
            f"[flow-metrics] no metrics.jsonl found for: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 2
    print(format_compare(diff))
    return 0


def _cmd_regression(args: argparse.Namespace) -> int:
    report = regression_counts(last=args.last)
    print(format_regression(report))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flow-metrics",
        description=(
            "워크플로우 metrics.jsonl 집계 CLI — summarize / compare / regression "
            "(W01 metrics.py 와 카탈로그 공유)"
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sum = sub.add_parser(
        "summarize",
        help="단일 registryKey 의 metrics.jsonl 요약 표 출력",
    )
    p_sum.add_argument(
        "registry_key",
        help="대상 registryKey (예: 20260505-183053)",
    )
    p_sum.set_defaults(func=_cmd_summarize)

    p_cmp = sub.add_parser(
        "compare", help="두 registryKey 의 summarize diff 표 출력"
    )
    p_cmp.add_argument("key1", help="비교 기준 registryKey (이전)")
    p_cmp.add_argument("key2", help="비교 대상 registryKey (이후)")
    p_cmp.set_defaults(func=_cmd_compare)

    p_reg = sub.add_parser(
        "regression",
        help="최근 N 개 워크플로우의 regression.pattern 빈도",
    )
    p_reg.add_argument(
        "--last",
        type=int,
        default=10,
        help="집계 대상 최근 워크플로우 개수 (기본 10)",
    )
    p_reg.set_defaults(func=_cmd_regression)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    try:
        return int(func(args) or 0)
    except KeyboardInterrupt:
        print("[flow-metrics] interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
