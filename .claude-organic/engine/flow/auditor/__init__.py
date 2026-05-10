"""Auditor T3 — LLM judge advisory layer (3-tier 2nd tier).

This module provides the schema canon for the Tier-2 LLM-based audit verdict
and is the single source of truth for ``audit-verdict.json`` structure.

Canon references
----------------
- T-413 (Done, commit 1ce3c2d): Auditor sidecar abolished.
  Rule: NO sidecar background process. Auditor runs integrated inside the
  workflow finalization flow (Step 4c-AUDIT), never as a standalone daemon.

- T-454 (Done): ``phase_verifier.py`` LLM-call-zero rule.
  Rule: ``engine/flow/phase_verifier.py`` must remain rule-based only
  (0 LLM calls). This module (``auditor/``) is the designated home for all
  LLM judge calls — kept strictly separate from ``phase_verifier.py``.

- T-411 (Done, commit 0c970fa): finalize AND-gate abolished.
  Rule: Advisory only. Verdict results MUST NOT block or force any kanban
  transition, merge pipeline, or workflow phase transition. Zero forced
  transitions, zero auto-revert, zero auto-block.

Advisory-only guarantee (enforced at all call sites)
------------------------------------------------------
The auditor result is advisory only:
  - Review→Done DnD proceeds regardless of verdict value (even FAIL).
  - No modal, no confirmation gate, no status forced-transition is triggered
    by any verdict value.
  - Callers MUST wrap ``run_auditor(...)`` in ``try/except`` and log WARN on
    failure; the outer finalization flow must continue unaffected.

``audit-verdict.json`` persistent schema (tier1 + tier2 combined)
------------------------------------------------------------------
This file lives at ``<work_dir>/audit-verdict.json``.
W04 (runner.py) writes it; W06 (Board API) reads it.
T-463 (Open) will populate ``tier1`` when implemented — this module reserves
the field as Optional so T-463 can read-modify-write without schema breakage.

Schema (JSON, snake_case):

.. code-block:: json

    {
        "tier1": null,
        "tier2": {
            "tier": 2,
            "items": [
                {
                    "at_id": "AT-01",
                    "score": 4,
                    "evidence": "Goal is clearly stated in one sentence.",
                    "verdict": "PASS"
                }
            ],
            "hard_gate_failed": [],
            "overall": "PASS",
            "model": "claude-sonnet-4-5",
            "tokens_in": 1234,
            "tokens_out": 567,
            "cost_usd": 0.0023,
            "duration_ms": 8900,
            "generated_at": "2026-05-10T19:11:07+09:00"
        },
        "combined": "PASS"
    }

``combined`` is computed by the Board API as worst-of(tier1.overall,
tier2.overall). Rules:
  - Either tier is FAIL  → combined = "FAIL"
  - Either tier is WARN  → combined = "WARN"
  - Both tiers are PASS  → combined = "PASS"
  - One tier is None, the other is PASS → combined = "PASS"
  - Both tiers are None  → combined = "NONE"

Public exports
--------------
- ``AuditItemScore``  — per-item score record (at_id, score, evidence, verdict)
- ``AuditVerdict``    — full tier-2 verdict record (all 10 fields)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Literal, Optional


@dataclass
class AuditItemScore:
    """Score record for a single AT-NN evaluation item.

    Attributes:
        at_id: Evaluation item identifier, e.g. ``"AT-01"``.
        score: Integer score 1–5, or ``None`` if the LLM call failed/was
            skipped.  ``None`` items are excluded from weighted-average
            calculation in ``rubric.py``.
        evidence: One-sentence rationale from the LLM judge supporting the
            score.  Set to ``"skipped: LLM call failed"`` when score is None.
        verdict: Derived verdict label.  Mapping: score ≥ 4 → ``"PASS"``,
            score == 3 → ``"WARN"``, score ≤ 2 → ``"FAIL"``.  When score is
            ``None`` the value should be ``"FAIL"`` unless the item was
            intentionally skipped (e.g., AT-12 for non-implement commands),
            in which case ``"PASS"`` with evidence ``"skipped: not applicable"``
            is used.
    """

    at_id: str
    score: Optional[int]
    evidence: str
    verdict: Literal["PASS", "WARN", "FAIL"]

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AuditItemScore":
        """Reconstruct from a plain dict (e.g., after ``json.loads``).

        Args:
            data: Dict with keys matching field names.

        Returns:
            Reconstructed ``AuditItemScore`` instance.
        """
        return cls(
            at_id=data["at_id"],
            score=data.get("score"),
            evidence=data["evidence"],
            verdict=data["verdict"],
        )


@dataclass
class AuditVerdict:
    """Full Tier-2 LLM audit verdict for a single workflow run.

    Attributes:
        tier: Always ``2`` for this module.  Reserved for future combined-tier
            records.
        items: List of per-item scores for AT-01 through AT-12.
        hard_gate_failed: List of ``at_id`` strings for any hard-gate items
            that failed (AT-06, AT-09).  Empty list when no hard-gate failure.
        overall: Aggregated verdict — ``"PASS"``, ``"WARN"``, ``"FAIL"``, or
            ``"INCONCLUSIVE"`` (when all items have ``score=None``).
        model: Model identifier used for LLM calls, e.g.
            ``"claude-sonnet-4-5"``.
        tokens_in: Total input tokens consumed across all AT-NN calls.
        tokens_out: Total output tokens consumed across all AT-NN calls.
        cost_usd: Total cost in USD across all AT-NN calls.
        duration_ms: Total wall-clock duration in milliseconds for all calls.
        generated_at: ISO-8601 timestamp string of when the verdict was
            produced, e.g. ``"2026-05-10T19:11:07+09:00"``.
    """

    tier: int
    items: list[AuditItemScore]
    hard_gate_failed: list[str]
    overall: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    duration_ms: int
    generated_at: str

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict representation.

        Returns:
            Dict with nested ``items`` as plain dicts.
        """
        d = asdict(self)
        return d

    def to_json(self) -> str:
        """Serialise to a JSON string.

        Returns:
            Compact JSON string suitable for writing to ``audit-verdict.json``.
        """
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "AuditVerdict":
        """Reconstruct from a plain dict (e.g., after ``json.loads``).

        Args:
            data: Dict with keys matching field names.  ``items`` values are
                reconstructed as ``AuditItemScore`` instances.

        Returns:
            Reconstructed ``AuditVerdict`` instance.
        """
        items = [AuditItemScore.from_dict(i) for i in data.get("items", [])]
        return cls(
            tier=data["tier"],
            items=items,
            hard_gate_failed=data.get("hard_gate_failed", []),
            overall=data["overall"],
            model=data["model"],
            tokens_in=data["tokens_in"],
            tokens_out=data["tokens_out"],
            cost_usd=data["cost_usd"],
            duration_ms=data["duration_ms"],
            generated_at=data["generated_at"],
        )

    @classmethod
    def from_json(cls, json_str: str) -> "AuditVerdict":
        """Deserialise from a JSON string.

        Args:
            json_str: JSON string as produced by ``to_json()``.

        Returns:
            Reconstructed ``AuditVerdict`` instance.
        """
        return cls.from_dict(json.loads(json_str))


__all__ = [
    "AuditItemScore",
    "AuditVerdict",
]
