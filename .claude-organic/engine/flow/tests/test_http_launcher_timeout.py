"""test_http_launcher_timeout.py - http_launcher.py TimeoutError 분기 단위 테스트.

T-358: flow-launcher POST /terminal/workflow/start 타임아웃 후
_handle_launch_timeout 헬퍼를 통한 후확인 분기를 검증한다.

케이스:
  1. test_timeout_with_session_present
       POST TimeoutError + list GET이 매칭 세션 반환
       → exit 0, stdout "LAUNCH: <sid> 실행 중 (초기화 지연)"

  2. test_timeout_with_session_missing
       POST TimeoutError + list GET이 빈 배열 반환
       → exit 1, stderr "초기화 타임아웃, 세션 미확인"

  3. test_timeout_with_list_failure
       POST TimeoutError + list GET이 Exception raise
       → exit 1, stderr에 ERROR 메시지 포함

  4. test_normal_path_unchanged
       POST 정상 응답 {"ok": True, "session_id": "wf-T-358-ok"}
       → exit 0, stdout "LAUNCH: wf-T-358-ok 실행 중"
         "(초기화 지연)" 접미사 미포함 (정상 경로 회귀 방지)

  5. test_timeout_via_urlerror_with_session_present
       POST URLError(reason=TimeoutError()) + list GET이 매칭 세션 반환
       → exit 0, stdout "LAUNCH: <sid> 실행 중 (초기화 지연)"
         (URLError 래핑 형태도 흡수되는지 검증)

  6. test_timeout_via_urlerror_missing
       POST URLError(reason=TimeoutError()) + list GET이 빈 배열 반환
       → exit 1, stderr에 "세션 미확인" 포함

외부 의존성 격리:
  _resolve_server_port, _is_server_running, _kanban_move_progress,
  _read_ticket_status 모두 mock 처리 → 파일시스템 / 네트워크 / 칸반 없음.
"""
from __future__ import annotations

import contextlib
import sys
import unittest
import urllib.error
from io import StringIO
from pathlib import Path
from unittest import mock

# sys.path: .claude-organic/engine 디렉터리를 포함해 flow 패키지 import 가능하게 한다.
_TEST_DIR = Path(__file__).resolve().parent
_FLOW_DIR = _TEST_DIR.parent
_ENGINE_DIR = _FLOW_DIR.parent
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

from flow.http_launcher import cmd_launch  # noqa: E402

# ---------------------------------------------------------------------------
# 공통 fixture 헬퍼
# ---------------------------------------------------------------------------

_TICKET_ID = "T-358"
_COMMAND = "implement"
_PORT = 9927

# patch 대상 — 모두 http_launcher 모듈 내부 이름으로 지정
_PATCH_RESOLVE_PORT = "flow.http_launcher._resolve_server_port"
_PATCH_IS_RUNNING = "flow.http_launcher._is_server_running"
_PATCH_KANBAN_MOVE = "flow.http_launcher._kanban_move_progress"
_PATCH_READ_STATUS = "flow.http_launcher._read_ticket_status"
_PATCH_POST = "flow.http_launcher._http_post_json"
_PATCH_GET = "flow.http_launcher._http_get_json"
_PATCH_LOG = "flow.http_launcher._log"

# flow-stop best-effort 호출이 테스트 환경에서 실제로 실행되지 않도록 subprocess 도 mock.
_PATCH_SUBPROCESS = "flow.http_launcher.subprocess.run"

# 재진입 감지 환경변수 — 테스트 환경에서 _WF_SESSION_TYPE=workflow 가 설정되어 있으면
# INLINE 분기로 빠져 POST가 호출되지 않는다. os.environ을 통한 분기를 우회한다.
_PATCH_OS_ENVIRON = "flow.http_launcher.os.environ"


