#!/usr/bin/env -S python3 -u
"""Compatibility wrapper for the PreToolUse hook app."""

from __future__ import annotations

import os
import sys

_AGENT_FACTORY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AGENT_FACTORY_DIR not in sys.path:
    sys.path.insert(0, _AGENT_FACTORY_DIR)

from engine.apps.hooks.pre_tool_use import (  # noqa: E402
    _record_tool_deny_metrics,
    main,
)


if __name__ == "__main__":
    sys.exit(main())
