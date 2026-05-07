"""test_sessions_status.py — sessions.py W08 회귀 테스트.

검증 항목:
  1. _HTTP_STATUS_MAP['stopped'] == '완료' 매핑 확인
  2. _parse_jsonl_status: process_exit 마커 → 종료 인식
  3. _parse_jsonl_status: stopped_by_flow_stop 마커 → 종료 인식
  4. _parse_jsonl_status: 두 마커 모두 없음 → 실행중
  5. _parse_jsonl_status: process_exit + success result → '완료'
  6. _parse_jsonl_status: process_exit + no success result → '실패'
  7. _parse_jsonl_status: stopped_by_flow_stop + no success result → '실패'
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

# sys.path 보장: flow/ 패키지 import 가능하도록 scripts/ 디렉터리 추가
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_FLOW_DIR = os.path.normpath(os.path.join(_TEST_DIR, ".."))
_SCRIPTS_DIR = os.path.normpath(os.path.join(_FLOW_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from flow.sessions import _HTTP_STATUS_MAP, _parse_jsonl_status  # noqa: E402


def _write_jsonl(lines: list[dict]) -> str:
    """임시 jsonl 파일에 레코드를 기록하고 경로를 반환한다."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        os.unlink(path)
        raise
    return path


# ---------------------------------------------------------------------------
# Case 1: _HTTP_STATUS_MAP 매핑 검증
# ---------------------------------------------------------------------------

def test_http_status_map_stopped():
    """_HTTP_STATUS_MAP['stopped'] 이 '완료'로 매핑되어야 한다."""
    assert _HTTP_STATUS_MAP.get("stopped") == "완료", (
        f"_HTTP_STATUS_MAP['stopped'] expected '완료', got {_HTTP_STATUS_MAP.get('stopped')!r}"
    )


def test_http_status_map_running():
    """_HTTP_STATUS_MAP['running'] 이 '실행중'으로 매핑되어야 한다."""
    assert _HTTP_STATUS_MAP.get("running") == "실행중"


# ---------------------------------------------------------------------------
# Case 2-7: _parse_jsonl_status 동작 검증
# ---------------------------------------------------------------------------

def test_parse_process_exit_marker_without_success():
    """process_exit 마커 + success result 없음 → '실패'."""
    meta = {"_meta": {"session_id": "wf-T-test-001", "ticket_id": "T-test"}}
    marker = {"type": "system", "subtype": "process_exit", "stopped_by": "flow-stop"}
    path = _write_jsonl([meta, marker])
    try:
        result = _parse_jsonl_status(path)
        assert result == "실패", f"Expected '실패', got {result!r}"
    finally:
        os.unlink(path)


def test_parse_process_exit_marker_with_success():
    """process_exit 마커 + success result → '완료'."""
    meta = {"_meta": {"session_id": "wf-T-test-002"}}
    success = {"type": "result", "subtype": "success"}
    marker = {"type": "system", "subtype": "process_exit", "stopped_by": "flow-stop"}
    path = _write_jsonl([meta, success, marker])
    try:
        result = _parse_jsonl_status(path)
        assert result == "완료", f"Expected '완료', got {result!r}"
    finally:
        os.unlink(path)


def test_parse_stopped_by_flow_stop_marker_without_success():
    """stopped_by_flow_stop 마커 + success result 없음 → '실패'.

    stopped_by_flow_stop 은 process_exit 동등 종료 마커로 인식된다 (T-904 W02).
    flow-stop 으로 강제 종료된 경우 success result 없이 종료되므로 '실패' 반환.
    """
    meta = {"_meta": {"session_id": "wf-T-test-003"}}
    marker = {"type": "system", "subtype": "stopped_by_flow_stop"}
    path = _write_jsonl([meta, marker])
    try:
        result = _parse_jsonl_status(path)
        assert result == "실패", f"Expected '실패', got {result!r}"
    finally:
        os.unlink(path)


def test_parse_stopped_by_flow_stop_marker_with_success():
    """stopped_by_flow_stop 마커 + success result → '완료'.

    성공 결과 후 flow-stop 이 호출된 엣지 케이스도 '완료'로 분류된다.
    """
    meta = {"_meta": {"session_id": "wf-T-test-004"}}
    success = {"type": "result", "subtype": "success"}
    marker = {"type": "system", "subtype": "stopped_by_flow_stop"}
    path = _write_jsonl([meta, success, marker])
    try:
        result = _parse_jsonl_status(path)
        assert result == "완료", f"Expected '완료', got {result!r}"
    finally:
        os.unlink(path)


def test_parse_no_exit_marker():
    """종료 마커가 없으면 → '실행중'."""
    meta = {"_meta": {"session_id": "wf-T-test-005"}}
    msg = {"type": "assistant", "content": "작업 중"}
    path = _write_jsonl([meta, msg])
    try:
        result = _parse_jsonl_status(path)
        assert result == "실행중", f"Expected '실행중', got {result!r}"
    finally:
        os.unlink(path)


def test_parse_empty_file():
    """빈 jsonl 파일 → '실행중' (종료 마커 없음으로 처리)."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    try:
        result = _parse_jsonl_status(path)
        assert result == "실행중", f"Expected '실행중', got {result!r}"
    finally:
        os.unlink(path)


def test_parse_nonexistent_file():
    """존재하지 않는 파일 → '실행중' (IOError fallback)."""
    result = _parse_jsonl_status("/tmp/nonexistent_wf_session_xyz.jsonl")
    assert result == "실행중", f"Expected '실행중', got {result!r}"


def test_parse_process_exit_is_sufficient_alone():
    """process_exit 마커가 파일 끝에 있으면 단독으로 종료 인식.

    이 케이스는 flow-stop 이 process_exit 만 append 하는 구현에서
    _parse_jsonl_status 가 즉시 비활성(실패/완료) 분기로 진입하는지 검증한다.
    """
    path = _write_jsonl([
        {"_meta": {"session_id": "wf-T-test-006"}},
        {"type": "assistant", "content": "some work"},
        {"type": "system", "subtype": "process_exit", "stopped_by": "flow-stop",
         "exit_signal": "SIGTERM"},
    ])
    try:
        result = _parse_jsonl_status(path)
        # success result 없으므로 '실패' (= 실행중 아님 = 즉시 비활성 인식 확인)
        assert result != "실행중", f"Expected non-running status, got {result!r}"
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# 간단한 실행기 (pytest 없이도 동작)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_http_status_map_stopped,
        test_http_status_map_running,
        test_parse_process_exit_marker_without_success,
        test_parse_process_exit_marker_with_success,
        test_parse_stopped_by_flow_stop_marker_without_success,
        test_parse_stopped_by_flow_stop_marker_with_success,
        test_parse_no_exit_marker,
        test_parse_empty_file,
        test_parse_nonexistent_file,
        test_parse_process_exit_is_sufficient_alone,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
