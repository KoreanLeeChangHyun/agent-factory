#!/usr/bin/env -S python3 -u
"""워크플로우 마무리 처리 스크립트 (flow-finish).

오케스트레이터가 직접 호출하는 워크플로우 마무리 5단계 결정론적 스크립트.

사용법:
  flow-finish <registryKey> <status> [--ticket-number <T-NNN>]

인자:
  registryKey      워크플로우 식별자 (YYYYMMDD-HHMMSS)
  status           완료 | 실패
  --ticket-number  T-NNN 형식 티켓 번호 (선택)

6단계:
  1. status.json 완료 처리   (update_state.py status, 이미 대상 상태면 스킵, 그 외 실패 시 exit 1 — sync 포함)
  2. 사용량 확정             (update_state.py usage-finalize, 비차단)
  3. 아카이빙               (history_sync.py archive, 비차단)
  4. 티켓 상태 갱신          (kanban.py move -> review, ticket_number 있을 때만, 비차단. 자동 merge 금지)
  4c. 체인 감지 및 다음 스테이지 발사 (chain_launcher.py, 완료+체인 존재 시만, 비동기)
  5. tmux 윈도우 백그라운드 지연 kill (TMUX_PANE+T-* 조건 시만, 비차단)

종료 코드:
  0  성공
  1  status.json 전이 실패

## Responsibility Boundary (T-455)

This module handles **termination responsibility** only (DONE / FAILED arrival):
- Kanban Review transition (kanban.py move -> review)
- History synchronization (history_sync archive)
- Session cleanup (TMUX_PANE / HTTP kill)
- Usage finalization (usage-finalize)

**Failure logic absorption is forbidden (MUST NOT)**:
Phase failure identification / sentinel creation / retry-context.json update /
retry eligibility judgment are the sole responsibility of
`engine/flow/failure_handler.py`. This module does NOT import failure_handler
functions and does NOT directly access failure data structures.

## T-455 4-step Flow Mapping

| Step | Module | Action |
|------|--------|--------|
| 1 | failure_handler.create_sentinel() | Create .workflow-failed sentinel + update retry-context.json |
| 2 | hooks/subagent-stop.py | Detect sentinel + call flow-fail-record (non-blocking) |
| 3 | bin/flow-fail-record (-> failure_handler.record_failure) | Idempotent retry-context update |
| 4 | finalization.py (this module) | On status="실패": kanban move review (existing behavior preserved) |

## Regression Guard (T-411 Canon)
Automatic forced status transitions / kanban auto-revert / commit-missing
auto-detection / advisory-only validators MUST NOT be added to this module.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error

# utils 패키지 import
_engine_dir: str = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import acquire_lock, load_json_file, release_lock, resolve_abs_work_dir, resolve_project_root
from constants import CHAIN_SEPARATOR, ERROR_THRESHOLD, LOGS_HEADER_LINE, LOGS_SEPARATOR_LINE
from flow.dashboard_updater import (
    _update_logs_md,
    _update_skill_frequency,
    _update_step_durations,
    _update_task_stats,
)
from flow.flow_logger import append_log as _append_log
from flow.session_identifier import WINDOW_PREFIX_P

PROJECT_ROOT: str = resolve_project_root()


# 스크립트 경로
HISTORY_SYNC: str = os.path.join(PROJECT_ROOT, ".claude-organic", "engine", "sync", "history_sync.py")
UPDATE_STATE: str = os.path.join(PROJECT_ROOT, ".claude-organic", "engine", "flow", "update_state.py")
USAGE_SYNC: str = os.path.join(PROJECT_ROOT, ".claude-organic", "engine", "sync", "usage_sync.py")
KANBAN_PY: str = os.path.join(PROJECT_ROOT, ".claude-organic", "engine", "flow", "kanban.py")
CHAIN_LAUNCHER: str = os.path.join(PROJECT_ROOT, ".claude-organic", "engine", "flow", "chain_launcher.py")
CHAIN_LAUNCH_WRAPPER: str = os.path.join(PROJECT_ROOT, ".claude-organic", "bin", "flow-chain-launch")


def run(
    cmd: list[str],
    label: str,
    critical: bool = False,
    input_data: str | None = None,
) -> int:
    """subprocess 실행 래퍼.

    Args:
        cmd: 실행할 명령어 리스트
        label: 로그용 라벨 (에러/경고 메시지에 표시)
        critical: True이면 실패 시 exit 1로 종료
        input_data: stdin으로 전달할 문자열 (선택)

    Returns:
        프로세스 종료 코드. 타임아웃 또는 예외 시 1 반환.
    """
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, input=input_data)
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if critical:
                print("FAIL", flush=True)
                print(f"[ERROR] {label}: exit {result.returncode}", file=sys.stderr)
                if stderr:
                    print(f"  {stderr}", file=sys.stderr)
                sys.exit(1)
            else:
                print(f"[WARN] {label}: exit {result.returncode}", file=sys.stderr)
                if stderr:
                    print(f"  {stderr}", file=sys.stderr)
        return result.returncode
    except subprocess.TimeoutExpired:
        if critical:
            print("FAIL", flush=True)
            print(f"[ERROR] {label}: timeout", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"[WARN] {label}: timeout", file=sys.stderr)
            return 1
    except Exception as e:
        if critical:
            print("FAIL", flush=True)
            print(f"[ERROR] {label}: {e}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"[WARN] {label}: {e}", file=sys.stderr)
            return 1


def _find_transcript_path(registry_key: str) -> str | None:
    """registryKey로부터 subagents 디렉터리의 transcript 경로를 구성한다.

    0차(최우선): usage.json의 _main_transcript 경로로부터 subagents/ 탐색.
    1차: status.json의 linked_sessions에서 세션 ID를 읽고 subagents/ 탐색.
    2차(대체): linked_sessions가 비어있을 때 usage.json의 _agent_map에 기록된
         알려진 agent_id로 glob하여 subagents 디렉터리를 역탐색한다.
    실제 agent-*.jsonl 파일이 존재하는 경우 첫 번째 파일 경로를 반환한다.

    Args:
        registry_key: YYYYMMDD-HHMMSS 형식 워크플로우 식별자

    Returns:
        agent-*.jsonl 파일 절대 경로. 찾지 못하면 None.
    """
    abs_work_dir = resolve_abs_work_dir(registry_key, PROJECT_ROOT)
    if not abs_work_dir:
        return None

    # 0차: usage.json의 _main_transcript 경로로부터 subagents/ 탐색
    usage_file = os.path.join(abs_work_dir, "usage.json")
    usage_data_early = load_json_file(usage_file)
    if isinstance(usage_data_early, dict):
        main_transcript = usage_data_early.get("_main_transcript", "")
        if main_transcript and os.path.isfile(main_transcript):
            # _main_transcript 파일의 디렉터리에 subagents/ 폴더가 있으면 탐색
            transcript_dir = os.path.dirname(main_transcript)
            subagents_dir = os.path.join(transcript_dir, "subagents")
            if os.path.isdir(subagents_dir):
                matches = sorted(glob.glob(os.path.join(subagents_dir, "agent-*.jsonl")))
                if matches:
                    return matches[0]

    status_file = os.path.join(abs_work_dir, "status.json")
    status_data = load_json_file(status_file)
    if not isinstance(status_data, dict):
        return None

    project_slug = PROJECT_ROOT.replace("/", "-")

    # 1차: linked_sessions 기반 탐색
    sessions = status_data.get("linked_sessions", [])
    for claude_base in [
        os.path.expanduser("~/.claude"),
        os.path.expanduser("~/.config/claude"),
    ]:
        projects_dir = os.path.join(claude_base, "projects", project_slug)
        if not os.path.isdir(projects_dir):
            continue
        for session_id in sessions:
            subagents_dir = os.path.join(projects_dir, session_id, "subagents")
            if os.path.isdir(subagents_dir):
                matches = sorted(glob.glob(os.path.join(subagents_dir, "agent-*.jsonl")))
                if matches:
                    return matches[0]

    # 2차: _agent_map에 기록된 알려진 agent_id로 역탐색
    usage_file = os.path.join(abs_work_dir, "usage.json")
    usage_data = load_json_file(usage_file)
    if not isinstance(usage_data, dict):
        return None

    agent_map = usage_data.get("_agent_map", {})
    if not agent_map:
        return None

    for claude_base in [
        os.path.expanduser("~/.claude"),
        os.path.expanduser("~/.config/claude"),
    ]:
        projects_dir = os.path.join(claude_base, "projects", project_slug)
        if not os.path.isdir(projects_dir):
            continue
        # _agent_map의 각 agent_id에 대해 glob으로 subagents 디렉터리 탐색
        for agent_id in agent_map:
            pattern = os.path.join(projects_dir, "*", "subagents", f"agent-{agent_id}.jsonl")
            matches = glob.glob(pattern)
            if matches:
                # subagents/ 상위 = session_dir, 해당 디렉터리의 첫 번째 agent-*.jsonl 반환
                subagents_dir = os.path.dirname(matches[0])
                all_agents = sorted(glob.glob(os.path.join(subagents_dir, "agent-*.jsonl")))
                if all_agents:
                    return all_agents[0]

    return None


def _build_result_update_args(
    abs_work_dir: str, registry_key: str | None = None,
) -> list[str]:
    """update-result CLI 추가 인자 리스트를 반환한다.

    abs_work_dir에서 registryKey를 추출하고, plan.md / report.md 존재 여부를
    확인하여 update-result CLI에 전달할 인자 리스트를 반환한다.

    Args:
        abs_work_dir: 워크플로우 작업 디렉터리 절대 경로
            (.workflow/{registryKey}/ 폴드 구조 — T-448/T-449 이후)
        registry_key: 호출자(main)가 인자로 받은 registry_key. 명시 전달 시
            abs_work_dir 정규식 추출 실패에 의존하지 않는다 (2026-04-29 보완).

    Returns:
        ["--registrykey", registryKey, "--workdir", workDir상대경로] 에
        plan.md / report.md가 존재하면 각각 "--plan" / "--report" 인자를 추가한 리스트.
        registryKey 추출과 workdir 매칭 모두 실패하면 빈 리스트.
    """
    import re as _re

    # registry_key 우선순위: 1) 인자로 받은 명시 값, 2) abs_work_dir 정규식 추출
    if not registry_key:
        _ts_pattern = _re.compile(r"\.claude-organic[/\\]runs[/\\](\d{8}-\d{6}(?:-\d+)?)")
        _match = _ts_pattern.search(abs_work_dir)
        if not _match:
            return []
        registry_key = _match.group(1)

    # 상대 workDir: .claude-organic/runs/{registryKey}/... 이후 부분을 포함한 경로
    _wf_idx = abs_work_dir.find(".claude-organic/runs/")
    if _wf_idx == -1:
        _wf_idx = abs_work_dir.find(".claude-organic\\runs\\")
    if _wf_idx == -1:
        return []
    work_dir_rel: str = abs_work_dir[_wf_idx:]
    # 경로 구분자를 슬래시로 통일하고 끝 슬래시 정규화
    work_dir_rel = work_dir_rel.replace("\\", "/").rstrip("/") + "/"

    args: list[str] = ["--registrykey", registry_key, "--workdir", work_dir_rel]

    plan_abs: str = os.path.join(abs_work_dir, "plan.md")
    if os.path.isfile(plan_abs):
        plan_rel: str = work_dir_rel + "plan.md"
        args += ["--plan", plan_rel]

    report_abs: str = os.path.join(abs_work_dir, "report.md")
    if os.path.isfile(report_abs):
        report_rel: str = work_dir_rel + "report.md"
        args += ["--report", report_rel]

    return args


# ──────────────────────────────────────────────────────────────────────
# W04: 회귀 패턴 캡처 (regression.pattern)
# ──────────────────────────────────────────────────────────────────────
#
# DONE 단계 진입 시점에 metrics.jsonl 및 workflow.log 를 분석하여
# 다음 5종 회귀 패턴을 분류하고 `regression.pattern` 이벤트를 append 한다.
#
#   1. worker_false_success
#      - subagent.end{outcome=ok} 가 1건 이상이고
#      - 그 subagent.end 이후의 tool.call{tool_name=Edit|Write} 카운트 == 0
#      → Worker 가 "성공" 상태로 반환했지만 실제 코드 변경이 없는 패턴
#
#   2. hook_deny
#      - tool.deny 카운트 ≥ 1
#
#   3. empty_bash_card
#      - tool.call{tool_name=Bash, bytes_out=0} 카운트 ≥ 1
#
#   4. stage_header_leak
#      - workflow.log 에 "[STEP]" 또는 "[PHASE]" 패턴이 일반 출력 위치에 노출
#        (간단히 정규식 매칭)
#
#   5. other
#      - 위 4종 0건 + status == "실패" 인 경우 fallback
#
# 모든 분류는 try/except 로 보호되어 단일 실패가 전체 캡처를 깨뜨리지 않는다.


def _read_metrics_events(metrics_path: str) -> list[dict]:
    """metrics.jsonl 의 모든 줄을 dict 리스트로 읽는다.

    각 줄은 jsonl 한 줄 = 한 JSON object. 파싱 실패 줄은 silently skip.

    Args:
        metrics_path: metrics.jsonl 절대 경로

    Returns:
        파싱 성공한 이벤트 dict 리스트. 파일이 없거나 비어있으면 빈 리스트.
    """
    if not os.path.isfile(metrics_path):
        return []
    events: list[dict] = []
    try:
        with open(metrics_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    events.append(obj)
    except Exception:
        return []
    return events


def _read_log_tail(log_path: str, max_bytes: int = 1024) -> str:
    """workflow.log 의 마지막 max_bytes 바이트를 텍스트로 읽는다.

    Args:
        log_path: workflow.log 절대 경로
        max_bytes: 꼬리에서 읽을 최대 바이트 수 (기본 1KB)

    Returns:
        디코딩된 꼬리 문자열. 파일이 없으면 빈 문자열.
    """
    if not os.path.isfile(log_path):
        return ""
    try:
        size = os.path.getsize(log_path)
        offset = max(0, size - max_bytes)
        with open(log_path, "rb") as f:
            f.seek(offset)
            data = f.read()
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _detect_worker_false_success(events: list[dict]) -> tuple[bool, str]:
    """worker_false_success 패턴 검출.

    subagent.end{outcome=ok} 이벤트가 1건 이상이고, 그 이벤트들 중
    가장 마지막 시점 이후로 tool.call{tool_name=Edit|Write} 카운트가
    0 이면 True 를 반환한다.

    Args:
        events: metrics.jsonl 이벤트 리스트 (등장 순서)

    Returns:
        (탐지 여부, signal_summary 텍스트)
    """
    subagent_ok_count: int = 0
    last_subagent_ok_idx: int = -1
    for idx, ev in enumerate(events):
        if ev.get("event_type") != "subagent.end":
            continue
        payload = ev.get("payload") or {}
        if isinstance(payload, dict) and payload.get("outcome") == "ok":
            subagent_ok_count += 1
            last_subagent_ok_idx = idx

    if subagent_ok_count == 0:
        return False, ""

    # 마지막 subagent.end{ok} 이후의 Edit/Write tool.call 카운트
    edit_write_after: int = 0
    for ev in events[last_subagent_ok_idx + 1 :]:
        if ev.get("event_type") != "tool.call":
            continue
        payload = ev.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        if payload.get("tool_name") in ("Edit", "Write"):
            edit_write_after += 1

    if edit_write_after == 0:
        summary = (
            f"subagent.end(ok) count={subagent_ok_count}, "
            f"Edit/Write tool.call after last subagent.end=0"
        )
        return True, summary
    return False, ""


def _detect_hook_deny(events: list[dict]) -> tuple[bool, str]:
    """hook_deny 패턴 검출.

    tool.deny 이벤트가 1건 이상이면 True.

    Args:
        events: metrics.jsonl 이벤트 리스트

    Returns:
        (탐지 여부, signal_summary)
    """
    deny_count: int = sum(1 for ev in events if ev.get("event_type") == "tool.deny")
    if deny_count >= 1:
        # 첫 deny 사유 추출 (signal_summary 가독성용)
        first_reason: str = ""
        for ev in events:
            if ev.get("event_type") == "tool.deny":
                payload = ev.get("payload") or {}
                if isinstance(payload, dict):
                    first_reason = str(payload.get("reason", ""))[:100]
                break
        summary = f"tool.deny count={deny_count}"
        if first_reason:
            summary += f", first_reason={first_reason!r}"
        return True, summary
    return False, ""


def _detect_empty_bash_card(events: list[dict]) -> tuple[bool, str]:
    """empty_bash_card 패턴 검출 (T-402 회귀).

    tool.call{tool_name=Bash, bytes_out=0} 이벤트가 1건 이상이면 True.

    Args:
        events: metrics.jsonl 이벤트 리스트

    Returns:
        (탐지 여부, signal_summary)
    """
    empty_count: int = 0
    for ev in events:
        if ev.get("event_type") != "tool.call":
            continue
        payload = ev.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        if payload.get("tool_name") != "Bash":
            continue
        if payload.get("bytes_out") == 0:
            empty_count += 1

    if empty_count >= 1:
        summary = f"tool.call(Bash, bytes_out=0) count={empty_count}"
        return True, summary
    return False, ""


def _detect_stage_header_leak(log_tail: str) -> tuple[bool, str]:
    """stage_header_leak 패턴 검출 (T-403 회귀).

    workflow.log 꼬리에 `[STEP]` 또는 `[PHASE]` 정규식이 매칭되면 True.

    Args:
        log_tail: workflow.log 의 마지막 꼬리 문자열

    Returns:
        (탐지 여부, signal_summary)
    """
    if not log_tail:
        return False, ""
    import re as _re

    # 단순 매칭 — 행 단위로 STEP/PHASE 헤더가 일반 출력 위치에 등장하는 패턴
    step_count: int = len(_re.findall(r"\[STEP\]", log_tail))
    phase_count: int = len(_re.findall(r"\[PHASE\]", log_tail))
    total: int = step_count + phase_count
    if total >= 1:
        summary = f"workflow.log tail contains [STEP]={step_count}, [PHASE]={phase_count}"
        return True, summary
    return False, ""


def _detect_worktree_commit_missing(abs_work_dir: str) -> tuple[bool, str]:
    """워크트리에 변경 >= 1 + commits ahead = 0 패턴 감지 (T-465 advisory detector).

    T-453 / T-457 워커 commit 누락 재현 패턴:
    - develop..HEAD commits ahead = 0  (커밋 없음)
    - git diff --name-only HEAD 변경 >= 1  (변경은 있음)

    Args:
        abs_work_dir: 워크트리 내 절대경로 (work_dir 또는 git 트리 내 경로)

    Returns:
        (True, detail): 회귀 패턴 감지
        (False, ""): 정상 또는 검사 불가

    Note:
        advisory only — status 전이 / kanban move / sentinel 생성 0건.
        subprocess 직접 호출 (worktree_manager import 금지 — finalization.py 독립성 캐논).
    """
    try:
        # git root 탐지 — abs_work_dir 가 git tree 내부라는 가정
        proc_root = subprocess.run(
            ["git", "-C", abs_work_dir, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc_root.returncode != 0:
            return (False, "")
        git_root = proc_root.stdout.strip()

        # commits ahead 측정 (develop..HEAD)
        proc_ahead = subprocess.run(
            ["git", "-C", git_root, "rev-list", "--count", "develop..HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc_ahead.returncode != 0:
            return (False, "")
        ahead = int(proc_ahead.stdout.strip())
        if ahead != 0:
            return (False, "")

        # 변경 파일 존재 여부 (HEAD 와 비교, staged + unstaged)
        proc_diff = subprocess.run(
            ["git", "-C", git_root, "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc_diff.returncode != 0:
            return (False, "")
        modified = [ln for ln in proc_diff.stdout.splitlines() if ln.strip()]
        if not modified:
            return (False, "")

        return (True, f"commits_ahead=0, modified_files={len(modified)}")
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return (False, "")


def _capture_regression_patterns(
    abs_work_dir: str | None,
    status: str,
    safe_metrics_event,
) -> None:
    """DONE 단계 진입 시 regression.pattern 5종 분류 휴리스틱 실행.

    metrics.jsonl 과 workflow.log 를 분석하여 5종 회귀 패턴 중 매칭되는
    모든 종류를 metrics.jsonl 에 append 한다. 분류 결과 0건이어도 정상.

    Args:
        abs_work_dir: 워크플로우 작업 디렉터리 절대 경로 (None 가능)
        status: 워크플로우 결과 상태 ("완료" 또는 "실패")
        safe_metrics_event: main() 안에서 정의된 비차단 metrics append 래퍼.
            시그니처 (work_dir, event_type, payload) -> None.

    분류 휴리스틱 (의사코드):
        events = read(metrics.jsonl)
        log_tail = read_tail(workflow.log, 1KB)
        detected = []
        if subagent.end(ok)≥1 and Edit/Write tool.call after last subagent.end == 0:
            detected.append("worker_false_success")
        if tool.deny ≥ 1:
            detected.append("hook_deny")
        if tool.call(Bash, bytes_out=0) ≥ 1:
            detected.append("empty_bash_card")
        if [STEP]/[PHASE] in log_tail:
            detected.append("stage_header_leak")
        if not detected and status == "실패":
            detected.append("other")
        for kind in detected:
            append regression.pattern{kind, signal_summary, last_log_tail}
    """
    if abs_work_dir is None:
        return

    metrics_path: str = os.path.join(abs_work_dir, "metrics.jsonl")
    log_path: str = os.path.join(abs_work_dir, "workflow.log")

    events: list[dict] = _read_metrics_events(metrics_path)
    log_tail: str = _read_log_tail(log_path, max_bytes=1024)

    # 5종 검출 휴리스틱 (각각 try/except 보호)
    detected: list[tuple[str, str]] = []  # [(kind, signal_summary), ...]

    detectors: list[tuple[str, "callable"]] = [
        ("worker_false_success", lambda: _detect_worker_false_success(events)),
        ("hook_deny", lambda: _detect_hook_deny(events)),
        ("empty_bash_card", lambda: _detect_empty_bash_card(events)),
        ("stage_header_leak", lambda: _detect_stage_header_leak(log_tail)),
        # NEW (T-465): 워크트리 commits ahead = 0 + diff >= 1 패턴 (워커 commit 누락)
        ("worktree_commit_missing", lambda: _detect_worktree_commit_missing(abs_work_dir)),
    ]
    for kind, detector in detectors:
        try:
            matched, summary = detector()
        except Exception as _exc:  # noqa: BLE001
            print(
                f"[WARN] regression detector({kind}) failed: {_exc}",
                file=sys.stderr,
            )
            continue
        if matched:
            detected.append((kind, summary))

    # other: 위 4종 0건 + status="실패"
    if not detected and status == "실패":
        detected.append(
            (
                "other",
                f"no specific pattern matched, status={status}, "
                f"events={len(events)}, log_tail_bytes={len(log_tail)}",
            )
        )

    # 검출 결과 0건이면 정상 (정상 워크플로우 종료) — 아무것도 append 하지 않는다
    if not detected:
        try:
            _append_log(
                abs_work_dir,
                "INFO",
                "FINALIZE_W04_REGRESSION: no pattern detected (clean run)",
            )
        except Exception:
            pass
        return

    # last_log_tail 은 4KB jsonl 줄 한도를 고려해 500자로 제한
    truncated_tail: str = log_tail[-500:] if log_tail else ""

    for kind, summary in detected:
        payload: dict = {
            "kind": kind,
            "signal_summary": summary[:500],
            "last_log_tail": truncated_tail,
        }
        safe_metrics_event(abs_work_dir, "regression.pattern", payload)
        try:
            _append_log(
                abs_work_dir,
                "INFO",
                f"FINALIZE_W04_REGRESSION: kind={kind} summary={summary[:200]}",
            )
        except Exception:
            pass


def _run_audit_hook(
    abs_work_dir: str,
    ticket_number: str | None,
    status: str,
) -> bool:
    """Step 4c-AUDIT — Auditor T3 LLM advisory hook (비차단).

    advisory only: verdict 결과가 어떤 칸반 전이/머지 흐름도 차단·강제하지 않는다.
    호출 실패 시 finalization 흐름 영향 0 — 모든 예외를 try/except 으로 감싸 WARN
    로그만 남기고 통과한다 (T-411 finalize AND-gate 폐지 캐논 인용).

    Skip 조건 — 아래 중 하나라도 해당하면 hook 자체를 호출하지 않는다 (디스패처가
    이미 status=='완료'/ticket_number 보장 시 호출):
      1. ``HOOK_AUDITOR_T3`` 환경변수가 'true' (대소문자 무시) 가 아닌 경우
      2. ``ticket_number`` 가 falsy (None / 빈 문자열) 인 경우
      3. ``status`` 가 '완료' 가 아닌 경우 (실패 워크플로우는 LLM 비용 회피)

    Args:
        abs_work_dir: 워크플로우 작업 디렉터리 절대 경로 (work_dir).
        ticket_number: 'T-NNN' 티켓 번호 또는 None.
        status: '완료' 또는 '실패'.

    Returns:
        True  — hook 이 실행되어 verdict 가 정상 산출된 경우.
        False — skip 또는 예외로 verdict 가 산출되지 못한 경우.
                어느 쪽이든 finalize 흐름은 비차단으로 통과한다.
    """
    if os.getenv("HOOK_AUDITOR_T3", "false").lower() != "true":
        return False
    if not ticket_number or status != "완료":
        return False

    model: str = os.getenv("AUDITOR_T3_MODEL", "sonnet")
    effort: str = os.getenv("AUDITOR_T3_EFFORT", "low")
    _append_log(
        abs_work_dir,
        "INFO",
        f"FINALIZE_STEP4C_AUDIT: ticket={ticket_number} model={model} effort={effort}",
    )

    try:
        # Local import — 비차단 캐논 보장 + auditor 패키지 import 실패도 finalize
        # 흐름에 영향 0. flow.auditor.runner 가 .claude-organic/engine/ 배치 (sys.path
        # 는 상단에서 등록 완료) 에 있으므로 정상 환경에서는 import 성공.
        from flow.auditor.runner import run_auditor

        verdict = run_auditor(
            abs_work_dir,
            model=model,
            effort=effort,
            ticket_id=ticket_number,
        )
    except Exception as exc:  # noqa: BLE001 — advisory only, 모든 예외 흡수
        _append_log(
            abs_work_dir,
            "WARN",
            f"FINALIZE_STEP4C_AUDIT_FAIL: ticket={ticket_number} error={type(exc).__name__}: {exc}",
        )
        return False

    _append_log(
        abs_work_dir,
        "INFO",
        (
            f"FINALIZE_STEP4C_AUDIT_DONE: ticket={ticket_number} "
            f"verdict={verdict.overall} tokens_in={verdict.tokens_in} "
            f"tokens_out={verdict.tokens_out} cost_usd={verdict.cost_usd} "
            f"duration_ms={verdict.duration_ms}"
        ),
    )
    return True


def main() -> None:
    """CLI 진입점. 인자 파싱 후 워크플로우 마무리 6단계를 순서대로 실행한다.

    6단계:
      1. status.json 완료 처리   (update_state.py status, 이미 대상 상태면 스킵, 그 외 실패 시 exit 1 — sync 포함)
      2. 사용량 확정             (update_state.py usage-finalize, 비차단)
      3. 아카이빙               (history_sync.py archive, 비차단)
      4. 티켓 상태 갱신          (kanban.py move -> review, ticket_number 있을 때만, 비차단. 자동 merge 금지)
      4c. 체인 감지 및 다음 스테이지 발사 (chain_launcher.py, 완료+체인 존재 시만, 비동기)
      5. tmux 윈도우 백그라운드 지연 kill (TMUX_PANE+T-* 조건 시만, 비차단)
    """
    parser = argparse.ArgumentParser(
        description="워크플로우 마무리 처리 (flow-finish 6단계)",
    )
    parser.add_argument("registryKey", help="워크플로우 식별자 (YYYYMMDD-HHMMSS)")
    parser.add_argument("status", choices=["완료", "실패"], help="워크플로우 결과 상태")
    parser.add_argument("--ticket-number", default=None, help="T-NNN 형식 티켓 번호 (선택)")
    parser.add_argument(
        "--worker-stdout",
        default=None,
        help="워커 반환 stdout (2줄 형식: 상태/커밋). advisory emit에만 사용. 기존 흐름 비차단."
    )

    args = parser.parse_args()

    registry_key: str = args.registryKey
    status: str = args.status
    ticket_number: str | None = args.ticket_number

    # ── W02: metrics 헬퍼 로드 (비차단) ──
    _metrics_mod = None
    try:
        import importlib.util as _ilu
        _metrics_py = os.path.join(PROJECT_ROOT, ".claude-organic", "engine", "flow", "metrics.py")
        if os.path.isfile(_metrics_py):
            _spec = _ilu.spec_from_file_location("flow.metrics", _metrics_py)
            if _spec and _spec.loader:
                _metrics_mod = _ilu.module_from_spec(_spec)
                _spec.loader.exec_module(_metrics_mod)  # type: ignore[attr-defined]
    except Exception as _me:
        print(f"[WARN] metrics module load failed: {_me}", file=sys.stderr)

    def _safe_metrics_event(work_dir: str | None, event_type: str, payload: dict) -> None:
        """비차단 metrics append 래퍼."""
        if _metrics_mod is None or work_dir is None:
            return
        try:
            _metrics_mod.append_event(work_dir, event_type, payload)  # type: ignore[attr-defined]
        except Exception as _exc:
            print(f"[WARN] metrics_event({event_type}) failed: {_exc}", file=sys.stderr)

    # ── Step 1: status.json 완료 처리 (critical) ──
    abs_work_dir: str | None = resolve_abs_work_dir(registry_key, PROJECT_ROOT)

    to_step: str = "DONE" if status == "완료" else "FAILED"

    # 이중 전이 방어: 이미 대상 상태이면 run() 호출 스킵
    # T-459: workflow_phase 단일 키. step/phase 는 legacy status.json (pre-T-459) 호환 read fallback.
    _step1_skip: bool = False
    if abs_work_dir is not None:
        _status_data = load_json_file(os.path.join(abs_work_dir, "status.json"))
        if _status_data is not None:
            _current_step = (
                _status_data.get("workflow_phase")
                or _status_data.get("step")   # legacy status.json (pre-T-459) 호환 read fallback
                or _status_data.get("phase")  # legacy status.json (pre-T-453) 호환 read fallback
            )
            if _current_step == to_step:
                print(f"[INFO] Step 1: already {to_step}, skipping status transition", file=sys.stderr, flush=True)
                _step1_skip = True

    if abs_work_dir is not None:
        _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP1: registryKey={registry_key} toStep={to_step}")

    # ── W04(T-435): DONE 단계 진입 step.start metrics (비차단) ──
    # 이중 emit 제거 (T-435 W04):
    #   - 정상 경로(_step1_skip=False): update_state.py FSM 전이가 step.start{DONE} emit 담당.
    #     finalization.py 는 emit하지 않음 (1회 보장).
    #   - 재진입 경로(_step1_skip=True): update_state.py 미호출이므로 finalization.py 가 직접 emit.
    # advisory only — 자동 차단/회귀 트리거 없음. T-411 폐기 사례 캐논 (commit 0c970fa) 준수.
    import time as _time_fin
    _done_start_ms = int(_time_fin.time() * 1000)
    if _step1_skip:
        # 이미 DONE 상태(재진입) — update_state.py 호출 안 됨, 직접 emit 필요
        # metric event 의 'step' 키는 status.json 'workflow_phase' 와 동일 의미 (metric event schema BC)
        _safe_metrics_event(
            abs_work_dir,
            "step.start",
            {"step": "DONE", "source": "fsm"},
        )

    if not _step1_skip:
        run(
            ["python3", UPDATE_STATE, "status", registry_key, to_step],
            "Step 1: status.json transition",
            critical=True,
        )

    if abs_work_dir is not None:
        _append_log(abs_work_dir, "INFO", f"Workflow finalized: {registry_key} ({status})")

    # ── W06(T-436): 워커 반환 advisory emit (비차단, 자동 강제 전이 0건) ──
    # --worker-stdout 인자가 있을 때만 파싱 후 commit 누락 시 WARN 로그만 emit한다.
    # 상태 강제 전이 / kanban move / finalization step skip 절대 금지 (MUST NOT).
    _worker_stdout: str | None = getattr(args, "worker_stdout", None)
    if _worker_stdout and abs_work_dir is not None:
        try:
            from flow.worker_return_parser import emit_commit_advisory, parse_worker_return
            _w_status, _w_commit = parse_worker_return(_worker_stdout)
            if _w_status is not None:
                emit_commit_advisory(registry_key, abs_work_dir, _w_status, _w_commit)
        except Exception as _adv_exc:
            # advisory 실패는 finalization 흐름을 깨뜨리지 않도록 흡수
            if abs_work_dir is not None:
                try:
                    _append_log(
                        abs_work_dir,
                        "WARN",
                        f"FINALIZE_W06_ADVISORY: parse/emit failed exc={_adv_exc}",
                    )
                except Exception:
                    pass

    # ── W03(T-447): REPORT 종료 후 report.md 디스크 존재 advisory (비차단) ──
    # status="완료"일 때만 호출 (실패 워크플로우는 report.md 부재가 정상이므로 노이즈 회피).
    # 강제 전이 / kanban move / step skip 절대 금지 (MUST NOT).
    # T-411 폐지 사례 참조(commit 0c970fa): 검증 자체가 아니라 자동 강제 전이가 문제.
    if status == "완료" and abs_work_dir is not None:
        _append_log(abs_work_dir, "INFO", "FINALIZE_REPORT_ADVISORY_START")
        try:
            from flow.worker_return_parser import emit_report_advisory  # noqa: PLC0415
            _report_abs = os.path.join(abs_work_dir, "report.md")
            emit_report_advisory(registry_key, abs_work_dir, _report_abs)
        except Exception as _rep_adv_exc:
            # advisory 실패는 finalization 흐름을 깨뜨리지 않도록 흡수
            if abs_work_dir is not None:
                try:
                    _append_log(
                        abs_work_dir,
                        "WARN",
                        f"FINALIZE_W03_ADVISORY: report.missing check failed exc={_rep_adv_exc}",
                    )
                except Exception:
                    pass
        _append_log(abs_work_dir, "INFO", "FINALIZE_REPORT_ADVISORY_END")

    # ── W04(T-435): DONE 단계 step.end metrics (비차단) ──
    # duration_ms 계산:
    #   - 정상 경로: update_state.py 가 생성한 .metrics_step_start_DONE.tmp 의 타임스탬프 사용
    #     (FSM 전이 emit 시점이 정확한 step.start 시점). 임시 파일은 step.end emit 후 정리.
    #   - 재진입 경로: 위에서 직접 emit 직전 기록한 _done_start_ms 사용.
    _done_end_ms = int(_time_fin.time() * 1000)
    _done_outcome = "ok" if status == "완료" else "fail"
    _start_ms_for_duration: int = _done_start_ms
    if not _step1_skip and abs_work_dir is not None:
        _done_tmp = os.path.join(abs_work_dir, ".metrics_step_start_DONE.tmp")
        if os.path.isfile(_done_tmp):
            try:
                _start_ms_for_duration = int(open(_done_tmp).read().strip())
                os.remove(_done_tmp)
            except Exception:
                pass
    # metric event 의 'step' 키는 status.json 'workflow_phase' 와 동일 의미 (metric event schema BC)
    _safe_metrics_event(
        abs_work_dir,
        "step.end",
        {
            "step": "DONE",
            "duration_ms": _done_end_ms - _start_ms_for_duration,
            "outcome": _done_outcome,
            "source": "fsm",
        },
    )

    # ── W04: 회귀 패턴 캡처 (regression.pattern, 비차단) ──
    # status / metrics.jsonl / workflow.log 분석 후 5종 분류 휴리스틱 적용.
    # 분류 결과 0건이어도 정상 (워크플로우 정상 종료 시).
    try:
        _capture_regression_patterns(
            abs_work_dir,
            status,
            _safe_metrics_event,
        )
    except Exception as _w04_exc:
        # 회귀 분류 실패가 finalization 흐름을 깨뜨리지 않도록 흡수
        if abs_work_dir is not None:
            try:
                _append_log(
                    abs_work_dir,
                    "WARN",
                    f"FINALIZE_W04_REGRESSION: capture failed exc={_w04_exc}",
                )
            except Exception:
                pass

    # ── Step 2: 사용량 확정 (비차단, status 무관) ──
    # Step 2a: JSONL 일괄 파싱 (usage_sync.py batch)
    transcript_path = _find_transcript_path(registry_key)
    if transcript_path:
        if abs_work_dir is not None:
            _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP2A: transcript=found path={transcript_path}")
        stdin_json = json.dumps({"agent_type": "orchestrator", "agent_transcript_path": transcript_path})
        run(
            ["python3", USAGE_SYNC, "batch"],
            "Step 2a: usage-sync batch",
            input_data=stdin_json,
        )
    else:
        if abs_work_dir is not None:
            # status=완료 인데 transcript 가 없으면 비정상 (사용량 집계 누락) → WARN 유지.
            # status=실패 / 짧은 디버그 워크플로우는 transcript 미생성이 정상이므로 INFO 로 강등 —
            # 로그 분석 (2026-04-29) 에서 102회 누적된 노이즈를 정상/비정상으로 분리한다.
            _level = "WARN" if status == "완료" else "INFO"
            _append_log(abs_work_dir, _level, "FINALIZE_STEP2A: transcript=not_found")

    # Step 2b: usage-finalize
    if abs_work_dir is not None:
        _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP2B: usage-finalize registryKey={registry_key}")
    run(
        ["python3", UPDATE_STATE, "usage-finalize", registry_key],
        "Step 2b: usage-finalize",
    )

    # ── Step 5: 로그/스킬 대시보드 갱신 (비차단) ──
    try:
        abs_work_dir = resolve_abs_work_dir(registry_key, PROJECT_ROOT)
        _update_logs_md(registry_key, abs_work_dir)
        if abs_work_dir is not None:
            # workflow.log 통계 수집 (로그 기록 전)
            _log_path = os.path.join(abs_work_dir, "workflow.log")
            _warn_count = 0
            _error_count = 0
            _hallu_count_log = 0
            if os.path.isfile(_log_path):
                try:
                    with open(_log_path, "r", encoding="utf-8", errors="replace") as _f:
                        _log_content = _f.read()
                    _warn_count = _log_content.count("[WARN]")
                    _error_count = _log_content.count("[ERROR]")
                    _hallu_count_log = _log_content.count("HALLUCINATION_SUSPECT")
                except Exception:
                    pass
            _append_log(abs_work_dir, "INFO", f"FINALIZE_LOGS_MD: registryKey={registry_key} warn={_warn_count} error={_error_count} hallu={_hallu_count_log}")
    except Exception:
        pass

    # ── Step 5b: 스킬 빈도 집계 갱신 (비차단) ──
    try:
        _update_skill_frequency()
        if abs_work_dir is not None:
            _append_log(abs_work_dir, "INFO", f"FINALIZE_SKILL_FREQ: registryKey={registry_key}")
    except Exception:
        pass

    # ── Step 5c: 태스크 성공/실패 통계 갱신 (비차단) ──
    try:
        _update_task_stats(registry_key, abs_work_dir)
        if abs_work_dir is not None:
            _append_log(abs_work_dir, "INFO", f"FINALIZE_TASK_STATS: registryKey={registry_key}")
    except Exception:
        pass

    # ── Step 5d: 단계별 소요 시간 집계 갱신 (비차단) ──
    try:
        _update_step_durations()
        if abs_work_dir is not None:
            _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP_DUR: registryKey={registry_key}")
    except Exception:
        pass

    # ── Step 3: 아카이빙 (비차단) ──
    if abs_work_dir is not None:
        _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP3: archive registryKey={registry_key}")
    run(
        ["python3", HISTORY_SYNC, "archive", registry_key],
        "Step 3: archive",
    )

    # ── Step 4: 티켓 상태 갱신 (ticket_number 있을 때만, 비차단) ──
    # T-455 Step 4: After failure_handler handles sentinel + retry-context (Steps 1-3),
    # finalization is responsible for termination only. This branch does NOT identify
    # the failure phase or make retry eligibility judgments — it simply moves the
    # ticket to the review column regardless of status.
    # status 무관 무조건 Review 로 보낸다 (회귀 정책 폐기).
    if ticket_number:
        target_column = "review"
        if abs_work_dir is not None:
            _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP4: kanban ticket={ticket_number} column={target_column}")
        run(
            ["python3", KANBAN_PY, "move", ticket_number, target_column],
            "Step 4: ticket status update",
        )

        # ── Step 4b: 결과 워크플로우 번호 기록 (완료 시만, 비차단) ──
        if status == "완료" and abs_work_dir is not None:
            # registry_key 명시 전달로 정규식 매치 실패 케이스 차단 (2026-04-29 보완,
            # "no workflow number" WARN 21회 누적된 회귀 해결).
            update_args = _build_result_update_args(abs_work_dir, registry_key=registry_key)
            if not update_args:
                _append_log(abs_work_dir, "WARN", f"FINALIZE_STEP4B: no workflow number in status.json ticket={ticket_number}, skipping result update")
            else:
                _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP4B: ticket={ticket_number} update_args={update_args}")
                run(
                    ["python3", KANBAN_PY, "update-result", ticket_number] + update_args,
                    "Step 4b: ticket result workflow update",
                )

    # ── Step 4c-AUDIT: Auditor T3 LLM judge advisory hook (비차단) ──
    # advisory only — verdict 결과가 어떤 칸반 전이/머지 흐름도 차단·강제 X.
    # 호출 실패 시 finalization 흐름 영향 0 (T-411 finalize AND-gate 폐지 캐논).
    # 활성화: HOOK_AUDITOR_T3=true (.claude-organic/.settings 또는 .env).
    if abs_work_dir is not None:
        try:
            _run_audit_hook(abs_work_dir, ticket_number, status)
        except Exception as _audit_exc:  # noqa: BLE001 — 2중 안전망
            _append_log(
                abs_work_dir,
                "WARN",
                f"FINALIZE_STEP4C_AUDIT_OUTER_FAIL: ticket={ticket_number} error={type(_audit_exc).__name__}: {_audit_exc}",
            )

    # ── Step 4wt: worktree 유지 (Review 단계, merge 금지) ──
    # worktree가 활성화된 경우, Review 상태에서 worktree를 유지한다.
    # 자동 커밋/merge/worktree 정리는 이 단계에서 절대 수행하지 않는다.
    # merge는 사용자의 명시적 완료 지시(/wf -d) 후 flow-merge로만 실행된다.
    # 정리 파이프라인: /wf -d -> 간단검토 -> 완료선택 -> flow-merge
    if ticket_number and abs_work_dir is not None:
        try:
            context_file_wt: str = os.path.join(abs_work_dir, ".context.json")
            context_wt = load_json_file(context_file_wt)
            if isinstance(context_wt, dict) and context_wt.get("worktree", {}).get("enabled"):
                wt_branch = context_wt["worktree"].get("featureBranch", "")
                wt_path = context_wt["worktree"].get("path", "")
                _append_log(
                    abs_work_dir,
                    "INFO",
                    f"FINALIZE_STEP4WT: worktree 유지 (Review 단계) branch={wt_branch} path={wt_path}",
                )
                print(
                    f"[INFO] worktree 유지: {wt_branch} (merge는 /wf -d 완료 지시 후 실행)",
                    file=sys.stderr,
                    flush=True,
                )
        except Exception:
            pass  # worktree 메타데이터 읽기 실패는 무시

    # ── Step 4wt-fb: 비-worktree 모드 originalBranch 복귀 훅 (T-370 C-2) ──
    # WORKFLOW_WORKTREE=false 또는 worktree 생성 실패로 비-worktree 모드인 경우,
    # 세션 종료 시 originalBranch로 메인 저장소 HEAD를 복귀시킨다.
    # 복귀 실패는 raise하지 않고 WARN 로그만 남긴다 (finalization 흐름 비차단).
    if abs_work_dir is not None:
        try:
            context_file_fb: str = os.path.join(abs_work_dir, ".context.json")
            context_fb = load_json_file(context_file_fb)
            if isinstance(context_fb, dict):
                wt_enabled_fb: bool = bool(
                    context_fb.get("worktree", {}).get("enabled", False)
                )
                original_branch_fb: str = context_fb.get("originalBranch", "")
                if not wt_enabled_fb and original_branch_fb:
                    restore = subprocess.run(
                        ["git", "checkout", original_branch_fb],
                        cwd=PROJECT_ROOT,
                        capture_output=True,
                        text=True,
                    )
                    if restore.returncode == 0:
                        _append_log(
                            abs_work_dir,
                            "INFO",
                            f"FINALIZE_BRANCH_RESTORE: HEAD -> {original_branch_fb}",
                        )
                    else:
                        _append_log(
                            abs_work_dir,
                            "WARN",
                            (
                                f"FINALIZE_BRANCH_RESTORE: failed "
                                f"(originalBranch={original_branch_fb}, "
                                f"stderr={restore.stderr.strip()})"
                            ),
                        )
                        print(
                            f"[WARN] 브랜치 복귀 실패: {original_branch_fb} "
                            f"(stderr={restore.stderr.strip()})",
                            file=sys.stderr,
                            flush=True,
                        )
        except Exception as restore_exc:
            _append_log(
                abs_work_dir,
                "WARN",
                f"FINALIZE_BRANCH_RESTORE: exception {restore_exc}",
            )

    # ── Step 4c: 체인 감지 및 다음 스테이지 발사 (비동기) ──
    # .context.json의 command에 ">" 구분자가 포함되면 체인으로 판별한다.
    # 현재 command(첫 세그먼트)를 제거한 나머지(remaining)가 있으면
    # chain_launcher.py를 비동기로 호출하여 다음 스테이지를 발사한다.
    _chain_launched: bool = False
    if status != "완료":
        _skip_msg = f"체인 발사 스킵: status가 '완료'가 아님 (status={status})"
        print(f"[INFO] Step 4c: {_skip_msg}", file=sys.stderr, flush=True)
        if abs_work_dir is not None:
            _append_log(abs_work_dir, "INFO", f"FINALIZE_CHAIN: {_skip_msg}")
    elif not ticket_number:
        _skip_msg = "체인 발사 스킵: ticket_number 미전달"
        print(f"[INFO] Step 4c: {_skip_msg}", file=sys.stderr, flush=True)
        if abs_work_dir is not None:
            _append_log(abs_work_dir, "INFO", f"FINALIZE_CHAIN: {_skip_msg}")
    elif abs_work_dir is None:
        _skip_msg = "체인 발사 스킵: abs_work_dir이 None"
        print(f"[INFO] Step 4c: {_skip_msg}", file=sys.stderr, flush=True)
    else:
        context_file: str = os.path.join(abs_work_dir, ".context.json")
        context_data = load_json_file(context_file)
        full_command: str = ""
        if isinstance(context_data, dict):
            full_command = context_data.get("command", "")

        if CHAIN_SEPARATOR not in full_command:
            _append_log(abs_work_dir, "INFO", f"FINALIZE_CHAIN: 체인 감지 안됨: command에 '>' 구분자 없음 (command={full_command!r})")

    if status == "완료" and ticket_number and abs_work_dir is not None:
        context_file = os.path.join(abs_work_dir, ".context.json")
        context_data = load_json_file(context_file)
        full_command = ""
        if isinstance(context_data, dict):
            full_command = context_data.get("command", "")

        if CHAIN_SEPARATOR in full_command:
            segments: list[str] = [s.strip() for s in full_command.split(CHAIN_SEPARATOR)]
            remaining_segments: list[str] = segments[1:]  # 첫 세그먼트(현재 command) 제거

            if remaining_segments:
                remaining_chain: str = CHAIN_SEPARATOR.join(remaining_segments)
                report_path: str = os.path.join(abs_work_dir, "report.md")

                if not os.path.isfile(report_path):
                    _append_log(abs_work_dir, "WARN", f"FINALIZE_CHAIN: report.md not found at {report_path}, using workdir as fallback")
                    report_path = abs_work_dir

                # bin wrapper 우선 (engine 직접 경로 의존 제거 — engine 역할 매핑
                # 분석 P2-3, 2026-04-29). wrapper 가 없으면 engine 스크립트로 폴백.
                if os.path.isfile(CHAIN_LAUNCH_WRAPPER) or os.path.isfile(CHAIN_LAUNCHER):
                    _append_log(
                        abs_work_dir,
                        "INFO",
                        f"FINALIZE_CHAIN: ticket={ticket_number} remaining={remaining_chain} prev_report={report_path}",
                    )
                    try:
                        _chain_log_path: str = os.path.join(abs_work_dir, "chain_launcher.log")
                        try:
                            _chain_log_fh = open(_chain_log_path, "a", encoding="utf-8")
                        except Exception:
                            _chain_log_fh = subprocess.DEVNULL  # type: ignore[assignment]
                        if os.path.isfile(CHAIN_LAUNCH_WRAPPER):
                            _chain_cmd = [
                                CHAIN_LAUNCH_WRAPPER,
                                ticket_number,
                                remaining_chain,
                                report_path,
                            ]
                        else:
                            _chain_cmd = [
                                "python3",
                                CHAIN_LAUNCHER,
                                ticket_number,
                                remaining_chain,
                                report_path,
                            ]
                        subprocess.Popen(
                            _chain_cmd,
                            stdout=subprocess.DEVNULL,
                            stderr=_chain_log_fh,
                            start_new_session=True,
                        )
                        _chain_launched = True
                        _append_log(abs_work_dir, "INFO", "FINALIZE_CHAIN: chain_launcher launched successfully")
                    except Exception as _chain_err:
                        _append_log(abs_work_dir, "ERROR", f"FINALIZE_CHAIN: launch error={_chain_err}")
                        print(f"[ERROR] Step 4c: chain_launcher.py 실행 실패: {_chain_err}", file=sys.stderr)
                        _ticket_num_str = (ticket_number or "").replace("T-", "").lstrip("0") or "N"
                        print(f"  수동으로 다음 스테이지를 시작하려면: /wf -s {_ticket_num_str}", file=sys.stderr)
                        print(f"  남은 체인: {remaining_chain}", file=sys.stderr)
                else:
                    _append_log(abs_work_dir, "WARN", f"FINALIZE_CHAIN: chain launcher not found (wrapper={CHAIN_LAUNCH_WRAPPER}, engine={CHAIN_LAUNCHER})")
                    print(f"[WARN] Step 4c: chain launcher not found (wrapper={CHAIN_LAUNCH_WRAPPER}, engine={CHAIN_LAUNCHER})", file=sys.stderr)
            else:
                if abs_work_dir is not None:
                    _append_log(abs_work_dir, "INFO", "FINALIZE_CHAIN: chain complete (no remaining segments)")

    # ── Step 5: 세션 백그라운드 지연 kill (비차단) ──
    # 체인이 발사된 경우, chain_launcher.py가 이전 세션 종료 대기 후
    # 새 세션을 생성하므로 여기서는 기존 로직대로 kill을 진행한다.
    #
    # 분기: _WF_SESSION_ID + _WF_SERVER_PORT 환경변수가 둘 다 존재하면
    #       HTTP API 경로, 그 외에는 기존 TMUX_PANE 기반 폴백을 유지한다.
    _wf_session_id: str | None = os.environ.get("_WF_SESSION_ID")
    _wf_server_port: str | None = os.environ.get("_WF_SERVER_PORT")

    if _wf_session_id and _wf_server_port:
        # ── HTTP API 경로: POST /terminal/workflow/kill ──
        def _http_kill_session(session_id: str, port: str, work_dir: str | None) -> None:
            """3초 지연 후 HTTP API로 세션 kill 요청을 보낸다."""
            time.sleep(3)
            url = f"http://127.0.0.1:{port}/terminal/workflow/kill"
            payload = json.dumps({"session_id": session_id}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    resp.read()
            except Exception:
                pass  # 비차단: kill 실패해도 프로세스 종료에 영향 없음

        if abs_work_dir is not None:
            _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP5: http_kill session_id={_wf_session_id}")
        t = threading.Thread(
            target=_http_kill_session,
            args=(_wf_session_id, _wf_server_port, abs_work_dir),
            daemon=True,
        )
        t.start()
    else:
        # ── TMUX 폴백 경로: 기존 TMUX_PANE 기반 kill ──
        if abs_work_dir is not None:
            _append_log(abs_work_dir, "INFO", "FINALIZE_STEP5: tmux_fallback_kill")
        tmux_pane: str | None = os.environ.get("TMUX_PANE")
        if tmux_pane:
            try:
                win_result = subprocess.run(
                    ["tmux", "display-message", "-t", tmux_pane, "-p", "#W"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                win_name: str = win_result.stdout.strip()
                if win_name.startswith(f"{WINDOW_PREFIX_P}T-"):
                    if abs_work_dir is not None:
                        _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP5: tmux_cleanup win={win_name} pane={tmux_pane} delay=3s")
                    pane_target: str = shlex.quote(tmux_pane)
                    bash_cmd: str = f"sleep 3 && tmux kill-window -t {pane_target}"
                    subprocess.Popen(
                        ["bash", "-c", bash_cmd],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                else:
                    if abs_work_dir is not None:
                        _append_log(abs_work_dir, "INFO", f"FINALIZE_STEP5: skip tmux_cleanup win={win_name!r} (not P:T-* prefix)")
            except Exception as _e:
                if abs_work_dir is not None:
                    _append_log(abs_work_dir, "WARN", f"FINALIZE_STEP5: tmux_cleanup error={_e}")
        else:
            if abs_work_dir is not None:
                _append_log(abs_work_dir, "INFO", "FINALIZE_STEP5: skip tmux_cleanup (TMUX_PANE not set)")

    print(f"[DONE] 워크플로우 {status}", flush=True)
    print(f"{registry_key}", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    main()
