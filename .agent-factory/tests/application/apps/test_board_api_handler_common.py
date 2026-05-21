"""Tests for shared Board API handler helpers."""

from __future__ import annotations

from pathlib import Path

from board.server.handlers import _handler_common as compat
from engine.apps.board_api import handler_common


def test_handler_common_compat_exports_match_app_boundary() -> None:
    assert compat._WORK_REQUEST_RE is handler_common._WORK_REQUEST_RE
    assert compat._CONVEYOR_ALL_DIRS is handler_common._CONVEYOR_ALL_DIRS
    assert compat._import_metrics_cli is handler_common._import_metrics_cli
    assert compat._import_launch_metrics_cli is handler_common._import_launch_metrics_cli


def test_work_request_regex_and_conveyor_dirs() -> None:
    assert handler_common._WORK_REQUEST_RE.match("WR-424")
    assert not handler_common._WORK_REQUEST_RE.match("X-424")
    assert "complete" in handler_common._CONVEYOR_ALL_DIRS


def test_board_server_shim_adds_agent_factory_import_root() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    shim = repo_root / ".agent-factory" / "board" / "server.py"

    text = shim.read_text(encoding="utf-8")
    assert "_AGENT_FACTORY_DIR = os.path.dirname(_BOARD_DIR)" in text
    assert "sys.path.insert(0, _AGENT_FACTORY_DIR)" in text
