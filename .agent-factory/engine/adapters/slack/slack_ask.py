#!/usr/bin/env -S python3 -u
"""Script to send Slack notification when AskUserQuestion is called.

Called from PreToolUse Hook (receives JSON input to stdin).

Main functions:
    main: Slack notification sending entry point

Environment variables (loaded from .agent-factory/.settings):
    CLAUDE_CODE_SLACK_BOT_TOKEN - Slack Bot OAuth Token
    CLAUDE_CODE_SLACK_CHANNEL_ID - Slack Channel ID

Workflow identification method (based on directory scan):
    1. Scan the .workflow/ directory to view the list of active workflows
    2. 1 active workflow -> select that workflow
    3. Multiple -> Filter workflows with phase="PLAN"
    4. Multiple PLAN -> Select the workflow with the most recent updated_at in the status.json of each workflow
    5. Construct messages by reading the local <workDir>/.context.json of the identified workflow
    6. Use existing fallback format in case of identification failure

Agent-specific colored emojis:
    Read the local .context.json's agent field and display that agent's emoji in front of the message.
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
    """Extract the first question text from stdin JSON.

    Args:
        data: JSON dictionary parsed from stdin

    Returns:
        First question string. If extraction fails, 'N/A' is returned.
    """
    return extract_json_field(
        data, "tool_input", "questions", 0, "question", default="N/A"
    )


def _extract_options(data: dict[str, Any]) -> str:
    """Extract options from stdin JSON Returns in "label - description | ..." format.

    Args:
        data: JSON dictionary parsed from stdin

    Returns:
        'label - description | An optional string in the format '...'. If there are no options, an empty string is returned.
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
    """AskUserQuestion hook Entry point for sending Slack notifications.

    Read JSON from stdin and parse the user question content,
    Identify active workflow information and send notifications to Slack.
    Quietly exits if environment variable loading fails.
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
