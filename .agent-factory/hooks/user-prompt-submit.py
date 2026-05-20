#!/usr/bin/env python3
"""Compatibility wrapper for the UserPromptSubmit hook app."""

import os
import sys

_AGENT_FACTORY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AGENT_FACTORY_DIR not in sys.path:
    sys.path.insert(0, _AGENT_FACTORY_DIR)

from engine.apps.hooks.user_prompt_submit import _is_main_session, main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
