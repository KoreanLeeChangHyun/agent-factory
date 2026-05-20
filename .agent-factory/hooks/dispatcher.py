"""Compatibility wrapper for Claude Code hook dispatcher utilities.

Claude Code settings point at scripts in ``.agent-factory/hooks`` and those
scripts import ``dispatcher`` from this directory. Keep that stable surface
while the implementation lives under ``engine.adapters.hooks``.
"""

from __future__ import annotations

import os
import sys

_AGENT_FACTORY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AGENT_FACTORY_DIR not in sys.path:
    sys.path.insert(0, _AGENT_FACTORY_DIR)

from engine.adapters.hooks.dispatcher import (  # noqa: E402,F401
    _env_path,
    _find_project_root,
    _find_workflow_log,
    collect_exit_codes,
    collect_outputs,
    dispatch,
    dispatch_async,
    is_enabled,
    load_env_flags,
    run_inline,
    scripts_dir,
)

__all__ = [
    "_env_path",
    "_find_project_root",
    "_find_workflow_log",
    "collect_exit_codes",
    "collect_outputs",
    "dispatch",
    "dispatch_async",
    "is_enabled",
    "load_env_flags",
    "run_inline",
    "scripts_dir",
]
