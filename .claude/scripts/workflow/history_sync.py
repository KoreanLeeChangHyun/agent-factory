#!/usr/bin/env -S python3 -u
"""
히스토리 동기화 및 상태 확인 명령어 (history-sync.sh -> history_sync.py 1:1 포팅)

사용법:
  history_sync.py sync [--dry-run] [--all] [--target PATH]
  history_sync.py status
"""

import os
import subprocess
import sys

# _utils 패키지 import
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from _utils.common import (
    C_CYAN,
    C_GREEN,
    C_RED,
    C_RESET,
    resolve_project_root,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = resolve_project_root()
CORE_SCRIPT = os.path.join(SCRIPT_DIR, "history-sync-core.py")


def main():
    if len(sys.argv) < 2:
        print(f"{C_RED}[ERROR]{C_RESET} 사용법: history_sync.py <sync|status> [옵션]")
        print()
        print("  sync [--dry-run] [--all] [--target PATH]")
        print("    .workflow/ 디렉토리를 스캔하여 history.md에 누락 항목 추가")
        print()
        print("  status")
        print("    .workflow/ 디렉토리 수, history.md 행 수, 누락 수 요약")
        sys.exit(1)

    subcmd = sys.argv[1]
    rest = sys.argv[2:]

    # 옵션 파싱
    dry_run = False
    include_all = False
    target_path = ""

    i = 0
    while i < len(rest):
        if rest[i] == "--dry-run":
            dry_run = True
        elif rest[i] == "--all":
            include_all = True
        elif rest[i] == "--target":
            i += 1
            if i >= len(rest):
                print(f"{C_RED}[ERROR]{C_RESET} --target 옵션에 경로가 필요합니다.", file=sys.stderr)
                sys.exit(1)
            target_path = rest[i]
        else:
            print(f"{C_RED}[ERROR]{C_RESET} 알 수 없는 옵션: {rest[i]}", file=sys.stderr)
            sys.exit(1)
        i += 1

    if not target_path:
        target_path = os.path.join(PROJECT_ROOT, ".prompt", "history.md")

    if not os.path.isabs(target_path):
        target_path = os.path.join(PROJECT_ROOT, target_path)

    workflow_dir = os.path.join(PROJECT_ROOT, ".workflow")

    if not os.path.isfile(CORE_SCRIPT):
        print(f"{C_RED}[ERROR]{C_RESET} Python 코어 스크립트를 찾을 수 없습니다: {CORE_SCRIPT}", file=sys.stderr)
        sys.exit(1)

    if subcmd == "sync":
        print(f"{C_CYAN}[history-sync]{C_RESET} sync 시작...")

        cmd = ["python3", CORE_SCRIPT, "sync", "--workflow-dir", workflow_dir, "--target", target_path]
        if dry_run:
            cmd.append("--dry-run")
        if include_all:
            cmd.append("--all")

        result = subprocess.run(cmd, capture_output=True, text=True)
        output = (result.stdout + result.stderr).strip()

        if result.returncode == 0:
            if output:
                print(output)
            print(f"{C_GREEN}[OK]{C_RESET} sync 완료")
        else:
            if output:
                print(output, file=sys.stderr)
            print(f"{C_RED}[FAIL]{C_RESET} sync 실패 (exit code: {result.returncode})", file=sys.stderr)
            sys.exit(1)

    elif subcmd == "status":
        cmd = ["python3", CORE_SCRIPT, "status", "--workflow-dir", workflow_dir, "--target", target_path]
        if include_all:
            cmd.append("--all")

        result = subprocess.run(cmd, capture_output=True, text=True)
        output = (result.stdout + result.stderr).strip()

        if result.returncode == 0:
            if output:
                print(output)
        else:
            if output:
                print(output, file=sys.stderr)
            print(f"{C_RED}[FAIL]{C_RESET} status 조회 실패", file=sys.stderr)
            sys.exit(1)

    else:
        print(f"{C_RED}[ERROR]{C_RESET} 알 수 없는 서브커맨드: {subcmd}")
        print("사용법: history_sync.py <sync|status> [옵션]")
        sys.exit(1)


if __name__ == "__main__":
    main()
