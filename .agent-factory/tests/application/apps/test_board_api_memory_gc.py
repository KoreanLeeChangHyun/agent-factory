"""Tests for Memory GC board API app boundary."""

from __future__ import annotations

from board.server.handlers.memory_gc import MemoryGcHandlerMixin as CompatMemoryGcHandlerMixin
from engine.apps.board_api.memory_gc import MemoryGcHandlerMixin


def test_memory_gc_handler_compat_export_matches_app_boundary() -> None:
    assert CompatMemoryGcHandlerMixin is MemoryGcHandlerMixin


def test_memory_gc_handler_exposes_expected_endpoint_methods() -> None:
    assert hasattr(MemoryGcHandlerMixin, "_handle_memory_gc_run")
    assert hasattr(MemoryGcHandlerMixin, "_handle_memory_gc_prune")
