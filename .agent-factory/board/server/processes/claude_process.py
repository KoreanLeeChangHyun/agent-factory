"""ClaudeProcess — wraps Claude Code CLI subprocess with JSON streaming."""

from __future__ import annotations

import copy
import datetime
import json
import os
import signal
import subprocess
import threading

from board.server._common import logger, server_debug_log
from board.server.channels.terminal_channel import TerminalSSEChannel


_ALLOWED_MEDIA_TYPES = {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}


def _compose_user_content(
    text: str,
    images: list[dict] | None,
    attachments: list[dict] | None,
) -> str | list:
    """Create a user message content.

    text block → text block → image block
    returns the value to the Claude CLI NDJSON Envelope's `content` field.

    attachments and images are all None/bin arrays and text if simple strings
    returns to maintain the same envelope structure as the existing text-only path.

    Args:
        text: user free input text. Allows empty strings.
        images: List of image blocks. Each item ``{"data": str, "media type": str}`.
                None No images.
        attachments: list of attachment tickets. Each item contains a minimum ``{"number": dict.
                     None or empty arrangements are not attached.

    Returns:
        content field value: list[dict], str if you need block array.
    """
    # Attach validity: list check (None / [] is not attached)
    valid_attachments: list[dict] = []
    if isinstance(attachments, list):
        for att in attachments:
            if isinstance(att, dict) and 'number' in att:
                valid_attachments.append(att)

    # image blocks synthesized (external logic)
    image_blocks: list[dict] = []
    if isinstance(images, list):
        image_blocks = [
            {
                'type': 'image',
                'source': {
                    'type': 'base64',
                    'media_type': img['media_type'],
                    'data': img['data'],
                },
            }
            for img in images
        ]

    # If you do not have an attachment image → Simple string (external text-only path)
    if not valid_attachments and not image_blocks:
        return text

    # Contact Person: Mr. Jerry Jiang
    text_blocks: list[dict] = [{'type': 'text', 'text': text}] if text else []

    attachment_text_blocks: list[dict] = [
        {
            'type': 'text',
            'text': (
                f"[Field 0    ]   FIELD 1   \\n\\n"
                f"## prompt\n{a.get('prompt', '')}\n\n"
                f"## report\n{a.get('report', '')}"
            ),
        }
        for a in valid_attachments
    ]

    return text_blocks + attachment_text_blocks + image_blocks


def _validate_images(images: list) -> str | None:
    """Verify the validity of the image list.

    Check if data (chart) and allowed media type exists in each item.

    Args:
        images: List of image items to validate.

    Returns:
        Error message string when not valid, if valid, None.
    """
    if not isinstance(images, list):
        return 'Invalid "images" field: must be a list'

    for i, img in enumerate(images):
        if not isinstance(img, dict):
            return f'Invalid image at index {i}: must be an object'

        data = img.get('data')
        if not isinstance(data, str) or not data:
            return f'Invalid image at index {i}: missing or invalid "data" field'

        media_type = img.get('media_type')
        if media_type not in _ALLOWED_MEDIA_TYPES:
            allowed = ', '.join(sorted(_ALLOWED_MEDIA_TYPES))
            return (
                f'Invalid image at index {i}: '
                f'"media_type" must be one of [{allowed}], got "{media_type}"'
            )

    return None


# ---------------------------------------------------------------------------
# Claude Process Manager
# ---------------------------------------------------------------------------


