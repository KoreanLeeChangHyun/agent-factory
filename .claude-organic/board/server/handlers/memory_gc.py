"""Memory GC POST handlers (run/prune-archive)."""

from __future__ import annotations

import os

from .._common import _memory_gc_run, _memory_gc_prune_archive, api_endpoint


class MemoryGcHandlerMixin:
    """Memory GC POST handlers (run/prune-archive)."""

    @api_endpoint("MGC", "run")
    def _handle_memory_gc_run(self) -> None:
        """POST /api/memory/gc/run — Memory GC 즉시 실행.

        method: POST
        url: /api/memory/gc/run
        domain: MGC
        handler: MemoryGcHandlerMixin._handle_memory_gc_run
        request: body {dry_run?: bool, with_reflection?: bool}
        response_ok: {ok: true, removed: int, archived: int, ...}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 500
        auth: none (local-only)
        side_effects: rewrite MEMORY.md AUTO_INDEX area + archive stale memories
        sse_events: memory_update (via FileWatcher)
        """
        data = self._read_json_body() or {}
        dry_run = bool(data.get('dry_run', False))
        with_reflection = bool(data.get('with_reflection', False))
        result = _memory_gc_run(
            os.getcwd(), dry_run=dry_run, with_reflection=with_reflection,
        )
        self._send_json(result)

    @api_endpoint("MGC", "prune_archive")
    def _handle_memory_gc_prune(self) -> None:
        """POST /api/memory/gc/prune-archive — archive 디렉터리 정리.

        method: POST
        url: /api/memory/gc/prune-archive
        domain: MGC
        handler: MemoryGcHandlerMixin._handle_memory_gc_prune
        request: body {apply?: bool}
        response_ok: {ok: true, pruned: int, kept: int}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 500
        auth: none (local-only)
        side_effects: remove memory archive files (irreversible when apply=true)
        sse_events: memory_update (via FileWatcher)
        """
        data = self._read_json_body() or {}
        apply = bool(data.get('apply', False))
        result = _memory_gc_prune_archive(os.getcwd(), apply=apply)
        self._send_json(result)
