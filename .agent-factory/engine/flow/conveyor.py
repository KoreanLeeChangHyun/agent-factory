#!/usr/bin/env -S python3 -u
"""conveyor.py - Conveyor board state management CLI router.

Use the XML work_request file (.conveyor/active/WR-NNN.xml) as the Single Source of Truth (SSoT).
No LLM calls (pure IO).

Usage:
  python3 conveyor.py create <title>
  python3 conveyor.py move <work_request> <target>
  python3 conveyor.py complete <work_request>
  python3 conveyor.py delete <work_request>
  python3 conveyor.py update-title <work_request> <title>
  python3 conveyor.py update-prompt <work_request> [--command <cmd>] [--goal "<goal>"] [--target "<target>"] ...
  python3 conveyor.py update-result <work_request> [--registrykey <RK>] [--workdir <WD>] [--plan <P>] [--report <R>]
  python3 conveyor.py set-editing <work_request> <on|off>
  python3 conveyor.py link <work_request> --derived-from <WR-NNN>
  python3 conveyor.py unlink <work_request> --derived-from <WR-NNN>
  python3 conveyor.py board
  python3 conveyor.py show <work_request>
  python3 conveyor.py list [status]

Business logic is delegated to the modules below:
  flow.work_request_repository - XML ​​CRUD, file navigation, utilities
  flow.ticket_state - State transition rules, state updates
  flow.conveyor_cli - subcommand implementation, argparse parser, dispatch
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

from flow.conveyor_cli import build_parser, dispatch  # noqa: E402
from flow.work_request_repository import log  # noqa: E402


# ─── main ────────────────────────────────────────────────────────────────────


def main() -> None:
    """CLI entry point. Parse the subcommand and call the corresponding handler."""
    parser = build_parser()
    args = parser.parse_args()
    log("INFO", f"conveyor.py: subcommand={args.subcommand}")
    dispatch(args)


if __name__ == "__main__":
    main()
