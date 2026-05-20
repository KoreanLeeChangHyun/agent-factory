#!/usr/bin/env -S python3 -u
"""AskUserQuestion 호출 시 Slack 알림 전송 스크립트.

PreToolUse Hook에서 호출됨 (stdin으로 JSON 입력 수신).

주요 함수:
    main: Slack 알림 전송 진입점

환경변수 (.agent-factory/.settings에서 로드):
    CLAUDE_CODE_SLACK_BOT_TOKEN - Slack Bot OAuth Token
    CLAUDE_CODE_SLACK_CHANNEL_ID - Slack Channel ID

워크플로우 식별 방식 (디렉터리 스캔 기반):
    1. .workflow/ 디렉터리 스캔으로 활성 워크플로우 목록 조회
    2. 활성 워크플로우 1개 -> 해당 워크플로우 선택
    3. 복수 -> phase="PLAN" 인 워크플로우 필터링
    4. PLAN 복수 -> 각 워크플로우의 status.json에서 가장 최근 updated_at인 워크플로우 선택
    5. 식별된 워크플로우의 로컬 <workDir>/.context.json 읽어 메시지 구성
    6. 식별 실패 시 기존 폴백 포맷 사용

에이전트별 색상 이모지:
    로컬 .context.json의 agent 필드를 읽어 해당 에이전트의 이모지를 메시지 앞에 표시
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

_script_dir = os.path.dirname(os.path.abspath(__file__))
_agent_factory_dir = os.path.normpath(os.path.join(_script_dir, "..", "..", ".."))
if _agent_factory_dir not in sys.path:
    sys.path.insert(0, _agent_factory_dir)

from engine.adapters.slack.slack_common import (
    build_json_payload,
    extract_json_field,
    get_agent_emoji,
    load_slack_env,
    log_warn,
    send_slack_message,
)
from engine.common import (
    resolve_active_workflow,
    resolve_project_root,
)


def _extract_question(data: dict[str, Any]) -> str:
    """stdin JSON에서 첫 번째 질문 텍스트를 추출한다.

    Args:
        data: stdin에서 파싱된 JSON 딕셔너리

    Returns:
        첫 번째 질문 문자열. 추출 실패 시 'N/A' 반환.
    """
    return extract_json_field(
        data, "tool_input", "questions", 0, "question", default="N/A"
    )


def _extract_options(data: dict[str, Any]) -> str:
    """Extract options from stdin JSON"label - description | ..." 형식으로 반환한다.

    Args:
        data: stdin에서 파싱된 JSON 딕셔너리

    Returns:
        'label - description | ...' 형식의 선택지 문자열. 선택지가 없으면 빈 문자열 반환.
    """
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


def main() -> None:
    """AskUserQuestion 훅 Slack 알림 전송의 진입점.

    stdin에서 JSON을 읽어 사용자 질문 내용을 파싱하고,
    활성 워크플로우 정보를 식별하여 Slack으로 알림을 전송한다.
    환경변수 로드 실패 시 조용히 종료한다.
    """
    # Load environment variables from .agent-factory/.settings
    if not load_slack_env():
        sys.exit(0)

    # Reading JSON from stdin
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, IOError):
        input_data = {}

    # Extract first question from tool_input
    question = _extract_question(input_data)

    # Extract options from tool_input
    options_raw = _extract_options(input_data)
    options_line = f"\n - Options: {options_raw}" if options_raw else ""

    # Identify active workflows (direct import)
    project_root = resolve_project_root()
    ctx = resolve_active_workflow(project_root)

    if ctx:
        # Agent Emoji Decision
        agent_emoji = get_agent_emoji(ctx["agent"])
        emoji_prefix = f"{agent_emoji} " if agent_emoji else ""

        # Create step information string
        phase_line = f"\n - Current step: {ctx['step']}" if ctx.get("step") else ""

        # Uniform format (same as slack_notify.py, includes agent emoji, but excludes report link)
        message = (
            f"{emoji_prefix}*{ctx['title']}*\n"
            f"- Work ID: `{ctx['workId']}` \n"
            f"- Work name: {ctx['workName']} \n"
            f"- Command: `{ctx['command']}`"
            f"{phase_line}\n"
            f"- Status: Waiting for user input \n"
            f"- Question: {question}"
            f"{options_line}"
        )
    else:
        # Fallback format (workflow identification failure)
        message = (
            f":bell: *Waiting for user input* \n"
            f"- Question: {question}"
            f"{options_line}"
        )

    # Configure JSON payload + send to Slack
    from slack.slack_common import SLACK_CHANNEL_ID as _channel
    json_payload = build_json_payload(_channel, message)
    send_slack_message(json_payload)

    sys.exit(0)


if __name__ == "__main__":
    main()
