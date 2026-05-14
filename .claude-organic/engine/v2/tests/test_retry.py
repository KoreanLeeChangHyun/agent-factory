"""test_retry.py — _retry.py 단위 테스트.

대상:
  - render_retry_prompt (template fill, missing items 형식, empty fallback)
  - spawn_with_retry (mock spawn + verify, N_max loop 정합)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from engine.v2._common import WorkflowContext
from engine.v2._retry import render_retry_prompt, spawn_with_retry
from engine.v2._spawn import SpawnResult
from engine.v2._verify import VerifyResult


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
    assert "다시 작성" in out
    assert "다른 영역 수정 금지" in out
    assert str(tmp_path / "plan.md") in out


def test_render_retry_prompt_empty_missing() -> None:
    out = render_retry_prompt([], Path("/tmp/x.md"))
    # 빈 missing 시 fallback 메시지
    assert "(산출물 누락)" in out


@pytest.fixture
def mock_spawn_calls():
    """spawn_claude / spawn_claude_resume mock — 호출 카운트 추적."""
    calls = {"initial": 0, "resume": 0}

    def fake_initial(**kwargs):
        calls["initial"] += 1
        return SpawnResult(returncode=0, stdout="", stderr="")

    def fake_resume(**kwargs):
        calls["resume"] += 1
        return SpawnResult(returncode=0, stdout="", stderr="")

    with patch("engine.v2._retry.spawn_claude", side_effect=fake_initial), \
         patch("engine.v2._retry.spawn_claude_resume", side_effect=fake_resume):
        yield calls


def test_spawn_with_retry_first_pass(mock_spawn_calls, tmp_path: Path) -> None:
    """verify PASS 즉시 반환 — initial 1회, resume 0회."""
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
    """첫 verify FAIL, retry 1회 후 PASS — initial 1, resume 1."""
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
    """N_max 초과 — verify 끝까지 FAIL."""
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
    # initial 1회 + resume N_max 회
    assert mock_spawn_calls["initial"] == 1
    assert mock_spawn_calls["resume"] == 2
