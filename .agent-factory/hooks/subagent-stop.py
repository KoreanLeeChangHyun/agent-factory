#!/usr/bin/env -S python3 -u
"""Compatibility wrapper for the SubagentStop hook app."""

from __future__ import annotations

import os
import sys

_AGENT_FACTORY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AGENT_FACTORY_DIR not in sys.path:
    sys.path.insert(0, _AGENT_FACTORY_DIR)

from engine.apps.hooks.subagent_stop import (  # noqa: E402
    _append_log,
    _resolve_fail_record_bin,
    _scan_and_trigger_fail_record,
    main,
    subprocess,
)


if __name__ == "__main__":
    sys.exit(main())
