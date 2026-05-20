"""Tests for Sync board API app boundary."""

from __future__ import annotations

from board.server.handlers.sync import SyncHandlerMixin as CompatSyncHandlerMixin
from engine.apps.board_api.sync import SyncHandlerMixin


def test_sync_handler_compat_export_matches_app_boundary() -> None:
    assert CompatSyncHandlerMixin is SyncHandlerMixin


def test_sync_handler_exposes_expected_endpoint_methods() -> None:
    assert hasattr(SyncHandlerMixin, "_handle_debug_log")
    assert hasattr(SyncHandlerMixin, "_handle_restart")
