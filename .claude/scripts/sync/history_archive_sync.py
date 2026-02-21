#!/usr/bin/env -S python3 -u
"""
오래된 워크플로우 디렉토리를 .workflow/.history/로 아카이브
(archive-workflow.sh -> history_archive_sync.py 1:1 포팅)

사용법:
  history_archive_sync.py <registryKey>

동작:
  1. .workflow/ 내 [0-9]* 패턴 디렉토리를 역순 정렬하여 수집
  2. 현재 워크플로우(registryKey)를 목록에서 제외
  3. 최신 10개를 유지하고 11번째 이후 항목을 .workflow/.history/로 이동
"""

import os
import re
import shutil
import sys

# utils 패키지 import
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from utils.common import (
    C_CYAN,
    C_GREEN,
    C_RED,
    C_RESET,
    C_YELLOW,
    resolve_project_root,
)
from data.constants import KEEP_COUNT

PROJECT_ROOT = resolve_project_root()
WORKFLOW_DIR = os.path.join(PROJECT_ROOT, ".workflow")
HISTORY_DIR = os.path.join(WORKFLOW_DIR, ".history")


def main():
    if len(sys.argv) < 2:
        print(f"{C_RED}[ERROR]{C_RESET} 사용법: history_archive_sync.py <registryKey>", file=sys.stderr)
        sys.exit(1)

    current_key = sys.argv[1]

    if not os.path.isdir(WORKFLOW_DIR):
        print(f"{C_YELLOW}[WARN]{C_RESET} .workflow/ 디렉토리가 존재하지 않습니다.", file=sys.stderr)
        sys.exit(0)

    # [0-9]* 패턴 디렉토리를 역순 정렬
    dirs = []
    for name in sorted(os.listdir(WORKFLOW_DIR), reverse=True):
        full_path = os.path.join(WORKFLOW_DIR, name)
        if os.path.isdir(full_path) and re.match(r"^[0-9]", name):
            dirs.append(name)

    if not dirs:
        sys.exit(0)

    # 현재 워크플로우 제외
    filtered = [d for d in dirs if d != current_key]

    if len(filtered) <= KEEP_COUNT:
        sys.exit(0)

    # .history/ 디렉토리 생성
    os.makedirs(HISTORY_DIR, exist_ok=True)

    moved = 0
    failed = 0
    for target in filtered[KEEP_COUNT:]:
        src = os.path.join(WORKFLOW_DIR, target)
        dst = os.path.join(HISTORY_DIR, target)
        try:
            shutil.move(src, dst)
            moved += 1
            print(f"{C_GREEN}[OK]{C_RESET} archived: {target}")
        except Exception:
            failed += 1
            print(f"{C_YELLOW}[WARN]{C_RESET} archive failed: {target} (skipping)", file=sys.stderr)

    if moved > 0:
        print(f"{C_CYAN}[archive]{C_RESET} {moved} directories archived to .history/")

    if failed > 0:
        print(f"[WARN] {failed} directories failed to archive", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
