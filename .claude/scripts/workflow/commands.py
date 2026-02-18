#!/usr/bin/env python3
"""
사용 가능한 cc:* 명령어 목록을 동적 스캔하여 출력
(commands.sh -> commands.py 1:1 포팅)

사용법:
  wf-commands
  python3 commands.py
"""

import os
import re
import sys

# _utils 패키지 import
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from _utils.common import (
    C_BOLD,
    C_CYAN,
    C_DIM,
    C_GREEN,
    C_RESET,
    C_YELLOW,
    resolve_project_root,
)

PROJECT_ROOT = resolve_project_root()
COMMANDS_DIR = os.path.join(PROJECT_ROOT, ".claude", "commands", "cc")


def extract_description(md_file):
    """frontmatter에서 description 추출."""
    try:
        with open(md_file, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
            if first_line != "---":
                return "(설명 없음)"

            for line in f:
                if line.strip() == "---":
                    break
                match = re.match(r"^description:\s*(.+)", line)
                if match:
                    return match.group(1).strip()
    except (IOError, OSError):
        pass
    return "(설명 없음)"


def main():
    if not os.path.isdir(COMMANDS_DIR):
        print(f"{C_YELLOW}[WARN] 명령어 디렉토리가 존재하지 않습니다: {COMMANDS_DIR}{C_RESET}")
        sys.exit(1)

    # .md 파일 스캔
    md_files = sorted(
        f for f in os.listdir(COMMANDS_DIR)
        if f.endswith(".md") and os.path.isfile(os.path.join(COMMANDS_DIR, f))
    )

    if not md_files:
        print(f"{C_YELLOW}[WARN] 명령어 파일이 없습니다: {COMMANDS_DIR}/*.md{C_RESET}")
        sys.exit(0)

    entries = []
    max_name_len = 0

    for md_file in md_files:
        filename = md_file[:-3]  # .md 제거
        cmd_name = f"cc:{filename}"
        description = extract_description(os.path.join(COMMANDS_DIR, md_file))
        entries.append((cmd_name, description))
        max_name_len = max(max_name_len, len(cmd_name))

    col_width = max(max_name_len + 4, 20)
    separator_width = col_width + 50
    separator = "\u2500" * separator_width

    print()
    print(f"  {C_BOLD}사용 가능한 명령어{C_RESET}  {C_DIM}({len(entries)}개){C_RESET}")
    print(f"  {C_DIM}{separator}{C_RESET}")
    print(f"  {C_BOLD}{C_CYAN}{'명령어':<{col_width}}{C_RESET} {C_BOLD}설명{C_RESET}")
    print(f"  {C_DIM}{separator}{C_RESET}")

    for cmd_name, description in entries:
        print(f"  {C_GREEN}{cmd_name:<{col_width}}{C_RESET} {description}")

    print(f"  {C_DIM}{separator}{C_RESET}")
    print(f"  {C_DIM}실행: /cc:<명령어> <요청내용>{C_RESET}")
    print()


if __name__ == "__main__":
    main()
