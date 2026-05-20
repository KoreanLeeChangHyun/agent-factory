"""Auditor T3 — Rubric scoring engine + 4-tier decision rules.

This module aggregates per-item ``AuditItemScore`` records into a single
``overall`` verdict using the T-406 §8 4-tier decision rule.  It is a pure
function module — no side effects, no LLM calls, no I/O.

T-411 abolition canon (2026-05-08, commit 0c970fa)
---------------------------------------------------
This module is **advisory only**.  Zero forced transitions, zero auto-revert,
zero auto-block.  No function in this file mutates kanban state, triggers
workflow phase transitions, blocks merges, or wraps a guard around any
finalization step.  The output ``overall`` string is purely informational —
how it is rendered (Board badge, log line, etc.) is the caller's concern.

Decision-rule order
-------------------------------------
1. **Command filter** — When ``command`` is not one of
   ``{"implement", "refactor", "build"}``, the AT-12 (Migration regression
   safety) item is removed from consideration before any other rule runs.
   AT-12 with ``score=None`` is automatically excluded from the weighted
   average regardless of command.

2. **Hard gate** — If AT-06 (goal-context purpose alignment) or AT-09
   (criteria measurability) has ``verdict == "FAIL"``, the overall verdict
   is forced to ``"FAIL"`` and ``hard_gate_failed`` records the offending
   ``at_id`` values.  Average is not computed in this case.

3. **Core gate** — If AT-04 (success criteria definition) has
   ``verdict == "FAIL"`` (and no hard gate triggered), the overall verdict
   is capped at ``"WARN"``.  PASS is blocked; if the underlying average
   already yields WARN or FAIL the cap is a no-op.

4. **Weighted average** — When neither hard gate nor (a PASS-blocking) core
   gate is triggered, items with ``score is None`` are excluded and the
   arithmetic mean of the remaining scores is computed (uniform weights).
   Mapping: ``mean >= 3.8`` → ``"PASS"``; ``3.0 <= mean < 3.8`` → ``"WARN"``;
   ``mean < 3.0`` → ``"FAIL"``.

5. **Inconclusive** — If after filtering all remaining items have
   ``score is None`` (denominator zero), overall = ``"INCONCLUSIVE"``.

Public API
----------
- :func:`score_to_verdict` — map an integer 1–5 score to a verdict label.
- :func:`apply_decision_rules` — aggregate per-item scores into ``overall``
  and ``hard_gate_failed``.

Reference
---------

  lines 234–253.


"""

from __future__ import annotations

from typing import Iterable

from . import AuditItemScore


# ---------------------------------------------------------------------------
# Constants — gate identifiers and command filter set
# ---------------------------------------------------------------------------

#: AT-NN identifiers whose FAIL verdict triggers an immediate overall=FAIL.
#: Sourced from prompt template headers (``gate_type: hard``).
HARD_GATE_IDS: frozenset[str] = frozenset({"AT-06", "AT-09"})

#: AT-NN identifier whose FAIL verdict caps overall at WARN (PASS blocked).
#: Sourced from prompt template header (``gate_type: core``).
CORE_GATE_ID: str = "AT-04"

#: AT-NN identifier that applies only to implement/refactor/build commands.
#: Sourced from prompt template header
#: (``applicable_commands: [implement, refactor, build]``).
IMPLEMENT_ONLY_AT_ID: str = "AT-12"

#: Command set for which AT-12 evaluation is applicable.
IMPLEMENT_LIKE_COMMANDS: frozenset[str] = frozenset(
    {"implement", "refactor", "build"}
)

