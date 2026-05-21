"""BoardHTTPRequestHandler — base HTTP router + Mixin composition."""

from __future__ import annotations

import json
import os
from http.server import SimpleHTTPRequestHandler

from board.server.support.common import _update_env_value
from engine.apps.board_api.files import FilesHandlerMixin
from engine.apps.board_api.sync import SyncHandlerMixin
from engine.apps.board_api.settings import SettingsHandlerMixin
from engine.apps.board_api.generic import GenericHandlerMixin
from engine.apps.board_api.terminal import TerminalHandlerMixin
from engine.apps.board_api.production_line_workflow import ProductionLineWorkflowHandlerMixin
from engine.apps.board_api.conveyor import ConveyorHandlerMixin
from engine.apps.board_api.metrics import MetricsHandlerMixin
from engine.apps.board_api.memory_gc import MemoryGcHandlerMixin
from engine.apps.board_api.worktree_commit import WorktreeCommitHandlerMixin
from engine.apps.board_api.ops_endpoints import OpsHandlerMixin


# T-513 P5 — V1 workflow engine batch disposal. WorkflowHandlerMixin +
# WorkflowUndoHandlerMixin Removal. Production Line
# (conveyor undo-complete absorption + settings workflow-sync absorption).
class BoardHTTPRequestHandler(
    TerminalHandlerMixin,
    ProductionLineWorkflowHandlerMixin,
    ConveyorHandlerMixin,
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
    """Board-only HTTP request handler.

    /events path is handled with SSE endpoint,
    /api/* path is handled with JSON API,
    Other paths are entrusted with the static file serving of SimpleHTTPRequestHandler.
    static files are called ``.agent-factory/board/web` directory.
    """

    def __init__(self, *args, **kwargs) -> None:
        static_dir = os.path.join(
            os.getcwd(), '.agent-factory', 'board', 'web',
        )
        self._project_root = os.getcwd()
        super().__init__(*args, directory=static_dir, **kwargs)

    def translate_path(self, path: str) -> str:
        """Default file path.

        Tag:
          - ``/.agent-factory/board/*` → ``web/*`
          - ``/.agent-factory/board/static/*`
          - ``/.agent-factory/*` → Project route (workflow output)
          - Other → ``web/*` (default)
        """
        from urllib.parse import urlsplit, unquote
        clean = urlsplit(path).path
        clean = unquote(clean)
        legacy = '/.agent-factory/board/'
        if clean.startswith(legacy):
            rel = clean[len(legacy):]
            if rel.startswith('static/'):
                rel = rel[len('static/'):]
            return os.path.join(self.directory, rel)
        wf_prefix = '/.agent-factory/'
        if clean.startswith(wf_prefix):
            rel = clean.lstrip('/')
            return os.path.join(self._project_root, rel)
        return super().translate_path(path)

    def do_GET(self) -> None:
        """handle GET requests."""
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
        elif self.path == '/api/conveyor/branch/active':
            self._handle_conveyor_branch_active()
        elif self.path.startswith('/api/v2/sessions') and self._production_line_dispatch_get():
            return
        elif self.path == '/api/ops/sse-status':
            self._handle_ops_sse_status()
        # T-513 P5 — conveyor domain singleization (V1 workflow alias batch waste).
        elif self.path == '/api/conveyor/workflow-entries':
            self._handle_conveyor_workflow_entries()
        elif self.path.startswith('/api/conveyor/workflow-detail'):
            self._handle_conveyor_workflow_detail()
        elif self.path.startswith('/api/'):
            self._handle_api()
        else:
            super().do_GET()

    def do_POST(self) -> None:
        """POST request."""
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
        # T-513 P5 — settings domain singleization (V1 sync alias batch disposal).
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
        elif self.path.startswith('/api/v2/sessions') and self._production_line_dispatch_post():
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
        elif self.path == '/api/conveyor/move':
            self._handle_conveyor_move()
        elif self.path == '/api/conveyor/workrequest':
            self._handle_conveyor_workrequest()
        elif self.path == '/api/conveyor/submit':
            self._handle_conveyor_submit()
        elif self.path == '/api/conveyor/complete':
            self._handle_conveyor_complete()
        elif self.path == '/api/conveyor/delete':
            self._handle_conveyor_delete()
        elif self.path == '/api/conveyor/branch/toggle':
            self._handle_conveyor_branch_toggle()
        elif self.path == '/api/conveyor/worktree-commit':
            self._handle_worktree_commit()
        # T-513 P5 — conveyor domain singleization (V1 undo-complete alias batch disposal).
        elif self.path == '/api/conveyor/undo-complete':
            self._handle_conveyor_undo_complete()
        elif self.path == '/api/ops/zombie-reap':
            self._handle_ops_zombie_reap()
        elif self.path == '/api/ops/debug-toggle':
            self._handle_ops_debug_toggle()
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self) -> None:
        """DELETE request.

        T-511 P4 — DELETE Quarter 4 generic.py ` handle api delete` dispatcher
        Inlinelogic X). Production-line Session DELETE is named ' production line dispatch delete'.
        """
        if self.path.startswith('/api/v2/sessions') and self._production_line_dispatch_delete():
            return
        if self.path.startswith('/api/'):
            self._handle_api_delete()
            return
        self.send_response(404)
        self.end_headers()

    def do_PATCH(self) -> None:
        """PATCH requests.

        T-511 P4 — production-line session status forced update (debug/recovery).
        This method is not the default of SimpleHTTPRequestHandler.
        """
        if self.path.startswith('/api/v2/sessions') and self._production_line_dispatch_patch():
            return
        self.send_response(404)
        self.end_headers()

    def _send_json(self, data: object) -> None:
        """JSON response."""
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _parse_query_param(self, key: str) -> str | None:
        """Extract the value of the specified key in the URL query parameter.

        Args:
            key: query parameter key to extract

        Returns:
            parameter value string. None.
        """
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        values = parse_qs(parsed.query).get(key)
        return values[0] if values else None

    def _read_json_body(self) -> dict | None:
        """returns the JSON body of the POST request.

        When parsing fails to send 400 error and return None.

        Returns:
            dict. None.
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
        """Sends JSON responses with specified HTTP status code.

        Args:
            status: HTTP status code
            data: JSON serialized response body
        """
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str) -> None:
        """Send an error response to JSON format.

        Args:
            code: HTTP status code
            message: error message
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
        """CORS preflight request."""
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, PATCH, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        """output log messages. Only SSE routes are logging at least.

        Args:
            format: log format string
            *args: format factor
        """
        # static file request log suppression, SSE/Terminal only logging (/poll request suppression)
        if args and isinstance(args[0], str) and (
            '/events' in args[0] or '/terminal' in args[0]
        ):
            super().log_message(format, *args)

    def end_headers(self) -> None:
        """Add CORS header and exit header."""
        # Add CORS header to request such as SSE, poll, terminal (fetch compatible in index.html)
        # /events, /poll, /terminal/* adds CORS header directly from each handler except
        if self.path not in ('/events', '/poll') and not self.path.startswith('/terminal/'):
            self.send_header('Access-Control-Allow-Origin', '*')
        # JS/CSS File Cache Prevention
        if self.path.endswith(('.js', '.css')):
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()
