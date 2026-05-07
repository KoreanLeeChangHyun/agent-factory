"""test_stop.py - 워크플로우 강제 중지 (T-904) E2E 시나리오 검증.

plan.md W09 명세의 5개 시나리오를 자동/수동 분류로 검증한다:

  시나리오 1 (자동) — 4축 정리 5초 내 완료:
    mock 환경에서 stop_workflow() 호출이 5초 내 반환하는지 + 4축 dict 필드 모두 채워지는지

  시나리오 2 (자동) — PID 트리 SIGTERM:
    실제 dummy bash 프로세스 (`bash -c 'sleep 60 & sleep 60 & wait'`) spawn 후
    `_collect_pid_tree` + `_terminate_pid_tree` 로 부모-자식 모두 종료 확인

  시나리오 3 (자동) — jsonl process_exit 마커:
    임시 jsonl 파일에 `_append_process_exit_marker` 호출 후 tail 라인이
    `subtype == "process_exit"` + `stopped_by == "flow-stop"` 확인

  시나리오 4 (자동, mock) — 워크트리 제거 순서:
    `_kanban_move_to_open` 호출 시점이 PID wait 완료 + jsonl marker append
    이후인지 stop_workflow() 함수 흐름을 monkey-patch 로 시퀀스 검증

  시나리오 5 (자동, mock) — launcher timeout fallback:
    `urllib.request.urlopen` 모킹으로 timeout 강제 → http_launcher.cmd_launch
    내부에서 `subprocess.run` 으로 flow-stop 호출되는지 confirm

추가 단위 테스트:
  - `_collect_children_via_pgrep` 정상/실패 경로
  - `_pid_alive` 좀비 프로세스 (State Z) 인식
  - `_resolve_target_session` (활성 0개/1개/다중)
  - `_read_kanban_status` (정규식 파싱)
  - `_kanban_move_to_open` (In Progress 가 아닐 때 skip)
  - `_append_process_exit_marker` (newline 보강 + by_launcher_timeout 플래그)

mock 한계 항목 (수동 검증 분류):
  - Board UI [중지] 버튼 클릭 → confirm 모달 → 카드 5초 내 제거 (W07 fronent)
  - 실제 활성 워크플로우 종료 후 `flow-sessions` 즉시 빈 결과
  - Board API `POST /api/workflow/stop` 라이브 호출
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

# sys.path: .claude-organic/engine 디렉터리를 포함해 flow 패키지 import 가능하게 한다.
_TEST_DIR = Path(__file__).resolve().parent
_FLOW_DIR = _TEST_DIR.parent
_ENGINE_DIR = _FLOW_DIR.parent
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

from flow import stop as stop_module  # noqa: E402
from flow.stop import (  # noqa: E402
    _append_process_exit_marker,
    _build_result_table,
    _collect_children_via_pgrep,
    _collect_pid_tree,
    _kanban_move_to_open,
    _pid_alive,
    _read_kanban_status,
    _resolve_target_session,
    _send_signal,
    _terminate_pid_tree,
    stop_workflow,
)


# ---------------------------------------------------------------------------
# 헬퍼: dummy 프로세스 spawn (시나리오 2 + 단위 테스트 공용)
# ---------------------------------------------------------------------------

def _spawn_parent_with_children(num_children: int = 2) -> subprocess.Popen:
    """`bash -c 'sleep 60 & sleep 60 & wait'` 패턴으로 부모-자식 트리 spawn.

    반환된 Popen 의 pid 는 부모 bash, 자식들은 sleep 프로세스 N개.
    pgrep -P <부모pid> 로 자식 PID 가 수집되어야 한다.
    """
    children_cmd = " & ".join([f"sleep 60" for _ in range(num_children)])
    cmd = f"{children_cmd} & wait"
    proc = subprocess.Popen(
        ["bash", "-c", cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # pgrep 이 자식을 인식할 시간 (bash 가 sleep 을 spawn 할 시간)
    time.sleep(0.3)
    return proc


def _cleanup_proc(proc: subprocess.Popen) -> None:
    """테스트 후 안전 정리. 이미 죽었을 수 있으므로 best-effort."""
    try:
        proc.kill()
    except (ProcessLookupError, OSError):
        pass
    try:
        proc.wait(timeout=2)
    except (subprocess.TimeoutExpired, OSError):
        pass


# ---------------------------------------------------------------------------
# 시나리오 2 — PID 트리 SIGTERM (자동, 실제 프로세스)
# ---------------------------------------------------------------------------

class TestScenario2PidTreeSigterm(unittest.TestCase):
    """plan.md W09 시나리오 2: PID 트리 검증.

    dummy bash 부모-자식 spawn 후 `_collect_pid_tree` 가 자식 포함 수집,
    `_terminate_pid_tree` 가 모든 PID 종료 확정.
    """

    def test_collect_pid_tree_includes_children(self):
        """`_collect_pid_tree` 가 부모 + 자식 PID 를 모두 수집해야 한다."""
        proc = _spawn_parent_with_children(num_children=2)
        try:
            tree = _collect_pid_tree(proc.pid)
            self.assertIn(proc.pid, tree, "tree should include root parent pid")
            # leaves → root 순서이므로 마지막이 root
            self.assertEqual(tree[-1], proc.pid, "root should be last (leaves first order)")
            # bash + 2 sleep 자식 = 최소 3개 (환경 따라 더 있을 수 있음)
            self.assertGreaterEqual(
                len(tree),
                2,
                f"expected at least parent + 1 child, got {tree}",
            )
        finally:
            _cleanup_proc(proc)

    def test_terminate_pid_tree_kills_all(self):
        """`_terminate_pid_tree` 호출 후 모든 PID 가 종료되어야 한다."""
        proc = _spawn_parent_with_children(num_children=2)
        try:
            tree = _collect_pid_tree(proc.pid)
            killed_pids, exit_signal = _terminate_pid_tree(
                tree, force_kill_timeout=2.0
            )
            self.assertGreaterEqual(len(killed_pids), 1)
            self.assertIn(exit_signal, ("SIGTERM", "SIGKILL"))

            # 종료 확정: 최대 3초 대기
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                if not any(_pid_alive(p) for p in tree):
                    break
                time.sleep(0.1)
            still_alive = [p for p in tree if _pid_alive(p)]
            self.assertEqual(
                still_alive,
                [],
                f"all pids should be dead after _terminate_pid_tree, but {still_alive} alive",
            )
        finally:
            _cleanup_proc(proc)


# ---------------------------------------------------------------------------
# 시나리오 3 — jsonl process_exit 마커 (자동, 실제 파일)
# ---------------------------------------------------------------------------

class TestScenario3JsonlMarker(unittest.TestCase):
    """plan.md W09 시나리오 3: jsonl `process_exit` 마커 추가 검증."""

    def setUp(self) -> None:
        # 임시 sessions 디렉터리 생성 + 모듈 상수 monkey-patch
        self.tmpdir = tempfile.mkdtemp(prefix="wf_test_stop_jsonl_")
        self._orig_sessions_dir = stop_module._SESSIONS_DIR
        stop_module._SESSIONS_DIR = self.tmpdir

    def tearDown(self) -> None:
        stop_module._SESSIONS_DIR = self._orig_sessions_dir
        # tmpdir 정리
        for f in os.listdir(self.tmpdir):
            try:
                os.unlink(os.path.join(self.tmpdir, f))
            except OSError:
                pass
        os.rmdir(self.tmpdir)

    def _write_jsonl(self, sid: str, lines: list[dict]) -> str:
        path = os.path.join(self.tmpdir, f"{sid}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        return path

    def test_marker_appended_with_correct_subtype(self):
        """append 후 마지막 라인이 process_exit + flow-stop stopped_by 이어야 한다."""
        sid = "wf-T-test-marker-001"
        path = self._write_jsonl(
            sid,
            [
                {"_meta": {"session_id": sid, "ticket_id": "T-test"}},
                {"type": "assistant", "content": "작업 중"},
            ],
        )
        added, err = _append_process_exit_marker(
            sid,
            killed_pids=[12345, 12346],
            exit_signal="SIGTERM",
            flush_wait=0.0,  # 테스트 가속
        )
        self.assertTrue(added, f"marker append failed: {err}")
        self.assertIsNone(err)
        # tail
        with open(path, "r", encoding="utf-8") as f:
            tail = f.readlines()[-1].strip()
        marker = json.loads(tail)
        self.assertEqual(marker["type"], "system")
        self.assertEqual(marker["subtype"], "process_exit")
        self.assertEqual(marker["stopped_by"], "flow-stop")
        self.assertEqual(marker["exit_signal"], "SIGTERM")
        self.assertEqual(marker["killed_pids"], [12345, 12346])
        self.assertIn("timestamp", marker)

    def test_marker_with_by_launcher_timeout(self):
        """`by_launcher_timeout=True` 시 메타에 플래그 기록."""
        sid = "wf-T-test-marker-002"
        self._write_jsonl(sid, [{"_meta": {"session_id": sid}}])
        added, _err = _append_process_exit_marker(
            sid,
            killed_pids=[1],
            exit_signal="SIGKILL",
            flush_wait=0.0,
            by_launcher_timeout=True,
        )
        self.assertTrue(added)
        path = os.path.join(self.tmpdir, f"{sid}.jsonl")
        with open(path, "r", encoding="utf-8") as f:
            tail = f.readlines()[-1].strip()
        marker = json.loads(tail)
        self.assertTrue(marker.get("by_launcher_timeout"))

    def test_marker_appended_when_file_missing_newline(self):
        """파일 끝 newline 누락 시에도 leading newline 보강하여 별도 라인으로 append."""
        sid = "wf-T-test-marker-003"
        path = os.path.join(self.tmpdir, f"{sid}.jsonl")
        # newline 없이 단일 라인 작성
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"_meta": {"session_id": sid}}, ensure_ascii=False))
        added, _err = _append_process_exit_marker(
            sid, killed_pids=[], exit_signal="SIGTERM", flush_wait=0.0,
        )
        self.assertTrue(added)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # 두 줄로 나뉘어 있어야 함 (leading newline 보강 결과)
        lines = content.splitlines()
        self.assertEqual(len(lines), 2)
        marker = json.loads(lines[-1])
        self.assertEqual(marker["subtype"], "process_exit")

    def test_marker_missing_jsonl_returns_error(self):
        """jsonl 파일이 없으면 added=False + error message."""
        added, err = _append_process_exit_marker(
            "wf-T-nonexistent-999",
            killed_pids=[],
            exit_signal="SIGTERM",
            flush_wait=0.0,
        )
        self.assertFalse(added)
        self.assertIsNotNone(err)
        self.assertIn("jsonl not found", err)


# ---------------------------------------------------------------------------
# 시나리오 1 — 4축 정리 5초 내 완료 (mock)
# ---------------------------------------------------------------------------

class TestScenario1FourAxisCleanup(unittest.TestCase):
    """plan.md W09 시나리오 1: 활성 세션 → flow-stop → 5초 내 4축 정리.

    실제 활성 워크플로우 환경 없이 mock 으로 4축 dict 필드 모두 채워지는지 확인.
    """

    def test_returns_within_5_seconds_with_full_dict(self):
        """`stop_workflow()` 호출이 5초 내 반환 + dict 필드 모두 존재."""
        # 활성 세션 1개 mock
        fake_sessions = [
            {
                "session_id": "wf-T-904-20260507-141555",
                "ticket_id": "T-904",
                "status": "실행중",
            }
        ]

        with mock.patch.object(
            stop_module, "get_sessions", return_value=(fake_sessions, "test")
        ), mock.patch.object(
            stop_module, "_resolve_root_pid", return_value=None
        ), mock.patch.object(
            stop_module,
            "_kanban_move_to_open",
            return_value=("skipped:Open", "current status is 'Open'"),
        ), mock.patch.object(
            stop_module,
            "_append_process_exit_marker",
            return_value=(False, "jsonl not found: /tmp/fake.jsonl"),
        ):
            t0 = time.monotonic()
            result = stop_workflow(ticket="T-904", session_id=None)
            elapsed = time.monotonic() - t0

        self.assertLess(elapsed, 5.0, f"stop_workflow took {elapsed:.2f}s (>=5s)")
        # 4축 dict 필드 존재
        for key in (
            "ok",
            "session_id",
            "ticket_id",
            "killed_pids",
            "jsonl_marker_added",
            "kanban_transition",
            "worktree_action",
            "errors",
        ):
            self.assertIn(key, result, f"missing key in result: {key}")
        self.assertEqual(result["session_id"], "wf-T-904-20260507-141555")
        self.assertEqual(result["ticket_id"], "T-904")

    def test_no_active_session_returns_error(self):
        """활성 세션 0개 + ticket/session_id None → errors 에 'no active session'."""
        with mock.patch.object(stop_module, "get_sessions", return_value=([], "test")):
            result = stop_workflow(ticket=None, session_id=None)
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("no active session" in e for e in result["errors"]),
            f"expected 'no active session' in errors, got {result['errors']}",
        )


# ---------------------------------------------------------------------------
# 시나리오 4 — 워크트리 제거 순서 (mock 시퀀스)
# ---------------------------------------------------------------------------

class TestScenario4WorktreeOrder(unittest.TestCase):
    """plan.md W09 시나리오 4: 워크트리 제거 순서 강제 검증.

    `stop_workflow()` 내부 호출 순서를 monkey-patch 로 추적:
      1. PID 트리 SIGTERM/wait
      2. jsonl `_append_process_exit_marker`
      3. `_kanban_move_to_open` (cmd_move 가 워크트리 정리 자동 트리거)
    """

    def test_call_order_is_pid_then_jsonl_then_kanban(self):
        """호출 순서가 _terminate_pid_tree → _append_process_exit_marker → _kanban_move_to_open 이어야 한다."""
        call_log: list[str] = []

        fake_sessions = [
            {
                "session_id": "wf-T-904-20260507-141555",
                "ticket_id": "T-904",
                "status": "실행중",
            }
        ]

        def fake_resolve_root_pid(_sid):
            call_log.append("resolve_root_pid")
            return 99999  # 가짜 PID

        def fake_collect_pid_tree(_pid):
            call_log.append("collect_pid_tree")
            return [99999]

        def fake_terminate(*_args, **_kwargs):
            call_log.append("terminate_pid_tree")
            return ([99999], "SIGTERM")

        def fake_pid_alive(_pid):
            # _terminate_pid_tree 후 _pid_alive 호출은 죽은 것으로
            return False

        def fake_marker(*_args, **_kwargs):
            call_log.append("append_marker")
            return (True, None)

        def fake_kanban(_ticket, **_kwargs):
            call_log.append("kanban_move")
            return ("In Progress → Open", None)

        with mock.patch.object(
            stop_module, "get_sessions", return_value=(fake_sessions, "test")
        ), mock.patch.object(
            stop_module, "_resolve_root_pid", side_effect=fake_resolve_root_pid
        ), mock.patch.object(
            stop_module, "_collect_pid_tree", side_effect=fake_collect_pid_tree
        ), mock.patch.object(
            stop_module, "_terminate_pid_tree", side_effect=fake_terminate
        ), mock.patch.object(
            stop_module, "_pid_alive", side_effect=fake_pid_alive
        ), mock.patch.object(
            stop_module, "_append_process_exit_marker", side_effect=fake_marker
        ), mock.patch.object(
            stop_module, "_kanban_move_to_open", side_effect=fake_kanban
        ):
            result = stop_workflow(ticket="T-904", session_id=None)

        # 순서 검증: terminate_pid_tree → append_marker → kanban_move
        idx_terminate = call_log.index("terminate_pid_tree")
        idx_marker = call_log.index("append_marker")
        idx_kanban = call_log.index("kanban_move")
        self.assertLess(
            idx_terminate, idx_marker,
            f"PID kill must precede jsonl marker; log={call_log}",
        )
        self.assertLess(
            idx_marker, idx_kanban,
            f"jsonl marker must precede kanban move; log={call_log}",
        )
        # 결과 검증
        self.assertTrue(result["ok"])
        self.assertEqual(result["kanban_transition"], "In Progress → Open")
        self.assertEqual(result["worktree_action"], "cleaned_via_cmd_move")


# ---------------------------------------------------------------------------
# 시나리오 5 — launcher timeout fallback (mock)
# ---------------------------------------------------------------------------

class TestScenario5LauncherTimeoutFallback(unittest.TestCase):
    """plan.md W09 시나리오 5: launcher timeout → flow-stop best-effort 호출 검증.

    `urllib.request.urlopen` 모킹으로 timeout 강제, http_launcher.cmd_launch
    내부에서 subprocess.run 으로 flow-stop 호출되는지 확인.
    """

    def test_urlopen_timeout_triggers_flow_stop_subprocess(self):
        """URLError(TimeoutError) → subprocess.run 으로 flow-stop 호출.

        cmd_launch 는 다단계 가드(티켓 상태/포트/서버/재진입)를 통과해야 urlopen
        에 도달하므로 모두 mock 으로 우회한 뒤 _http_post_json 이 raise 하도록
        세팅한다.
        """
        from flow import http_launcher

        timeout_error = urllib.error.URLError(reason=TimeoutError("timed out"))

        captured: list[list[str]] = []

        def fake_subprocess_run(cmd, **kwargs):
            captured.append(list(cmd))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

        with mock.patch.object(
            http_launcher, "_read_ticket_status", return_value="In Progress"
        ), mock.patch.object(
            http_launcher, "_kanban_move_progress", return_value=None
        ), mock.patch.object(
            http_launcher, "_normalize_command", return_value="/wf -s 904"
        ), mock.patch.object(
            http_launcher, "_resolve_server_port", return_value=9927
        ), mock.patch.object(
            http_launcher, "_is_server_running", return_value=True
        ), mock.patch.dict(
            os.environ, {}, clear=False
        ), mock.patch.object(
            http_launcher, "_http_post_json", side_effect=timeout_error
        ), mock.patch.object(
            http_launcher.subprocess, "run", side_effect=fake_subprocess_run
        ):
            # 재진입 감지 환경변수 클리어
            os.environ.pop("_WF_SESSION_TYPE", None)
            rc = http_launcher.cmd_launch("T-904", "implement")

        self.assertEqual(rc, 1, "cmd_launch should return 1 on timeout")
        flow_stop_calls = [c for c in captured if c and "flow-stop" in c[0]]
        self.assertGreater(
            len(flow_stop_calls), 0,
            f"flow-stop subprocess not invoked; captured={captured}",
        )
        first = flow_stop_calls[0]
        self.assertIn("T-904", first)
        self.assertIn("--by-launcher-timeout", first)
        self.assertIn("--json", first)


# ---------------------------------------------------------------------------
# 단위 테스트 — _collect_children_via_pgrep
# ---------------------------------------------------------------------------

class TestCollectChildrenViaPgrep(unittest.TestCase):
    def test_returns_empty_for_dead_pid(self):
        """존재하지 않는 PID 의 자식은 빈 리스트."""
        children = _collect_children_via_pgrep(99999999)
        self.assertEqual(children, [])

    def test_returns_children_for_live_parent(self):
        """살아있는 부모 PID 의 자식 PID 를 수집한다."""
        proc = _spawn_parent_with_children(num_children=2)
        try:
            children = _collect_children_via_pgrep(proc.pid)
            # bash 부모는 sleep 자식들을 spawn → 최소 1개 이상 자식 존재해야 함
            self.assertGreaterEqual(
                len(children), 1, f"expected sleep children, got {children}"
            )
        finally:
            _cleanup_proc(proc)

    def test_handles_pgrep_missing(self):
        """pgrep 미설치 시 빈 리스트 반환 (FileNotFoundError 처리)."""
        with mock.patch.object(
            stop_module.subprocess,
            "run",
            side_effect=FileNotFoundError("pgrep not installed"),
        ):
            children = _collect_children_via_pgrep(1)
        self.assertEqual(children, [])


# ---------------------------------------------------------------------------
# 단위 테스트 — _pid_alive
# ---------------------------------------------------------------------------

class TestPidAlive(unittest.TestCase):
    def test_self_pid_alive(self):
        """현재 프로세스 PID 는 살아있다."""
        self.assertTrue(_pid_alive(os.getpid()))

    def test_dead_pid_not_alive(self):
        """존재하지 않는 PID 는 dead."""
        self.assertFalse(_pid_alive(99999999))

    def test_send_signal_to_dead_pid_returns_false(self):
        """죽은 PID 에 시그널 전송은 False 반환 (예외 X)."""
        self.assertFalse(_send_signal(99999999, signal.SIGTERM))


# ---------------------------------------------------------------------------
# 단위 테스트 — _resolve_target_session
# ---------------------------------------------------------------------------

class TestResolveTargetSession(unittest.TestCase):
    def test_no_active_session(self):
        with mock.patch.object(stop_module, "get_sessions", return_value=([], "test")):
            sid, tid, err = _resolve_target_session(None, None)
        self.assertIsNone(sid)
        self.assertIsNone(tid)
        self.assertEqual(err, "no active session")

    def test_single_active_auto_resolve(self):
        sessions = [
            {"session_id": "wf-T-904-001", "ticket_id": "T-904", "status": "실행중"}
        ]
        with mock.patch.object(stop_module, "get_sessions", return_value=(sessions, "test")):
            sid, tid, err = _resolve_target_session(None, None)
        self.assertEqual(sid, "wf-T-904-001")
        self.assertEqual(tid, "T-904")
        self.assertIsNone(err)

    def test_multiple_active_returns_error(self):
        sessions = [
            {"session_id": "wf-A", "ticket_id": "T-1", "status": "실행중"},
            {"session_id": "wf-B", "ticket_id": "T-2", "status": "실행중"},
        ]
        with mock.patch.object(stop_module, "get_sessions", return_value=(sessions, "test")):
            sid, tid, err = _resolve_target_session(None, None)
        self.assertIsNone(sid)
        self.assertIn("multiple active", err or "")

    def test_ticket_match_in_active(self):
        sessions = [
            {"session_id": "wf-A", "ticket_id": "T-1", "status": "실행중"},
            {"session_id": "wf-B", "ticket_id": "T-2", "status": "실행중"},
        ]
        with mock.patch.object(stop_module, "get_sessions", return_value=(sessions, "test")):
            sid, tid, err = _resolve_target_session("T-2", None)
        self.assertEqual(sid, "wf-B")
        self.assertEqual(tid, "T-2")
        self.assertIsNone(err)

    def test_session_id_match_in_inactive_allowed(self):
        """이미 종료된 세션도 session_id 명시 시 매칭 허용 (멱등 정리)."""
        sessions = [
            {"session_id": "wf-A", "ticket_id": "T-1", "status": "완료"},
        ]
        with mock.patch.object(stop_module, "get_sessions", return_value=(sessions, "test")):
            sid, tid, err = _resolve_target_session(None, "wf-A")
        self.assertEqual(sid, "wf-A")
        self.assertIsNone(err)

    def test_session_id_not_found(self):
        with mock.patch.object(stop_module, "get_sessions", return_value=([], "test")):
            sid, tid, err = _resolve_target_session(None, "wf-MISSING")
        self.assertIsNone(sid)
        self.assertIn("session not found", err or "")


# ---------------------------------------------------------------------------
# 단위 테스트 — _read_kanban_status / _kanban_move_to_open
# ---------------------------------------------------------------------------

class TestKanbanHelpers(unittest.TestCase):
    def test_read_kanban_status_parses_in_progress(self):
        fake = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="ID: T-904\nStatus: In Progress\nTitle: ...",
            stderr="",
        )
        with mock.patch.object(stop_module.subprocess, "run", return_value=fake), \
             mock.patch("os.path.isfile", return_value=True):
            status, err = _read_kanban_status("T-904")
        self.assertEqual(status, "In Progress")
        self.assertIsNone(err)

    def test_read_kanban_status_parses_korean_label(self):
        fake = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="ID: T-904\n상태: Open\n제목: ...",
            stderr="",
        )
        with mock.patch.object(stop_module.subprocess, "run", return_value=fake), \
             mock.patch("os.path.isfile", return_value=True):
            status, err = _read_kanban_status("T-904")
        self.assertEqual(status, "Open")

    def test_read_kanban_status_handles_exit_nonzero(self):
        fake = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="ticket not found"
        )
        with mock.patch.object(stop_module.subprocess, "run", return_value=fake), \
             mock.patch("os.path.isfile", return_value=True):
            status, err = _read_kanban_status("T-999")
        self.assertIsNone(status)
        self.assertIn("exit=1", err or "")

    def test_kanban_move_skips_if_not_in_progress(self):
        """현재 상태가 In Progress 가 아니면 skip + 경고 메시지 반환."""
        with mock.patch.object(
            stop_module,
            "_read_kanban_status",
            return_value=("Review", None),
        ):
            transition, err = _kanban_move_to_open("T-904")
        self.assertTrue(transition.startswith("skipped:"))
        self.assertIn("Review", transition)
        self.assertIsNotNone(err)

    def test_kanban_move_invokes_subprocess_when_in_progress(self):
        """In Progress 면 flow-kanban move <ticket> open 호출."""
        captured_args: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            captured_args.append(list(cmd))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        with mock.patch.object(
            stop_module,
            "_read_kanban_status",
            return_value=("In Progress", None),
        ), mock.patch("os.path.isfile", return_value=True), \
             mock.patch.object(stop_module.subprocess, "run", side_effect=fake_run):
            transition, err = _kanban_move_to_open("T-904")
        self.assertEqual(transition, "In Progress → Open")
        self.assertIsNone(err)
        self.assertEqual(len(captured_args), 1)
        cmd = captured_args[0]
        self.assertIn("move", cmd)
        self.assertIn("T-904", cmd)
        self.assertIn("open", cmd)


# ---------------------------------------------------------------------------
# 단위 테스트 — _build_result_table 출력
# ---------------------------------------------------------------------------

class TestResultTableRendering(unittest.TestCase):
    def test_table_contains_key_fields(self):
        result = {
            "ok": True,
            "session_id": "wf-T-904-001",
            "ticket_id": "T-904",
            "killed_pids": [123, 456],
            "jsonl_marker_added": True,
            "kanban_transition": "In Progress → Open",
            "worktree_action": "cleaned_via_cmd_move",
            "errors": [],
        }
        text = _build_result_table(result)
        # ANSI escape 가 포함될 수 있으므로 핵심 필드만 검증
        self.assertIn("flow-stop", text)
        self.assertIn("T-904", text)
        self.assertIn("wf-T-904-001", text)
        self.assertIn("123", text)
        self.assertIn("In Progress", text)


# ---------------------------------------------------------------------------
# 간단한 실행기 (pytest 없이도 동작) — test_sessions_status.py 패턴 따름
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # unittest 기본 러너 사용 (pytest 도 동일하게 인식)
    unittest.main(verbosity=2)
