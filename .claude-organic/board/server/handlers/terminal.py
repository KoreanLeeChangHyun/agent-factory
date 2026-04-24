"""TerminalHandlerMixin — /terminal/* endpoints."""

from __future__ import annotations

import datetime
import json
import os
import time
import uuid
from urllib.parse import parse_qs, urlparse

from ..state import terminal_sse_channel, claude_process, workflow_registry
from .._common import logger, _get_git_branch
from ..terminal_channel import _resolve_last_event_id
from ..claude_process import _validate_images


_HISTORY_SKIP_TYPES = frozenset({
    'queue-operation', 'last-prompt', 'summary', 'attachment',
    'progress', 'file-history-snapshot', 'system', 'permission-mode',
})


def _extract_tool_result_text(content: object) -> str:
    """tool_result content에서 평문 텍스트만 추출한다.

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
    """슬래시 커맨드 래퍼, system-reminder 등 히스토리에서 숨겨야 할 user 메시지를 판별한다."""
    stripped = text.lstrip()
    if stripped.startswith(_TITLE_SKIP_PREFIXES):
        return True
    if text in _TITLE_SKIP_EXACT:
        return True
    return False


def _build_render_events(data: dict) -> list[dict]:
    """jsonl 라인 한 줄을 0~N개의 렌더 이벤트로 전개한다.

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
    # Claude Code 하네스가 주입한 Skill/command 래퍼 user 메시지는
    # isMeta=True 로 표시된다. 실제 사용자 입력/tool_result 에는 없는 필드이므로
    # 이 플래그 하나로 정확히 구분 가능 (SKILL.md 본문이 하늘색 term-user 블록으로
    # 터미널에 노출되던 버그 원인).
    if data.get('isMeta') is True:
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

    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get('type')
        if btype == 'text':
            text = (block.get('text') or '').strip()
            if not text:
                continue
            if role == 'user' and _is_system_wrapper_text(text):
                continue
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
    "첫 메시지입니다. '세션이 초기화 되었습니다.' 라고만 답하세요.",
)
_TITLE_MAX_LENGTH = 100
_TITLE_SCAN_MAX_LINES = 300


