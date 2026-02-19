#!/usr/bin/env -S python3 -u
"""
워크플로우 자동 계속 Stop Hook (workflow-auto-continue.sh -> workflow_auto_continue.py 1:1 포팅)

입력: stdin으로 JSON (session_id, stop_hook_active 등)
출력: 차단 시 {"decision":"block","reason":"..."}, 통과 시 빈 출력

안전장치:
  - 연속 3회 차단 시 허용 (무한 루프 방지)
  - PLAN phase에서는 차단하지 않음
  - 종료 phase에서는 차단하지 않음
  - .done-marker 파일 존재 시 즉시 통과
  - TTL 30분: 갱신 없으면 STALE 전환
  - 세션 불일치: 고아로 판단하여 차단하지 않음
"""

import json
import os
import sys
import tempfile
import shutil
from datetime import datetime, timedelta, timezone

# _utils 패키지 import
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from _utils.common import (
    atomic_write_json,
    load_json_file,
    resolve_project_root,
)

PROJECT_ROOT = resolve_project_root()
STALE_TTL_MINUTES = 30
COUNTER_FILE = os.path.join(PROJECT_ROOT, ".workflow", ".stop-block-counter")


def clear_counter():
    """카운터 파일 제거."""
    try:
        if os.path.exists(COUNTER_FILE):
            os.remove(COUNTER_FILE)
    except OSError:
        pass


def main():
    # bypass 체크
    if os.environ.get("WORKFLOW_GUARD_DISABLE") == "1":
        sys.exit(0)
    if os.path.isfile(os.path.join(PROJECT_ROOT, ".workflow", "bypass")):
        sys.exit(0)

    # .done-marker 파일 존재 시 즉시 통과
    done_marker = os.path.join(PROJECT_ROOT, ".workflow", ".done-marker")
    if os.path.exists(done_marker):
        clear_counter()
        sys.exit(0)

    # stdin에서 JSON 읽기
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    stop_hook_active = data.get("stop_hook_active", False)
    current_session_id = data.get("session_id", "")

    # registry.json에서 활성 워크플로우 확인
    registry_path = os.path.join(PROJECT_ROOT, ".workflow", "registry.json")
    if not os.path.exists(registry_path):
        clear_counter()
        sys.exit(0)

    registry = load_json_file(registry_path)
    if not isinstance(registry, dict) or not registry:
        clear_counter()
        sys.exit(0)

    # 활성 워크플로우 필터링
    terminal_phases = ("COMPLETED", "FAILED", "CANCELLED", "STALE", "", "REPORT")
    active_workflows = []
    for key, entry in registry.items():
        phase = entry.get("phase", "").upper()
        if phase not in terminal_phases:
            active_workflows.append({"key": key, "phase": phase, "entry": entry})

    if not active_workflows:
        clear_counter()
        sys.exit(0)

    # --- TTL 검사 ---
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    stale_threshold = STALE_TTL_MINUTES * 60

    registry_changed = False
    still_active = []

    for wf in active_workflows:
        key = wf["key"]
        entry = wf["entry"]
        work_dir = entry.get("workDir", "")

        if not work_dir:
            continue

        abs_work_dir = work_dir if work_dir.startswith("/") else os.path.join(PROJECT_ROOT, work_dir)
        status_file = os.path.join(abs_work_dir, "status.json")
        is_stale = False

        if not os.path.isfile(status_file):
            registry[key]["phase"] = "STALE"
            registry_changed = True
            continue

        status_data = load_json_file(status_file)
        if not isinstance(status_data, dict):
            continue

        # 세션 ID 불일치 검사
        wf_session_id = status_data.get("session_id", "")
        wf_linked = status_data.get("linked_sessions", [])
        session_match = (
            current_session_id
            and wf_session_id
            and (current_session_id == wf_session_id or current_session_id in wf_linked)
        )

        # TTL 검사
        time_str = status_data.get("updated_at") or status_data.get("created_at", "")
        elapsed = 0
        if time_str:
            try:
                updated = datetime.fromisoformat(time_str)
                elapsed = (now - updated).total_seconds()
            except (ValueError, TypeError):
                pass

        # STALE 판정 — 세션이 일치하면 자기 워크플로우이므로 STALE 전환하지 않음
        if not session_match and (current_session_id or elapsed > stale_threshold):
            is_stale = True
            transition_time = now.strftime("%Y-%m-%dT%H:%M:%S+09:00")
            old_phase = status_data.get("phase", "")
            status_data["phase"] = "STALE"
            status_data["updated_at"] = transition_time
            if "transitions" not in status_data:
                status_data["transitions"] = []
            status_data["transitions"].append({"from": old_phase, "to": "STALE", "at": transition_time})

            # status.json 원자적 쓰기
            try:
                atomic_write_json(status_file, status_data)
            except Exception:
                pass

            registry[key]["phase"] = "STALE"
            registry_changed = True

        if not is_stale:
            still_active.append(wf)

    # 레지스트리 변경 시 저장
    if registry_changed:
        try:
            atomic_write_json(registry_path, registry)
        except Exception:
            pass

    # TTL 정리 후 활성 워크플로우가 없으면 통과
    if not still_active:
        clear_counter()
        sys.exit(0)

    # PLAN phase 예외
    all_plan = all(w["phase"] == "PLAN" for w in still_active)
    if all_plan:
        sys.exit(0)

    # 카운터 확인
    block_count = 0
    try:
        if os.path.exists(COUNTER_FILE):
            with open(COUNTER_FILE, "r") as f:
                block_count = int(f.read().strip())
    except (ValueError, IOError):
        block_count = 0

    # 연속 3회 차단 시 허용
    if block_count >= 3:
        clear_counter()
        sys.exit(0)

    # 카운터 증가
    block_count += 1
    try:
        os.makedirs(os.path.dirname(COUNTER_FILE), exist_ok=True)
        with open(COUNTER_FILE, "w") as f:
            f.write(str(block_count))
    except IOError:
        pass

    # 차단
    result = {"decision": "block", "reason": f"Continue workflow. ({block_count}/3)"}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
