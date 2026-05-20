#!/usr/bin/env -S python3 -u
"""Compatibility wrapper for the PostToolUse hook app.

Claude Code settings point at this top-level script. Keep the file stable while
the implementation lives under ``engine.apps.hooks``.
"""

from __future__ import annotations

import os
import sys

_AGENT_FACTORY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AGENT_FACTORY_DIR not in sys.path:
    sys.path.insert(0, _AGENT_FACTORY_DIR)

from engine.apps.hooks.post_tool_use import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
