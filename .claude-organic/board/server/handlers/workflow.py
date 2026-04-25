"""WorkflowHandlerMixin — /workflow/* endpoints."""

from __future__ import annotations

import json
import os
import time
import uuid

from ..state import workflow_registry
from .._common import logger
from ..event_filter import is_user_visible
from ..terminal_channel import _resolve_last_event_id, TerminalSSEChannel
from ..claude_process import _validate_images

# REST history 전용 throwaway 채널. _classify_event / _build_payload 는
# 인스턴스 state 를 사용하지 않으므로 단일 인스턴스 재사용 가능.
_REST_CLASSIFIER = TerminalSSEChannel()


class WorkflowHandlerMixin:
    """Workflow session HTTP endpoints."""

    def _handle_workflow_start(self) -> None:
        """워크플로우 세션 시작 엔드포인트를 처리한다.

        POST /terminal/workflow/start
        요청 본문: {"ticket": "T-NNN", "command": "implement", "work_dir": "/path/..."}

        워크플로우 레지스트리에 새 세션을 생성하고, Claude CLI 프로세스를 시작한다.
        프로세스 환경변수에 _WF_SESSION_TYPE, _WF_TICKET_ID, _WF_SESSION_ID,
        _WF_SERVER_PORT를 주입한다.
        """
        data = self._read_json_body()
        if data is None:
            return

        ticket = data.get('ticket', '')
        command = data.get('command', '')
        work_dir = data.get('work_dir', '')

        if not ticket:
            self._send_error(400, 'Missing "ticket" field')
            return
        if not command:
            self._send_error(400, 'Missing "command" field')
            return

        session = workflow_registry.create(ticket, command, work_dir)

        # 서버 포트 추출
        server_port = str(self.server.server_address[1])

        env_extras = {
            '_WF_SESSION_TYPE': 'workflow',
            '_WF_TICKET_ID': ticket,
            '_WF_SESSION_ID': session.session_id,
            '_WF_SERVER_PORT': server_port,
        }

        # 워크플로우 세션은 bypassPermissions 모드 유지 (블로킹 방지)
        spawn_result = session.process.spawn(
            extra_args=['--permission-mode', 'bypassPermissions'],
            env_extras=env_extras,
        )

        if not spawn_result.get('ok'):
            # 프로세스 시작 실패 시 레지스트리에서 제거
            workflow_registry.remove(session.session_id)
            self._send_error(500, spawn_result.get('error', 'Failed to start process'))
            return

        # CLI 초기화 완료까지 대기 (spawn 후 init 이벤트 수신 전 명령 유실 방지)
        if not session.process._init_event.wait(timeout=10):
            logger.warning("spawn init timeout after 10s, proceeding anyway")

        # launcher가 전달한 command를 세션에 자동 주입
        if command:
            session.process.send_input(command)

        self._send_json({
            'ok': True,
            'session_id': session.session_id,
        })

    def _handle_workflow_kill(self) -> None:
        """워크플로우 세션 프로세스를 종료한다. (세션 메타와 SSE 이력은 유지)

        POST /terminal/workflow/kill
        요청 본문: {"session_id": "wf-T-NNN-..."}
        선택 필드: "purge": true → 세션 메타까지 레지스트리에서 완전히 제거

        기본 동작: 프로세스만 kill, 세션/채널은 레지스트리에 남겨 SSE 재접속 시
        이력 재생이 가능하도록 유지한다. 명시적 purge 요청 시에만 완전 제거한다.
        """
        data = self._read_json_body()
        if data is None:
            return

        session_id = data.get('session_id', '')
        purge = bool(data.get('purge', False))
        if not session_id:
            self._send_error(400, 'Missing "session_id" field')
            return

        session = workflow_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        session.process.kill()
        if purge:
            workflow_registry.purge(session_id)

        self._send_json({'ok': True, 'purged': purge})

    def _handle_workflow_input(self) -> None:
        """워크플로우 세션 입력 전송 엔드포인트를 처리한다.

        POST /terminal/workflow/input
        요청 본문: {"session_id": "wf-T-NNN-...", "text": "사용자 메시지"}

        지정된 세션의 Claude CLI 프로세스에 사용자 메시지를 전송한다.
        """
        data = self._read_json_body()
        if data is None:
            return

        session_id = data.get('session_id', '')
        if not session_id:
            self._send_error(400, 'Missing "session_id" field')
            return

        text = data.get('text', '')
        images = data.get('images', None)

        if not text and not images:
            self._send_error(400, 'Missing "text" field')
            return

        if images is not None:
            validation_error = _validate_images(images)
            if validation_error:
                self._send_error(400, validation_error)
                return

        session = workflow_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        # 사용자 입력을 SSE 히스토리에 기록 (텍스트만, 이미지 base64 제외)
        if text:
            session.channel.broadcast(
                {'type': 'user_input', 'text': text}
            )

        result = session.process.send_input(text, images=images)
        self._send_json(result)

    def _handle_workflow_status(self) -> None:
        """워크플로우 세션 상태 조회 엔드포인트를 처리한다.

        GET /terminal/workflow/status?session_id=wf-T-NNN-...

        지정된 세션의 프로세스 상태와 메타데이터를 JSON으로 응답한다.
        registry에 없어도 .jsonl 아카이브가 있으면 archived 상태로 응답한다.
        """
        session_id = self._parse_query_param('session_id')
        if not session_id:
            self._send_error(400, 'Missing "session_id" query parameter')
            return

        session = workflow_registry.get(session_id)
        archived = False
        if session is None:
            session = workflow_registry.load_archived(session_id)
            if session is None:
                self._send_error(404, f'Session not found: {session_id}')
                return
            archived = True

        self._send_json({
            'session_id': session.session_id,
            'ticket_id': session.ticket_id,
            'command': session.command,
            'work_dir': session.work_dir,
            'status': 'archived' if archived else session.process.status,
            'archived': archived,
            'created_at': session.created_at,
            'clients': 0 if archived else session.channel.client_count,
            'current_step': session.current_step,
            'last_artifact': session.last_artifact,
        })

    def _handle_workflow_sse(self) -> None:
        """워크플로우 세션 전용 SSE 엔드포인트를 처리한다.

        GET /terminal/workflow/events?session_id=wf-T-NNN-...

        지정된 세션의 TerminalSSEChannel로부터 Claude CLI stdout 이벤트를
        클라이언트에 스트리밍한다. 기존 /terminal/events SSE와 동일한 패턴을 사용하되,
        세션별 독립 채널을 통해 멀티플렉싱한다. registry에 없지만 .jsonl 아카이브가
        있는 경우 히스토리를 일회성으로 재생한 후 아카이브 종료 시그널로 스트림을 닫는다.
        """
        session_id = self._parse_query_param('session_id')
        if not session_id:
            self._send_error(400, 'Missing "session_id" query parameter')
            return

        session = workflow_registry.get(session_id)
        if session is None:
            archived_session = workflow_registry.load_archived(session_id)
            if archived_session is None:
                self._send_error(404, f'Session not found: {session_id}')
                return
            self._stream_archived_session(archived_session)
            return

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

        # 재접속 시 last_event_id로 중복 재생 방지 (헤더 + 쿼리 파라미터)
        last_event_id = _resolve_last_event_id(self.headers, self.path)
        session.channel.add(self.wfile, last_event_id=last_event_id)
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

    def _stream_archived_session(self, session: 'WorkflowSession') -> None:
        """아카이브 세션의 히스토리를 일회성 재생 후 스트림을 종료한다.

        persist .jsonl 파일이 남은 세션에 대해 last_event_id 이후의 이벤트만
        재생하고, 완료 시그널(archived_end)을 전송한 후 연결을 닫는다.
        클라이언트는 아카이브 종료 시그널을 받아 재연결 루프를 멈춘다.
        """
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'close')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        last_event_id = _resolve_last_event_id(self.headers, self.path)
        try:
            self.wfile.write(b': archived\n\n')
            self.wfile.flush()
            session.channel.add(self.wfile, last_event_id=last_event_id)
            payload = json.dumps({'archived': True, 'session_id': session.session_id}, ensure_ascii=False)
            self.wfile.write(
                f'event: archived_end\ndata: {payload}\n\n'.encode('utf-8')
            )
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            session.channel.remove(self.wfile)

    def _handle_workflow_list(self) -> None:
        """워크플로우 세션 목록 조회 엔드포인트를 처리한다.

        GET /terminal/workflow/list

        현재 레지스트리에 등록된 모든 워크플로우 세션의 메타데이터를
        JSON 배열로 응답한다.
        """
        self._send_json(workflow_registry.list_all())

    def _handle_workflow_step_update(self) -> None:
        """워크플로우 단계 전이를 통보받아 SSE 이벤트를 발행한다.

        POST /terminal/workflow/step
        요청 본문: {"session_id": "wf-T-NNN-...", "step": "plan"|"work"|...}
        선택 필드: "detail": {...} (phase, mode 등 추가 정보)
        """
        data = self._read_json_body()
        if data is None:
            return

        session_id = data.get('session_id', '').strip()
        step = data.get('step', '').strip()
        if not session_id or not step:
            self._send_error(400, 'Missing "session_id" or "step"')
            return

        session = workflow_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        detail = data.get('detail') or {}
        detail['trigger'] = 'api'
        session.current_step = step
        session.channel.emit_step(step, detail)
        self._send_json({'ok': True, 'step': step})

    def _handle_workflow_history(self) -> None:
        """워크플로우 세션 전체 이벤트 이력을 JSON으로 반환한다.

        GET /terminal/workflow/history?session_id=wf-T-NNN-...

        레지스트리에 등록된 세션이면 persist_path, 없으면 archived 복원 경로로
        jsonl 파일을 읽어 이벤트 배열로 변환한다. _meta 첫 줄은 skip하고,
        나머지 줄을 {seq, event, data} 형태로 반환한다. 파싱 실패 라인은
        logger.error 기록 후 skip (전체 실패로 확장 금지).

        응답:
            {"session_id": ..., "total_count": N, "events": [{seq, event, data}, ...]}
        """
        session_id = self._parse_query_param('session_id')
        if not session_id:
            self._send_error(400, 'Missing "session_id" query parameter')
            return

        # jsonl 파일 경로 결정: 등록 세션 우선, 없으면 archived 경로
        jsonl_path: str | None = None

        session = workflow_registry.get(session_id)
        if session is not None:
            # 활성 세션: channel의 persist_path 사용
            jsonl_path = session.channel._persist_path
        else:
            # archived 세션: registry의 _session_file 경로 직접 사용
            candidate = workflow_registry._session_file(session_id)
            if candidate and os.path.exists(candidate):
                jsonl_path = candidate

        if not jsonl_path or not os.path.exists(jsonl_path):
            self._send_error(404, f'Session not found: {session_id}')
            return

        events: list[dict] = []
        seq = 0
        try:
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError as exc:
                        logger.error(
                            "workflow_history[%s]: jsonl 파싱 실패 (seq=%d): %s — %r",
                            session_id, seq, exc, line[:120],
                        )
                        seq += 1
                        continue

                    # _meta 첫 줄 skip
                    if '_meta' in obj:
                        continue

                    # 사용자 가시성 정책 적용 (isMeta 등 제외)
                    if not is_user_visible(obj):
                        continue

                    # workflow_step 은 _classify_event 매핑 밖 — 직접 처리
                    obj_type = obj.get('type', '')
                    if obj_type == 'workflow_step':
                        event_type = 'workflow_step'
                        data_field = {k: v for k, v in obj.items() if k != 'type'}
                    else:
                        # SSE live 경로와 동일하게 이벤트 분류 + payload 빌드
                        event_type = _REST_CLASSIFIER._classify_event(obj)
                        data_field = _REST_CLASSIFIER._build_payload(obj, event_type)

                    events.append({
                        'seq': seq,
                        'event': event_type,
                        'data': data_field,
                    })
                    seq += 1
        except OSError as exc:
            logger.error(
                "workflow_history[%s]: jsonl 파일 읽기 실패 (%s): %s",
                session_id, jsonl_path, exc,
            )
            self._send_error(500, f'Failed to read session history: {exc}')
            return

        self._send_json({
            'session_id': session_id,
            'total_count': len(events),
            'events': events,
        })

    def _handle_workflow_artifact(self, qs: dict) -> None:
        """워크플로우 산출물 파일 조회 엔드포인트를 처리한다.

        GET /api/workflow/artifact?session_id=wf-*&path=plan.md

        세션의 work_dir 하위 화이트리스트 파일만 plain text로 반환한다.
        화이트리스트: plan.md, report.md, work/*.md, skill-mapping.md

        경로 traversal 방지:
        - ``..`` 포함 경로 즉시 차단
        - ``os.path.realpath`` 정규화 후 work_dir prefix 검증
        - 화이트리스트 패턴 불일치 시 403 반환

        응답 헤더: Content-Type: text/markdown; charset=utf-8

        Args:
            qs: parse_qs 결과 dict (URL 쿼리 파라미터)

        Returns:
            None (응답 전송 후 종료)
        """
        import re as _re

        session_id_list = qs.get('session_id')
        path_list = qs.get('path')

        if not session_id_list or not path_list:
            self._send_error(404, 'Missing "session_id" or "path" query parameter')
            return

        session_id = session_id_list[0]
        rel_path = path_list[0]

        # 경로 traversal 조기 차단: '..' 포함 즉시 거부
        if '..' in rel_path:
            self._send_error(403, 'Path traversal detected')
            return

        # 세션 조회
        session = workflow_registry.get(session_id)
        if session is None:
            self._send_error(404, f'Session not found: {session_id}')
            return

        # work_dir 미설정 검증
        work_dir = session.work_dir
        if not work_dir:
            self._send_error(404, 'Session work_dir is not set')
            return

        # 화이트리스트 패턴 검증
        _WHITELIST_PATTERNS = [
            _re.compile(r'^plan\.md$'),
            _re.compile(r'^report\.md$'),
            _re.compile(r'^skill-mapping\.md$'),
            _re.compile(r'^work/[^/]+\.md$'),
        ]
        if not any(p.match(rel_path) for p in _WHITELIST_PATTERNS):
            self._send_error(403, f'Path not in whitelist: {rel_path}')
            return

        # work_dir realpath 정규화
        try:
            real_work_dir = os.path.realpath(work_dir)
        except (OSError, ValueError):
            self._send_error(404, 'Invalid work_dir')
            return

        # 파일 절대 경로 구성 + realpath 정규화
        candidate = os.path.join(real_work_dir, rel_path)
        try:
            real_candidate = os.path.realpath(candidate)
        except (OSError, ValueError):
            self._send_error(403, 'Invalid file path')
            return

        # work_dir prefix 검증 (symlink 우회 방지)
        if not real_candidate.startswith(real_work_dir + os.sep) and real_candidate != real_work_dir:
            self._send_error(403, 'Path escapes work_dir boundary')
            return

        # 파일 읽기
        if not os.path.isfile(real_candidate):
            self._send_error(404, f'File not found: {rel_path}')
            return

        try:
            with open(real_candidate, encoding='utf-8') as f:
                content = f.read()
        except OSError as exc:
            self._send_error(404, f'Cannot read file: {exc}')
            return

        body = content.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/markdown; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
