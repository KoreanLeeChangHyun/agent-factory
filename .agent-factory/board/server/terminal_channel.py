"""TerminalSSEChannel — terminal per-session SSE (Remove REST /workflow/history)."""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable

from ._common import logger
from .event_filter import is_user_visible
from .sse_client_manager import _NDJSON_EVENT_MAP

# ---------------------------------------------------------------------------
# Workflow step detection patterns (stdout banner parsing)
# ---------------------------------------------------------------------------
_STEP_PATTERN = re.compile(
    r'(?:\[STEP\]\s+(PLAN|WORK|REPORT|DONE)'
    r'|║\s+\[●[^\]]*\]\s+(PLAN|WORK|REPORT|DONE))'
)
_INIT_PATTERN = re.compile(r'(?:\[INIT\]\s+|║\s+INIT:\s+)')
_PHASE_PATTERN = re.compile(
    r'(?:\[PHASE\]\s+(\d+)\s+(sequential|parallel)'
    r'|║\s+STATE:\s+Phase\s+(\d+)\s+(sequential|parallel))'
)
_FINISH_PATTERN = re.compile(
    r'News :\\[DONE\\]\\s+Workflow\\s+(Finished)'
    r'|\\s+DONE:\\s+Workflow\\s+(Finished)'
)


def _parse_last_event_id(headers: object) -> int:
    """parse Last-Event-ID in the HTTP request header.

    Browser EventSource automatically receives the ID of the last reception event when redirected
    send to Last-Event-ID header.

    Args:
        headers: HTTP request header objects

    Returns:
        Integer ID. -1 when there is no header or parsing failure.
    """
    try:
        raw = headers.get('Last-Event-ID')
        if raw is None:
            return -1
        return int(str(raw).strip())
    except (ValueError, AttributeError):
        return -1


def _parse_last_event_id_from_query(path: str) -> int:
    """parse the last event id parameter in the URL query string.

    EventSource API does not allow custom header injections,
    If the client reconnects the previous event ID to the query parameter instead of header
    Send header values( parse last event id)
    Adopt big side.

    Args:
        path: HTTP request path (include quarry, example: ``/terminal/events?last event id=42`)

    Returns:
        Integer ID. -1 when there is no parameter or parsing failure.
    """
    try:
        if '?' not in path:
            return -1
        from urllib.parse import parse_qs
        qs = parse_qs(path.split('?', 1)[1])
        raw = qs.get('last_event_id', [None])[0]
        if raw is None:
            return -1
        return int(str(raw).strip())
    except (ValueError, TypeError, AttributeError):
        return -1


def _resolve_last_event_id(headers: object, path: str) -> int:
    """returns the maximum value by interpreting last event id in header and query parameters.

    EventSource does not include the Last-Event-ID header when creating a new instance,
    The explicit query parameter path is the main path. The header path is a poly bag.
    """
    return max(_parse_last_event_id(headers), _parse_last_event_id_from_query(path))