def _make_stack(
    stack: contextlib.ExitStack,
    post_side_effect=None,
    post_return_value=None,
    get_side_effect=None,
    get_return_value=None,
) -> None:
    """ExitStack에 공통 mock + POST/GET 설정을 추가한다.

    외부 의존성 격리:
      _resolve_server_port → _PORT
      _is_server_running   → True
      _read_ticket_status  → "Open"
      _kanban_move_progress → True
      _log                 → no-op
      subprocess.run       → no-op MagicMock
      os.environ           → {} (재진입 감지 환경변수 격리)
    """
    stack.enter_context(mock.patch(_PATCH_RESOLVE_PORT, return_value=_PORT))
    stack.enter_context(mock.patch(_PATCH_IS_RUNNING, return_value=True))
    stack.enter_context(mock.patch(_PATCH_READ_STATUS, return_value="Open"))
    stack.enter_context(mock.patch(_PATCH_KANBAN_MOVE, return_value=True))
    stack.enter_context(mock.patch(_PATCH_LOG))
    stack.enter_context(mock.patch(_PATCH_SUBPROCESS))
    # _WF_SESSION_TYPE 격리: 테스트 환경에서 workflow 세션 내부로 인식되어
    # INLINE 분기로 빠지지 않도록 빈 dict를 주입한다.
    stack.enter_context(mock.patch(_PATCH_OS_ENVIRON, {}))

    if post_side_effect is not None:
        stack.enter_context(mock.patch(_PATCH_POST, side_effect=post_side_effect))
    elif post_return_value is not None:
        stack.enter_context(mock.patch(_PATCH_POST, return_value=post_return_value))

    if get_side_effect is not None:
        stack.enter_context(mock.patch(_PATCH_GET, side_effect=get_side_effect))
    elif get_return_value is not None:
        stack.enter_context(mock.patch(_PATCH_GET, return_value=get_return_value))


def _run_cmd_launch_captured(ticket_id: str, command: str):
    """cmd_launch 실행 후 (exit_code, stdout_text, stderr_text) 반환."""
    captured_out = StringIO()
    captured_err = StringIO()
    with mock.patch("sys.stdout", captured_out), \
         mock.patch("sys.stderr", captured_err):
        exit_code = cmd_launch(ticket_id, command)
    return exit_code, captured_out.getvalue(), captured_err.getvalue()


# ---------------------------------------------------------------------------
# 케이스 1: TimeoutError 직접 + list GET이 매칭 세션 반환
# ---------------------------------------------------------------------------

class TestTimeoutWithSessionPresent(unittest.TestCase):
    """POST TimeoutError + GET 매칭 세션 존재 → exit 0 + (초기화 지연)."""

    def test_timeout_with_session_present(self):
        matching_sessions = [
            {"ticket_id": _TICKET_ID, "session_id": "wf-T-358-test"}
        ]
        with contextlib.ExitStack() as stack:
            _make_stack(
                stack,
                post_side_effect=TimeoutError("connection timed out"),
                get_return_value=matching_sessions,
            )
            result, stdout_text, _ = _run_cmd_launch_captured(_TICKET_ID, _COMMAND)

        self.assertEqual(result, 0, "exit code should be 0 when session is found after timeout")
        self.assertIn("LAUNCH:", stdout_text)
        self.assertIn("wf-T-358-test", stdout_text)
        self.assertIn("실행 중 (초기화 지연)", stdout_text)


# ---------------------------------------------------------------------------
# 케이스 2: TimeoutError 직접 + list GET이 빈 배열 반환
# ---------------------------------------------------------------------------

class TestTimeoutWithSessionMissing(unittest.TestCase):
    """POST TimeoutError + GET 빈 응답 → exit 1 + '세션 미확인' stderr."""

    def test_timeout_with_session_missing(self):
        with contextlib.ExitStack() as stack:
            _make_stack(
                stack,
                post_side_effect=TimeoutError("connection timed out"),
                get_return_value=[],
            )
            result, _, stderr_text = _run_cmd_launch_captured(_TICKET_ID, _COMMAND)

        self.assertEqual(result, 1, "exit code should be 1 when no session found after timeout")
        self.assertIn("초기화 타임아웃, 세션 미확인", stderr_text)


