"""GenericHandlerMixin — api / poll / sse endpoints."""

from __future__ import annotations

import json
import os
import time

from board.server.runtime.state import sse_manager, poll_tracker
from board.server.support.common import (
    SERVER_STARTED_AT,
    SERVER_PID,
    api_endpoint,
    _parse_env_file,
    _read_kanban_tickets,
    _read_dashboard,
    _get_git_branch,
    _list_memory_files,
    _read_memory_file,
    _list_rules_files,
    _read_rules_file,
    _read_claude_md,
    _read_roadmap,
    _memory_gc_status,
)
from engine.apps.board_api.prompt_store import (
    _list_prompt_files,
    _read_prompt_file,
    _read_quick_prompts,
)


class GenericHandlerMixin:
    """Kanban / dashboard / workflow / memory / rules / prompt API + SSE."""

    def _handle_api_delete(self) -> None:
        """internal helper — not exposed as endpoint.

        T-511 P4 — /api/* DELETE routing dispatcher. 4 DELETE endpoint
        mixin handler method (_handle_memory_delete / _handle_rules_delete /
        Delegate to _handle_prompt_delete / _handle_quick_prompt_delete).

        After abolishing the inline branch of http_router.py do_DELETE, this dispatcher becomes a single
        Routing entry point. The handler method is a query/path parsing + error response delegation pattern.
        preservation.
        """
        from urllib.parse import urlparse
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/memory/file':
            self._handle_memory_delete()
        elif path == '/api/prompt/rules/file':
            self._handle_rules_delete()
        elif path == '/api/prompt/prompt-files/file':
            self._handle_prompt_delete()
        elif path == '/api/quick-prompts/item':
            self._handle_quick_prompt_delete()
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_api(self) -> None:
        """internal helper — not exposed as endpoint.

        /api/* GET routing dispatcher. Each URL → After branching within this method
        inline (call board_data function directly) or delegate to mixin handler (_handle_*).
        """
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        project_root = os.getcwd()

        if path == '/api/env':
            self._send_json(_parse_env_file(project_root))
        elif path == '/api/kanban':
            files_param = qs.get('files', [None])[0]
            files = files_param.split(",") if files_param else None
            self._send_json(_read_kanban_tickets(project_root, files))
        elif path == '/api/dashboard':
            self._send_json(_read_dashboard(project_root))
        # T-513 P2 — Old workflow entries/detail inline branch transferred to KANBAN domain
        # (KanbanHandlerMixin._handle_kanban_workflow_{entries,detail}). This _handle_api
        # An inline branch is dead — http_router do_GET delegates directly.
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
        elif path == '/api/quick-prompts':
            self._send_json(_read_quick_prompts(project_root))
        elif path == '/api/memory/gc/status':
            self._send_json(_memory_gc_status(project_root))
        elif path.startswith('/api/metrics/run/'):
            registry_key = path[len('/api/metrics/run/'):].strip('/')
            self._handle_metrics_run(registry_key)
        elif path == '/api/metrics/aggregate':
            last = self._parse_metrics_last(qs, default=20)
            self._handle_metrics_aggregate(last)
        elif path == '/api/metrics/regression':
            last = self._parse_metrics_last(qs, default=20)
            self._handle_metrics_regression(last)
        elif path == '/api/metrics/launch_latency':
            last = self._parse_metrics_last(qs, default=10)
            self._handle_metrics_launch_latency(last=last)
        elif path == '/api/worktree/uncommitted/all':
            self._handle_worktree_uncommitted_all()
        elif path == '/api/kanban/review-verdict':
            self._handle_kanban_review_verdict()
        elif path == '/api/kanban/audit/verdict':
            self._handle_kanban_audit_verdict()
        elif path == '/api/kanban/done-verdict':
            self._handle_kanban_done_verdict()
        else:
            self.send_response(404)
            self.end_headers()

    @api_endpoint("SYS", "poll")
    def _handle_poll(self) -> None:
        """Handles polling endpoints.

        method: GET
        url: /poll
        domain: SYS
        handler: GenericHandlerMixin._handle_poll
        request: query none
        response_ok: {changes: [str, ...]}
        response_error: n/a (always 200)
        status_codes: 200
        auth: none (local-only)
        side_effects: poll_tracker.flush()
        sse_events: none
        """
        changes = poll_tracker.flush()
        body = json.dumps(changes).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    @api_endpoint("SYS", "sse")
    def _handle_sse(self) -> None:
        """Handles SSE endpoints.

        method: GET
        url: /events
        domain: SYS
        handler: GenericHandlerMixin._handle_sse
        request: query none (long-lived connection)
        response_ok: text/event-stream (kanban_update / workflow_update / dashboard_update / memory_update / roadmap_update / launch / git_branch)
        response_error: n/a (HTTP keep-alive stream)
        status_codes: 200
        auth: none (local-only)
        side_effects: sse_manager.add(self.wfile); heartbeat thread
        sse_events: emit-only channel — see board.md §1.3
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

        sse_manager.add(self.wfile)
        try:
            while True:
                time.sleep(1)
                client_lock = sse_manager.get_lock(self.wfile)
                if client_lock is None:
                    break
                try:
                    with client_lock:
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break
        finally:
            sse_manager.remove(self.wfile)
