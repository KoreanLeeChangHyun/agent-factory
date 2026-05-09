"""metrics.py - 워크플로우 metrics jsonl writer 인프라.

워크플로우 한 번 실행될 때마다 발생하는 12종 이벤트를 단일 jsonl
파일(`<workDir>/metrics.jsonl`)에 append-only 로 기록한다. 호출 측은
`MetricsWriter` 클래스 또는 함수형 헬퍼 `append_event()` 둘 중 하나를
사용한다.

저장 형식:
    JSON Lines (jsonl). 한 줄 = 한 JSON object + ``\\n``.
    공통 필드:
        - event_type: 11종 카탈로그 중 하나
        - timestamp: ISO8601 (KST, UTC+9)
        - ticket: T-NNN (또는 None 허용)
        - registry_key: YYYYMMDD-HHMMSS (또는 None 허용)
        - work_dir: 절대 경로
        - payload: dict (event_type 별 필수 키 검증)

12종 event_type 카탈로그:
    step.start, step.end, phase.start, phase.end, tool.call, tool.deny,
    usage.snapshot, subagent.spawn, subagent.end, worktree.io,
    regression.pattern, report.missing

검증 규칙:
    - event_type 미등록 → ValueError
    - payload 가 dict 가 아님 → ValueError
    - payload 필수 키 누락 → ValueError
    - timestamp 자동 생성 (KST ISO8601)

IO 규칙:
    - append-only (open mode "a")
    - write 후 flush() (no fsync)
    - ensure_ascii=False (한국어 보존)
    - 줄당 4KB 권고 — 본 모듈은 검증만 수행, truncate 는 호출측 책임

예시:
    >>> from flow.metrics import MetricsWriter, append_event
    >>> w = MetricsWriter("/tmp/run/work", ticket="T-400",
    ...                   registry_key="20260505-183053")
    >>> w.append("step.start", {"step": "INIT", "source": "banner"})
    >>> w.close()

    또는 함수형:
    >>> append_event("/tmp/run/work", "step.start",
    ...              {"step": "INIT", "source": "banner"},
    ...              ticket="T-400", registry_key="20260505-183053")
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, Union

# KST (UTC+9)
_KST = timezone(timedelta(hours=9))

# 줄당 권고 4KB 한도 (호출측 truncate 권고용 상수)
LINE_BYTE_LIMIT: int = 4096

# metrics.jsonl 파일명
_METRICS_FILENAME: str = "metrics.jsonl"

# 12종 event_type → payload 필수 키 카탈로그
# plan.md §5 (registryKey 20260505-183053) 정의 기준. T-447로 report.missing 추가.
# NOTE: metric event 의 'step' 키는 status.json 'workflow_phase' 와 동일 의미 (metric event schema BC — 별도 마이그레이션 트랙).
_SCHEMA: dict[str, list[str]] = {
    "step.start": ["step", "source"],
    "step.end": ["step", "duration_ms", "outcome", "source"],
    "phase.start": ["phase_index", "total"],
    "phase.end": ["phase_index", "duration_ms", "outcome"],
    "tool.call": [
        "tool_name",
        "tool_use_id",
        "duration_ms",
        "allowed",
    ],
    "tool.deny": ["tool_name", "tool_use_id", "reason"],
    "usage.snapshot": [
        "step",
        "input_tokens",
        "output_tokens",
        "cache_creation_tokens",
        "cache_read_tokens",
        "effective_tokens",
    ],
    "subagent.spawn": ["agent_kind", "parent_tool_use_id"],
    "subagent.end": ["agent_kind", "tool_use_id", "duration_ms", "outcome"],
    "worktree.io": ["op", "duration_ms", "outcome"],
    "regression.pattern": ["kind", "signal_summary"],
    # T-447: reporter Write SDK 차단 시 report.md 부재 탐지 (advisory only)
    "report.missing": ["report_path", "signal_summary"],
}


def _now_kst_iso() -> str:
    """현재 시각을 KST ISO8601 형식으로 반환한다.

    Returns:
        예: "2026-05-05T18:30:53.123456+09:00"
    """
    return datetime.now(_KST).isoformat()


def schema_for(event_type: str) -> list[str]:
    """event_type 에 대한 payload 필수 키 목록을 반환한다.

    Args:
        event_type: 11종 카탈로그 중 하나.

    Returns:
        필수 payload 키 리스트의 새 복사본 (호출측 변경이 카탈로그에 영향 X).

    Raises:
        KeyError: event_type 이 카탈로그에 없을 때.
    """
    if event_type not in _SCHEMA:
        raise KeyError(
            f"unknown event_type: {event_type!r} "
            f"(known: {sorted(_SCHEMA.keys())})"
        )
    return list(_SCHEMA[event_type])


def known_event_types() -> list[str]:
    """등록된 12종 event_type 카탈로그를 정렬해 반환한다.

    Returns:
        event_type 문자열 리스트 (사전순 정렬).
    """
    return sorted(_SCHEMA.keys())


def metrics_path(work_dir: Union[str, Path]) -> Path:
    """work_dir 에 대한 metrics.jsonl 절대 경로를 반환한다.

    Args:
        work_dir: 워크플로우 작업 디렉터리 (str 또는 Path).

    Returns:
        ``<work_dir>/metrics.jsonl`` 의 Path 객체.
    """
    return Path(work_dir) / _METRICS_FILENAME


def _validate(event_type: str, payload: Any) -> None:
    """event_type / payload 의 형식과 필수 키 존재 여부를 검증한다.

    Args:
        event_type: 11종 카탈로그 중 하나여야 함.
        payload: dict 여야 하며 schema_for() 가 요구하는 키를 모두 포함해야 함.

    Raises:
        ValueError: 검증 실패 시. 메시지에 사유 포함.
    """
    if event_type not in _SCHEMA:
        raise ValueError(
            f"unknown event_type: {event_type!r} "
            f"(known: {sorted(_SCHEMA.keys())})"
        )
    if not isinstance(payload, dict):
        raise ValueError(
            f"payload must be dict, got {type(payload).__name__}"
        )
    required = _SCHEMA[event_type]
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValueError(
            f"payload missing required keys for {event_type!r}: {missing} "
            f"(required: {required})"
        )


def _load_context_defaults(work_dir: Path) -> dict[str, Optional[str]]:
    """work_dir 의 .context.json 에서 ticket / registry_key 기본값을 로드한다.

    Args:
        work_dir: 워크플로우 작업 디렉터리.

    Returns:
        {"ticket": <T-NNN | None>, "registry_key": <YYYYMMDD-HHMMSS | None>}
        파일 부재 / 파싱 실패 / 키 없음 → None 으로 채움.
    """
    ctx_path = Path(work_dir) / ".context.json"
    defaults: dict[str, Optional[str]] = {"ticket": None, "registry_key": None}
    try:
        with open(ctx_path, encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, json.JSONDecodeError):
        return defaults
    if not isinstance(data, dict):
        return defaults
    # 흔한 키 후보 두 가지 모두 지원 (ticket / ticket_number, registry_key / registryKey)
    ticket_val = data.get("ticket") or data.get("ticket_number")
    rkey_val = data.get("registry_key") or data.get("registryKey")
    if isinstance(ticket_val, str) and ticket_val:
        defaults["ticket"] = ticket_val
    if isinstance(rkey_val, str) and rkey_val:
        defaults["registry_key"] = rkey_val
    return defaults


class MetricsWriter:
    """metrics.jsonl 파일에 이벤트를 append 하는 writer.

    Attributes:
        work_dir: 워크플로우 작업 디렉터리 (절대 경로 권장).
        ticket: 티켓 번호 (예: "T-400"). None 허용.
        registry_key: registryKey (예: "20260505-183053"). None 허용.
        path: ``<work_dir>/metrics.jsonl`` 절대 경로.

    Notes:
        - 인스턴스는 fd 를 보유하지 않는다. 매 append 시 short-lived
          ``open(..., "a")`` → write → flush → close 하여 동시성/충돌
          위험을 최소화한다 (subagent + 메인 동시 쓰기 시나리오 고려).
        - close() 는 호환성을 위해 제공되며 no-op.
    """

    def __init__(
        self,
        work_dir: Union[str, Path],
        ticket: Optional[str] = None,
        registry_key: Optional[str] = None,
    ) -> None:
        """Writer 인스턴스를 초기화한다.

        Args:
            work_dir: 워크플로우 작업 디렉터리.
            ticket: 티켓 번호 (예: "T-400"). 모든 이벤트의 공통 헤더에 들어감.
            registry_key: registryKey (예: "20260505-183053").
        """
        self.work_dir: Path = Path(work_dir)
        self.ticket: Optional[str] = ticket
        self.registry_key: Optional[str] = registry_key
        self.path: Path = metrics_path(self.work_dir)

    def append(self, event_type: str, payload: dict[str, Any]) -> None:
        """이벤트 한 줄을 jsonl 파일에 append 한다.

        Args:
            event_type: 11종 카탈로그 중 하나.
            payload: event_type 에 대한 payload dict.

        Raises:
            ValueError: event_type 이 미등록이거나, payload 형식 오류 또는
                필수 키 누락 시.
            OSError: 디스크 IO 실패 시 (호출측에서 try/except 권고).
        """
        _validate(event_type, payload)
        record: dict[str, Any] = {
            "event_type": event_type,
            "timestamp": _now_kst_iso(),
            "ticket": self.ticket,
            "registry_key": self.registry_key,
            "work_dir": str(self.work_dir),
            "payload": payload,
        }
        # 부모 디렉터리 보장 (work_dir 자체가 없으면 호출측 잘못이지만 안전망)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with open(self.path, "a", encoding="utf-8") as fp:
            fp.write(line)
            fp.write("\n")
            fp.flush()

    def close(self) -> None:
        """호환성 더미. 본 writer 는 fd 를 보유하지 않으므로 no-op."""
        return None

    # 컨텍스트 매니저 지원 (with 블록에서 사용 가능)
    def __enter__(self) -> "MetricsWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def append_event(
    work_dir: Union[str, Path],
    event_type: str,
    payload: dict[str, Any],
    *,
    ticket: Optional[str] = None,
    registry_key: Optional[str] = None,
) -> None:
    """함수형 헬퍼 — 1회성 append 시 인스턴스 생성을 생략하고 호출.

    work_dir/.context.json 이 존재하면 ticket / registry_key 를 자동
    로드하여 명시 인자가 None 일 때 기본값으로 사용한다.

    Args:
        work_dir: 워크플로우 작업 디렉터리.
        event_type: 11종 카탈로그 중 하나.
        payload: event_type 에 대한 payload dict.
        ticket: 명시 시 .context.json 보다 우선.
        registry_key: 명시 시 .context.json 보다 우선.

    Raises:
        ValueError: 검증 실패 시.
        OSError: 디스크 IO 실패 시.
    """
    work_dir_path = Path(work_dir)
    if ticket is None or registry_key is None:
        defaults = _load_context_defaults(work_dir_path)
        if ticket is None:
            ticket = defaults.get("ticket")
        if registry_key is None:
            registry_key = defaults.get("registry_key")
    writer = MetricsWriter(
        work_dir=work_dir_path, ticket=ticket, registry_key=registry_key
    )
    writer.append(event_type, payload)


# ---------------------------------------------------------------------------
# 자가 검증 (__main__)
# ---------------------------------------------------------------------------

def _selfcheck() -> int:
    """11종 스키마의 정상/누락 케이스를 검증하고 결과 표를 출력한다.

    Returns:
        실패 케이스 수. 0 이면 모든 검증 통과.
    """
    import tempfile

    cases: list[tuple[str, str, dict[str, Any], Optional[type[Exception]]]] = []

    # 11종 정상 케이스 (필수 키만 채움)
    valid_payloads: dict[str, dict[str, Any]] = {
        "step.start": {"step": "INIT", "source": "banner"},
        "step.end": {
            "step": "INIT",
            "duration_ms": 1234,
            "outcome": "ok",
            "source": "banner",
        },
        "phase.start": {"phase_index": 1, "total": 2},
        "phase.end": {"phase_index": 1, "duration_ms": 5678, "outcome": "ok"},
        "tool.call": {
            "tool_name": "Bash",
            "tool_use_id": "tu_01",
            "duration_ms": 42,
            "allowed": True,
        },
        "tool.deny": {
            "tool_name": "Edit",
            "tool_use_id": "tu_02",
            "reason": "path outside worktree",
        },
        "usage.snapshot": {
            "step": "WORK",
            "input_tokens": 100,
            "output_tokens": 200,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 50,
            "effective_tokens": 1105.0,
        },
        "subagent.spawn": {"agent_kind": "worker", "parent_tool_use_id": "tu_03"},
        "subagent.end": {
            "agent_kind": "worker",
            "tool_use_id": "tu_03",
            "duration_ms": 99999,
            "outcome": "ok",
        },
        "worktree.io": {"op": "create", "duration_ms": 200, "outcome": "ok"},
        "regression.pattern": {
            "kind": "worker_false_success",
            "signal_summary": "Edit count=0 but status=success",
        },
    }
    for et in known_event_types():
        cases.append(("정상", et, valid_payloads[et], None))

    # 비정상 케이스 ≥ 3
    cases.append(
        (
            "비정상-미등록",
            "unknown.event",
            {"foo": "bar"},
            ValueError,
        )
    )
    cases.append(
        (
            "비정상-payload타입",
            "step.start",
            ["not", "a", "dict"],  # type: ignore[arg-type]
            ValueError,
        )
    )
    cases.append(
        (
            "비정상-필수키누락",
            "step.end",
            {"step": "INIT"},  # duration_ms / outcome / source 누락
            ValueError,
        )
    )
    cases.append(
        (
            "비정상-payload=None",
            "tool.call",
            None,  # type: ignore[arg-type]
            ValueError,
        )
    )

    rows: list[tuple[str, str, str]] = []
    failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        writer = MetricsWriter(
            work_dir=tmp, ticket="T-400", registry_key="20260505-183053"
        )
        for label, et, payload, expected_exc in cases:
            try:
                writer.append(et, payload)  # type: ignore[arg-type]
                actual = "OK"
                exc_name = "-"
            except Exception as exc:  # noqa: BLE001
                actual = "RAISE"
                exc_name = type(exc).__name__

            if expected_exc is None:
                ok = actual == "OK"
            else:
                ok = actual == "RAISE" and exc_name == expected_exc.__name__

            if not ok:
                failed += 1
            verdict = "PASS" if ok else "FAIL"
            rows.append((label + " / " + et, exc_name + " (" + actual + ")", verdict))

        # 정상 케이스 줄 수 검증 (jsonl 라인 수 == 11)
        path = metrics_path(tmp)
        with open(path, encoding="utf-8") as fp:
            lines = [ln for ln in fp.read().splitlines() if ln.strip()]
        # 정상 케이스만 기록되었는지 확인
        line_check_ok = len(lines) == len(valid_payloads)
        rows.append(
            (
                "jsonl 줄 수",
                f"{len(lines)} / {len(valid_payloads)}",
                "PASS" if line_check_ok else "FAIL",
            )
        )
        if not line_check_ok:
            failed += 1

        # 모든 줄이 valid JSON 인지 확인
        json_ok = True
        for ln in lines:
            try:
                json.loads(ln)
            except json.JSONDecodeError:
                json_ok = False
                break
        rows.append(
            (
                "jsonl JSON 파싱",
                f"{len(lines)} 줄",
                "PASS" if json_ok else "FAIL",
            )
        )
        if not json_ok:
            failed += 1

        # append_event() 함수형 헬퍼 동작 검증 (.context.json 자동 로드)
        ctx_dir = Path(tmp) / "ctx_test"
        ctx_dir.mkdir()
        with open(ctx_dir / ".context.json", "w", encoding="utf-8") as fp:
            json.dump(
                {"ticket": "T-401", "registry_key": "20260505-190000"}, fp
            )
        append_event(
            ctx_dir,
            "step.start",
            {"step": "PLAN", "source": "fsm"},
        )
        with open(metrics_path(ctx_dir), encoding="utf-8") as fp:
            rec = json.loads(fp.readline())
        ctx_ok = (
            rec["ticket"] == "T-401"
            and rec["registry_key"] == "20260505-190000"
            and rec["event_type"] == "step.start"
        )
        rows.append(
            (
                "append_event 컨텍스트 자동로드",
                "ticket=T-401 / registry_key=20260505-190000",
                "PASS" if ctx_ok else "FAIL",
            )
        )
        if not ctx_ok:
            failed += 1

    # 표 출력
    print("metrics.py 자가 검증 결과")
    print("=" * 88)
    header = ("케이스", "결과", "판정")
    widths = (44, 32, 6)
    print(
        f"{header[0]:<{widths[0]}} | {header[1]:<{widths[1]}} | {header[2]:<{widths[2]}}"
    )
    print("-" * 88)
    for r in rows:
        print(
            f"{r[0]:<{widths[0]}} | {r[1]:<{widths[1]}} | {r[2]:<{widths[2]}}"
        )
    print("=" * 88)
    print(f"총 케이스: {len(rows)} / 실패: {failed}")
    return failed


if __name__ == "__main__":
    import sys as _sys

    _sys.exit(_selfcheck())
