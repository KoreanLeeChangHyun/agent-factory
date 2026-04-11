"""TerminalHandlerMixin — /terminal/* endpoints."""

from __future__ import annotations

import json
import os
import time
import uuid

from ..state import terminal_sse_channel, claude_process, workflow_registry
from .._common import logger, _get_git_branch
from ..terminal_channel import _resolve_last_event_id
from ..claude_process import _validate_images


class TerminalHandlerMixin:
    """Terminal main-session HTTP endpoints."""

    def _handle_terminal_sse(self) -> None:
        """터미널 전용 SSE 엔드포인트를 처리한다.

        /terminal/events 경로에 대해 TerminalSSEChannel로부터
        Claude CLI stdout 이벤트를 클라이언트에 스트리밍한다.
        기존 /events SSE와 완전히 독립된 채널을 사용한다.
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

        # 재접속 시 last_event_id로 중복 재생 방지 (헤더 + 쿼리 파라미터)
        last_event_id = _resolve_last_event_id(self.headers, self.path)
        terminal_sse_channel.add(self.wfile, last_event_id=last_event_id)
        try:
            while True:
                time.sleep(1)
                client_lock = terminal_sse_channel.get_lock(self.wfile)
                if client_lock is None:
                    break
                try:
                    with client_lock:
                        self.wfile.write(b': heartbeat\n\n')
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break
        finally:
            terminal_sse_channel.remove(self.wfile)

    def _handle_terminal_status(self) -> None:
        """터미널 상태 조회 엔드포인트를 처리한다.

        GET /terminal/status: Claude 프로세스의 현재 상태를 JSON으로 응답한다.
        """
        project_root = os.getcwd()
        self._send_json({
            'status': claude_process.status,
            'session_id': claude_process.session_id,
            'last_session_id': claude_process.session_id,
            'model': claude_process._model,
            'permission_mode': claude_process._permission_mode,
            'branch': _get_git_branch(project_root),
            'clients': terminal_sse_channel.client_count,
        })

    def _handle_terminal_sessions(self) -> None:
        """세션 목록 조회 엔드포인트를 처리한다.

        GET /terminal/sessions: ~/.claude/projects/<project-path>/ 디렉터리에서
        .jsonl 파일을 mtime 기준 내림차순 최대 20개 스캔하여 JSON 배열로 반환한다.
        파일 내용을 읽지 않고 파일명(UUID)과 stat(mtime)만 활용한다.

        응답 항목:
            session_id: UUID (파일명에서 추출)
            last_active: mtime 기반 ISO 8601 형식 시각
            is_current: 현재 활성 세션과 일치 여부
        """
        project_root = os.getcwd()

        # cwd 기반으로 ~/.claude/projects/ 하위 디렉터리 경로 산출
        # 예: /home/deus/workspace/claude -> -home-deus-workspace-claude
        home_dir = os.path.expanduser('~')
        project_slug = project_root.replace('/', '-')
        sessions_dir = os.path.join(home_dir, '.claude', 'projects', project_slug)

        current_session_id = claude_process.session_id

        entries: list[tuple[float, str]] = []  # (mtime, session_id)
        try:
            with os.scandir(sessions_dir) as it:
                for entry in it:
                    if not entry.name.endswith('.jsonl'):
                        continue
                    stem = entry.name[:-6]  # ".jsonl" 제거
                    # UUID 형식 검증
                    try:
                        uuid.UUID(stem)
                    except ValueError:
                        continue
                    try:
                        mtime = entry.stat().st_mtime
                    except OSError:
                        continue
                    entries.append((mtime, stem))
        except OSError as e:
            logger.debug('세션 디렉터리 스캔 실패: %s', e)
            self._send_json([])
            return

        # mtime 내림차순 정렬 후 최대 20개 선택
        entries.sort(key=lambda x: x[0], reverse=True)
        entries = entries[:20]

        result = []
        for mtime, session_id in entries:
            last_active = datetime.datetime.fromtimestamp(
                mtime, tz=datetime.timezone.utc
            ).strftime('%Y-%m-%dT%H:%M:%SZ')
            result.append({
                'session_id': session_id,
                'last_active': last_active,
                'is_current': session_id == current_session_id,
            })

        self._send_json(result)

    def _handle_terminal_start(self) -> None:
        """터미널 세션 시작 엔드포인트를 처리한다.

        POST /terminal/start: Claude CLI 프로세스를 시작한다.
        요청 본문에 {"args": [...]} 형태로 추가 CLI 인자를 지정할 수 있다.
        """
        extra_args = None
        resume_session_id = None
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                extra_args = data.get('args')
                resume_session_id = data.get('resume_session_id')
            except (json.JSONDecodeError, AttributeError):
                pass

        if resume_session_id:
            # UUID 형식 검증: 유효하지 않으면 새 세션으로 시작
            try:
                uuid.UUID(str(resume_session_id))
            except ValueError:
                logger.warning('유효하지 않은 resume_session_id: %s', resume_session_id)
                resume_session_id = None

        if resume_session_id:
            extra_args = ['--resume', resume_session_id]
        else:
            # 새 세션 시작 시에만 이전 이벤트 히스토리 초기화
            terminal_sse_channel.clear_history()

        result = claude_process.spawn(extra_args)
        self._send_json(result)

    def _handle_terminal_input(self) -> None:
        """터미널 입력 전송 엔드포인트를 처리한다.

        POST /terminal/input: 사용자 메시지를 Claude CLI에 전송한다.
        요청 본문: {"text": "사용자 메시지"}

        프로세스 미시작 시 409 Conflict를 반환한다.
        """
        if claude_process.status == 'stopped':
            self._send_error(409, 'Claude process not running')
            return

        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self._send_error(400, 'Empty request body')
            return

        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_error(400, 'Invalid JSON')
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

        # 사용자 입력을 SSE 히스토리에 기록 (텍스트만, 이미지 base64 제외)
        if text:
            terminal_sse_channel.broadcast(
                {'type': 'user_input', 'text': text}
            )

        result = claude_process.send_input(text, images=images)
        self._send_json(result)

    def _handle_terminal_kill(self) -> None:
        """터미널 세션 종료 엔드포인트를 처리한다.

        POST /terminal/kill: Claude CLI 프로세스를 종료한다.

        프로세스 미시작 시 409 Conflict를 반환한다.
        """
        if claude_process.status == 'stopped':
            self._send_error(409, 'Claude process not running')
            return

        result = claude_process.kill()
        self._send_json(result)

    def _handle_terminal_command(self) -> None:
        """슬래시 명령어 전달 엔드포인트를 처리한다.

        POST /terminal/command: 클라이언트에서 전송한 슬래시 명령어를 Claude CLI stdin에
        전달한다. 기존 send_input() 메서드를 재사용하여 NDJSON 엔벨로프로 전송한다.

        요청 본문: {"command": "/clear"}
        선택 필드: "session_id" (현재 미사용, 메인 세션 전용)

        프로세스 미시작 시 409 Conflict를 반환한다.
        """
        if claude_process.status == 'stopped':
            self._send_error(409, 'Claude process not running')
            return

        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self._send_error(400, 'Empty request body')
            return

        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_error(400, 'Invalid JSON')
            return

        command = data.get('command', '').strip()
        if not command:
            self._send_error(400, 'Missing "command" field')
            return

        if not command.startswith('/'):
            self._send_error(400, 'Command must start with "/"')
            return

        result = claude_process.send_input(command)
        self._send_json(result)

    def _handle_terminal_permission(self) -> None:
        """permission 요청에 대한 승인/거부 응답 엔드포인트를 처리한다.

        POST /terminal/permission
        요청 본문: {"request_id": "...", "decision": "allow"|"deny"}
        선택 필드: "session_id" (워크플로우 세션용)

        session_id가 있으면 workflow_registry에서 해당 세션의 프로세스를 사용하고,
        없으면 claude_process(메인 터미널)를 사용한다.

        프로세스 미실행 시 409 Conflict, 잘못된 요청 시 400 Bad Request를 반환한다.
        """
        data = self._read_json_body()
        if data is None:
            return

        request_id = data.get('request_id', '').strip()
        if not request_id:
            self._send_error(400, 'Missing "request_id" field')
            return

        decision = data.get('decision', '').strip()
        if decision not in ('allow', 'deny'):
            self._send_error(400, '"decision" must be "allow" or "deny"')
            return

        session_id = data.get('session_id', '').strip() or None

        if session_id:
            session = workflow_registry.get(session_id)
            if session is None:
                self._send_error(404, f'Session not found: {session_id}')
                return
            process = session.process
        else:
            process = claude_process

        if process.status == 'stopped':
            self._send_error(409, 'Claude process not running')
            return

        result = process.send_permission_response(request_id, decision, session_id)
        self._send_json(result)

    def _handle_terminal_interrupt(self) -> None:
        """현재 응답 생성 중단 엔드포인트를 처리한다.

        POST /terminal/interrupt: Claude CLI 프로세스에 SIGINT를 전송한다.
        프로세스를 종료하지 않고 현재 응답 생성만 중단한다.

        프로세스가 stopped 상태이면 409 Conflict를 반환한다.
        """
        if claude_process.status == 'stopped':
            self._send_error(409, 'Claude process not running')
            return

        result = claude_process.interrupt()
        self._send_json(result)