#: Weighted-average thresholds (inclusive lower bound).
PASS_THRESHOLD: float = 3.8
WARN_THRESHOLD: float = 3.0


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def score_to_verdict(score: int | None) -> str:
    """Map a 1-5 integer score to a verdict label.

    Per the T-406 §8 rubric:

    +-----------+-----------+
    | Score     | Verdict   |
    +===========+===========+
    | 4 or 5    | ``PASS``  |
    +-----------+-----------+
    | 3         | ``WARN``  |
    +-----------+-----------+
    | 1 or 2    | ``FAIL``  |
    +-----------+-----------+

    Args:
        score: Integer 1-5 from the LLM judge, or ``None`` when the LLM
            call failed/was skipped.

    Returns:
        One of ``"PASS"``, ``"WARN"``, ``"FAIL"``.  ``None`` input yields
        ``"FAIL"`` so callers that bypass explicit ``None`` handling still
        produce a conservative verdict.

    Raises:
        ValueError: When ``score`` is an integer outside 1-5, or when its
            type is not ``int`` or ``None``.
    """
    if score is None:
        return "FAIL"
    if not isinstance(score, int) or isinstance(score, bool):
        raise ValueError(
            f"score must be int (1-5) or None, got {type(score).__name__}"
        )
    if score < 1 or score > 5:
        raise ValueError(f"score must be in [1, 5], got {score}")
    if score >= 4:
        return "PASS"
    if score == 3:
        return "WARN"
    return "FAIL"


def apply_decision_rules(
    items: Iterable[AuditItemScore],
    command: str,
) -> tuple[str, list[str]]:
    """Aggregate per-item scores into an overall verdict and hard-gate list.

    Applies the T-406 §8 4-tier decision rule (see module docstring for
    the full ordering and thresholds).

    Args:
        items: Iterable of ``AuditItemScore`` records.  Order is preserved
            for the ``hard_gate_failed`` output, but the final list is sorted
            for deterministic round-trip.
        command: Workflow command name (e.g. ``"implement"``,
            ``"research"``, ``"review"``, ``"refactor"``, ``"build"``).
            Determines whether AT-12 participates in the average.

    Returns:
        2-tuple ``(overall, hard_gate_failed)`` where:

        - ``overall`` is one of ``"PASS"``, ``"WARN"``, ``"FAIL"``,
          ``"INCONCLUSIVE"``.
        - ``hard_gate_failed`` is a list of ``at_id`` strings (AT-06 / AT-09)
          whose verdict is ``"FAIL"``.  Empty when no hard gate fires.
    """
    # Materialise once - caller may pass a generator.
    item_list = list(items)

    # Step 1: Command filter - drop AT-12 when command is not implement-like.
    if command not in IMPLEMENT_LIKE_COMMANDS:
        item_list = [
            it for it in item_list if it.at_id != IMPLEMENT_ONLY_AT_ID
        ]

    # Step 2: Hard gate - AT-06 or AT-09 verdict==FAIL -> immediate FAIL.
    hard_gate_failed: list[str] = [
        it.at_id
        for it in item_list
        if it.at_id in HARD_GATE_IDS and it.verdict == "FAIL"
    ]
    if hard_gate_failed:
        # Stable order regardless of input order.
        hard_gate_failed = sorted(hard_gate_failed)
        return "FAIL", hard_gate_failed

    # Step 3: Weighted average - exclude score=None items.
    scored = [it.score for it in item_list if it.score is not None]
    if not scored:
        # All items skipped or failed at LLM-call layer.
        return "INCONCLUSIVE", []

    mean = sum(scored) / len(scored)

    if mean >= PASS_THRESHOLD:
        avg_verdict = "PASS"
    elif mean >= WARN_THRESHOLD:
        avg_verdict = "WARN"
    else:
        avg_verdict = "FAIL"

    # Step 4: Core gate - AT-04 FAIL caps PASS down to WARN.
    if _core_gate_failed(item_list) and avg_verdict == "PASS":
        return "WARN", []

    return avg_verdict, []


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _core_gate_failed(items: Iterable[AuditItemScore]) -> bool:
    """Return True iff AT-04 is present and has verdict==FAIL."""
    return any(
        it.at_id == CORE_GATE_ID and it.verdict == "FAIL" for it in items
    )


__all__ = [
    "HARD_GATE_IDS",
    "CORE_GATE_ID",
    "IMPLEMENT_ONLY_AT_ID",
    "IMPLEMENT_LIKE_COMMANDS",
    "PASS_THRESHOLD",
    "WARN_THRESHOLD",
    "score_to_verdict",
    "apply_decision_rules",
]
