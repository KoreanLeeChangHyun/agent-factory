"""Compatibility exports for board workflow sessions."""

from __future__ import annotations

from board.server.sessions.workflow_session import (
    WorkflowSession,
    WorkflowSessionRegistry,
)

__all__ = ["WorkflowSession", "WorkflowSessionRegistry"]
