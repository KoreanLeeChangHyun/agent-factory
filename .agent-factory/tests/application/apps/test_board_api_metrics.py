"""Tests for Metrics board API app boundary."""

from __future__ import annotations

from board.server.handlers.metrics import MetricsHandlerMixin as CompatMetricsHandlerMixin
from engine.apps.board_api.metrics import MetricsHandlerMixin


def test_metrics_handler_compat_export_matches_app_boundary() -> None:
    assert CompatMetricsHandlerMixin is MetricsHandlerMixin


def test_metrics_handler_exposes_expected_endpoint_methods() -> None:
    assert hasattr(MetricsHandlerMixin, "_handle_metrics_run")
    assert hasattr(MetricsHandlerMixin, "_handle_metrics_aggregate")
    assert hasattr(MetricsHandlerMixin, "_handle_metrics_regression")
    assert hasattr(MetricsHandlerMixin, "_handle_metrics_launch_latency")


def test_parse_metrics_last_handles_invalid_values() -> None:
    assert MetricsHandlerMixin._parse_metrics_last({}, 20) == 20
    assert MetricsHandlerMixin._parse_metrics_last({"last": ["7"]}, 20) == 7
    assert MetricsHandlerMixin._parse_metrics_last({"last": ["0"]}, 20) == 20
    assert MetricsHandlerMixin._parse_metrics_last({"last": ["bad"]}, 20) == 20
