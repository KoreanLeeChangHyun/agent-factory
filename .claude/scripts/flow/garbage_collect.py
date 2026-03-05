#!/usr/bin/env -S python3 -u
"""garbage_collect.py - 좀비 워크플로우 정리 독립 스크립트.

기능:
  1. .workflow/ 하위에서 TTL(24시간) 만료 + 미완료 status.json을 STALE로 전환

사용법:
  python3 garbage_collect.py [project_root]

인자:
  project_root - (선택적) 프로젝트 루트 경로. 미지정 시 스크립트 위치 기준으로 자동 탐지
"""

from __future__ import annotations

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

from data.constants import KST, ZOMBIE_TTL_HOURS, TERMINAL_STEPS, TERMINAL_PHASES

_KST = KST
_TTL_HOURS = ZOMBIE_TTL_HOURS
_TERMINAL_PHASES = TERMINAL_STEPS  # TERMINAL_STEPS 사용 (TERMINAL_PHASES는 별칭)


def _atomic_write_json(path: str, data: object) -> None:
    """JSON을 임시 파일에 쓴 후 원자적으로 대상 경로로 이동한다.

    Args:
        path: 최종 저장할 파일 경로
        data: JSON으로 직렬화할 데이터 객체

    Raises:
        Exception: 쓰기 또는 이동 실패 시 임시 파일을 삭제하고 재발생.
    """
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


def _process_status_file(status_file: str, status_dir: str, now: datetime) -> bool:
    """status.json을 TTL 검사하여 STALE로 전환한다.

    Args:
        status_file: 검사할 status.json 파일 경로
        status_dir: status.json이 위치한 디렉터리 경로
        now: 현재 시각 (KST timezone-aware)

    Returns:
        STALE로 전환되었으면 True, 그렇지 않으면 False.
    """
    try:
        with open(status_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        phase = data.get("step") or data.get("phase", "")
        if phase in _TERMINAL_PHASES:
            return False

        time_str = data.get("updated_at") or data.get("created_at", "")
        if not time_str:
            return False

        created = datetime.fromisoformat(time_str)
        elapsed = now - created

        if elapsed.total_seconds() > _TTL_HOURS * 3600:
            transition_time = now.strftime("%Y-%m-%dT%H:%M:%S+09:00")
            data["step"] = "STALE"
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
    except (json.JSONDecodeError, IOError, ValueError, TypeError):
        return False


def _step1_mark_stale(workflow_root: str) -> None:
    """Step 1: .workflow/ 하위에서 TTL 만료 워크플로우를 STALE로 전환한다.

    중첩 구조(.workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>/status.json)와
    레거시 플랫 구조(.workflow/<id>/status.json)를 모두 지원한다.

    Args:
        workflow_root: .workflow 디렉터리 절대 경로
    """
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


def main() -> None:
    """CLI 진입점. project_root를 인자로 받아 좀비 워크플로우를 정리한다.

    Args (sys.argv):
        project_root: (선택적) 프로젝트 루트 경로.
                      미지정 시 스크립트 위치 기준으로 자동 탐지.
    """
    if len(sys.argv) >= 2 and sys.argv[1]:
        project_root = sys.argv[1]
    else:
        project_root = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))

    workflow_root = os.path.join(project_root, ".workflow")

    _step1_mark_stale(workflow_root)


if __name__ == "__main__":
    main()
