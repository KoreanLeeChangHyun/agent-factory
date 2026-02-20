#!/usr/bin/env -S python3 -u
"""
slack_ask.py - AskUserQuestion 호출 시 Slack 알림 전송 스크립트

PreToolUse Hook에서 호출됨 (stdin으로 JSON 입력 수신).

환경변수 (.claude.env에서 로드):
    CLAUDE_CODE_SLACK_BOT_TOKEN - Slack Bot OAuth Token
    CLAUDE_CODE_SLACK_CHANNEL_ID - Slack Channel ID

워크플로우 식별 방식 (활성 워크플로우 레지스트리 기반):
    1. 전역 .workflow/registry.json 딕셔너리에서 활성 워크플로우 목록 조회
    2. 활성 워크플로우 1개 -> 해당 워크플로우 선택
    3. 복수 -> phase="PLAN" 인 워크플로우 필터링
    4. PLAN 복수 -> 각 워크플로우의 status.json에서 가장 최근 updated_at인 워크플로우 선택
    5. 식별된 워크플로우의 로컬 <workDir>/.context.json 읽어 메시지 구성
    6. 식별 실패 시 기존 폴백 포맷 사용

에이전트별 색상 이모지:
    로컬 .context.json의 agent 필드를 읽어 해당 에이전트의 이모지를 메시지 앞에 표시
"""

import json
import os
import subprocess
import sys

# utils 패키지 import를 위한 경로 설정
_script_dir = os.path.dirname(os.path.abspath(__file__))
_scripts_dir = os.path.normpath(os.path.join(_script_dir, ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from utils.slack_common import (
    build_json_payload,
    extract_json_field,
    get_agent_emoji,
    load_slack_env,
    log_warn,
    send_slack_message,
)
from utils.common import (
    load_json_file,
    resolve_project_root,
)


def _extract_question(data):
    """stdin JSON에서 첫 번째 질문 추출."""
    return extract_json_field(
        data, "tool_input", "questions", 0, "question", default="N/A"
    )


def _extract_options(data):
    """stdin JSON에서 선택지(options) 추출하여 "label - description | ..." 형식 반환."""
    options = extract_json_field(
        data, "tool_input", "questions", 0, "options", default=[]
    )
    if not isinstance(options, list) or not options:
        return ""

    parts = []
    for opt in options:
        if not isinstance(opt, dict):
            continue
        label = opt.get("label", "")
        desc = opt.get("description", "")
        if label:
            parts.append(f"{label} - {desc}" if desc else label)

    return " | ".join(parts) if parts else ""


def _resolve_workflow_context(project_root):
    """
    활성 워크플로우 레지스트리에서 워크플로우 식별 및 컨텍스트 로드.

    외부 resolve-workflow.py 스크립트를 호출하여 워크플로우를 식별.

    Returns:
        dict or None: {title, work_id, work_name, command, agent, phase}
    """
    registry_file = os.path.join(project_root, ".workflow", "registry.json")
    if not os.path.isfile(registry_file):
        return None

    resolve_script = os.path.join(
        project_root, ".claude", "scripts", "utils", "resolve-workflow.py"
    )

    try:
        result = subprocess.run(
            ["python3", resolve_script, registry_file, project_root],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        lines = result.stdout.strip().split("\n")
        if len(lines) < 6:
            return None

        return {
            "title": lines[0],
            "work_id": lines[1],
            "work_name": lines[2],
            "command": lines[3],
            "agent": lines[4],
            "phase": lines[5],
        }

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def main():
    # .claude.env에서 환경변수 로드
    if not load_slack_env():
        sys.exit(0)

    # stdin에서 JSON 읽기
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, IOError):
        input_data = {}

    # tool_input에서 첫 번째 질문 추출
    question = _extract_question(input_data)

    # tool_input에서 선택지(options) 추출
    options_raw = _extract_options(input_data)
    options_line = f"\n- 선택지: {options_raw}" if options_raw else ""

    # 활성 워크플로우 레지스트리에서 워크플로우 식별
    project_root = resolve_project_root()
    ctx = _resolve_workflow_context(project_root)

    if ctx:
        # 에이전트 이모지 결정
        agent_emoji = get_agent_emoji(ctx["agent"])
        emoji_prefix = f"{agent_emoji} " if agent_emoji else ""

        # phase 정보 문자열 생성
        phase_line = f"\n- 현재 단계: {ctx['phase']}" if ctx.get("phase") else ""

        # 통일 포맷 (slack_notify.py와 동일, 에이전트 이모지 포함, 보고서 링크 제외)
        message = (
            f"{emoji_prefix}*{ctx['title']}*\n"
            f"- 작업ID: `{ctx['work_id']}`\n"
            f"- 작업이름: {ctx['work_name']}\n"
            f"- 명령어: `{ctx['command']}`"
            f"{phase_line}\n"
            f"- 상태: 사용자 입력 대기 중\n"
            f"- 질문: {question}"
            f"{options_line}"
        )
    else:
        # 폴백 포맷 (registry.json 없거나 워크플로우 식별 실패)
        message = (
            f":bell: *사용자 입력 대기 중*\n"
            f"- 질문: {question}"
            f"{options_line}"
        )

    # JSON payload 구성 + Slack 전송
    from utils.slack_common import SLACK_CHANNEL_ID as _channel
    json_payload = build_json_payload(_channel, message)
    send_slack_message(json_payload)

    sys.exit(0)


if __name__ == "__main__":
    main()
