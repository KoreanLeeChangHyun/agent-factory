#!/usr/bin/env -S python3 -u
"""inject_prompt.py - Injects a system-prompt dedicated to the workflow session with the SessionStart hook.

T-483 (2026-05-13): Discard system-prompt-wf.xml + integrate SKILL.md directly with inject.
system prompt in workflow session = .claude/skills/workflow-orchestration/SKILL.md
(Body after frontmatter removal). The SKILL.md required to run the workflow engine has already been installed.
Must be session loaded, so consolidated into a single source of truth.

movement:
  - Determine workflow session (session_identifier.is_workflow_session) → If not, terminate immediately
  - Output .claude/skills/workflow-orchestration/SKILL.md body (frontmatter removed) to stdout
  - Add <ticket-prefix> XML block when detecting an active ticket (T-NNN) inject
"""

from __future__ import annotations

import os
import sys

_agent_factory_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
)
if _agent_factory_dir not in sys.path:
    sys.path.insert(0, _agent_factory_dir)

from engine.common import resolve_project_root
from engine.flow.flow_logger import append_log, resolve_work_dir_for_logging
from engine.flow.session_identifier import is_workflow_session, get_session_ticket_id


def _extract_ticket_id() -> str | None:
    """Returns the active ticket ID (T-NNN) of the current session.

    Delegates to session_identifier.get_session_ticket_id().

    Returns:
        Ticket ID string (e.g. "T-001"). None if not in a workflow session or if extraction fails.
    """
    return get_session_ticket_id()


def _is_workflow_session() -> bool:
    """Determines whether the current session is a workflow session.

    Delegates to session_identifier.is_workflow_session().

    Returns:
        True if it is a workflow session, False otherwise.
    """
    return is_workflow_session()


def _strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter (--- ... ---) from SKILL.md and return only the body.

    If frontmatter is not present, the original is returned.
    """
    if not content.startswith("---\n"):
        return content
    # Search for the second '---' location
    end_idx = content.find("\n---\n", 4)
    if end_idx == -1:
        return content
    return content[end_idx + 5 :].lstrip()


def main() -> None:
    """Determines the session type and outputs the SKILL.md body to stdout only when it is a workflow session.

    The main session (if it is not a workflow session) ends immediately without outputting anything.
    The main session policy is handled by CLAUDE.md + .claude/rules/workflow.md.
    """
    project_root = resolve_project_root()

    if not _is_workflow_session():
        sys.exit(0)

    skill_file = os.path.join(
        project_root, ".claude", "skills", "workflow-orchestration", "SKILL.md"
    )

    _log_dir = resolve_work_dir_for_logging(project_root)
    if _log_dir:
        append_log(_log_dir, "INFO", "inject_prompt: session_type=workflow source=SKILL.md")

    if not os.path.exists(skill_file):
        sys.exit(0)

    with open(skill_file, encoding="utf-8") as f:
        raw = f.read()
    content = _strip_frontmatter(raw)

    ticket_id = _extract_ticket_id()
    if ticket_id:
        ticket_prefix_block = (
            f"\n<ticket-prefix>\n"
            f"Be sure to print the [{ticket_id}] prefix on the first line of every response. \n"
            f"Example: [{ticket_id}] Response content... \n"
            f"</ticket-prefix>"
        )
        content = content + ticket_prefix_block

    print(content, end="")
    sys.exit(0)


if __name__ == "__main__":
    main()
