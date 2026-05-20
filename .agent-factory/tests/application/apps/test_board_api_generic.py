"""Tests for generic board API app boundary."""

from __future__ import annotations

from board.server.handlers.generic import GenericHandlerMixin as CompatGenericHandlerMixin
from engine.apps.board_api.generic import GenericHandlerMixin


def test_generic_handler_compat_export_matches_app_boundary() -> None:
    assert CompatGenericHandlerMixin is GenericHandlerMixin


def test_generic_handler_exposes_expected_endpoint_methods() -> None:
    assert hasattr(GenericHandlerMixin, "_handle_api")
    assert hasattr(GenericHandlerMixin, "_handle_api_delete")
    assert hasattr(GenericHandlerMixin, "_handle_poll")
    assert hasattr(GenericHandlerMixin, "_handle_sse")
