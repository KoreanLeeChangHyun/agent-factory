#!/usr/bin/env -S python3 -u
"""워크플로우 상태 일괄 업데이트 스크립트.

update-state.sh에서 update_state.py로 1:1 포팅된 스크립트.
워크플로우 상태 전이, 컨텍스트 갱신, 사용량 기록 등을 처리한다.

사용법:
  update_state.py context <workDir> <agent>
  update_state.py status <workDir> <toPhase>
  update_state.py both <workDir> <agent> <toPhase>
  update_state.py link-session <workDir> <sessionId>
  update_state.py usage-pending <workDir> <id1> [id2] ...
  update_state.py usage <workDir> <agent_name> <input_tokens> <output_tokens> [cache_creation] [cache_read] [task_id]
  update_state.py usage-finalize <workDir>
  update_state.py usage-regenerate (no args)
  update_state.py env <workDir> set|unset <KEY> [VALUE]
  update_state.py task-status <workDir> <status> <id1> [id2] ...
  update_state.py task-status <workDir> <taskId> <status>  (레거시)
  update_state.py task-start <workDir> <id1> [id2] ...

종료 코드:
  항상 0 (비차단 원칙)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from typing import Any

# utils 패키지 import
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

HISTORY_SYNC_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sync", "history_sync.py")

from data.constants import FSM_TRANSITIONS, KST
from common import (
    C_BLUE,
    C_BOLD,
    C_CLAUDE,
    C_DIM,
    C_GRAY,
    C_GREEN,
    C_PURPLE,
    C_RED,
    C_RESET,
    STEP_COLORS,
    TS_PATTERN,
    atomic_write_json,
    extract_registry_key,
    load_json_file,
    resolve_abs_work_dir,
    resolve_project_root,
)

# 하위 호환 별칭
PHASE_COLORS = STEP_COLORS


def _print_state_banner(from_step: str, to_step: str, abs_work_dir: str = "") -> None:
    """상태 전이 배너를 2줄 포맷으로 출력한다.

    Args:
        from_step: 이전 단계 이름 (예: 'PLAN', 'WORK')
        to_step: 다음 단계 이름 (예: 'WORK', 'REPORT')
        abs_work_dir: 워크 디렉터리 절대 경로 (로그 기록용, 빈 문자열이면 로그 생략)
    """
    c_from = STEP_COLORS.get(from_step, C_GRAY)
    c_to = STEP_COLORS.get(to_step, C_GRAY)
    line1 = f"{C_CLAUDE}║ STATE:{C_RESET} {C_DIM}단계 변경{C_RESET}"
    line2 = (
        f"{C_CLAUDE}║{C_RESET} "
        f"{C_CLAUDE}>>{C_RESET} "
        f"{c_from}{from_step}{C_RESET} "
        f"{C_CLAUDE}->{C_RESET} "
        f"{c_to}{C_BOLD}{to_step}{C_RESET}"
    )
    print(line1, flush=True)
    print(line2, flush=True)
    if abs_work_dir:
        plain_line1 = re.sub(r'\x1b\[[0-9;]*m', '', line1)
        plain_line2 = re.sub(r'\x1b\[[0-9;]*m', '', line2)
        _append_log(abs_work_dir, "INFO", plain_line1)
        _append_log(abs_work_dir, "INFO", plain_line2)



# =============================================================================
# 경로 해석
# =============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = resolve_project_root()


def resolve_paths(work_dir_arg: str) -> tuple[str, str, str]:
    """workDir 인자를 절대 경로로 해석하고 관련 경로들을 반환한다.

    Args:
        work_dir_arg: 워크 디렉터리 인자 (registryKey 또는 절대 경로)

    Returns:
        (abs_work_dir, local_context, status_file) 3-tuple.
        abs_work_dir: 절대 경로로 해석된 워크 디렉터리,
        local_context: .context.json 경로,
        status_file: status.json 경로.
    """
    abs_work_dir = resolve_abs_work_dir(work_dir_arg, PROJECT_ROOT)
    local_context = os.path.join(abs_work_dir, ".context.json")
    status_file = os.path.join(abs_work_dir, "status.json")
    return abs_work_dir, local_context, status_file


# =============================================================================
# mkdir 기반 POSIX 잠금
# =============================================================================

def acquire_lock(lock_dir: str, max_wait: int = 5) -> bool:
    """mkdir 기반 POSIX 잠금을 획득한다. stale lock 감지 포함.

    Args:
        lock_dir: 잠금 디렉터리 경로
        max_wait: 최대 대기 횟수 (초 단위)

    Returns:
        잠금 획득 성공 시 True, 타임아웃 시 False.
    """
    waited = 0
    while True:
        try:
            os.makedirs(lock_dir)
            # PID + 타임스탬프 기록
            try:
                with open(os.path.join(lock_dir, "pid"), "w") as f:
                    f.write(f"{os.getpid()} {time.time()}")
            except OSError:
                pass
            return True
        except OSError:
            # stale lock 감지
            pid_file = os.path.join(lock_dir, "pid")
            if os.path.isfile(pid_file):
                try:
                    with open(pid_file, "r") as f:
                        pid_content = f.read().strip()
                    parts = pid_content.split()
                    lock_pid = int(parts[0])
                    lock_ts = float(parts[1]) if len(parts) > 1 else 0
                    # 프로세스가 존재하지 않으면 stale lock 제거
                    os.kill(lock_pid, 0)
                    # 프로세스는 존재하지만 max_wait초 이상 경과 시 stale로 판단
                    if lock_ts and (time.time() - lock_ts) > max_wait:
                        # 제거 전 PID 파일 재확인 (TOCTOU 방어)
                        try:
                            with open(pid_file, "r") as f:
                                recheck = f.read().strip()
                            if recheck == pid_content:
                                shutil.rmtree(lock_dir)
                                waited += 1
                                continue
                        except OSError:
                            pass
                except (ValueError, ProcessLookupError, OSError):
                    # PID 파일 재확인 후 제거 (TOCTOU 방어)
                    try:
                        with open(pid_file, "r") as f:
                            recheck = f.read().strip()
                        if recheck == pid_content:
                            shutil.rmtree(lock_dir)
                    except OSError:
                        pass
                    waited += 1
                    continue
                except PermissionError:
                    # 프로세스가 살아있지만 kill 권한 없음 → stale lock 아님, 대기
                    pass
            waited += 1
            if waited >= max_wait:
                return False
            time.sleep(1)


def release_lock(lock_dir: str) -> None:
    """잠금을 해제한다.

    Args:
        lock_dir: 잠금 디렉터리 경로
    """
    try:
        pid_file = os.path.join(lock_dir, "pid")
        if os.path.exists(pid_file):
            os.unlink(pid_file)
    except OSError:
        pass
    try:
        os.rmdir(lock_dir)
    except OSError:
        pass


def _append_log(abs_work_dir: str, level: str, message: str) -> None:
    """workflow.log에 로그 항목을 비차단 방식으로 append한다.

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로
        level: 로그 레벨 (예: 'INFO', 'WARN', 'ERROR', 'AUDIT')
        message: 로그 메시지
    """
    try:
        log_path = os.path.join(abs_work_dir, "workflow.log")
        timestamp = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")
    except Exception:
        pass


# =============================================================================
# context 업데이트
# =============================================================================

def update_context(local_context: str, agent: str) -> str:
    """context.json의 agent 필드만 갱신한다.

    Args:
        local_context: .context.json 파일 절대 경로
        agent: 설정할 에이전트 이름

    Returns:
        처리 결과 문자열. 예: 'context -> agent=orchestrator',
        'context -> skipped (file not found)', 'context -> failed'.
    """
    if not os.path.exists(local_context):
        print(f"[WARN] .context.json not found: {local_context}", file=sys.stderr)
        return "context -> skipped (file not found)"

    try:
        data = load_json_file(local_context)
        if data is None:
            print(f"[WARN] .context.json read failed: {local_context}", file=sys.stderr)
            return "context -> skipped (read failed)"

        data["agent"] = agent
        atomic_write_json(local_context, data)
        _append_log(os.path.dirname(local_context), "INFO", f"Context updated: agent={agent}")
        return f"context -> agent={agent}"
    except Exception as e:
        print(f"[WARN] .context.json update failed ({local_context}): {e}", file=sys.stderr)
        return "context -> failed"


# =============================================================================
# status 업데이트
# =============================================================================

def update_status(abs_work_dir: str, status_file: str, from_step: str, to_step: str) -> str:
    """status.json을 업데이트하고 registry step을 동기화한다.

    FSM 검증 로직:
      1. WORKFLOW_SKIP_GUARD=1 환경변수가 설정된 경우 검증을 건너뜀
      2. current_step 확인: status.json의 현재 step과 from_step이 일치하는지 검증
      3. allowed 확인: FSM_TRANSITIONS(constants.py)에서 현재 mode/from_step에 허용된
         대상 목록을 조회하고 to_step이 포함되어 있는지 검증

    비차단 원칙:
      FSM 검증 실패 시에도 프로세스를 종료하지 않음 (항상 exit 0).

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로
        status_file: status.json 파일 경로
        from_step: 전이 시작 단계 이름
        to_step: 전이 목표 단계 이름

    Returns:
        처리 결과 문자열. 예: 'status -> PLAN->WORK',
        'status -> FSM guard blocked (reason: ...)',
        'status -> skipped (file not found)', 'status -> failed'.
    """
    skip_guard = os.environ.get("WORKFLOW_SKIP_GUARD", "") == "1"

    if not os.path.exists(status_file):
        print(f"[WARN] status.json not found: {status_file}", file=sys.stderr)
        _append_log(abs_work_dir, "WARN", f"status.json not found: {status_file}")
        return "status -> skipped (file not found)"

    try:
        data = load_json_file(status_file)
        if data is None:
            print(f"[WARN] status.json read failed: {status_file}", file=sys.stderr)
            _append_log(abs_work_dir, "WARN", f"status.json read failed: {status_file}")
            return "status -> skipped (read failed)"

        # FSM 전이 검증
        if skip_guard:
            print(f"[AUDIT] WORKFLOW_SKIP_GUARD active: {from_step}->{to_step}", file=sys.stderr, flush=True)
            _append_log(abs_work_dir, "AUDIT", f"WORKFLOW_SKIP_GUARD active: {from_step}->{to_step}")
        else:
            current_step = data.get("step") or data.get("phase", "NONE")
            workflow_mode = data.get("mode", "full").lower()

            # allowed_targets는 두 검증 모두에서 에러 메시지에 필요하므로 미리 조회
            allowed_table = FSM_TRANSITIONS.get(
                workflow_mode, FSM_TRANSITIONS.get("full", {})
            )
            allowed = allowed_table.get(current_step, [])

            if from_step != current_step:
                print(
                    f"[ERROR] FSM guard: from_step mismatch. "
                    f"from_step={from_step}, to_step={to_step}, "
                    f"current_step={current_step}, workflow_mode={workflow_mode}, "
                    f"allowed_targets={allowed}. transition blocked.",
                    file=sys.stderr,
                )
                _append_log(
                    abs_work_dir, "ERROR",
                    f"FSM guard: from_step mismatch. from_step={from_step}, to_step={to_step}, "
                    f"current_step={current_step}, workflow_mode={workflow_mode}, "
                    f"allowed_targets={allowed}. transition blocked.",
                )
                return (
                    f"status -> FSM guard blocked "
                    f"(reason: from_step mismatch, expected={current_step}, got={from_step}, "
                    f"workflow_mode={workflow_mode}, allowed_targets={allowed})"
                )

            if to_step not in allowed:
                print(
                    f"[ERROR] FSM guard: illegal transition {from_step}->{to_step}. "
                    f"current_step={current_step}, workflow_mode={workflow_mode}, "
                    f"allowed_targets={allowed}. transition blocked.",
                    file=sys.stderr,
                )
                _append_log(
                    abs_work_dir, "ERROR",
                    f"FSM guard: illegal transition {from_step}->{to_step}. "
                    f"current_step={current_step}, workflow_mode={workflow_mode}, "
                    f"allowed_targets={allowed}. transition blocked.",
                )
                return (
                    f"status -> FSM guard blocked "
                    f"(reason: illegal transition {from_step}->{to_step}, "
                    f"workflow_mode={workflow_mode}, allowed_targets={allowed})"
                )

        # KST 시간
        kst = KST
        now = datetime.now(kst).strftime("%Y-%m-%dT%H:%M:%S+09:00")

        data["step"] = to_step
        data["updated_at"] = now

        if "transitions" not in data:
            data["transitions"] = []
        data["transitions"].append({"from": from_step, "to": to_step, "at": now})

        atomic_write_json(status_file, data)
        _append_log(abs_work_dir, "INFO", f"State transition: {from_step} -> {to_step}")

        # history_sync.py sync 호출 (비차단 원칙: 실패 시 경고만 출력)
        try:
            subprocess.run(
                ["python3", HISTORY_SYNC_PATH, "sync"],
                capture_output=True,
                timeout=30,
            )
        except Exception as e:
            print(f"[WARN] history sync failed: {e}", file=sys.stderr)
            _append_log(abs_work_dir, "WARN", f"history sync failed: {e}")

        # 반환값에는 ANSI 코드 없음 (배너는 _print_state_banner()가 담당)
        result = f"status -> {from_step}->{to_step}"
    except Exception as e:
        print(f"[WARN] status.json update failed: {e}", file=sys.stderr)
        _append_log(abs_work_dir, "WARN", f"status.json update failed: {e}")
        return "status -> failed"

    return result


# =============================================================================
# link-session
# =============================================================================

def link_session(status_file: str, session_id: str) -> str:
    """status.json의 linked_sessions 배열에 세션 ID를 추가한다.

    Args:
        status_file: status.json 파일 경로
        session_id: 등록할 Claude 세션 ID

    Returns:
        처리 결과 문자열. 예: 'link-session -> added: abc123 (total: 2)',
        'link-session -> already linked: abc123',
        'link-session -> skipped (empty)', 'link-session -> failed'.
    """
    if not session_id:
        print("[WARN] link-session: sessionId가 비어있어 무시합니다.", file=sys.stderr)
        return "link-session -> skipped (empty)"

    if not os.path.exists(status_file):
        print(f"[WARN] status.json not found: {status_file}", file=sys.stderr)
        return "link-session -> skipped (file not found)"

    try:
        data = load_json_file(status_file)
        if data is None:
            return "link-session -> skipped (read failed)"

        if "linked_sessions" not in data or not isinstance(data.get("linked_sessions"), list):
            data["linked_sessions"] = []

        if session_id in data["linked_sessions"]:
            return f"link-session -> already linked: {session_id}"

        data["linked_sessions"].append(session_id)
        atomic_write_json(status_file, data)
        count = len(data["linked_sessions"])
        _append_log(
            os.path.dirname(status_file),
            "INFO",
            f"SESSION_LINKED: sessionId={session_id} total={count}",
        )
        return f"link-session -> added: {session_id} (total: {count})"
    except Exception as e:
        print(f"[WARN] link-session failed: {e}", file=sys.stderr)
        return "link-session -> failed"


# =============================================================================
# task-status
# =============================================================================

def update_task_status(status_file: str, task_id: str, task_status: str) -> str:
    """status.json의 tasks 객체에 태스크 상태를 기록한다.

    Args:
        status_file: status.json 파일 경로
        task_id: 태스크 ID (예: 'W01', 'W02')
        task_status: 태스크 상태. 허용값: pending|running|completed|failed.
            in_progress는 running으로 자동 변환.

    Returns:
        처리 결과 문자열. 예: 'task-status -> W01: completed (updated_at: ...)',
        'task-status -> skipped (missing args)', 'task-status -> failed'.
    """
    if not task_id or not task_status:
        print("[WARN] task-status: task_id, status 인자가 필요합니다.", file=sys.stderr)
        return "task-status -> skipped (missing args)"

    STATUS_ALIASES = {"in_progress": "running"}
    task_status = STATUS_ALIASES.get(task_status, task_status)
    valid_statuses = {"pending", "running", "completed", "failed"}
    if task_status not in valid_statuses:
        print(
            f"[WARN] task-status: status는 pending|running|completed|failed 중 하나여야 합니다. (받은 값: {task_status})",
            file=sys.stderr,
        )
        return "task-status -> skipped (invalid status)"

    if not os.path.exists(status_file):
        print(f"[WARN] status.json not found: {status_file}", file=sys.stderr)
        return "task-status -> skipped (file not found)"

    try:
        data = load_json_file(status_file)
        if data is None:
            return "task-status -> skipped (read failed)"

        if "tasks" not in data or not isinstance(data.get("tasks"), dict):
            data["tasks"] = {}

        kst = KST
        now = datetime.now(kst).strftime("%Y-%m-%dT%H:%M:%S+09:00")

        data["tasks"][task_id] = {"status": task_status, "updated_at": now}
        atomic_write_json(status_file, data)

        # 상태별 구조화 로그 기록
        abs_work_dir_log = os.path.dirname(status_file)
        if task_status == "running":
            _append_log(abs_work_dir_log, "INFO", f"AGENT_DISPATCH: taskId={task_id}")
        elif task_status in {"completed", "failed"}:
            _append_log(abs_work_dir_log, "INFO", f"AGENT_RETURN: taskId={task_id} status={task_status}")

        return f"task-status -> {task_id}: {task_status} (updated_at: {now})"
    except Exception as e:
        print(f"[WARN] task-status failed: {e}", file=sys.stderr)
        return "task-status -> failed"


# =============================================================================
# usage-pending
# =============================================================================

def usage_pending(abs_work_dir: str, agent_id: str, task_id: str) -> str:
    """usage.json의 _pending_workers에 agent_id->taskId 매핑을 등록한다.

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로
        agent_id: 에이전트 ID (예: 'W01')
        task_id: 매핑할 태스크 ID (예: 'W01')

    Returns:
        처리 결과 문자열. 예: 'usage-pending -> W01=W01',
        'usage-pending -> skipped (missing args)', 'usage-pending -> lock failed'.
    """
    if not agent_id or not task_id:
        print("[WARN] usage-pending: agent_id, task_id 인자가 필요합니다.", file=sys.stderr)
        return "usage-pending -> skipped (missing args)"

    usage_file = os.path.join(abs_work_dir, "usage.json")
    lock_dir = usage_file + ".lockdir"

    if not acquire_lock(lock_dir):
        print("[WARN] usage-pending: 잠금 획득 실패", file=sys.stderr)
        return "usage-pending -> lock failed"

    try:
        data = load_json_file(usage_file)
        if not isinstance(data, dict):
            data = {}

        if "_pending_workers" not in data or not isinstance(data.get("_pending_workers"), dict):
            data["_pending_workers"] = {}

        data["_pending_workers"][agent_id] = task_id

        os.makedirs(os.path.dirname(usage_file), exist_ok=True)
        atomic_write_json(usage_file, data)
        _append_log(abs_work_dir, "INFO", f"USAGE_PENDING: agentId={agent_id} taskId={task_id}")
        return f"usage-pending -> {agent_id}={task_id}"
    finally:
        release_lock(lock_dir)


# =============================================================================
# usage
# =============================================================================

def usage_record(
    abs_work_dir: str,
    agent_name: str,
    input_tokens: int | str,
    output_tokens: int | str,
    cache_creation: int | str = 0,
    cache_read: int | str = 0,
    task_id: str = "",
) -> str:
    """usage.json의 agents 객체에 에이전트별 토큰 데이터를 기록한다.

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로
        agent_name: 에이전트 이름 (예: 'orchestrator', 'worker')
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수
        cache_creation: 캐시 생성 토큰 수 (기본값 0)
        cache_read: 캐시 읽기 토큰 수 (기본값 0)
        task_id: worker 에이전트의 태스크 ID (agent_name='worker'일 때만 사용)

    Returns:
        처리 결과 문자열. 예: 'usage -> orchestrator: in=1000 out=500 cc=0 cr=0',
        'usage -> workers.W01: in=2000 out=1000 cc=100 cr=50',
        'usage -> skipped (missing args)', 'usage -> lock failed'.
    """
    if not agent_name or input_tokens is None or output_tokens is None:
        print("[WARN] usage: agent_name, input_tokens, output_tokens 인자가 필요합니다.", file=sys.stderr)
        return "usage -> skipped (missing args)"

    usage_file = os.path.join(abs_work_dir, "usage.json")
    lock_dir = usage_file + ".lockdir"

    if not acquire_lock(lock_dir):
        print("[WARN] usage: 잠금 획득 실패", file=sys.stderr)
        return "usage -> lock failed"

    try:
        data = load_json_file(usage_file)
        if not isinstance(data, dict):
            data = {}

        if "agents" not in data or not isinstance(data.get("agents"), dict):
            data["agents"] = {}

        token_data = {
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "cache_creation_tokens": int(cache_creation),
            "cache_read_tokens": int(cache_read),
            "method": "subagent_transcript",
        }

        if agent_name == "worker" and task_id:
            if "workers" not in data["agents"] or not isinstance(data["agents"].get("workers"), dict):
                data["agents"]["workers"] = {}
            data["agents"]["workers"][task_id] = token_data
            label = f"workers.{task_id}"
        else:
            data["agents"][agent_name] = token_data
            label = agent_name

        os.makedirs(os.path.dirname(usage_file), exist_ok=True)
        atomic_write_json(usage_file, data)
        _append_log(abs_work_dir, "INFO", f"USAGE_RECORDED: agent={label}")
        return f"usage -> {label}: in={input_tokens} out={output_tokens} cc={cache_creation} cr={cache_read}"
    finally:
        release_lock(lock_dir)


# =============================================================================
# usage-finalize 헬퍼
# =============================================================================

def _calc_effective(d: dict[str, Any]) -> float:
    """토큰 데이터 dict에서 effective_tokens를 계산한다.

    Args:
        d: 토큰 데이터 딕셔너리 (input_tokens, output_tokens,
           cache_creation_tokens, cache_read_tokens 키 포함)

    Returns:
        가중 합산된 effective_tokens 값.
    """
    return (
        d.get("input_tokens", 0)
        + d.get("output_tokens", 0) * 5
        + d.get("cache_creation_tokens", 0) * 1.25
        + d.get("cache_read_tokens", 0) * 0.1
    )


def _sum_tokens(agents_list: list[dict[str, Any]]) -> dict[str, int]:
    """에이전트 토큰 데이터 리스트의 합계를 반환한다.

    Args:
        agents_list: 토큰 데이터 딕셔너리 목록

    Returns:
        input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens
        합산 딕셔너리.
    """
    totals = {"input_tokens": 0, "output_tokens": 0, "cache_creation_tokens": 0, "cache_read_tokens": 0}
    for a in agents_list:
        for k in totals:
            totals[k] += a.get(k, 0)
    return totals


def _to_k(n: float | int) -> str:
    """숫자를 k 단위 문자열로 변환한다. 0이면 '-'.

    Args:
        n: 변환할 숫자

    Returns:
        k 단위 문자열 (예: '10k', '-').
    """
    return "-" if n == 0 else f"{int(n) // 1000}k"


def _to_k_precise(n: float | int) -> str:
    """숫자를 소수점 1자리 k 단위 문자열로 변환한다. 0이면 '-'.

    Args:
        n: 변환할 숫자

    Returns:
        소수점 1자리 k 단위 문자열 (예: '10.5k', '-').
    """
    return "-" if n == 0 else f"{n / 1000:.1f}k"


def _update_usage_md(row: str, eff_weighted: float) -> str | None:
    """.dashboard/.usage.md 파일에 사용량 행을 삽입한다.

    Args:
        row: 삽입할 마크다운 테이블 행 문자열 (11컬럼 스키마)
        eff_weighted: 가중 합산 effective_tokens (경고 메시지 생성용)

    Returns:
        성공 시 None, 실패 시 에러 결과 문자열.
    """
    usage_md = os.path.join(PROJECT_ROOT, ".dashboard", ".usage.md")
    marker = "<!-- 새 항목은 이 줄 아래에 추가됩니다 -->"
    header_line = "| 날짜 | 작업ID | 제목 | 명령 | ORC | PLN | WRK | EXP | VAL | RPT | 합계 |"
    separator_line = "|------|--------|------|------|-----|-----|-----|-----|-----|-----|------|"

    content = ""
    if os.path.exists(usage_md):
        with open(usage_md, "r", encoding="utf-8") as f:
            content = f.read()

    if marker not in content:
        content = f"# 워크플로우 사용량 추적\n\n{marker}\n\n{header_line}\n{separator_line}\n"

    # row 컬럼 수 검증: 11컬럼이 아니면 삽입하지 않음
    if row.count("|") - 1 != 11:
        print(
            f"[WARN] usage-finalize: row column count mismatch (expected 11, got {row.count('|') - 1}). row insertion skipped.",
            file=sys.stderr,
        )
        return f"usage-finalize -> totals: eff={_to_k_precise(eff_weighted)}, usage.md skipped (column mismatch)"

    if separator_line in content:
        marker_pos = content.find(marker)
        if marker_pos >= 0:
            sep_pos = content.find(separator_line, marker_pos)
            if sep_pos >= 0:
                insert_pos = sep_pos + len(separator_line)
                if insert_pos < len(content) and content[insert_pos] == "\n":
                    insert_pos += 1
                content = content[:insert_pos] + row + "\n" + content[insert_pos:]
            else:
                content = content.replace(
                    marker, f"{marker}\n\n{header_line}\n{separator_line}\n{row}"
                )
        else:
            content = content.replace(
                marker, f"{marker}\n\n{header_line}\n{separator_line}\n{row}"
            )
    else:
        content = content.replace(
            marker, f"{marker}\n\n{header_line}\n{separator_line}\n{row}"
        )

    os.makedirs(os.path.dirname(usage_md), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(usage_md), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        shutil.move(tmp, usage_md)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

    return None  # 성공


# =============================================================================
# usage-finalize
# =============================================================================

def usage_finalize(abs_work_dir: str) -> str:
    """totals를 계산하고 effective_tokens를 산출하여 .dashboard/.usage.md에 행을 추가한다.

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로 (usage.json이 위치하는 디렉터리)

    Returns:
        처리 결과 문자열. 예: 'usage-finalize -> totals: eff=12.5k, usage.md updated',
        'usage-finalize -> skipped (file not found)', 'usage-finalize -> failed'.
    """
    usage_file = os.path.join(abs_work_dir, "usage.json")
    if not os.path.isfile(usage_file):
        print(f"[WARN] usage-finalize: usage.json not found: {usage_file}", file=sys.stderr)
        return "usage-finalize -> skipped (file not found)"

    try:
        data = load_json_file(usage_file)
        if not isinstance(data, dict):
            return "usage-finalize -> skipped (invalid format)"

        # $schema 가드: usage-v2가 아니면 마이그레이션
        if data.get("$schema") != "usage-v2":
            data.pop("init", None)
            data.pop("done", None)
            data["$schema"] = "usage-v2"

        agents = data.get("agents", {})

        # 모든 에이전트 토큰 데이터 수집
        all_agents = []
        for key in ["orchestrator", "planner", "explorer", "validator", "reporter"]:
            if key in agents and isinstance(agents[key], dict):
                all_agents.append(agents[key])

        workers = agents.get("workers", {})
        if isinstance(workers, dict):
            for w in workers.values():
                if isinstance(w, dict):
                    all_agents.append(w)

        # totals 계산
        totals = _sum_tokens(all_agents)
        totals["effective_tokens"] = _calc_effective(totals)
        data["totals"] = totals

        atomic_write_json(usage_file, data)

        # registryKey 추출
        registry_key = extract_registry_key(abs_work_dir)

        # .context.json에서 메타데이터 조회
        reg_title = ""
        reg_command = ""
        ctx_file = os.path.join(abs_work_dir, ".context.json")
        ctx_data = load_json_file(ctx_file)
        if isinstance(ctx_data, dict):
            reg_title = ctx_data.get("title", "")
            reg_command = ctx_data.get("command", "")

        title = reg_title[:30] if reg_title else ""

        # 날짜 추출
        date_str = ""
        if len(registry_key) >= 15:
            try:
                date_str = f"{registry_key[4:6]}-{registry_key[6:8]} {registry_key[9:11]}:{registry_key[11:13]}"
            except Exception:
                date_str = registry_key

        # 에이전트별 effective_tokens
        orch_eff = _calc_effective(agents.get("orchestrator", {})) if "orchestrator" in agents else 0
        plan_eff = _calc_effective(agents.get("planner", {})) if "planner" in agents else 0
        work_eff = (
            sum(_calc_effective(w) for w in workers.values() if isinstance(w, dict))
            if isinstance(workers, dict)
            else 0
        )
        exp_eff = _calc_effective(agents.get("explorer", {})) if "explorer" in agents else 0
        val_eff = _calc_effective(agents.get("validator", {})) if "validator" in agents else 0
        report_eff = _calc_effective(agents.get("reporter", {})) if "reporter" in agents else 0
        total_eff = orch_eff + plan_eff + work_eff + exp_eff + val_eff + report_eff
        eff_weighted = totals.get("effective_tokens", total_eff)

        # usage.md 행 생성 (11칼럼 스키마: 날짜|작업ID|제목|명령|ORC|PLN|WRK|EXP|VAL|RPT|합계)
        row = (
            f"| {date_str} "
            f"| {registry_key} "
            f"| {title} "
            f"| {reg_command} "
            f"| {_to_k(orch_eff)} "
            f"| {_to_k(plan_eff)} "
            f"| {_to_k(work_eff)} "
            f"| {_to_k(exp_eff)} "
            f"| {_to_k(val_eff)} "
            f"| {_to_k(report_eff)} "
            f"| {_to_k(total_eff)} |"
        )

        # .dashboard/.usage.md 갱신
        md_err = _update_usage_md(row, eff_weighted)
        if md_err is not None:
            return md_err

        return f"usage-finalize -> totals: eff={_to_k_precise(eff_weighted)}, usage.md updated"
    except Exception as e:
        print(f"[WARN] usage-finalize failed: {e}", file=sys.stderr)
        return "usage-finalize -> failed"


# =============================================================================
# env 관리
# =============================================================================

def env_manage(action: str, key: str, value: str = "") -> str:
    """claude.env 파일의 환경 변수를 관리한다.

    Args:
        action: 수행할 동작. 허용값: 'set', 'unset'.
        key: 환경 변수 키. HOOK_* 또는 GUARD_* 접두사, 또는 HOOKS_EDIT_ALLOWED만 허용.
        value: 설정할 값 (action='set'일 때 필수)

    Returns:
        처리 결과 문자열. 예: 'env -> set HOOK_FOO=bar',
        'env -> unset GUARD_BAR', 'env -> skipped (missing args)', 'env -> failed'.
    """
    if not action or not key:
        print("[WARN] env: action(set|unset)과 KEY 인자가 필요합니다.", file=sys.stderr)
        return "env -> skipped (missing args)"

    if action not in ("set", "unset"):
        print(f"[WARN] env: action은 set 또는 unset만 허용됩니다. got={action}", file=sys.stderr)
        return "env -> skipped (invalid action)"

    if action == "set" and not value:
        print("[WARN] env: set 명령에는 VALUE 인자가 필요합니다.", file=sys.stderr)
        return "env -> skipped (missing value)"

    # KEY 화이트리스트 검증
    if not key.startswith("HOOK_") and not key.startswith("GUARD_") and key != "HOOKS_EDIT_ALLOWED":
        print(f"[WARN] env: 허용되지 않는 KEY입니다: {key} (허용: HOOK_*, GUARD_* 접두사)", file=sys.stderr)
        return "env -> skipped (disallowed key)"

    env_file = os.path.join(PROJECT_ROOT, ".claude.env")
    if not os.path.isfile(env_file):
        print(f"[WARN] env: .claude.env not found: {env_file}", file=sys.stderr)
        return "env -> skipped (file not found)"

    try:
        with open(env_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if action == "set":
            found = False
            new_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith(key + "="):
                    new_lines.append(f"{key}={value}\n")
                    found = True
                else:
                    new_lines.append(line)

            if not found:
                if new_lines and not new_lines[-1].endswith("\n"):
                    new_lines[-1] += "\n"
                new_lines.append(f"{key}={value}\n")

            lines = new_lines
            label = f"env -> set {key}={value}"

        elif action == "unset":
            new_lines = []
            i = 0
            while i < len(lines):
                stripped = lines[i].strip()
                if stripped.startswith(key + "="):
                    if new_lines and new_lines[-1].strip().startswith("#"):
                        new_lines.pop()
                    i += 1
                    continue
                new_lines.append(lines[i])
                i += 1

            lines = new_lines
            label = f"env -> unset {key}"

        # 원자적 쓰기
        dir_name = os.path.dirname(env_file)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.writelines(lines)
            shutil.move(tmp_path, env_file)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        return label
    except Exception as e:
        print(f"[WARN] env failed: {e}", file=sys.stderr)
        return "env -> failed"


# =============================================================================
# 메인
# =============================================================================

_VALID_MODES = frozenset({
    "context", "status", "both", "link-session",
    "usage-pending", "usage", "usage-finalize", "usage-regenerate", "env", "task-status", "task-start",
})


# =============================================================================
# 디스패처 핸들러 함수
# =============================================================================

def _handle_context(abs_work_dir: str, local_context: str, status_file: str) -> tuple[str | None, str | None, bool]:
    """context 모드 핸들러.

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로
        local_context: .context.json 파일 경로
        status_file: status.json 파일 경로

    Returns:
        (banner_from, banner_to, banner_ok) 3-tuple.
        context 모드는 배너를 출력하지 않으므로 (None, None, False) 반환.
    """
    agent = sys.argv[3] if len(sys.argv) > 3 else ""
    if not agent:
        print("[WARN] context 모드: agent 인자가 필요합니다.", file=sys.stderr)
        sys.exit(0)
    update_context(local_context, agent)
    return None, None, False


def _handle_status(abs_work_dir: str, local_context: str, status_file: str) -> tuple[str | None, str | None, bool]:
    """status 모드 핸들러.

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로
        local_context: .context.json 파일 경로
        status_file: status.json 파일 경로

    Returns:
        (banner_from, banner_to, banner_ok) 3-tuple.
        전이 성공 시 (from_step, to_step, True), 실패/스킵 시 (from_step, to_step, False).
    """
    to_step = sys.argv[3] if len(sys.argv) > 3 else ""
    if not to_step:
        print("[WARN] status 모드: toPhase 인자가 필요합니다.", file=sys.stderr)
        sys.exit(0)
    _data = load_json_file(status_file) if os.path.isfile(status_file) else None
    from_step = (_data.get("step") or _data.get("phase", "NONE")) if isinstance(_data, dict) else "NONE"
    result = update_status(abs_work_dir, status_file, from_step, to_step)
    banner_ok = not any(x in result for x in ("blocked", "skipped", "failed"))
    return from_step, to_step, banner_ok


def _handle_both(abs_work_dir: str, local_context: str, status_file: str) -> tuple[str | None, str | None, bool]:
    """both 모드 핸들러. context 갱신과 status 전이를 함께 수행한다.

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로
        local_context: .context.json 파일 경로
        status_file: status.json 파일 경로

    Returns:
        (banner_from, banner_to, banner_ok) 3-tuple.
        전이 성공 시 (from_step, to_step, True), 실패/스킵 시 (from_step, to_step, False).
    """
    agent = sys.argv[3] if len(sys.argv) > 3 else ""
    to_step = sys.argv[4] if len(sys.argv) > 4 else ""
    if not agent or not to_step:
        print("[WARN] both 모드: agent, toPhase 인자가 필요합니다.", file=sys.stderr)
        sys.exit(0)
    _data = load_json_file(status_file) if os.path.isfile(status_file) else None
    from_step = (_data.get("step") or _data.get("phase", "NONE")) if isinstance(_data, dict) else "NONE"
    update_context(local_context, agent)
    result = update_status(abs_work_dir, status_file, from_step, to_step)
    banner_ok = not any(x in result for x in ("blocked", "skipped", "failed"))
    if banner_ok:
        _append_log(abs_work_dir, "INFO", f"STATE_BOTH: agent={agent} step={from_step}->{to_step}")
    return from_step, to_step, banner_ok


def _handle_link_session(abs_work_dir: str, local_context: str, status_file: str) -> tuple[str | None, str | None, bool]:
    """link-session 모드 핸들러.

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로
        local_context: .context.json 파일 경로
        status_file: status.json 파일 경로

    Returns:
        (None, None, False) - 배너 출력 없음.
    """
    session_id = sys.argv[3] if len(sys.argv) > 3 else ""
    if not session_id:
        print("[WARN] link-session 모드: sessionId 인자가 필요합니다.", file=sys.stderr)
        sys.exit(0)
    link_session(status_file, session_id)
    return None, None, False


def _handle_usage_pending(abs_work_dir: str, local_context: str, status_file: str) -> tuple[str | None, str | None, bool]:
    """usage-pending 모드 핸들러.

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로
        local_context: .context.json 파일 경로
        status_file: status.json 파일 경로

    Returns:
        (None, None, False) - 배너 출력 없음.
    """
    task_ids = sys.argv[3:]
    if not task_ids:
        print("[WARN] usage-pending 모드: task_id 인자가 필요합니다.", file=sys.stderr)
        sys.exit(0)
    seen = set()
    for tid in task_ids:
        if tid not in seen:
            seen.add(tid)
            usage_pending(abs_work_dir, tid, tid)
    return None, None, False


def _handle_usage(abs_work_dir: str, local_context: str, status_file: str) -> tuple[str | None, str | None, bool]:
    """usage 모드 핸들러.

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로
        local_context: .context.json 파일 경로
        status_file: status.json 파일 경로

    Returns:
        (None, None, False) - 배너 출력 없음.
    """
    agent_name = sys.argv[3] if len(sys.argv) > 3 else ""
    input_tokens = sys.argv[4] if len(sys.argv) > 4 else ""
    output_tokens = sys.argv[5] if len(sys.argv) > 5 else ""
    cache_creation = sys.argv[6] if len(sys.argv) > 6 else "0"
    cache_read = sys.argv[7] if len(sys.argv) > 7 else "0"
    task_id_arg = sys.argv[8] if len(sys.argv) > 8 else ""
    if not agent_name or not input_tokens or not output_tokens:
        print("[WARN] usage 모드: agent_name, input_tokens, output_tokens 인자가 필요합니다.", file=sys.stderr)
        sys.exit(0)
    usage_record(abs_work_dir, agent_name, input_tokens, output_tokens, cache_creation, cache_read, task_id_arg)
    return None, None, False


def _handle_usage_finalize(abs_work_dir: str, local_context: str, status_file: str) -> tuple[str | None, str | None, bool]:
    """usage-finalize 모드 핸들러.

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로
        local_context: .context.json 파일 경로
        status_file: status.json 파일 경로

    Returns:
        (None, None, False) - 배너 출력 없음.
    """
    usage_finalize(abs_work_dir)
    return None, None, False


# =============================================================================
# usage-regenerate: .usage.md 레거시 행 전체 재생성
# =============================================================================

def usage_regenerate() -> str:
    """.workflow/ 및 .workflow/.history/ 하위의 모든 usage.json을 순회하여 .dashboard/.usage.md를 재생성한다.

    v2 스키마 행을 전체 재생성한다.
    registryKey를 날짜 내림차순으로 정렬하여 최신 항목이 상단에 오도록 배치한다.

    Returns:
        처리 결과 문자열. 예: 'usage-regenerate -> rows regenerated: 10',
        'usage-regenerate -> failed'.
    """
    try:
        # 레거시 행 데이터 수집
        rows_data = []  # (registry_key, date_str, title, command, orch_eff, plan_eff, work_eff, exp_eff, val_eff, report_eff, total_eff)

        workflow_base = os.path.join(PROJECT_ROOT, ".workflow")
        workflow_history = os.path.join(workflow_base, ".history")

        dirs_to_scan = []
        if os.path.isdir(workflow_base):
            for entry in os.listdir(workflow_base):
                entry_path = os.path.join(workflow_base, entry)
                if os.path.isdir(entry_path) and entry != ".history":
                    dirs_to_scan.append(entry_path)

        if os.path.isdir(workflow_history):
            for entry in os.listdir(workflow_history):
                entry_path = os.path.join(workflow_history, entry)
                if os.path.isdir(entry_path):
                    dirs_to_scan.append(entry_path)

        # 각 워크플로우 디렉터리에서 usage.json과 .context.json 읽기
        for workflow_dir in dirs_to_scan:
            usage_file = os.path.join(workflow_dir, "usage.json")
            context_file = os.path.join(workflow_dir, ".context.json")

            if not os.path.isfile(usage_file):
                continue

            try:
                usage_data = load_json_file(usage_file)
                context_data = load_json_file(context_file) if os.path.isfile(context_file) else {}

                if not isinstance(usage_data, dict):
                    continue

                # v2 스키마 확인
                if usage_data.get("$schema") != "usage-v2":
                    continue

                # registryKey 추출
                try:
                    registry_key = extract_registry_key(workflow_dir)
                except Exception:
                    continue

                # .context.json에서 메타데이터 추출
                title = context_data.get("title", "")[:30] if isinstance(context_data, dict) else ""
                command = context_data.get("command", "") if isinstance(context_data, dict) else ""

                # 날짜 추출
                date_str = ""
                if len(registry_key) >= 15:
                    try:
                        date_str = f"{registry_key[4:6]}-{registry_key[6:8]} {registry_key[9:11]}:{registry_key[11:13]}"
                    except Exception:
                        date_str = registry_key

                # 에이전트별 effective_tokens 계산
                agents = usage_data.get("agents", {})
                orch_eff = _calc_effective(agents.get("orchestrator", {})) if "orchestrator" in agents else 0
                plan_eff = _calc_effective(agents.get("planner", {})) if "planner" in agents else 0
                workers = agents.get("workers", {})
                work_eff = (
                    sum(_calc_effective(w) for w in workers.values() if isinstance(w, dict))
                    if isinstance(workers, dict)
                    else 0
                )
                exp_eff = _calc_effective(agents.get("explorer", {})) if "explorer" in agents else 0
                val_eff = _calc_effective(agents.get("validator", {})) if "validator" in agents else 0
                report_eff = _calc_effective(agents.get("reporter", {})) if "reporter" in agents else 0
                total_eff = orch_eff + plan_eff + work_eff + exp_eff + val_eff + report_eff

                rows_data.append((registry_key, date_str, title, command, orch_eff, plan_eff, work_eff, exp_eff, val_eff, report_eff, total_eff))

            except Exception:
                # 비차단 원칙: 개별 usage.json 파싱 실패해도 계속 진행
                continue

        # registryKey 날짜 내림차순 정렬 (최신이 상단)
        rows_data.sort(key=lambda x: x[0], reverse=True)

        # .dashboard/.usage.md 읽기
        usage_md = os.path.join(PROJECT_ROOT, ".dashboard", ".usage.md")
        content = ""
        if os.path.isfile(usage_md):
            with open(usage_md, "r", encoding="utf-8") as f:
                content = f.read()

        # 마커와 헤더/분리선 정의
        marker = "<!-- 새 항목은 이 줄 아래에 추가됩니다 -->"
        header_line = "| 날짜 | 작업ID | 제목 | 명령 | ORC | PLN | WRK | EXP | VAL | RPT | 합계 |"
        separator_line = "|------|--------|------|------|-----|-----|-----|-----|-----|-----|------|"

        # <details> 아카이브 섹션 추출 및 보존
        archive_section = ""
        if "<details>" in content:
            details_start = content.find("<details>")
            archive_section = content[details_start:]

        # 새로운 v2 테이블 행 생성
        new_rows = []
        for reg_key, date_str, title, command, orch_eff, plan_eff, work_eff, exp_eff, val_eff, report_eff, total_eff in rows_data:
            row = (
                f"| {date_str} "
                f"| {reg_key} "
                f"| {title} "
                f"| {command} "
                f"| {_to_k(orch_eff)} "
                f"| {_to_k(plan_eff)} "
                f"| {_to_k(work_eff)} "
                f"| {_to_k(exp_eff)} "
                f"| {_to_k(val_eff)} "
                f"| {_to_k(report_eff)} "
                f"| {_to_k(total_eff)} |"
            )
            new_rows.append(row)

        # 새로운 콘텐츠 구성
        new_content = f"# 워크플로우 사용량 추적\n\n{marker}\n\n{header_line}\n{separator_line}\n"
        for row in new_rows:
            new_content += row + "\n"

        # 아카이브 섹션 추가 (있으면)
        if archive_section:
            new_content += "\n" + archive_section

        # .usage.md 원자적 갱신
        os.makedirs(os.path.dirname(usage_md), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(usage_md), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(new_content)
            shutil.move(tmp, usage_md)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

        return f"usage-regenerate -> rows regenerated: {len(new_rows)}"

    except Exception as e:
        print(f"[WARN] usage-regenerate failed: {e}", file=sys.stderr)
        return "usage-regenerate -> failed"


def _handle_usage_regenerate(abs_work_dir: str, local_context: str, status_file: str) -> tuple[str | None, str | None, bool]:
    """usage-regenerate 모드 핸들러.

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로
        local_context: .context.json 파일 경로
        status_file: status.json 파일 경로

    Returns:
        (None, None, False) - 배너 출력 없음.
    """
    usage_regenerate()
    return None, None, False


def _handle_env(abs_work_dir: str, local_context: str, status_file: str) -> tuple[str | None, str | None, bool]:
    """env 모드 핸들러.

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로
        local_context: .context.json 파일 경로
        status_file: status.json 파일 경로

    Returns:
        (None, None, False) - 배너 출력 없음.
    """
    action = sys.argv[3] if len(sys.argv) > 3 else ""
    key = sys.argv[4] if len(sys.argv) > 4 else ""
    value = sys.argv[5] if len(sys.argv) > 5 else ""
    if not action or not key:
        print("[WARN] env 모드: action(set|unset), KEY 인자가 필요합니다.", file=sys.stderr)
        sys.exit(0)
    env_manage(action, key, value)
    return None, None, False


def _handle_task_start(abs_work_dir: str, local_context: str, status_file: str) -> tuple[str | None, str | None, bool]:
    """task-start 모드 핸들러. 태스크 상태를 running으로 설정하고 usage-pending을 등록한다.

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로
        local_context: .context.json 파일 경로
        status_file: status.json 파일 경로

    Returns:
        (None, None, False) - 배너 출력 없음.
    """
    task_ids = sys.argv[3:]
    if not task_ids:
        print("[WARN] task-start 모드: task_id 인자가 필요합니다.", file=sys.stderr)
        sys.exit(0)
    seen = set()
    for tid in task_ids:
        if tid not in seen:
            seen.add(tid)
            update_task_status(status_file, tid, "running")
            usage_pending(abs_work_dir, tid, tid)
    return None, None, False


def _handle_task_status(abs_work_dir: str, local_context: str, status_file: str) -> tuple[str | None, str | None, bool]:
    """task-status 모드 핸들러.

    복수 태스크 ID 지원: `update_state.py task-status <workDir> <status> <id1> [id2] ...`
    레거시 형식도 지원: `update_state.py task-status <workDir> <taskId> <status>`

    Args:
        abs_work_dir: 워크 디렉터리 절대 경로
        local_context: .context.json 파일 경로
        status_file: status.json 파일 경로

    Returns:
        (None, None, False) - 배너 출력 없음.
    """
    _TS_VALID_STATUSES = {"pending", "running", "completed", "failed", "in_progress"}
    arg3 = sys.argv[3] if len(sys.argv) > 3 else ""
    arg4 = sys.argv[4] if len(sys.argv) > 4 else ""
    if not arg3:
        print("[WARN] task-status 모드: status, task_id 인자가 필요합니다.", file=sys.stderr)
        sys.exit(0)
    if arg3 in _TS_VALID_STATUSES:
        task_ids = sys.argv[4:]
        for tid in task_ids:
            update_task_status(status_file, tid, arg3)
    else:
        update_task_status(status_file, arg3, arg4)
    return None, None, False


_HANDLERS = {
    "context": _handle_context,
    "status": _handle_status,
    "both": _handle_both,
    "link-session": _handle_link_session,
    "usage-pending": _handle_usage_pending,
    "usage": _handle_usage,
    "usage-finalize": _handle_usage_finalize,
    "usage-regenerate": _handle_usage_regenerate,
    "env": _handle_env,
    "task-status": _handle_task_status,
    "task-start": _handle_task_start,
}


def main() -> None:
    """커맨드라인 인자를 파싱하여 적절한 핸들러를 디스패치한다."""
    if len(sys.argv) < 3:
        print("[WARN] 사용법: update_state.py context|status|both|link-session|usage-pending|usage|usage-finalize|usage-regenerate|env|task-status|task-start <workDir> [args...]", file=sys.stderr)
        sys.exit(0)

    mode = sys.argv[1]
    work_dir_arg = sys.argv[2]

    # 인자 순서 자동 교정: argv[1]이 모드가 아니고 argv[2]가 모드인 경우 swap
    if mode not in _VALID_MODES and work_dir_arg in _VALID_MODES:
        mode, work_dir_arg = work_dir_arg, mode
        print(
            f"[WARN] 인자 순서 자동 교정: mode={mode}, workDir={work_dir_arg} "
            f"(올바른 사용법: update_state.py <mode> <workDir> [args...])",
            file=sys.stderr,
        )

    abs_work_dir, local_context, status_file = resolve_paths(work_dir_arg)

    handler = _HANDLERS.get(mode)
    if handler is None:
        print(
            f"[WARN] 알 수 없는 모드: {mode} (context|status|both|link-session|usage-pending|usage|usage-finalize|usage-regenerate|env|task-status|task-start 중 선택)",
            file=sys.stderr,
        )
        print("FAIL", flush=True)
        sys.exit(0)

    _banner_from, _banner_to, _banner_ok = handler(abs_work_dir, local_context, status_file)

    if _banner_ok and _banner_from and _banner_to:
        _print_state_banner(_banner_from, _banner_to, abs_work_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()
