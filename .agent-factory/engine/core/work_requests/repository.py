"""Repository port for WorkRequest persistence."""

from __future__ import annotations

from typing import Protocol

from .domain import WorkRequest, WorkRequestRef


class WorkRequestStore(Protocol):
    """Persistence boundary for WorkRequest objects."""

    def get(self, ref: WorkRequestRef) -> WorkRequest:
        """Load one WorkRequest by stable reference."""

    def save(self, request: WorkRequest) -> None:
        """Persist one WorkRequest."""

