"""flow-metrics app boundary coverage."""

from __future__ import annotations

from pathlib import Path


def test_metrics_cli_imports_from_app_boundary() -> None:
    from engine.apps.cli import metrics_cli

    assert callable(metrics_cli.aggregate_run)
    assert "step.start" in metrics_cli.known_event_types()


def test_flow_metrics_wrapper_points_to_app_cli() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    wrapper = repo_root / ".agent-factory" / "bin" / "flow-metrics"

    assert "engine/apps/cli/metrics_cli.py" in wrapper.read_text(encoding="utf-8")
