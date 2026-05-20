"""Tests for Settings board API app boundary."""

from __future__ import annotations

from board.server.handlers.settings import SettingsHandlerMixin as CompatSettingsHandlerMixin
from engine.apps.board_api.settings import SettingsHandlerMixin


def test_settings_handler_compat_export_matches_app_boundary() -> None:
    assert CompatSettingsHandlerMixin is SettingsHandlerMixin


def test_settings_handler_exposes_expected_endpoint_methods() -> None:
    assert hasattr(SettingsHandlerMixin, "_handle_settings_workflow_sync")
