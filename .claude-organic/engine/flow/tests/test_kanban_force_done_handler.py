"""test_kanban_force_done_handler.py - T-418 handler 회귀 테스트.

검증 범위:
  T1: test_open_done_force_branch_calls_move_with_force
      force=true body 호출 시 'flow-kanban move T-NNN done --force' subprocess 검증 + 200 응답
  T2: test_open_delete_endpoint_invokes_flow_kanban_delete
      _handle_kanban_delete 호출 시 'flow-kanban delete T-NNN' subprocess 검증 + 200 + worktree_removed 키
  T3: test_dirty_worktree_blocks_force_done_without_force_dirty
      _get_dirty_files 모킹으로 dirty 파일 반환 + force_dirty=false body → 409 + error_kind='dirty_worktree'
  T4: test_delete_blocked_when_derived_ticket_open
      tempfile 로 격리된 tickets/ 트리 + derived-from 자식(Open 상태) → 409 + error_kind='derived_blocked'

generic.py 는 board/server 패키지 내부 상대 import 를 포함하므로
모듈 전체 import 가 불가하다. _load_generic_helpers() 로 파일 상단 독립 영역 +
_classify_done_failure / _get_dirty_files / _check_derived_blocked 을 격리 추출한다.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

# handlers/ 경로 계산: tests/ → engine/ → .claude-organic/ → board/server/handlers/
_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_HANDLERS_DIR = _WORKTREE_ROOT / ".claude-organic" / "board" / "server" / "handlers"
_GENERIC_PY = _HANDLERS_DIR / "generic.py"
_HANDLER_COMMON_PY = _HANDLERS_DIR / "_handler_common.py"
_KANBAN_DONE_RE_PY = _HANDLERS_DIR / "_kanban_done_re.py"


# ─── 격리 로드 헬퍼 ──────────────────────────────────────────────────────────


def _load_generic_helpers() -> dict:
    """generic.py + _handler_common.py + _kanban_done_re.py 에서 헬퍼들을 격리 추출한다.

    T-499 위계 재정리 후 심볼은 다음 3 모듈에 분산되어 있다:
      * _handler_common.py — _TICKET_RE / _KANBAN_ALL_DIRS / _import_*_cli (standalone)
      * _kanban_done_re.py — _classify_done_failure + _DONE_* / _UNDO_* 정규식 (standalone)
      * generic.py         — GenericHandlerMixin 클래스 (board/server 패키지 상대 import 포함)

    board/server 패키지 상대 import 를 우회하기 위해 standalone 2 모듈은 파일 전체를,
    generic.py 는 'from ..state import ...' 직전 헤더 + GenericHandlerMixin 클래스 영역만
    exec 로 합쳐 단일 네임스페이스에 적재한다.

    Returns:
        {'_classify_done_failure', '_TICKET_RE', '_KANBAN_ALL_DIRS',
         'GenericHandlerMixin', ...} 가 포함된 네임스페이스 dict.
    """
    common_src = _HANDLER_COMMON_PY.read_text(encoding="utf-8")
    re_src = _KANBAN_DONE_RE_PY.read_text(encoding="utf-8")
    src = _GENERIC_PY.read_text(encoding="utf-8")

    # generic.py — 패키지 의존 import 시작 지점까지 헤더 + GenericHandlerMixin 클래스
    cut = src.find("from ..state import")
    header = src[:cut]
    class_start = src.find("\nclass GenericHandlerMixin")
    class_src = src[class_start:]

    # 실행 네임스페이스에 필요한 모듈 사전 주입
    ns: dict = {
        "__builtins__": __builtins__,
        "os": os,
        "sys": sys,
        "json": json,
        "re": __import__("re"),
        "time": __import__("time"),
        "io": io,
    }

    # 1단계: _handler_common (_TICKET_RE / _KANBAN_ALL_DIRS / _import_*_cli)
    exec(common_src, ns)  # noqa: S102

    # 2단계: _kanban_done_re (_classify_done_failure + 정규식)
    exec(re_src, ns)  # noqa: S102

    # 3단계: generic.py 헤더 + GenericHandlerMixin 클래스
    exec(header, ns)  # noqa: S102
    ns.setdefault("logger", MagicMock())
    ns.setdefault("_read_kanban_tickets", MagicMock(return_value={}))
    ns.setdefault("sse_manager", MagicMock())
    ns.setdefault("poll_tracker", MagicMock())

    exec(class_src, ns)  # noqa: S102
    return ns


_ns = _load_generic_helpers()
_classify_done_failure = _ns["_classify_done_failure"]
_TICKET_RE = _ns["_TICKET_RE"]
_KANBAN_ALL_DIRS = _ns["_KANBAN_ALL_DIRS"]
GenericHandlerMixin = _ns["GenericHandlerMixin"]


# ─── 핸들러 테스트용 Stub 클래스 ─────────────────────────────────────────────


class _StubHandler(GenericHandlerMixin):
    """GenericHandlerMixin 을 테스트하기 위한 최소 stub.

    HTTPServer 기반 속성 없이도 동작하도록 _send_json / _send_error /
    _send_json_with_status / _read_json_body 를 직접 구현한다.
    """

    def __init__(self, body: dict | None = None):
        self._request_body = body or {}
        self.responses: list[tuple[int, dict | str]] = []
        # 인스턴스 path 속성은 http_router 에서 주입되지만 테스트에서는 불필요
        self.path = "/api/kanban/done"

    def _read_json_body(self) -> dict:
        return dict(self._request_body)

    def _send_json(self, data: dict) -> None:
        self.responses.append((200, data))

    def _send_error(self, status: int, message: str) -> None:
        self.responses.append((status, {"error": message}))

    def _send_json_with_status(self, status: int, data: dict) -> None:
        self.responses.append((status, data))

    # BaseHTTPServer 메서드 stub (호출되면 무시)
    def send_response(self, *args, **kwargs): pass
    def send_header(self, *args, **kwargs): pass
    def end_headers(self, *args, **kwargs): pass

    @property
    def last_status(self) -> int:
        return self.responses[-1][0] if self.responses else 0

    @property
    def last_body(self) -> dict | str:
        return self.responses[-1][1] if self.responses else {}


# ─── T1: force=true 분기 — flow-kanban move done --force 호출 검증 ───────────


class TestOpenDoneForceBranchCallsMoveWithForce(unittest.TestCase):
    """T1: force=true body 호출 시 subprocess.run 으로
    'flow-kanban move T-NNN done --force' 를 호출하고 200 응답을 반환한다.
    """

    def test_open_done_force_branch_calls_move_with_force(self):
        """force=true + Open XML 존재 + 워크트리 import 실패 환경 → 200 + ok=true."""
        ticket = "T-999"

        with tempfile.TemporaryDirectory() as tmpdir:
            # tickets/open/<ticket>.xml 생성 (force 분기 사전 검증 통과용)
            open_dir = os.path.join(tmpdir, ".claude-organic", "tickets", "open")
            os.makedirs(open_dir, exist_ok=True)
            open_xml = os.path.join(open_dir, f"{ticket}.xml")
            with open(open_xml, "w") as f:
                f.write(f"<ticket><metadata><number>{ticket}</number></metadata></ticket>")

            # flow-kanban 실행 파일 경로도 tmpdir 기반으로 패치
            bin_dir = os.path.join(tmpdir, ".claude-organic", "bin")
            os.makedirs(bin_dir, exist_ok=True)
            flow_kanban_path = os.path.join(bin_dir, "flow-kanban")
            with open(flow_kanban_path, "w") as f:
                f.write("#!/bin/sh\necho 'ok'\n")
            os.chmod(flow_kanban_path, 0o755)

            handler = _StubHandler(body={"ticket": ticket, "force": True, "force_dirty": False})

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "done"
            mock_result.stderr = ""

            with patch("subprocess.run", return_value=mock_result) as mock_run, \
                 patch("os.getcwd", return_value=tmpdir), \
                 patch.dict(sys.modules, {"flow": None, "flow.worktree_manager": None}):
                # worktree_manager import 실패 시뮬레이션 (ImportError)
                import importlib
                orig_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

                def _fake_import(name, *args, **kwargs):
                    if "worktree_manager" in name or (name == "flow" and args and "worktree_manager" in str(args)):
                        raise ImportError("stub: worktree disabled")
                    return orig_import(name, *args, **kwargs)

                with patch("builtins.__import__", side_effect=_fake_import):
                    handler._handle_kanban_done()

            # subprocess.run 이 호출되었는지 검증 (flow-kanban move <ticket> done --force)
            self.assertTrue(mock_run.called, "subprocess.run 이 호출되어야 한다")
            call_args = mock_run.call_args
            cmd = call_args[0][0]  # 첫 번째 positional 인자가 커맨드 리스트
            self.assertIn("move", cmd, "커맨드에 'move' 가 포함되어야 한다")
            self.assertIn(ticket, cmd, f"커맨드에 {ticket} 이 포함되어야 한다")
            self.assertIn("done", cmd, "커맨드에 'done' 이 포함되어야 한다")
            self.assertIn("--force", cmd, "커맨드에 '--force' 가 포함되어야 한다")

            # 200 응답 + ok=true 검증
            self.assertEqual(handler.last_status, 200)
            body = handler.last_body
            self.assertTrue(body.get("ok"), "응답 ok 가 True 여야 한다")
            self.assertTrue(body.get("force"), "응답 force 가 True 여야 한다")


# ─── T2: delete endpoint — flow-kanban delete 호출 + worktree_removed 키 ──────


class TestOpenDeleteEndpointInvokesFlowKanbanDelete(unittest.TestCase):
    """T2: _handle_kanban_delete 호출 시 'flow-kanban delete T-NNN' subprocess 호출 +
    200 응답 + worktree_removed 키 존재 검증.
    """

    def test_open_delete_endpoint_invokes_flow_kanban_delete(self):
        """파생 티켓 없는 정상 경로 → subprocess 'delete' 호출 + 200 + worktree_removed."""
        ticket = "T-888"

        with tempfile.TemporaryDirectory() as tmpdir:
            # tickets/ 디렉터리 생성 (파생 티켓 없음)
            tickets_dir = os.path.join(tmpdir, ".claude-organic", "tickets")
            for d in _KANBAN_ALL_DIRS:
                os.makedirs(os.path.join(tickets_dir, d), exist_ok=True)

            handler = _StubHandler(body={"ticket": ticket})

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = f"{ticket} deleted"
            mock_result.stderr = ""

            # worktree_manager 를 sys.modules 에 직접 주입하여 ImportError 우회
            import types
            fake_wm = MagicMock()
            fake_wm.remove_worktree.side_effect = ImportError("stub: worktree disabled")
            fake_flow_mod = types.ModuleType("flow")
            # flow 패키지 자체를 mock 으로 대체하면 from flow import worktree_manager 에서
            # ImportError 를 발생시킬 수 있도록 flow.worktree_manager 를 None 으로 설정
            sys.modules["flow.worktree_manager"] = None  # type: ignore[assignment]
            try:
                with patch("subprocess.run", return_value=mock_result) as mock_run, \
                     patch("os.getcwd", return_value=tmpdir):
                    handler._handle_kanban_delete()
            finally:
                sys.modules.pop("flow.worktree_manager", None)

            # subprocess.run 이 'delete' 커맨드로 호출되었는지 검증
            self.assertTrue(mock_run.called, "subprocess.run 이 호출되어야 한다")
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            self.assertIn("delete", cmd, "커맨드에 'delete' 가 포함되어야 한다")
            self.assertIn(ticket, cmd, f"커맨드에 {ticket} 이 포함되어야 한다")

            # 200 응답 검증
            self.assertEqual(handler.last_status, 200)
            body = handler.last_body
            self.assertTrue(body.get("ok"), "응답 ok 가 True 여야 한다")
            self.assertIn("worktree_removed", body, "응답에 worktree_removed 키가 있어야 한다")


# ─── T3: dirty 워크트리 → force_dirty=false 시 409 차단 ──────────────────────


class TestDirtyWorktreeBlocksForceDoneWithoutForceDirty(unittest.TestCase):
    """T3: _get_dirty_files 가 비어있지 않은 목록을 반환하고
    force_dirty=false body → 409 + error_kind='dirty_worktree' + dirty_files 비어있지 않음.
    """

    def test_dirty_worktree_blocks_force_done_without_force_dirty(self):
        """dirty 파일 존재 + force_dirty=false → 409 + error_kind='dirty_worktree'."""
        ticket = "T-777"
        dirty_file_list = ["src/main.py", "README.md"]

        with tempfile.TemporaryDirectory() as tmpdir:
            # tickets/open/<ticket>.xml 생성
            open_dir = os.path.join(tmpdir, ".claude-organic", "tickets", "open")
            os.makedirs(open_dir, exist_ok=True)
            open_xml = os.path.join(open_dir, f"{ticket}.xml")
            with open(open_xml, "w") as f:
                f.write(f"<ticket><metadata><number>{ticket}</number></metadata></ticket>")

            handler = _StubHandler(body={"ticket": ticket, "force": True, "force_dirty": False})

            # worktree_manager mock: has_uncommitted_changes=True, get_worktree_path 반환
            mock_wm = MagicMock()
            mock_wm.get_worktree_path.return_value = "/fake/worktree/path"
            mock_wm.has_uncommitted_changes.return_value = True

            with patch("os.getcwd", return_value=tmpdir), \
                 patch.object(handler, "_get_dirty_files", return_value=dirty_file_list):

                # sys.path 조작 + from flow import worktree_manager 패치
                import types
                fake_flow = types.ModuleType("flow")
                fake_flow.worktree_manager = mock_wm
                sys.modules["flow"] = fake_flow
                sys.modules["flow.worktree_manager"] = mock_wm

                try:
                    handler._handle_kanban_done()
                finally:
                    sys.modules.pop("flow", None)
                    sys.modules.pop("flow.worktree_manager", None)

            # 409 응답 검증
            self.assertEqual(handler.last_status, 409, "dirty + force_dirty=false 시 409 여야 한다")
            body = handler.last_body
            self.assertFalse(body.get("ok"), "ok 가 False 여야 한다")
            self.assertEqual(body.get("error_kind"), "dirty_worktree",
                             "error_kind 가 'dirty_worktree' 여야 한다")
            self.assertTrue(len(body.get("dirty_files", [])) > 0,
                            "dirty_files 가 비어있지 않아야 한다")


# ─── T4: delete — derived-from 자식 Open 상태 → 409 차단 ────────────────────


def _make_ticket_xml(ticket: str, status: str, derived_from: str | None = None) -> str:
    """테스트용 티켓 XML 을 생성한다.

    Args:
        ticket: 티켓 번호 (예: 'T-001').
        status: 칸반 상태 (예: 'Open', 'Done').
        derived_from: 이 티켓의 derived-from 원본 티켓 번호 (없으면 None).

    Returns:
        XML 문자열.
    """
    relations_block = ""
    if derived_from:
        relations_block = (
            "<relations>"
            f'<relation type="derived-from" ticket="{derived_from}"/>'
            "</relations>"
        )
    return (
        f"<ticket>"
        f"<metadata>"
        f"<number>{ticket}</number>"
        f"<status>{status}</status>"
        f"</metadata>"
        f"{relations_block}"
        f"</ticket>"
    )


class TestDeleteBlockedWhenDerivedTicketOpen(unittest.TestCase):
    """T4: derived-from 자식 티켓이 Open 상태일 때 _handle_kanban_delete 호출 시
    409 + error_kind='derived_blocked' 를 반환한다.

    tempfile 로 격리된 .claude-organic/tickets/ 트리를 구성하여
    실제 파일시스템 읽기를 테스트한다.
    """

    def test_delete_blocked_when_derived_ticket_open(self):
        """자식 티켓 T-001(Open) 이 T-999 를 derived-from 으로 참조 → 409 + derived_blocked."""
        parent_ticket = "T-999"
        child_ticket = "T-001"
        child_status = "Open"

        with tempfile.TemporaryDirectory() as tmpdir:
            tickets_dir = os.path.join(tmpdir, ".claude-organic", "tickets")

            # 모든 상태 디렉터리 생성
            for d in _KANBAN_ALL_DIRS:
                os.makedirs(os.path.join(tickets_dir, d), exist_ok=True)

            # Open 디렉터리에 파생 자식 티켓 XML 배치
            child_xml_path = os.path.join(tickets_dir, "open", f"{child_ticket}.xml")
            child_xml = _make_ticket_xml(child_ticket, child_status, derived_from=parent_ticket)
            with open(child_xml_path, "w", encoding="utf-8") as f:
                f.write(child_xml)

            handler = _StubHandler(body={"ticket": parent_ticket})

            with patch("os.getcwd", return_value=tmpdir):
                handler._handle_kanban_delete()

            # 409 응답 검증
            self.assertEqual(handler.last_status, 409,
                             "파생 미완료 티켓 존재 시 409 여야 한다")
            body = handler.last_body
            self.assertFalse(body.get("ok"), "ok 가 False 여야 한다")
            self.assertEqual(body.get("error_kind"), "derived_blocked",
                             "error_kind 가 'derived_blocked' 여야 한다")

            # blocked_by 에 자식 티켓 정보 포함 검증
            blocked_by = body.get("blocked_by", [])
            self.assertTrue(len(blocked_by) > 0, "blocked_by 가 비어있지 않아야 한다")
            blocked_str = " ".join(blocked_by)
            self.assertIn(child_ticket, blocked_str,
                          f"blocked_by 에 {child_ticket} 이 포함되어야 한다")

    def test_delete_allowed_when_derived_ticket_done(self):
        """자식 티켓이 Done 상태이면 파생 가드를 통과하고 subprocess 를 호출한다."""
        parent_ticket = "T-998"
        child_ticket = "T-002"
        child_status = "Done"

        with tempfile.TemporaryDirectory() as tmpdir:
            tickets_dir = os.path.join(tmpdir, ".claude-organic", "tickets")
            for d in _KANBAN_ALL_DIRS:
                os.makedirs(os.path.join(tickets_dir, d), exist_ok=True)

            # done 디렉터리에 완료된 자식 티켓 배치
            child_xml_path = os.path.join(tickets_dir, "done", f"{child_ticket}.xml")
            child_xml = _make_ticket_xml(child_ticket, child_status, derived_from=parent_ticket)
            with open(child_xml_path, "w", encoding="utf-8") as f:
                f.write(child_xml)

            handler = _StubHandler(body={"ticket": parent_ticket})

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = f"{parent_ticket} deleted"
            mock_result.stderr = ""

            # sys.modules 직접 조작으로 worktree_manager ImportError 시뮬레이션
            sys.modules["flow.worktree_manager"] = None  # type: ignore[assignment]
            try:
                with patch("subprocess.run", return_value=mock_result) as mock_run, \
                     patch("os.getcwd", return_value=tmpdir):
                    handler._handle_kanban_delete()
            finally:
                sys.modules.pop("flow.worktree_manager", None)

            # 파생 가드 통과 후 subprocess 호출 검증
            self.assertTrue(mock_run.called, "Done 상태 자식만 있으면 subprocess 호출되어야 한다")
            self.assertEqual(handler.last_status, 200)


if __name__ == "__main__":
    unittest.main()
