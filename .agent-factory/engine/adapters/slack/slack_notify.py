#!/usr/bin/env -S python3 -u
"""Slack message sending script.

New signature (based on workDir):
    python3 slack_notify.py <workDir> <state> [report path] [agent]
    - Detected in a new way if workDir starts with .agent-factory/ or an absolute path (/)
    - workDir format: .agent-factory/runs/YYYYMMDD-HHMMSS/
      Or the old format: .agent-factory/runs/YYYYMMDD-HHMMSS/<workName>/<command> (backwards compatible)
    - Automatically read title, workId, workName, and command from .context.json

Existing signatures (backwards compatible):
    python3 slack_notify.py <Task Title> <Task ID> <Task Name> <Command> <Status> [Report Path] [Agent]

Main functions:
    main: Slack notification sending entry point

Environment variables (loaded from .agent-factory/.settings):
    AGENT_FACTORY_SLACK_BOT_TOKEN - Slack Bot OAuth Token
    AGENT_FACTORY_SLACK_CHANNEL_ID - Slack Channel ID

Agent-specific colored emojis:
    When the agent argument is received, the emoji is determined based on that value.
    If there is no agent argument, the existing format is maintained without emojis.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse

_script_dir = os.path.dirname(os.path.abspath(__file__))
_agent_factory_dir = os.path.normpath(os.path.join(_script_dir, "..", "..", ".."))
if _agent_factory_dir not in sys.path:
    sys.path.insert(0, _agent_factory_dir)

from engine.adapters.slack.slack_common import (
    build_json_payload,
    get_agent_emoji,
    load_slack_env,
    log_warn,
    send_slack_message,
    SLACK_CHANNEL_ID,
)
from engine.common import (
    extract_registry_key,
    load_json_file,
    resolve_project_root,
    TS_PATTERN,
)


def _detect_wsl() -> bool:
    """Detects whether it is a WSL environment.

    Returns:
        True if it is a WSL environment, False otherwise.
    """
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except (IOError, OSError):
        return False


def _get_wsl_distro_name() -> str:
    """Extract the WSL distribution name.

    Reads the distribution name and version from /etc/os-release and returns it in 'Ubuntu-22.04' format.

    Returns:
        A distro name string in the format 'Distro-Version'. If parsing fails, an empty string is returned.
    """
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


def _build_vscode_uri(abs_path: str) -> str:
    """Convert the file path to vscode:// URI.

    Detects WSL, Mac, and Linux environments respectively and converts them to appropriate URI format.

    Args:
        abs_path: Absolute path of the file to convert

    Returns:
        URI string in vscode:// scheme
    """
    encoded = urllib.parse.quote(abs_path, safe="/")
    if _detect_wsl():
        distro_name = _get_wsl_distro_name()
        return f"vscode://file//wsl$/{distro_name}{encoded}"
    return f"vscode://file{encoded}"


def _parse_new_signature(args: list[str]) -> dict[str, str]:
    """Parse the new signature: <workDir> <state> [reportpath] [agent].

    The title, work_id, work_name, and command are automatically read from .context.json.

    Args:
        args: Command line argument list (sys.argv[1:])

    Returns:
        Dictionary with keys title, work_id, work_name, command, status, report_path, agent

    Raises:
        SystemExit: Insufficient number of arguments or absence of .context.json file/parsing failure
    """
    if len(args) < 2:
        log_warn("Usage: slack_notify.py <workDir> <state> [report path] [agent]")
        sys.exit(1)

    work_dir = args[0]
    status = args[1]
    report_path = args[2] if len(args) > 2 else ""
    agent = args[3] if len(args) > 3 else ""

    project_root = resolve_project_root()

    # workDir absolute path calculation
    if os.path.isabs(work_dir):
        abs_work_dir = work_dir
    else:
        abs_work_dir = os.path.join(project_root, work_dir)

    # Read .context.json
    context_file = os.path.join(abs_work_dir, ".context.json")
    if not os.path.isfile(context_file):
        log_warn(f"Cannot find .context.json: {context_file}")
        sys.exit(0)

    ctx = load_json_file(context_file)
    if ctx is None:
        log_warn(f"Failed to parse .context.json: {context_file}")
        sys.exit(0)

    title = ctx.get("title", "") or "unknown"
    work_id = ctx.get("workId", "") or "none"
    work_name = ctx.get("workName", "") or title
    command = ctx.get("command", "") or "unknown"

    # Extract YYYYMMDD-HHMMSS identifier from workDir
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


def _parse_legacy_signature(args: list[str]) -> dict[str, str]:
    """Parse existing signatures: <task title> <task ID> <task name> <command> <state> [report path] [agent].

    Args:
        args: Command line argument list (sys.argv[1:])

    Returns:
        Dictionary with keys title, work_id, work_name, command, status, report_path, agent

    Raises:
        SystemExit: If there are less than 5 required arguments
    """
    if len(args) < 5:
        log_warn(
            "Usage: slack_notify.py <Task Title> <Task ID> <Task Name> <Command> <Status>"
            "[Report Path] [Agent]"
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


def main() -> None:
    """Entry point for sending Slack messages.

    Parses command line arguments and creates a new signature (based on workDir) or an existing signature.
    Organize task information and send notifications to Slack.
    Quietly exits if environment variable loading fails.
    """
    args = sys.argv[1:]

    # Load environment variables (quietly exits on failure)
    if not load_slack_env():
        sys.exit(0)

    # Double signature detection
    if args and (args[0].startswith(".agent-factory/") or args[0].startswith("/")):
        info = _parse_new_signature(args)
    else:
        info = _parse_legacy_signature(args)

    # Agent Emoji Decision
    agent_emoji = ""
    if info["agent"]:
        agent_emoji = get_agent_emoji(info["agent"])

    # Create an emoji prefix
    emoji_prefix = f"{agent_emoji} " if agent_emoji else ""

    # Create report vscode:// link
    report_link = ""
    if info["report_path"]:
        report_path = info["report_path"]
        project_root = resolve_project_root()
        if os.path.isabs(report_path):
            abs_report = report_path
        else:
            abs_report = os.path.join(project_root, report_path)
        vscode_uri = _build_vscode_uri(abs_report)
        report_link = f"\n - Report: <{vscode_uri}|Open Report>"

    # Organize Slack messages
    message = (
        f"{emoji_prefix}*{info['title']}*\n"
        f"- Work ID: `{info['work_id']}` \n"
        f"- Work name: {info['work_name']} \n"
        f"- Command: `{info['command']}` \n"
        f"- Status: {info['status']}"
        f"{report_link}"
    )

    # Configure JSON payload + send to Slack
    from slack.slack_common import SLACK_CHANNEL_ID as _channel
    json_payload = build_json_payload(_channel, message)
    send_slack_message(json_payload)

    sys.exit(0)


if __name__ == "__main__":
    main()
