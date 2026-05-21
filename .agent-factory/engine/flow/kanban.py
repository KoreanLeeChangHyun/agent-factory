#!/usr/bin/env -S python3 -u
"""kanban.py - Kanban board state management CLI router.

Use the XML ticket file (.kanban/active/T-NNN.xml) as the Single Source of Truth (SSoT).
No LLM calls (pure IO).

Usage:
  python3 kanban.py create <title>
  python3 kanban.py move <ticket> <target>
  python3 kanban.py done <ticket>
  python3 kanban.py delete <ticket>
  python3 kanban.py update-title <ticket> <title>
  python3 kanban.py update-prompt <ticket> [--command <cmd>] [--goal "<goal>"] [--target "<target>"] ...
  python3 kanban.py update-result <ticket> [--registrykey <RK>] [--workdir <WD>] [--plan <P>] [--report <R>]
  python3 kanban.py set-editing <ticket> <on|off>
  python3 kanban.py link <ticket> --derived-from <T-NNN>
  python3 kanban.py unlink <ticket> --derived-from <T-NNN>
  python3 kanban.py board
  python3 kanban.py show <ticket>
  python3 kanban.py list [status]

Business logic is delegated to the modules below:
  flow.ticket_repository - XML ​​CRUD, file navigation, utilities
  flow.ticket_state - State transition rules, state updates
  flow.kanban_cli - subcommand implementation, argparse parser, dispatch
"""

from __future__ import annotations

import os
import sys

# ─── sys.path settings ────────────────────────────────────────────────────────────────

_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR: str = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# ─── Import module ───────────────────────────────────────────────────────────────

from flow.kanban_cli import build_parser, dispatch  # noqa: E402
from flow.ticket_repository import log  # noqa: E402


# ─── main ────────────────────────────────────────────────────────────────────


def main() -> None:
    """CLI entry point. Parse the subcommand and call the corresponding handler."""
    parser = build_parser()
    args = parser.parse_args()
    log("INFO", f"kanban.py: subcommand={args.subcommand}")
    dispatch(args)


if __name__ == "__main__":
    main()
