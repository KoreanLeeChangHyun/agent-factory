#!/usr/bin/env -S python3 -u
"""
SubagentStop(done) Hook: JSONL 일괄 파싱으로 정확한 에이전트별 토큰 사용량 집계

done 에이전트 종료 시점에 subagents/ 디렉터리 전체 JSONL을 파싱하고,
메인 세션 JSONL에서 오케스트레이터 토큰을 집계하여 usage.json에 기록한다.

입력 (stdin JSON): agent_type, agent_id, agent_transcript_path
비차단 원칙: 모든 에러 경로에서 exit 0
"""

import glob
import json
import os
import subprocess
import sys
import time

# utils 패키지 import
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from utils.common import (
    atomic_write_json,
    load_json_file,
    resolve_project_root,
)

PROJECT_ROOT = resolve_project_root()
REGISTRY_FILE = os.path.join(PROJECT_ROOT, ".workflow", "registry.json")

# 파일 크기 상한 (50MB) - 초과 시 경고 출력 후 계속 시도
MAX_JSONL_SIZE = 50 * 1024 * 1024


def parse_jsonl_usage(filepath):
    """JSONL 파일의 모든 assistant 레코드 usage를 합산한다.

    Args:
        filepath: JSONL 파일 경로

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
            f"[usage-jsonl-sync] WARNING: JSONL file exceeds {MAX_JSONL_SIZE // (1024*1024)}MB: {filepath} ({file_size // (1024*1024)}MB)",
            file=sys.stderr,
        )

    try:
        with open(filepath, "r", encoding="utf-8") as f:
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
        print(f"[usage-jsonl-sync] WARNING: Failed to parse {filepath}: {e}", file=sys.stderr)
        return None

    return totals


def find_subagents_dir(transcript_path):
    """agent_transcript_path에서 subagents/ 디렉터리 경로를 역산한다.

    transcript_path 예시: ~/.claude/projects/<slug>/<session>/subagents/agent-<id>.jsonl
    """
    parent = os.path.dirname(transcript_path)
    if os.path.basename(parent) == "subagents":
        return parent
    return None


def find_main_session_jsonl(subagents_dir):
    """subagents/ 디렉터리의 상위에서 메인 세션 JSONL을 찾는다.

    subagents_dir 예시: ~/.claude/projects/<slug>/<session>/subagents/
    session_dir: ~/.claude/projects/<slug>/<session>/
    메인 JSONL: ~/.claude/projects/<slug>/<session>.jsonl
    """
    session_dir = os.path.dirname(subagents_dir)
    session_jsonl = session_dir + ".jsonl"
    if os.path.isfile(session_jsonl):
        return session_jsonl
    return None


def find_main_session_from_status(work_dir):
    """status.json의 linked_sessions에서 메인 세션 JSONL 경로를 구성한다.

    폴백: subagents 경로에서 역산할 수 없는 경우에 사용
    """
    status_file = os.path.join(work_dir, "status.json")
    status = load_json_file(status_file)
    if not isinstance(status, dict):
        return None

    sessions = status.get("linked_sessions", [])
    if not sessions:
        return None

    # project slug 구성
    project_slug = PROJECT_ROOT.replace("/", "-")
    if project_slug.startswith("-"):
        pass  # 그대로 유지 (-home-deus-workspace-claude)

    # ~/.claude/projects/ 또는 ~/.config/claude/projects/ 탐색
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

    return None


def resolve_agent_type_from_map(agent_filename, agent_map):
    """_agent_map에서 agent-<id>.jsonl의 agent_type을 식별한다.

    agent_filename: "agent-<id>.jsonl"
    agent_map: { agent_id: agent_type, ... }
    """
    # agent-<id>.jsonl -> <id>
    basename = os.path.basename(agent_filename)
    if basename.startswith("agent-") and basename.endswith(".jsonl"):
        agent_id = basename[len("agent-"):-len(".jsonl")]
        return agent_map.get(agent_id)
    return None


def resolve_agent_type_from_jsonl(filepath):
    """JSONL 파일의 user 레코드에서 slug 필드를 읽어 agent_type을 추정한다.

    폴백: _agent_map에 해당 agent_id가 없는 경우 사용
    """
    valid_types = {
        "init", "planner", "indexer", "worker", "explorer",
        "validator", "reporter", "strategy", "done",
    }
    try:
        with open(filepath, "r", encoding="utf-8") as f:
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
                    # slug가 에이전트 유형 이름과 일치하는지 확인
                    if slug in valid_types:
                        return slug
                    # slug에서 에이전트 유형 추출 시도 (예: "worker-task-xxx")
                    for t in valid_types:
                        if slug.startswith(t):
                            return t
                    break  # 첫 번째 user 레코드만 검사
    except Exception:
        pass
    return None


def main():
    # stdin JSON 읽기
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    agent_type = input_data.get("agent_type", "")
    transcript_path = input_data.get("agent_transcript_path", "")

    # done 에이전트가 아니면 종료 (이 스크립트는 done 종료 시점에만 실행)
    if agent_type != "done":
        sys.exit(0)

    if not transcript_path or not os.path.isfile(transcript_path):
        sys.exit(0)

    # subagents/ 디렉터리 탐색
    subagents_dir = find_subagents_dir(transcript_path)
    if not subagents_dir or not os.path.isdir(subagents_dir):
        print("[usage-jsonl-sync] subagents directory not found", file=sys.stderr)
        sys.exit(0)

    # registry.json에서 활성 워크플로우의 workDir 조회
    if not os.path.isfile(REGISTRY_FILE):
        sys.exit(0)

    registry = load_json_file(REGISTRY_FILE)
    if not isinstance(registry, dict) or not registry:
        sys.exit(0)

    work_dir = None
    for key, entry in registry.items():
        if isinstance(entry, dict) and "workDir" in entry:
            rel_dir = entry["workDir"]
            candidate = os.path.join(PROJECT_ROOT, rel_dir) if not rel_dir.startswith("/") else rel_dir
            if os.path.isdir(candidate):
                work_dir = candidate
                break

    if not work_dir:
        sys.exit(0)

    usage_file = os.path.join(work_dir, "usage.json")

    # mkdir 기반 POSIX 잠금
    lock_dir = usage_file + ".lockdir"
    max_wait = 10  # JSONL 일괄 파싱은 시간이 더 걸릴 수 있으므로 대기 시간 확장
    waited = 0
    locked = False

    while waited < max_wait:
        try:
            os.makedirs(lock_dir)
            locked = True
            break
        except OSError:
            time.sleep(1)
            waited += 1

    if not locked:
        print("[usage-jsonl-sync] WARNING: Could not acquire lock", file=sys.stderr)
        sys.exit(0)

    try:
        # usage.json 읽기
        usage_data = load_json_file(usage_file)
        if not isinstance(usage_data, dict):
            usage_data = {"$schema": "usage-v1", "agents": {}, "totals": {}, "_pending_workers": {}}

        if "agents" not in usage_data:
            usage_data["agents"] = {}

        # _agent_map 읽기 (usage_sync.py가 SubagentStop마다 기록)
        agent_map = usage_data.get("_agent_map", {})

        # subagents/ 디렉터리 내 모든 agent-*.jsonl 파일 열거
        agent_files = sorted(glob.glob(os.path.join(subagents_dir, "agent-*.jsonl")))

        if not agent_files:
            print("[usage-jsonl-sync] No agent JSONL files found", file=sys.stderr)
            # 잠금 해제 후 종료
            try:
                os.rmdir(lock_dir)
            except OSError:
                pass
            sys.exit(0)

        # 에이전트별 JSONL 파싱 및 usage 합산
        worker_tokens = {}
        for agent_file in agent_files:
            # agent_type 식별
            a_type = resolve_agent_type_from_map(agent_file, agent_map)
            if not a_type:
                a_type = resolve_agent_type_from_jsonl(agent_file)
            if not a_type:
                print(
                    f"[usage-jsonl-sync] WARNING: Could not identify agent_type for {os.path.basename(agent_file)}",
                    file=sys.stderr,
                )
                continue

            tokens = parse_jsonl_usage(agent_file)
            if not tokens:
                continue

            tokens["method"] = "jsonl_full_parse"

            if a_type == "worker":
                # worker는 agent_id를 키로 임시 저장 (아래에서 _pending_workers와 매핑)
                basename = os.path.basename(agent_file)
                agent_id = basename[len("agent-"):-len(".jsonl")] if basename.startswith("agent-") else basename
                worker_tokens[agent_id] = tokens
            else:
                # worker 이외 에이전트는 직접 기록 (기존 SubagentStop 개별 추적 값을 덮어씀)
                usage_data["agents"][a_type] = tokens

        # worker 토큰 처리: _pending_workers 매핑 또는 agent_id 직접 사용
        if worker_tokens:
            if "workers" not in usage_data["agents"]:
                usage_data["agents"]["workers"] = {}

            existing_workers = usage_data["agents"]["workers"]
            pending = usage_data.get("_pending_workers", {})

            # 기존 매핑된 worker 데이터의 agent_id -> task_id 역매핑 구성
            # pending에 남아있는 매핑과, 이미 매핑 완료된 데이터 모두 활용
            agent_to_task = {}
            for aid, tid in pending.items():
                agent_to_task[aid] = tid

            # 기존 workers에 이미 매핑된 데이터가 있으면 그 task_id를 유지
            for tid, tdata in existing_workers.items():
                if isinstance(tdata, dict):
                    # 이미 매핑된 task_id는 유지
                    pass

            for agent_id, tokens in worker_tokens.items():
                task_id = agent_to_task.get(agent_id)
                if task_id:
                    existing_workers[task_id] = tokens
                else:
                    # task_id를 찾을 수 없으면 기존 매핑 유지 또는 agent_id를 키로 사용
                    existing_workers[agent_id] = tokens

        # 메인 세션 JSONL 파싱 (오케스트레이터 토큰)
        main_jsonl = find_main_session_jsonl(subagents_dir)
        if not main_jsonl:
            main_jsonl = find_main_session_from_status(work_dir)

        if main_jsonl:
            orc_tokens = parse_jsonl_usage(main_jsonl)
            if orc_tokens:
                orc_tokens["method"] = "jsonl_full_parse"
                usage_data["agents"]["orchestrator"] = orc_tokens
        else:
            print("[usage-jsonl-sync] WARNING: Main session JSONL not found, orchestrator tokens not updated", file=sys.stderr)

        # usage.json 저장
        os.makedirs(os.path.dirname(usage_file), exist_ok=True)
        atomic_write_json(usage_file, usage_data)

    finally:
        try:
            os.rmdir(lock_dir)
        except OSError:
            pass

    # update_state.py usage-finalize 호출
    try:
        update_state_script = os.path.join(
            PROJECT_ROOT, ".claude", "scripts", "state", "update_state.py"
        )
        rel_work_dir = os.path.relpath(work_dir, PROJECT_ROOT)
        if os.path.isfile(update_state_script):
            subprocess.run(
                [sys.executable, update_state_script, "usage-finalize", rel_work_dir],
                capture_output=True,
                text=True,
                timeout=30,
            )
    except Exception as e:
        print(f"[usage-jsonl-sync] WARNING: usage-finalize call failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
