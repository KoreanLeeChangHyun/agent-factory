"""Current WR-424 board handler regression coverage.

The original legacy test expected the removed ``workflow_undo`` handler. Current
runtime routes undo-complete through ``ConveyorHandlerMixin._handle_conveyor_undo_complete``.
"""

from __future__ import annotations

import re
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_board_http_request_handler_imports_current_mixins() -> None:
    from board.server.routing.http_router import BoardHTTPRequestHandler

    required = [
        "_handle_conveyor_move",
        "_handle_conveyor_submit",
        "_handle_conveyor_complete",
        "_handle_conveyor_delete",
        "_handle_conveyor_undo_complete",
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


def test_conveyor_complete_regex_exports_match_complete_and_undo_output() -> None:
    from board.server.handlers._handler_common import _CONVEYOR_ALL_DIRS, _WORK_REQUEST_RE
    from board.server.handlers._conveyor_complete_re import (
        _COMPLETE_CONFLICT_WARN_RE,
        _COMPLETE_MERGE_OK_RE,
        _UNDO_ERROR_RE,
        _UNDO_WORKTREE_RE,
    )

    complete_match = _COMPLETE_MERGE_OK_RE.search("feat/WR-424-branch -> Development completion (ab12cd34)")
    assert complete_match is not None
    assert complete_match.group(1).strip() == "feat/WR-424-branch"
    assert complete_match.group(2).strip() == "ab12cd34"
    assert _COMPLETE_CONFLICT_WARN_RE.search("[WARN] merge conflict detected in src/app.py")

    undo_match = _UNDO_WORKTREE_RE.search(
        "[undo-complete] Worktree Regeneration: path=/tmp/feat-WR-424 branch=feat/WR-424-test"
    )
    assert undo_match is not None
    assert undo_match.group(1) == "/tmp/feat-WR-424"
    assert undo_match.group(2) == "feat/WR-424-test"

    error_match = _UNDO_ERROR_RE.search("[undo-complete] ERROR: WR-424 is not in Complete column")
    assert error_match is not None
    assert error_match.group(1).strip() == "WR-424 is not in Complete column"
    assert _WORK_REQUEST_RE.match("WR-424")
    assert "complete" in _CONVEYOR_ALL_DIRS


def test_classify_complete_failure_distinguishes_conflict_dirty_and_other() -> None:
    from board.server.handlers._conveyor_complete_re import _classify_complete_failure

    assert _classify_complete_failure("", "") == {
        "error_kind": "other",
        "conflicts": [],
        "dirty_files": [],
        "message": "",
    }

    conflict = _classify_complete_failure("[ERROR] merge conflict in src/foo.py\n    - src/foo.py\n", "")
    assert conflict["error_kind"] == "merge_conflict"
    assert "src/foo.py" in conflict["conflicts"]

    dirty = _classify_complete_failure("src/bar.py\\n", "")
    assert dirty["error_kind"] == "dirty_worktree"
    assert "src/bar.py" in dirty["dirty_files"]


def test_complete_transition_pattern_matches_only_target_work_request() -> None:
    work_request = "WR-424"
    complete_transition_re = re.compile(rf"^{re.escape(work_request)}:\s+\S+\s+->\s+Complete\b|^{re.escape(work_request)}:\s+\S+\s+→\s+Complete\b")

    assert any(complete_transition_re.match(line) for line in "WR-424: verifying → Complete\n".splitlines())
    assert not any(complete_transition_re.match(line) for line in "WR-999: verifying → Complete\n".splitlines())


def _make_complete_handler():
    handler = MagicMock()
    handler._send_error = MagicMock()
    handler._send_json = MagicMock()
    handler._send_json_with_status = MagicMock()
    handler._get_dirty_files = MagicMock(return_value=[])
    return handler


def test_verifying_xml_missing_returns_400_for_complete_verifying() -> None:
    from engine.apps.board_api.conveyor_complete_helpers import handle_conveyor_complete_review

    handler = _make_complete_handler()
    with patch("engine.apps.board_api.conveyor_complete_helpers.os.path.isfile", return_value=False):
        handle_conveyor_complete_review(handler, "WR-424", "/fake/root", "/fake/flow-conveyor")

    handler._send_error.assert_called_once()
    assert handler._send_error.call_args.args[0] == 400
    assert "not in Verifying" in handler._send_error.call_args.args[1]


def test_verifying_xml_present_invokes_flow_conveyor_complete() -> None:
    from engine.apps.board_api.conveyor_complete_helpers import handle_conveyor_complete_review

    handler = _make_complete_handler()
    result = subprocess.CompletedProcess(
        args=["flow-conveyor", "complete", "WR-424"],
        returncode=0,
        stdout="feat/WR-424-branch -> Development completion (ab12cd34)\\n",
        stderr="",
    )
    with patch("engine.apps.board_api.conveyor_complete_helpers.os.path.isfile", return_value=True), patch(
        "engine.apps.board_api.conveyor_complete_helpers.subprocess.run",
        return_value=result,
    ) as run:
        handle_conveyor_complete_review(handler, "WR-424", "/fake/root", "/fake/flow-conveyor")

    cmd = run.call_args.args[0]
    assert "complete" in cmd
    assert "WR-424" in cmd
    handler._send_json.assert_called_once()


class _UndoHandler:
    def __init__(self, body: dict | None = None) -> None:
        from board.server.handlers.conveyor import ConveyorHandlerMixin

        self._mixin = ConveyorHandlerMixin
        self._body = body or {"work_request": "WR-424", "force": False}
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
        self._mixin._handle_conveyor_undo_complete(self)


def test_conveyor_undo_complete_missing_complete_xml_returns_400(tmp_path: Path) -> None:
    handler = _UndoHandler()

    with patch("os.getcwd", return_value=str(tmp_path)):
        handler.run()

    assert handler.errors
    assert handler.errors[0][0] == 400
    assert "not in Complete" in handler.errors[0][1]


def test_conveyor_undo_complete_extracts_error_from_stderr(tmp_path: Path) -> None:
    complete_dir = tmp_path / ".agent-factory" / "work-requests" / "complete"
    complete_dir.mkdir(parents=True)
    (complete_dir / "WR-424.xml").write_text("<work_request />", encoding="utf-8")
    handler = _UndoHandler()
    result = subprocess.CompletedProcess(
        args=["flow-undo-complete", "WR-424"],
        returncode=1,
        stdout="",
        stderr="[undo-complete] ERROR: develop branch diverged\n",
    )

    with patch("os.getcwd", return_value=str(tmp_path)), patch("subprocess.run", return_value=result):
        handler.run()

    assert handler.responses
    status, payload = handler.responses[0]
    assert status == 409
    assert payload["ok"] is False
    assert "develop branch diverged" in payload["error"]


def test_conveyor_undo_complete_parses_success_stdout(tmp_path: Path) -> None:
    complete_dir = tmp_path / ".agent-factory" / "work-requests" / "complete"
    complete_dir.mkdir(parents=True)
    (complete_dir / "WR-424.xml").write_text("<work_request />", encoding="utf-8")
    handler = _UndoHandler()
    result = subprocess.CompletedProcess(
        args=["flow-undo-complete", "WR-424"],
        returncode=0,
        stdout=(
            "[undo-complete] Strategy 1: reset --hard progress\n"
            "[undo-complete] Worktree Regeneration: path=/tmp/wt branch=feat/WR-424\n"
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
    assert payload["branch"] == "feat/WR-424"


def test_force_complete_accepted_xml_missing_returns_400() -> None:
    from engine.apps.board_api.conveyor_complete_helpers import handle_conveyor_complete_force

    handler = _make_complete_handler()
    with patch("engine.apps.board_api.conveyor_complete_helpers.os.path.isfile", return_value=False):
        handle_conveyor_complete_force(handler, "WR-424", False, "/fake/root", "/fake/flow-conveyor")

    handler._send_error.assert_called_once()
    assert handler._send_error.call_args.args[0] == 400
    assert "not in Accepted" in handler._send_error.call_args.args[1]


def test_force_complete_dirty_guard_returns_409() -> None:
    from engine.apps.board_api.conveyor_complete_helpers import handle_conveyor_complete_force

    handler = _make_complete_handler()
    handler._get_dirty_files = MagicMock(return_value=["src/foo.py"])
    worktree_manager = MagicMock()
    worktree_manager.get_worktree_path.return_value = "/fake/wt"
    worktree_manager.has_uncommitted_changes.return_value = True

    with patch("engine.apps.board_api.conveyor_complete_helpers.os.path.isfile", return_value=True), patch.dict(
        sys.modules,
        {"flow": types.SimpleNamespace(worktree_manager=worktree_manager)},
    ):
        handle_conveyor_complete_force(handler, "WR-424", False, "/fake/root", "/fake/flow-conveyor")

    handler._send_json_with_status.assert_called_once()
    status, payload = handler._send_json_with_status.call_args.args
    assert status == 409
    assert payload["error_kind"] == "dirty_worktree"
    assert payload["dirty_files"] == ["src/foo.py"]
