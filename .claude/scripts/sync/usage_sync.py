#!/usr/bin/env -S python3 -u
"""
usage_sync.py - 워크플로우 토큰 사용량 추적 (증분 + 일괄)

서브커맨드:
  track   SubagentStop 훅에서 호출. 개별 에이전트 종료 시 증분 토큰 추적
  batch   finalization.py에서 호출. 전체 JSONL 일괄 파싱으로 최종 정산

입력 (stdin JSON): agent_type, agent_id, agent_transcript_path
비차단 원칙: 모든 에러 경로에서 exit 0
"""

import glob
import json
import os
import shutil
import sys
import time

# utils 패키지 import
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import (
    atomic_write_json,
    load_json_file,
    resolve_project_root,
    scan_active_workflows,
)

PROJECT_ROOT = resolve_project_root()

# 파일 크기 상한 (50MB)
MAX_JSONL_SIZE = 50 * 1024 * 1024

VALID_AGENT_TYPES = {
    "orchestrator", "planner", "worker", "explorer",
    "validator", "reporter",
}


# =============================================================================
# 공통 유틸리티
# =============================================================================

def _read_stdin_json():
    """stdin에서 JSON을 읽어 반환. 실패 시 exit 0."""
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)


def _find_work_dir():
    """디렉터리 스캔으로 활성 워크플로우의 workDir을 조회."""
    workflows = scan_active_workflows(project_root=PROJECT_ROOT)
    if not workflows:
        return None

    for key, entry in workflows.items():
        if isinstance(entry, dict) and "workDir" in entry:
            rel_dir = entry["workDir"]
            candidate = os.path.join(PROJECT_ROOT, rel_dir) if not rel_dir.startswith("/") else rel_dir
            if os.path.isdir(candidate):
                return candidate
    return None


def _acquire_lock(lock_dir, max_wait=5):
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
                print(
                    f"[usage-sync] WARNING: lock acquisition failed after {max_wait}s: {lock_dir}",
                    file=sys.stderr,
                )
                return False
            time.sleep(1)


def _release_lock(lock_dir):
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


def _load_usage(usage_file):
    """usage.json을 로드. 없으면 기본 스키마 반환."""
    data = load_json_file(usage_file)
    if not isinstance(data, dict):
        data = {"$schema": "usage-v2", "agents": {}, "totals": {}, "_pending_workers": {}}
    if "agents" not in data:
        data["agents"] = {}
    # 기존 usage.json에서 "init", "done" 키 정리
    for old_key in ("init", "done"):
        data["agents"].pop(old_key, None)
    return data


def parse_jsonl_usage(filepath):
    """JSONL 파일의 모든 assistant 레코드 usage를 합산한다.

    Returns:
        dict: {input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens}
        또는 파싱 실패 시 None
    """
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
    }

    if not os.path.isfile(filepath):
        return None

    file_size = os.path.getsize(filepath)
    if file_size > MAX_JSONL_SIZE:
        print(
            f"[usage-sync] WARNING: JSONL file exceeds {MAX_JSONL_SIZE // (1024*1024)}MB: "
            f"{filepath} ({file_size // (1024*1024)}MB)",
            file=sys.stderr,
        )

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if rec.get("type") != "assistant":
                    continue
                if rec.get("isApiErrorMessage"):
                    continue

                usage = None
                msg = rec.get("message")
                if isinstance(msg, dict) and "usage" in msg:
                    usage = msg["usage"]
                elif "usage" in rec:
                    usage = rec["usage"]

                if isinstance(usage, dict):
                    totals["input_tokens"] += usage.get("input_tokens", 0)
                    totals["output_tokens"] += usage.get("output_tokens", 0)
                    totals["cache_creation_tokens"] += usage.get("cache_creation_input_tokens", 0)
                    totals["cache_read_tokens"] += usage.get("cache_read_input_tokens", 0)
    except Exception as e:
        print(f"[usage-sync] WARNING: Failed to parse {filepath}: {e}", file=sys.stderr)
        return None

    return totals


# =============================================================================
# track: 개별 에이전트 종료 시 증분 추적
# =============================================================================

