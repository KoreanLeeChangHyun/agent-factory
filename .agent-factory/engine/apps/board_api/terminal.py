"""TerminalHandlerMixin — /terminal/* endpoints."""

from __future__ import annotations

import datetime
import json
import os
import time
import uuid
from urllib.parse import parse_qs, urlparse

from board.server.runtime import state as runtime_state
from board.server.support.common import api_endpoint, logger, _get_git_branch, server_debug_log
from board.server.channels.event_filter import is_user_visible
from board.server.channels.terminal_channel import _resolve_last_event_id
from board.server.processes.brain_process import validate_images
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

    Give a turn_id field to the chronological render events array and return it as is.

    1:1 simplification rule (1 user event = 1 turn):
    - Whenever a user event appears, a new turn_id is unconditionally started.
      Timestamp adjacency (gap threshold) / turn_has_assistant branch is discarded.
    - tool_result is a user role, but is treated as part of assistant turn
      Does not start a new turn.
    - The assistant/tool ​​event inherits the previous user turn_id.
    - turn_id format: f"hist-{ev_timestamp}" — based on user event timestamp
      Deterministic ID. Even after refreshing, the same event receives the same ID.

    Orphan handling:
    - In the edge case where the first event is assistant, 'hist-orphan' is assigned.

    side-effect: The 'turn_id' key is added (in-place) to each ev dict.
    The return value returns the same list for convenience.
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

    Only plain text is extracted from tool_result content.

    content is (a) a string or (b) an array [{type:text|image, ...}, ...].
    The image block is excluded.
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

    Determines user messages that need to be hidden in the history, such as slash command wrappers and system-reminder.
    """
    stripped = text.lstrip()
    if stripped.startswith(_TITLE_SKIP_PREFIXES):
        return True
    if text in _TITLE_SKIP_EXACT:
        return True
    return False


def _build_render_events(data: dict) -> list[dict]:
    """internal helper — not exposed as endpoint.

    Each jsonl line is expanded into 0~N render events.

    One assistant message can contain multiple blocks thinking + text + tool_use
    Therefore, events equal to the number of blocks are returned. Empty text, system wrapper user
    Messages are excluded.

    Return event schema:
        - role: 'user' | 'assistant'
        - kind: 'text' | 'thinking' | 'tool_use' | 'tool_result'
        - text: text (excluding tool_use)
        - tool_use_id: kind in {tool_use, tool_result}
        - name: kind == 'tool_use'
        - input: kind == 'tool_use' (dict)
        - is_error: kind == 'tool_result' (bool)
        - timestamp: ISO 8601 (maintain original)
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

    Extract (title, branch) from the jsonl file in one scan.

    title: First valid user message (filter rules are the same as existing _extract_session_title)
    branch: The value of the most recent ``gitBranch`` field (empty string if none)

    - Messages (tool results) including toolUseResult are skipped from title candidates.
    - Skip the slash command wrapper (<command-*>) but leave the flag set.
      Markdown that immediately begins with `# ` is considered as command .md body injection and is further skipped.
    - Skip local commands/system reminder wrappers as well
    - Skip the resume initialization template message
    - Only checks up to _TITLE_SCAN_MAX_LINES lines (branch is also extracted only in the same range)
    - If the title is not complete (None, branch), it is returned → The caller decides to exclude the result.
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
        """Handles terminal-only SSE endpoints.

        From TerminalSSEChannel for path /terminal/events
        Claude CLI Streams stdout events to the client.
        It uses a completely independent channel from the existing /events SSE.

        method: GET
        url: /terminal/events
        domain: T
        handler: TerminalHandlerMixin._handle_terminal_sse
        request: query {last_event_id?: int, skip_replay?: bool}
        response_ok: text/event-stream (TerminalSSEChannel)
        response_error: n/a (HTTP keep-alive stream)
        status_codes: 200
        auth: none (local-only)
        side_effects: register self.wfile to runtime_state.terminal_sse_channel
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

        runtime_state.terminal_sse_channel.add(
            self.wfile,
            last_event_id=last_event_id,
            skip_replay=skip_replay,
        )
        try:
            while True:
                time.sleep(0.25)
                client_lock = runtime_state.terminal_sse_channel.get_lock(self.wfile)
                if client_lock is None:
                    break
                try:
                    with client_lock:
                        self.wfile.write(b': heartbeat\n\n')
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break
        finally:
            runtime_state.terminal_sse_channel.remove(self.wfile)

    @api_endpoint("T", "status")
    def _handle_terminal_status(self) -> None:
        """Processes the terminal status inquiry endpoint.

        GET /terminal/status: Returns the current status of the Claude process as JSON.

        method: GET
        url: /terminal/status
        domain: T
        handler: TerminalHandlerMixin._handle_terminal_status
        request: query none
        response_ok: {status, session_id, model, permission_mode, branch, clients, awaiting_response}
        response_error: n/a (always 200)
        status_codes: 200
        auth: none (local-only)
        side_effects: read runtime_state.brain_process snapshot
        sse_events: none
        """
        project_root = os.getcwd()
        awaiting = bool(runtime_state.brain_process.awaiting_response)
        server_debug_log('status.response', {
            'status': runtime_state.brain_process.status,
            'session_id': runtime_state.brain_process.session_id,
            'awaiting_response': awaiting,
        })
        self._send_json({
            'status': runtime_state.brain_process.status,
            'session_id': runtime_state.brain_process.session_id,
            'last_session_id': runtime_state.brain_process.session_id,
            'model': runtime_state.brain_process.model,
            'permission_mode': runtime_state.brain_process.permission_mode,
            'provider': runtime_state.brain_process.provider,
            'branch': _get_git_branch(project_root),
            'clients': runtime_state.terminal_sse_channel.client_count,
            # Signal for the client to determine spinner/input lock recovery after refresh.
            # True after sending user input until receiving the result. Process status alone
            # Judgment during creation is impossible (since the status remains 'idle' even after the result).
            'awaiting_response': awaiting,
        })

    @api_endpoint("T", "sessions")
    def _handle_terminal_sessions(self) -> None:
        """Processes the session list query endpoint.

        GET /terminal/sessions: from directory ~/.claude/projects/<project-path>/
        All .jsonl files are scanned in descending order based on mtime and returned as a JSON array.
        The title field is extracted by parsing the first valid user message from each file.
        Temporary/initialized sessions without valid messages are excluded from the results.

        Response item:
            session_id: UUID (extracted from file name)
            last_active: mtime based ISO 8601 format time
            is_current: Matches a session that is currently "running" (status != 'stopped')
            is_last: Whether the last session indicated by ``.last-session-id``
                     (Restore candidates that remain even in stopped state)
            title: First valid user message (maximum 100 characters)
            branch: Last ``gitBranch`` value of session jsonl ("" if not present)
            size_bytes: jsonl file size (bytes)

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

        # Session with is_current = "Running now". If status == 'stopped'
        # The session_id restored from .last-session-id is 'last session' (is_last)
        # This is not ‘current session’.
        last_session_id = runtime_state.brain_process.session_id
        current_session_id = (
            last_session_id if runtime_state.brain_process.status != 'stopped' else ''
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
        """Processes session conversation history inquiry endpoint.

        GET /terminal/history?session_id=<uuid>[&since=<iso-timestamp>]:
        Read the file ``~/.claude/projects/<project-slug>/<session_id>.jsonl``
        Returns as a render event array.

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

        jsonl events in 4 types: text / thinking / tool_use / tool_result
        Expand and restore to the same granularity as SSE Live. If ``since`` is given
        Only events with timestamps larger than the relevant point in time are returned (supplementing the reconnection gap).

        The ``last_usage`` / ``last_cost_usd`` fields are independent of ``since``
        Returns the most recent value across sessions. When reconnecting, the client
        This is for restoring the state initialized to 0 with ``resetTokens()``.
        This is because the current total is always needed regardless of whether there is a gap or not.

        Response schema:
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
        if runtime_state.brain_process.session_id == session_id:
            in_flight = runtime_state.brain_process.get_in_flight_snapshot()
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
        sid_match = runtime_state.brain_process.session_id == session_id
        awaiting_for_log = bool(runtime_state.brain_process.awaiting_response)
        if sid_match:
            if runtime_state.brain_process.awaiting_response:
                # If the last event is user and there is no in_flight event
                if events and not events[-1].get('in_flight'):
                    last_ev = events[-1]
                    # A user event (interrupted=true) stopped by ESC is not an unresolved turn.
                    # Defense Augmentation: awaiting_response can fail to fall to false.
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
        """Handles the terminal session start endpoint.

        POST /terminal/start: Starts the Claude CLI process.
        Additional CLI arguments can be specified in the request body in the form {"args": [...]}.

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

        runtime_state.configure_brain_process(os.getcwd())
        result = runtime_state.brain_process.spawn(extra_args)

        # When resuming, Claude CLI does not issue an init event until the first input.
        # There was a problem where session_id was returned as an empty value. The resume target UUID is
        # Since it is already known, it is reflected in the response and process._session_id
        # Allows you to set termSessionId right away. Afterwards, when the init event comes
        # It is the same value or overwritten with a new UUID that the server falls back on.
        if resume_session_id and result.get('ok') and not result.get('session_id'):
            result['session_id'] = resume_session_id
            runtime_state.brain_process.set_session_id(resume_session_id)

        self._send_json(result)

    @api_endpoint("T", "input")
    def _handle_terminal_input(self) -> None:
        """Processes terminal input transmission endpoints.

        POST /terminal/input: Sends a user message to Claude CLI.
        Request body: {"text": "user message"}

        If the process does not start, 409 Conflict is returned.

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
        if runtime_state.brain_process.status == 'stopped':
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
            validation_error = validate_images(images)
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
            runtime_state.terminal_sse_channel.broadcast(broadcast_payload)

        result = runtime_state.brain_process.send_input(
            text, images=images, attachments=attachments or None,
        )

        # AttachmentsSidecar handles no-op when session_id is undetermined or there is no attachment.
        if attachments and result.get('ok'):
            try:
                AttachmentsSidecar(runtime_state.brain_process.session_id or '').append(
                    user_msg_ts, attachments,
                )
            except Exception as exc:  # noqa: BLE001 — sidecar IO is best-effort
                logger.error('attachments sidecar append failed: %s', exc)

        self._send_json(result)

    @api_endpoint("T", "kill")
    def _handle_terminal_kill(self) -> None:
        """Handles the terminal session termination endpoint.

        POST /terminal/kill: Terminates the Claude CLI process.

        If the process does not start, 409 Conflict is returned.

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
        if runtime_state.brain_process.status == 'stopped':
            self._send_error(409, 'Claude process not running')
            return

        result = runtime_state.brain_process.kill()
        self._send_json(result)

    @api_endpoint("T", "command")
    def _handle_terminal_command(self) -> None:
        """Processes the slash command delivery endpoint.

        POST /terminal/command: Slash command sent from the client to Claude CLI stdin.
        Deliver. Reuse the existing send_input() method to send with an NDJSON envelope.

        Request body: {"command": "/clear"}
        Optional field: "session_id" (currently unused, main session only)

        If the process does not start, 409 Conflict is returned.

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
        if runtime_state.brain_process.status == 'stopped':
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

        result = runtime_state.brain_process.send_input(command)
        self._send_json(result)

    @api_endpoint("T", "permission")
    def _handle_terminal_permission(self) -> None:
        """Processes approval/denial response endpoints for permission requests.

        POST /terminal/permission
        Request body: {"request_id": "...", "decision": "allow"|"deny"}
        Optional field: "session_id" (for workflow sessions)

        If session_id is present, use the process of that session in runtime_state.workflow_registry,
        If not, use runtime_state.brain_process (main terminal).

        If the process is not executed, 409 Conflict is returned, and if an incorrect request is made, 400 Bad Request is returned.

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
            session = runtime_state.workflow_registry.get(session_id)
            if session is None:
                self._send_error(404, f'Session not found: {session_id}')
                return
            process = session.process
        else:
            process = runtime_state.brain_process

        if process.status == 'stopped':
            self._send_error(409, 'Claude process not running')
            return

        result = process.send_permission_response(request_id, decision, session_id)
        self._send_json(result)

    @api_endpoint("T", "interrupt")
    def _handle_terminal_interrupt(self) -> None:
        """Handles the current response generation aborted endpoint.

        POST /terminal/interrupt: Sends SIGINT to the Claude CLI process.
        Does not terminate the process, but only stops generating the current response.

        Guaranteed session retention:
        - This endpoint only performs calls to ``runtime_state.brain_process.interrupt()``.
        - Do not change session identifiers or status fields such as conversation history.
        - Therefore, even if the client refreshes after SIGINT, the conversation history
          It can be restored as is in jsonl.

        If the process is stopped, 409 Conflict is returned.

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
        if runtime_state.brain_process.status == 'stopped':
            self._send_error(409, 'Claude process not running')
            return

        result = runtime_state.brain_process.interrupt()
        self._send_json(result)
