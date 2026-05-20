"""Tests for CLI app entrypoints."""

from __future__ import annotations

from engine.apps.cli import flow_wf


def test_flow_wf_delegates_to_v2_driver(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_driver_main(argv: list[str] | None = None) -> int:
        calls.append(list(argv or []))
        return 17

    monkeypatch.setattr(flow_wf, "driver_main", fake_driver_main)

    assert flow_wf.main(["T-123", "--step", "PLAN"]) == 17
    assert calls == [["T-123", "--step", "PLAN"]]
