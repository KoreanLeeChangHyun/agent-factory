"""Shared imports, constants, logger for server/ package."""

from __future__ import annotations

import atexit
import collections
import datetime
import hashlib
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# board_data 는 sibling 모듈 (`.claude-organic/board/board_data.py`). 본 파일을
# `board.server` 패키지 경로로 import 한 환경에서도 bare `from board_data import`
# 가 통하도록 board/ 디렉터리를 sys.path 에 자체 부트스트랩.
_BOARD_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BOARD_PKG_DIR not in sys.path:
    sys.path.insert(0, _BOARD_PKG_DIR)

from board_data import (
    KANBAN_DIRS_LIST,
    WF_BASE,
    WF_HISTORY,
    DASH_BASE,
    DASH_FILES,
    WF_ENTRY_RE,
    WF_DETAIL_FILES,
    _resolve_settings_file,
    _parse_env_file,
    _update_env_value,
    _read_kanban_tickets,
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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PORT_RANGE_START: int = 9900
PORT_RANGE_END: int = 9999
WATCH_INTERVAL: float = 1.0
SERVER_STARTED_AT: str = time.strftime('%Y-%m-%d %H:%M:%S')
SERVER_PID: int = os.getpid()

# 감시 대상 경로 -> SSE 이벤트 타입 매핑
WATCH_DIRS: dict[str, str] = {
    os.path.join('.claude-organic', 'tickets', 'open'): 'kanban',
    os.path.join('.claude-organic', 'tickets', 'progress'): 'kanban',
    os.path.join('.claude-organic', 'tickets', 'review'): 'kanban',
    os.path.join('.claude-organic', 'tickets', 'done'): 'kanban',
    os.path.join('.claude-organic', 'runs'): 'workflow',
    os.path.join('.claude-organic', 'runs', '.history'): 'workflow',
    os.path.join('.claude-organic', 'board', 'data'): 'dashboard',
    os.path.join('.claude-organic', 'roadmap'): 'roadmap',
}

# 메모리 GC 디렉터리 감시 — 사용자 글로벌 영역, project_root 기준 상대경로 X
# (server.py 가 watcher 등록 시 절대경로 변환 필요. 일단 SSE 채널만 예약)
MEMORY_WATCH_EVENT: str = 'memory_gc'

# Workflow sync (init-claude-workflow.sh) 부트스트랩 URL과 동시 실행 차단 락
_WORKFLOW_SYNC_URL: str = (
    'https://raw.githubusercontent.com/KoreanLeeChangHyun/'
    'claude-workflow/main/init-claude-workflow.sh'
)
_workflow_sync_lock: threading.Lock = threading.Lock()


# ── Server-side debug logger ──
# 클라이언트 Board.debugLog 와 동일 파일/형식. 플래그 파일이 존재할 때만 append.
def server_debug_log(tag: str, data: object) -> None:
    """서버 측 진단 로그를 .claude-organic/runs/bg/debug.log 에 append.

    플래그 파일 .claude-organic/runs/bg/debug.enabled 가 존재할 때만 기록.
    클라이언트 debugLog 와 같은 NDJSON 형식. 평소 오버헤드는 os.path.exists 한 번.
    """
    try:
        log_dir = os.path.join(os.getcwd(), '.claude-organic', 'runs', 'bg')
        if not os.path.exists(os.path.join(log_dir, 'debug.enabled')):
            return
        entry = {
            'ts': datetime.datetime.utcnow().isoformat() + 'Z',
            'tag': 'server.' + str(tag),
            'data': data,
        }
        with open(os.path.join(log_dir, 'debug.log'), 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + '\n')
    except (OSError, TypeError, ValueError):
        pass
