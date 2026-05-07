"""Memory GC POST handlers (run/prune-archive)."""

from __future__ import annotations

import os

from .._common import _memory_gc_run, _memory_gc_prune_archive


class MemoryGcHandlerMixin:
    """Memory GC POST handlers (run/prune-archive)."""

    def _handle_memory_gc_run(self) -> None:
        """POST /api/memory/gc/run — body {"dry_run": bool, "with_reflection": bool}"""
        data = self._read_json_body() or {}
        dry_run = bool(data.get('dry_run', False))
        with_reflection = bool(data.get('with_reflection', False))
        result = _memory_gc_run(
            os.getcwd(), dry_run=dry_run, with_reflection=with_reflection,
        )
        self._send_json(result)

    def _handle_memory_gc_prune(self) -> None:
        """POST /api/memory/gc/prune-archive — body {"apply": bool}"""
        data = self._read_json_body() or {}
        apply = bool(data.get('apply', False))
        result = _memory_gc_prune_archive(os.getcwd(), apply=apply)
        self._send_json(result)
