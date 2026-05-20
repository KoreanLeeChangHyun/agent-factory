"""Tests for Files board API app boundary."""

from __future__ import annotations

from board.server.handlers.files import FilesHandlerMixin as CompatFilesHandlerMixin
from engine.apps.board_api.files import FilesHandlerMixin


def test_files_handler_compat_export_matches_app_boundary() -> None:
    assert CompatFilesHandlerMixin is FilesHandlerMixin


def test_files_handler_exposes_expected_endpoint_methods() -> None:
    expected = [
        "_handle_memory_write",
        "_handle_memory_delete",
        "_handle_rules_write",
        "_handle_rules_delete",
        "_handle_prompt_write",
        "_handle_prompt_delete",
        "_handle_claude_md_write",
        "_handle_quick_prompt_write",
        "_handle_quick_prompt_delete",
    ]
    for method_name in expected:
        assert hasattr(FilesHandlerMixin, method_name)
