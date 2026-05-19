"""BoardHTTPRequestHandler — base HTTP router + Mixin composition."""

from __future__ import annotations

import json
import os
from http.server import SimpleHTTPRequestHandler

from ._common import _update_env_value
from .handlers.files import FilesHandlerMixin
from .handlers.sync import SyncHandlerMixin
from .handlers.settings import SettingsHandlerMixin
from .handlers.generic import GenericHandlerMixin
from .handlers.terminal import TerminalHandlerMixin
from .handlers.v2_workflow import V2WorkflowHandlerMixin
from .handlers.kanban import KanbanHandlerMixin
from .handlers.metrics import MetricsHandlerMixin
from .handlers.memory_gc import MemoryGcHandlerMixin
from .handlers.worktree_commit import WorktreeCommitHandlerMixin
from .handlers.ops_endpoints import OpsHandlerMixin


# T-513 P5 — V1 워크플로우 엔진 일괄 폐기. WorkflowHandlerMixin +
# WorkflowUndoHandlerMixin 제거. V2 단일화 (V2WorkflowHandlerMixin +
# kanban undo-done 흡수 + settings workflow-sync 흡수).
class BoardHTTPRequestHandler(
    TerminalHandlerMixin,
    V2WorkflowHandlerMixin,
    KanbanHandlerMixin,
    MetricsHandlerMixin,
    MemoryGcHandlerMixin,
    WorktreeCommitHandlerMixin,
    OpsHandlerMixin,
    FilesHandlerMixin,
    GenericHandlerMixin,
    SyncHandlerMixin,
    SettingsHandlerMixin,
    SimpleHTTPRequestHandler,
):
    """Board 전용 HTTP 요청 핸들러.

    /events 경로는 SSE 엔드포인트로 처리하고,
    /api/* 경로는 JSON API로 처리하고,
    그 외 경로는 SimpleHTTPRequestHandler의 정적 파일 서빙으로 위임한다.
    정적 파일은 ``.claude-organic/board/static`` 디렉터리를 루트로 서빙한다.
    """

    def __init__(self, *args, **kwargs) -> None:
        static_dir = os.path.join(
            os.getcwd(), '.claude-organic', 'board', 'static',
        )
        self._project_root = os.getcwd()
        super().__init__(*args, directory=static_dir, **kwargs)

    def translate_path(self, path: str) -> str:
        """정적 파일 경로를 해석한다.

        라우팅:
          - ``/.claude-organic/board/*`` → ``static/*`` (기존 북마크 호환)
          - ``/.claude-organic/*``       → 프로젝트 루트 (워크플로우 산출물)
          - 그 외                          → ``static/*`` (기본)
        """
        from urllib.parse import urlsplit, unquote
        clean = urlsplit(path).path
        clean = unquote(clean)
        legacy = '/.claude-organic/board/'
        if clean.startswith(legacy):
            rel = clean[len(legacy):]
            return os.path.join(self.directory, rel)
        wf_prefix = '/.claude-organic/'
        if clean.startswith(wf_prefix):
            rel = clean.lstrip('/')
            return os.path.join(self._project_root, rel)
        return super().translate_path(path)

    def do_GET(self) -> None:
        """GET 요청을 처리한다."""
        if self.path == '/events':
            self._handle_sse()
        elif self.path == '/poll':
            self._handle_poll()
        elif self.path.startswith('/terminal/events'):
            self._handle_terminal_sse()
        elif self.path == '/terminal/status':
            self._handle_terminal_status()
        elif self.path == '/terminal/sessions':
            self._handle_terminal_sessions()
        elif self.path.startswith('/terminal/history'):
            self._handle_terminal_history()
        elif self.path == '/api/kanban/branch/active':
            self._handle_kanban_branch_active()
        elif self.path.startswith('/api/v2/sessions') and self._v2_dispatch_get():
            return
        elif self.path == '/api/ops/sse-status':
            self._handle_ops_sse_status()
        # T-513 P5 — kanban 도메인 단일화 (V1 워크플로우 alias 일괄 폐기).
        elif self.path == '/api/kanban/workflow-entries':
            self._handle_kanban_workflow_entries()
        elif self.path.startswith('/api/kanban/workflow-detail'):
            self._handle_kanban_workflow_detail()
        elif self.path.startswith('/api/'):
            self._handle_api()
        else:
            super().do_GET()

    def do_POST(self) -> None:
        """POST 요청을 처리한다."""
        if self.path == '/api/env':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                ok = _update_env_value(os.getcwd(), data['key'], data['value'])
                self._send_json({'ok': ok})
            except (json.JSONDecodeError, KeyError):
                self.send_response(400)
                self.end_headers()
        elif self.path == '/api/restart':
            self._handle_restart()
        elif self.path == '/api/debug-log':
            self._handle_debug_log()
        # T-513 P5 — settings 도메인 단일화 (V1 sync alias 일괄 폐기).
        elif self.path == '/api/settings/workflow-sync':
            self._handle_settings_workflow_sync()
        elif self.path == '/terminal/start':
            self._handle_terminal_start()
        elif self.path == '/terminal/input':
            self._handle_terminal_input()
        elif self.path == '/terminal/interrupt':
            self._handle_terminal_interrupt()
        elif self.path == '/terminal/kill':
            self._handle_terminal_kill()
        elif self.path.startswith('/api/v2/sessions') and self._v2_dispatch_post():
            return
        elif self.path == '/terminal/command':
            self._handle_terminal_command()
        elif self.path == '/terminal/permission':
            self._handle_terminal_permission()
        elif self.path == '/api/memory/file':
            self._handle_memory_write()
        elif self.path == '/api/prompt/rules/file':
            self._handle_rules_write()
        elif self.path == '/api/prompt/prompt-files/file':
            self._handle_prompt_write()
        elif self.path == '/api/prompt/claude-md':
            self._handle_claude_md_write()
        elif self.path == '/api/quick-prompts/item':
            self._handle_quick_prompt_write()
        elif self.path == '/api/memory/gc/run':
            self._handle_memory_gc_run()
        elif self.path == '/api/memory/gc/prune-archive':
            self._handle_memory_gc_prune()
        elif self.path == '/api/kanban/move':
            self._handle_kanban_move()
        elif self.path == '/api/kanban/submit':
            self._handle_kanban_submit()
        elif self.path == '/api/kanban/done':
            self._handle_kanban_done()
        elif self.path == '/api/kanban/delete':
            self._handle_kanban_delete()
        elif self.path == '/api/kanban/branch/toggle':
            self._handle_kanban_branch_toggle()
        elif self.path == '/api/kanban/worktree-commit':
            self._handle_worktree_commit()
        # T-513 P5 — kanban 도메인 단일화 (V1 undo-done alias 일괄 폐기).
        elif self.path == '/api/kanban/undo-done':
            self._handle_kanban_undo_done()
        elif self.path == '/api/ops/zombie-reap':
            self._handle_ops_zombie_reap()
        elif self.path == '/api/ops/debug-toggle':
            self._handle_ops_debug_toggle()
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self) -> None:
        """DELETE 요청을 처리한다.

        T-511 P4 — DELETE 분기 4건을 generic.py `_handle_api_delete` dispatcher
        에 위임 (inline 로직 X). v2 세션 DELETE 는 `_v2_dispatch_delete` 위임.
        """
        if self.path.startswith('/api/v2/sessions') and self._v2_dispatch_delete():
            return
        if self.path.startswith('/api/'):
            self._handle_api_delete()
            return
        self.send_response(404)
        self.end_headers()

    def do_PATCH(self) -> None:
        """PATCH 요청을 처리한다.

        T-511 P4 — v2 세션 status 강제 갱신 (debug/recovery).
        본 메서드는 SimpleHTTPRequestHandler 의 기본에는 없으므로 신설.
        """
        if self.path.startswith('/api/v2/sessions') and self._v2_dispatch_patch():
            return
        self.send_response(404)
        self.end_headers()

    def _send_json(self, data: object) -> None:
        """JSON 응답을 전송한다."""
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _parse_query_param(self, key: str) -> str | None:
        """URL 쿼리 파라미터에서 지정한 키의 값을 추출한다.

        Args:
            key: 추출할 쿼리 파라미터 키

        Returns:
            파라미터 값 문자열. 존재하지 않으면 None.
        """
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        values = parse_qs(parsed.query).get(key)
        return values[0] if values else None

    def _read_json_body(self) -> dict | None:
        """POST 요청의 JSON 본문을 파싱하여 반환한다.

        파싱 실패 시 400 에러를 전송하고 None을 반환한다.

        Returns:
            파싱된 dict. 실패 시 None.
        """
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self._send_error(400, 'Empty request body')
            return None

        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_error(400, 'Invalid JSON')
            return None

        if not isinstance(data, dict):
            self._send_error(400, 'Expected JSON object')
            return None

        return data

    def _send_json_with_status(self, status: int, data: object) -> None:
        """지정한 HTTP 상태 코드로 JSON 응답을 전송한다.

        Args:
            status: HTTP 상태 코드
            data: JSON 직렬화 가능한 응답 본문
        """
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str) -> None:
        """에러 응답을 JSON 형식으로 전송한다.

        Args:
            code: HTTP 상태 코드
            message: 에러 메시지
        """
        body = json.dumps(
            {'ok': False, 'error': message},
            ensure_ascii=False,
        ).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        """CORS preflight 요청을 처리한다."""
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, PATCH, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        """로그 메시지를 출력한다. SSE 경로만 최소 로깅한다.

        Args:
            format: 로그 포맷 문자열
            *args: 포맷 인자
        """
        # 정적 파일 요청 로그 억제, SSE/터미널 관련만 로깅 (/poll 요청도 억제)
        if args and isinstance(args[0], str) and (
            '/events' in args[0] or '/terminal' in args[0]
        ):
            super().log_message(format, *args)

    def end_headers(self) -> None:
        """CORS 헤더를 추가한 후 헤더를 종료한다."""
        # SSE, poll, terminal 외 요청에도 CORS 헤더 추가 (index.html에서의 fetch 호환)
        # /events, /poll, /terminal/*은 각 핸들러에서 직접 CORS 헤더를 추가하므로 제외
        if self.path not in ('/events', '/poll') and not self.path.startswith('/terminal/'):
            self.send_header('Access-Control-Allow-Origin', '*')
        # JS/CSS 파일 캐시 방지
        if self.path.endswith(('.js', '.css')):
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()
