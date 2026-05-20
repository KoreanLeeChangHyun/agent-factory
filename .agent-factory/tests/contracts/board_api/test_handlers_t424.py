"""Current T-424 board handler regression coverage.

The original legacy test expected the removed ``workflow_undo`` handler. Current
runtime routes undo-done through ``KanbanHandlerMixin._handle_kanban_undo_done``.
"""

from __future__ import annotations

import re
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_board_http_request_handler_imports_current_mixins() -> None:
    from board.server.http_router import BoardHTTPRequestHandler

    required = [
        "_handle_kanban_move",
        "_handle_kanban_submit",
        "_handle_kanban_done",
        "_handle_kanban_delete",
        "_handle_kanban_undo_done",
        "_handle_metrics_run",
        "_handle_metrics_aggregate",
        "_handle_metrics_regression",
        "_handle_worktree_uncommitted_all",
        "_handle_worktree_commit",
        "_handle_memory_gc_run",
        "_handle_memory_gc_prune",
        "_handle_api",
        "_handle_poll",
        "_handle_sse",
        "_send_json_with_status",
    ]

    missing = [name for name in required if not hasattr(BoardHTTPRequestHandler, name)]
    assert missing == []


def test_kanban_done_regex_exports_match_done_and_undo_output() -> None:
    from board.server.handlers._handler_common import _KANBAN_ALL_DIRS, _TICKET_RE
    from board.server.handlers._kanban_done_re import (
        _DONE_CONFLICT_WARN_RE,
        _DONE_MERGE_OK_RE,
        _UNDO_ERROR_RE,
        _UNDO_WORKTREE_RE,
    )

    done_match = _DONE_MERGE_OK_RE.search("feat/T-424-branch -> develop 병합 완료 (ab12cd34)")
    assert done_match is not None
    assert done_match.group(1).strip() == "feat/T-424-branch"
    assert done_match.group(2).strip() == "ab12cd34"
    assert _DONE_CONFLICT_WARN_RE.search("[WARN] merge conflict detected in src/app.py")

    undo_match = _UNDO_WORKTREE_RE.search(
        "[undo-done] 워크트리 재생성 완료: path=/tmp/feat-T-424 branch=feat/T-424-test"
    )
    assert undo_match is not None
    assert undo_match.group(1) == "/tmp/feat-T-424"
    assert undo_match.group(2) == "feat/T-424-test"

    error_match = _UNDO_ERROR_RE.search("[undo-done] ERROR: T-424 is not in Done column")
    assert error_match is not None
    assert error_match.group(1).strip() == "T-424 is not in Done column"
    assert _TICKET_RE.match("T-424")
    assert "done" in _KANBAN_ALL_DIRS


def test_classify_done_failure_distinguishes_conflict_dirty_and_other() -> None:
    from board.server.handlers._kanban_done_re import _classify_done_failure

    assert _classify_done_failure("", "") == {
        "error_kind": "other",
        "conflicts": [],
        "dirty_files": [],
        "message": "",
    }

    conflict = _classify_done_failure("[ERROR] merge conflict in src/foo.py\n    - src/foo.py\n", "")
    assert conflict["error_kind"] == "merge_conflict"
    assert "src/foo.py" in conflict["conflicts"]

    dirty = _classify_done_failure("미커밋 파일 목록 :\n    - src/bar.py\n", "")
    assert dirty["error_kind"] == "dirty_worktree"
    assert "src/bar.py" in dirty["dirty_files"]


def test_done_transition_pattern_matches_only_target_ticket() -> None:
    ticket = "T-424"
    done_transition_re = re.compile(rf"^{re.escape(ticket)}:\s+\S+\s+->\s+Done\b|^{re.escape(ticket)}:\s+\S+\s+→\s+Done\b")

    assert any(done_transition_re.match(line) for line in "T-424: review → Done\n".splitlines())
    assert not any(done_transition_re.match(line) for line in "T-999: review → Done\n".splitlines())


def _make_done_handler():
    handler = MagicMock()
    handler._send_error = MagicMock()
    handler._send_json = MagicMock()
    handler._send_json_with_status = MagicMock()
    handler._get_dirty_files = MagicMock(return_value=[])
    return handler


def test_review_xml_missing_returns_400_for_done_review() -> None:
    from board.server.handlers._kanban_done_helpers import handle_kanban_done_review

    handler = _make_done_handler()
    with patch("board.server.handlers._kanban_done_helpers.os.path.isfile", return_value=False):
        handle_kanban_done_review(handler, "T-424", "/fake/root", "/fake/flow-kanban")

    handler._send_error.assert_called_once()
    assert handler._send_error.call_args.args[0] == 400
    assert "not in Review" in handler._send_error.call_args.args[1]


