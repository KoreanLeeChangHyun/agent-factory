"""PollChangeTracker — diff-only polling state."""

from __future__ import annotations

import threading


class PollChangeTracker:
    """Change event accumulator for polling clients.

    After the last polling, the filename will be accumulated by dict.
    returns and initializes accumulated changes when calling flush().

    Attributes:
        changes: Event type -> Change filename set map
        lock: Lock for thread-safe access
    """

    def __init__(self) -> None:
        """Add to cart"""
        self._changes: dict[str, set[str]] = {}
        self._lock: threading.Lock = threading.Lock()

    def add(self, event_type: str, files: list[str]) -> None:
        """Add a change event type and filename list.

        Args:
            event type: event type(kanban, workflow, dashboard)
            files: List of changed filenames
        """
        with self._lock:
            if event_type not in self._changes:
                self._changes[event_type] = set()
            self._changes[event_type].update(files)

    def flush(self) -> dict[str, list[str]]:
        """Returns and resets accumulated changes events.

        Returns:
            Change filename list by event type dict.
            Example: {"kanban": ["T-038.xml"], "workflow": ["state.json"]}
            empty dict without changing.
        """
        with self._lock:
            result = {k: list(v) for k, v in self._changes.items()}
            self._changes.clear()
            return result