class TerminalSSEChannel:
    """SSE broadcast channel dedicated to terminal output.

    Create an independent instance with the same interface as SSEClientManager,
    Provides /terminal/events-only streams without interfering with existing /events SSE.

    NDJSON Cheongk converts to SSE events to send it to all client connected.
    REST /workflow/history
    Restore jsonl files via endpoint.

    Attributes:
        clients: list of wfile objects associated
        lock: Client List Approach Lock
        client locks: per-client Lock Dix
    """

    def __init__(self, persist_path: str | None = None) -> None:
        """Add to cart

        Args:
            persist path: JSONL file path to save event. If None persist inactive.
        """
        self._clients: list = []
        self._lock: threading.Lock = threading.Lock()
        self._client_locks: dict = {}
        self._next_seq: int = 0
        self._persist_path: str | None = persist_path
        self._persist_lock: threading.Lock = threading.Lock()
        # stdout based workflow step detection
        self._step_buffer: str = ''
        self._current_step: str = ''
        self.on_step: Callable[[str, dict], None] | None = None

    def add(
        self,
        wfile: object,
        last_event_id: int = -1,
        skip_replay: bool = False,
    ) -> None:
        """Add client to live event stream.

        Ring Buffer play path was removed. REST /workflow/history
        executed in jsonl file via endpoint and this method is done in the new SSE client
        We only accept live events issued after registration.

        The ``skip replay` parameter keeps the signature for subcontract and does not affect the operation.
        `last event id` parameter is also maintained and is currently unused.

        Args:
            wfile: HTTP handler wfile (socket output stream)
            last event id:
            skip replay:
        """
        with self._lock:
            self._clients.append(wfile)
            self._client_locks[id(wfile)] = threading.Lock()

    def remove(self, wfile: object) -> None:
        """Remove the client.

        Args:
            wfile: wfile of client to remove
        """
        with self._lock:
            try:
                self._clients.remove(wfile)
            except ValueError:
                pass
            self._client_locks.pop(id(wfile), None)

    def get_lock(self, wfile: object) -> threading.Lock | None:
        """returns per-client lock to wfile.

        Args:
            wfile: client wfile to acquire lock

        Returns:
            Lock of the wfile. None if the client does not exist.
        """
        with self._lock:
            return self._client_locks.get(id(wfile))

    def broadcast(self, data: dict) -> None:
        """NDJSON messages are converted to SSE events to send them to all clients.

        Determine the appropriate SSE event name according to the message type NEWS
        - stream_event (text_delta) -> event: stdout
        - stream_event (input_json_delta) -> event: stdout
        - result -> event: result
        - system -> event: system
        - control_request -> event: permission
        - attachment (skill_listing) -> event: skill_listing
        - Other -> event: stdout (default)

        The client fails to send (connect break) will be removed from the list.

        Args:
            data: dirching NDJSON messages
        """
        if not is_user_visible(data):
            return
        event_name = self._classify_event(data)
        payload = self._build_payload(data, event_name)
        json_payload = json.dumps(payload, ensure_ascii=False)

        self._emit_event(event_name, json_payload)

        # file persist (restore when server restart) - use separate lock
        if self._persist_path is not None:
            try:
                line = json.dumps(data, ensure_ascii=False) + '\n'
                with self._persist_lock:
                    with open(self._persist_path, 'a', encoding='utf-8') as f:
                        f.write(line)
            except (OSError, TypeError) as exc:
                logger.error("terminal channel: %s", self._persist_path, exc)

        # stdout based workflow step detection
        self._detect_step_from_broadcast(event_name, payload)

    def _emit_event(self, event_name: str, json_payload: str) -> None:
        """Send SSE event to all client connected after seq id authorization.

        Ring Buffer storage and replay buffering logic was removed.
        """
        dead_clients: list = []
        with self._lock:
            seq_id = self._next_seq
            self._next_seq += 1
            message = f"id: {seq_id}\nevent: {event_name}\ndata: {json_payload}\n\n"
            encoded = message.encode('utf-8')
            clients_snapshot = list(self._clients)

        for wfile in clients_snapshot:
            wfile_id = id(wfile)
            client_lock = self._client_locks.get(wfile_id)
            if client_lock is None:
                continue
            try:
                with client_lock:
                    wfile.write(encoded)
                    wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                dead_clients.append(wfile)

        if dead_clients:
            with self._lock:
                for wfile in dead_clients:
                    try:
                        self._clients.remove(wfile)
                    except ValueError:
                        pass
                    self._client_locks.pop(id(wfile), None)

    def _classify_event(self, data: dict) -> str:
        """Set the SSE event name from the NDJSON message type.

        Args:
            data: dirching NDJSON messages

        Returns:
            SSE Event Name String
        """
        msg_type = data.get('type', '')

        if msg_type == 'user_input':
            return 'user_input'

        if msg_type == 'stream_event':
            delta_type = (
                data.get('event', {}).get('delta', {}).get('type', '')
            )
            return _NDJSON_EVENT_MAP.get(delta_type, 'stdout')

        if msg_type == 'assistant':
            return 'stdout'

        if msg_type == 'attachment':
            attachment_type = data.get('attachment', {}).get('type', '')
            if attachment_type == 'skill_listing':
                return 'skill_listing'
            return 'stdout'

        return _NDJSON_EVENT_MAP.get(msg_type, 'stdout')

    def _build_payload(self, data: dict, event_name: str) -> dict:
        """SSE configures the payload to the client.

        Args:
            data: original NDJSON message dict
            event name: Crystal SSE Event Name

        Returns:
            Doc
        """
        if event_name == 'user_input':
            # timetamp is delivered together and frontend is used in cardender and self-echo guard.
            payload: dict = {'text': data.get('text', '')}
            if data.get('timestamp'):
                payload['timestamp'] = data['timestamp']
            attachments = data.get('attachments')
            if attachments:
                payload['attachments'] = attachments
            return payload
        if event_name == 'skill_listing':
            return self._build_skill_listing_payload(data)
        if event_name == 'stdout':
            return self._build_stdout_payload(data)
        if event_name == 'result':
            return self._build_result_payload(data)
        if event_name == 'system':
            return self._build_system_payload(data)
        if event_name == 'permission':
            req = data.get('request', {})
            return {
                'kind': 'permission',
                'request_id': data.get('request_id', ''),
                'tool_name': req.get('tool_name', ''),
                'description': req.get('description', ''),
                'input': req.get('input', {}),
                'raw': data,
            }
        if event_name == 'rate_limit':
            info = data.get('rate_limit_info', {}) or {}
            return {
                'kind': 'rate_limit',
                'status': info.get('status', 'unknown'),
                'resets_at': info.get('resetsAt'),
                'rate_limit_type': info.get('rateLimitType', ''),
                'is_using_overage': bool(info.get('isUsingOverage', False)),
                'overage_status': info.get('overageStatus', ''),
                'session_id': data.get('session_id', ''),
            }
        if event_name == 'error':
            return {
                'kind': 'error',
                'message': data.get('message', 'Unknown error'),
                'exit_code': data.get('exit_code'),
                'session_id': data.get('session_id', ''),
            }
        # Raw data delivery
        return {'kind': data.get('type', 'unknown'), 'raw': data}

    def _build_skill_listing_payload(self, data: dict) -> dict:
        """Configuring the skill listing event payload.

        Args:
            data: original NDJSON message dict (type == 'attachment')

        Returns:
            Skill listing Payload dict
        """
        attachment = data.get('attachment', {})
        return {
            'kind': 'skill_listing',
            'content': attachment.get('content', ''),
            'skillCount': attachment.get('skillCount', 0),
            'isInitial': attachment.get('isInitial', False),
        }

    def _build_stdout_payload(self, data: dict) -> dict:
        """Configuring the stdout event payload.

        stream event text delta,
        Recovers the entire text from the assistant message.

        Args:
            data: original NDJSON message dict

        Returns:
            Stdout Payload dict
        """
        msg_type = data.get('type', '')

        if msg_type == 'stream_event':
            event = data.get('event', {})
            delta = event.get('delta', {})
            delta_type = delta.get('type', '')

            if delta_type == 'text_delta':
                return {
                    'kind': 'text_delta',
                    'chunk': delta.get('text', ''),
                }
            if delta_type == 'input_json_delta':
                return {
                    'kind': 'input_json_delta',
                    'chunk': delta.get('partial_json', ''),
                }
            # content block start, message start, message delta, etc.
            payload = {
                'kind': event.get('type', 'stream_event'),
                'raw': event,
            }
            # Usage Location is different from event type NEWS
            #   - message_start: event.message.usage (input_tokens + cache_* + output_tokens=1)
            #   - message delta: event.usage (output tokens only, no input)
            # input 0 in the event(message delta) without send
            # setInputTokens(0) = 0% We use cookies to give you the best experience on our website.
            event_usage = event.get('usage') or event.get('message', {}).get('usage')
            if event_usage:
                payload_usage: dict = {}
                has_input = any(
                    k in event_usage
                    for k in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')
                )
                if has_input:
                    payload_usage['input_tokens'] = (
                        event_usage.get('input_tokens', 0)
                        + event_usage.get('cache_read_input_tokens', 0)
                        + event_usage.get('cache_creation_input_tokens', 0)
                    )
                if 'output_tokens' in event_usage:
                    payload_usage['output_tokens'] = event_usage['output_tokens']
                if payload_usage:
                    payload['usage'] = payload_usage
            return payload

        if msg_type == 'assistant':
            content = data.get('message', {}).get('content', [])
            text_parts = [
                block.get('text', '')
                for block in content
                if block.get('type') == 'text'
            ]
            payload = {
                'kind': 'assistant',
                'text': ''.join(text_parts),
            }
            usage = data.get('message', {}).get('usage', {})
            if usage:
                payload['usage'] = {
                    'input_tokens': (usage.get('input_tokens', 0)
                        + usage.get('cache_read_input_tokens', 0)
                        + usage.get('cache_creation_input_tokens', 0)),
                    'output_tokens': usage.get('output_tokens', 0),
                }
            return payload

        return {'kind': msg_type or 'unknown', 'raw': data}

    def _build_result_payload(self, data: dict) -> dict:
        """result Compose event payload.

        Args:
            data: original NDJSON message dict

        Returns:
            result payload dict
        """
        usage = data.get('usage', {})
        return {
            'kind': 'result',
            'done': True,
            'subtype': data.get('subtype', ''),
            'is_error': data.get('is_error', False),
            'result': data.get('result', ''),
            'duration_ms': data.get('duration_ms', 0),
            'session_id': data.get('session_id', ''),
            'cost_usd': data.get('total_cost_usd', 0),
            'input_tokens': usage.get('input_tokens', 0)
                + usage.get('cache_read_input_tokens', 0)
                + usage.get('cache_creation_input_tokens', 0),
            'output_tokens': usage.get('output_tokens', 0),
        }

    # subtype field contract where client approaches to top-level.
    # If you do not specify this table for new subtypes, you must access raw oil from the client.
    _SYSTEM_TOP_LEVEL_FIELDS: dict[str, tuple[str, ...]] = {
        'task_started': ('task_id', 'tool_use_id', 'description', 'last_tool_name', 'task_count', 'task_index'),
        'task_progress': ('task_id', 'tool_use_id', 'description', 'last_tool_name'),
        'task_notification': ('task_id', 'tool_use_id', 'status', 'summary'),
        'process_exit': ('exit_code',),
        # The last user message timestamp of the ESC interflow point is exposed to the client.
        # The client grants .interrupted markers to this timestamp and the matching user.
        'user_input_interrupted': ('timestamp',),
    }

    def _build_system_payload(self, data: dict) -> dict:
        """Configuring system event payload.

        subtype the field where the client approaches to top-level
        ' SYSTEM TOP LEVEL FIELDS'
        Clients can only perform simple approaches without raw crude.

        Args:
            data: original NDJSON message dict

        Returns:
            system dict
        """
        subtype = data.get('subtype', '')
        payload: dict = {
            'kind': 'system',
            'subtype': subtype,
            'session_id': data.get('session_id', ''),
            'raw': data,
        }
        for key in self._SYSTEM_TOP_LEVEL_FIELDS.get(subtype, ()):
            if key in data:
                payload[key] = data[key]
        return payload

    @property
    def client_count(self) -> int:
        """Returns the number of client currently connected."""
        with self._lock:
            return len(self._clients)

    @property
    def current_step(self) -> str:
        """return the current workflow step."""
        return self._current_step

    # ------------------------------------------------------------------
    # Phase 1: workflow_step SSE event
    # ------------------------------------------------------------------

    def emit_step(self, step_name: str, detail: dict | None = None) -> None:
        """publish workflow step SSE events and record jsonl files.

        jsonl jsonl

        Args:
            step name: stage name (init, plan, work, report, done)
            detail: Additional information dict (phase, mode, trigger, etc.)
        """
        prev = self._current_step
        self._current_step = step_name
        payload: dict = {'step': step_name, 'prev_step': prev}
        if detail:
            payload.update(detail)
        self._emit_event('workflow_step', json.dumps(payload, ensure_ascii=False))

        # jsonl recording (broadcast mirror)
        if self._persist_path is not None:
            try:
                record = {'type': 'workflow_step', 'step': step_name, 'prev_step': prev}
                if detail:
                    record.update(detail)
                line = json.dumps(record, ensure_ascii=False) + '\n'
                with self._persist_lock:
                    with open(self._persist_path, 'a', encoding='utf-8') as f:
                        f.write(line)
            except (OSError, TypeError) as exc:
                logger.error("terminal channel: emit step persist write failed (%s): %s", self._persist_path, exc)

        if self.on_step:
            try:
                self.on_step(step_name, payload)
            except Exception:
                pass

    def _detect_step_from_broadcast(self, event_name: str, payload: dict) -> None:
        """Detects workflow stage transitions in the broadcast stdout event."""
        if event_name != 'stdout':
            return
        kind = payload.get('kind', '')
        if kind == 'text_delta':
            self._step_buffer += payload.get('chunk', '')
        elif kind == 'assistant':
            self._step_buffer += payload.get('text', '')
        else:
            return
        # Contains a line with a running unit, pattern matching
        while '\n' in self._step_buffer:
            line, self._step_buffer = self._step_buffer.split('\n', 1)
            self._check_step_line(line.strip())

    def _check_step_line(self, line: str) -> None:
        """Check the workflow stage pattern in a single stdout line."""
        if not line:
            return
        m = _STEP_PATTERN.search(line)
        if m:
            step = (m.group(1) or m.group(2)).lower()
            self.emit_step(step, {'trigger': 'stdout'})
            return
        m = _INIT_PATTERN.search(line)
        if m:
            self.emit_step('init', {'trigger': 'stdout'})
            return
        m = _PHASE_PATTERN.search(line)
        if m:
            phase_num = int(m.group(1) or m.group(3))
            mode = m.group(2) or m.group(4)
            self.emit_step(self._current_step, {
                'trigger': 'stdout',
                'phase': phase_num,
                'mode': mode,
            })
            return
        m = _FINISH_PATTERN.search(line)
        if m:
            result = 'success' if (m.group(1) or m.group(2)) == 'Application' else 'failure'
            self.emit_step('done', {'trigger': 'stdout', 'result': result})


# ---------------------------------------------------------------------------
# Image Validation Helper
# ---------------------------------------------------------------------------

_ALLOWED_MEDIA_TYPES = {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}
