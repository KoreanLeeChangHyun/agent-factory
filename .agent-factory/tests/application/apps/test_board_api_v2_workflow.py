"""Tests for V2 Workflow board API app boundary."""

from __future__ import annotations

from board.server.handlers.v2_workflow import (
    _SESSION_PATH_RE as COMPAT_SESSION_PATH_RE,
    V2WorkflowHandlerMixin as CompatV2WorkflowHandlerMixin,
)
from engine.apps.board_api.production_line_workflow import _SESSION_PATH_RE, V2WorkflowHandlerMixin


def test_v2_workflow_handler_compat_export_matches_app_boundary() -> None:
    assert CompatV2WorkflowHandlerMixin is V2WorkflowHandlerMixin
    assert COMPAT_SESSION_PATH_RE is _SESSION_PATH_RE


def test_v2_workflow_handler_exposes_dispatch_methods() -> None:
    assert hasattr(V2WorkflowHandlerMixin, "_v2_dispatch_get")
    assert hasattr(V2WorkflowHandlerMixin, "_v2_dispatch_post")
    assert hasattr(V2WorkflowHandlerMixin, "_v2_dispatch_delete")
    assert hasattr(V2WorkflowHandlerMixin, "_v2_dispatch_patch")


def test_v2_session_path_regex_matches_session_subpath() -> None:
    match = _SESSION_PATH_RE.match("/api/v2/sessions/session-1/history")
    assert match is not None
    assert match.group("session_id") == "session-1"
    assert match.group("sub") == "history"