def _extract_session_meta(filepath: str) -> tuple[str | None, str]:
    """jsonl 파일에서 (title, branch) 를 한 번의 스캔으로 추출한다.

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

                # branch: 모든 라인에서 가능한 만큼 갱신 (마지막 등장 값)
                if isinstance(event.get('gitBranch'), str) and event['gitBranch']:
                    branch = event['gitBranch']

                if title is not None:
                    # title 이미 확정 → branch 만 계속 추적
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
        logger.debug('세션 메타 추출 실패 (%s): %s', filepath, err)
    return title, branch


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

        # ``skip_replay=1`` 쿼리 플래그: 클라이언트가 REST /terminal/history 로
        # 과거를 이미 복원했다는 선언. 서버는 링버퍼 재생을 생략하고 라이브
        # 이벤트만 전달한다. 메인 터미널이 첫 연결 시 사용한다.
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
            # 새로고침 후 클라이언트가 스피너/입력 잠금 복구를 판단하는 신호.
            # 사용자 입력 전송 후 result 수신 전까지 True. claude_process._status 만으로는
            # 생성 중 판정이 불가능 (result 후에도 계속 'idle' 상태로 유지되므로).
            'awaiting_response': bool(getattr(claude_process, '_awaiting_response', False)),
        })

    def _handle_terminal_sessions(self) -> None:
        """세션 목록 조회 엔드포인트를 처리한다.

        GET /terminal/sessions: ~/.claude/projects/<project-path>/ 디렉터리에서
        .jsonl 파일을 mtime 기준 내림차순으로 전수 스캔하여 JSON 배열로 반환한다.
        각 파일에서 최초 유효 user 메시지를 파싱하여 title 필드를 추출한다.
        유효 메시지가 없는 임시/초기화 세션은 결과에서 제외한다.

        응답 항목:
            session_id: UUID (파일명에서 추출)
            last_active: mtime 기반 ISO 8601 형식 시각
            is_current: 현재 "실행 중"인 세션과 일치 여부 (status != 'stopped')
            is_last: ``.last-session-id`` 가 가리키는 마지막 세션 여부
                     (stopped 상태에도 유지되는 복원 후보)
            title: 첫 유효 user 메시지 (최대 100자)
            branch: 세션 jsonl 의 마지막 ``gitBranch`` 값 (없으면 "")
            size_bytes: jsonl 파일 크기 (바이트)
        """
        project_root = os.getcwd()

        # cwd 기반으로 ~/.claude/projects/ 하위 디렉터리 경로 산출
        # 예: /home/deus/workspace/claude -> -home-deus-workspace-claude
        home_dir = os.path.expanduser('~')
        project_slug = project_root.replace('/', '-')
        sessions_dir = os.path.join(home_dir, '.claude', 'projects', project_slug)

        # is_current = "지금 실행 중"인 세션. status == 'stopped' 인 경우
        # .last-session-id 에서 복원된 session_id 는 '마지막 세션'(is_last)
        # 이지 '현재 세션'이 아니다.
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
                    stem = entry.name[:-6]  # ".jsonl" 제거
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
            logger.debug('세션 디렉터리 스캔 실패: %s', e)
            self._send_json([])
            return

        # mtime 내림차순 정렬
        entries.sort(key=lambda x: x[0], reverse=True)

        result = []
        for mtime, session_id, filepath, size_bytes in entries:
            title, branch = _extract_session_meta(filepath)
            if title is None:
                # 제목 추출 실패 = 임시/초기화 세션으로 간주하여 제외
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

    def _handle_terminal_history(self) -> None:
        """세션 대화 히스토리 조회 엔드포인트를 처리한다.

        GET /terminal/history?session_id=<uuid>[&since=<iso-timestamp>]:
        ``~/.claude/projects/<project-slug>/<session_id>.jsonl`` 파일을 읽어
        렌더 이벤트 배열로 반환한다.

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

                    # assistant.message.usage — 각 API 호출 시점의 전체 컨텍스트
                    # 사용량 (델타 아님). 세션 전체에서 가장 마지막 값만 유지한다.
                    # SSE 라이브 경로(terminal_channel._build_stream_payload)와
                    # 동일하게 input_tokens + cache_read + cache_creation 합산을
                    # 사용해야 상태바 퍼센티지가 일관된다.
                    if msg_type == 'assistant':
                        msg = data.get('message')
                        if isinstance(msg, dict):
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

                    # result 타입: 세션 누적 비용(total_cost_usd) + 마지막 usage.
                    # 샘플 세션엔 없을 수 있음(상호작용 중이거나 subtype 에 따라).
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

                    # ISO 8601 문자열은 사전순 비교가 시간순과 일치한다.
                    for ev in line_events:
                        ts = ev.get('timestamp') or ''
                        if since and ts and ts <= since:
                            continue
                        events.append(ev)
                        if ts and ts > last_timestamp:
                            last_timestamp = ts
        except OSError as err:
            logger.debug('세션 히스토리 읽기 실패 (%s): %s', filepath, err)
            self._send_error(500, 'Failed to read session history')
            return

        # 현재 스트리밍 중인 assistant 메시지를 합친다 (jsonl 에는 아직 없음).
        # Claude CLI 는 메시지 완료 시점에만 jsonl 에 flush 하므로, 응답 생성
        # 도중 새로고침 시 부분 내용이 어디에도 없어 UI 에서 통째로 유실된다.
        # 이 캐시는 그 간격을 메꾼다. 마지막 block 만 `in_flight` 플래그를 달아
        # 클라이언트가 텍스트 버퍼에 시딩하도록 한다 (DOM 에 완성된 블록으로
        # 렌더하면 이어지는 live text_delta 가 별도 블록을 만들어 두 조각이 됨).
        if claude_process.session_id == session_id:
            in_flight = claude_process.get_in_flight_snapshot()
            if in_flight:
                in_flight_ts = in_flight.get('timestamp', '') or ''
                if not since or (in_flight_ts and in_flight_ts > since):
                    in_flight_events = _build_render_events(in_flight)
                    if in_flight_events:
                        in_flight_events[-1]['in_flight'] = True
                        # tool_use 가 in-flight 인 경우 partial_input_json 전달
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

        response: dict = {
            'session_id': session_id,
            'last_timestamp': last_timestamp,
            'events': events,
        }
        if last_usage is not None:
            response['last_usage'] = last_usage
        if last_cost_usd is not None:
            response['last_cost_usd'] = last_cost_usd

        self._send_json(response)

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
            extra_args = []

        result = claude_process.spawn(extra_args)

        # resume 시 Claude CLI가 첫 입력 전까지 init 이벤트를 내놓지 않는 경우가
        # 있어 session_id 가 빈 값으로 회신되던 문제가 있었다. resume 대상 UUID 는
        # 이미 알려져 있으므로 응답과 process._session_id 에 선반영하여 클라가
        # 곧바로 termSessionId 를 세팅할 수 있도록 한다. 이후 init 이벤트가 오면
        # 동일 값이거나 서버가 fallback 한 새 UUID 로 덮어쓴다.
        if resume_session_id and result.get('ok') and not result.get('session_id'):
            result['session_id'] = resume_session_id
            claude_process._session_id = resume_session_id

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
