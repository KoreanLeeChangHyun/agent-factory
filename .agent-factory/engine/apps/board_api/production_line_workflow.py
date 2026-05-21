"""Production-line workflow REST + SSE endpoint.

Legacy `/api/v2/wf-event` single endpoint is decomposed into semantic endpoints:
  POST /api/v2/sessions — Session explicit registration (lazy create discarded)
  GET /api/v2/sessions — Full session list
  GET /api/v2/sessions/<id> — session details (step / phase / artifacts / ts)
  GET /api/v2/sessions/<id>/events — SSE subscription (per-session client fan-out)
  GET /api/v2/sessions/<id>/history — persist entire NDJSON event (T-513 P1)
  POST /api/v2/sessions/<id>/step — Step transition notification (workflow_step firing)
  POST /api/v2/sessions/<id>/stdout           — claude -p stdout chunk forward
  POST /api/v2/sessions/<id>/phase — WORK internal phase notification
  POST /api/v2/sessions/<id>/finish — cycle termination notification (DONE / FAILED)
  GET /api/v2/sessions/<id>/artifacts/<path> — read artifact file (runs/.../)

0 ClaudeProcess dependencies. Separate from legacy workflow.py handler.
"""

from __future__ import annotations

import json
import os
import re
import time
from urllib.parse import unquote, urlparse

from board.server.support.common import api_endpoint, logger
from board.server.runtime.state import production_line_registry


# /api/v2/sessions/<session_id>[/<sub_path>] matching
_SESSION_PATH_RE = re.compile(
    r'^/api/v2/sessions/(?P<session_id>[^/]+)(?:/(?P<sub>.+))?$'
)


