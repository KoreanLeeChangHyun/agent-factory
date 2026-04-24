"""ClaudeProcess — wraps Claude Code CLI subprocess with JSON streaming."""

from __future__ import annotations

import copy
import datetime
import json
import logging
import os
import signal
import subprocess
import threading
import time
import uuid

from ._common import logger
from .terminal_channel import TerminalSSEChannel


_ALLOWED_MEDIA_TYPES = {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}


def _validate_images(images: list) -> str | None:
    """이미지 목록의 유효성을 검증한다.

    각 항목에 data(문자열)와 허용된 media_type이 존재하는지 확인한다.

    Args:
        images: 검증할 이미지 항목 목록.

    Returns:
        유효하지 않을 때 에러 메시지 문자열, 유효하면 None.
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
    """Claude CLI 프로세스 생명주기 관리자.

    subprocess.Popen으로 Claude CLI를 실행하고, stdin/stdout을 통한
    NDJSON 양방향 통신을 관리한다.

    Attributes:
        _process: subprocess.Popen 인스턴스 (프로세스 시작 전에는 None)
        _session_id: system/init 메시지에서 추출한 세션 ID
        _status: 프로세스 상태 (stopped/running/idle)
        _stdin_lock: stdin 접근 보호 Lock
        _stdout_thread: stdout 읽기 데몬 스레드
        _channel: SSE 브로드캐스트 채널
    """

    def __init__(self, channel: TerminalSSEChannel, persist_file: str | None = None) -> None:
        """초기화한다.

        Args:
            channel: NDJSON 이벤트를 브로드캐스트할 TerminalSSEChannel 인스턴스
            persist_file: session_id를 영속화할 파일 경로 (선택적)
        """
        self._process: subprocess.Popen | None = None
        self._session_id: str = ''
        self._model: str = ''
        self._permission_mode: str = ''
        self._status: str = 'stopped'
        self._stdin_lock: threading.Lock = threading.Lock()
        self._stdout_thread: threading.Thread | None = None
        self._channel: TerminalSSEChannel = channel
        self._init_event: threading.Event = threading.Event()
        self._persist_file: str | None = persist_file
        # 현재 스트리밍 중인 assistant 메시지 캐시. Claude CLI 가 jsonl 에는
        # 메시지 완료 시점에만 flush 하므로, 스트리밍 중 새로고침 시 부분 내용이
        # 유실되는 것을 막기 위해 stream_event NDJSON 을 누적한다.
        # 구조는 jsonl 의 assistant 라인과 동일:
        #   {'type': 'assistant',
        #    'message': {'role': 'assistant', 'content': [blocks...]},
        #    'timestamp': '<iso>'}
        self._in_flight_lock: threading.Lock = threading.Lock()
        self._in_flight_message: dict | None = None
        # 사용자 입력 전송 후 result 수신 전 여부. status 엔드포인트가 이 플래그를
        # 노출하면 새로고침 후에도 클라이언트가 스피너 복구/입력 잠금을 판단할 수 있다.
        self._awaiting_response: bool = False

    def spawn(
        self,
        extra_args: list[str] | None = None,
        env_extras: dict[str, str] | None = None,
    ) -> dict:
        """Claude CLI 프로세스를 시작한다.

        이미 실행 중인 프로세스가 있으면 먼저 종료한다.
        프로세스 시작 후 system/init SSE 이벤트를 최대 10초까지 대기하여
        session_id를 응답에 포함한다.

        Args:
            extra_args: 추가 CLI 인자 목록 (선택적)
            env_extras: 자식 프로세스에 주입할 추가 환경변수 dict (선택적).
                        예: {"_WF_SESSION_TYPE": "workflow", "_WF_TICKET_ID": "T-238"}

        Returns:
            시작 결과 dict: {"ok": True/False, "session_id": str, "error": str}
        """
        if self._process and self._process.poll() is None:
            self.kill()
            self._init_event.clear()

        # 이전 stdout 스레드가 완전히 종료될 때까지 대기
        if self._stdout_thread and self._stdout_thread.is_alive():
            self._stdout_thread.join(timeout=3)

        # -p(print mode)로 시작: --input-format stream-json은 print mode 전용
        # 이미지 content block이 정상 전달되려면 -p 플래그가 반드시 필요하다
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

        # env_extras가 지정되면 현재 환경에 추가 환경변수를 병합
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

        # stdout 읽기 데몬 스레드 시작
        self._stdout_thread = threading.Thread(
            target=self._read_stdout_loop,
            daemon=True,
            name='claude-stdout-reader',
        )
        self._stdout_thread.start()

        # init 대기 없이 즉시 응답 — SSE로 init 이벤트가 전달됨

        return {
            'ok': True,
            'session_id': self._session_id,
            'error': '',
        }

    def send_input(self, text: str, images: list[dict] | None = None) -> dict:
        """사용자 메시지를 Claude CLI stdin에 NDJSON 엔벨로프로 전송한다.

        Args:
            text: 전송할 사용자 메시지 텍스트
            images: 첨부 이미지 목록. 각 항목은 {"data": str, "media_type": str} 형태.
                    None이면 텍스트 전용 content 문자열로 구성한다.

        Returns:
            전송 결과 dict: {"ok": True/False, "error": str}
        """
        if not self._process or self._process.poll() is not None:
            # -p 모드에서 result 후 프로세스가 종료된 경우 --resume으로 자동 재시작
            if self._session_id:
                resume_args = ['--resume', self._session_id]
                self._init_event.clear()
                result = self.spawn(extra_args=resume_args)
                if not result.get('ok'):
                    return {'ok': False, 'error': f'respawn failed: {result.get("error", "")}'}
                # init 이벤트가 완료될 때까지 최대 10초 대기
                if not self._init_event.wait(timeout=10):
                    return {'ok': False, 'error': 'respawn init timeout'}
            else:
                return {'ok': False, 'error': 'process not running'}

        if images is not None:
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
            content: str | list = (
                [{'type': 'text', 'text': text}] + image_blocks
                if text else image_blocks
            )
        else:
            content = text

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

        # 입력 전송 성공 → 응답 대기 상태. result 수신 시 해제됨.
        self._awaiting_response = True

        return {'ok': True, 'error': ''}

    def send_permission_response(
        self,
        request_id: str,
        decision: str,
        session_id: str | None = None,
    ) -> dict:
        """permission 요청에 대한 control_response NDJSON을 stdin으로 전송한다.

        Args:
            request_id: 응답할 control_request의 request_id
            decision: "allow" 또는 "deny"
            session_id: 워크플로우 세션 ID (선택적). 지정 시 최상위 session_id 필드 추가.

        Returns:
            전송 결과 dict: {"ok": True/False, "error": str}
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
        """Claude CLI 프로세스에 SIGINT를 전송하여 현재 응답 생성만 중단한다.

        kill()과 달리 프로세스를 종료하지 않는다. SIGINT를 수신한 Claude CLI는
        현재 응답 생성을 중단하고 새 입력 대기 상태(idle)로 복귀한다.
        _status는 변경하지 않는다 — Claude CLI가 result 이벤트를 발행하면
        _read_stdout_loop에서 idle로 전환된다.

        Returns:
            결과 dict: {"ok": True/False, "error": str}
        """
        if not self._process:
            return {'ok': False, 'error': 'process not running'}

        if self._process.poll() is not None:
            self._status = 'stopped'
            self._process = None
            return {'ok': False, 'error': 'process not running'}

        try:
            os.kill(self._process.pid, signal.SIGINT)
        except OSError as e:
            return {'ok': False, 'error': str(e)}

        return {'ok': True, 'error': ''}

    def kill(self) -> dict:
        """Claude CLI 프로세스를 종료한다.

        SIGTERM으로 먼저 시도하고, 2초 내 종료되지 않으면 SIGKILL로 강제 종료한다.

        Returns:
            종료 결과 dict: {"ok": True/False, "error": str}
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
        """프로세스 상태를 반환한다.

        Returns:
            "running", "idle", "stopped" 중 하나
        """
        if not self._process:
            return 'stopped'
        if self._process.poll() is not None:
            self._status = 'stopped'
            self._process = None
            return 'stopped'
        return self._status

    @property
    def session_id(self) -> str:
        """현재 세션 ID를 반환한다."""
        return self._session_id

    def _track_in_flight(self, data: dict) -> None:
        """stream_event NDJSON을 누적하여 현재 스트리밍 중인 assistant 메시지 상태를 유지한다.

        jsonl 은 메시지 경계에서만 append 되므로(= Claude CLI 가 message_stop 후에
        한 줄을 쓴다) 스트리밍 도중 새로고침이 발생하면 미완성 메시지가 어떠한
        권위 출처에도 남지 않아 UI에서 통째로 사라지는 문제가 있다.
        이 캐시는 /terminal/history 응답에 병합되어 그 간격을 메꾼다.

        데이터 구조는 jsonl 의 assistant 라인과 동일하게 유지하여 기존
        _build_render_events() 를 그대로 재사용할 수 있게 한다.

        수명 주기:
            message_start                → 새 캐시 초기화
            content_block_start          → blocks 에 빈 block append
            content_block_delta          → 마지막 block 의 text/thinking/partial_json 누적
            content_block_stop           → tool_use partial_json 을 input 으로 파싱
            'assistant'/'user'/'result'  → 캐시 비움 (완성 메시지가 jsonl 에 기록되거나
                                           턴이 종료됨)
        """
        msg_type = data.get('type', '')

        # 완성 메시지가 도착(= jsonl 이 곧 권위 출처가 됨) 또는 턴 종료 → 캐시 해제
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

            # Claude CLI 는 **블록 단위로 `assistant` NDJSON 을 flush** 하므로
            # 직전 블록 완료 시 `_track_in_flight` 가 캐시를 비운다. 다음 블록이
            # 시작할 때 `content_block_start` 가 먼저 도착하므로, 여기서 캐시를
            # 지연 초기화해야 두 번째 이후 블록도 추적 대상이 된다.
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
                            # 비정상 부분 JSON — 빈 input 유지
                            pass
                return

            # message_delta / message_stop 은 별도 처리 불필요.
            # message_stop 직후 'assistant' NDJSON 이 도착하여 캐시가 비워진다.

    def get_in_flight_snapshot(self) -> dict | None:
        """현재 스트리밍 중인 assistant 메시지의 읽기 전용 스냅샷을 반환한다.

        /terminal/history 응답에 포함되어 jsonl 이 아직 flush 하지 못한
        부분 메시지를 클라이언트에 전달하는 용도다. 반환 구조는 jsonl 의
        assistant 라인과 동일하여 _build_render_events() 로 바로 전개 가능.

        tool_use 블록의 input 이 아직 스트리밍 중이면 `_partial_input_json`
        에 누적된 문자열을 별도 필드 `partial_input_json` 으로 노출한다
        (클라이언트가 tool-box 입력 버퍼에 시딩할 수 있도록).
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
                    # content_block_stop 이 오기 전이라 input 이 비어있으면
                    # 부분 파싱 시도 (실패해도 partial_input_json 을 그대로 노출)
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
        """stdout에서 NDJSON 한 줄씩 읽어 파싱하고 SSE 채널로 브로드캐스트한다.

        프로세스 종료 또는 stdout EOF 시 루프를 빠져나온다.
        데몬 스레드에서 실행된다.
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

                # system/init에서 session_id 추출 후 init 대기 이벤트 해제
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
                            logger.debug('session_id persist 실패: %s', _e)
                    self._init_event.set()

                # result 수신 시 상태를 idle로 전환
                if data.get('type') == 'result':
                    self._status = 'idle'
                    self._awaiting_response = False

                # in-flight 캐시 업데이트 (스트리밍 중 새로고침 시 부분 내용 보존용)
                self._track_in_flight(data)

                self._channel.broadcast(data)
        except (ValueError, OSError):
            # 프로세스 종료 시 발생 가능
            pass
        finally:
            # 좀비 프로세스 방지: 명시적으로 wait() 호출
            try:
                proc.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                pass

            # 프로세스가 종료된 경우 상태 업데이트
            if proc.poll() is not None:
                exit_code = proc.returncode
                # -p 모드에서 result 완료 후 정상 종료(exit_code 0)는
                # idle 상태로 전환하여 즉시 재입력 가능하게 한다.
                # 비정상 종료(exit_code != 0)만 stopped로 설정한다.
                if exit_code == 0:
                    self._status = 'idle'
                else:
                    self._status = 'stopped'
                # 종료 이벤트를 SSE로 알림
                self._channel.broadcast({
                    'type': 'system',
                    'subtype': 'process_exit',
                    'exit_code': exit_code,
                    'session_id': self._session_id,
                })
                # 비정상 종료 시 에러 이벤트도 전송
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
