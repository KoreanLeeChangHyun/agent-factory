#!/usr/bin/env -S python3 -u
"""
init_workflow.py - 워크플로우 초기화 통합 스크립트

prompt.txt 읽기, 디렉터리 생성, 파일 복사/클리어, 메타데이터 생성, 좀비 정리,
레지스트리 등록을 일괄 수행한다.

사용법:
  python3 init_workflow.py <command> <title> [mode]

인자:
  command - 실행 명령어 (implement, review, research, strategy)
  title   - 작업 제목 (init 에이전트가 prompt.txt로부터 생성한 한글 제목)
  mode    - (선택적) 워크플로우 모드 (full, strategy, noplan). 기본값: full

출력 (stdout):
  workDir=.workflow/<registryKey>/<workName>/<command>
  registryKey=<YYYYMMDD-HHMMSS>
  workId=<HHMMSS>
  workName=<변환된 작업이름>
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
_SCRIPTS_DIR = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from data.constants import KST, KEEP_COUNT, VALID_COMMANDS, VALID_MODES, WORK_NAME_MAX_LEN

_VALID_COMMANDS = VALID_COMMANDS
_VALID_MODES = VALID_MODES
_KST = KST


def _err(msg):
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(1)


def _warn(msg):
    print(f"[WARN] {msg}", file=sys.stderr)


def _sanitize_work_name(title):
    """title에서 workName 변환 (공백->하이픈, 특수문자 제거, 20자 절단)."""
    name = re.sub(r"\s+", "-", title.strip())
    name = re.sub(r'[!@#$%^&*()/:;<>?|~"`\\]', "", name)
    name = re.sub(r"\.", "-", name)
    name = re.sub(r"-{2,}", "-", name)
    name = name.strip("-")
    name = name[:WORK_NAME_MAX_LEN]
    return name


def _atomic_write_json(path, data):
    """JSON 원자적 쓰기 (tmpfile + mv)."""
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


def main():
    # --- 인자 확인 ---
    if len(sys.argv) < 3:
        _err(f"사용법: {sys.argv[0]} <command> <title> [mode]")

    command = sys.argv[1]
    title = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "full"

    if command not in _VALID_COMMANDS:
        _err(f"Invalid command: '{command}'. Allowed: {', '.join(sorted(_VALID_COMMANDS))}")

    if not title or title.isspace():
        _err("Title must not be empty")

    if title.startswith((".workflow/", "./", "/")):
        _err("Invalid title: must not be a file path")

    if mode not in _VALID_MODES:
        _warn(f"Unknown mode '{mode}', defaulting to 'full'")
        mode = "full"

    claude_sid = os.environ.get("CLAUDE_SESSION_ID", "")

    # --- Step 0: registryKey/workId/workName/workDir 자동 생성 ---
    now = datetime.now(_KST)
    registry_key = now.strftime("%Y%m%d-%H%M%S")
    work_id = registry_key.split("-")[1]  # HHMMSS

    work_name = _sanitize_work_name(title)
    if not work_name:
        _err(f"Title produced empty workName after sanitization: '{title}'")

    work_dir = f".workflow/{registry_key}/{work_name}/{command}"
    abs_work_dir = os.path.join(_PROJECT_ROOT, work_dir)

    prompt_dir = os.path.join(_PROJECT_ROOT, ".prompt")
    prompt_file = os.path.join(prompt_dir, "prompt.txt")
    querys_file = os.path.join(prompt_dir, "querys.txt")

    # --- Step 1: prompt.txt 읽기 ---
    prompt_content = ""
    if os.path.isfile(prompt_file):
        with open(prompt_file, "r", encoding="utf-8") as f:
            prompt_content = f.read()

    # --- Step 2: 작업 디렉터리 생성 ---
    os.makedirs(abs_work_dir, exist_ok=True)

    # --- Step 3: user_prompt.txt 저장 ---
    user_prompt_path = os.path.join(abs_work_dir, "user_prompt.txt")
    with open(user_prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt_content)

    # --- Step 3-B: .uploads/ 파일 처리 ---
    uploads_dir = os.path.join(_PROJECT_ROOT, ".uploads")
    if os.path.isdir(uploads_dir) and os.listdir(uploads_dir):
        files_dir = os.path.join(abs_work_dir, "files")
        os.makedirs(files_dir, exist_ok=True)
        for item in os.listdir(uploads_dir):
            src = os.path.join(uploads_dir, item)
            dst = os.path.join(files_dir, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        # .uploads/ 클리어
        for item in os.listdir(uploads_dir):
            item_path = os.path.join(uploads_dir, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.unlink(item_path)

    # --- Step 4: prompt.txt 클리어 ---
    if os.path.isfile(prompt_file):
        with open(prompt_file, "w", encoding="utf-8") as f:
            pass  # truncate

    # --- Step 5: querys.txt 갱신 ---
    os.makedirs(prompt_dir, exist_ok=True)
    kst_date = now.strftime("%Y-%m-%d %H:%M")
    with open(querys_file, "a", encoding="utf-8") as f:
        f.write(f"{kst_date} [{command}] {title}\n")
        if prompt_content:
            f.write(f"{prompt_content}\n\n")

    # --- Step 6: .context.json 생성 ---
    context_data = {
        "title": title,
        "workId": work_id,
        "workName": work_name,
        "command": command,
        "agent": "init",
        "created_at": now.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
    }
    _atomic_write_json(os.path.join(abs_work_dir, ".context.json"), context_data)

    # --- Step 7: status.json 생성 ---
    session_id = str(uuid.uuid4())[:8]
    status_data = {
        "phase": "INIT",
        "mode": mode,
        "session_id": session_id,
        "linked_sessions": [claude_sid] if claude_sid else [],
        "created_at": now.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "updated_at": now.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "transitions": [
            {
                "from": "NONE",
                "to": "INIT",
                "at": now.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            }
        ],
    }
    _atomic_write_json(os.path.join(abs_work_dir, "status.json"), status_data)

    # --- Step 8: 좀비 정리 ---
    cleanup_script = os.path.join(_SCRIPT_DIR, "cleanup_zombie.py")
    if os.path.isfile(cleanup_script):
        try:
            subprocess.run(
                ["python3", cleanup_script, _PROJECT_ROOT],
                timeout=30, capture_output=True
            )
        except Exception:
            pass
    else:
        # 폴백: shell 스크립트
        cleanup_sh = os.path.join(_SCRIPT_DIR, "cleanup-zombie.sh")
        if os.path.isfile(cleanup_sh):
            try:
                subprocess.run(
                    ["bash", cleanup_sh, _PROJECT_ROOT],
                    timeout=30, capture_output=True
                )
            except Exception:
                pass

    # --- Step 8b: 활성 디렉토리 수 점검 및 보조 아카이빙 ---
    keep_count = KEEP_COUNT
    workflow_root = os.path.join(_PROJECT_ROOT, ".workflow")
    active_count = 0
    if os.path.isdir(workflow_root):
        for entry in os.listdir(workflow_root):
            if entry[0].isdigit() and entry != registry_key:
                entry_path = os.path.join(workflow_root, entry)
                if os.path.isdir(entry_path):
                    active_count += 1

    if active_count > keep_count:
        print(f"[init] Active directories ({active_count}) exceed KEEP_COUNT ({keep_count}), triggering archive...",
              file=sys.stderr)
        archive_script = os.path.join(_SCRIPT_DIR, "..", "sync", "history_archive_sync.py")
        if os.path.isfile(archive_script):
            try:
                subprocess.run(
                    ["python3", archive_script, registry_key],
                    timeout=30, capture_output=True
                )
            except Exception:
                pass
        else:
            archive_sh = os.path.join(_SCRIPT_DIR, "..", "sync", "archive-workflow.sh")
            if os.path.isfile(archive_sh):
                try:
                    subprocess.run(
                        ["bash", archive_sh, registry_key],
                        timeout=30, capture_output=True
                    )
                except Exception:
                    pass

    # --- Step 9: 전역 레지스트리 등록 ---
    update_state_script = os.path.join(_SCRIPT_DIR, "..", "state", "update_state.py")
    if os.path.isfile(update_state_script):
        try:
            subprocess.run(
                ["python3", update_state_script, "register", work_dir, title, command],
                timeout=30, capture_output=True
            )
        except Exception:
            pass
    else:
        update_state_sh = os.path.join(_SCRIPT_DIR, "..", "state", "update-state.sh")
        if os.path.isfile(update_state_sh):
            try:
                subprocess.run(
                    ["bash", update_state_sh, "register", work_dir, title, command],
                    timeout=30, capture_output=True
                )
            except Exception:
                pass

    # --- stdout 출력: init 에이전트가 파싱할 결과 ---
    print(f"workDir={work_dir}")
    print(f"registryKey={registry_key}")
    print(f"workId={work_id}")
    print(f"workName={work_name}")


if __name__ == "__main__":
    main()
