"""Core metrics event helper coverage."""

from __future__ import annotations

import json

from engine.core.metrics import append_event, known_event_types, metrics_path, schema_for


def test_core_metrics_exports_event_schema_and_writer(tmp_path) -> None:
    assert "step.start" in known_event_types()
    assert schema_for("step.start") == ["step", "source"]

    append_event(tmp_path, "step.start", {"step": "PLAN", "source": "test"})

    lines = metrics_path(tmp_path).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event_type"] == "step.start"
    assert record["payload"] == {"step": "PLAN", "source": "test"}
