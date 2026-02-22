#!/usr/bin/env -S python3 -u
"""
slack_common.py - Slack 공용 함수 라이브러리

slack_notify.py, slack_ask.py에서 import하여 사용.
기존 slack-common.sh의 Python 1:1 포팅.

제공 함수:
    load_slack_env()            - .claude.env에서 SLACK_BOT_TOKEN, SLACK_CHANNEL_ID 로드
    get_agent_emoji(agent_name) - 에이전트별 Slack 이모지 매핑
    extract_json_field(data, *keys, default) - 딕셔너리에서 중첩 키 추출
    build_json_payload(channel, text) - Slack API용 JSON payload 구성
    send_slack_message(payload, token) - curl로 Slack API 호출 + 응답 검증
    log_info(msg)               - stderr로 정보 로그 출력
    log_warn(msg)               - stderr로 경고 로그 출력
"""

import json
import os
import sys
import urllib.request
import urllib.error

# data 패키지 import (sys.path 기반)
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from data.constants import SLACK_API_URL
from data.slack_emoji_map import SLACK_EMOJI_MAP

from . import env_utils

_EMOJI_MAP = SLACK_EMOJI_MAP


# 모듈 수준 변수 (load_slack_env 호출 후 설정됨)
SLACK_BOT_TOKEN = ""
SLACK_CHANNEL_ID = ""


def log_info(msg):
    """stderr로 정보 로그 출력."""
    print(f"[OK] {msg}", file=sys.stderr)


def log_warn(msg):
    """stderr로 경고 로그 출력."""
    print(f"[WARN] {msg}", file=sys.stderr)


def load_slack_env(env_file=None):
    """
    .claude.env에서 Slack 환경변수 로드.

    설정 후 모듈 변수 SLACK_BOT_TOKEN, SLACK_CHANNEL_ID 사용 가능.

    Args:
        env_file: .claude.env 파일 경로 (None이면 자동 해석)

    Returns:
        bool: True=성공, False=환경변수 누락
    """
    global SLACK_BOT_TOKEN, SLACK_CHANNEL_ID

    SLACK_BOT_TOKEN = env_utils.read_env("CLAUDE_CODE_SLACK_BOT_TOKEN", "", env_file)
    SLACK_CHANNEL_ID = env_utils.read_env("CLAUDE_CODE_SLACK_CHANNEL_ID", "", env_file)

    if not SLACK_BOT_TOKEN or not SLACK_CHANNEL_ID:
        log_warn(
            "CLAUDE_CODE_SLACK_BOT_TOKEN 또는 CLAUDE_CODE_SLACK_CHANNEL_ID가 "
            "설정되지 않았습니다. Slack 전송을 건너뜁니다."
        )
        return False

    return True


def get_agent_emoji(agent_name):
    """
    에이전트별 Slack 이모지 매핑.

    Args:
        agent_name: 에이전트 이름 (init|planner|worker|reporter)

    Returns:
        str: 이모지 문자열 (매칭 없으면 빈 문자열)
    """
    return _EMOJI_MAP.get(agent_name, "")


def extract_json_field(data, *keys, default="N/A"):
    """
    딕셔너리에서 중첩 키를 안전하게 추출.

    기존 shell 스크립트의 jq/python3 폴백 체인을 단순화.
    순수 Python이므로 별도 폴백 불필요.

    Args:
        data: JSON 파싱 결과 딕셔너리
        *keys: 중첩 키 경로 (예: 'tool_input', 'questions', 0, 'question')
        default: 키가 없을 때 반환할 기본값

    Returns:
        추출된 값 또는 default
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


def build_json_payload(channel, text):
    """
    Slack API용 JSON payload 구성.

    Args:
        channel: Slack 채널 ID
        text: 메시지 텍스트

    Returns:
        str: JSON 문자열
    """
    payload = {
        "channel": channel,
        "text": text,
        "mrkdwn": True,
    }
    return json.dumps(payload, ensure_ascii=False)


def send_slack_message(json_payload, token=None):
    """
    Slack API로 메시지 전송 + 응답 검증.

    Args:
        json_payload: JSON payload 문자열
        token: Slack Bot Token (None이면 모듈 변수 SLACK_BOT_TOKEN 사용)

    Returns:
        bool: True=성공, False=실패
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