class ProductionLineWorkflowHandlerMixin:
    """Production-line endpoint mixin.

    `BoardHTTPRequestHandler` is used in this mixin when routing do_GET / do_POST.
        Call the `_production_line_handle_*` method. Method names keep public
        `/api/v2/*` HTTP contract stable.
    """

    # ------------------------------------------------------------------
    # do_GET / do_POST entry points — called by http_router.py
    # ------------------------------------------------------------------

    def _production_line_dispatch_get(self) -> bool:
        """internal helper — not exposed as endpoint.

        GET /api/v2/sessions[...] routing. Returns True when processed.
        """
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/v2/sessions':
            self._production_line_handle_sessions_list()
            return True

        match = _SESSION_PATH_RE.match(path)
        if match is None:
            return False

        session_id = unquote(match.group('session_id'))
        sub = match.group('sub')

        if sub is None:
            self._production_line_handle_session_detail(session_id)
            return True

        if sub == 'events':
            self._production_line_handle_session_events(session_id)
            return True

        if sub == 'history':
            self._production_line_handle_session_history(session_id)
            return True

        if sub.startswith('artifacts/'):
            artifact_rel = sub[len('artifacts/'):]
            self._production_line_handle_session_artifact(session_id, artifact_rel)
            return True

        return False

    def _production_line_dispatch_post(self) -> bool:
        """internal helper — not exposed as endpoint.

        POST /api/v2/sessions[...] routing. Returns True when processed.
        """
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/v2/sessions':
            self._production_line_handle_session_create()
            return True

        match = _SESSION_PATH_RE.match(path)
        if match is None:
            return False

        session_id = unquote(match.group('session_id'))
        sub = match.group('sub')

        if sub == 'step':
            self._production_line_handle_session_step(session_id)
            return True
        if sub == 'stdout':
            self._production_line_handle_session_stdout(session_id)
            return True
        if sub == 'phase':
            self._production_line_handle_session_phase(session_id)
            return True
        if sub == 'finish':
            self._production_line_handle_session_finish(session_id)
            return True
        if sub == 'artifacts':
            self._production_line_handle_session_post_artifacts(session_id)
            return True

        return False

    def _production_line_dispatch_delete(self) -> bool:
        """internal helper — not exposed as endpoint.

        DELETE /api/v2/sessions/<id> routing. Returns True when processed.
        """
        parsed = urlparse(self.path)
        path = parsed.path

        match = _SESSION_PATH_RE.match(path)
        if match is None:
            return False

        session_id = unquote(match.group('session_id'))
        sub = match.group('sub')

        # /api/v2/sessions/<id> (sub=None) — Delete session
        if sub is None:
            self._production_line_handle_session_delete(session_id)
            return True

        return False

    def _production_line_dispatch_patch(self) -> bool:
        """internal helper — not exposed as endpoint.

        PATCH /api/v2/sessions/<id>/status routing. Returns True when processed.
        """
        parsed = urlparse(self.path)
        path = parsed.path

        match = _SESSION_PATH_RE.match(path)
        if match is None:
            return False

        session_id = unquote(match.group('session_id'))
        sub = match.group('sub')

        if sub == 'status':
            self._production_line_handle_session_patch_status(session_id)
            return True

        return False

    # ------------------------------------------------------------------
    # GET endpoint
    # ------------------------------------------------------------------

    @api_endpoint("W2", "list")
    def _production_line_handle_sessions_list(self) -> None:
        """GET /api/v2/sessions — Full list of sessions (meta dict array).

        method: GET
        url: /api/v2/sessions
        domain: W2
        handler: ProductionLineWorkflowHandlerMixin._production_line_handle_sessions_list
        request: query none
        response_ok: [{session_id, work_request, command, current_step, ...}]
        response_error: n/a (always 200)
        status_codes: 200
        auth: none (local-only)
        side_effects: read production_line_registry (in-memory snapshot)
        sse_events: none
        """
        self._send_json(production_line_registry.list_all())

    @api_endpoint("W2", "detail")
    def _production_line_handle_session_detail(self, session_id: str) -> None:
        """GET /api/v2/sessions/<id> — Session details (current_step / phase / artifacts / ts).

        method: GET
        url: /api/v2/sessions/<id>
        domain: W2
        handler: ProductionLineWorkflowHandlerMixin._production_line_handle_session_detail
        request: path {session_id: str}
        response_ok: {session_id, work_request, command, current_step, current_phase, artifacts, ts}
        response_error: {ok: false, error: str}
        status_codes: 200, 404
        auth: none (local-only)
        side_effects: read production_line_registry
        sse_events: none
        """
        session = production_line_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return
        self._send_json({
            'session_id': session.session_id,
            'work_request': session.work_request,
            'command': session.command,
            'work_dir': session.work_dir,
            'worktree_path': session.worktree_path,
            'status': session.status,
            'current_step': session.current_step,
            'current_phase': session.current_phase,
            'cycle_start_ts': session.cycle_start_ts,
            'step_ts': session.step_ts,
            'artifacts': session.artifacts,
            'created_at': session.created_at,
        })

    @api_endpoint("W2", "events")
    def _production_line_handle_session_events(self, session_id: str) -> None:
        """GET /api/v2/sessions/<id>/events — SSE subscription (per-session).

        method: GET
        url: /api/v2/sessions/<id>/events
        domain: W2
        handler: ProductionLineWorkflowHandlerMixin._production_line_handle_session_events
        request: path {session_id: str}
        response_ok: text/event-stream (workflow_step / workflow_stdout / workflow_phase / workflow_finish)
        response_error: 404 (session not found)
        status_codes: 200, 404
        auth: none (local-only)
        side_effects: register self.wfile to session.channel
        sse_events: ProductionLineSSEChannel events (board.md §1.2)
        """
        session = production_line_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        try:
            self.wfile.write(b': connected\n\n')
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

        session.channel.add(self.wfile)
        try:
            while True:
                time.sleep(0.25)
                client_lock = session.channel.get_lock(self.wfile)
                if client_lock is None:
                    break
                try:
                    with client_lock:
                        self.wfile.write(b': heartbeat\n\n')
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break
        finally:
            session.channel.remove(self.wfile)

    @api_endpoint("W2", "history")
    def _production_line_handle_session_history(self, session_id: str) -> None:
        """GET /api/v2/sessions/<id>/history — Returns the entire persist NDJSON event.

        T-513 P1 — Decision point #2 Adopted, REST history V2 endpoint newly established. When reconnecting
        Past events are loaded in batches before the client registers for live SSE. SSE replay
        Use ringbuffer
        adjustment).

        method: GET
        url: /api/v2/sessions/<id>/history
        domain: W2
        handler: ProductionLineWorkflowHandlerMixin._production_line_handle_session_history
        request: path {session_id: str}
        response_ok: {session_id, total_count, events: [{ts, event, payload}]}
        response_error: {ok: false, error: str}
        status_codes: 200, 404
        auth: none (local-only)
        side_effects: read NDJSON persist file (no registry mutation)
        sse_events: none
        """
        session = production_line_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        persist_path = session.channel.persist_path
        events: list = []
        if persist_path and os.path.isfile(persist_path):
            try:
                with open(persist_path, 'r', encoding='utf-8') as f:
                    for raw_line in f:
                        line = raw_line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        # Skip the _meta line (first line) — return only events
                        if isinstance(rec, dict) and '_meta' in rec:
                            continue
                        events.append(rec)
            except OSError as exc:
                logger.error(
                    'production-line history read failed (%s): %s', persist_path, exc,
                )
                # graceful — returns empty events

        self._send_json({
            'session_id': session_id,
            'total_count': len(events),
            'events': events,
        })

    @api_endpoint("W2", "artifact_get")
    def _production_line_handle_session_artifact(self, session_id: str, artifact_rel: str) -> None:
        """GET /api/v2/sessions/<id>/artifacts/<rel> — Read artifact files.

        Relative path based on work_dir. Prevent path traversal (..block).

        method: GET
        url: /api/v2/sessions/<id>/artifacts/<rel>
        domain: W2
        handler: ProductionLineWorkflowHandlerMixin._production_line_handle_session_artifact
        request: path {session_id, artifact_rel}
        response_ok: file content (Content-Type by extension)
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 404, 500
        auth: none (local-only)
        side_effects: read from work_dir filesystem
        sse_events: none
        """
        session = production_line_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        if '..' in artifact_rel.split('/'):
            self._send_error(400, 'Invalid artifact path (.. blocked)')
            return

        if not session.work_dir:
            self._send_error(404, 'Session has no work_dir')
            return

        target = os.path.normpath(os.path.join(session.work_dir, artifact_rel))
        work_dir_norm = os.path.normpath(session.work_dir)
        if not target.startswith(work_dir_norm + os.sep) and target != work_dir_norm:
            self._send_error(400, 'Artifact path escapes work_dir')
            return

        if not os.path.isfile(target):
            self._send_error(404, f'Artifact not found: {artifact_rel}')
            return

        try:
            with open(target, 'rb') as f:
                body = f.read()
        except OSError as exc:
            self._send_error(500, f'Read failed: {exc}')
            return

        content_type = self._guess_content_type(artifact_rel)
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _guess_content_type(rel_path: str) -> str:
        """internal helper — not exposed as endpoint.

        Extension-based content-type guessing.
        """
        lower = rel_path.lower()
        if lower.endswith('.md'):
            return 'text/markdown; charset=utf-8'
        if lower.endswith('.json'):
            return 'application/json; charset=utf-8'
        if lower.endswith('.jsonl'):
            return 'application/x-ndjson; charset=utf-8'
        if lower.endswith('.log') or lower.endswith('.txt'):
            return 'text/plain; charset=utf-8'
        return 'application/octet-stream'

    # ------------------------------------------------------------------
    # POST endpoint
    # ------------------------------------------------------------------

    @api_endpoint("W2", "create")
    def _production_line_handle_session_create(self) -> None:
        """POST /api/v2/sessions — Register a session explicitly.

        Body: {session_id, work_request, command, work_dir, worktree_path?}
        When re-invoking the same session_id, the original is returned (idempotent).

        method: POST
        url: /api/v2/sessions
        domain: W2
        handler: ProductionLineWorkflowHandlerMixin._production_line_handle_session_create
        request: body {session_id, work_request, command, work_dir, worktree_path?}
        response_ok: {ok: true, session_id, created_at}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 403
        auth: none (local-only) — naming guard rejects fake/test session_id (403)
        side_effects: production_line_registry.create + new ProductionLineSession instance
        sse_events: none (subsequent step/stdout/phase/finish events emit via per-session channel)
        """
        data = self._read_json_body()
        if data is None:
            return

        session_id = (data.get('session_id') or '').strip()
        work_request = (data.get('work_request') or '').strip()
        command = (data.get('command') or '').strip()
        work_dir = (data.get('work_dir') or '').strip()
        worktree_path = (data.get('worktree_path') or '').strip()

        if not session_id or not work_request or not command:
            self._send_error(400, 'Missing "session_id" / "work_request" / "command"')
            return

        try:
            session = production_line_registry.create(
                session_id=session_id,
                work_request=work_request,
                command=command,
                work_dir=work_dir,
                worktree_path=worktree_path,
            )
        except ValueError as exc:
            # Block fake/test session_id pattern (block T-495 production endpoint contamination regression)
            self._send_error(403, str(exc))
            return
        self._send_json({
            'ok': True,
            'session_id': session.session_id,
            'created_at': session.created_at,
        })

    @api_endpoint("W2", "step")
    def _production_line_handle_session_step(self, session_id: str) -> None:
        """POST /api/v2/sessions/<id>/step — Step transition.

        Body: {step: NONE|INIT|PLAN|WORK|VALIDATE|REPORT|DONE|FAILED, phase?: str, prev_step?: str}

        method: POST
        url: /api/v2/sessions/<id>/step
        domain: W2
        handler: ProductionLineWorkflowHandlerMixin._production_line_handle_session_step
        request: body {step: str, phase?: str, prev_step?: str, ...extras}
        response_ok: {ok: true, step, phase}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 404
        auth: none (local-only) — driver subprocess only
        side_effects: production_line_registry.update_step + session.channel.emit_step
        sse_events: workflow_step (ProductionLineSSEChannel)
        """
        data = self._read_json_body()
        if data is None:
            return

        step = (data.get('step') or '').strip().upper()
        phase = (data.get('phase') or '').strip()
        prev_step = (data.get('prev_step') or '').strip().upper()
        if not step:
            self._send_error(400, 'Missing "step"')
            return

        session = production_line_registry.update_step(session_id, step, phase)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        # T-495 P3 — Pass forward-compatible extras (verdict/commit/retry, etc.)
        extras = self._production_line_collect_extras(data, exclude={'step', 'phase', 'prev_step'})
        session.channel.emit_step(step, phase=phase, prev_step=prev_step, extras=extras)
        self._send_json({'ok': True, 'step': step, 'phase': phase})

    @api_endpoint("W2", "stdout")
    def _production_line_handle_session_stdout(self, session_id: str) -> None:
        """POST /api/v2/sessions/<id>/stdout — claude -p stdout chunk forward.

        Body: {text: str, raw?: dict}

        method: POST
        url: /api/v2/sessions/<id>/stdout
        domain: W2
        handler: ProductionLineWorkflowHandlerMixin._production_line_handle_session_stdout
        request: body {text: str, raw?: dict}
        response_ok: {ok: true}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 404
        auth: none (local-only) — driver subprocess only
        side_effects: session.channel.emit_stdout (broadcast to per-session SSE clients)
        sse_events: workflow_stdout (ProductionLineSSEChannel)
        """
        data = self._read_json_body()
        if data is None:
            return

        text = data.get('text', '')
        raw = data.get('raw')
        if not isinstance(text, str):
            self._send_error(400, '"text" must be a string')
            return
        if raw is not None and not isinstance(raw, dict):
            self._send_error(400, '"raw" must be a dict')
            return

        session = production_line_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        session.channel.emit_stdout(text, raw=raw)
        self._send_json({'ok': True})

    @api_endpoint("W2", "phase")
    def _production_line_handle_session_phase(self, session_id: str) -> None:
        """POST /api/v2/sessions/<id>/phase — WORK internal phase transition.

        Body: {phase: str, action: start|end}

        method: POST
        url: /api/v2/sessions/<id>/phase
        domain: W2
        handler: ProductionLineWorkflowHandlerMixin._production_line_handle_session_phase
        request: body {phase: str, action: start|end, ...extras}
        response_ok: {ok: true, phase, action}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 404
        auth: none (local-only) — driver subprocess only
        side_effects: production_line_registry.update_step (phase update) + session.channel.emit_phase
        sse_events: workflow_phase (ProductionLineSSEChannel)
        """
        data = self._read_json_body()
        if data is None:
            return

        phase = (data.get('phase') or '').strip()
        action = (data.get('action') or 'start').strip().lower()
        if not phase:
            self._send_error(400, 'Missing "phase"')
            return
        if action not in ('start', 'end'):
            self._send_error(400, '"action" must be start|end')
            return

        session = production_line_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        if action == 'start':
            production_line_registry.update_step(session_id, session.current_step, phase)
        else:
            production_line_registry.update_step(session_id, session.current_step, '')

        # T-495 P3 — forward-compatible extras
        extras = self._production_line_collect_extras(data, exclude={'phase', 'action'})
        session.channel.emit_phase(phase, action=action, extras=extras)
        self._send_json({'ok': True, 'phase': phase, 'action': action})

    @api_endpoint("W2", "finish")
    def _production_line_handle_session_finish(self, session_id: str) -> None:
        """POST /api/v2/sessions/<id>/finish — End cycle.

        Body: {outcome: ok|fail, summary?: str}

        method: POST
        url: /api/v2/sessions/<id>/finish
        domain: W2
        handler: ProductionLineWorkflowHandlerMixin._production_line_handle_session_finish
        request: body {outcome: ok|fail, summary?: str, ...extras}
        response_ok: {ok: true, outcome, terminal_step}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 404
        auth: none (local-only) — driver subprocess only
        side_effects: production_line_registry.update_step (terminal DONE|FAILED) + session.channel.emit_finish
        sse_events: workflow_finish (ProductionLineSSEChannel)
        """
        data = self._read_json_body()
        if data is None:
            return

        outcome = (data.get('outcome') or '').strip().lower()
        summary = data.get('summary', '')
        if outcome not in ('ok', 'fail'):
            self._send_error(400, '"outcome" must be ok|fail')
            return
        if not isinstance(summary, str):
            self._send_error(400, '"summary" must be a string')
            return

        terminal_step = 'DONE' if outcome == 'ok' else 'FAILED'
        session = production_line_registry.update_step(session_id, terminal_step, '')
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        # T-495 P3 — forward-compatible extras (verdict/commit/retry)
        extras = self._production_line_collect_extras(data, exclude={'outcome', 'summary'})
        session.channel.emit_finish(outcome, summary=summary, extras=extras)
        self._send_json({'ok': True, 'outcome': outcome, 'terminal_step': terminal_step})

    @staticmethod
    def _production_line_collect_extras(data: dict, exclude: set[str]) -> dict | None:
        """internal helper — not exposed as endpoint.

        T-495 P3 — frontend forward-compatible meta key extraction.

        Fixed key of body (step/phase/prev_step/outcome/summary/action), etc.
        All keys are summarized as extras. driver has verdict/commit_hash/retry/regression
        If you send it, it passes straight through to the SSE payload.
        """
        if not isinstance(data, dict):
            return None
        extras = {k: v for k, v in data.items() if k not in exclude}
        return extras or None

    # ------------------------------------------------------------------
    # T-511 P4 — DELETE / PATCH / POST artifacts (3 new endpoints)
    # ------------------------------------------------------------------

    @api_endpoint("W2", "delete")
    def _production_line_handle_session_delete(self, session_id: str) -> None:
        """DELETE /api/v2/sessions/<id> — Force kill session + dispose of work_dir.

        This endpoint is for debug/recovery. Recommended to use only user-specified calls.
        The work_dir directory can also be deleted with the force query parameter.

        method: DELETE
        url: /api/v2/sessions/<id>
        domain: W2
        handler: ProductionLineWorkflowHandlerMixin._production_line_handle_session_delete
        request: query {force?: 1|0}
        response_ok: {ok: true, session_id, removed: bool, work_dir_removed: bool}
        response_error: {ok: false, error: str}
        status_codes: 200, 404, 500
        auth: none (local-only) — debug/recovery use
        side_effects: production_line_registry.purge + optional work_dir rmtree
        sse_events: none (channel closed on session purge)
        """
        session = production_line_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        # When force=1, the work_dir directory is also deleted.
        force_raw = self._parse_query_param('force')
        force = force_raw in ('1', 'true', 'True')

        work_dir = session.work_dir
        work_dir_removed = False
        if force and work_dir and os.path.isdir(work_dir):
            try:
                import shutil
                shutil.rmtree(work_dir)
                work_dir_removed = True
            except OSError as exc:
                logger.error('production-line session delete: rmtree %s failed: %s', work_dir, exc)
                self._send_error(500, f'rmtree failed: {exc}')
                return

        removed = production_line_registry.purge(session_id) if hasattr(
            production_line_registry, 'purge'
        ) else production_line_registry.remove(session_id)

        self._send_json({
            'ok': True,
            'session_id': session_id,
            'removed': bool(removed),
            'work_dir_removed': work_dir_removed,
        })

    @api_endpoint("W2", "patch_status")
    def _production_line_handle_session_patch_status(self, session_id: str) -> None:
        """PATCH /api/v2/sessions/<id>/status — Force step/phase update.

        For debug/recovery. After the driver terminates abnormally, the user may manually correct the
        Used when an external tool forcibly moves the session state to another step.

        method: PATCH
        url: /api/v2/sessions/<id>/status
        domain: W2
        handler: ProductionLineWorkflowHandlerMixin._production_line_handle_session_patch_status
        request: body {step?: str, phase?: str}
        response_ok: {ok: true, session_id, step, phase}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 404
        auth: none (local-only) — debug/recovery use
        side_effects: production_line_registry.update_step (no SSE emit)
        sse_events: none (silent patch — user manual correction path)
        """
        data = self._read_json_body()
        if data is None:
            return

        session = production_line_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        step = (data.get('step') or session.current_step or '').strip().upper()
        phase = data.get('phase')
        if phase is None:
            phase = session.current_phase or ''
        if not isinstance(phase, str):
            self._send_error(400, '"phase" must be a string')
            return

        if not step:
            self._send_error(400, 'Missing "step" (current_step is also empty)')
            return

        updated = production_line_registry.update_step(session_id, step, phase)
        if updated is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        self._send_json({
            'ok': True,
            'session_id': session_id,
            'step': step,
            'phase': phase,
        })

    @api_endpoint("W2", "post_artifacts")
    def _production_line_handle_session_post_artifacts(self, session_id: str) -> None:
        """POST /api/v2/sessions/<id>/artifacts — Force injection of artifacts.

        Path where external tools can force-inject output files into work_dir.
        This endpoint is for retry/manual calibration. Block path traversal.

        method: POST
        url: /api/v2/sessions/<id>/artifacts
        domain: W2
        handler: ProductionLineWorkflowHandlerMixin._production_line_handle_session_post_artifacts
        request: body {path: str (relative), content: str}
        response_ok: {ok: true, session_id, path, bytes_written: int}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 404, 500
        auth: none (local-only) — recovery use
        side_effects: write file under session.work_dir (path traversal blocked)
        sse_events: none
        """
        data = self._read_json_body()
        if data is None:
            return

        session = production_line_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        rel_path = (data.get('path') or '').strip()
        content = data.get('content', '')
        if not rel_path:
            self._send_error(400, 'Missing "path"')
            return
        if not isinstance(content, str):
            self._send_error(400, '"content" must be a string')
            return
        if '..' in rel_path.split('/') or rel_path.startswith('/'):
            self._send_error(400, 'Invalid path (.. or absolute blocked)')
            return

        if not session.work_dir:
            self._send_error(400, 'Session has no work_dir')
            return

        target = os.path.normpath(os.path.join(session.work_dir, rel_path))
        work_dir_norm = os.path.normpath(session.work_dir)
        if not target.startswith(work_dir_norm + os.sep) and target != work_dir_norm:
            self._send_error(400, 'Artifact path escapes work_dir')
            return

        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, 'w', encoding='utf-8') as f:
                f.write(content)
        except OSError as exc:
            logger.error('production-line artifact write failed: %s', exc)
            self._send_error(500, f'Write failed: {exc}')
            return

        # Update session.artifacts metadata (if any)
        try:
            if hasattr(session, 'artifacts') and isinstance(session.artifacts, dict):
                session.artifacts[rel_path] = {
                    'size': len(content.encode('utf-8')),
                    'updated_at': time.time(),
                }
        except Exception:  # noqa: BLE001 — metadata failure causes endpoint itself to fail
            pass

        self._send_json({
            'ok': True,
            'session_id': session_id,
            'path': rel_path,
            'bytes_written': len(content.encode('utf-8')),
        })


ProductionLineWorkflowHandlerMixin = ProductionLineWorkflowHandlerMixin
