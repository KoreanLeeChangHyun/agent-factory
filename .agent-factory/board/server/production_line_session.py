"""Compatibility exports for production-line board sessions."""

from __future__ import annotations

from board.server.sessions.production_line_session import (
    ProductionLineSession,
    ProductionLineSessionRegistry,
    is_fake_session_id,
)

__all__ = [
    "ProductionLineSession",
    "ProductionLineSessionRegistry",
    "is_fake_session_id",
]
