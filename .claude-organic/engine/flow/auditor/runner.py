"""Auditor T3 — LLM call adapter, cost measurement, verdict persistence.

This module is the *only* place in the auditor package that makes external
LLM calls.  It collects the four workflow artifacts from ``work_dir``,
substitutes them into the AT-01..AT-12 prompt templates, dispatches one
``claude`` CLI subprocess per item, parses the JSON verdict line, accumulates
per-call cost/duration, and persists the combined Tier-2 result to
``audit-verdict.json``.

Canon references (must be preserved by every code path here)
------------------------------------------------------------
- T-413 (Done, commit 1ce3c2d) — Auditor sidecar abolished.
  Rule: NO sidecar background process.  The auditor runs synchronously inside
  the workflow finalization flow (called from ``finalization.py`` Step 4c).
  This module never spawns daemons, never writes to a queue, never schedules
  itself.  Each call is one-shot and returns to the caller.

- T-454 (Done) — ``phase_verifier.py`` LLM-call-zero rule.
  Rule: ``engine/flow/phase_verifier.py`` MUST remain rule-based only
  (0 LLM calls).  All LLM judge calls live here, kept strictly separate.
  No import of phase_verifier or use of its decision functions in this file.

- T-411 (Done, commit 0c970fa) — finalize AND-gate abolished.
  Rule: Advisory only.  The verdict produced here MUST NOT block, gate, or
  force any kanban transition / merge pipeline / workflow phase change.  The
  caller (Step 4c-AUDIT) wraps this entry point in ``try/except`` and logs
  WARN on failure; finalization continues unaffected.  This module raises
  exceptions only when it cannot persist the verdict file at all — never to
  signal a "failed" verdict result (that goes via the ``overall`` field).

External dependency
-------------------
- ``claude`` CLI — invoked via ``subprocess.run`` with::

      claude --print --model <name> --output-format json

  When the CLI binary is not on ``PATH`` (FileNotFoundError) the runner
  degrades gracefully: every per-item score becomes ``None``,
  ``evidence`` records the failure reason, and the verdict still persists
  with ``overall="INCONCLUSIVE"``.  The caller must not treat CLI absence as
  a workflow error.

Cost measurement (4 metrics per AT-NN call)
--------------------------------------------
+---------------+-----------------------------------------------------------+
| Metric        | Source                                                    |
+===============+===========================================================+
| tokens_in     | ``usage.input_tokens`` from the CLI JSON envelope         |
+---------------+-----------------------------------------------------------+
| tokens_out    | ``usage.output_tokens`` from the CLI JSON envelope        |
+---------------+-----------------------------------------------------------+
| cost_usd      | ``total_cost_usd`` from the CLI JSON envelope, or fallback|
|               | computed from ``MODEL_PRICING`` table                     |
+---------------+-----------------------------------------------------------+
| duration_ms   | ``time.monotonic()`` diff around the subprocess.run call  |
+---------------+-----------------------------------------------------------+

Per-item totals are summed into the ``AuditVerdict`` record:
``tokens_in``, ``tokens_out``, ``cost_usd``, ``duration_ms``.

Persistence
-----------
Two side effects (and only these two) at the end of every call:

1. ``<work_dir>/audit-verdict.json`` — read-modify-write JSON file.
   Existing ``tier1`` field (if any) is preserved; only ``tier2`` is updated;
   ``combined`` is recomputed as worst-of(tier1.overall, tier2.overall).

2. ``<work_dir>/metrics.jsonl`` — single line appended with shape::

       {"event_type": "auditor_t3.summary",
        "ticket_id": "T-NNN" or null,
        "overall": "PASS|WARN|FAIL|INCONCLUSIVE",
        "total_tokens_in": int, "total_tokens_out": int,
        "total_cost_usd": float, "total_duration_ms": int,
        "item_count": int,
        "generated_at": "..."}

   T-462 Dashboard Phase 4 aggregates this event_type for cost reporting.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import AuditItemScore, AuditVerdict
from .rubric import IMPLEMENT_LIKE_COMMANDS, apply_decision_rules, score_to_verdict


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: AT-NN ids in the order they are evaluated.
AT_IDS: tuple[str, ...] = tuple(f"AT-{i:02d}" for i in range(1, 13))

#: AT-NN that applies only to implement/refactor/build commands.
IMPLEMENT_ONLY_AT_ID: str = "AT-12"

#: Per-call subprocess timeout in seconds (per W04 spec line 110).
CALL_TIMEOUT_S: int = 90

#: Fallback per-MTok pricing (USD) for when ``total_cost_usd`` is missing.
#: Conservative defaults — Sonnet 4.5 list price as of 2026-05.
MODEL_PRICING: dict[str, dict[str, float]] = {
    "sonnet": {"input": 3.0, "output": 15.0},
    "claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "haiku": {"input": 0.80, "output": 4.0},
    "opus": {"input": 15.0, "output": 75.0},
}
DEFAULT_PRICING: dict[str, float] = {"input": 3.0, "output": 15.0}


#: Frontmatter regex — matches the first ``---`` ... ``---`` block at the
#: top of an AT-NN.md file.  The body after the closing ``---`` is the
#: prompt template.
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)

#: AT-NN frontmatter key/value extractor (one per line).
_FM_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_auditor(
    work_dir: str,
    *,
    model: str = "sonnet",
    effort: str = "low",
    ticket_id: Optional[str] = None,
) -> AuditVerdict:
    """Run all applicable AT-NN evaluations and persist the verdict.

    Args:
        work_dir: Absolute path to the workflow run directory containing
            ``user_prompt.txt``, ``plan.md``, ``report.md`` and
            ``work/W*.md`` artifacts.
        model: Model identifier passed to ``claude --model``.  Default
            ``"sonnet"``.
        effort: Effort level passed to ``claude --effort``.  Default
            ``"low"`` (per plan.md AUDITOR_T3_EFFORT default).
        ticket_id: Optional T-NNN id recorded in the metrics event for
            downstream aggregation.  Set to ``None`` when unknown.

    Returns:
        Fully populated ``AuditVerdict`` containing 12 item scores and the
        aggregated overall verdict.  When the ``claude`` CLI is unavailable
        every score is ``None`` and ``overall`` is ``"INCONCLUSIVE"``.

    Raises:
        OSError: When ``audit-verdict.json`` cannot be written to ``work_dir``
            (e.g., directory is read-only).  All other failures (LLM errors,
            timeouts, parse errors) are captured per-item and produce a
            valid verdict object with ``score=None`` for the affected items.
    """
    work_dir_path = Path(work_dir).resolve()

    # ---- Collect artifacts -------------------------------------------------
    artifacts = _collect_artifacts(work_dir_path)

    # ---- Determine command from ticket XML --------------------------------
    command = _extract_command(artifacts["ticket_xml"]) or "implement"

    # ---- Iterate AT-01..AT-12 ----------------------------------------------
    items: list[AuditItemScore] = []
    total_tokens_in = 0
    total_tokens_out = 0
    total_cost_usd = 0.0
    total_duration_ms = 0

    cli_available = shutil.which("claude") is not None

    prompts_dir = Path(__file__).parent / "prompts"

    for at_id in AT_IDS:
        prompt_path = prompts_dir / f"{at_id}.md"

        # Skip AT-12 outside implement/refactor/build commands.
        if at_id == IMPLEMENT_ONLY_AT_ID and command not in IMPLEMENT_LIKE_COMMANDS:
            items.append(
                AuditItemScore(
                    at_id=at_id,
                    score=None,
                    evidence="skipped: command not applicable",
                    verdict="PASS",
                )
            )
            continue

        # Build the substituted prompt.
        try:
            prompt_text = _build_prompt(prompt_path, artifacts)
        except FileNotFoundError as exc:
            items.append(
                AuditItemScore(
                    at_id=at_id,
                    score=None,
                    evidence=f"prompt template missing: {exc}",
                    verdict="FAIL",
                )
            )
            continue

        # Short-circuit when the CLI is absent — no point invoking subprocess.
        if not cli_available:
            items.append(
                AuditItemScore(
                    at_id=at_id,
                    score=None,
                    evidence="LLM CLI unavailable: claude binary not on PATH",
                    verdict="FAIL",
                )
            )
            continue

        # Dispatch one LLM call.
        item_score, metrics = _call_llm_judge(
            at_id=at_id,
            prompt_text=prompt_text,
            model=model,
            effort=effort,
        )
        items.append(item_score)
        total_tokens_in += metrics["tokens_in"]
        total_tokens_out += metrics["tokens_out"]
        total_cost_usd += metrics["cost_usd"]
        total_duration_ms += metrics["duration_ms"]

    # ---- Aggregate verdict --------------------------------------------------
    overall, hard_gate_failed = apply_decision_rules(items, command)

    verdict = AuditVerdict(
        tier=2,
        items=items,
        hard_gate_failed=hard_gate_failed,
        overall=overall,
        model=model,
        tokens_in=total_tokens_in,
        tokens_out=total_tokens_out,
        cost_usd=round(total_cost_usd, 6),
        duration_ms=total_duration_ms,
        generated_at=_now_iso(),
    )

    # ---- Persist ------------------------------------------------------------
    _persist_verdict(work_dir_path, verdict)
    _append_metrics_event(
        work_dir_path,
        verdict=verdict,
        ticket_id=ticket_id,
    )

    return verdict


# ---------------------------------------------------------------------------
# Artifact collection
# ---------------------------------------------------------------------------


def _collect_artifacts(work_dir: Path) -> dict[str, str]:
    """Read the four artifact inputs from ``work_dir``.

    Missing files are tolerated (empty string) so the runner can still emit
    a verdict object — the LLM judge will see the absence and score
    accordingly.
    """
    ticket_xml = _safe_read(work_dir / "user_prompt.txt")
    plan_md = _safe_read(work_dir / "plan.md")
    report_md = _safe_read(work_dir / "report.md")
    work_md_aggregated = _aggregate_work_md(work_dir / "work")

    return {
        "ticket_xml": ticket_xml,
        "plan_md": plan_md,
        "report_md": report_md,
        "work_md_aggregated": work_md_aggregated,
    }


def _safe_read(path: Path) -> str:
    """Return file contents or an empty string if absent / unreadable."""
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""


def _aggregate_work_md(work_dir: Path) -> str:
    """Concatenate all ``W*.md`` files in ``<work_dir>/work/`` with headers.

    Files are sorted alphabetically (W01 < W02 < ... < W10 < W11) and each
    file is preceded by a ``## <filename>`` heading so the LLM can identify
    individual worker reports.
    """
    if not work_dir.is_dir():
        return ""

    parts: list[str] = []
    for entry in sorted(work_dir.glob("W*.md")):
        body = _safe_read(entry)
        if not body:
            continue
        parts.append(f"## {entry.name}\n\n{body}".rstrip())
    return "\n\n".join(parts)


def _extract_command(ticket_xml: str) -> Optional[str]:
    """Pull the ``<command>...</command>`` value from the ticket XML."""
    if not ticket_xml:
        return None
    match = re.search(
        r"<command>\s*(\w+)\s*</command>", ticket_xml, re.IGNORECASE
    )
    return match.group(1).lower() if match else None


# ---------------------------------------------------------------------------
# Prompt substitution
# ---------------------------------------------------------------------------


def _build_prompt(prompt_path: Path, artifacts: dict[str, str]) -> str:
    """Read an AT-NN.md, strip frontmatter, and substitute artifact placeholders.

    The prompt body uses Python-style ``{ticket_xml}`` placeholders that we
    substitute manually (not str.format) to avoid issues with curly braces
    inside the artifact contents.
    """
    raw = prompt_path.read_text(encoding="utf-8")

    # Strip frontmatter if present.
    fm_match = _FRONTMATTER_RE.match(raw)
    body = fm_match.group(2) if fm_match else raw

    # Manual placeholder substitution.
    for key in ("ticket_xml", "plan_md", "report_md", "work_md_aggregated"):
        body = body.replace("{" + key + "}", artifacts.get(key, ""))

    return body


def _parse_frontmatter(prompt_path: Path) -> dict[str, str]:
    """Return frontmatter key->value strings from an AT-NN.md template.

    Used to discover ``gate_type`` and ``applicable_commands`` metadata.
    Robust to missing frontmatter (returns empty dict).
    """
    raw = _safe_read(prompt_path)
    if not raw:
        return {}
    fm_match = _FRONTMATTER_RE.match(raw)
    if not fm_match:
        return {}
    out: dict[str, str] = {}
    for line in fm_match.group(1).splitlines():
        kv = _FM_LINE_RE.match(line)
        if kv:
            out[kv.group(1)] = kv.group(2).strip()
    return out


# ---------------------------------------------------------------------------
# LLM dispatch + JSON parsing
# ---------------------------------------------------------------------------


def _call_llm_judge(
    *,
    at_id: str,
    prompt_text: str,
    model: str,
    effort: str,
) -> tuple[AuditItemScore, dict[str, Any]]:
    """Invoke the ``claude`` CLI for one AT-NN item and parse the response.

    Returns:
        2-tuple ``(item_score, metrics_dict)``.  ``metrics_dict`` always
        contains keys ``tokens_in``, ``tokens_out``, ``cost_usd``,
        ``duration_ms`` (zero when the call failed before completion).
    """
    metrics = {
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
        "duration_ms": 0,
    }

    cmd = [
        "claude",
        "--print",
        "--model",
        model,
        "--output-format",
        "json",
        "--effort",
        effort,
    ]

    t_start = time.monotonic()
    try:
        completed = subprocess.run(
            cmd,
            input=prompt_text,
            capture_output=True,
            text=True,
            timeout=CALL_TIMEOUT_S,
            check=False,
        )
    except FileNotFoundError as exc:
        metrics["duration_ms"] = int((time.monotonic() - t_start) * 1000)
        return (
            AuditItemScore(
                at_id=at_id,
                score=None,
                evidence=f"LLM CLI unavailable: {exc}",
                verdict="FAIL",
            ),
            metrics,
        )
    except subprocess.TimeoutExpired:
        metrics["duration_ms"] = CALL_TIMEOUT_S * 1000
        return (
            AuditItemScore(
                at_id=at_id,
                score=None,
                evidence=f"LLM call failed: timeout after {CALL_TIMEOUT_S}s",
                verdict="FAIL",
            ),
            metrics,
        )
    except OSError as exc:
        metrics["duration_ms"] = int((time.monotonic() - t_start) * 1000)
        return (
            AuditItemScore(
                at_id=at_id,
                score=None,
                evidence=f"LLM call failed: OSError {exc}",
                verdict="FAIL",
            ),
            metrics,
        )

    metrics["duration_ms"] = int((time.monotonic() - t_start) * 1000)

    if completed.returncode != 0:
        return (
            AuditItemScore(
                at_id=at_id,
                score=None,
                evidence=(
                    f"LLM call failed: exit={completed.returncode} "
                    f"stderr={(completed.stderr or '').strip()[:80]}"
                ),
                verdict="FAIL",
            ),
            metrics,
        )

    # Parse the CLI JSON envelope.
    try:
        envelope = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return (
            AuditItemScore(
                at_id=at_id,
                score=None,
                evidence=f"LLM call failed: bad envelope JSON ({exc.msg})",
                verdict="FAIL",
            ),
            metrics,
        )

    # Extract usage + cost metrics.
    usage = envelope.get("usage") or {}
    metrics["tokens_in"] = int(usage.get("input_tokens", 0) or 0)
    metrics["tokens_out"] = int(usage.get("output_tokens", 0) or 0)

    if envelope.get("total_cost_usd") is not None:
        metrics["cost_usd"] = float(envelope["total_cost_usd"])
    else:
        # Fallback to model pricing table.
        metrics["cost_usd"] = _estimate_cost_usd(
            model=model,
            tokens_in=metrics["tokens_in"],
            tokens_out=metrics["tokens_out"],
        )

    # Pull verdict JSON out of the result text.
    result_text = envelope.get("result") or ""
    item_score = _parse_verdict_line(at_id, result_text)
    return item_score, metrics


def _parse_verdict_line(at_id: str, result_text: str) -> AuditItemScore:
    """Extract a verdict JSON object from the LLM's free-form response.

    Strategy: scan lines from the bottom up; the first line that parses as a
    JSON object containing an ``at_id`` key wins.  Falls back to FAIL with
    parse-error evidence if no candidate line is found.
    """
    if not result_text.strip():
        return AuditItemScore(
            at_id=at_id,
            score=None,
            evidence="LLM call failed: empty result text",
            verdict="FAIL",
        )

    candidates = [ln.strip() for ln in result_text.strip().splitlines() if ln.strip()]
    for line in reversed(candidates):
        # Quick filter — must look like a JSON object.
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict) or "at_id" not in obj:
            continue
        return _coerce_item_score(at_id, obj)

    return AuditItemScore(
        at_id=at_id,
        score=None,
        evidence="LLM call failed: verdict JSON line not found in result",
        verdict="FAIL",
    )


def _coerce_item_score(at_id: str, obj: dict[str, Any]) -> AuditItemScore:
    """Build an ``AuditItemScore`` from a parsed verdict dict.

    Validates score range (1-5 or null) and verdict label.  When the LLM's
    self-reported verdict disagrees with ``score_to_verdict`` we trust the
    score-derived label (deterministic).
    """
    raw_score = obj.get("score")
    score: Optional[int]
    if raw_score is None:
        score = None
    else:
        try:
            score = int(raw_score)
        except (TypeError, ValueError):
            score = None
        else:
            if score < 1 or score > 5:
                score = None

    evidence = str(obj.get("evidence", ""))[:240]
    if not evidence:
        evidence = "no evidence provided"

    raw_verdict = str(obj.get("verdict", "")).upper()
    if score is None:
        # Trust the LLM's verdict in skip cases (PASS for "not applicable").
        if raw_verdict in ("PASS", "WARN", "FAIL"):
            verdict = raw_verdict
        else:
            verdict = "FAIL"
    else:
        verdict = score_to_verdict(score)

    return AuditItemScore(
        at_id=at_id,
        score=score,
        evidence=evidence,
        verdict=verdict,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Cost fallback
# ---------------------------------------------------------------------------


def _estimate_cost_usd(*, model: str, tokens_in: int, tokens_out: int) -> float:
    """Estimate cost in USD when the CLI envelope omits ``total_cost_usd``.

    Looks up per-MTok input/output rates in ``MODEL_PRICING``.  Unknown
    models fall back to ``DEFAULT_PRICING`` (Sonnet rates).
    """
    pricing = MODEL_PRICING.get(model) or DEFAULT_PRICING
    cost_in = (tokens_in / 1_000_000.0) * pricing["input"]
    cost_out = (tokens_out / 1_000_000.0) * pricing["output"]
    return round(cost_in + cost_out, 6)


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def _persist_verdict(work_dir: Path, verdict: AuditVerdict) -> None:
    """Write/update ``<work_dir>/audit-verdict.json``.

    Read-modify-write semantics: existing ``tier1`` is preserved, ``tier2``
    is replaced, ``combined`` recomputed.  Atomic write via tmp + rename
    when possible.
    """
    target = work_dir / "audit-verdict.json"

    # Read existing data (preserves tier1 from a future T-463 run).
    existing: dict[str, Any]
    if target.is_file():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                existing = {}
        except (OSError, json.JSONDecodeError):
            existing = {}
    else:
        existing = {}

    tier1 = existing.get("tier1")  # may be None or a dict
    tier2_dict = asdict(verdict)
    combined = _combine_overall(
        tier1.get("overall") if isinstance(tier1, dict) else None,
        tier2_dict.get("overall"),
    )

    payload = {
        "tier1": tier1,
        "tier2": tier2_dict,
        "combined": combined,
    }

    # Best-effort atomic write — tmp file + rename within same dir.
    work_dir.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, target)


def _combine_overall(tier1_overall: Optional[str], tier2_overall: Optional[str]) -> str:
    """Worst-of(tier1, tier2) policy from W01 schema docstring.

    - Either tier FAIL                         -> FAIL
    - Either tier WARN (and no FAIL)           -> WARN
    - Both PASS                                -> PASS
    - One None, the other PASS                 -> PASS
    - Both None / unrecognised                 -> NONE
    - INCONCLUSIVE treated as None for combining
    """
    def normalise(v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v_up = v.upper()
        if v_up in ("PASS", "WARN", "FAIL"):
            return v_up
        return None  # INCONCLUSIVE / unknown -> treat as missing

    a = normalise(tier1_overall)
    b = normalise(tier2_overall)

    if a == "FAIL" or b == "FAIL":
        return "FAIL"
    if a == "WARN" or b == "WARN":
        return "WARN"
    if a == "PASS" or b == "PASS":
        return "PASS"
    return "NONE"


def _append_metrics_event(
    work_dir: Path,
    *,
    verdict: AuditVerdict,
    ticket_id: Optional[str],
) -> None:
    """Append a single ``auditor_t3.summary`` event to ``metrics.jsonl``.

    Failure to append is *not* propagated — metrics are best-effort and the
    verdict file is the canonical source of truth.
    """
    target = work_dir / "metrics.jsonl"
    event = {
        "event_type": "auditor_t3.summary",
        "ticket_id": ticket_id,
        "overall": verdict.overall,
        "total_tokens_in": verdict.tokens_in,
        "total_tokens_out": verdict.tokens_out,
        "total_cost_usd": verdict.cost_usd,
        "total_duration_ms": verdict.duration_ms,
        "item_count": len(verdict.items),
        "model": verdict.model,
        "generated_at": verdict.generated_at,
    }
    try:
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        # metrics is advisory — silently skip on filesystem errors.
        pass


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return the current time as an ISO-8601 string with timezone."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


__all__ = [
    "AT_IDS",
    "CALL_TIMEOUT_S",
    "MODEL_PRICING",
    "DEFAULT_PRICING",
    "run_auditor",
]
