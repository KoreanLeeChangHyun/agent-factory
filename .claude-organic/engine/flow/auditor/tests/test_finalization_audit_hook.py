"""Unit tests for finalization._run_audit_hook — Step 4c-AUDIT advisory hook.

Covers the four isolation cases from W05 spec:

  Case 1: HOOK_AUDITOR_T3 unset/false  -> returns False, run_auditor not called.
  Case 2: HOOK_AUDITOR_T3=true + status='완료' + ticket_number set
          -> run_auditor called once, returns True.
  Case 3: run_auditor raises an Exception
          -> returns False, exception does NOT propagate (advisory-only canon).
  Case 4: status='실패'
          -> returns False, run_auditor not called (LLM cost-avoidance canon).

Canon references preserved by every test:
  - T-411 (commit 0c970fa) — finalize AND-gate abolished: advisory only.
  - T-413 (commit 1ce3c2d) — Auditor sidecar abolished.
  - T-454 (Done)           — phase_verifier LLM-call-zero rule.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# sys.path setup — .claude-organic/engine must be importable as `flow` package.
# ---------------------------------------------------------------------------

_ENGINE_DIR = str(Path(__file__).resolve().parents[3])
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from flow.finalization import _run_audit_hook  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_verdict(**kwargs) -> MagicMock:
    """Return a mock AuditVerdict with sensible defaults."""
    v = MagicMock()
    v.overall = kwargs.get("overall", "PASS")
    v.tokens_in = kwargs.get("tokens_in", 100)
    v.tokens_out = kwargs.get("tokens_out", 20)
    v.cost_usd = kwargs.get("cost_usd", 0.001)
    v.duration_ms = kwargs.get("duration_ms", 500)
    return v


# ---------------------------------------------------------------------------
# Case 1 — HOOK_AUDITOR_T3 unset / false -> skip
# ---------------------------------------------------------------------------


class TestCase1_HookDisabled:
    """run_auditor must not be called and False must be returned when the hook
    environment variable is absent or set to anything other than 'true'."""

    @pytest.mark.parametrize(
        "env_value",
        [None, "false", "FALSE", "0", "off", ""],
    )
    def test_returns_false_when_hook_disabled(self, env_value, tmp_path):
        work_dir = str(tmp_path)
        (tmp_path / "workflow.log").touch()

        env_patch = {}
        if env_value is not None:
            env_patch["HOOK_AUDITOR_T3"] = env_value

        with patch.dict(os.environ, env_patch, clear=False):
            if env_value is None:
                os.environ.pop("HOOK_AUDITOR_T3", None)

            with patch("flow.auditor.runner.run_auditor") as mock_run:
                result = _run_audit_hook(work_dir, "T-477", "완료")

        assert result is False, f"Expected False for HOOK_AUDITOR_T3={env_value!r}"
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# Case 2 — HOOK_AUDITOR_T3=true + status=완료 + ticket_number set -> happy path
# ---------------------------------------------------------------------------


class TestCase2_HookEnabled:
    """When the hook is enabled with a valid completed workflow, run_auditor
    must be called exactly once and True must be returned."""

    def test_returns_true_and_calls_run_auditor_once(self, tmp_path):
        work_dir = str(tmp_path)
        (tmp_path / "workflow.log").touch()
        verdict = _make_verdict(overall="PASS")

        with patch.dict(
            os.environ,
            {
                "HOOK_AUDITOR_T3": "true",
                "AUDITOR_T3_MODEL": "sonnet",
                "AUDITOR_T3_EFFORT": "low",
            },
        ):
            with patch("flow.auditor.runner.run_auditor", return_value=verdict) as mock_run:
                result = _run_audit_hook(work_dir, "T-477", "완료")

        assert result is True
        mock_run.assert_called_once_with(
            work_dir,
            model="sonnet",
            effort="low",
            ticket_id="T-477",
        )

    def test_env_model_effort_forwarded(self, tmp_path):
        """Custom AUDITOR_T3_MODEL / EFFORT values must reach run_auditor."""
        work_dir = str(tmp_path)
        (tmp_path / "workflow.log").touch()
        verdict = _make_verdict(overall="WARN")

        with patch.dict(
            os.environ,
            {
                "HOOK_AUDITOR_T3": "true",
                "AUDITOR_T3_MODEL": "opus",
                "AUDITOR_T3_EFFORT": "high",
            },
        ):
            with patch("flow.auditor.runner.run_auditor", return_value=verdict) as mock_run:
                _run_audit_hook(work_dir, "T-001", "완료")

        _, kwargs = mock_run.call_args
        assert kwargs["model"] == "opus"
        assert kwargs["effort"] == "high"


# ---------------------------------------------------------------------------
# Case 3 — run_auditor raises Exception -> False returned, exception NOT raised
# ---------------------------------------------------------------------------


class TestCase3_RunAuditorException:
    """Advisory-only canon (T-411): any exception from run_auditor must be
    silenced inside _run_audit_hook.  Finalization flow must not be affected."""

    @pytest.mark.parametrize(
        "exc_type,exc_msg",
        [
            (RuntimeError, "subprocess failed"),
            (FileNotFoundError, "claude CLI not found"),
            (ValueError, "malformed verdict JSON"),
            (Exception, "unexpected error"),
        ],
    )
    def test_exception_is_absorbed_returns_false(self, exc_type, exc_msg, tmp_path):
        work_dir = str(tmp_path)
        (tmp_path / "workflow.log").touch()

        with patch.dict(os.environ, {"HOOK_AUDITOR_T3": "true"}):
            with patch(
                "flow.auditor.runner.run_auditor",
                side_effect=exc_type(exc_msg),
            ):
                try:
                    result = _run_audit_hook(work_dir, "T-477", "완료")
                except Exception as propagated:  # noqa: BLE001
                    pytest.fail(
                        f"_run_audit_hook propagated {type(propagated).__name__}: {propagated}"
                    )

        assert result is False, "Expected False when run_auditor raises"


# ---------------------------------------------------------------------------
# Case 4 — status='실패' -> False, run_auditor not called (LLM cost avoidance)
# ---------------------------------------------------------------------------


class TestCase4_StatusFail:
    """When status is '실패', _run_audit_hook must skip the LLM call entirely
    to avoid wasting tokens on a failed workflow (cost-avoidance canon)."""

    def test_failed_status_returns_false_no_call(self, tmp_path):
        work_dir = str(tmp_path)
        (tmp_path / "workflow.log").touch()

        with patch.dict(os.environ, {"HOOK_AUDITOR_T3": "true"}):
            with patch("flow.auditor.runner.run_auditor") as mock_run:
                result = _run_audit_hook(work_dir, "T-477", "실패")

        assert result is False
        mock_run.assert_not_called()

    def test_empty_ticket_number_returns_false(self, tmp_path):
        """ticket_number=None or '' must also be skipped."""
        work_dir = str(tmp_path)
        (tmp_path / "workflow.log").touch()

        with patch.dict(os.environ, {"HOOK_AUDITOR_T3": "true"}):
            with patch("flow.auditor.runner.run_auditor") as mock_run:
                result_none = _run_audit_hook(work_dir, None, "완료")
                result_empty = _run_audit_hook(work_dir, "", "완료")

        assert result_none is False
        assert result_empty is False
        mock_run.assert_not_called()
