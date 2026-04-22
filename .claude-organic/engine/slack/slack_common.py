#!/usr/bin/env -S python3 -u
"""Slack 공용 함수 라이브러리.

slack_notify.py, slack_ask.py에서 import하여 사용.
기존 slack-common.sh의 Python 1:1 포팅.

주요 함수:
    load_slack_env: .claude-organic/.settings에서 SLACK_BOT_TOKEN, SLACK_CHANNEL_ID 로드
    get_agent_emoji: 에이전트별 Slack 이모지 매핑
    extract_json_field: 딕셔너리에서 중첩 키 추출
    build_json_payload: Slack API용 JSON payload 구성
    send_slack_message: urllib로 Slack API 호출 + 응답 검증
    log_info: stderr로 정보 로그 출력
    log_warn: stderr로 경고 로그 출력
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from typing import Any

# data 패키지 import (sys.path 기반)
_engine_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from constants import SLACK_API_URL, SLACK_EMOJI_MAP

from common import read_env

_EMOJI_MAP: dict[str, str] = SLACK_EMOJI_MAP


# 모듈 수준 변수 (load_slack_env 호출 후 설정됨)
SLACK_BOT_TOKEN: str = ""
SLACK_CHANNEL_ID: str = ""


def log_info(msg: str) -> None:
    """stderr로 정보 로그를 출력한다.

    Args:
        msg: 출력할 정보 메시지
    """
    print(f"[OK] {msg}", file=sys.stderr)


def log_warn(msg: str) -> None:
    """stderr로 경고 로그를 출력한다.

    Args:
        msg: 출력할 경고 메시지
    """
    print(f"[WARN] {msg}", file=sys.stderr)


def load_slack_env(env_file: str | None = None) -> bool:
    """
    .claude-organic/.settings에서 Slack 환경변수 로드.

    설정 후 모듈 변수 SLACK_BOT_TOKEN, SLACK_CHANNEL_ID 사용 가능.

    Args:
        env_file: .claude-organic/.settings 파일 경로 (None이면 자동 해석)

    Returns:
        True이면 로드 성공, False이면 필수 환경변수 누락
    """
    global SLACK_BOT_TOKEN, SLACK_CHANNEL_ID

    SLACK_BOT_TOKEN = read_env("CLAUDE_CODE_SLACK_BOT_TOKEN", "", env_file)
    SLACK_CHANNEL_ID = read_env("CLAUDE_CODE_SLACK_CHANNEL_ID", "", env_file)

    if not SLACK_BOT_TOKEN or not SLACK_CHANNEL_ID:
        log_warn(
            "CLAUDE_CODE_SLACK_BOT_TOKEN 또는 CLAUDE_CODE_SLACK_CHANNEL_ID가 "
            "설정되지 않았습니다. Slack 전송을 건너뜁니다."
        )
        return False

    return True


def get_agent_emoji(agent_name: str) -> str:
    """에이전트 이름에 대응하는 Slack 이모지를 반환한다.

    Args:
        agent_name: 에이전트 이름 (init|planner|worker|reporter)

    Returns:
        이모지 문자열. 매칭되는 에이전트가 없으면 빈 문자열 반환.
    """
    return _EMOJI_MAP.get(agent_name, "")


def extract_json_field(data: Any, *keys: Any, default: Any = "N/A") -> Any:
    """딕셔너리에서 중첩 키를 안전하게 추출한다.

    기존 shell 스크립트의 jq/python3 폴백 체인을 단순화.
    순수 Python이므로 별도 폴백 불필요.

    Args:
        data: JSON 파싱 결과 딕셔너리 또는 리스트
        *keys: 중첩 키 경로 (예: 'tool_input', 'questions', 0, 'question')
        default: 키가 없을 때 반환할 기본값

    Returns:
        추출된 값. 키가 없거나 오류 발생 시 default 반환.
    """
    current = data
    for key in keys:
        try:
            if isinstance(current, dict):
                current = current.get(key, None)
            elif isinstance(current, (list, tuple)):
                current = current[key]
            else:
                return default
            if current is None:
                return default
        except (IndexError, KeyError, TypeError):
            return default
    return current


def build_json_payload(channel: str, text: str) -> str:
    """Slack API용 JSON payload를 구성한다.

    Args:
        channel: Slack 채널 ID
        text: 전송할 메시지 텍스트

    Returns:
        JSON 직렬화된 payload 문자열
    """
    payload = {
        "channel": channel,
        "text": text,
        "mrkdwn": True,
    }
    return json.dumps(payload, ensure_ascii=False)


def send_slack_message(json_payload: str, token: str | None = None) -> bool:
    """Slack API로 메시지를 전송하고 응답을 검증한다.

    Args:
        json_payload: JSON payload 문자열
        token: Slack Bot Token. None이면 모듈 변수 SLACK_BOT_TOKEN 사용.

    Returns:
        True이면 전송 성공, False이면 전송 실패
    """
    bot_token = token or SLACK_BOT_TOKEN
    if not bot_token:
        log_warn("SLACK_BOT_TOKEN이 설정되지 않았습니다.")
        return False

    url = SLACK_API_URL
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json",
    }

    try:
        req = urllib.request.Request(
            url,
            data=json_payload.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            response_data = json.loads(resp.read().decode("utf-8"))

        if response_data.get("ok"):
            log_info("Slack 메시지 전송 성공")
            return True
        else:
            log_warn(f"Slack 메시지 전송 실패: {json.dumps(response_data, ensure_ascii=False)}")
            return False

    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
        log_warn(f"Slack 메시지 전송 실패: {e}")
        return False
