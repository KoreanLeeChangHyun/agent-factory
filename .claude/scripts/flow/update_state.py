#!/usr/bin/env -S python3 -u
"""
워크플로우 상태 일괄 업데이트 스크립트 (update-state.sh -> update_state.py 1:1 포팅)

사용법:
  update_state.py context <workDir> <agent>
  update_state.py status <workDir> <toPhase>
  update_state.py both <workDir> <agent> <toPhase>
  update_state.py link-session <workDir> <sessionId>
  update_state.py usage-pending <workDir> <agent_id> <task_id>
  update_state.py usage <workDir> <agent_name> <input_tokens> <output_tokens> [cache_creation] [cache_read] [task_id]
  update_state.py usage-finalize <workDir>
  update_state.py env <workDir> set|unset <KEY> [VALUE]
  update_state.py task-status <workDir> <task_id> <status>

종료 코드:
  항상 0 (비차단 원칙)
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime

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


def _print_state_banner(from_step, to_step):
    """상태 전이 배너 출력: 2줄 포맷."""
    c_from = STEP_COLORS.get(from_step, C_GRAY)
    c_to = STEP_COLORS.get(to_step, C_GRAY)
    print(f"{C_CLAUDE}║ STATE:{C_RESET} {C_DIM}단계 변경{C_RESET}", flush=True)
    print(
        f"{C_CLAUDE}║{C_RESET} "
        f"{C_CLAUDE}>>{C_RESET} "
        f"{c_from}{from_step}{C_RESET} "
        f"{C_CLAUDE}->{C_RESET} "
        f"{c_to}{C_BOLD}{to_step}{C_RESET}",
        flush=True,
    )



# =============================================================================
# 경로 해석
# =============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = resolve_project_root()


def resolve_paths(work_dir_arg):
    """workDir 인자를 절대 경로로 해석하고 관련 경로들을 반환."""
    abs_work_dir = resolve_abs_work_dir(work_dir_arg, PROJECT_ROOT)
    local_context = os.path.join(abs_work_dir, ".context.json")
    status_file = os.path.join(abs_work_dir, "status.json")
    return abs_work_dir, local_context, status_file


# =============================================================================
# mkdir 기반 POSIX 잠금
# =============================================================================

def acquire_lock(lock_dir, max_wait=5):
    """mkdir 기반 POSIX 잠금 획득. stale lock 감지 포함."""
    waited = 0
    while True:
        try:
            os.makedirs(lock_dir)
            # PID 기록
            try:
                with open(os.path.join(lock_dir, "pid"), "w") as f:
                    f.write(str(os.getpid()))
            except OSError:
                pass
            return True
        except OSError:
            # stale lock 감지
            pid_file = os.path.join(lock_dir, "pid")
            if os.path.isfile(pid_file):
                try:
                    with open(pid_file, "r") as f:
                        lock_pid = int(f.read().strip())
                    # 프로세스가 존재하지 않으면 stale lock 제거
                    os.kill(lock_pid, 0)
                except (ValueError, ProcessLookupError, OSError):
                    try:
                        shutil.rmtree(lock_dir)
                    except OSError:
                        pass
                    continue
                except PermissionError:
                    # 프로세스가 살아있지만 kill 권한 없음 → stale lock 아님, 대기
                    pass
            waited += 1
            if waited >= max_wait:
                return False
            time.sleep(1)


def release_lock(lock_dir):
    """잠금 해제."""
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


# =============================================================================
# context 업데이트
# =============================================================================

def update_context(local_context, agent):
    """context.json의 agent 필드만 갱신."""
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
        return f"context -> agent={agent}"
    except Exception as e:
        print(f"[WARN] .context.json update failed ({local_context}): {e}", file=sys.stderr)
        return "context -> failed"


# =============================================================================
# status 업데이트
# =============================================================================

def update_status(abs_work_dir, status_file, from_step, to_step):
    """status.json 업데이트 + registry step 동기화.

    FSM 검증 로직:
      1. WORKFLOW_SKIP_GUARD=1 환경변수가 설정된 경우 검증을 건너뜀
      2. current_step 확인: status.json의 현재 step과 from_step이 일치하는지 검증
      3. allowed 확인: FSM_TRANSITIONS(constants.py)에서 현재 mode/from_step에 허용된 대상 목록을 조회하고
         to_step이 포함되어 있는지 검증

    비차단 원칙:
      FSM 검증 실패 시에도 프로세스를 종료하지 않음 (항상 exit 0).
      검증 실패 시 구조화된 에러 메시지를 반환하되, 상태 전이는 수행하지 않음.
      에러 메시지에는 from_step, to_step, current_step, workflow_mode, allowed_targets
      5개 필드가 모두 포함되어 디버깅을 용이하게 함.

    참고:
      register, unregister, link-session 등 status 전이가 아닌 명령은
      main()에서 별도 분기로 처리되므로 이 함수가 호출되지 않음.
    """
    skip_guard = os.environ.get("WORKFLOW_SKIP_GUARD", "") == "1"

    if not os.path.exists(status_file):
        print(f"[WARN] status.json not found: {status_file}", file=sys.stderr)
        return "status -> skipped (file not found)"

    try:
        data = load_json_file(status_file)
        if data is None:
            print(f"[WARN] status.json read failed: {status_file}", file=sys.stderr)
            return "status -> skipped (read failed)"

        # FSM 전이 검증
        if not skip_guard:
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

        # history_sync.py sync 호출 (비차단 원칙: 실패 시 경고만 출력)
        try:
            subprocess.run(
                ["python3", HISTORY_SYNC_PATH, "sync"],
                capture_output=True,
                timeout=30,
            )
        except Exception as e:
            print(f"[WARN] history sync failed: {e}", file=sys.stderr)

        # 색상 출력
        c_from = STEP_COLORS.get(from_step, "")
        r_from = C_RESET if c_from else ""
        c_to = STEP_COLORS.get(to_step, "")
        r_to = C_RESET if c_to else ""
        result = f"status -> {c_from}{from_step}{r_from}->{c_to}{to_step}{r_to}"
    except Exception as e:
        print(f"[WARN] status.json update failed: {e}", file=sys.stderr)
        return "status -> failed"

    return result


# =============================================================================
# link-session
# =============================================================================

def link_session(status_file, session_id):
    """status.json의 linked_sessions 배열에 세션 ID 추가."""
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
        return f"link-session -> added: {session_id} (total: {len(data['linked_sessions'])})"
    except Exception as e:
        print(f"[WARN] link-session failed: {e}", file=sys.stderr)
        return "link-session -> failed"


# =============================================================================
# task-status
# =============================================================================

def update_task_status(status_file, task_id, task_status):
    """status.json의 tasks 객체에 태스크 상태 기록."""
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
        return f"task-status -> {task_id}: {task_status} (updated_at: {now})"
    except Exception as e:
        print(f"[WARN] task-status failed: {e}", file=sys.stderr)
        return "task-status -> failed"


# =============================================================================
# usage-pending
# =============================================================================

def usage_pending(abs_work_dir, agent_id, task_id):
    """usage.json의 _pending_workers에 agent_id->taskId 매핑 등록."""
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
        return f"usage-pending -> {agent_id}={task_id}"
    finally:
        release_lock(lock_dir)


# =============================================================================
# usage
# =============================================================================

def usage_record(abs_work_dir, agent_name, input_tokens, output_tokens, cache_creation=0, cache_read=0, task_id=""):
    """usage.json의 agents 객체에 에이전트별 토큰 데이터 기록."""
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
        return f"usage -> {label}: in={input_tokens} out={output_tokens} cc={cache_creation} cr={cache_read}"
    finally:
        release_lock(lock_dir)


# =============================================================================
# usage-finalize
# =============================================================================

def usage_finalize(abs_work_dir):
    """totals 계산, effective_tokens 산출, .dashboard/.usage.md 행 추가."""
    usage_file = os.path.join(abs_work_dir, "usage.json")
    if not os.path.isfile(usage_file):
        print(f"[WARN] usage-finalize: usage.json not found: {usage_file}", file=sys.stderr)
        return "usage-finalize -> skipped (file not found)"

    def calc_effective(d):
        return (
            d.get("input_tokens", 0)
            + d.get("output_tokens", 0) * 5
            + d.get("cache_creation_tokens", 0) * 1.25
            + d.get("cache_read_tokens", 0) * 0.1
        )

    def sum_tokens(agents_list):
        totals = {"input_tokens": 0, "output_tokens": 0, "cache_creation_tokens": 0, "cache_read_tokens": 0}
        for a in agents_list:
            for k in totals:
                totals[k] += a.get(k, 0)
        return totals

    def to_k(n):
        return "-" if n == 0 else f"{int(n) // 1000}k"

    def to_k_precise(n):
        return "-" if n == 0 else f"{n / 1000:.1f}k"

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
        totals = sum_tokens(all_agents)
        totals["effective_tokens"] = calc_effective(totals)
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
        orch_eff = calc_effective(agents.get("orchestrator", {})) if "orchestrator" in agents else 0
        plan_eff = calc_effective(agents.get("planner", {})) if "planner" in agents else 0
        work_eff = (
            sum(calc_effective(w) for w in workers.values() if isinstance(w, dict))
            if isinstance(workers, dict)
            else 0
        )
        exp_eff = calc_effective(agents.get("explorer", {})) if "explorer" in agents else 0
        val_eff = calc_effective(agents.get("validator", {})) if "validator" in agents else 0
        report_eff = calc_effective(agents.get("reporter", {})) if "reporter" in agents else 0
        total_eff = orch_eff + plan_eff + work_eff + exp_eff + val_eff + report_eff
        eff_weighted = totals.get("effective_tokens", total_eff)

        # usage.md 행 생성 (11칼럼 스키마: 날짜|작업ID|제목|명령|ORC|PLN|WRK|EXP|VAL|RPT|합계)
        row = (
            f"| {date_str} "
            f"| {registry_key} "
            f"| {title} "
            f"| {reg_command} "
            f"| {to_k(orch_eff)} "
            f"| {to_k(plan_eff)} "
            f"| {to_k(work_eff)} "
            f"| {to_k(exp_eff)} "
            f"| {to_k(val_eff)} "
            f"| {to_k(report_eff)} "
            f"| {to_k(total_eff)} |"
        )

        # .dashboard/.usage.md 갱신
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
            return f"usage-finalize -> totals: eff={to_k_precise(eff_weighted)}, usage.md skipped (column mismatch)"

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

        return f"usage-finalize -> totals: eff={to_k_precise(eff_weighted)}, usage.md updated"
    except Exception as e:
        print(f"[WARN] usage-finalize failed: {e}", file=sys.stderr)
        return "usage-finalize -> failed"


# =============================================================================
# env 관리
# =============================================================================

def env_manage(action, key, value=""):
    """claude.env 파일의 환경 변수 관리."""
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
    "usage-pending", "usage", "usage-finalize", "env", "task-status",
})


def main():
    if len(sys.argv) < 3:
        print("[WARN] 사용법: update_state.py context|status|both|link-session|usage-pending|usage|usage-finalize|env|task-status <workDir> [args...]", file=sys.stderr)
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

    # 상태 전이 배너 출력용 추적 변수
    _banner_from = ""
    _banner_to = ""
    _banner_ok = False

    if mode == "context":
        agent = sys.argv[3] if len(sys.argv) > 3 else ""
        if not agent:
            print("[WARN] context 모드: agent 인자가 필요합니다.", file=sys.stderr)
            sys.exit(0)
        update_context(local_context, agent)

    elif mode == "status":
        to_step = sys.argv[3] if len(sys.argv) > 3 else ""
        if not to_step:
            print("[WARN] status 모드: toPhase 인자가 필요합니다.", file=sys.stderr)
            sys.exit(0)
        _data = load_json_file(status_file) if os.path.isfile(status_file) else None
        from_step = (_data.get("step") or _data.get("phase", "NONE")) if isinstance(_data, dict) else "NONE"
        result = update_status(abs_work_dir, status_file, from_step, to_step)
        _banner_from = from_step
        _banner_to = to_step
        _banner_ok = not any(x in result for x in ("blocked", "skipped", "failed"))

    elif mode == "both":
        agent = sys.argv[3] if len(sys.argv) > 3 else ""
        to_step = sys.argv[4] if len(sys.argv) > 4 else ""
        if not agent or not to_step:
            print("[WARN] both 모드: agent, toPhase 인자가 필요합니다.", file=sys.stderr)
            sys.exit(0)
        _data = load_json_file(status_file) if os.path.isfile(status_file) else None
        from_step = (_data.get("step") or _data.get("phase", "NONE")) if isinstance(_data, dict) else "NONE"
        update_context(local_context, agent)
        result = update_status(abs_work_dir, status_file, from_step, to_step)
        _banner_from = from_step
        _banner_to = to_step
        _banner_ok = not any(x in result for x in ("blocked", "skipped", "failed"))

    elif mode == "link-session":
        session_id = sys.argv[3] if len(sys.argv) > 3 else ""
        if not session_id:
            print("[WARN] link-session 모드: sessionId 인자가 필요합니다.", file=sys.stderr)
            sys.exit(0)
        link_session(status_file, session_id)

    elif mode == "usage-pending":
        agent_id = sys.argv[3] if len(sys.argv) > 3 else ""
        task_id = sys.argv[4] if len(sys.argv) > 4 else ""
        if not agent_id or not task_id:
            print("[WARN] usage-pending 모드: agent_id, task_id 인자가 필요합니다.", file=sys.stderr)
            sys.exit(0)
        usage_pending(abs_work_dir, agent_id, task_id)

    elif mode == "usage":
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

    elif mode == "usage-finalize":
        usage_finalize(abs_work_dir)

    elif mode == "env":
        action = sys.argv[3] if len(sys.argv) > 3 else ""
        key = sys.argv[4] if len(sys.argv) > 4 else ""
        value = sys.argv[5] if len(sys.argv) > 5 else ""
        if not action or not key:
            print("[WARN] env 모드: action(set|unset), KEY 인자가 필요합니다.", file=sys.stderr)
            sys.exit(0)
        env_manage(action, key, value)

    elif mode == "task-status":
        task_id = sys.argv[3] if len(sys.argv) > 3 else ""
        task_status = sys.argv[4] if len(sys.argv) > 4 else ""
        if not task_id or not task_status:
            print("[WARN] task-status 모드: task_id, status 인자가 필요합니다.", file=sys.stderr)
            sys.exit(0)
        update_task_status(status_file, task_id, task_status)

    else:
        print(
            f"[WARN] 알 수 없는 모드: {mode} (context|status|both|link-session|usage-pending|usage|usage-finalize|env|task-status 중 선택)",
            file=sys.stderr,
        )
        print("FAIL", flush=True)
        sys.exit(0)

    if _banner_ok and _banner_from and _banner_to:
        _print_state_banner(_banner_from, _banner_to)  # from_step, to_step
    sys.exit(0)


if __name__ == "__main__":
    main()
