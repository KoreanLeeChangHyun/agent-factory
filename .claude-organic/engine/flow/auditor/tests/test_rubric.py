"""Tests for auditor/rubric.py — score mapping + 4-tier decision rules.

Required coverage (W03, plan.md line 96-99):

  (1) AT-06 verdict=FAIL              -> overall=FAIL, hard_gate_failed=["AT-06"]
  (2) AT-09 verdict=FAIL              -> overall=FAIL, hard_gate_failed=["AT-09"]
  (3) AT-04 verdict=FAIL but mean=4.0 -> overall=WARN, hard_gate_failed=[]
  (4) mean=3.9 (all PASS/WARN)        -> overall=PASS
  (5) command="research"              -> AT-12 excluded, mean recomputed cleanly

Plus auxiliary sanity tests for ``score_to_verdict`` and the
``INCONCLUSIVE`` edge case (all items have score=None).

No LLM calls, no external dependencies.  Pure unit tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add .claude-organic/engine to sys.path so `flow` package is importable.
_ENGINE_DIR = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from flow.auditor import AuditItemScore  # noqa: E402
from flow.auditor.rubric import (  # noqa: E402
    apply_decision_rules,
    score_to_verdict,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _item(at_id: str, score: int | None, verdict: str | None = None) -> AuditItemScore:
    """Build an AuditItemScore for tests.

    When ``verdict`` is omitted, derive it from ``score`` using the standard
    mapping (>=4 PASS / ==3 WARN / <=2 FAIL / None FAIL).
    """
    if verdict is None:
        verdict = score_to_verdict(score)
    return AuditItemScore(
        at_id=at_id,
        score=score,
        evidence=f"test evidence for {at_id}",
        verdict=verdict,  # type: ignore[arg-type]
    )


def _build_baseline_implement_items(
    overrides: dict[str, tuple[int | None, str | None]] | None = None,
) -> list[AuditItemScore]:
    """Build a baseline 12-item AT-01..AT-12 list at score=4 (all PASS).

    Args:
        overrides: Optional ``{at_id: (score, verdict)}`` map applied last.
    """
    items = [_item(f"AT-{i:02d}", 4) for i in range(1, 13)]
    if not overrides:
        return items
    new_items: list[AuditItemScore] = []
    for it in items:
        if it.at_id in overrides:
            score, verdict = overrides[it.at_id]
            new_items.append(_item(it.at_id, score, verdict))
        else:
            new_items.append(it)
    return new_items


# ---------------------------------------------------------------------------
# score_to_verdict — pure mapping
# ---------------------------------------------------------------------------


class TestScoreToVerdict:
    """Unit tests for ``score_to_verdict``."""

    @pytest.mark.parametrize("score, expected", [
        (5, "PASS"),
        (4, "PASS"),
        (3, "WARN"),
        (2, "FAIL"),
        (1, "FAIL"),
    ])
    def test_int_score_mapping(self, score: int, expected: str) -> None:
        """1-5 integer scores map to the rubric verdicts."""
        assert score_to_verdict(score) == expected

    def test_none_returns_fail(self) -> None:
        """None score returns conservative FAIL."""
        assert score_to_verdict(None) == "FAIL"

    @pytest.mark.parametrize("bad_score", [0, 6, -1, 100])
    def test_out_of_range_raises(self, bad_score: int) -> None:
        """Scores outside [1, 5] raise ValueError."""
        with pytest.raises(ValueError):
            score_to_verdict(bad_score)

    @pytest.mark.parametrize("bad_value", [3.5, "4", True])
    def test_non_int_raises(self, bad_value: object) -> None:
        """Non-int (and bool) values raise ValueError."""
        with pytest.raises(ValueError):
            score_to_verdict(bad_value)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# apply_decision_rules — 5 required cases + INCONCLUSIVE
# ---------------------------------------------------------------------------


class TestHardGate:
    """Step 2 of the 4-tier rule — AT-06/AT-09 hard gate."""

    def test_case_1_at06_fail_forces_overall_fail(self) -> None:
        """(1) AT-06 verdict=FAIL → overall=FAIL, hard_gate_failed=['AT-06'].

        All other items intentionally PASS (score=5) so that absent the gate,
        the average would be a clear PASS. The gate must override.
        """
        items = _build_baseline_implement_items(
            overrides={"AT-06": (1, "FAIL")}
        )
        # Every other item set to score=5 to make the no-gate path obviously PASS.
        items = [
            _item(it.at_id, 5) if it.at_id != "AT-06" else it for it in items
        ]

        overall, hard_gate_failed = apply_decision_rules(items, "implement")

        assert overall == "FAIL"
        assert hard_gate_failed == ["AT-06"]

    def test_case_2_at09_fail_forces_overall_fail(self) -> None:
        """(2) AT-09 verdict=FAIL → overall=FAIL, hard_gate_failed=['AT-09']."""
        items = _build_baseline_implement_items(
            overrides={"AT-09": (2, "FAIL")}
        )
        items = [
            _item(it.at_id, 5) if it.at_id != "AT-09" else it for it in items
        ]

        overall, hard_gate_failed = apply_decision_rules(items, "implement")

        assert overall == "FAIL"
        assert hard_gate_failed == ["AT-09"]

    def test_both_hard_gates_fail_lists_both_sorted(self) -> None:
        """Both AT-06 and AT-09 FAIL → list contains both sorted."""
        items = _build_baseline_implement_items(
            overrides={
                "AT-06": (1, "FAIL"),
                "AT-09": (2, "FAIL"),
            }
        )

        overall, hard_gate_failed = apply_decision_rules(items, "implement")

        assert overall == "FAIL"
        assert hard_gate_failed == ["AT-06", "AT-09"]


class TestCoreGate:
    """Step 4 of the 4-tier rule — AT-04 core gate caps PASS to WARN."""

    def test_case_3_at04_fail_with_high_average_caps_to_warn(self) -> None:
        """(3) AT-04 FAIL but mean ≈ 4.0 → overall=WARN, hard_gate_failed=[].

        Set AT-04 verdict=FAIL but score=4 so the arithmetic mean of the
        remaining 11 items (all 4) plus AT-04 (4) stays at 4.0.  Without
        the core gate this would yield PASS — the gate must cap to WARN.
        """
        items = _build_baseline_implement_items(
            overrides={"AT-04": (4, "FAIL")}
        )

        overall, hard_gate_failed = apply_decision_rules(items, "implement")

        assert overall == "WARN"
        assert hard_gate_failed == []

    def test_at04_fail_with_low_average_stays_fail_no_hard_gate(self) -> None:
        """AT-04 FAIL with low average BUT hard gates pinned PASS.

        Construct: AT-04 verdict=FAIL with score=2; AT-06/AT-09 pinned to
        score=4 (PASS) so the hard gate does NOT trip; remaining items
        score=1 to drive the average below 3.0.

        Expected: overall=FAIL by weighted average.  The core-gate cap is
        a no-op when the underlying average is already FAIL.
        ``hard_gate_failed=[]`` because AT-06/AT-09 pass.
        """
        items: list[AuditItemScore] = []
        for i in range(1, 13):
            at_id = f"AT-{i:02d}"
            if at_id in ("AT-06", "AT-09"):
                items.append(_item(at_id, 4))  # PASS - bypass hard gate
            elif at_id == "AT-04":
                items.append(_item(at_id, 2, "FAIL"))  # core gate fails
            else:
                items.append(_item(at_id, 1))  # FAIL by score

        overall, hard_gate_failed = apply_decision_rules(items, "implement")

        assert overall == "FAIL"
        assert hard_gate_failed == []


class TestWeightedAverage:
    """Step 3 of the 4-tier rule — uniform-weight average."""

    def test_case_4_mean_above_pass_threshold_returns_pass(self) -> None:
        """(4) mean=3.9 (all PASS/WARN, no gate) → overall=PASS.

        Construct 12 items whose arithmetic mean lands at 3.9.  Concretely:
        ten items at score=4 (PASS) and two items at score=3 (WARN) yields
        (10*4 + 2*3) / 12 = 46/12 = 3.833...

        That's < 3.8? No, 3.833 > 3.8 so PASS.  We need exactly 3.9.
        Use eleven 4s + one 3 = (44 + 3) / 12 = 47/12 ≈ 3.917 (PASS).

        Use a clean 3.9 by an alternative: 9 fives + 3 ones, mean = 48/12 = 4.0.
        Cleaner: simulate "all PASS or WARN, mean ≥ 3.8" by 11 PASS + 1 WARN:
        (11*4 + 1*3)/12 = 47/12 ≈ 3.917 → PASS.  Asserting >= 3.8 condition.
        """
        # 11 PASS items (score=4) + 1 WARN item (score=3) -> mean ~3.917.
        items = [_item(f"AT-{i:02d}", 4) for i in range(1, 13)]
        items[2] = _item("AT-03", 3)  # one WARN item

        overall, hard_gate_failed = apply_decision_rules(items, "implement")

        assert overall == "PASS"
        assert hard_gate_failed == []

    def test_mean_just_below_pass_threshold_returns_warn(self) -> None:
        """mean=3.7 (just below 3.8) → overall=WARN."""
        # 9 fours + 3 threes -> mean = (36+9)/12 = 3.75 -> WARN.
        items = [_item(f"AT-{i:02d}", 4) for i in range(1, 13)]
        for at_id in ("AT-01", "AT-02", "AT-03"):
            items = [_item(it.at_id, 3) if it.at_id == at_id else it for it in items]

        overall, hard_gate_failed = apply_decision_rules(items, "implement")

        assert overall == "WARN"
        assert hard_gate_failed == []

    def test_mean_below_warn_threshold_returns_fail(self) -> None:
        """mean<3.0 (and no hard gate) → overall=FAIL.

        Pin AT-06/AT-09 to score=3 so their verdict is WARN (not FAIL),
        bypassing the hard gate.  All other items score=2 (FAIL).
        Mean = (10*2 + 2*3) / 12 = 26/12 ≈ 2.17 → FAIL.
        """
        items: list[AuditItemScore] = []
        for i in range(1, 13):
            at_id = f"AT-{i:02d}"
            if at_id in ("AT-06", "AT-09"):
                items.append(_item(at_id, 3))  # WARN, no hard gate
            else:
                items.append(_item(at_id, 2))  # FAIL by score

        overall, hard_gate_failed = apply_decision_rules(items, "implement")

        assert overall == "FAIL"
        assert hard_gate_failed == []


class TestCommandFilter:
    """Step 1 of the 4-tier rule — AT-12 dropped for non-implement commands."""

    def test_case_5_research_command_excludes_at12(self) -> None:
        """(5) command='research' → AT-12 excluded, mean recomputed cleanly.

        AT-12 set to score=1 (FAIL).  All others at score=4 (PASS).

        - With AT-12 included (implement): mean = (11*4 + 1*1)/12 = 45/12 ≈ 3.75 -> WARN
        - With AT-12 excluded (research):  mean = 11*4 / 11 = 4.0 -> PASS
        """
        items = _build_baseline_implement_items(
            overrides={"AT-12": (1, "FAIL")}
        )

        # implement: AT-12 included, mean drops to ~3.75 -> WARN
        overall_impl, _ = apply_decision_rules(items, "implement")
        assert overall_impl == "WARN"

        # research: AT-12 dropped, mean = 4.0 -> PASS
        overall_research, hgf_research = apply_decision_rules(items, "research")
        assert overall_research == "PASS"
        assert hgf_research == []

    def test_at12_score_none_auto_excluded_regardless_of_command(self) -> None:
        """AT-12 with score=None is naturally excluded from the average."""
        # AT-12 score=None (skipped); 11 others all score=4.
        items = [_item(f"AT-{i:02d}", 4) for i in range(1, 12)]
        items.append(_item("AT-12", None, "PASS"))  # skipped: not applicable

        overall, _ = apply_decision_rules(items, "implement")

        # Mean = 11*4 / 11 = 4.0 -> PASS.
        assert overall == "PASS"

    def test_review_command_also_drops_at12(self) -> None:
        """command='review' drops AT-12 too."""
        items = _build_baseline_implement_items(
            overrides={"AT-12": (1, "FAIL")}
        )
        overall, _ = apply_decision_rules(items, "review")
        assert overall == "PASS"

    @pytest.mark.parametrize("cmd", ["implement", "refactor", "build"])
    def test_implement_like_commands_keep_at12(self, cmd: str) -> None:
        """implement/refactor/build all retain AT-12 in the average."""
        items = _build_baseline_implement_items(
            overrides={"AT-12": (1, "FAIL")}
        )
        overall, _ = apply_decision_rules(items, cmd)
        # AT-12 included -> mean ~3.75 -> WARN
        assert overall == "WARN"


class TestInconclusive:
    """Edge case — every applicable item has score=None."""

    def test_all_none_scores_returns_inconclusive(self) -> None:
        """All score=None items with non-FAIL verdicts → overall='INCONCLUSIVE'.

        Per W01 schema docstring, items intentionally skipped (LLM not
        called) carry verdict='PASS' with evidence='skipped: not applicable'
        — score is None but verdict is PASS, which keeps the hard gate
        idle.  All 12 items skipped this way → denominator zero →
        INCONCLUSIVE.
        """
        items = [_item(f"AT-{i:02d}", None, "PASS") for i in range(1, 13)]

        overall, hard_gate_failed = apply_decision_rules(items, "implement")

        assert overall == "INCONCLUSIVE"
        assert hard_gate_failed == []

    def test_inconclusive_does_not_trip_hard_gate(self) -> None:
        """Hard gate requires verdict=='FAIL'; score=None with verdict=FAIL still trips it."""
        # When the LLM call truly fails on a hard-gate item the verdict is FAIL
        # even though score is None.  The gate must still fire.
        items = _build_baseline_implement_items()
        items = [
            _item("AT-06", None, "FAIL") if it.at_id == "AT-06" else it
            for it in items
        ]

        overall, hard_gate_failed = apply_decision_rules(items, "implement")

        assert overall == "FAIL"
        assert hard_gate_failed == ["AT-06"]

    def test_empty_items_returns_inconclusive(self) -> None:
        """An empty input list yields INCONCLUSIVE."""
        overall, hard_gate_failed = apply_decision_rules([], "implement")
        assert overall == "INCONCLUSIVE"
        assert hard_gate_failed == []
