"""BoardHTTPRequestHandler — base HTTP router + Mixin composition."""

from __future__ import annotations

import json
import os
from http.server import SimpleHTTPRequestHandler

from ._common import (
    logger,
    _update_env_value,
    _delete_memory_file,
    _delete_rules_file,
    _delete_prompt_file,
)
from .handlers.files import FilesHandlerMixin
from .handlers.sync import SyncHandlerMixin
from .handlers.generic import GenericHandlerMixin
from .handlers.terminal import TerminalHandlerMixin
from .handlers.workflow import WorkflowHandlerMixin


class BoardHTTPRequestHandler(
    TerminalHandlerMixin,
    WorkflowHandlerMixin,
    FilesHandlerMixin,
    GenericHandlerMixin,
    SyncHandlerMixin,
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
        elif self.path.startswith('/terminal/workflow/status'):
            self._handle_workflow_status()
        elif self.path.startswith('/terminal/workflow/events'):
            self._handle_workflow_sse()
        elif self.path == '/terminal/workflow/list':
            self._handle_workflow_list()
        elif self.path.startswith('/terminal/workflow/history'):
            self._handle_workflow_history()
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
        elif self.path == '/api/workflow/sync':
            self._handle_workflow_sync()
        elif self.path == '/terminal/start':
            self._handle_terminal_start()
        elif self.path == '/terminal/input':
            self._handle_terminal_input()
        elif self.path == '/terminal/interrupt':
            self._handle_terminal_interrupt()
        elif self.path == '/terminal/kill':
            self._handle_terminal_kill()
        elif self.path == '/terminal/workflow/start':
            self._handle_workflow_start()
        elif self.path == '/terminal/workflow/kill':
            self._handle_workflow_kill()
        elif self.path == '/terminal/workflow/input':
            self._handle_workflow_input()
        elif self.path == '/terminal/workflow/step':
            self._handle_workflow_step_update()
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
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self) -> None:
        """DELETE 요청을 처리한다."""
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == '/api/memory/file':
            name = qs.get('name', [None])[0]
            if not name:
                self._send_error(400, 'Missing "name" query parameter')
                return
            try:
                self._send_json(
                    _delete_memory_file(os.getcwd(), name),
                )
            except ValueError as e:
                self._send_error(400, str(e))
            except FileNotFoundError as e:
                self._send_error(404, str(e))
        elif path == '/api/prompt/rules/file':
            rel_path = qs.get('path', [None])[0]
            if not rel_path:
                self._send_error(400, 'Missing "path" query parameter')
                return
            try:
                self._send_json(_delete_rules_file(os.getcwd(), rel_path))
            except ValueError as e:
                self._send_error(400, str(e))
            except FileNotFoundError as e:
                self._send_error(404, str(e))
            except RuntimeError as e:
                self._send_error(500, str(e))
        elif path == '/api/prompt/prompt-files/file':
            name = qs.get('name', [None])[0]
            if not name:
                self._send_error(400, 'Missing "name" query parameter')
                return
            try:
                self._send_json(_delete_prompt_file(os.getcwd(), name))
            except ValueError as e:
                self._send_error(400, str(e))
            except FileNotFoundError as e:
                self._send_error(404, str(e))
        elif path == '/api/quick-prompts/item':
            self._handle_quick_prompt_delete()
        else:
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
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
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
