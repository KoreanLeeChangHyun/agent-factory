"""Tests for Production Line Workflow board API app boundary."""

from __future__ import annotations

from board.server.handlers.production_line_workflow import (
    _SESSION_PATH_RE as COMPAT_SESSION_PATH_RE,
    ProductionLineWorkflowHandlerMixin as CompatProductionLineWorkflowHandlerMixin,
)
from engine.apps.board_api.production_line_workflow import _SESSION_PATH_RE, ProductionLineWorkflowHandlerMixin


def test_production_line_workflow_handler_compat_export_matches_app_boundary() -> None:
    assert CompatProductionLineWorkflowHandlerMixin is ProductionLineWorkflowHandlerMixin
    assert COMPAT_SESSION_PATH_RE is _SESSION_PATH_RE


def test_production_line_workflow_handler_exposes_dispatch_methods() -> None:
    assert hasattr(ProductionLineWorkflowHandlerMixin, "_production_line_dispatch_get")
    assert hasattr(ProductionLineWorkflowHandlerMixin, "_production_line_dispatch_post")
    assert hasattr(ProductionLineWorkflowHandlerMixin, "_production_line_dispatch_delete")
    assert hasattr(ProductionLineWorkflowHandlerMixin, "_production_line_dispatch_patch")


def test_production_line_session_path_regex_matches_session_subpath() -> None:
    match = _SESSION_PATH_RE.match("/api/v2/sessions/session-1/history")
    assert match is not None
    assert match.group("session_id") == "session-1"
    assert match.group("sub") == "history"
