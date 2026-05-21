#!/usr/bin/env -S python3 -u
"""flow-kanban done Guards verification of completion of derived ticket when executed.

Detect the flow-kanban done command in the PreToolUse(Bash) event,
If the ticket derived from the ticket in question is not Done, it is blocked.

Toggle: Environment variable HOOK_DONE_RELATION_GUARD (false/0 = disabled, default enabled)
"""

from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ET

# Set utils package import path
_engine_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

_guards_dir = os.path.dirname(os.path.abspath(__file__))
if _guards_dir not in sys.path:
    sys.path.insert(0, _guards_dir)

from common import read_env

# flow-kanban done T-NNN pattern
_DONE_PATTERN = re.compile(r"\bflow-kanban\s+done\s+(T-\d{3})\b")

# Kanban Directory
KANBAN_DIRS = ["todo", "open", "progress", "review"]


def _deny(reason: str) -> None:
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


def _find_ticket_xml(kanban_base: str, ticket_num: str) -> str | None:
    """Find the ticket XML path in any Kanban directory."""
    for d in KANBAN_DIRS + ["done"]:
        path = os.path.join(kanban_base, d, f"{ticket_num}.xml")
        if os.path.isfile(path):
            return path
    return None


def _get_ticket_status(kanban_base: str, ticket_num: str) -> str | None:
    """Returns the current status of the ticket."""
    path = _find_ticket_xml(kanban_base, ticket_num)
    if not path:
        return None
    try:
        tree = ET.parse(path)
        status_el = tree.find(".//metadata/status")
        return status_el.text.strip() if status_el is not None and status_el.text else None
    except (ET.ParseError, OSError):
        return None


def _find_derived_tickets(kanban_base: str, source_ticket: str) -> list[str]:
    """Returns a list of tickets referencing source_ticket as derived-from."""
    derived = []
    for d in KANBAN_DIRS + ["done"]:
        dir_path = os.path.join(kanban_base, d)
        if not os.path.isdir(dir_path):
            continue
        try:
            for entry in os.scandir(dir_path):
                if not entry.is_file() or not entry.name.endswith(".xml"):
                    continue
                try:
                    tree = ET.parse(entry.path)
                    for rel in tree.findall(".//relations/relation"):
                        if (rel.get("type") == "derived-from"
                                and rel.get("ticket") == source_ticket):
                            num_el = tree.find(".//metadata/number")
                            if num_el is not None and num_el.text:
                                derived.append(num_el.text.strip())
                except (ET.ParseError, OSError):
                    continue
        except OSError:
            continue
    return derived


def main() -> None:
    hook_flag = os.environ.get("HOOK_DONE_RELATION_GUARD") or read_env("HOOK_DONE_RELATION_GUARD")
    if hook_flag in ("false", "0"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    match = _DONE_PATTERN.search(command)
    if not match:
        sys.exit(0)

    ticket_num = match.group(1)

    # Project root estimation
    project_root = os.environ.get("PROJECT_ROOT", os.getcwd())
    kanban_base = os.path.join(project_root, ".agent-factory", "tickets")

    if not os.path.isdir(kanban_base):
        sys.exit(0)

    # Find derived tickets that reference this ticket as derived-from
    derived = _find_derived_tickets(kanban_base, ticket_num)
    if not derived:
        sys.exit(0)

    # Check if any of the derived tickets are not Done
    not_done = []
    for dt in derived:
        st = _get_ticket_status(kanban_base, dt)
        if st != "Done":
            not_done.append(f"{dt}({st or '?'})")

    if not_done:
        _deny(
            f"Block {ticket_num} Done: derived ticket {', '.join(not_done)}"
            f"It's not done yet. Proceed after completing the derivative ticket."
        )


if __name__ == "__main__":
    main()
