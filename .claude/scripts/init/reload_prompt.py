#!/usr/bin/env -S python3 -u
"""
reload_prompt.py - 수정 피드백을 워크플로우에 반영하는 스크립트

prompt.txt의 피드백을 user_prompt.txt에 append하고,
.uploads/ 파일 복사, prompt.txt 클리어, querys.txt 갱신을 수행한다.

사용법:
  python3 reload_prompt.py <workDir>

인자:
  workDir - 작업 디렉터리 상대 경로

수행 작업 (순서대로):
  1. .prompt/prompt.txt 읽기 (비어있으면 경고 후 종료)
  2. <workDir>/user_prompt.txt에 구분선 + 피드백 append
  3. .uploads/ -> <workDir>/files/ 복사 후 .uploads/ 클리어
  4. .prompt/prompt.txt 클리어
  5. .prompt/querys.txt에 수정 기록 append

출력 (stdout):
  피드백 내용 전문
"""

import os
import shutil
import sys
from datetime import datetime, timezone, timedelta

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
_KST = timezone(timedelta(hours=9))


def main():
    # --- 인자 확인 ---
    if len(sys.argv) < 2:
        print(f"[ERROR] 사용법: {sys.argv[0]} <workDir>", file=sys.stderr)
        sys.exit(1)

    work_dir = sys.argv[1]
    abs_work_dir = os.path.join(_PROJECT_ROOT, work_dir)

    if not os.path.isdir(abs_work_dir):
        print(f"[ERROR] workDir not found: {work_dir}", file=sys.stderr)
        sys.exit(1)

    prompt_dir = os.path.join(_PROJECT_ROOT, ".prompt")
    prompt_file = os.path.join(prompt_dir, "prompt.txt")
    querys_file = os.path.join(prompt_dir, "querys.txt")

    # --- Step 1: prompt.txt 읽기 ---
    feedback = ""
    if os.path.isfile(prompt_file):
        with open(prompt_file, "r", encoding="utf-8") as f:
            feedback = f.read()

    if not feedback:
        print("[WARN] prompt.txt is empty")
        sys.exit(0)

    # --- Step 2: user_prompt.txt에 피드백 append ---
    kst_date = datetime.now(_KST).strftime("%Y-%m-%d %H:%M")
    user_prompt_file = os.path.join(abs_work_dir, "user_prompt.txt")

    with open(user_prompt_file, "a", encoding="utf-8") as f:
        f.write(f"\n\n--- (수정 피드백, {kst_date}) ---\n\n")
        f.write(feedback)

    # --- Step 3: .uploads/ 파일 처리 ---
    uploads_dir = os.path.join(_PROJECT_ROOT, ".uploads")
    if os.path.isdir(uploads_dir) and os.listdir(uploads_dir):
        files_dir = os.path.join(abs_work_dir, "files")
        os.makedirs(files_dir, exist_ok=True)
        for item in os.listdir(uploads_dir):
            src = os.path.join(uploads_dir, item)
            dst = os.path.join(files_dir, item)
            try:
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
            except Exception:
                pass
        # .uploads/ 클리어
        for item in os.listdir(uploads_dir):
            item_path = os.path.join(uploads_dir, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.unlink(item_path)
            except Exception:
                pass

    # --- Step 4: prompt.txt 클리어 ---
    try:
        with open(prompt_file, "w", encoding="utf-8") as f:
            pass  # truncate
    except Exception:
        pass

    # --- Step 5: querys.txt 갱신 ---
    feedback_summary = feedback[:30]
    with open(querys_file, "a", encoding="utf-8") as f:
        f.write(f"{kst_date} [수정] {feedback_summary}\n")

    # --- stdout: 피드백 내용 전문 출력 ---
    print(feedback)


if __name__ == "__main__":
    main()
