#!/usr/bin/env -S python3 -u
"""
워크플로우 상태 일괄 업데이트 스크립트 (update-state.sh -> update_state.py 1:1 포팅)

사용법:
  update_state.py context <workDir> <agent>
  update_state.py status <workDir> <fromPhase> <toPhase>
  update_state.py both <workDir> <agent> <fromPhase> <toPhase>
  update_state.py register <workDir> [title] [command]
  update_state.py unregister <workDir>
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

from data.constants import FSM_TRANSITIONS_FILENAME, KST
from utils.common import (
    C_GREEN,
    C_PURPLE,
    C_RED,
    C_RESET,
    C_YELLOW,
    C_BLUE,
    PHASE_COLORS,
    TS_PATTERN,
    atomic_write_json,
    extract_registry_key,
    load_json_file,
    resolve_abs_work_dir,
    resolve_project_root,
)


# =============================================================================
# 경로 해석
# =============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = resolve_project_root()


def resolve_paths(work_dir_arg):
    """workDir 인자를 절대 경로로 해석하고 관련 경로들을 반환."""
    abs_work_dir = resolve_abs_work_dir(work_dir_arg, PROJECT_ROOT)
    global_registry = os.path.join(PROJECT_ROOT, ".workflow", "registry.json")
    local_context = os.path.join(abs_work_dir, ".context.json")
    status_file = os.path.join(abs_work_dir, "status.json")
    return abs_work_dir, global_registry, local_context, status_file


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
                except (ValueError, ProcessLookupError, PermissionError, OSError):
                    try:
                        shutil.rmtree(lock_dir)
                    except OSError:
                        pass
                    continue
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
        return f"context -> agent={agent} (local)"
    except Exception as e:
        print(f"[WARN] .context.json update failed ({local_context}): {e}", file=sys.stderr)
        return "context -> failed"


# =============================================================================
# register / unregister
# =============================================================================

def register_workflow(abs_work_dir, global_registry, reg_title="", reg_command=""):
    """전역 레지스트리에 워크플로우 등록."""
    lock_dir = global_registry + ".lockdir"
    if not acquire_lock(lock_dir):
        print("[WARN] register: 잠금 획득 실패", file=sys.stderr)
        return "register -> lock failed"

    try:
        registry_key = extract_registry_key(abs_work_dir)

        # 상대 workDir 구성
        if abs_work_dir.startswith(PROJECT_ROOT):
            rel_work_dir = os.path.relpath(abs_work_dir, PROJECT_ROOT)
        else:
            rel_work_dir = abs_work_dir

        # 레지스트리 읽기
        data = load_json_file(global_registry)
        if not isinstance(data, dict):
            data = {}

        # 중복 등록 방지
        if registry_key in data:
            return f"register -> already registered: {registry_key}"

        # 등록
        data[registry_key] = {
            "title": reg_title,
            "phase": "INIT",
            "workDir": rel_work_dir,
            "command": reg_command,
        }

        os.makedirs(os.path.dirname(global_registry), exist_ok=True)
        atomic_write_json(global_registry, data)
        return f"register -> key={registry_key}"
    finally:
        release_lock(lock_dir)


def unregister_workflow(abs_work_dir, global_registry):
    """전역 레지스트리에서 워크플로우 해제."""
    lock_dir = global_registry + ".lockdir"
    if not acquire_lock(lock_dir):
        print("[WARN] unregister: 잠금 획득 실패", file=sys.stderr)
        return "unregister -> lock failed"

    try:
        if not os.path.exists(global_registry):
            return "unregister -> registry not found, skipping"

        data = load_json_file(global_registry)
        if not isinstance(data, dict):
            return "unregister -> invalid registry format, skipping"

        registry_key = extract_registry_key(abs_work_dir)
        if registry_key not in data:
            return f"unregister -> key {registry_key} not found in registry, skipping"

        del data[registry_key]
        atomic_write_json(global_registry, data)
        return f"unregister -> removed key={registry_key}"
    finally:
        release_lock(lock_dir)


# =============================================================================
# registry phase 동기화
# =============================================================================

def sync_registry_phase(abs_work_dir, global_registry, to_phase):
    """전역 레지스트리의 phase 동기화."""
    lock_dir = global_registry + ".lockdir"
    if not acquire_lock(lock_dir):
        print("[WARN] sync_registry_phase: 잠금 획득 실패", file=sys.stderr)
        return

    try:
        if not os.path.exists(global_registry):
            return

        data = load_json_file(global_registry)
        if not isinstance(data, dict):
            return

        registry_key = extract_registry_key(abs_work_dir)
        if registry_key not in data:
            return

        data[registry_key]["phase"] = to_phase
        atomic_write_json(global_registry, data)
    finally:
        release_lock(lock_dir)


# =============================================================================
# status 업데이트
# =============================================================================

def update_status(abs_work_dir, global_registry, status_file, from_phase, to_phase):
    """status.json 업데이트 + registry phase 동기화."""
    skip_guard = os.environ.get("WORKFLOW_SKIP_GUARD", "") == "1"

    # FSM 전이 규칙 로드
    fsm_file = os.path.join(SCRIPT_DIR, FSM_TRANSITIONS_FILENAME)
    fsm_data = load_json_file(fsm_file)
    if fsm_data is None:
        print(f"[ERROR] FSM 규칙 파일 로드 실패: {fsm_file}", file=sys.stderr)
        return "status -> FSM load failed"

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
            current_phase = data.get("phase", "NONE")
            workflow_mode = data.get("mode", "full").lower()

            if from_phase != current_phase:
                print(
                    f"[ERROR] FSM guard: from_phase mismatch. expected={current_phase}, got={from_phase}. transition blocked.",
                    file=sys.stderr,
                )
                return "status -> FSM guard blocked (mismatch)"

            allowed_table = fsm_data.get("modes", {}).get(
                workflow_mode, fsm_data.get("modes", {}).get("full", {})
            )
            allowed = allowed_table.get(from_phase, [])
            if to_phase not in allowed:
                print(
                    f"[ERROR] FSM guard: illegal transition {from_phase}->{to_phase}. allowed={allowed}. transition blocked.",
                    file=sys.stderr,
                )
                return "status -> FSM guard blocked (illegal)"

        # KST 시간
        kst = KST
        now = datetime.now(kst).strftime("%Y-%m-%dT%H:%M:%S+09:00")

        data["phase"] = to_phase
        data["updated_at"] = now

        if "transitions" not in data:
            data["transitions"] = []
        data["transitions"].append({"from": from_phase, "to": to_phase, "at": now})

        atomic_write_json(status_file, data)

        # 색상 출력
        c_from = PHASE_COLORS.get(from_phase, "")
        r_from = C_RESET if c_from else ""
        c_to = PHASE_COLORS.get(to_phase, "")
        r_to = C_RESET if c_to else ""
        result = f"status -> {c_from}{from_phase}{r_from}->{c_to}{to_phase}{r_to}"
    except Exception as e:
        print(f"[WARN] status.json update failed: {e}", file=sys.stderr)
        return "status -> failed"

    # 전역 레지스트리 phase 동기화
    sync_registry_phase(abs_work_dir, global_registry, to_phase)

    # history.md 실시간 갱신 (비동기, 실패 무시)
    history_sync_py = os.path.join(SCRIPT_DIR, "..", "sync", "history_sync.py")
    try:
        if os.path.isfile(history_sync_py):
            subprocess.Popen(
                [sys.executable, history_sync_py, "sync"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass

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

def usage_finalize(abs_work_dir, global_registry):
    """totals 계산, effective_tokens 산출, .prompt/usage.md 행 추가."""
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

        agents = data.get("agents", {})

        # 모든 에이전트 토큰 데이터 수집
        all_agents = []
        for key in ["orchestrator", "init", "planner", "reporter"]:
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

        # registry에서 메타데이터 조회
        reg_title = ""
        reg_command = ""
        reg_data = load_json_file(global_registry)
        if isinstance(reg_data, dict) and registry_key in reg_data:
            reg_title = reg_data[registry_key].get("title", "")
            reg_command = reg_data[registry_key].get("command", "")

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
        init_eff = calc_effective(agents.get("init", {})) if "init" in agents else 0
        plan_eff = calc_effective(agents.get("planner", {})) if "planner" in agents else 0
        work_eff = (
            sum(calc_effective(w) for w in workers.values() if isinstance(w, dict))
            if isinstance(workers, dict)
            else 0
        )
        report_eff = calc_effective(agents.get("reporter", {})) if "reporter" in agents else 0
        total_eff = orch_eff + init_eff + plan_eff + work_eff + report_eff
        eff_weighted = totals.get("effective_tokens", total_eff)

        # usage.md 행 생성
        row = (
            f"| {date_str} "
            f"| {registry_key} "
            f"| {title} "
            f"| {reg_command} "
            f"| {to_k(orch_eff)} "
            f"| {to_k(init_eff)} "
            f"| {to_k(plan_eff)} "
            f"| {to_k(work_eff)} "
            f"| {to_k(report_eff)} "
            f"| {to_k(total_eff)} "
            f"| {to_k_precise(eff_weighted)} |"
        )

        # .prompt/usage.md 갱신
        usage_md = os.path.join(PROJECT_ROOT, ".prompt", "usage.md")
        marker = "<!-- 새 항목은 이 줄 아래에 추가됩니다 -->"
        header_line = "| 날짜 | 작업ID | 제목 | 명령어 | Orch | Init | Plan | Work | Report | 합계 | eff |"
        separator_line = "|------|--------|------|--------|------|------|------|------|--------|------|-----|"

        content = ""
        if os.path.exists(usage_md):
            with open(usage_md, "r", encoding="utf-8") as f:
                content = f.read()

        if marker not in content:
            content = f"# 워크플로우 사용량 추적\n\n{marker}\n\n{header_line}\n{separator_line}\n"

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

def main():
    if len(sys.argv) < 3:
        print("[WARN] 사용법: update_state.py context|status|both|register|unregister <workDir> [args...]", file=sys.stderr)
        sys.exit(0)

    mode = sys.argv[1]
    work_dir_arg = sys.argv[2]

    abs_work_dir, global_registry, local_context, status_file = resolve_paths(work_dir_arg)

    if mode == "context":
        agent = sys.argv[3] if len(sys.argv) > 3 else ""
        if not agent:
            print("[WARN] context 모드: agent 인자가 필요합니다.", file=sys.stderr)
            sys.exit(0)
        result = update_context(local_context, agent)
        print(f"{C_YELLOW}[OK]{C_RESET} state updated: {result}")

    elif mode == "status":
        from_phase = sys.argv[3] if len(sys.argv) > 3 else ""
        to_phase = sys.argv[4] if len(sys.argv) > 4 else ""
        if not from_phase or not to_phase:
            print("[WARN] status 모드: fromPhase, toPhase 인자가 필요합니다.", file=sys.stderr)
            sys.exit(0)
        result = update_status(abs_work_dir, global_registry, status_file, from_phase, to_phase)
        print(f"{C_YELLOW}[OK]{C_RESET} state updated: {result}")

    elif mode == "both":
        agent = sys.argv[3] if len(sys.argv) > 3 else ""
        from_phase = sys.argv[4] if len(sys.argv) > 4 else ""
        to_phase = sys.argv[5] if len(sys.argv) > 5 else ""
        if not agent or not from_phase or not to_phase:
            print("[WARN] both 모드: agent, fromPhase, toPhase 인자가 필요합니다.", file=sys.stderr)
            sys.exit(0)
        result_ctx = update_context(local_context, agent)
        result_sts = update_status(abs_work_dir, global_registry, status_file, from_phase, to_phase)
        print(f"{C_YELLOW}[OK]{C_RESET} state updated: {result_ctx}, {result_sts}")

    elif mode == "register":
        reg_title = sys.argv[3] if len(sys.argv) > 3 else ""
        reg_command = sys.argv[4] if len(sys.argv) > 4 else ""
        result = register_workflow(abs_work_dir, global_registry, reg_title, reg_command)
        print(f"{C_YELLOW}[OK]{C_RESET} state updated: {result}")

    elif mode == "unregister":
        result = unregister_workflow(abs_work_dir, global_registry)
        print(f"{C_YELLOW}[OK]{C_RESET} state updated: {result}")

    elif mode == "link-session":
        session_id = sys.argv[3] if len(sys.argv) > 3 else ""
        if not session_id:
            print("[WARN] link-session 모드: sessionId 인자가 필요합니다.", file=sys.stderr)
            sys.exit(0)
        result = link_session(status_file, session_id)
        print(f"{C_YELLOW}[OK]{C_RESET} state updated: {result}")

    elif mode == "usage-pending":
        agent_id = sys.argv[3] if len(sys.argv) > 3 else ""
        task_id = sys.argv[4] if len(sys.argv) > 4 else ""
        if not agent_id or not task_id:
            print("[WARN] usage-pending 모드: agent_id, task_id 인자가 필요합니다.", file=sys.stderr)
            sys.exit(0)
        result = usage_pending(abs_work_dir, agent_id, task_id)
        print(f"{C_YELLOW}[OK]{C_RESET} state updated: {result}")

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
        result = usage_record(abs_work_dir, agent_name, input_tokens, output_tokens, cache_creation, cache_read, task_id_arg)
        print(f"{C_YELLOW}[OK]{C_RESET} state updated: {result}")

    elif mode == "usage-finalize":
        result = usage_finalize(abs_work_dir, global_registry)
        print(f"{C_YELLOW}[OK]{C_RESET} state updated: {result}")

    elif mode == "env":
        action = sys.argv[3] if len(sys.argv) > 3 else ""
        key = sys.argv[4] if len(sys.argv) > 4 else ""
        value = sys.argv[5] if len(sys.argv) > 5 else ""
        if not action or not key:
            print("[WARN] env 모드: action(set|unset), KEY 인자가 필요합니다.", file=sys.stderr)
            sys.exit(0)
        result = env_manage(action, key, value)
        print(f"{C_YELLOW}[OK]{C_RESET} state updated: {result}")

    elif mode == "task-status":
        task_id = sys.argv[3] if len(sys.argv) > 3 else ""
        task_status = sys.argv[4] if len(sys.argv) > 4 else ""
        if not task_id or not task_status:
            print("[WARN] task-status 모드: task_id, status 인자가 필요합니다.", file=sys.stderr)
            sys.exit(0)
        result = update_task_status(status_file, task_id, task_status)
        print(f"{C_YELLOW}[OK]{C_RESET} state updated: {result}")

    else:
        print(
            f"[WARN] 알 수 없는 모드: {mode} (context|status|both|register|unregister|link-session|usage-pending|usage|usage-finalize|env|task-status 중 선택)",
            file=sys.stderr,
        )

    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
