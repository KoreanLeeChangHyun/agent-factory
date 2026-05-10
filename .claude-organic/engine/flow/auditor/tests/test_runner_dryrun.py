"""Tests for auditor/runner.py — LLM dispatch + cost + persistence.

Required coverage (W04, plan.md line 113):

  (1) Mock subprocess.run to simulate 12 successful calls — AT-06 returns
      verdict=FAIL, all others PASS → hard_gate_failed=['AT-06'], overall=FAIL.
  (2) audit-verdict.json is persisted with the correct three-key schema
      (tier1=null, tier2=verdict_dict, combined='FAIL').
  (3) metrics.jsonl receives exactly one auditor_t3.summary line with
      total_tokens_in / total_tokens_out / total_cost_usd / total_duration_ms.
  (4) command='research' triggers AT-12 skip — subprocess.run called 11 times.
  (5) FileNotFoundError on subprocess.run (claude CLI absent) → graceful
      fallback: every item score=None, overall='INCONCLUSIVE', verdict file
      still written.

No real LLM calls are made.  All tests use mocks.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add .claude-organic/engine to sys.path so `flow` package is importable.
_ENGINE_DIR = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from flow.auditor import AuditVerdict  # noqa: E402
from flow.auditor.runner import (  # noqa: E402
    AT_IDS,
    _combine_overall,
    _estimate_cost_usd,
    _parse_verdict_line,
    run_auditor,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _make_envelope(
    *,
    at_id: str,
    score: int | None = 5,
    verdict: str = "PASS",
    evidence: str = "test evidence",
    input_tokens: int = 100,
    output_tokens: int = 20,
    duration_ms: int = 1500,
    cost_usd: float = 0.0015,
) -> str:
    """Return a JSON-serialised CLI envelope mimicking ``claude --output-format json``.

    The ``result`` field embeds the AT-NN verdict line that
    ``_parse_verdict_line`` extracts.
    """
    score_repr: object = score if score is not None else None
    verdict_line = json.dumps(
        {
            "at_id": at_id,
            "score": score_repr,
            "evidence": evidence,
            "verdict": verdict,
        }
    )
    envelope = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "duration_ms": duration_ms,
        "duration_api_ms": duration_ms - 50,
        "num_turns": 1,
        "result": f"Internal reasoning here.\n{verdict_line}",
        "stop_reason": "end_turn",
        "session_id": "fake-session-id",
        "total_cost_usd": cost_usd,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
    }
    return json.dumps(envelope)


class _FakeCompleted:
    """Mimic ``subprocess.CompletedProcess`` with the fields runner.py reads."""

    def __init__(self, stdout: str, returncode: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _write_baseline_artifacts(work_dir: Path, command: str = "implement") -> None:
    """Populate work_dir with the four artifacts required by run_auditor.

    The contents are minimal but valid — enough for the runner to read +
    substitute placeholders without errors.
    """
    work_dir.mkdir(parents=True, exist_ok=True)

    (work_dir / "user_prompt.txt").write_text(
        f"<ticket>\n  <number>T-477</number>\n  <command>{command}</command>\n"
        f"  <goal>Test goal for runner dry-run.</goal>\n"
        f"  <criteria>Test criteria.</criteria>\n"
        f"</ticket>\n",
        encoding="utf-8",
    )
    (work_dir / "plan.md").write_text(
        "# Test Plan\n\nMinimal plan body for testing.\n",
        encoding="utf-8",
    )
    (work_dir / "report.md").write_text(
        "# Test Report\n\nMinimal report body for testing.\n",
        encoding="utf-8",
    )
    work_subdir = work_dir / "work"
    work_subdir.mkdir(exist_ok=True)
    (work_subdir / "W01-test.md").write_text(
        "# W01\n\nWorker 1 test report.\n",
        encoding="utf-8",
    )
    (work_subdir / "W02-test.md").write_text(
        "# W02\n\nWorker 2 test report.\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# 12-call orchestration with AT-06 FAIL hard gate
# ---------------------------------------------------------------------------


class TestRunnerImplementFlow:
    """Full 12-call run with implement command — exercises the hot path."""

    def test_at06_fail_triggers_hard_gate_overall_fail(
        self, tmp_path: Path
    ) -> None:
        """(1)+(2)+(3) — AT-06 FAIL pinned by mock, rest PASS.

        Expected: overall=FAIL, hard_gate_failed=['AT-06'].  audit-verdict.json
        persisted with combined='FAIL'.  metrics.jsonl receives one summary line.
        """
        _write_baseline_artifacts(tmp_path, command="implement")

        def fake_run(cmd, **kwargs):
            # The runner doesn't pass at_id directly — derive it from the
            # prompt text in stdin.  Each prompt body contains "AT-NN" prefix
            # near the top.  We extract the first such occurrence.
            stdin = kwargs.get("input") or ""
            at_id = _detect_at_id(stdin)
            assert at_id is not None, "prompt text missing AT-NN marker"

            if at_id == "AT-06":
                env = _make_envelope(at_id=at_id, score=1, verdict="FAIL",
                                     evidence="goal-context mismatch")
            else:
                env = _make_envelope(at_id=at_id, score=5, verdict="PASS",
                                     evidence="meets criterion")
            return _FakeCompleted(stdout=env)

        with patch("flow.auditor.runner.shutil.which", return_value="/usr/bin/claude"):
            with patch("flow.auditor.runner.subprocess.run", side_effect=fake_run) as run_mock:
                verdict = run_auditor(str(tmp_path), ticket_id="T-477")

        # 12 calls (AT-01..AT-12 all dispatched for implement).
        assert run_mock.call_count == 12

        # Verdict assertions.
        assert isinstance(verdict, AuditVerdict)
        assert verdict.overall == "FAIL"
        assert verdict.hard_gate_failed == ["AT-06"]
        assert len(verdict.items) == 12
        # AT-06 item should record FAIL.
        at06 = next(it for it in verdict.items if it.at_id == "AT-06")
        assert at06.verdict == "FAIL"
        assert at06.score == 1

        # Cost aggregation: 12 calls * 100 in / 20 out / 0.0015 usd.
        assert verdict.tokens_in == 12 * 100
        assert verdict.tokens_out == 12 * 20
        assert verdict.cost_usd == pytest.approx(12 * 0.0015, rel=1e-3)
        # duration_ms is from time.monotonic — only assert non-negative.
        assert verdict.duration_ms >= 0

        # audit-verdict.json persisted.
        verdict_path = tmp_path / "audit-verdict.json"
        assert verdict_path.is_file()
        payload = json.loads(verdict_path.read_text(encoding="utf-8"))
        assert payload["tier1"] is None
        assert payload["tier2"]["overall"] == "FAIL"
        assert payload["tier2"]["hard_gate_failed"] == ["AT-06"]
        assert payload["combined"] == "FAIL"
        # 12 items in tier2.
        assert len(payload["tier2"]["items"]) == 12

        # metrics.jsonl appended exactly once.
        metrics_path = tmp_path / "metrics.jsonl"
        assert metrics_path.is_file()
        lines = metrics_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["event_type"] == "auditor_t3.summary"
        assert event["ticket_id"] == "T-477"
        assert event["overall"] == "FAIL"
        assert event["total_tokens_in"] == 12 * 100
        assert event["total_tokens_out"] == 12 * 20
        assert event["item_count"] == 12

    def test_all_pass_overall_pass_combined_pass(self, tmp_path: Path) -> None:
        """All AT-NN PASS → overall=PASS, combined=PASS, hard_gate empty."""
        _write_baseline_artifacts(tmp_path, command="implement")

        def fake_run(cmd, **kwargs):
            at_id = _detect_at_id(kwargs.get("input") or "")
            return _FakeCompleted(
                stdout=_make_envelope(at_id=at_id, score=5, verdict="PASS")
            )

        with patch("flow.auditor.runner.shutil.which", return_value="/usr/bin/claude"):
            with patch("flow.auditor.runner.subprocess.run", side_effect=fake_run):
                verdict = run_auditor(str(tmp_path))

        assert verdict.overall == "PASS"
        assert verdict.hard_gate_failed == []
        payload = json.loads((tmp_path / "audit-verdict.json").read_text())
        assert payload["combined"] == "PASS"


# ---------------------------------------------------------------------------
# Command filter — research skips AT-12
# ---------------------------------------------------------------------------


class TestCommandFilter:
    """(4) command='research' triggers AT-12 skip — only 11 subprocess calls."""

    def test_research_command_skips_at12(self, tmp_path: Path) -> None:
        _write_baseline_artifacts(tmp_path, command="research")

        def fake_run(cmd, **kwargs):
            at_id = _detect_at_id(kwargs.get("input") or "")
            # AT-12 should never be invoked under research.
            assert at_id != "AT-12", "AT-12 must be skipped for research command"
            return _FakeCompleted(
                stdout=_make_envelope(at_id=at_id, score=5, verdict="PASS")
            )

        with patch("flow.auditor.runner.shutil.which", return_value="/usr/bin/claude"):
            with patch("flow.auditor.runner.subprocess.run", side_effect=fake_run) as run_mock:
                verdict = run_auditor(str(tmp_path))

        # AT-01..AT-11 = 11 calls.
        assert run_mock.call_count == 11

        # AT-12 record present but score=None, evidence='skipped: command not applicable'.
        at12 = next(it for it in verdict.items if it.at_id == "AT-12")
        assert at12.score is None
        assert "not applicable" in at12.evidence
        assert at12.verdict == "PASS"  # skipped items are PASS by convention.

        # Overall should be PASS (research filter excludes AT-12 from average).
        assert verdict.overall == "PASS"


# ---------------------------------------------------------------------------
# CLI unavailable fallback
# ---------------------------------------------------------------------------


class TestCliUnavailableFallback:
    """(5) FileNotFoundError fallback — CLI absence triggers conservative FAIL.

    Per the W01 schema docstring, items with score=None default to
    ``verdict="FAIL"`` (conservative).  The rubric's hard-gate rule therefore
    fires on AT-06 and AT-09, producing overall='FAIL' with
    hard_gate_failed=['AT-06','AT-09'] — the *correct* advisory signal that
    the audit could not be performed.  Advisory only: this never blocks any
    kanban transition.
    """

    def test_cli_missing_via_which_returns_failure_with_hard_gate(
        self, tmp_path: Path
    ) -> None:
        """``shutil.which('claude')`` returns None — no subprocess call attempted."""
        _write_baseline_artifacts(tmp_path, command="implement")

        with patch("flow.auditor.runner.shutil.which", return_value=None):
            with patch("flow.auditor.runner.subprocess.run") as run_mock:
                verdict = run_auditor(str(tmp_path))

        # subprocess.run never invoked because cli_available is False.
        assert run_mock.call_count == 0

        # Every item has score=None.
        assert all(it.score is None for it in verdict.items)
        # Each item evidence cites the CLI absence reason.
        for it in verdict.items:
            assert "LLM CLI unavailable" in it.evidence

        # Hard gate fires on AT-06/AT-09 (conservative default verdict=FAIL).
        assert verdict.overall == "FAIL"
        assert verdict.hard_gate_failed == ["AT-06", "AT-09"]

        # Verdict file still persisted with combined='FAIL'.
        payload = json.loads((tmp_path / "audit-verdict.json").read_text())
        assert payload["tier2"]["overall"] == "FAIL"
        assert payload["combined"] == "FAIL"

    def test_cli_present_but_subprocess_raises_filenotfound(
        self, tmp_path: Path
    ) -> None:
        """``shutil.which`` lies (returns path) but subprocess.run raises.

        TOCTOU race or binary deletion between lookup and spawn.  Runner
        must capture FileNotFoundError per-item without crashing — same
        hard-gate dynamics as the cli-missing case.
        """
        _write_baseline_artifacts(tmp_path, command="implement")

        def boom(cmd, **kwargs):
            raise FileNotFoundError(2, "No such file or directory: 'claude'")

        with patch("flow.auditor.runner.shutil.which", return_value="/usr/bin/claude"):
            with patch("flow.auditor.runner.subprocess.run", side_effect=boom):
                verdict = run_auditor(str(tmp_path))

        # All scores None; conservative FAIL default trips hard gate.
        assert all(it.score is None for it in verdict.items)
        assert verdict.overall == "FAIL"
        assert verdict.hard_gate_failed == ["AT-06", "AT-09"]
        # Each item evidence carries the failure reason.
        for it in verdict.items:
            assert "LLM CLI unavailable" in it.evidence


# ---------------------------------------------------------------------------
# Subprocess failure variants
# ---------------------------------------------------------------------------


class TestSubprocessFailureVariants:
    """Per-item resilience — single failure must not abort the run."""

    def test_timeout_on_one_item_continues(self, tmp_path: Path) -> None:
        """One AT-NN times out → that item gets score=None, others succeed."""
        _write_baseline_artifacts(tmp_path, command="implement")

        def fake_run(cmd, **kwargs):
            at_id = _detect_at_id(kwargs.get("input") or "")
            if at_id == "AT-03":
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=90)
            return _FakeCompleted(
                stdout=_make_envelope(at_id=at_id, score=5, verdict="PASS")
            )

        with patch("flow.auditor.runner.shutil.which", return_value="/usr/bin/claude"):
            with patch("flow.auditor.runner.subprocess.run", side_effect=fake_run):
                verdict = run_auditor(str(tmp_path))

        at03 = next(it for it in verdict.items if it.at_id == "AT-03")
        assert at03.score is None
        assert "timeout" in at03.evidence.lower()
        # Remaining items still PASS.
        others = [it for it in verdict.items if it.at_id != "AT-03"]
        assert all(it.score == 5 for it in others)

    def test_nonzero_returncode_records_failure(self, tmp_path: Path) -> None:
        """Subprocess returncode != 0 → score=None + stderr captured."""
        _write_baseline_artifacts(tmp_path, command="implement")

        def fake_run(cmd, **kwargs):
            at_id = _detect_at_id(kwargs.get("input") or "")
            if at_id == "AT-05":
                return _FakeCompleted(stdout="", returncode=2, stderr="rate limited")
            return _FakeCompleted(
                stdout=_make_envelope(at_id=at_id, score=4, verdict="PASS")
            )

        with patch("flow.auditor.runner.shutil.which", return_value="/usr/bin/claude"):
            with patch("flow.auditor.runner.subprocess.run", side_effect=fake_run):
                verdict = run_auditor(str(tmp_path))

        at05 = next(it for it in verdict.items if it.at_id == "AT-05")
        assert at05.score is None
        assert "exit=2" in at05.evidence

    def test_malformed_envelope_records_failure(self, tmp_path: Path) -> None:
        """Bad JSON envelope → parse error captured per item."""
        _write_baseline_artifacts(tmp_path, command="implement")

        def fake_run(cmd, **kwargs):
            at_id = _detect_at_id(kwargs.get("input") or "")
            if at_id == "AT-08":
                return _FakeCompleted(stdout="not json at all")
            return _FakeCompleted(
                stdout=_make_envelope(at_id=at_id, score=4, verdict="PASS")
            )

        with patch("flow.auditor.runner.shutil.which", return_value="/usr/bin/claude"):
            with patch("flow.auditor.runner.subprocess.run", side_effect=fake_run):
                verdict = run_auditor(str(tmp_path))

        at08 = next(it for it in verdict.items if it.at_id == "AT-08")
        assert at08.score is None
        assert "envelope" in at08.evidence.lower()


# ---------------------------------------------------------------------------
# Tier1 preservation under read-modify-write
# ---------------------------------------------------------------------------


class TestTier1Preservation:
    """The runner must preserve any pre-existing tier1 record (T-463 future)."""

    def test_existing_tier1_preserved(self, tmp_path: Path) -> None:
        """When audit-verdict.json already has tier1, it survives the rewrite."""
        _write_baseline_artifacts(tmp_path, command="implement")

        # Seed a tier1 record (simulating a future T-463 sidecar).
        existing = {
            "tier1": {
                "tier": 1,
                "overall": "WARN",
                "evidence": "rule-based: criteria too brief",
            },
            "tier2": None,
            "combined": "WARN",
        }
        (tmp_path / "audit-verdict.json").write_text(
            json.dumps(existing), encoding="utf-8"
        )

        def fake_run(cmd, **kwargs):
            at_id = _detect_at_id(kwargs.get("input") or "")
            return _FakeCompleted(
                stdout=_make_envelope(at_id=at_id, score=5, verdict="PASS")
            )

        with patch("flow.auditor.runner.shutil.which", return_value="/usr/bin/claude"):
            with patch("flow.auditor.runner.subprocess.run", side_effect=fake_run):
                run_auditor(str(tmp_path))

        payload = json.loads((tmp_path / "audit-verdict.json").read_text())
        # tier1 preserved.
        assert payload["tier1"] == existing["tier1"]
        # tier2 updated.
        assert payload["tier2"]["overall"] == "PASS"
        # combined = worst-of(WARN, PASS) = WARN.
        assert payload["combined"] == "WARN"


# ---------------------------------------------------------------------------
# Pure-function unit tests
# ---------------------------------------------------------------------------


class TestParseVerdictLine:
    """``_parse_verdict_line`` extracts the verdict JSON from result text."""

    def test_extracts_last_json_line(self) -> None:
        text = (
            "Some preamble\n"
            "Internal reasoning step 1\n"
            '{"at_id": "AT-01", "score": 4, "evidence": "ok", "verdict": "PASS"}\n'
        )
        item = _parse_verdict_line("AT-01", text)
        assert item.score == 4
        assert item.verdict == "PASS"

    def test_invalid_score_yields_none(self) -> None:
        text = '{"at_id": "AT-01", "score": 99, "evidence": "bad", "verdict": "PASS"}'
        item = _parse_verdict_line("AT-01", text)
        assert item.score is None

    def test_score_null_with_pass_verdict_preserved(self) -> None:
        text = (
            '{"at_id": "AT-12", "score": null, '
            '"evidence": "skipped: not applicable", "verdict": "PASS"}'
        )
        item = _parse_verdict_line("AT-12", text)
        assert item.score is None
        assert item.verdict == "PASS"

    def test_empty_result_returns_fail(self) -> None:
        item = _parse_verdict_line("AT-01", "")
        assert item.score is None
        assert item.verdict == "FAIL"

    def test_missing_json_line_returns_fail(self) -> None:
        item = _parse_verdict_line("AT-01", "no json here at all")
        assert item.score is None
        assert "not found" in item.evidence


class TestEstimateCostUsd:
    """``_estimate_cost_usd`` falls back to per-MTok pricing."""

    def test_known_model_uses_table(self) -> None:
        cost = _estimate_cost_usd(
            model="sonnet", tokens_in=1_000_000, tokens_out=1_000_000
        )
        # Sonnet: $3 in + $15 out = $18.
        assert cost == pytest.approx(18.0, rel=1e-6)

    def test_unknown_model_uses_default(self) -> None:
        cost = _estimate_cost_usd(
            model="some-future-model", tokens_in=1_000_000, tokens_out=0
        )
        # Default = sonnet rates → $3 input.
        assert cost == pytest.approx(3.0, rel=1e-6)


class TestCombineOverall:
    """Worst-of(tier1, tier2) policy."""

    @pytest.mark.parametrize("a, b, expected", [
        ("PASS", "PASS", "PASS"),
        ("PASS", "WARN", "WARN"),
        ("PASS", "FAIL", "FAIL"),
        ("WARN", "FAIL", "FAIL"),
        ("FAIL", "FAIL", "FAIL"),
        (None, "PASS", "PASS"),
        ("PASS", None, "PASS"),
        (None, None, "NONE"),
        ("INCONCLUSIVE", None, "NONE"),
        ("PASS", "INCONCLUSIVE", "PASS"),
    ])
    def test_combinations(
        self, a: str | None, b: str | None, expected: str
    ) -> None:
        assert _combine_overall(a, b) == expected


# ---------------------------------------------------------------------------
# Helper used by mocks
# ---------------------------------------------------------------------------


def _detect_at_id(prompt_text: str) -> str | None:
    """Find the first ``AT-NN`` token in the prompt body.

    The AT-NN.md templates always contain ``**Item:** AT-NN`` near the top,
    so we can identify which item the runner is currently dispatching from
    the stdin we capture in the mock.
    """
    import re as _re
    m = _re.search(r"AT-\d{2}", prompt_text)
    return m.group(0) if m else None


# ---------------------------------------------------------------------------
# Sanity smoke
# ---------------------------------------------------------------------------


def test_at_ids_constant_is_12() -> None:
    """AT_IDS must enumerate AT-01 through AT-12."""
    assert AT_IDS == tuple(f"AT-{i:02d}" for i in range(1, 13))
    assert len(AT_IDS) == 12
