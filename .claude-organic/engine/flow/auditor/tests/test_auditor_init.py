"""Tests for auditor/__init__.py — schema dataclass round-trip.

Verifies that AuditItemScore and AuditVerdict can be serialised to JSON
and deserialised back to equal dataclass instances (json.dumps → json.loads
→ equality).  No LLM calls or external dependencies required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add .claude-organic/engine to sys.path so `flow` package is importable.
_ENGINE_DIR = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from flow.auditor import AuditItemScore, AuditVerdict


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_item(at_id: str = "AT-01", score: int = 4) -> AuditItemScore:
    """Return a minimal AuditItemScore for testing."""
    return AuditItemScore(
        at_id=at_id,
        score=score,
        evidence="Sample evidence text.",
        verdict="PASS" if score >= 4 else ("WARN" if score == 3 else "FAIL"),
    )


def _make_verdict(items: list[AuditItemScore] | None = None) -> AuditVerdict:
    """Return a minimal AuditVerdict for testing."""
    if items is None:
        items = [_make_item("AT-01", 4), _make_item("AT-02", 3)]
    return AuditVerdict(
        tier=2,
        items=items,
        hard_gate_failed=[],
        overall="WARN",
        model="claude-sonnet-4-5",
        tokens_in=1000,
        tokens_out=200,
        cost_usd=0.0018,
        duration_ms=5400,
        generated_at="2026-05-10T19:11:07+09:00",
    )


# ---------------------------------------------------------------------------
# AuditItemScore round-trip
# ---------------------------------------------------------------------------


class TestAuditItemScoreRoundTrip:
    """Round-trip serialisation tests for AuditItemScore."""

    def test_pass_item_round_trip(self) -> None:
        """PASS item: json.dumps → json.loads → dataclass equality."""
        original = _make_item("AT-01", 5)

        serialised = json.dumps(original.to_dict(), ensure_ascii=False)
        restored = AuditItemScore.from_dict(json.loads(serialised))

        assert restored == original

    def test_warn_item_round_trip(self) -> None:
        """WARN item (score=3): round-trip preserves score and verdict."""
        original = AuditItemScore(
            at_id="AT-04",
            score=3,
            evidence="Criteria partially defined.",
            verdict="WARN",
        )

        serialised = json.dumps(original.to_dict(), ensure_ascii=False)
        restored = AuditItemScore.from_dict(json.loads(serialised))

        assert restored == original
        assert restored.verdict == "WARN"
        assert restored.score == 3

    def test_fail_item_round_trip(self) -> None:
        """FAIL item (score=2): round-trip preserves score and verdict."""
        original = AuditItemScore(
            at_id="AT-06",
            score=2,
            evidence="No clear success criteria found.",
            verdict="FAIL",
        )

        serialised = json.dumps(original.to_dict(), ensure_ascii=False)
        restored = AuditItemScore.from_dict(json.loads(serialised))

        assert restored == original
        assert restored.verdict == "FAIL"

    def test_none_score_item_round_trip(self) -> None:
        """Item with score=None (LLM call failed): round-trip preserves None."""
        original = AuditItemScore(
            at_id="AT-09",
            score=None,
            evidence="skipped: LLM call failed",
            verdict="FAIL",
        )

        serialised = json.dumps(original.to_dict(), ensure_ascii=False)
        restored = AuditItemScore.from_dict(json.loads(serialised))

        assert restored == original
        assert restored.score is None


# ---------------------------------------------------------------------------
# AuditVerdict round-trip
# ---------------------------------------------------------------------------


class TestAuditVerdictRoundTrip:
    """Round-trip serialisation tests for AuditVerdict."""

    def test_full_verdict_round_trip(self) -> None:
        """Full AuditVerdict: json.dumps → json.loads → equality."""
        original = _make_verdict()

        serialised = original.to_json()
        restored = AuditVerdict.from_json(serialised)

        assert restored == original

    def test_verdict_items_restored_as_dataclass(self) -> None:
        """Nested items must be AuditItemScore instances after deserialisation."""
        original = _make_verdict()

        restored = AuditVerdict.from_json(original.to_json())

        assert all(isinstance(item, AuditItemScore) for item in restored.items)

    def test_hard_gate_failed_preserved(self) -> None:
        """hard_gate_failed list is preserved through round-trip."""
        items = [_make_item("AT-06", 1)]
        original = AuditVerdict(
            tier=2,
            items=items,
            hard_gate_failed=["AT-06"],
            overall="FAIL",
            model="claude-sonnet-4-5",
            tokens_in=800,
            tokens_out=150,
            cost_usd=0.0012,
            duration_ms=3200,
            generated_at="2026-05-10T20:00:00+09:00",
        )

        restored = AuditVerdict.from_json(original.to_json())

        assert restored.hard_gate_failed == ["AT-06"]
        assert restored.overall == "FAIL"

    def test_verdict_to_dict_is_json_serialisable(self) -> None:
        """to_dict() output must be directly JSON-serialisable (no custom types)."""
        original = _make_verdict()
        d = original.to_dict()

        # Must not raise
        json_str = json.dumps(d)
        parsed = json.loads(json_str)

        assert parsed["tier"] == 2
        assert len(parsed["items"]) == len(original.items)
        assert parsed["cost_usd"] == pytest.approx(original.cost_usd, rel=1e-6)

    def test_empty_items_verdict_round_trip(self) -> None:
        """AuditVerdict with empty items list: INCONCLUSIVE overall round-trip."""
        original = AuditVerdict(
            tier=2,
            items=[],
            hard_gate_failed=[],
            overall="INCONCLUSIVE",
            model="claude-sonnet-4-5",
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            duration_ms=0,
            generated_at="2026-05-10T21:00:00+09:00",
        )

        restored = AuditVerdict.from_json(original.to_json())

        assert restored == original
        assert restored.overall == "INCONCLUSIVE"
        assert restored.items == []