class ClaudeProcess:
    """Claude CLI Process Lifecycle Manager.

    execute Claude CLI with subprocess.Popen, through stdin/stdout
    NDJSON manages two-way communication.

    Attributes:
        process: subprocess.Popen instances (unless before the procedure starts)
        session id: Session ID extracted from system/init message
        status: Process Status (stopped/running/idle)
        stdin lock: stdin access protection lock
        stdout thread: stdout read daemon thread
        channel: SSE broadcast channel
    """

    def __init__(self, channel: TerminalSSEChannel, persist_file: str | None = None) -> None:
        """Add to cart

        Args:
            channel: TerminalSSEChannel instance to broadcast NDJSON events
            persist file: session id file path (optional)
        """
        self._process: subprocess.Popen | None = None
        self._session_id: str = ''
        self._model: str = ''
        self._permission_mode: str = ''
        self._status: str = 'stopped'
        # Stage 3-B — production-line subprocess returns outside status override.
        # None General ClaudeProcess (self. process tracking). 'running'/'stopped' set time
        # status property returns first (board side is process direct spawn mode).
        self._external_status: str | None = None
        self._stdin_lock: threading.Lock = threading.Lock()
        self._stdout_thread: threading.Thread | None = None
        self._channel: TerminalSSEChannel = channel
        self._init_event: threading.Event = threading.Event()
        self._persist_file: str | None = persist_file
        # Currently streaming assistant message cache. jsonl with Claude CLI
        # Flushing only at the time of message completion, so part content is refreshed during streaming.
        # null stream event NDJSON to prevent silence.
        # The structure is the same as the assistant line of jsonl:
        #   {'type': 'assistant',
        #    'message': {'role': 'assistant', 'content': [blocks...]},
        #    'timestamp': '<iso>'}
        self._in_flight_lock: threading.Lock = threading.Lock()
        self._in_flight_message: dict | None = None
        # If the user inputs the result before receiving it. status endpoints this flag
        # When exposed, the client can judge the spinner recovery/input lock even after a new one.
        self._awaiting_response: bool = False

    def spawn(
        self,
        extra_args: list[str] | None = None,
        env_extras: dict[str, str] | None = None,
    ) -> dict:
        """Claude CLI

        If you already have a process running, it will end first.
        System/init SSE event up to 10 seconds after the process begins
        include session id in response.

        Args:
            extra args: additional CLI argument list (optional)
            env extras: Added environment variable dict (optional) to be injected into a child process.
                        Example: {" WF SESSION TYPE": "workflow", " WF TICKET ID": "T-238"}

        Returns:
            dict: {"ok": true/False, "session id": str, "error": str}
        """
        server_debug_log('spawn.entry', {
            'awaiting_response': self._awaiting_response,
            'status': self._status,
            'session_id': self._session_id,
            'has_process': bool(self._process),
            'process_alive': bool(self._process and self._process.poll() is None),
        })
        # New Process Start = Previous Unsolved Turn Invalid.
        # if the result failed in the ESC stream and the process ends  awaiting response is
        # The new spawn instance that remains true to carry over → status response in a new
        # awaiting response=true is wrong exposed to the clover to enter busy.
        # Forced reset at the point of entering the spawn.
        self._awaiting_response = False
        if self._process and self._process.poll() is None:
            self.kill()
            self._init_event.clear()

        # Previous stdout thread wait until completely terminated
        if self._stdout_thread and self._stdout_thread.is_alive():
            self._stdout_thread.join(timeout=3)

        # --input-format stream-json
        # -p flag is required to send image content block to normal
        cmd = [
            'claude',
            '-p',
            '--output-format', 'stream-json',
            '--input-format', 'stream-json',
            '--include-partial-messages',
            '--verbose',
            '--permission-mode', 'default',
            '--permission-prompt-tool', 'stdio',
        ]
        if extra_args:
            cmd.extend(extra_args)

        self._init_event.clear()

        # env extras merges additional environment variables in the current environment
        proc_env = None
        if env_extras:
            proc_env = {**os.environ, **env_extras}

        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1,
                env=proc_env,
            )
        except FileNotFoundError:
            self._status = 'stopped'
            return {
                'ok': False,
                'session_id': '',
                'error': 'claude CLI not found in PATH',
            }
        except OSError as e:
            self._status = 'stopped'
            return {
                'ok': False,
                'session_id': '',
                'error': str(e),
            }

        self._status = 'running'
        self._session_id = ''

        # stdout read daemon thread start
        self._stdout_thread = threading.Thread(
            target=self._read_stdout_loop,
            daemon=True,
            name='claude-stdout-reader',
        )
        self._stdout_thread.start()

        # response immediately without init wait — delivered init event to SSE

        return {
            'ok': True,
            'session_id': self._session_id,
            'error': '',
        }

    def send_input(
        self,
        text: str,
        images: list[dict] | None = None,
        attachments: list[dict] | None = None,
    ) -> dict:
        """Send a user message to Claude CLI stdin to NDJSON Endopro.

        Args:
            text: user message text to send
            images: List of attachments. {"data": str, "media type": str} form.
                    None
            attachments: list of attachment tickets. Each item contains a minimum {"number": str} dict.
                         None or empty arrangements are not attached.
                         if content array is synthesized as text block, which is cognitive.

        Returns:
            dict: {"ok": true/False, "error": str}
        """
        if not self._process or self._process.poll() is not None:
            # --resume
            if self._session_id:
                resume_args = ['--resume', self._session_id]
                self._init_event.clear()
                result = self.spawn(extra_args=resume_args)
                if not result.get('ok'):
                    return {'ok': False, 'error': f'respawn failed: {result.get("error", "")}'}
                # Up to 10 seconds waiting until the init event is completed
                if not self._init_event.wait(timeout=10):
                    return {'ok': False, 'error': 'respawn init timeout'}
            else:
                return {'ok': False, 'error': 'process not running'}

        content: str | list = _compose_user_content(text, images, attachments)

        envelope = {
            'type': 'user',
            'message': {
                'role': 'user',
                'content': content,
            },
        }
        if self._session_id:
            envelope['session_id'] = self._session_id

        ndjson_line = json.dumps(envelope, ensure_ascii=False) + '\n'

        with self._stdin_lock:
            try:
                self._process.stdin.write(ndjson_line)
                self._process.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                self._status = 'stopped'
                return {'ok': False, 'error': str(e)}

        # Input transmission success → response standby status. result Unsubscribe
        server_debug_log('awaiting_response.set_true', {
            'reason': 'send_input',
            'session_id': self._session_id,
            'prev': self._awaiting_response,
        })
        self._awaiting_response = True

        return {'ok': True, 'error': ''}

    def send_permission_response(
        self,
        request_id: str,
        decision: str,
        session_id: str | None = None,
    ) -> dict:
        """permission to send control response NDJSON to stdin

        Args:
            request id: control request request id to respond
            "allow" or "deny"
            session id: Workflow Session ID (optional). Add the top-level session id field when specified.

        Returns:
            dict: {"ok": true/False, "error": str}
        """
        if not self._process or self._process.poll() is not None:
            return {'ok': False, 'error': 'process not running'}

        if decision == 'allow':
            response_body = {
                'subtype': 'success',
                'request_id': request_id,
                'response': {},
            }
        else:
            response_body = {
                'subtype': 'error',
                'request_id': request_id,
                'error': 'User denied permission',
            }

        envelope: dict = {
            'type': 'control_response',
            'response': response_body,
        }
        if session_id:
            envelope['session_id'] = session_id

        ndjson_line = json.dumps(envelope, ensure_ascii=False) + '\n'

        with self._stdin_lock:
            try:
                self._process.stdin.write(ndjson_line)
                self._process.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                self._status = 'stopped'
                return {'ok': False, 'error': str(e)}

        return {'ok': True, 'error': ''}

    def interrupt(self) -> dict:
        """Send SIGINT to the Claude CLI process to stop current response generation.

        Unlike kill(), the process does not end. Claude CLI received by SIGINT
        Stops the current response generation and returns to a new input atmospheric state (idle).
        status does not change — if Claude CLI issues a result event
        read stdout loop to idle

        Price:
        - Find the last real user message timestamp of SDK jsonl and sidecar file
          (`<session id>.interrupted.jsonl`)
        - SSE Live event ``system/user input interrupted` ``
          The client can immediately display the marker on the user ending line.
        - After the refreshing call, sidecar will act as a permanent signal when the history is restored.

        Returns:
            result dict: {"ok": true/False, "error": str}
        """
        if not self._process:
            return {'ok': False, 'error': 'process not running'}

        if self._process.poll() is not None:
            self._status = 'stopped'
            self._process = None
            return {'ok': False, 'error': 'process not running'}

        # SIGINT Pre-sidecar record + SSE broadcast (SIGINT hood SDK jsonl)
        # You can add flush to the race, so at the SIGINT position
        # jsonl end of the last real user message).
        last_user_ts = self._record_user_interrupt_to_sidecar()
        if last_user_ts:
            try:
                self._channel.broadcast({
                    'type': 'system',
                    'subtype': 'user_input_interrupted',
                    'timestamp': last_user_ts,
                    'session_id': self._session_id or '',
                })
            except (OSError, TypeError) as exc:
                logger.error("interrupted: %s", exc)

        try:
            os.kill(self._process.pid, signal.SIGINT)
        except OSError as e:
            return {'ok': False, 'error': str(e)}

        return {'ok': True, 'error': ''}

    def _record_user_interrupt_to_sidecar(self) -> str | None:
        """The last real user message timetamp in SDK jsonl and append on sidecar.

        sidecar file: ``~/.claude/projects/<slug>/<session id>.interrupted.jsonl`
        One interflow record per line ``{"timestamp": "...", "kind": "user interrupted"}`.

        real user message = ``type=user` and text block in ``content`
        (except user records only intool result).

        Returns:
            If you find timestamp string, None.
        """
        if not self._session_id:
            return None
        project_root = os.getcwd()
        home_dir = os.path.expanduser('~')
        project_slug = project_root.replace('/', '-')
        jsonl_path = os.path.join(
            home_dir, '.claude', 'projects', project_slug, f'{self._session_id}.jsonl',
        )
        sidecar_path = os.path.join(
            home_dir, '.claude', 'projects', project_slug,
            f'{self._session_id}.interrupted.jsonl',
        )
        if not os.path.isfile(jsonl_path):
            return None

        last_user_ts: str | None = None
        try:
            with open(jsonl_path, 'r', encoding='utf-8') as fp:
                for line in fp:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        rec = json.loads(stripped)
                    except (ValueError, json.JSONDecodeError):
                        continue
                    if rec.get('type') != 'user':
                        continue
                    msg = rec.get('message')
                    if not isinstance(msg, dict):
                        continue
                    content = msg.get('content')
                    has_text_block = False
                    text_value = ''
                    if isinstance(content, str):
                        has_text_block = bool(content)
                        text_value = content
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get('type') == 'text':
                                has_text_block = True
                                text_value = block.get('text') or ''
                                break
                    if not has_text_block:
                        continue
                    # placeholder user messages that are automatically recorded by the SDK sidecar
                    # No matching target. If you caught this, it is removed with the history filter
                    # stoped marker causes the race revolving.
                    if text_value.strip() == '[Request interrupted by user]':
                        continue
                    ts = rec.get('timestamp', '') or ''
                    if ts:
                        last_user_ts = ts
        except OSError as exc:
            logger.error("interrupt: jsonl failed to read (%s): %s", jsonl_path, exc)
            return None

        if not last_user_ts:
            return None

        try:
            with open(sidecar_path, 'a', encoding='utf-8') as fp:
                fp.write(json.dumps(
                    {'timestamp': last_user_ts, 'kind': 'user_interrupted'},
                    ensure_ascii=False,
                ) + '\n')
        except OSError as exc:
            logger.error("interrupt: sidecar write failed (%s): %s", sidecar_path, exc)
            return None

        return last_user_ts

    def kill(self) -> dict:
        """terminate the Claude CLI process.

        First attempt to SIGTERM, and endangered with SIGKILL if it fails within 2 seconds.

        Returns:
            dict: {"ok": true/False, "error": str}
        """
        if not self._process:
            self._status = 'stopped'
            return {'ok': True, 'error': ''}

        if self._process.poll() is not None:
            self._status = 'stopped'
            self._process = None
            return {'ok': True, 'error': ''}

        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        except OSError as e:
            return {'ok': False, 'error': str(e)}
        finally:
            self._status = 'stopped'
            self._process = None

        return {'ok': True, 'error': ''}

    @property
    def status(self) -> str:
        """return the process status.

        Stage 3-B — ` external status` set (production-line subprocess external mode)
        returns that value first. v1 spawn infrastructure.

        Returns:
            "running", "idle", "stopped"
        """
        if self._external_status is not None:
            return self._external_status
        if not self._process:
            return 'stopped'
        if self._process.poll() is not None:
            self._status = 'stopped'
            self._process = None
            return 'stopped'
        return self._status

    def set_external_status(self, status: str) -> None:
        """set.

        v1 spawn infrastructure detects auto stopping with 'self. process.poll()' but
        the status of the process from outside is not tracked by the board side
        The caller is set.

        T-498 (2026-05-18) The caller of this method is 0 — v1 hybrid suture
        path(`/api/v2/wf-event` + `workflow registry.create external`) is the
        . . . . . . Removing method itself from follow-up tracks.
        """
        self._external_status = status

    @property
    def session_id(self) -> str:
        """returns the current session ID."""
        return self._session_id

    def _track_in_flight(self, data: dict) -> None:
        """stream event NDJSON keeps the current streaming assistant message status.

        jsonl is only append to message bounds(= Claude CLI is message stop after
        If you have a new call during a single line), you will be asked to send an unfinished message
        There is a problem that disappears from the UI that does not leave the authority source.
        This cache is merged to /terminal/history response and migrate that interval.

        The data structure remains the same as the jsonl’s assistant line
        build render events()

        Price:
            message start → reset new cache
            content block start → block empty block append
            text/thinking/partial json
            content block stop → tool use partial json to input
            'assistant'/'user'/'result' → cache rain (complete message is recorded in jsonl or
                                           Closed
        """
        msg_type = data.get('type', '')

        # Complete message arrives (= jsonl is soon become an authoritative source) or turn ends → unchecked
        if msg_type in ('assistant', 'user', 'result'):
            with self._in_flight_lock:
                self._in_flight_message = None
            return

        if msg_type != 'stream_event':
            return

        event = data.get('event') or {}
        if not isinstance(event, dict):
            return
        ev_type = event.get('type')

        with self._in_flight_lock:
            if ev_type == 'message_start':
                timestamp = datetime.datetime.now(tz=datetime.timezone.utc).strftime(
                    '%Y-%m-%dT%H:%M:%S.%fZ'
                )
                self._in_flight_message = {
                    'type': 'assistant',
                    'message': {'role': 'assistant', 'content': []},
                    'timestamp': timestamp,
                }
                return

            # Claude CLI Flush**
            # ` track in flight` returns the cache when the block is completed. Next Block
            # When starting, `content block start` arrives first, so here’s cache
            # After the second delay, the block will be tracked.
            if ev_type == 'content_block_start' and self._in_flight_message is None:
                timestamp = datetime.datetime.now(tz=datetime.timezone.utc).strftime(
                    '%Y-%m-%dT%H:%M:%S.%fZ'
                )
                self._in_flight_message = {
                    'type': 'assistant',
                    'message': {'role': 'assistant', 'content': []},
                    'timestamp': timestamp,
                }

            if self._in_flight_message is None:
                return

            blocks = self._in_flight_message['message']['content']

            if ev_type == 'content_block_start':
                block = event.get('content_block') or {}
                btype = block.get('type')
                if btype == 'text':
                    blocks.append({'type': 'text', 'text': ''})
                elif btype == 'thinking':
                    blocks.append({'type': 'thinking', 'thinking': ''})
                elif btype == 'tool_use':
                    blocks.append({
                        'type': 'tool_use',
                        'id': block.get('id', '') or '',
                        'name': block.get('name', '') or '',
                        'input': {},
                        '_partial_input_json': '',
                    })
                return

            if ev_type == 'content_block_delta':
                if not blocks:
                    return
                delta = event.get('delta') or {}
                dtype = delta.get('type')
                current = blocks[-1]
                if dtype == 'text_delta' and current.get('type') == 'text':
                    current['text'] = (current.get('text') or '') + (delta.get('text') or '')
                elif dtype == 'thinking_delta' and current.get('type') == 'thinking':
                    current['thinking'] = (
                        (current.get('thinking') or '') + (delta.get('thinking') or '')
                    )
                elif dtype == 'input_json_delta' and current.get('type') == 'tool_use':
                    current['_partial_input_json'] = (
                        (current.get('_partial_input_json') or '')
                        + (delta.get('partial_json') or '')
                    )
                return

            if ev_type == 'content_block_stop':
                if not blocks:
                    return
                current = blocks[-1]
                if current.get('type') == 'tool_use':
                    partial = current.pop('_partial_input_json', '') or ''
                    if partial:
                        try:
                            parsed = json.loads(partial)
                            if isinstance(parsed, dict):
                                current['input'] = parsed
                        except json.JSONDecodeError:
                            # Unfair JSON — Keeping empty input
                            pass
                return

            # message delta / message stop is not processed separately.
            # after message stop 'assistant' NDJSON arrives and the cache is empty.

    def get_in_flight_snapshot(self) -> dict | None:
        """returns the read-only snapshot of the assistant message currently streaming.

        /terminal/history included in the response jsonl has not yet flush
        Uses to send part messages to clients. return structure of jsonl
        build render events()

        if the input of the tool use block is still streaming, ` partial input json`
        exposes a cumulative string to a separate field `partial input json`
        (To allow the client to finish the tool-box input buffer).
        """
        with self._in_flight_lock:
            if self._in_flight_message is None:
                return None
            snapshot = copy.deepcopy(self._in_flight_message)

        blocks = snapshot.get('message', {}).get('content', [])
        for block in blocks:
            if block.get('type') == 'tool_use':
                partial = block.pop('_partial_input_json', '') or ''
                if partial:
                    # content block stop
                    # attempt to parsing (expanded as partial input json)
                    if not block.get('input'):
                        try:
                            parsed = json.loads(partial)
                            if isinstance(parsed, dict):
                                block['input'] = parsed
                        except json.JSONDecodeError:
                            pass
                    block['partial_input_json'] = partial
        return snapshot

    def _read_stdout_loop(self) -> None:
        """NDJSON reads one line in stdout and broadcasts to SSE channels.

        exit the process or stdout EOF loop.
        Run in the daemon thread.
        """
        proc = self._process
        if not proc or not proc.stdout:
            return

        try:
            for line in proc.stdout:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    data = json.loads(stripped)
                except json.JSONDecodeError:
                    logger.debug('Non-JSON stdout line: %s', stripped[:200])
                    continue

                # init wait event after extracting session id from system/init
                if (
                    data.get('type') == 'system'
                    and data.get('subtype') == 'init'
                ):
                    self._session_id = data.get('session_id', '')
                    self._model = data.get('model', '')
                    self._permission_mode = data.get('permissionMode', '')
                    if self._persist_file and self._session_id:
                        try:
                            with open(self._persist_file, 'w') as _pf:
                                _pf.write(self._session_id)
                        except OSError as _e:
                            logger.debug('session id persist fail: %s', _e)
                    self._init_event.set()

                # result Convert status to idle
                if data.get('type') == 'result':
                    server_debug_log('awaiting_response.set_false', {
                        'reason': 'result',
                        'session_id': self._session_id,
                        'prev': self._awaiting_response,
                        'subtype': data.get('subtype'),
                    })
                    self._status = 'idle'
                    self._awaiting_response = False

                # in-flight cache update (for preserving part contents during the refreshing moment)
                self._track_in_flight(data)

                self._channel.broadcast(data)
        except (ValueError, OSError):
            # You can use the following:
            pass
        finally:
            # Zombie Process Prevention: Explicitly call wait()
            try:
                proc.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                pass

            # If the process ends, the status update
            if proc.poll() is not None:
                exit_code = proc.returncode
                server_debug_log('process_exit', {
                    'exit_code': exit_code,
                    'session_id': self._session_id,
                    'awaiting_response_at_exit': self._awaiting_response,
                    'status_before': self._status,
                })
                # process termination = unsolved turn itself ends.
                # Since SDKs can end before sending result in the ESC stream
                # In the process end path, specify reset. Prevent stale exposure when refreshing.
                self._awaiting_response = False
                # -exit code 0
                # Convert idle status to enable instant re-enter.
                # Set the default exit (exit code != 0) only to stop.
                if exit_code == 0:
                    self._status = 'idle'
                else:
                    self._status = 'stopped'
                # SSE
                self._channel.broadcast({
                    'type': 'system',
                    'subtype': 'process_exit',
                    'exit_code': exit_code,
                    'session_id': self._session_id,
                })
                # Please contact us for further details.
                if exit_code != 0:
                    self._channel.broadcast({
                        'type': 'error',
                        'message': f'Claude process exited with code {exit_code}',
                        'exit_code': exit_code,
                        'session_id': self._session_id,
                    })


# ---------------------------------------------------------------------------
# Poll Change Tracker
# ---------------------------------------------------------------------------
