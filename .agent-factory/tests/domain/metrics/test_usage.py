"""Core usage tracking coverage."""

from __future__ import annotations

import json

from engine.core.metrics.usage import usage_pending, usage_record


def test_usage_pending_and_record_write_usage_and_metrics(tmp_path) -> None:
    assert usage_pending(str(tmp_path), "W01", "T-1") == "usage-pending -> W01=T-1"

    result = usage_record(str(tmp_path), "orchestrator", 100, 20, 4, 10)

    assert result == "usage -> orchestrator: in=100 out=20 cc=4 cr=10"
    usage = json.loads((tmp_path / "usage.json").read_text(encoding="utf-8"))
    assert usage["_pending_workers"] == {"W01": "T-1"}
    assert usage["agents"]["orchestrator"]["input_tokens"] == 100

    metrics = (tmp_path / "metrics.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(metrics) == 1
    event = json.loads(metrics[0])
    assert event["event_type"] == "usage.snapshot"
    assert event["payload"]["effective_tokens"] == 206.0
