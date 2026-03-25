#!/usr/bin/env -S python3 -u
"""AskUserQuestion 호출 시 Slack 알림 전송 스크립트.

PreToolUse Hook에서 호출됨 (stdin으로 JSON 입력 수신).

주요 함수:
    main: Slack 알림 전송 진입점

환경변수 (.claude.workflow/.env에서 로드):
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

# utils 패키지 import를 위한 경로 설정
_script_dir = os.path.dirname(os.path.abspath(__file__))
_scripts_dir = os.path.normpath(os.path.join(_script_dir, ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from slack.slack_common import (
    build_json_payload,
    extract_json_field,
    get_agent_emoji,
    load_slack_env,
    log_warn,
    send_slack_message,
)
from common import (
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
    """stdin JSON에서 선택지(options)를 추출하여 "label - description | ..." 형식으로 반환한다.

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
    # .claude.workflow/.env에서 환경변수 로드
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

    # 활성 워크플로우 식별 (직접 import)
    project_root = resolve_project_root()
    ctx = resolve_active_workflow(project_root)

    if ctx:
        # 에이전트 이모지 결정
        agent_emoji = get_agent_emoji(ctx["agent"])
        emoji_prefix = f"{agent_emoji} " if agent_emoji else ""

        # step 정보 문자열 생성
        phase_line = f"\n- 현재 단계: {ctx['step']}" if ctx.get("step") else ""

        # 통일 포맷 (slack_notify.py와 동일, 에이전트 이모지 포함, 보고서 링크 제외)
        message = (
            f"{emoji_prefix}*{ctx['title']}*\n"
            f"- 작업ID: `{ctx['workId']}`\n"
            f"- 작업이름: {ctx['workName']}\n"
            f"- 명령어: `{ctx['command']}`"
            f"{phase_line}\n"
            f"- 상태: 사용자 입력 대기 중\n"
            f"- 질문: {question}"
            f"{options_line}"
        )
    else:
        # 폴백 포맷 (워크플로우 식별 실패)
        message = (
            f":bell: *사용자 입력 대기 중*\n"
            f"- 질문: {question}"
            f"{options_line}"
        )

    # JSON payload 구성 + Slack 전송
    from slack.slack_common import SLACK_CHANNEL_ID as _channel
    json_payload = build_json_payload(_channel, message)
    send_slack_message(json_payload)

    sys.exit(0)


if __name__ == "__main__":
    main()