def cmd_track():
    """SubagentStop 훅에서 호출. 개별 에이전트 토큰을 usage.json에 기록."""
    input_data = _read_stdin_json()

    agent_type = input_data.get("agent_type", "")
    agent_id = input_data.get("agent_id", "")
    transcript_path = input_data.get("agent_transcript_path", "")

    if agent_type not in VALID_AGENT_TYPES:
        sys.exit(0)
    if not transcript_path or not os.path.isfile(transcript_path):
        sys.exit(0)

    work_dir = _find_work_dir()
    if not work_dir:
        sys.exit(0)

    # JSONL 파싱
    tokens = parse_jsonl_usage(transcript_path)
    if not tokens:
        print(f"[usage-sync] No valid usage data found in: {transcript_path}", file=sys.stderr)
        sys.exit(0)

    tokens["method"] = "subagent_transcript"

    usage_file = os.path.join(work_dir, "usage.json")
    lock_dir = usage_file + ".lockdir"

    if not _acquire_lock(lock_dir):
        print(
            f"[usage-sync] WARNING: track lock failed, usage data may be lost for {agent_type}:{agent_id}",
            file=sys.stderr,
        )
        sys.exit(0)

    try:
        usage_data = _load_usage(usage_file)

        # _agent_map에 agent_id -> agent_type 매핑 기록 (batch에서 참조)
        if "_agent_map" not in usage_data:
            usage_data["_agent_map"] = {}
        usage_data["_agent_map"][agent_id] = agent_type

        if agent_type == "worker":
            pending = usage_data.get("_pending_workers", {})
            task_id = pending.get(agent_id, None)

            if "workers" not in usage_data["agents"]:
                usage_data["agents"]["workers"] = {}

            existing_workers = usage_data["agents"]["workers"]

            if task_id:
                # agent_id가 pending key로 직접 매핑된 경우 (이상적 경로)
                existing_workers[task_id] = tokens
                del pending[agent_id]
            else:
                # agent_id가 hex 문자열이어서 pending에 없는 경우:
                # pending의 값(task_id) 중 아직 workers에 기록되지 않은 첫 번째 task_id를 큐 방식으로 할당
                assigned_task_id = None
                for pkey, ptid in list(pending.items()):
                    if ptid not in existing_workers:
                        assigned_task_id = ptid
                        del pending[pkey]
                        break

                if assigned_task_id:
                    print(
                        f"[usage-sync] INFO: agent_id '{agent_id}' mapped to task_id '{assigned_task_id}' via queue assignment",
                        file=sys.stderr,
                    )
                    existing_workers[assigned_task_id] = tokens
                    # _agent_map에 agent_id -> task_id 관계 기록 (batch 참조용)
                    usage_data["_agent_map"][agent_id] = "worker"
                else:
                    # 완전히 매핑 불가: agent_id를 키로 폴백 기록
                    print(
                        f"[usage-sync] WARNING: agent_id '{agent_id}' not found in _pending_workers and no unassigned task_id, using agent_id as key",
                        file=sys.stderr,
                    )
                    existing_workers[agent_id] = tokens
        else:
            usage_data["agents"][agent_type] = tokens

        os.makedirs(os.path.dirname(usage_file), exist_ok=True)
        atomic_write_json(usage_file, usage_data)
    finally:
        _release_lock(lock_dir)


# =============================================================================
# batch: 워크플로우 종료 시 전체 JSONL 일괄 정산
# =============================================================================

def _find_subagents_dir(transcript_path):
    """agent_transcript_path에서 subagents/ 디렉터리 경로를 역산."""
    parent = os.path.dirname(transcript_path)
    if os.path.basename(parent) == "subagents":
        return parent
    return None


def _find_main_session_jsonl(subagents_dir):
    """subagents/ 상위에서 메인 세션 JSONL을 찾는다."""
    session_dir = os.path.dirname(subagents_dir)
    session_jsonl = session_dir + ".jsonl"
    if os.path.isfile(session_jsonl):
        return session_jsonl
    return None


