#!/usr/bin/env -S python3 -u
"""
워크플로우 정보 조회 스크립트 (info.sh -> info.py 1:1 포팅)

사용법:
  python3 .claude/scripts/workflow/info.py 20260208-135954
  python3 .claude/scripts/workflow/info.py .workflow/20260208-135954/디렉터리-구조-변경/implement
  python3 .claude/scripts/workflow/info.py .workflow/20260208-135954
"""

import os
import sys

# _utils 패키지 import
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from _utils.common import (
    C_BLUE,
    C_BOLD,
    C_CYAN,
    C_DIM,
    C_GRAY,
    C_GREEN,
    C_PURPLE,
    C_RED,
    C_RESET,
    C_YELLOW,
    PHASE_COLORS,
    load_json_file,
    resolve_abs_work_dir,
    resolve_project_root,
)

PROJECT_ROOT = resolve_project_root()


def phase_color(phase):
    """Phase별 색상 반환."""
    colors = {
        "INIT": C_RED,
        "PLAN": C_BLUE,
        "WORK": C_GREEN,
        "REPORT": C_PURPLE,
        "COMPLETED": C_YELLOW,
    }
    return colors.get(phase, C_GRAY)


def count_files(dir_path):
    """디렉토리 내 파일 수 카운트."""
    count = 0
    if os.path.isdir(dir_path):
        for root, dirs, files in os.walk(dir_path):
            count += len(files)
    return count


def main():
    if len(sys.argv) < 2 or not sys.argv[1]:
        print(f"{C_RED}사용법: python3 .claude/scripts/workflow/info.py <워크플로우ID 또는 workDir 경로>{C_RESET}")
        print(f"{C_DIM}  예: python3 .claude/scripts/workflow/info.py 20260208-135954{C_RESET}")
        print(f"{C_DIM}  예: python3 .claude/scripts/workflow/info.py .workflow/20260208-135954/디렉터리-구조-변경/implement{C_RESET}")
        sys.exit(1)

    input_arg = sys.argv[1]
    abs_work_dir = resolve_abs_work_dir(input_arg, PROJECT_ROOT)

    if not os.path.isdir(abs_work_dir):
        # resolve_abs_work_dir 로 해석된 경로가 없으면 상대 경로로 재시도
        if input_arg.startswith(".workflow/"):
            abs_work_dir = os.path.join(PROJECT_ROOT, input_arg)
        elif input_arg.startswith("/"):
            abs_work_dir = input_arg
        else:
            abs_work_dir = os.path.join(PROJECT_ROOT, ".workflow", input_arg)

    if not os.path.isdir(abs_work_dir):
        print(f"{C_RED}[ERROR] 워크플로우 디렉토리가 존재하지 않습니다: {input_arg}{C_RESET}")
        sys.exit(1)

    # .context.json 읽기
    ctx_data = load_json_file(os.path.join(abs_work_dir, ".context.json"))
    title = ""
    work_id = ""
    command = ""
    if isinstance(ctx_data, dict):
        title = ctx_data.get("title", "")
        work_id = ctx_data.get("workId", "")
        command = ctx_data.get("command", "")

    if not work_id:
        work_id = os.path.basename(abs_work_dir)
    if not title:
        title = "(제목 없음)"
    if not command:
        command = "(알 수 없음)"

    # status.json 읽기
    status_data = load_json_file(os.path.join(abs_work_dir, "status.json"))
    phase = ""
    if isinstance(status_data, dict):
        phase = status_data.get("phase", "")
    if not phase:
        phase = "(알 수 없음)"

    p_color = phase_color(phase)

    # 파일 경로
    plan_path = os.path.join(abs_work_dir, "plan.md")
    work_path = os.path.join(abs_work_dir, "work")
    report_path = os.path.join(abs_work_dir, "report.md")

    plan_exists = os.path.exists(plan_path)
    work_exists = os.path.exists(work_path)
    report_exists = os.path.exists(report_path)
    work_file_count = count_files(work_path) if work_exists else 0

    separator = "\u2500" * 60

    print()
    print(f"  {C_BOLD}{work_id}{C_RESET} {C_DIM}\u00b7{C_RESET} {title}")
    print(f"  {C_DIM}{separator}{C_RESET}")
    print(f"  {C_DIM}명령어{C_RESET}  {C_CYAN}{command}{C_RESET}    {C_DIM}상태{C_RESET}  {p_color}{C_BOLD}{phase}{C_RESET}")
    print(f"  {C_DIM}{separator}{C_RESET}")

    if plan_exists:
        print(f"  {C_GREEN}\u25cf{C_RESET} plan.md   {C_DIM}\u2192{C_RESET}  {plan_path}")
    else:
        print(f"  {C_RED}\u25cb{C_RESET} plan.md   {C_DIM}\u2192{C_RESET}  {C_DIM}(없음){C_RESET}")

    if work_exists:
        print(f"  {C_GREEN}\u25cf{C_RESET} work/     {C_DIM}\u2192{C_RESET}  {work_path}/  {C_DIM}({work_file_count}개 파일){C_RESET}")
    else:
        print(f"  {C_RED}\u25cb{C_RESET} work/     {C_DIM}\u2192{C_RESET}  {C_DIM}(없음){C_RESET}")

    if report_exists:
        print(f"  {C_GREEN}\u25cf{C_RESET} report.md {C_DIM}\u2192{C_RESET}  {report_path}")
    else:
        print(f"  {C_RED}\u25cb{C_RESET} report.md {C_DIM}\u2192{C_RESET}  {C_DIM}(없음){C_RESET}")

    print(flush=True)


if __name__ == "__main__":
    main()
