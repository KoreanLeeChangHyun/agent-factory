"""test retry.py —  retry.py module testing.

Price:
  - render retry prompt (template fill, missing items format, empty fallback)
  - spawn with retry (mock spawn + verification, N max loop fixation)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from engine.apps.production_line._common import WorkflowContext
from engine.apps.production_line._retry import render_retry_prompt, spawn_with_retry
from engine.apps.production_line._spawn import SpawnResult
from engine.apps.production_line._verify import VerifyResult


def _make_ctx(tmp_path: Path) -> WorkflowContext:
    return WorkflowContext(
        ticket_no="T-489",
        registry_key="20260515-000000",
        work_dir=tmp_path,
        current_step="PLAN",
    )


def test_render_retry_prompt_basic(tmp_path: Path) -> None:
    out = render_retry_prompt(
        ["plan.md frontmatter parse failed", "phases empty"],
        tmp_path / "plan.md",
    )
    assert "plan.md frontmatter parse failed" in out
    assert "phases empty" in out
    assert "Log in" in out
    assert "Default Search" in out
    assert str(tmp_path / "plan.md") in out


def test_render_retry_prompt_empty_missing() -> None:
    out = render_retry_prompt([], Path("/tmp/x.md"))
    # empty missing when fallback message
    assert "(Personal order)" in out


@pytest.fixture
def mock_spawn_calls():
    """spawn claude / spawn claude resume mock — call count tracking."""
    calls = {"initial": 0, "resume": 0}

    def fake_initial(**kwargs):
        calls["initial"] += 1
        return SpawnResult(returncode=0, stdout="", stderr="")

    def fake_resume(**kwargs):
        calls["resume"] += 1
        return SpawnResult(returncode=0, stdout="", stderr="")

    with patch("engine.apps.production_line._retry.spawn_claude", side_effect=fake_initial), \
         patch("engine.apps.production_line._retry.spawn_claude_resume", side_effect=fake_resume):
        yield calls


def test_spawn_with_retry_first_pass(mock_spawn_calls, tmp_path: Path) -> None:
    """verification PASS Instant return — 1 initial resume, 0 times."""
    ctx = _make_ctx(tmp_path)
    artifact = tmp_path / "plan.md"

    def verify_pass() -> VerifyResult:
        return VerifyResult(True, [])

    result, _, retry = spawn_with_retry(
        ctx,
        step="PLAN",
        initial_prompt="initial",
        system_prompt="sys",
        session_id="uuid-x",
        verify=verify_pass,
        artifact_path=artifact,
    )
    assert result.ok
    assert retry == 0
    assert mock_spawn_calls["initial"] == 1
    assert mock_spawn_calls["resume"] == 0


def test_spawn_with_retry_one_retry(mock_spawn_calls, tmp_path: Path) -> None:
    """First verification FAIL, one retry pass — initial 1, resume 1."""
    ctx = _make_ctx(tmp_path)
    artifact = tmp_path / "plan.md"
    attempts = {"n": 0}

    def verify_then_pass() -> VerifyResult:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return VerifyResult(False, ["missing field"])
        return VerifyResult(True, [])

    result, _, retry = spawn_with_retry(
        ctx,
        step="PLAN",
        initial_prompt="initial",
        system_prompt="sys",
        session_id="uuid-x",
        verify=verify_then_pass,
        artifact_path=artifact,
    )
    assert result.ok
    assert retry == 1
    assert mock_spawn_calls["initial"] == 1
    assert mock_spawn_calls["resume"] == 1


def test_spawn_with_retry_max_exceeded(mock_spawn_calls, tmp_path: Path) -> None:
    """N max exceed — FAIL until the end of verification."""
    ctx = _make_ctx(tmp_path)
    artifact = tmp_path / "plan.md"

    def verify_always_fail() -> VerifyResult:
        return VerifyResult(False, ["persistent error"])

    result, _, retry = spawn_with_retry(
        ctx,
        step="PLAN",  # PLAN N_max=2
        initial_prompt="initial",
        system_prompt="sys",
        session_id="uuid-x",
        verify=verify_always_fail,
        artifact_path=artifact,
    )
    assert not result.ok
    assert retry == 2  # PLAN N_max
    # 1st + N resume max
    assert mock_spawn_calls["initial"] == 1
    assert mock_spawn_calls["resume"] == 2
