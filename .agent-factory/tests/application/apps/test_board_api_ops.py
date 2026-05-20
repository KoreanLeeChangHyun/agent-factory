"""Tests for Ops board API app boundary."""

from __future__ import annotations

from board.server.handlers.ops_endpoints import OpsHandlerMixin as CompatOpsHandlerMixin
from engine.apps.board_api.ops_endpoints import OpsHandlerMixin


def test_ops_handler_compat_export_matches_app_boundary() -> None:
    assert CompatOpsHandlerMixin is OpsHandlerMixin


def test_ops_handler_exposes_expected_endpoint_methods() -> None:
    assert hasattr(OpsHandlerMixin, "_handle_ops_zombie_reap")
    assert hasattr(OpsHandlerMixin, "_handle_ops_debug_toggle")
    assert hasattr(OpsHandlerMixin, "_handle_ops_sse_status")
