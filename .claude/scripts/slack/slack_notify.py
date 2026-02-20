#!/usr/bin/env -S python3 -u
"""
slack_notify.py - Slack 메시지 전송 스크립트

새 시그니처 (workDir 기반):
    python3 slack_notify.py <workDir> <상태> [보고서경로] [에이전트]
    - workDir이 .workflow/ 또는 절대경로(/)로 시작하면 새 방식으로 감지
    - workDir 형식: .workflow/YYYYMMDD-HHMMSS/<workName>/<command>
    - .context.json에서 title, workId, workName, command 자동 읽기

기존 시그니처 (하위 호환):
    python3 slack_notify.py <작업제목> <작업ID> <작업이름> <명령어> <상태> [보고서경로] [에이전트]

환경변수 (.claude.env에서 로드):
    CLAUDE_CODE_SLACK_BOT_TOKEN - Slack Bot OAuth Token
    CLAUDE_CODE_SLACK_CHANNEL_ID - Slack Channel ID

에이전트별 색상 이모지:
    agent 인자를 전달받으면 해당 값으로 이모지 결정
    agent 인자가 없으면 이모지 없이 기존 포맷 유지
"""

import json
import os
import sys
import urllib.parse

# utils 패키지 import를 위한 경로 설정
_script_dir = os.path.dirname(os.path.abspath(__file__))
_scripts_dir = os.path.normpath(os.path.join(_script_dir, ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from utils.slack_common import (
    build_json_payload,
    get_agent_emoji,
    load_slack_env,
    log_warn,
    send_slack_message,
    SLACK_CHANNEL_ID,
)
from utils.common import (
    extract_registry_key,
    load_json_file,
    resolve_project_root,
    TS_PATTERN,
)


def _detect_wsl():
    """WSL 환경인지 감지."""
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except (IOError, OSError):
        return False


def _get_wsl_distro_name():
    """WSL 배포판 이름 추출 (예: Ubuntu-22.04)."""
    distro = ""
    version = ""
    try:
        with open("/etc/os-release", "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ID="):
                    distro = line.split("=", 1)[1].strip('"')
                elif line.startswith("VERSION_ID="):
                    version = line.split("=", 1)[1].strip('"')
    except (IOError, OSError):
        pass
    if distro:
        distro = distro[0].upper() + distro[1:] if distro else distro
        return f"{distro}-{version}" if version else distro
    return ""


def _build_vscode_uri(abs_path):
    """파일 경로를 vscode:// URI로 변환 (WSL/Mac/Linux 대응)."""
    encoded = urllib.parse.quote(abs_path, safe="/")
    if _detect_wsl():
        distro_name = _get_wsl_distro_name()
        return f"vscode://file//wsl$/{distro_name}{encoded}"
    return f"vscode://file{encoded}"


def _parse_new_signature(args):
    """
    새 시그니처 파싱: <workDir> <상태> [보고서경로] [에이전트]

    Returns:
        dict: title, work_id, work_name, command, status, report_path, agent
    """
    if len(args) < 2:
        log_warn("사용법: slack_notify.py <workDir> <상태> [보고서경로] [에이전트]")
        sys.exit(1)

    work_dir = args[0]
    status = args[1]
    report_path = args[2] if len(args) > 2 else ""
    agent = args[3] if len(args) > 3 else ""

    project_root = resolve_project_root()

    # workDir 절대 경로 계산
    if os.path.isabs(work_dir):
        abs_work_dir = work_dir
    else:
        abs_work_dir = os.path.join(project_root, work_dir)

    # .context.json 읽기
    context_file = os.path.join(abs_work_dir, ".context.json")
    if not os.path.isfile(context_file):
        log_warn(f".context.json을 찾을 수 없습니다: {context_file}")
        sys.exit(0)

    ctx = load_json_file(context_file)
    if ctx is None:
        log_warn(f".context.json 파싱 실패: {context_file}")
        sys.exit(0)

    title = ctx.get("title", "") or "unknown"
    work_id = ctx.get("workId", "") or "none"
    work_name = ctx.get("workName", "") or title
    command = ctx.get("command", "") or "unknown"

    # workDir에서 YYYYMMDD-HHMMSS 식별자 추출
    reg_key = extract_registry_key(abs_work_dir)
    if TS_PATTERN.match(reg_key):
        work_id = reg_key

    return {
        "title": title,
        "work_id": work_id,
        "work_name": work_name,
        "command": command,
        "status": status,
        "report_path": report_path,
        "agent": agent,
    }


def _parse_legacy_signature(args):
    """
    기존 시그니처 파싱: <작업제목> <작업ID> <작업이름> <명령어> <상태> [보고서경로] [에이전트]

    Returns:
        dict: title, work_id, work_name, command, status, report_path, agent
    """
    if len(args) < 5:
        log_warn(
            "사용법: slack_notify.py <작업제목> <작업ID> <작업이름> <명령어> <상태> "
            "[보고서경로] [에이전트]"
        )
        sys.exit(1)

    return {
        "title": args[0],
        "work_id": args[1],
        "work_name": args[2],
        "command": args[3],
        "status": args[4],
        "report_path": args[5] if len(args) > 5 else "",
        "agent": args[6] if len(args) > 6 else "",
    }


def main():
    args = sys.argv[1:]

    # 환경변수 로드 (실패 시 조용히 종료)
    if not load_slack_env():
        sys.exit(0)

    # 이중 시그니처 감지
    if args and (args[0].startswith(".workflow/") or args[0].startswith("/")):
        info = _parse_new_signature(args)
    else:
        info = _parse_legacy_signature(args)

    # 에이전트 이모지 결정
    agent_emoji = ""
    if info["agent"]:
        agent_emoji = get_agent_emoji(info["agent"])

    # 이모지 접두사 생성
    emoji_prefix = f"{agent_emoji} " if agent_emoji else ""

    # 보고서 vscode:// 링크 생성
    report_link = ""
    if info["report_path"]:
        report_path = info["report_path"]
        project_root = resolve_project_root()
        if os.path.isabs(report_path):
            abs_report = report_path
        else:
            abs_report = os.path.join(project_root, report_path)
        vscode_uri = _build_vscode_uri(abs_report)
        report_link = f"\n- 보고서: <{vscode_uri}|보고서 열기>"

    # Slack 메시지 구성
    message = (
        f"{emoji_prefix}*{info['title']}*\n"
        f"- 작업ID: `{info['work_id']}`\n"
        f"- 작업이름: {info['work_name']}\n"
        f"- 명령어: `{info['command']}`\n"
        f"- 상태: {info['status']}"
        f"{report_link}"
    )

    # JSON payload 구성 + Slack 전송
    from utils.slack_common import SLACK_CHANNEL_ID as _channel
    json_payload = build_json_payload(_channel, message)
    send_slack_message(json_payload)

    sys.exit(0)


if __name__ == "__main__":
    main()
