#!/usr/bin/env -S python3 -u
"""
cleanup_zombie.py - 좀비 워크플로우 정리 독립 스크립트

기능:
  1. .workflow/ 하위에서 TTL(24시간) 만료 + 미완료 status.json을 STALE로 전환
  2. registry.json에서 STALE/COMPLETED/FAILED/CANCELLED 엔트리 제거 + 고아 정리

사용법:
  python3 cleanup_zombie.py [project_root]

인자:
  project_root - (선택적) 프로젝트 루트 경로. 미지정 시 스크립트 위치 기준으로 자동 탐지
"""

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from data.constants import KST, ZOMBIE_TTL_HOURS, REPORT_TTL_HOURS, TERMINAL_PHASES

_KST = KST
_TTL_HOURS = ZOMBIE_TTL_HOURS
_REPORT_TTL_HOURS = REPORT_TTL_HOURS
_TERMINAL_PHASES = TERMINAL_PHASES


def _atomic_write_json(path, data):
    """JSON 원자적 쓰기."""
    dir_name = os.path.dirname(path)
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        shutil.move(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _process_status_file(status_file, status_dir, now):
    """status.json을 TTL 검사하여 STALE로 전환. 반환: 전환 여부."""
    try:
        with open(status_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        phase = data.get("phase", "")
        if phase in _TERMINAL_PHASES:
            return False

        time_str = data.get("updated_at") or data.get("created_at", "")
        if not time_str:
            return False

        created = datetime.fromisoformat(time_str)
        elapsed = now - created

        if elapsed.total_seconds() > _TTL_HOURS * 3600:
            transition_time = now.strftime("%Y-%m-%dT%H:%M:%S+09:00")
            data["phase"] = "STALE"
            data["updated_at"] = transition_time
            if "transitions" not in data:
                data["transitions"] = []
            data["transitions"].append({
                "from": phase,
                "to": "STALE",
                "at": transition_time,
            })
            _atomic_write_json(status_file, data)
            return True

        return False
    except (json.JSONDecodeError, IOError, ValueError):
        return False


def _step1_mark_stale(workflow_root):
    """Step 1: .workflow/ 하위에서 TTL 만료 워크플로우를 STALE로 전환."""
    if not os.path.isdir(workflow_root):
        return

    now = datetime.now(_KST)
    stale_count = 0

    for entry in os.listdir(workflow_root):
        entry_path = os.path.join(workflow_root, entry)
        if not os.path.isdir(entry_path) or entry.startswith("."):
            continue

        # 중첩 구조 탐색: .workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>/status.json
        found = False
        for work_name in os.listdir(entry_path):
            wn_path = os.path.join(entry_path, work_name)
            if not os.path.isdir(wn_path) or work_name.startswith("."):
                continue
            for cmd_name in os.listdir(wn_path):
                cmd_path = os.path.join(wn_path, cmd_name)
                if not os.path.isdir(cmd_path):
                    continue
                nested_status = os.path.join(cmd_path, "status.json")
                if os.path.exists(nested_status):
                    if _process_status_file(nested_status, cmd_path, now):
                        stale_count += 1
                    found = True

        if not found:
            # 레거시 플랫 구조 호환
            flat_status = os.path.join(entry_path, "status.json")
            if os.path.exists(flat_status):
                if _process_status_file(flat_status, entry_path, now):
                    stale_count += 1

    if stale_count > 0:
        print(f"[INFO] zombie cleanup: {stale_count} workflow(s) marked as STALE", file=sys.stderr)


def _step2_clean_registry(project_root):
    """Step 2: registry.json 좀비 정리."""
    registry_file = os.path.join(project_root, ".workflow", "registry.json")
    if not os.path.isfile(registry_file):
        return

    try:
        with open(registry_file, "r", encoding="utf-8") as f:
            registry = json.load(f)
    except (json.JSONDecodeError, IOError):
        return

    if not isinstance(registry, dict) or not registry:
        return

    now = datetime.now(_KST)
    keys_to_remove = []  # (key, reason) 튜플

    for key, entry in registry.items():
        work_dir = entry.get("workDir", "")
        if not work_dir:
            keys_to_remove.append((key, "empty workDir"))
            continue

        # status.json 존재 여부 확인 (고아 정리)
        if os.path.isabs(work_dir):
            abs_work_dir = work_dir
        else:
            abs_work_dir = os.path.join(project_root, work_dir)

        status_file = os.path.join(abs_work_dir, "status.json")

        if not os.path.isfile(status_file):
            keys_to_remove.append((key, "orphan (no status.json)"))
            continue

        # status.json 읽기
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                status_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            keys_to_remove.append((key, "orphan (status.json unreadable)"))
            continue

        status_phase = status_data.get("phase", "")
        registry_phase = entry.get("phase", "")

        # 1. 기존 정리: STALE/COMPLETED/FAILED/CANCELLED (status.json 기준)
        if status_phase in _TERMINAL_PHASES:
            keys_to_remove.append((key, f"status phase={status_phase}"))
            continue

        # 2. registry와 status.json의 phase 불일치 정리
        if status_phase in _TERMINAL_PHASES and registry_phase not in _TERMINAL_PHASES:
            keys_to_remove.append((key, f"phase mismatch: registry={registry_phase}, status={status_phase}"))
            continue

        # 3. REPORT 단계 잔류 엔트리 정리 (1시간 초과)
        if registry_phase == "REPORT" or status_phase == "REPORT":
            time_str = status_data.get("updated_at") or status_data.get("created_at", "")
            if time_str:
                try:
                    updated = datetime.fromisoformat(time_str)
                    elapsed = now - updated
                    if elapsed.total_seconds() > _REPORT_TTL_HOURS * 3600:
                        keys_to_remove.append((key, f"REPORT stale ({elapsed.total_seconds()/3600:.1f}h elapsed)"))
                        continue
                except (ValueError, TypeError):
                    pass

    if not keys_to_remove:
        return

    for key, _reason in keys_to_remove:
        del registry[key]

    _atomic_write_json(registry_file, registry)

    details = "; ".join(f"{k}({r})" for k, r in keys_to_remove)
    print(f"[INFO] registry cleanup: {len(keys_to_remove)} entry(ies) removed [{details}]", file=sys.stderr)


def main():
    if len(sys.argv) >= 2 and sys.argv[1]:
        project_root = sys.argv[1]
    else:
        project_root = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))

    workflow_root = os.path.join(project_root, ".workflow")

    _step1_mark_stale(workflow_root)
    _step2_clean_registry(project_root)


if __name__ == "__main__":
    main()
