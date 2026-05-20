"""TerminalHandlerMixin — /terminal/* endpoints."""

from __future__ import annotations

import datetime
import json
import os
import time
import uuid
from urllib.parse import parse_qs, urlparse

from board.server.runtime.state import terminal_sse_channel, claude_process, workflow_registry
from board.server.support.common import api_endpoint, logger, _get_git_branch, server_debug_log
from board.server.channels.event_filter import is_user_visible
from board.server.channels.terminal_channel import _resolve_last_event_id
from board.server.processes.claude_process import _validate_images
from board.server.artifacts.attachments_persist import AttachmentsSidecar


# Apply ``min_attachment_threshold`` to prevent collisions. (envelope synthesis
# When the prompt + report body is combined in the step, it is usually more than 1KB, so 200 characters are required.
# Sufficiently conservative lower bound.)
_ATTACHMENT_BLOCK_PREFIX = '[Attachment T-'
_ATTACHMENT_BLOCK_MIN_LEN = 200


_HISTORY_SKIP_TYPES = frozenset({
    'queue-operation', 'last-prompt', 'summary', 'attachment',
    'progress', 'file-history-snapshot', 'system', 'permission-mode',
})


def _assign_turn_ids(events: list[dict]) -> list[dict]:
    """internal helper — not exposed as endpoint.

    시간순 render events 배열에 turn_id 필드를 부여하고 그대로 반환한다.

    1:1 단순화 규칙 (1 user 이벤트 = 1 turn):
    - user 이벤트가 등장할 때마다 무조건 새 turn_id 를 시작한다.
      timestamp 인접성(gap 임계값) / turn_has_assistant 분기는 폐기.
    - tool_result 는 user 역할이지만 assistant turn 의 일부로 취급하여
      새 turn 을 시작하지 않는다.
    - assistant/tool 이벤트는 직전 user turn_id 를 그대로 상속한다.
    - turn_id 형식: f"hist-{ev_timestamp}" — user 이벤트 timestamp 기반
      결정론적 ID. 새로고침 후에도 동일 이벤트가 동일 id 를 받는다.

    orphan 처리:
    - 첫 이벤트가 assistant 인 엣지 케이스에서는 'hist-orphan' 을 할당한다.

    side-effect: 각 ev dict 에 'turn_id' 키가 추가된다 (in-place).
    반환값은 편의를 위해 동일 리스트를 그대로 반환한다.
    """
    current_turn_id: str | None = None

    for ev in events:
        role = ev.get('role', '')
        kind = ev.get('kind', '')
        ts = ev.get('timestamp', '') or ''

        # tool_result is a user role, but is treated as part of assistant turn
        is_tool_result = (role == 'user' and kind == 'tool_result')
        is_real_user = (role == 'user' and not is_tool_result)

        if is_real_user:
            # New user event = unconditional new turn (regardless of gap threshold)
            # Fallback processing for extremely rare legacy records without timestamps
            current_turn_id = f"hist-{ts}" if ts else "hist-orphan"

        # If current_turn_id does not exist, fallback: orphan assistant event
        # (Edge case where the first event is assistant)
        if current_turn_id is None:
            current_turn_id = 'hist-orphan'

        ev['turn_id'] = current_turn_id

    return events


