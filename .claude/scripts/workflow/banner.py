#!/usr/bin/env -S python3 -u
"""
워크플로우 단계 배너 출력 스크립트 (banner.sh -> banner.py 1:1 포팅)

시그니처:
  단축 형식: banner.py <YYYYMMDD-HHMMSS> <phase> [status] [path]
  신규 형식: banner.py <workDir> <phase> [status] [path]
  레거시:    banner.py <phase> <workId> <title> [status] [path] [workDir]

종료 코드: 0
"""

import os
import re
import subprocess
import sys
import unicodedata

# utils 패키지 import
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from utils.common import (
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
    TS_PATTERN,
    load_json_file,
    resolve_project_root,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = resolve_project_root()


# =============================================================================
# 유틸리티 함수
# =============================================================================

def get_color(phase):
    """단계별 색상 반환."""
    colors = {
        "INIT": C_RED,
        "PLAN": C_BLUE,
        "WORK": C_GREEN,
        "REPORT": C_PURPLE,
        "DONE": "\033[0;33m",
    }
    return colors.get(phase, "\033[0;37m")


def get_progress(phase):
    """프로그레스 바 반환."""
    bars = {
        "INIT": f"{C_RED}{C_BOLD}\u25a0{C_RESET}{C_GRAY}\u25a1\u25a1\u25a1\u25a1{C_RESET}",
        "PLAN": f"{C_RED}\u25a0{C_BLUE}{C_BOLD}\u25a0{C_RESET}{C_GRAY}\u25a1\u25a1\u25a1{C_RESET}",
        "WORK": f"{C_RED}\u25a0{C_BLUE}\u25a0{C_GREEN}{C_BOLD}\u25a0{C_RESET}{C_GRAY}\u25a1\u25a1{C_RESET}",
        "REPORT": f"{C_RED}\u25a0{C_BLUE}\u25a0{C_GREEN}\u25a0{C_PURPLE}{C_BOLD}\u25a0{C_RESET}{C_GRAY}\u25a1{C_RESET}",
        "DONE": f"{C_RED}\u25a0{C_BLUE}\u25a0{C_GREEN}\u25a0{C_PURPLE}\u25a0{C_YELLOW}{C_BOLD}\u25a0{C_RESET}",
    }
    return bars.get(phase, f"{C_GRAY}\u25a1\u25a1\u25a1\u25a1\u25a1{C_RESET}")


def display_width(s):
    """터미널 표시 너비 계산 (한글 등 wide 문자는 2칸)."""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def resolve_registry_key(key):
    """YYYYMMDD-HHMMSS 키를 registry.json에서 workDir로 해석."""
    reg_file = os.path.join(PROJECT_ROOT, ".workflow", "registry.json")
    data = load_json_file(reg_file)
    if isinstance(data, dict) and key in data and "workDir" in data[key]:
        return data[key]["workDir"]
    return None


def resolve_arg1(arg1):
    """첫 번째 인자를 workDir로 해석."""
    if not TS_PATTERN.match(arg1):
        return arg1

    # YYYYMMDD-HHMMSS 단축 형식
    resolved = resolve_registry_key(arg1)
    if resolved:
        return resolved

    # 폴백 1: 중첩 디렉토리 탐색
    base_dir = os.path.join(PROJECT_ROOT, ".workflow", arg1)
    if os.path.isdir(base_dir):
        for wname in sorted(os.listdir(base_dir)):
            wname_dir = os.path.join(base_dir, wname)
            if not os.path.isdir(wname_dir):
                continue
            for cmd in sorted(os.listdir(wname_dir)):
                cmd_dir = os.path.join(wname_dir, cmd)
                if not os.path.isdir(cmd_dir):
                    continue
                if os.path.isfile(os.path.join(cmd_dir, ".context.json")):
                    return f".workflow/{arg1}/{wname}/{cmd}"

    # 폴백 2: 레거시 플랫 구조
    return f".workflow/{arg1}"


def read_context(abs_work_dir):
    """context.json에서 workId, title, command 읽기."""
    ctx_file = os.path.join(abs_work_dir, ".context.json")
    data = load_json_file(ctx_file)
    if isinstance(data, dict):
        return (
            data.get("workId", ""),
            data.get("title", ""),
            data.get("command", ""),
        )
    return "", "", ""


# =============================================================================
# 메인
# =============================================================================

def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print("사용법: banner.py <workDir|registryKey> <phase> [status] [path]")
        sys.exit(1)

    # arg1 해석
    resolved_arg1 = resolve_arg1(args[0])

    # 시그니처 감지
    if resolved_arg1.startswith(".workflow/") or resolved_arg1.startswith("/"):
        # 신규 방식
        work_dir = resolved_arg1
        phase = args[1]
        status = args[2] if len(args) > 2 else ""
        doc_path = args[3] if len(args) > 3 else ""

        if work_dir.startswith("/"):
            abs_work_dir = work_dir
        else:
            abs_work_dir = os.path.join(PROJECT_ROOT, work_dir)

        work_id, title, command = read_context(abs_work_dir)
        if not work_id:
            work_id = "none"
        if not title:
            title = "unknown"
    else:
        # 레거시 방식
        if len(args) < 3:
            print("사용법: banner.py <phase> <workId> <title> [status] [path]")
            sys.exit(1)

        phase = args[0]
        work_id = args[1]
        title = args[2]
        status = args[3] if len(args) > 3 else ""
        doc_path = args[4] if len(args) > 4 else ""
        work_dir = args[5] if len(args) > 5 else ""
        command = ""

        # 레거시 방식에서 WORK_DIR이 비어있을 때 registry에서 역해석
        if not work_dir and work_id and re.match(r"^\d{6}$", work_id):
            reg_file = os.path.join(PROJECT_ROOT, ".workflow", "registry.json")
            data = load_json_file(reg_file)
            if isinstance(data, dict):
                for key, val in data.items():
                    if key.endswith("-" + work_id) and isinstance(val, dict) and "workDir" in val:
                        work_dir = val["workDir"]
                        break

        if work_dir:
            if work_dir.startswith("/"):
                abs_work_dir = work_dir
            else:
                abs_work_dir = os.path.join(PROJECT_ROOT, work_dir)

            ctx_file = os.path.join(abs_work_dir, ".context.json")
            ctx_data = load_json_file(ctx_file)
            if isinstance(ctx_data, dict):
                command = ctx_data.get("command", "")
        else:
            abs_work_dir = ""

    # --- WORK-PHASE 서브배너 ---
    if phase == "WORK-PHASE":
        if resolved_arg1.startswith(".workflow/") or resolved_arg1.startswith("/") or TS_PATTERN.match(args[0]):
            wp_phase_num = status  # 3번째 인자
            wp_task_ids = doc_path  # 4번째 인자
            wp_mode = args[4] if len(args) > 4 else ""  # 5번째 인자
        else:
            # 레거시 방식
            wp_phase_num = args[3] if len(args) > 3 else ""
            wp_task_ids = args[4] if len(args) > 4 else ""
            wp_mode = args[5] if len(args) > 5 else ""
        # mode 검증: parallel|sequential 만 허용, 그 외(full 등)는 sequential 폴백
        if wp_mode not in ("parallel", "sequential"):
            wp_mode = "sequential"
        print(f"    {C_GREEN}\u25ba{C_RESET} {C_BOLD}Phase {wp_phase_num}{C_RESET}  {C_DIM}{wp_task_ids}{C_RESET}  {C_GRAY}{wp_mode}{C_RESET}", flush=True)
        sys.exit(0)

    color = get_color(phase)
    progress = get_progress(phase)

    # 배너 폭
    MIN_WIDTH = 75
    MAX_WIDTH = 100

    title_dwidth = display_width(title)

    if work_id == "none":
        content_len = len(phase) + title_dwidth + 10
    else:
        content_len = len(phase) + len(work_id) + title_dwidth + 13

    width = max(MIN_WIDTH, min(MAX_WIDTH, content_len))
    line = "\u2500" * width

    if phase == "DONE" and status:
        # 최종 완료 배너
        print()
        cmd_label = ""
        if command:
            cmd_label = f" ({C_CYAN}{command}{C_RESET})"
        print(f"  {C_YELLOW}{C_BOLD}[OK]{C_RESET}  {work_id} \u00b7 {title} {cmd_label} {C_YELLOW}\uc6cc\ud06c\ud50c\ub85c\uc6b0 \uc644\ub8cc{C_RESET}")
        print(flush=True)

        # .done-marker 생성
        done_marker = os.path.join(PROJECT_ROOT, ".workflow", ".done-marker")
        try:
            os.makedirs(os.path.dirname(done_marker), exist_ok=True)
            open(done_marker, "a").close()
        except OSError:
            pass

        # Slack 완료 알림 (비동기, 비차단)
        if work_dir:
            slack_py = os.path.join(SCRIPT_DIR, "..", "slack", "slack_notify.py")
            slack_sh = os.path.join(SCRIPT_DIR, "..", "slack", "slack.sh")
            report_path = ""
            if abs_work_dir and os.path.isfile(os.path.join(abs_work_dir, "report.md")):
                report_path = f"{work_dir}/report.md"
            try:
                if os.path.isfile(slack_py):
                    subprocess.Popen(
                        [sys.executable, slack_py, work_dir, "\uc644\ub8cc", report_path, ""],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                elif os.path.isfile(slack_sh):
                    subprocess.Popen(
                        ["bash", slack_sh, work_dir, "\uc644\ub8cc", report_path, ""],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            except Exception:
                pass

    elif not status:
        # 시작 배너
        if phase == "INIT":
            done_marker = os.path.join(PROJECT_ROOT, ".workflow", ".done-marker")
            try:
                os.unlink(done_marker)
            except OSError:
                pass

        print()
        print(f"{color}\u250c{line}\u2510{C_RESET}")
        if work_id == "none":
            print(f"  {progress}  {color}{C_BOLD}{phase}{C_RESET}  {title}")
        else:
            print(f"  {progress}  {color}{C_BOLD}{phase}{C_RESET}  {work_id} \u00b7 {title}")
        print(f"{color}\u2514{line}\u2518{C_RESET}", flush=True)

    else:
        # 완료 배너
        if not doc_path and work_dir:
            default_paths = {
                "PLAN": f"{work_dir}/plan.md",
                "WORK": f"{work_dir}/work/",
                "REPORT": f"{work_dir}/report.md",
            }
            doc_path = default_paths.get(phase, "")

        if doc_path:
            print(f"{color}  \u2713 {C_BOLD}{phase}{C_RESET}  {C_DIM}{work_id} \u00b7 {title}{C_RESET}")
            print(f"{color}  \u2713 {C_DIM}{doc_path}{C_RESET}")
        else:
            print(f"{color}  \u2713 {C_BOLD}{phase}{C_RESET}  {C_DIM}{work_id} \u00b7 {title}{C_RESET}")

        print(f"{color}  \u2713 {C_BOLD}{phase} DONE{C_RESET}", flush=True)


if __name__ == "__main__":
    main()
