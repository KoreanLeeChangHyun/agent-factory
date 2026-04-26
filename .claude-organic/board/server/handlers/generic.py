"""GenericHandlerMixin — api / poll / sse endpoints."""

from __future__ import annotations

import json
import os
import time

from ..state import sse_manager, poll_tracker
from .._common import (
    SERVER_STARTED_AT,
    SERVER_PID,
    _parse_env_file,
    _read_kanban_tickets,
    _read_dashboard,
    _list_workflow_entries,
    _get_git_branch,
    _workflow_detail,
    _resolve_memory_dir,
    _list_memory_files,
    _read_memory_file,
    _list_rules_files,
    _read_rules_file,
    _list_prompt_files,
    _read_prompt_file,
    _read_claude_md,
    _read_roadmap,
    _memory_gc_status,
    _memory_gc_run,
    _memory_gc_prune_archive,
    logger,
)


class GenericHandlerMixin:
    """Kanban / dashboard / workflow / memory / rules / prompt API + SSE."""

    def _handle_api(self) -> None:
        """API 요청을 라우팅한다."""
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        project_root = os.getcwd()

        if path == '/api/env':
            self._send_json(_parse_env_file(project_root))
        elif path == '/api/kanban':
            files_param = qs.get('files', [None])[0]
            files = files_param.split(',') if files_param else None
            self._send_json(_read_kanban_tickets(project_root, files))
        elif path == '/api/dashboard':
            self._send_json(_read_dashboard(project_root))
        elif path == '/api/workflow/entries':
            self._send_json(_list_workflow_entries(project_root))
        elif path == '/api/workflow/detail':
            entry = qs.get('entry', [None])[0]
            if not entry:
                self._send_json([])
                return
            self._send_json(_workflow_detail(project_root, entry))
        elif path == '/api/server-info':
            self._send_json({
                'pid': SERVER_PID,
                'started_at': SERVER_STARTED_AT,
            })
        elif path == '/api/branch':
            self._send_json({'branch': _get_git_branch(project_root)})
        elif path == '/api/roadmap':
            self._send_json(_read_roadmap(project_root))
        elif path == '/api/workflow/artifact':
            self._handle_workflow_artifact(qs)
        elif path == '/api/memory':
            self._send_json(_list_memory_files(project_root))
        elif path == '/api/memory/file':
            name = qs.get('name', [None])[0]
            if not name:
                self._send_error(400, 'Missing "name" query parameter')
                return
            try:
                self._send_json(_read_memory_file(project_root, name))
            except ValueError as e:
                self._send_error(400, str(e))
            except FileNotFoundError as e:
                self._send_error(404, str(e))
        elif path == '/api/prompt/rules':
            self._send_json(_list_rules_files(project_root))
        elif path == '/api/prompt/rules/file':
            rel_path = qs.get('path', [None])[0]
            if not rel_path:
                self._send_error(400, 'Missing "path" query parameter')
                return
            try:
                self._send_json(_read_rules_file(project_root, rel_path))
            except ValueError as e:
                self._send_error(400, str(e))
            except FileNotFoundError as e:
                self._send_error(404, str(e))
        elif path == '/api/prompt/prompt-files':
            self._send_json(_list_prompt_files(project_root))
        elif path == '/api/prompt/prompt-files/file':
            name = qs.get('name', [None])[0]
            if not name:
                self._send_error(400, 'Missing "name" query parameter')
                return
            try:
                self._send_json(_read_prompt_file(project_root, name))
            except ValueError as e:
                self._send_error(400, str(e))
            except FileNotFoundError as e:
                self._send_error(404, str(e))
        elif path == '/api/prompt/claude-md':
            try:
                self._send_json(_read_claude_md(project_root))
            except FileNotFoundError as e:
                self._send_error(404, str(e))
        elif path == '/api/memory/gc/status':
            self._send_json(_memory_gc_status(project_root))
        else:
            self.send_response(404)
            self.end_headers()

    # ---------------- Memory GC POST handlers ----------------

    def _handle_memory_gc_run(self) -> None:
        """POST /api/memory/gc/run — body {"dry_run": bool, "with_reflection": bool}"""
        data = self._read_json_body() or {}
        dry_run = bool(data.get('dry_run', False))
        with_reflection = bool(data.get('with_reflection', False))
        result = _memory_gc_run(
            os.getcwd(), dry_run=dry_run, with_reflection=with_reflection,
        )
        self._send_json(result)

    def _handle_memory_gc_prune(self) -> None:
        """POST /api/memory/gc/prune-archive — body {"apply": bool}"""
        data = self._read_json_body() or {}
        apply = bool(data.get('apply', False))
        result = _memory_gc_prune_archive(os.getcwd(), apply=apply)
        self._send_json(result)

    def _handle_poll(self) -> None:
        """폴링 엔드포인트를 처리한다.

        마지막 폴링 이후 변경된 이벤트 타입 목록을 JSON으로 응답한다.
        """
        changes = poll_tracker.flush()
        body = json.dumps(changes).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _handle_sse(self) -> None:
        """SSE 엔드포인트를 처리한다.

        연결을 유지하며 FileWatcher의 이벤트를 클라이언트에 스트리밍한다.
        """
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # 연결 확인용 초기 주석 전송
        try:
            self.wfile.write(b': connected\n\n')
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

        sse_manager.add(self.wfile)
        try:
            # 연결이 유지되는 동안 대기
            while True:
                time.sleep(1)
                # keep-alive 주석 전송으로 연결 상태 확인
                client_lock = sse_manager.get_lock(self.wfile)
                if client_lock is None:
                    break
                try:
                    with client_lock:
                        self.wfile.write(b': heartbeat\n\n')
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break
        finally:
            sse_manager.remove(self.wfile)