def _extract_tool_result_text(content: object) -> str:
    """internal helper — not exposed as endpoint.

    tool_result content에서 평문 텍스트만 추출한다.

    content는 (a) 문자열 또는 (b) [{type:text|image, ...}, ...] 배열.
    image 블록은 제외한다.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get('type') != 'text':
                continue
            text = item.get('text') or ''
            if text:
                parts.append(text)
        return '\n'.join(parts)
    return ''


def _is_system_wrapper_text(text: str) -> bool:
    """internal helper — not exposed as endpoint.

    슬래시 커맨드 래퍼, system-reminder 등 히스토리에서 숨겨야 할 user 메시지를 판별한다.
    """
    stripped = text.lstrip()
    if stripped.startswith(_TITLE_SKIP_PREFIXES):
        return True
    if text in _TITLE_SKIP_EXACT:
        return True
    return False


def _build_render_events(data: dict) -> list[dict]:
    """internal helper — not exposed as endpoint.

    jsonl 라인 한 줄을 0~N개의 렌더 이벤트로 전개한다.

    하나의 assistant 메시지가 thinking + text + tool_use 여러 블록을 포함할 수
    있으므로 블록 수만큼의 이벤트를 반환한다. 빈 텍스트, 시스템 래퍼 user
    메시지는 제외된다.

    반환 이벤트 스키마:
        - role: 'user' | 'assistant'
        - kind: 'text' | 'thinking' | 'tool_use' | 'tool_result'
        - text: 본문 (tool_use 제외)
        - tool_use_id: kind in {tool_use, tool_result}
        - name: kind == 'tool_use'
        - input: kind == 'tool_use' (dict)
        - is_error: kind == 'tool_result' (bool)
        - timestamp: ISO 8601 (원본 유지)
    """
    timestamp = data.get('timestamp', '') or ''
    if not is_user_visible(data):
        return []
    message = data.get('message') or {}
    if not isinstance(message, dict):
        return []
    role = message.get('role')
    if role not in ('user', 'assistant'):
        return []
    content = message.get('content')

    events: list[dict] = []

    if isinstance(content, str):
        text = content.strip()
        if not text:
            return []
        if role == 'user' and _is_system_wrapper_text(text):
            return []
        events.append({
            'role': role, 'kind': 'text', 'text': text,
            'timestamp': timestamp,
        })
        return events

    if not isinstance(content, list):
        return []

    # ----------------------------------------
    # If the user role's content is a list with length >= 2, only the first text block
    # Adopt it as a user text event and attach the subsequent text block (with ``[Attachment T-``)
    # start + length ``_ATTACHMENT_BLOCK_MIN_LEN`` or higher) in the user message render.
    # Exclude. Attachments are separate in the sidecar(``<session_id>.attachments.jsonl``)
    # It is stored, and ``_handle_terminal_history`` is sent to the user event by ts matching.
    # Provides an ``attachments`` field.
    #
    # The length threshold (_ATTACHMENT_BLOCK_MIN_LEN=200) allows the user to manually
    # The attachment block synthesized when sending to the frontend includes the prompt + report body, so
    # Usually exceeds 1KB.
    skip_attachment_blocks = (
        role == 'user' and isinstance(content, list) and len(content) >= 2
    )
    user_text_emitted = False

    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get('type')
        if btype == 'text':
            raw_text = block.get('text') or ''
            text = raw_text.strip()
            if not text:
                continue
            if role == 'user' and _is_system_wrapper_text(text):
                continue
            if skip_attachment_blocks:
                if not user_text_emitted:
                    # First user text block = user input
                    user_text_emitted = True
                else:
                    # Second and subsequent blocks: attach prefix + skip when length threshold is met
                    if (
                        text.startswith(_ATTACHMENT_BLOCK_PREFIX)
                        and len(raw_text) >= _ATTACHMENT_BLOCK_MIN_LEN
                    ):
                        continue
                    # If the prefix/length is not met, it is output as a general text block.
                    # (Case where user legitimately sends multiple text blocks
                    # regression 0)
            events.append({
                'role': role, 'kind': 'text', 'text': text,
                'timestamp': timestamp,
            })
        elif btype == 'thinking':
            text = (block.get('thinking') or '').strip()
            if not text:
                continue
            events.append({
                'role': role, 'kind': 'thinking', 'text': text,
                'timestamp': timestamp,
            })
        elif btype == 'tool_use':
            events.append({
                'role': role, 'kind': 'tool_use',
                'tool_use_id': block.get('id', '') or '',
                'name': block.get('name', '') or '',
                'input': block.get('input') if isinstance(block.get('input'), dict) else {},
                'timestamp': timestamp,
            })
        elif btype == 'tool_result':
            events.append({
                'role': role, 'kind': 'tool_result',
                'tool_use_id': block.get('tool_use_id', '') or '',
                'text': _extract_tool_result_text(block.get('content')),
                'is_error': bool(block.get('is_error')),
                'timestamp': timestamp,
            })

    return events


_TITLE_SKIP_PREFIXES = (
    '<local-command-',
    '<command-message>',
    '<command-name>',
    '<command-stdout>',
    '<command-args>',
    '<system-reminder>',
)
_TITLE_SKIP_EXACT = (
    "This is the first message. 'The session has been reset.' Just answer:",
)
_TITLE_MAX_LENGTH = 100
_TITLE_SCAN_MAX_LINES = 300


def _extract_session_meta(filepath: str) -> tuple[str | None, str]:
    """internal helper — not exposed as endpoint.

    jsonl 파일에서 (title, branch) 를 한 번의 스캔으로 추출한다.

    title: 첫 유효 user 메시지 (필터 규칙은 기존 _extract_session_title 동일)
    branch: 가장 최근에 등장한 ``gitBranch`` 필드 값 (없으면 빈 문자열)

    - toolUseResult 포함 메시지(툴 결과)는 title 후보에서 스킵
    - 슬래시 명령 래퍼(<command-*>)는 스킵하되 플래그를 세워두고
      그 직후의 `# ` 시작 마크다운은 명령어 .md 본문 주입으로 간주하여 추가 스킵
    - 로컬 커맨드 / 시스템 리마인더 래퍼도 스킵
    - resume 초기화 템플릿 메시지는 스킵
    - 최대 _TITLE_SCAN_MAX_LINES 라인까지만 검사 (branch 도 같은 범위에서만 추출)
    - title 이 끝까지 없으면 (None, branch) 반환 → 호출부에서 결과 제외 판단
    """
    title: str | None = None
    branch = ''
    command_context = False
    try:
        with open(filepath, 'r', encoding='utf-8') as fp:
            for index, line in enumerate(fp):
                if index > _TITLE_SCAN_MAX_LINES:
                    break
                try:
                    event = json.loads(line)
                except (ValueError, json.JSONDecodeError):
                    continue

                # branch: update as much as possible on every line (last occurrence of value)
                if isinstance(event.get('gitBranch'), str) and event['gitBranch']:
                    branch = event['gitBranch']

                if title is not None:
                    # Title already confirmed → Continue tracking only the branch
                    continue

                if event.get('type') != 'user':
                    continue
                if 'toolUseResult' in event:
                    continue
                message = event.get('message') or {}
                content = message.get('content', '')
                text = ''
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get('type') == 'text':
                            text = block.get('text', '') or ''
                            break
                elif isinstance(content, str):
                    text = content
                text = text.strip()
                if not text:
                    continue
                if text.startswith(('<command-message>', '<command-name>',
                                    '<command-stdout>', '<command-args>')):
                    command_context = True
                    continue
                if command_context and text.startswith('# '):
                    continue
                command_context = False
                if text.startswith(_TITLE_SKIP_PREFIXES):
                    continue
                if text in _TITLE_SKIP_EXACT:
                    continue
                title = text[:_TITLE_MAX_LENGTH]
    except (OSError, IOError) as err:
        logger.debug('Session meta extraction failed (%s): %s', filepath, err)
    return title, branch


class TerminalHandlerMixin:
    """Terminal main-session HTTP endpoints."""

    @api_endpoint("T", "sse")
    def _handle_terminal_sse(self) -> None:
        """터미널 전용 SSE 엔드포인트를 처리한다.

        /terminal/events 경로에 대해 TerminalSSEChannel로부터
        Claude CLI stdout 이벤트를 클라이언트에 스트리밍한다.
        기존 /events SSE와 완전히 독립된 채널을 사용한다.

        method: GET
        url: /terminal/events
        domain: T
        handler: TerminalHandlerMixin._handle_terminal_sse
        request: query {last_event_id?: int, skip_replay?: bool}
        response_ok: text/event-stream (TerminalSSEChannel)
        response_error: n/a (HTTP keep-alive stream)
        status_codes: 200
        auth: none (local-only)
        side_effects: register self.wfile to terminal_sse_channel
        sse_events: stdout, result, system, permission, user_input, error, skill_listing, rate_limit, workflow_step (board.md §1.1)
        """
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # Send initial annotation to confirm connection
        try:
            self.wfile.write(b': connected\n\n')
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

        # Prevent duplicate playback with last_event_id when reconnecting (header + query parameters)
        last_event_id = _resolve_last_event_id(self.headers, self.path)

        # ``skip_replay=1`` query flag: client to REST /terminal/history
        # A declaration that the past has already been restored. The server skips ring buffer playback and goes live.
        # Only events are delivered. The main terminal is used for the first connection.
        parsed_query = parse_qs(urlparse(self.path).query)
        skip_replay = parsed_query.get('skip_replay', ['0'])[0] == '1'

        terminal_sse_channel.add(
            self.wfile,
            last_event_id=last_event_id,
            skip_replay=skip_replay,
        )
        try:
            while True:
                time.sleep(0.25)
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

    @api_endpoint("T", "status")
    def _handle_terminal_status(self) -> None:
        """터미널 상태 조회 엔드포인트를 처리한다.

        GET /terminal/status: Claude 프로세스의 현재 상태를 JSON으로 응답한다.

        method: GET
        url: /terminal/status
        domain: T
        handler: TerminalHandlerMixin._handle_terminal_status
        request: query none
        response_ok: {status, session_id, model, permission_mode, branch, clients, awaiting_response}
        response_error: n/a (always 200)
        status_codes: 200
        auth: none (local-only)
        side_effects: read claude_process snapshot
        sse_events: none
        """
        project_root = os.getcwd()
        awaiting = bool(getattr(claude_process, '_awaiting_response', False))
        server_debug_log('status.response', {
            'status': claude_process.status,
            'session_id': claude_process.session_id,
            'awaiting_response': awaiting,
        })
        self._send_json({
            'status': claude_process.status,
            'session_id': claude_process.session_id,
            'last_session_id': claude_process.session_id,
            'model': claude_process._model,
            'permission_mode': claude_process._permission_mode,
            'branch': _get_git_branch(project_root),
            'clients': terminal_sse_channel.client_count,
            # Signal for the client to determine spinner/input lock recovery after refresh.
            # True after sending user input until receiving the result. claude_process._status alone
            # Judgment during creation is impossible (since the status remains 'idle' even after the result).
            'awaiting_response': awaiting,
        })

    @api_endpoint("T", "sessions")
    def _handle_terminal_sessions(self) -> None:
        """세션 목록 조회 엔드포인트를 처리한다.

        GET /terminal/sessions: ~/.claude/projects/<project-path>/ 디렉터리에서
        .jsonl 파일을 mtime 기준 내림차순으로 전수 스캔하여 JSON 배열로 반환한다.
        각 파일에서 최초 유효 user 메시지를 파싱하여 title 필드를 추출한다.
        유효 메시지가 없는 임시/초기화 세션은 결과에서 제외한다.

        응답 항목:
            session_id: UUID (파일명에서 추출)
            last_active: mtime 기반 ISO 8601 형식 시각
            is_current: 현재 "running"인 세션과 일치 여부 (status != 'stopped')
            is_last: ``.last-session-id`` 가 가리키는 마지막 세션 여부
                     (stopped 상태에도 유지되는 복원 후보)
            title: 첫 유효 user 메시지 (최대 100자)
            branch: 세션 jsonl 의 마지막 ``gitBranch`` 값 (없으면 "")
            size_bytes: jsonl 파일 크기 (바이트)

        method: GET
        url: /terminal/sessions
        domain: T
        handler: TerminalHandlerMixin._handle_terminal_sessions
        request: query none
        response_ok: [{session_id, last_active, is_current, is_last, title, branch, size_bytes}]
        response_error: n/a (always 200; missing dir → empty list)
        status_codes: 200
        auth: none (local-only)
        side_effects: scandir ~/.claude/projects/<slug>/, parse jsonl headers
        sse_events: none
        """
        project_root = os.getcwd()

        # Calculate the ~/.claude/projects/ subdirectory path based on cwd
        # Example: /home/deus/workspace/claude -> -home-deus-workspace-claude
        home_dir = os.path.expanduser('~')
        project_slug = project_root.replace('/', '-')
        sessions_dir = os.path.join(home_dir, '.claude', 'projects', project_slug)

        # is_current = "Running now"인 세션. status == 'stopped' 인 경우
        # .last-session-id 에서 복원된 session_id 는 'last session'(is_last)
        # 이지 'current session'이 아니다.
        last_session_id = claude_process.session_id
        current_session_id = (
            last_session_id if claude_process.status != 'stopped' else ''
        )

        entries: list[tuple[float, str, str, int]] = []  # (mtime, session_id, filepath, size)
        try:
            with os.scandir(sessions_dir) as it:
                for entry in it:
                    if not entry.name.endswith('.jsonl'):
                        continue
                    stem = entry.name[:-6]  # Remove ".jsonl"
                    try:
                        uuid.UUID(stem)
                    except ValueError:
                        continue
                    try:
                        st = entry.stat()
                    except OSError:
                        continue
                    entries.append((st.st_mtime, stem, entry.path, st.st_size))
        except OSError as e:
            logger.debug('Session directory scan failed: %s', e)
            self._send_json([])
            return

        # Sort by mtime descending
        entries.sort(key=lambda x: x[0], reverse=True)

        result = []
        for mtime, session_id, filepath, size_bytes in entries:
            title, branch = _extract_session_meta(filepath)
            if title is None:
                # Title extraction failure = excluded as temporary/reset session
                continue
            last_active = datetime.datetime.fromtimestamp(
                mtime, tz=datetime.timezone.utc
            ).strftime('%Y-%m-%dT%H:%M:%SZ')
            result.append({
                'session_id': session_id,
                'last_active': last_active,
                'is_current': bool(current_session_id) and session_id == current_session_id,
                'is_last': bool(last_session_id) and session_id == last_session_id,
                'title': title,
                'branch': branch,
                'size_bytes': size_bytes,
            })

        self._send_json(result)

    @api_endpoint("T", "history")
    def _handle_terminal_history(self) -> None:
        """세션 대화 히스토리 조회 엔드포인트를 처리한다.

        GET /terminal/history?session_id=<uuid>[&since=<iso-timestamp>]:
        ``~/.claude/projects/<project-slug>/<session_id>.jsonl`` 파일을 읽어
        렌더 이벤트 배열로 반환한다.

        method: GET
        url: /terminal/history
        domain: T
        handler: TerminalHandlerMixin._handle_terminal_history
        request: query {session_id: str, since?: iso8601}
        response_ok: {session_id, events: [{role, kind, text, timestamp, turn_id, ...}]}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 404, 500
        auth: none (local-only)
        side_effects: read session jsonl file
        sse_events: none

        jsonl 이벤트를 text / thinking / tool_use / tool_result 4종 kind로
        전개하여 SSE 라이브와 동일한 입도로 복원한다. ``since`` 가 주어지면
        해당 시점보다 timestamp 가 큰 이벤트만 반환한다 (재연결 gap 보충).

        ``last_usage`` / ``last_cost_usd`` 필드는 ``since`` 와 무관하게
        세션 전체에서 가장 최근 값을 반환한다. 재연결 시 클라이언트가
        ``resetTokens()`` 로 0 초기화된 상태를 복원하기 위한 용도이므로
        gap 여부와 관계없이 항상 현재 총계가 필요하기 때문이다.

        응답 스키마:
            {
              "session_id": "<uuid>",
              "last_timestamp": "<iso>",
              "last_usage": {"input_tokens": N, "output_tokens": N},  # optional
              "last_cost_usd": 0.1234,                                 # optional
              "events": [
                {"role": "user|assistant",
                 "kind": "text|thinking|tool_use|tool_result",
                 "text": "...",
                 "tool_use_id": "...",      # tool_use, tool_result
                 "name": "...",              # tool_use
                 "input": {...},             # tool_use
                 "is_error": false,          # tool_result
                 "timestamp": "<iso>"},
                ...
              ]
            }
        """
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        session_id = (query.get('session_id') or [''])[0].strip()
        since = (query.get('since') or [''])[0].strip()

        if not session_id:
            self._send_error(400, 'Missing "session_id" query parameter')
            return

        try:
            uuid.UUID(session_id)
        except ValueError:
            self._send_error(400, 'Invalid session_id format')
            return

        project_root = os.getcwd()
        home_dir = os.path.expanduser('~')
        project_slug = project_root.replace('/', '-')
        filepath = os.path.join(
            home_dir, '.claude', 'projects', project_slug, f'{session_id}.jsonl',
        )

        if not os.path.isfile(filepath):
            self._send_error(404, 'Session history not found')
            return

        events: list[dict] = []
        last_timestamp = ''
        last_usage: dict | None = None
        last_usage_ts = ''
        last_cost_usd: float | None = None
        last_cost_ts = ''
        last_model: str | None = None
        last_model_ts = ''
        try:
            with open(filepath, 'r', encoding='utf-8') as fp:
                for line in fp:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        data = json.loads(stripped)
                    except (ValueError, json.JSONDecodeError):
                        continue

                    msg_type = data.get('type', '')
                    line_ts = data.get('timestamp', '') or ''

                    # assistant.message.usage — Full context at the time of each API call
                    # Usage (not delta). Only the last value is maintained throughout the session.
                    # SSE live path (terminal_channel._build_stream_payload) and
                    # Similarly, sum input_tokens + cache_read + cache_creation
                    # It must be used so that the status bar percentage is consistent.
                    if msg_type == 'assistant':
                        msg = data.get('message')
                        if isinstance(msg, dict):
                            model_val = msg.get('model')
                            if isinstance(model_val, str) and line_ts >= last_model_ts:
                                last_model = model_val
                                last_model_ts = line_ts
                            usage = msg.get('usage')
                            if isinstance(usage, dict) and line_ts >= last_usage_ts:
                                in_raw = usage.get('input_tokens', 0) or 0
                                in_cache_r = usage.get('cache_read_input_tokens', 0) or 0
                                in_cache_c = usage.get('cache_creation_input_tokens', 0) or 0
                                out_raw = usage.get('output_tokens', 0) or 0
                                if in_raw or in_cache_r or in_cache_c or out_raw:
                                    last_usage = {
                                        'input_tokens': in_raw + in_cache_r + in_cache_c,
                                        'output_tokens': out_raw,
                                    }
                                    last_usage_ts = line_ts

                    # result type: Session cumulative cost (total_cost_usd) + last usage.
                    # May not be present in sample session (depending on interaction or subtype).
                    if msg_type == 'result':
                        cost = data.get('total_cost_usd')
                        if isinstance(cost, (int, float)) and line_ts >= last_cost_ts:
                            last_cost_usd = float(cost)
                            last_cost_ts = line_ts
                        r_usage = data.get('usage')
                        if isinstance(r_usage, dict) and line_ts >= last_usage_ts:
                            in_raw = r_usage.get('input_tokens', 0) or 0
                            in_cache_r = r_usage.get('cache_read_input_tokens', 0) or 0
                            in_cache_c = r_usage.get('cache_creation_input_tokens', 0) or 0
                            out_raw = r_usage.get('output_tokens', 0) or 0
                            if in_raw or in_cache_r or in_cache_c or out_raw:
                                last_usage = {
                                    'input_tokens': in_raw + in_cache_r + in_cache_c,
                                    'output_tokens': out_raw,
                                }
                                last_usage_ts = line_ts

                    if msg_type in _HISTORY_SKIP_TYPES:
                        continue

                    line_events = _build_render_events(data)
                    if not line_events:
                        continue

                    # For ISO 8601 strings, alphabetic comparison matches chronological order.
                    for ev in line_events:
                        ts = ev.get('timestamp') or ''
                        if since and ts and ts <= since:
                            continue
                        events.append(ev)
                        if ts and ts > last_timestamp:
                            last_timestamp = ts
        except OSError as err:
            logger.debug('Failed to read session history (%s): %s', filepath, err)
            self._send_error(500, 'Failed to read session history')
            return

        # Merge currently streaming assistant messages (not yet in jsonl).
        # Claude CLI flushes to jsonl only when the message is completed, so a response is generated
        # When refreshing, the partial content is nowhere to be found and is completely lost from the UI.
        # This cache fills that gap. Only the last block has the `in_flight` flag
        # Have the client seed a text buffer (as a complete block in the DOM)
        # When rendered, the subsequent live text_delta creates a separate block and becomes two pieces).
        if claude_process.session_id == session_id:
            in_flight = claude_process.get_in_flight_snapshot()
            if in_flight:
                in_flight_ts = in_flight.get('timestamp', '') or ''
                if not since or (in_flight_ts and in_flight_ts > since):
                    in_flight_events = _build_render_events(in_flight)
                    if in_flight_events:
                        in_flight_events[-1]['in_flight'] = True
                        # Pass partial_input_json if tool_use is in-flight
                        last_block = in_flight.get('message', {}).get('content', [])
                        if last_block:
                            last_raw = last_block[-1]
                            if last_raw.get('type') == 'tool_use' and last_raw.get('partial_input_json'):
                                in_flight_events[-1]['partial_input_json'] = (
                                    last_raw['partial_input_json']
                                )
                        for ev in in_flight_events:
                            events.append(ev)
                            ts = ev.get('timestamp') or ''
                            if ts and ts > last_timestamp:
                                last_timestamp = ts

        # Placeholder user message automatically added to jsonl when SDK interrupts ESC
        # "[Request interrupted by user]" is not a message sent by the user, so events
        # Filter from . The same information matches our .interrupted badge with a sidecar.
        # display to prevent noise generation.
        events = [
            ev for ev in events
            if not (
                ev.get('role') == 'user'
                and ev.get('kind') == 'text'
                and (ev.get('text') or '').strip() == '[Request interrupted by user]'
            )
        ]

        # turn_id grouping: give turn_id field to all events (including in-flight)
        _assign_turn_ids(events)

        # Apply ESC interrupt sidecar: timestamp of <session_id>.interrupted.jsonl
        # Add the field ``interrupted=true`` to the user event matching .
        # tool_result is a user role, but is not subject to interrupt (excluding).
        sidecar_path = filepath.replace('.jsonl', '.interrupted.jsonl')
        if os.path.isfile(sidecar_path):
            interrupted_ts: set[str] = set()
            try:
                with open(sidecar_path, 'r', encoding='utf-8') as fp:
                    for line in fp:
                        stripped = line.strip()
                        if not stripped:
                            continue
                        try:
                            rec = json.loads(stripped)
                        except (ValueError, json.JSONDecodeError):
                            continue
                        ts = rec.get('timestamp')
                        if isinstance(ts, str) and ts:
                            interrupted_ts.add(ts)
            except OSError:
                interrupted_ts = set()
            if interrupted_ts:
                for ev in events:
                    if ev.get('role') != 'user':
                        continue
                    if ev.get('kind') == 'tool_result':
                        continue
                    if ev.get('timestamp') in interrupted_ts:
                        ev['interrupted'] = True

        # -----------------------------------------------------------------
        # Read the lines ``<session_id>.attachments.jsonl`` for user_msg_ts and user
        # Matches the timestamp of the event and gives ``ev['attachments']``.
        # Matching strategy (graceful fallback):
        #   1) Exact match
        #   2) Second normalized matching (compare ``YYYY-MM-DDTHH:MM:SS`` prefix) —
        #      Claude CLI jsonl ts and the ts we recorded during broadcast
        #      Absorbs sub-second differences
        #   3) If both of the above fail, treat as absence of attachments (graceful, regression 0)
        #
        # Tool_result, etc. other than user role or tool_result of user role are excluded.
        try:
            attachments_map = AttachmentsSidecar(session_id).load_map()
        except Exception as exc:  # noqa: BLE001 — sidecar IO is best-effort
            logger.error('Failed to load attachments sidecar: %s', exc)
            attachments_map = {}

        if attachments_map:
            # Second normalized index (for sub-second difference matching)
            sec_index: dict[str, list[dict]] = {}
            for ts_key, atts in attachments_map.items():
                if isinstance(ts_key, str) and len(ts_key) >= 19:
                    sec_key = ts_key[:19]  # 'YYYY-MM-DDTHH:MM:SS'
                    sec_index.setdefault(sec_key, atts)

            for ev in events:
                if ev.get('role') != 'user':
                    continue
                if ev.get('kind') != 'text':
                    continue
                ts = ev.get('timestamp') or ''
                if not ts:
                    continue
                # 1) Exact match
                atts = attachments_map.get(ts)
                if atts is None:
                    # 2) Second normalized matching
                    if len(ts) >= 19:
                        atts = sec_index.get(ts[:19])
                if atts:
                    ev['attachments'] = atts

        # pending_turn flag: When waiting for a response immediately after the last user event
        # Informs the client to seed the spinner without closing the turn-card.
        # If there is already an in_flight event, the client
        # Since it is handled with sawInFlight, pending_turn is a supplementary solution if in_flight does not exist.
        pending_turn = False
        last_ev_for_log = events[-1] if events else None
        sid_match = claude_process.session_id == session_id
        awaiting_for_log = bool(getattr(claude_process, '_awaiting_response', False))
        if sid_match:
            if getattr(claude_process, '_awaiting_response', False):
                # If the last event is user and there is no in_flight event
                if events and not events[-1].get('in_flight'):
                    last_ev = events[-1]
                    # A user event (interrupted=true) stopped by ESC is not an unresolved turn.
                    # Defense Augmentation: _awaiting_response fails to fall to true False.
                    # Even in this scenario, the last interrupted user event blocks pending_turn entry.
                    if (last_ev.get('role') == 'user'
                            and last_ev.get('kind') != 'tool_result'
                            and not last_ev.get('interrupted')):
                        pending_turn = True
        server_debug_log('history.pending_turn_eval', {
            'session_id': session_id,
            'sid_match': sid_match,
            'awaiting_response': awaiting_for_log,
            'events_count': len(events) if events else 0,
            'last_ev': {
                'role': last_ev_for_log.get('role') if last_ev_for_log else None,
                'kind': last_ev_for_log.get('kind') if last_ev_for_log else None,
                'in_flight': bool(last_ev_for_log.get('in_flight')) if last_ev_for_log else None,
                'interrupted': bool(last_ev_for_log.get('interrupted')) if last_ev_for_log else None,
            } if last_ev_for_log else None,
            'pending_turn_result': pending_turn,
        })

        response: dict = {
            'session_id': session_id,
            'last_timestamp': last_timestamp,
            'events': events,
        }
        if last_usage is not None:
            response['last_usage'] = last_usage
        if last_cost_usd is not None:
            response['last_cost_usd'] = last_cost_usd
        if last_model is not None:
            response['last_model'] = last_model
        if pending_turn:
            response['pending_turn'] = True

        self._send_json(response)

    @api_endpoint("T", "start")
    def _handle_terminal_start(self) -> None:
        """터미널 세션 시작 엔드포인트를 처리한다.

        POST /terminal/start: Claude CLI 프로세스를 시작한다.
        요청 본문에 {"args": [...]} 형태로 추가 CLI 인자를 지정할 수 있다.

        method: POST
        url: /terminal/start
        domain: T
        handler: TerminalHandlerMixin._handle_terminal_start
        request: body {args?: list[str], resume_session_id?: uuid}
        response_ok: {ok: true, session_id: uuid}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 409
        auth: none (local-only)
        side_effects: spawn Claude CLI subprocess (`claude` binary)
        sse_events: system init (via TerminalSSEChannel)
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
            # UUID format validation: if invalid, start new session
            try:
                uuid.UUID(str(resume_session_id))
            except ValueError:
                logger.warning('Invalid resume_session_id: %s', resume_session_id)
                resume_session_id = None

        if resume_session_id:
            extra_args = ['--resume', resume_session_id]
        else:
            extra_args = []

        result = claude_process.spawn(extra_args)

        # When resuming, Claude CLI does not issue an init event until the first input.
        # There was a problem where session_id was returned as an empty value. The resume target UUID is
        # Since it is already known, it is reflected in the response and process._session_id
        # Allows you to set termSessionId right away. Afterwards, when the init event comes
        # It is the same value or overwritten with a new UUID that the server falls back on.
        if resume_session_id and result.get('ok') and not result.get('session_id'):
            result['session_id'] = resume_session_id
            claude_process._session_id = resume_session_id

        self._send_json(result)

    @api_endpoint("T", "input")
    def _handle_terminal_input(self) -> None:
        """터미널 입력 전송 엔드포인트를 처리한다.

        POST /terminal/input: 사용자 메시지를 Claude CLI에 전송한다.
        요청 본문: {"text": "user message"}

        프로세스 미시작 시 409 Conflict를 반환한다.

        method: POST
        url: /terminal/input
        domain: T
        handler: TerminalHandlerMixin._handle_terminal_input
        request: body {text?: str, images?: list, attachments?: list}
        response_ok: {ok: true, ...send_input result}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 409
        auth: none (local-only)
        side_effects: feed NDJSON envelope to Claude CLI stdin + sidecar append
        sse_events: user_input (TerminalSSEChannel)
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
        attachments_raw = data.get('attachments', None)

        # Missing elements are ignored and data sent by the wrong client is sent.
        # Avoid blocking it entirely (return guard).
        attachments: list[dict] = []
        if isinstance(attachments_raw, list):
            for att in attachments_raw:
                if isinstance(att, dict) and 'number' in att:
                    attachments.append(att)

        if not text and not images and not attachments:
            self._send_error(400, 'Missing "text" field')
            return

        if images is not None:
            validation_error = _validate_images(images)
            if validation_error:
                self._send_error(400, validation_error)
                return

        # ------------------------------------
        # When Claude CLI flushes the user envelope received from stdin to jsonl
        # Gives its own timestamp. ``user_msg_ts`` we will record in the sidecar
        # and jsonl ts may not match exactly to the sub-second, so
        # In the matching step of ``_handle_terminal_history`` (a) exact match → (b)
        # Graceful fallback to second normalization matching step. Here, broadcast and
        # After refreshing the frontend using the same ts in the sidecar,
        # Ensure consistency.
        user_msg_ts = (
            datetime.datetime.now(tz=datetime.timezone.utc)
            .strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        )

        # Log user input to SSE history (text only, no image base64)
        # Reduce the SSE payload size. The text is preserved only in the sidecar.
        if text or attachments:
            broadcast_payload: dict = {
                'type': 'user_input',
                'text': text,
                'timestamp': user_msg_ts,
            }
            if attachments:
                broadcast_payload['attachments'] = [
                    {
                        'number': att.get('number'),
                        'command': att.get('command'),
                        'title': att.get('title'),
                    }
                    for att in attachments
                ]
            terminal_sse_channel.broadcast(broadcast_payload)

        result = claude_process.send_input(
            text, images=images, attachments=attachments or None,
        )

        # AttachmentsSidecar handles no-op when session_id is undetermined or there is no attachment.
        if attachments and result.get('ok'):
            try:
                AttachmentsSidecar(claude_process.session_id or '').append(
                    user_msg_ts, attachments,
                )
            except Exception as exc:  # noqa: BLE001 — sidecar IO is best-effort
                logger.error('attachments sidecar append failed: %s', exc)

        self._send_json(result)

    @api_endpoint("T", "kill")
    def _handle_terminal_kill(self) -> None:
        """터미널 세션 종료 엔드포인트를 처리한다.

        POST /terminal/kill: Claude CLI 프로세스를 종료한다.

        프로세스 미시작 시 409 Conflict를 반환한다.

        method: POST
        url: /terminal/kill
        domain: T
        handler: TerminalHandlerMixin._handle_terminal_kill
        request: body none
        response_ok: {ok: true, ...kill result}
        response_error: {ok: false, error: str}
        status_codes: 200, 409
        auth: none (local-only) — user-triggered
        side_effects: SIGTERM Claude CLI subprocess
        sse_events: process_exit (TerminalSSEChannel system event)
        """
        if claude_process.status == 'stopped':
            self._send_error(409, 'Claude process not running')
            return

        result = claude_process.kill()
        self._send_json(result)

    @api_endpoint("T", "command")
    def _handle_terminal_command(self) -> None:
        """슬래시 명령어 전달 엔드포인트를 처리한다.

        POST /terminal/command: 클라이언트에서 전송한 슬래시 명령어를 Claude CLI stdin에
        전달한다. 기존 send_input() 메서드를 재사용하여 NDJSON 엔벨로프로 전송한다.

        요청 본문: {"command": "/clear"}
        선택 필드: "session_id" (현재 미사용, 메인 세션 전용)

        프로세스 미시작 시 409 Conflict를 반환한다.

        method: POST
        url: /terminal/command
        domain: T
        handler: TerminalHandlerMixin._handle_terminal_command
        request: body {command: str (starts with /)}
        response_ok: {ok: true, ...send_input result}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 409
        auth: none (local-only)
        side_effects: feed slash command to Claude CLI stdin
        sse_events: stdout / result (downstream Claude output)
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

    @api_endpoint("T", "permission")
    def _handle_terminal_permission(self) -> None:
        """permission 요청에 대한 승인/거부 응답 엔드포인트를 처리한다.

        POST /terminal/permission
        요청 본문: {"request_id": "...", "decision": "allow"|"deny"}
        선택 필드: "session_id" (워크플로우 세션용)

        session_id가 있으면 workflow_registry에서 해당 세션의 프로세스를 사용하고,
        없으면 claude_process(메인 터미널)를 사용한다.

        프로세스 미실행 시 409 Conflict, 잘못된 요청 시 400 Bad Request를 반환한다.

        method: POST
        url: /terminal/permission
        domain: T
        handler: TerminalHandlerMixin._handle_terminal_permission
        request: body {request_id: str, decision: allow|deny, session_id?: str}
        response_ok: {ok: true, ...response result}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 404, 409
        auth: none (local-only)
        side_effects: forward control_response to Claude CLI subprocess
        sse_events: none (closes pending permission prompt)
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

    @api_endpoint("T", "interrupt")
    def _handle_terminal_interrupt(self) -> None:
        """현재 응답 생성 중단 엔드포인트를 처리한다.

        POST /terminal/interrupt: Claude CLI 프로세스에 SIGINT를 전송한다.
        프로세스를 종료하지 않고 현재 응답 생성만 중단한다.

        세션 보존 보장:
        - 이 엔드포인트는 ``claude_process.interrupt()`` 호출만 수행한다.
        - ``claude_process._status``, ``claude_process._session_id``,
          conversation history 등 세션 식별자나 상태 필드를 변경하지 않는다.
        - 따라서 SIGINT 이후 클라이언트가 새로고침해도 conversation history 를
          jsonl 에서 그대로 복원할 수 있다.

        프로세스가 stopped 상태이면 409 Conflict를 반환한다.

        method: POST
        url: /terminal/interrupt
        domain: T
        handler: TerminalHandlerMixin._handle_terminal_interrupt
        request: body none
        response_ok: {ok: true, ...interrupt result}
        response_error: {ok: false, error: str}
        status_codes: 200, 409
        auth: none (local-only) — ESC key trigger
        side_effects: SIGINT to Claude CLI subprocess (session preserved)
        sse_events: system (subtype=user_input_interrupted)
        """
        if claude_process.status == 'stopped':
            self._send_error(409, 'Claude process not running')
            return

        result = claude_process.interrupt()
        self._send_json(result)
