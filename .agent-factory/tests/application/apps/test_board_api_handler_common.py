"""Tests for shared Board API handler helpers."""

from __future__ import annotations

from board.server.handlers import _handler_common as compat
from engine.apps.board_api import handler_common


def test_handler_common_compat_exports_match_app_boundary() -> None:
    assert compat._TICKET_RE is handler_common._TICKET_RE
    assert compat._KANBAN_ALL_DIRS is handler_common._KANBAN_ALL_DIRS
    assert compat._import_metrics_cli is handler_common._import_metrics_cli
    assert compat._import_launch_metrics_cli is handler_common._import_launch_metrics_cli


def test_ticket_regex_and_kanban_dirs() -> None:
    assert handler_common._TICKET_RE.match("T-424")
    assert not handler_common._TICKET_RE.match("X-424")
    assert "done" in handler_common._KANBAN_ALL_DIRS
