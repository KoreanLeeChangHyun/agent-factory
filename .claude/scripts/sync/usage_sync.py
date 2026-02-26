#!/usr/bin/env -S python3 -u
"""
SubagentStop Hook: 워크플로우 서브에이전트별 토큰 사용량 자동 추적
(usage-tracker.sh -> usage_sync.py 1:1 포팅)

입력 (stdin JSON): agent_type, agent_id, agent_transcript_path
비차단 원칙: 모든 에러 경로에서 exit 0
"""

import json
import os
import subprocess
import sys
import tempfile
import shutil
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


def main():
    # stdin JSON 읽기
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    agent_type = input_data.get("agent_type", "")
    agent_id = input_data.get("agent_id", "")
    transcript_path = input_data.get("agent_transcript_path", "")

    # 워크플로우 에이전트 필터링
    if agent_type not in ("init", "planner", "indexer", "worker", "explorer", "validator", "reporter", "strategy", "done"):
        sys.exit(0)

    # transcript 경로 유효성 확인
    if not transcript_path or not os.path.isfile(transcript_path):
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

    # JSONL 파싱: 전체 파일의 모든 assistant 레코드 usage를 합산
    # (usage는 API 호출당 증분값이므로 마지막 1개가 아닌 전체 합산 필요)
    tokens = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
    }
    found_any = False

    try:
        file_size = os.path.getsize(transcript_path)
        # 50MB 초과 시 tail 폴백 (대용량 JSONL 성능 보호)
        if file_size > 50 * 1024 * 1024:
            result = subprocess.run(
                ["tail", "-n", "500", transcript_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        else:
            with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
    except Exception:
        sys.exit(0)

    if not lines or all(not l.strip() for l in lines):
        print(f"[usage-tracker] JSONL file empty or no valid lines: {transcript_path}", file=sys.stderr)
        sys.exit(0)

    for line in lines:
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        if data.get("isApiErrorMessage"):
            continue

        if data.get("type") != "assistant":
            continue

        usage = None
        msg = data.get("message")
        if isinstance(msg, dict) and "usage" in msg:
            usage = msg["usage"]
        elif "usage" in data:
            usage = data["usage"]

        if isinstance(usage, dict):
            tokens["input_tokens"] += usage.get("input_tokens", 0)
            tokens["output_tokens"] += usage.get("output_tokens", 0)
            tokens["cache_creation_tokens"] += usage.get("cache_creation_input_tokens", 0)
            tokens["cache_read_tokens"] += usage.get("cache_read_input_tokens", 0)
            found_any = True

    if not found_any:
        print(f"[usage-tracker] No valid usage data found in: {transcript_path}", file=sys.stderr)
        sys.exit(0)

    # mkdir 기반 POSIX 잠금
    lock_dir = usage_file + ".lockdir"
    max_wait = 5
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
        sys.exit(0)

    try:
        # usage.json 읽기
        usage_data = load_json_file(usage_file)
        if not isinstance(usage_data, dict):
            usage_data = {"$schema": "usage-v1", "agents": {}, "totals": {}, "_pending_workers": {}}

        if "agents" not in usage_data:
            usage_data["agents"] = {}

        tokens["method"] = "subagent_transcript"

        # _agent_map에 agent_id -> agent_type 매핑 기록
        # (usage_jsonl_sync.py가 done SubagentStop 시점에 참조)
        if "_agent_map" not in usage_data:
            usage_data["_agent_map"] = {}
        usage_data["_agent_map"][agent_id] = agent_type

        if agent_type == "worker":
            pending = usage_data.get("_pending_workers", {})
            task_id = pending.get(agent_id, None)

            if "workers" not in usage_data["agents"]:
                usage_data["agents"]["workers"] = {}

            if task_id:
                usage_data["agents"]["workers"][task_id] = tokens
                if agent_id in pending:
                    del pending[agent_id]
            else:
                print(
                    f"[usage-tracker] WARNING: agent_id '{agent_id}' not found in _pending_workers, using agent_id as key",
                    file=sys.stderr,
                )
                usage_data["agents"]["workers"][agent_id] = tokens
        else:
            usage_data["agents"][agent_type] = tokens

        os.makedirs(os.path.dirname(usage_file), exist_ok=True)
        atomic_write_json(usage_file, usage_data)
    finally:
        try:
            os.rmdir(lock_dir)
        except OSError:
            pass


if __name__ == "__main__":
    main()
