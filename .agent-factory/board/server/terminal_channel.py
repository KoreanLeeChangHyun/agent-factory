"""Compatibility exports for terminal SSE channels."""

from __future__ import annotations

from board.server.channels.terminal_channel import (
    TerminalSSEChannel,
    _parse_last_event_id,
    _parse_last_event_id_from_query,
    _resolve_last_event_id,
)

__all__ = [
    "TerminalSSEChannel",
    "_parse_last_event_id",
    "_parse_last_event_id_from_query",
    "_resolve_last_event_id",
]
