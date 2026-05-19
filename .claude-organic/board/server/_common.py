"""Shared imports, constants, logger for server/ package."""

from __future__ import annotations

import datetime
import functools
import json
import logging
import os
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

# board_data 는 sibling 모듈 (`.claude-organic/board/board_data.py`). 본 파일을
# `board.server` 패키지 경로로 import 한 환경에서도 bare `from board_data import`
# 가 통하도록 board/ 디렉터리를 sys.path 에 자체 부트스트랩.
_BOARD_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BOARD_PKG_DIR not in sys.path:
    sys.path.insert(0, _BOARD_PKG_DIR)

# noqa: E402 — sys.path 부트스트랩 이후에 import 필요.
# noqa: F401 — 본 _common.py 는 board_data 의 식별자를 handlers/* 가 재import 하는
# hub 역할. _common.py 내부에서 직접 사용 안 해도 export 의무.
from board_data import (  # noqa: E402, F401
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


# ---------------------------------------------------------------------------
# @api_endpoint decorator (T-511 P2)
# ---------------------------------------------------------------------------
# Board BE 의 모든 endpoint handler method 가 동일 디버그 tag 컨벤션으로
# debug.log 에 entry/exit/error 라인을 발화하도록 강제하는 표준 helper.
#
# 사용:
#     @api_endpoint("K", "move")
#     def _handle_kanban_move(self) -> None:
#         """...docstring 11 필드..."""
#         ...
#
# 발화 tag 형식 (project_board_api_spec.md §3):
#     api.<domain>.<verb>.entry  — 진입 직후
#     api.<domain>.<verb>.exit   — 정상 반환 직후
#     api.<domain>.<verb>.error  — 예외 발생 (예외는 그대로 재발생)
#
# server_debug_log 가 'server.' prefix 자동 부착 → 최종 NDJSON tag 는
# `server.api.<domain>.<verb>.<phase>` 가 된다.
#
# 오버헤드:
#   debug.enabled 플래그 부재 시 server_debug_log 가 즉시 return —
#   decorator 추가 비용은 functools.wraps 호출 + 빈 try/except 한 겹.
def api_endpoint(domain: str, verb: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Board BE endpoint handler method 표준 decorator.

    Args:
        domain: 도메인 코드 (project_board_api_spec.md §2 의 11종).
                K, W1, W2, T, M, PR, MET, WTC, MGC, SYS, INF.
        verb: 동사/명사 (list, get, save, delete, move, submit, done, …).

    Returns:
        decorated 함수. entry/exit/error 3 phase 의 debug.log 라인을 발화한다.

    예시 tag:
        api.K.move.entry / api.K.move.exit / api.K.move.error
    """
    base_tag = f"api.{domain}.{verb}"

    def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            server_debug_log(base_tag + '.entry', {'args_count': len(args), 'kwargs_keys': list(kwargs.keys())})
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                server_debug_log(base_tag + '.error', {'type': type(exc).__name__, 'msg': str(exc)})
                raise
            server_debug_log(base_tag + '.exit', {'result_type': type(result).__name__})
            return result

        return _wrapped

    return _decorator