# ---------------------------------------------------------------------------
# 케이스 3: TimeoutError 직접 + list GET이 Exception raise
# ---------------------------------------------------------------------------

class TestTimeoutWithListFailure(unittest.TestCase):
    """POST TimeoutError + GET Exception → exit 1 + ERROR stderr."""

    def test_timeout_with_list_failure(self):
        with contextlib.ExitStack() as stack:
            _make_stack(
                stack,
                post_side_effect=TimeoutError("connection timed out"),
                get_side_effect=Exception("list GET network error"),
            )
            result, _, stderr_text = _run_cmd_launch_captured(_TICKET_ID, _COMMAND)

        self.assertEqual(result, 1, "exit code should be 1 when list GET fails")
        # 후확인 GET 오류 경로의 ERROR 메시지가 출력되어야 한다
        self.assertIn("ERROR", stderr_text)


# ---------------------------------------------------------------------------
# 케이스 4: 정상 응답 — (초기화 지연) 접미사 미포함 검증
# ---------------------------------------------------------------------------

class TestNormalPathUnchanged(unittest.TestCase):
    """POST 정상 응답 → exit 0 + (초기화 지연) 미포함 (정상 경로 회귀 방지)."""

    def test_normal_path_unchanged(self):
        normal_response = {"ok": True, "session_id": "wf-T-358-ok"}
        with contextlib.ExitStack() as stack:
            _make_stack(stack, post_return_value=normal_response)
            result, stdout_text, _ = _run_cmd_launch_captured(_TICKET_ID, _COMMAND)

        self.assertEqual(result, 0, "exit code should be 0 for normal response")
        self.assertIn("LAUNCH: wf-T-358-ok 실행 중", stdout_text)
        self.assertNotIn("(초기화 지연)", stdout_text,
                         "normal path must NOT include '(초기화 지연)' suffix")


# ---------------------------------------------------------------------------
# 케이스 5: URLError(reason=TimeoutError) 래핑 + list GET이 매칭 세션 반환
# ---------------------------------------------------------------------------

class TestTimeoutViaURLErrorWithSessionPresent(unittest.TestCase):
    """POST URLError(reason=TimeoutError) + GET 매칭 세션 → exit 0 + (초기화 지연).

    Python 3.9 이하 등에서 urlopen이 TimeoutError를 URLError로 래핑하여 raise 하는
    형태도 _handle_launch_timeout으로 흡수되는지 검증한다.
    """

    def test_timeout_via_urlerror_with_session_present(self):
        matching_sessions = [
            {"ticket_id": _TICKET_ID, "session_id": "wf-T-358-urlerr"}
        ]
        url_error = urllib.error.URLError(reason=TimeoutError("timed out"))
        with contextlib.ExitStack() as stack:
            _make_stack(
                stack,
                post_side_effect=url_error,
                get_return_value=matching_sessions,
            )
            result, stdout_text, _ = _run_cmd_launch_captured(_TICKET_ID, _COMMAND)

        self.assertEqual(result, 0)
        self.assertIn("LAUNCH:", stdout_text)
        self.assertIn("wf-T-358-urlerr", stdout_text)
        self.assertIn("실행 중 (초기화 지연)", stdout_text)


# ---------------------------------------------------------------------------
# 케이스 6: URLError(reason=TimeoutError) + list GET 빈 배열
# ---------------------------------------------------------------------------

class TestTimeoutViaURLErrorMissing(unittest.TestCase):
    """POST URLError(reason=TimeoutError) + GET 빈 배열 → exit 1 + '세션 미확인'."""

    def test_timeout_via_urlerror_missing(self):
        url_error = urllib.error.URLError(reason=TimeoutError("timed out"))
        with contextlib.ExitStack() as stack:
            _make_stack(
                stack,
                post_side_effect=url_error,
                get_return_value=[],
            )
            result, _, stderr_text = _run_cmd_launch_captured(_TICKET_ID, _COMMAND)

        self.assertEqual(result, 1)
        self.assertIn("세션 미확인", stderr_text)


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