def _find_main_session_from_status(work_dir):
    """status.json의 linked_sessions 또는 _agent_map에서 메인 세션 JSONL 경로를 구성.

    1차: linked_sessions에 기록된 세션 ID로 <session_id>.jsonl을 직접 탐색.
    2차(대체): linked_sessions가 비어있을 때, usage.json의 _agent_map에 기록된
         알려진 agent_id로 subagents 디렉터리를 역탐색하여 상위 세션 JSONL을 반환.
    """
    status_file = os.path.join(work_dir, "status.json")
    status = load_json_file(status_file)
    if not isinstance(status, dict):
        return None

    project_slug = PROJECT_ROOT.replace("/", "-")

    # 1차: linked_sessions 기반 탐색
    sessions = status.get("linked_sessions", [])
    for claude_base in [
        os.path.expanduser("~/.claude"),
        os.path.expanduser("~/.config/claude"),
    ]:
        projects_dir = os.path.join(claude_base, "projects", project_slug)
        if not os.path.isdir(projects_dir):
            continue
        for session_id in sessions:
            path = os.path.join(projects_dir, f"{session_id}.jsonl")
            if os.path.isfile(path):
                return path

    # 2차: _agent_map에 기록된 알려진 agent_id로 역탐색
    usage_file = os.path.join(work_dir, "usage.json")
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
        for agent_id in agent_map:
            pattern = os.path.join(projects_dir, "*", "subagents", f"agent-{agent_id}.jsonl")
            matches = glob.glob(pattern)
            if matches:
                # subagents/ -> session_dir -> session_dir.jsonl
                session_dir = os.path.dirname(os.path.dirname(matches[0]))
                main_jsonl = session_dir + ".jsonl"
                if os.path.isfile(main_jsonl):
                    return main_jsonl

    return None


