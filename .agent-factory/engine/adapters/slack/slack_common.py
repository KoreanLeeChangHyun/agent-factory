#!/usr/bin/env -S python3 -u
"""Slack common function library.

Used by importing from slack_notify.py and slack_ask.py.
Python 1:1 port of the existing slack-common.sh.

Main functions:
    load_slack_env: Load SLACK_BOT_TOKEN, SLACK_CHANNEL_ID from .agent-factory/.settings
    get_agent_emoji: Slack emoji mapping per agent
    extract_json_field: Extract nested keys from dictionary
    build_json_payload: Configure JSON payload for Slack API
    send_slack_message: Call Slack API with urllib + verify response
    log_info: Output information log to stderr
    log_warn: Print warning log to stderr
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from typing import Any

# import data package (based on sys.path)
_engine_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from engine.constants import SLACK_API_URL, SLACK_EMOJI_MAP

from engine.common import read_env

_EMOJI_MAP: dict[str, str] = SLACK_EMOJI_MAP


# Module level variable (set after calling load_slack_env)
SLACK_BOT_TOKEN: str = ""
SLACK_CHANNEL_ID: str = ""


def _read_setting(key: str, *legacy_keys: str, env_file: str | None = None) -> str:
    for candidate in (key, *legacy_keys):
        value = read_env(candidate, "", env_file)
        if value:
            return value
    return ""


def log_info(msg: str) -> None:
    """Prints information logs to stderr.

    Args:
        msg: Informational message to print
    """
    print(f"[OK] {msg}", file=sys.stderr)


def log_warn(msg: str) -> None:
    """Prints warning logs to stderr.

    Args:
        msg: warning message to print
    """
    print(f"[WARN] {msg}", file=sys.stderr)


def load_slack_env(env_file: str | None = None) -> bool:
    """
    Load Slack environment variables from .agent-factory/.settings.

    After setting, module variables SLACK_BOT_TOKEN and SLACK_CHANNEL_ID can be used.

    Args:
        env_file: .agent-factory/.settings file path (automatically interpreted if None)

    Returns:
        If True, the load was successful. If False, required environment variables are missing.
    """
    global SLACK_BOT_TOKEN, SLACK_CHANNEL_ID

    SLACK_BOT_TOKEN = _read_setting(
        "SLACK_BOT_TOKEN",
        "AGENT_FACTORY_SLACK_BOT_TOKEN",
        "CLAUDE_CODE_SLACK_BOT_TOKEN",
        env_file=env_file,
    )
    SLACK_CHANNEL_ID = _read_setting(
        "SLACK_CHANNEL_ID",
        "AGENT_FACTORY_SLACK_CHANNEL_ID",
        "CLAUDE_CODE_SLACK_CHANNEL_ID",
        env_file=env_file,
    )

    if not SLACK_BOT_TOKEN or not SLACK_CHANNEL_ID:
        log_warn(
            "SLACK_BOT_TOKEN or SLACK_CHANNEL_ID "
            "Not set. Skip the Slack transfer."
        )
        return False

    return True


def get_agent_emoji(agent_name: str) -> str:
    """Returns the Slack emoji corresponding to the agent name.

    Args:
        agent_name: Agent name (init|planner|worker|reporter)

    Returns:
        Emoji string. If there is no matching agent, an empty string is returned.
    """
    return _EMOJI_MAP.get(agent_name, "")


def extract_json_field(data: Any, *keys: Any, default: Any = "N/A") -> Any:
    """Safely extract nested keys from a dictionary.

    Simplifying the jq/python3 fallback chain of existing shell scripts.
    Since it is pure Python, no separate fallback is required.

    Args:
        data: JSON parsing result dictionary or list
        *keys: Nested key paths (e.g. 'tool_input', 'questions', 0, 'question')
        default: Default value to return when key does not exist

    Returns:
        Extracted value. Returns default if the key is missing or an error occurs.
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
    """Configure JSON payload for Slack API.

    Args:
        channel: Slack channel ID
        text: Message text to send

    Returns:
        JSON serialized payload string
    """
    payload = {
        "channel": channel,
        "text": text,
        "mrkdwn": True,
    }
    return json.dumps(payload, ensure_ascii=False)


def send_slack_message(json_payload: str, token: str | None = None) -> bool:
    """Send a message to the Slack API and verify the response.

    Args:
        json_payload: JSON payload string
        token: Slack Bot Token. If None, use module variable SLACK_BOT_TOKEN.

    Returns:
        If True, transmission is successful. If False, transmission fails.
    """
    bot_token = token or SLACK_BOT_TOKEN
    if not bot_token:
        log_warn("SLACK_BOT_TOKEN is not set.")
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
            log_info("Slack message sent successfully")
            return True
        else:
            log_warn(f"Slack message delivery failed: {json.dumps(response_data, ensure_ascii=False)}")
            return False

    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
        log_warn(f"Slack message delivery failed: {e}")
        return False
