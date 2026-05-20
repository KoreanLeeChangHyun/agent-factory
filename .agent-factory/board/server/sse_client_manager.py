"""Compatibility exports for board SSE client management."""

from __future__ import annotations

from board.server.channels.sse_client_manager import (
    FileWatcher,
    GitBranchWatcher,
    SSEClientManager,
    _NDJSON_EVENT_MAP,
)

__all__ = [
    "FileWatcher",
    "GitBranchWatcher",
    "SSEClientManager",
    "_NDJSON_EVENT_MAP",
]
