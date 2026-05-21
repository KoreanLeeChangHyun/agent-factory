"""Shared imports, constants, logger for server/ package."""

from __future__ import annotations

import json
import logging
import os
import threading
import time

# noqa: F401 — Pattern  common.py handlers/* reimport identifiers of factory data
# hub role.  common.py direct use in internally export duty.
from board.factory_data import (  # noqa: F401
    CONVEYOR_DIRS_LIST,
    WF_BASE,
    WF_HISTORY,
    DASH_BASE,
    DASH_FILES,
    WF_ENTRY_RE,
    WF_DETAIL_FILES,
    _resolve_settings_file,
    _parse_env_file,
    _update_env_value,
    _read_conveyor_work_requests,
    _read_dashboard,
    _list_workflow_entries,
    _get_git_branch,
    _workflow_detail,
    _resolve_memory_dir,
    _list_memory_files,
    _read_memory_file,
    _write_memory_file,
    _delete_memory_file,
    _list_rules_files,
    _read_rules_file,
    _write_rules_file,
    _delete_rules_file,
    _list_prompt_files,
    _read_prompt_file,
    _write_prompt_file,
    _delete_prompt_file,
    _read_claude_md,
    _write_claude_md,
    _read_roadmap,
    _read_quick_prompts,
    _write_quick_prompt,
    _delete_quick_prompt,
    _memory_gc_status,
    _memory_gc_run,
    _memory_gc_prune_archive,
)

from engine.apps.board_api.observability import (  # noqa: E402, F401
    api_endpoint,
    server_debug_log,
)


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PORT_RANGE_START: int = 9900
PORT_RANGE_END: int = 9999
WATCH_INTERVAL: float = 1.0
SERVER_STARTED_AT: str = time.strftime('%Y-%m-%d %H:%M:%S')
SERVER_PID: int = os.getpid()

# Monitoring Target Path -> SSE Event Type Mapping
WATCH_DIRS: dict[str, str] = {
    os.path.join('.agent-factory', 'work-requests', 'draft'): 'conveyor',
    os.path.join('.agent-factory', 'work-requests', 'accepted'): 'conveyor',
    os.path.join('.agent-factory', 'work-requests', 'executing'): 'conveyor',
    os.path.join('.agent-factory', 'work-requests', 'verifying'): 'conveyor',
    os.path.join('.agent-factory', 'work-requests', 'complete'): 'conveyor',
    os.path.join('.agent-factory', 'runs'): 'workflow',
    os.path.join('.agent-factory', 'runs', '.history'): 'workflow',
    os.path.join('.agent-factory', 'board', 'data'): 'dashboard',
    os.path.join('.agent-factory', 'roadmap'): 'roadmap',
}

# Memory GC Directory Guard — User Global Area, Project root Standard Relative View X
# (server.py need to convert to absolute view when watcher registration. Once SSE Channel Only Reservation)
MEMORY_WATCH_EVENT: str = 'memory_gc'

# Agent Factory sync (init.sh) bootstrap URL and simultaneous run lock
_WORKFLOW_SYNC_URL: str = (
    'https://raw.githubusercontent.com/KoreanLeeChangHyun/'
    'claude-workflow/main/init.sh'
)
_workflow_sync_lock: threading.Lock = threading.Lock()