def _resolve_agent_type(agent_filename, agent_map):
    """agent-<id>.jsonl의 agent_type을 식별. _agent_map 우선, JSONL 폴백."""
    basename = os.path.basename(agent_filename)
    if basename.startswith("agent-") and basename.endswith(".jsonl"):
        agent_id = basename[len("agent-"):-len(".jsonl")]
        mapped = agent_map.get(agent_id)
        if mapped:
            return mapped

    # 폴백: JSONL의 첫 user 레코드에서 slug로 추정
    try:
        with open(agent_filename, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("type") == "user":
                    slug = rec.get("slug", "")
                    if slug in VALID_AGENT_TYPES:
                        return slug
                    for t in VALID_AGENT_TYPES:
                        if slug.startswith(t):
                            return t
                    break
    except Exception:
        pass
    return None


def cmd_batch():
    """finalization.py에서 호출. 전체 JSONL 일괄 파싱으로 usage.json 최종 정산."""
    input_data = _read_stdin_json()

    transcript_path = input_data.get("agent_transcript_path", "")
    if not transcript_path or not os.path.isfile(transcript_path):
        sys.exit(0)

    subagents_dir = _find_subagents_dir(transcript_path)
    if not subagents_dir or not os.path.isdir(subagents_dir):
        print("[usage-sync] subagents directory not found", file=sys.stderr)
        sys.exit(0)

    work_dir = _find_work_dir()
    if not work_dir:
        sys.exit(0)

    usage_file = os.path.join(work_dir, "usage.json")
    lock_dir = usage_file + ".lockdir"

    if not _acquire_lock(lock_dir, max_wait=10):
        print("[usage-sync] WARNING: Could not acquire lock", file=sys.stderr)
        sys.exit(0)

    try:
        usage_data = _load_usage(usage_file)
        agent_map = usage_data.get("_agent_map", {})

        # subagents/ 내 모든 agent-*.jsonl 파일 열거
        agent_files = sorted(glob.glob(os.path.join(subagents_dir, "agent-*.jsonl")))
        if not agent_files:
            print("[usage-sync] No agent JSONL files found", file=sys.stderr)
            _release_lock(lock_dir)
            sys.exit(0)

        # 에이전트별 JSONL 파싱 (보완 모드: track으로 수집 완료된 에이전트는 스킵)
        worker_tokens = {}
        skipped_agents = []
        for agent_file in agent_files:
            a_type = _resolve_agent_type(agent_file, agent_map)
            if not a_type:
                print(
                    f"[usage-sync] WARNING: Could not identify agent_type for {os.path.basename(agent_file)}",
                    file=sys.stderr,
                )
                continue

            # 보완 모드 스킵: track으로 수집 완료된 비-worker 에이전트
            if a_type != "worker":
                existing = usage_data["agents"].get(a_type)
                if isinstance(existing, dict) and existing.get("method") == "subagent_transcript":
                    skipped_agents.append(a_type)
                    continue

            tokens = parse_jsonl_usage(agent_file)
            if not tokens:
                continue

            tokens["method"] = "jsonl_full_parse"

            if a_type == "worker":
                basename = os.path.basename(agent_file)
                agent_id = basename[len("agent-"):-len(".jsonl")] if basename.startswith("agent-") else basename
                worker_tokens[agent_id] = tokens
            else:
                usage_data["agents"][a_type] = tokens

        # worker 토큰 처리 (보완 모드: track으로 수집 완료된 worker는 스킵)
        if worker_tokens:
            if "workers" not in usage_data["agents"]:
                usage_data["agents"]["workers"] = {}

            existing_workers = usage_data["agents"]["workers"]
            pending = usage_data.get("_pending_workers", {})

            # agent_to_task: _pending_workers 값(task_id)이 키인 경우와
            # agent_id가 키인 경우 모두 처리.
            # _pending_workers는 {task_id: task_id} 또는 {agent_id: task_id} 형태일 수 있음.
            # agent_id가 hex 문자열이고 pending이 {task_id: task_id} 형태인 경우:
            # pending의 값(task_id) 목록과 worker_tokens의 agent_id 목록을 순서대로 매핑.
            # agent_to_task: _pending_workers의 pkey가 실제 agent_id인 경우 직접 매핑
            agent_to_task = {}
            for pkey, ptid in pending.items():
                agent_to_task[pkey] = ptid

            # task_id=task_id 형태의 pending만 unassigned 큐에 추가.
            # agent_id가 hex 문자열일 때 순서대로 매핑하기 위한 폴백 큐.
            already_mapped_tasks = set(existing_workers.keys())
            unassigned_queue = [
                ptid for pkey, ptid in pending.items()
                if pkey == ptid and ptid not in already_mapped_tasks
            ]

            for agent_id, tokens in worker_tokens.items():
                # 우선: agent_to_task에서 직접 매핑 시도
                task_id = agent_to_task.get(agent_id)

                if not task_id:
                    # agent_id가 hex 문자열인 경우: unassigned_queue에서 순서대로 할당
                    if unassigned_queue:
                        task_id = unassigned_queue.pop(0)
                        print(
                            f"[usage-sync] INFO: batch agent_id '{agent_id}' mapped to task_id '{task_id}' via queue",
                            file=sys.stderr,
                        )

                key = task_id if task_id else agent_id
                # 보완 모드 스킵: track으로 수집 완료된 worker task
                if isinstance(existing_workers.get(key), dict) and existing_workers[key].get("method") == "subagent_transcript":
                    skipped_agents.append(f"worker/{key}")
                    continue
                existing_workers[key] = tokens

        # 스킵된 에이전트 목록 로그
        if skipped_agents:
            print(f"[usage-sync] batch: skipped already-tracked: {skipped_agents}", file=sys.stderr)

        # 메인 세션 JSONL 파싱 (오케스트레이터 토큰)
        main_jsonl = _find_main_session_jsonl(subagents_dir)
        if not main_jsonl:
            main_jsonl = _find_main_session_from_status(work_dir)

        if main_jsonl:
            orc_tokens = parse_jsonl_usage(main_jsonl)
            if orc_tokens:
                orc_tokens["method"] = "jsonl_full_parse"
                usage_data["agents"]["orchestrator"] = orc_tokens
        else:
            print("[usage-sync] WARNING: Main session JSONL not found", file=sys.stderr)

        os.makedirs(os.path.dirname(usage_file), exist_ok=True)
        atomic_write_json(usage_file, usage_data)
    finally:
        _release_lock(lock_dir)


# =============================================================================
# 메인
# =============================================================================

def main():
    # 서브커맨드 파싱. 인자 없으면 track (하위 호환)
    subcmd = sys.argv[1] if len(sys.argv) > 1 else "track"

    if subcmd == "track":
        cmd_track()
    elif subcmd == "batch":
        cmd_batch()
    else:
        print(f"[usage-sync] Unknown subcommand: {subcmd} (track|batch)", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