def test_review_xml_present_invokes_flow_kanban_done() -> None:
    from board.server.handlers._kanban_done_helpers import handle_kanban_done_review

    handler = _make_done_handler()
    result = subprocess.CompletedProcess(
        args=["flow-kanban", "done", "T-424"],
        returncode=0,
        stdout="feat/T-424-branch -> develop 병합 완료 (ab12cd34)\n",
        stderr="",
    )
    with patch("board.server.handlers._kanban_done_helpers.os.path.isfile", return_value=True), patch(
        "board.server.handlers._kanban_done_helpers.subprocess.run",
        return_value=result,
    ) as run:
        handle_kanban_done_review(handler, "T-424", "/fake/root", "/fake/flow-kanban")

    cmd = run.call_args.args[0]
    assert "done" in cmd
    assert "T-424" in cmd
    handler._send_json.assert_called_once()


class _UndoHandler:
    def __init__(self, body: dict | None = None) -> None:
        from board.server.handlers.kanban import KanbanHandlerMixin

        self._mixin = KanbanHandlerMixin
        self._body = body or {"ticket": "T-424", "force": False}
        self.errors: list[tuple[int, str]] = []
        self.responses: list[object] = []

    def _read_json_body(self) -> dict:
        return self._body

    def _send_error(self, code: int, msg: str) -> None:
        self.errors.append((code, msg))

    def _send_json(self, data: object) -> None:
        self.responses.append(data)

    def _send_json_with_status(self, status: int, data: object) -> None:
        self.responses.append((status, data))

    def run(self) -> None:
        self._mixin._handle_kanban_undo_done(self)


def test_kanban_undo_done_missing_done_xml_returns_400(tmp_path: Path) -> None:
    handler = _UndoHandler()

    with patch("os.getcwd", return_value=str(tmp_path)):
        handler.run()

    assert handler.errors
    assert handler.errors[0][0] == 400
    assert "not in Done" in handler.errors[0][1]


def test_kanban_undo_done_extracts_error_from_stderr(tmp_path: Path) -> None:
    done_dir = tmp_path / ".agent-factory" / "tickets" / "done"
    done_dir.mkdir(parents=True)
    (done_dir / "T-424.xml").write_text("<ticket />", encoding="utf-8")
    handler = _UndoHandler()
    result = subprocess.CompletedProcess(
        args=["flow-undo-done", "T-424"],
        returncode=1,
        stdout="",
        stderr="[undo-done] ERROR: develop branch diverged\n",
    )

    with patch("os.getcwd", return_value=str(tmp_path)), patch("subprocess.run", return_value=result):
        handler.run()

    assert handler.responses
    status, payload = handler.responses[0]
    assert status == 409
    assert payload["ok"] is False
    assert "develop branch diverged" in payload["error"]


def test_kanban_undo_done_parses_success_stdout(tmp_path: Path) -> None:
    done_dir = tmp_path / ".agent-factory" / "tickets" / "done"
    done_dir.mkdir(parents=True)
    (done_dir / "T-424.xml").write_text("<ticket />", encoding="utf-8")
    handler = _UndoHandler()
    result = subprocess.CompletedProcess(
        args=["flow-undo-done", "T-424"],
        returncode=0,
        stdout=(
            "[undo-done] 전략 1: reset --hard 진행\n"
            "[undo-done] 워크트리 재생성 완료: path=/tmp/wt branch=feat/T-424\n"
        ),
        stderr="",
    )

    with patch("os.getcwd", return_value=str(tmp_path)), patch("subprocess.run", return_value=result):
        handler.run()

    assert handler.responses
    payload = handler.responses[0]
    assert payload["ok"] is True
    assert payload["strategy"] == "reset"
    assert payload["worktree_path"] == "/tmp/wt"
    assert payload["branch"] == "feat/T-424"


def test_force_done_open_xml_missing_returns_400() -> None:
    from board.server.handlers._kanban_done_helpers import handle_kanban_done_force

    handler = _make_done_handler()
    with patch("board.server.handlers._kanban_done_helpers.os.path.isfile", return_value=False):
        handle_kanban_done_force(handler, "T-424", False, "/fake/root", "/fake/flow-kanban")

    handler._send_error.assert_called_once()
    assert handler._send_error.call_args.args[0] == 400
    assert "not in Open" in handler._send_error.call_args.args[1]


def test_force_done_dirty_guard_returns_409() -> None:
    from board.server.handlers._kanban_done_helpers import handle_kanban_done_force

    handler = _make_done_handler()
    handler._get_dirty_files = MagicMock(return_value=["src/foo.py"])
    worktree_manager = MagicMock()
    worktree_manager.get_worktree_path.return_value = "/fake/wt"
    worktree_manager.has_uncommitted_changes.return_value = True

    with patch("board.server.handlers._kanban_done_helpers.os.path.isfile", return_value=True), patch.dict(
        sys.modules,
        {"flow": types.SimpleNamespace(worktree_manager=worktree_manager)},
    ):
        handle_kanban_done_force(handler, "T-424", False, "/fake/root", "/fake/flow-kanban")

    handler._send_json_with_status.assert_called_once()
    status, payload = handler._send_json_with_status.call_args.args
    assert status == 409
    assert payload["error_kind"] == "dirty_worktree"
    assert payload["dirty_files"] == ["src/foo.py"]
