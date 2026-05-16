"""V2WorkflowHandlerMixin — v2 driver subprocess 전용 REST + SSE endpoint.

v1 `/api/v2/wf-event` 단일 endpoint 는 의미별 endpoint 로 분해됨:
  POST /api/v2/sessions                       — 세션 명시 등록 (lazy create 폐기)
  GET  /api/v2/sessions                       — 전체 세션 목록
  GET  /api/v2/sessions/<id>                  — 세션 상세 (step / phase / artifacts / ts)
  GET  /api/v2/sessions/<id>/events           — SSE 구독 (per-session client fan-out)
  POST /api/v2/sessions/<id>/step             — Step 전이 통보 (workflow_step 발화)
  POST /api/v2/sessions/<id>/stdout           — claude -p stdout chunk forward
  POST /api/v2/sessions/<id>/phase            — WORK 내부 phase 통보
  POST /api/v2/sessions/<id>/finish           — 사이클 종결 통보 (DONE / FAILED)
  GET  /api/v2/sessions/<id>/artifacts/<path> — 산출물 파일 read (runs/.../)

ClaudeProcess 의존 0건. v1 workflow.py handler 와 별도.
"""

from __future__ import annotations

import json
import os
import re
import time
from urllib.parse import unquote, urlparse

from .._common import logger
from ..state import v2_workflow_registry


# /api/v2/sessions/<session_id>[/<sub_path>] 매칭
_SESSION_PATH_RE = re.compile(
    r'^/api/v2/sessions/(?P<session_id>[^/]+)(?:/(?P<sub>.+))?$'
)


class V2WorkflowHandlerMixin:
    """v2 driver subprocess 전용 endpoint mixin.

    `BoardHTTPRequestHandler` 가 do_GET / do_POST 라우팅 시 본 mixin 의
    `_handle_v2_*` 메서드를 호출한다.
    """

    # ------------------------------------------------------------------
    # do_GET / do_POST 진입점 — http_router.py 가 호출
    # ------------------------------------------------------------------

    def _v2_dispatch_get(self) -> bool:
        """GET /api/v2/sessions[...] 라우팅. 처리되면 True 반환."""
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/v2/sessions':
            self._v2_handle_sessions_list()
            return True

        match = _SESSION_PATH_RE.match(path)
        if match is None:
            return False

        session_id = unquote(match.group('session_id'))
        sub = match.group('sub')

        if sub is None:
            self._v2_handle_session_detail(session_id)
            return True

        if sub == 'events':
            self._v2_handle_session_events(session_id)
            return True

        if sub.startswith('artifacts/'):
            artifact_rel = sub[len('artifacts/'):]
            self._v2_handle_session_artifact(session_id, artifact_rel)
            return True

        return False

    def _v2_dispatch_post(self) -> bool:
        """POST /api/v2/sessions[...] 라우팅. 처리되면 True 반환."""
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/v2/sessions':
            self._v2_handle_session_create()
            return True

        match = _SESSION_PATH_RE.match(path)
        if match is None:
            return False

        session_id = unquote(match.group('session_id'))
        sub = match.group('sub')

        if sub == 'step':
            self._v2_handle_session_step(session_id)
            return True
        if sub == 'stdout':
            self._v2_handle_session_stdout(session_id)
            return True
        if sub == 'phase':
            self._v2_handle_session_phase(session_id)
            return True
        if sub == 'finish':
            self._v2_handle_session_finish(session_id)
            return True

        return False

    # ------------------------------------------------------------------
    # GET endpoint
    # ------------------------------------------------------------------

    def _v2_handle_sessions_list(self) -> None:
        """GET /api/v2/sessions — 전체 세션 목록 (메타 dict 배열)."""
        self._send_json(v2_workflow_registry.list_all())

    def _v2_handle_session_detail(self, session_id: str) -> None:
        """GET /api/v2/sessions/<id> — 세션 상세 (current_step / phase / artifacts / ts)."""
        session = v2_workflow_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return
        self._send_json({
            'session_id': session.session_id,
            'ticket_id': session.ticket_id,
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

    def _v2_handle_session_events(self, session_id: str) -> None:
        """GET /api/v2/sessions/<id>/events — SSE 구독 (per-session)."""
        session = v2_workflow_registry.get(session_id)
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

    def _v2_handle_session_artifact(self, session_id: str, artifact_rel: str) -> None:
        """GET /api/v2/sessions/<id>/artifacts/<rel> — 산출물 파일 read.

        work_dir 기준 상대 경로. path traversal 방지 (.. 차단).
        """
        session = v2_workflow_registry.get(session_id)
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
        """확장자 기반 content-type 추측."""
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

    def _v2_handle_session_create(self) -> None:
        """POST /api/v2/sessions — 세션 명시 등록.

        본문: {session_id, ticket_id, command, work_dir, worktree_path?}
        동일 session_id 재호출 시 기존 반환 (idempotent).
        """
        data = self._read_json_body()
        if data is None:
            return

        session_id = (data.get('session_id') or '').strip()
        ticket_id = (data.get('ticket_id') or '').strip()
        command = (data.get('command') or '').strip()
        work_dir = (data.get('work_dir') or '').strip()
        worktree_path = (data.get('worktree_path') or '').strip()

        if not session_id or not ticket_id or not command:
            self._send_error(400, 'Missing "session_id" / "ticket_id" / "command"')
            return

        session = v2_workflow_registry.create(
            session_id=session_id,
            ticket_id=ticket_id,
            command=command,
            work_dir=work_dir,
            worktree_path=worktree_path,
        )
        self._send_json({
            'ok': True,
            'session_id': session.session_id,
            'created_at': session.created_at,
        })

    def _v2_handle_session_step(self, session_id: str) -> None:
        """POST /api/v2/sessions/<id>/step — Step 전이.

        본문: {step: NONE|INIT|PLAN|WORK|VALIDATE|REPORT|DONE|FAILED, phase?: str, prev_step?: str}
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

        session = v2_workflow_registry.update_step(session_id, step, phase)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        session.channel.emit_step(step, phase=phase, prev_step=prev_step)
        self._send_json({'ok': True, 'step': step, 'phase': phase})

    def _v2_handle_session_stdout(self, session_id: str) -> None:
        """POST /api/v2/sessions/<id>/stdout — claude -p stdout chunk forward.

        본문: {text: str, raw?: dict}
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

        session = v2_workflow_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        session.channel.emit_stdout(text, raw=raw)
        self._send_json({'ok': True})

    def _v2_handle_session_phase(self, session_id: str) -> None:
        """POST /api/v2/sessions/<id>/phase — WORK 내부 phase 전이.

        본문: {phase: str, action: start|end}
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

        session = v2_workflow_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        if action == 'start':
            v2_workflow_registry.update_step(session_id, session.current_step, phase)
        else:
            v2_workflow_registry.update_step(session_id, session.current_step, '')

        session.channel.emit_phase(phase, action=action)
        self._send_json({'ok': True, 'phase': phase, 'action': action})

    def _v2_handle_session_finish(self, session_id: str) -> None:
        """POST /api/v2/sessions/<id>/finish — 사이클 종결.

        본문: {outcome: ok|fail, summary?: str}
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
        session = v2_workflow_registry.update_step(session_id, terminal_step, '')
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        session.channel.emit_finish(outcome, summary=summary)
        self._send_json({'ok': True, 'outcome': outcome, 'terminal_step': terminal_step})
