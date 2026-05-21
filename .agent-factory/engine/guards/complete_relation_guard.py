#!/usr/bin/env -S python3 -u
"""flow-conveyor complete Guards verification of completion of derived work_request when executed.

Detect the flow-conveyor complete command in the PreToolUse(Bash) event,
If the work_request derived from the work_request in question is not Complete, it is blocked.

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

# flow-conveyor complete WR-NNN pattern
_DONE_PATTERN = re.compile(r"\bflow-conveyor\s+complete\s+(T-\d{3})\b")

# Conveyor Directory
CONVEYOR_DIRS = ["draft", "open", "executing", "verifying"]


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


def _find_work_request_xml(conveyor_base: str, work_request_num: str) -> str | None:
    """Find the work_request XML path in any Conveyor directory."""
    for d in CONVEYOR_DIRS + ["complete"]:
        path = os.path.join(conveyor_base, d, f"{work_request_num}.xml")
        if os.path.isfile(path):
            return path
    return None


def _get_work_request_status(conveyor_base: str, work_request_num: str) -> str | None:
    """Returns the current status of the work_request."""
    path = _find_work_request_xml(conveyor_base, work_request_num)
    if not path:
        return None
    try:
        tree = ET.parse(path)
        status_el = tree.find(".//metadata/status")
        return status_el.text.strip() if status_el is not None and status_el.text else None
    except (ET.ParseError, OSError):
        return None


def _find_derived_work_requests(conveyor_base: str, source_work_request: str) -> list[str]:
    """Returns a list of work_requests referencing source_work_request as derived-from."""
    derived = []
    for d in CONVEYOR_DIRS + ["complete"]:
        dir_path = os.path.join(conveyor_base, d)
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
                                and rel.get("work_request") == source_work_request):
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

    work_request_num = match.group(1)

    # Project root estimation
    project_root = os.environ.get("PROJECT_ROOT", os.getcwd())
    conveyor_base = os.path.join(project_root, ".agent-factory", "work_requests")

    if not os.path.isdir(conveyor_base):
        sys.exit(0)

    # Find derived work_requests that reference this work_request as derived-from
    derived = _find_derived_work_requests(conveyor_base, work_request_num)
    if not derived:
        sys.exit(0)

    # Check if any of the derived work_requests are not Complete
    not_complete = []
    for dt in derived:
        st = _get_work_request_status(conveyor_base, dt)
        if st != "Complete":
            not_complete.append(f"{dt}({st or '?'})")

    if not_complete:
        _deny(
            f"Block {work_request_num} Complete: derived work_request {', '.join(not_complete)}"
            f"It's not complete yet. Proceed after completing the derivative work_request."
        )


if __name__ == "__main__":
    main()
