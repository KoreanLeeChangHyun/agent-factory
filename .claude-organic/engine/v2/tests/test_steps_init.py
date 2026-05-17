"""test_steps_init.py — INIT Step 헬퍼 단위 테스트.

대상 (SPEC.md §9.1.1, Stage 3-D):
  - _parse_ticket_meta: kanban_show 출력에서 (command, title) 추출
  - _maybe_create_worktree: command=research|review 시 (None, None) 반환
  - init_step (T-495 P2): V2_REGISTRY_KEY env 우선 사용 (board 사전 발급)

통합 (worktree 실제 생성) 은 smoke 사이클로 검증.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from engine.v2.steps.init import _maybe_create_worktree, _parse_ticket_meta
from engine.v2 import steps as _steps_pkg
from engine.v2.steps import init as init_mod


_KANBAN_DUMP_TEMPLATE = """## T-491: 샘플 티켓

### Metadata
- Number: T-491
- Title: {title}
- Status: Review
- Command: {command}

### Relations
- derived-from: T-489

### Prompt
- Goal: 검증
"""


def test_parse_ticket_meta_implement() -> None:
    dump = _KANBAN_DUMP_TEMPLATE.format(command="implement", title="구현 티켓 샘플")
    command, title = _parse_ticket_meta(dump)
    assert command == "implement"
    assert title == "구현 티켓 샘플"


def test_parse_ticket_meta_research() -> None:
    dump = _KANBAN_DUMP_TEMPLATE.format(command="research", title="연구 조사")
    command, title = _parse_ticket_meta(dump)
    assert command == "research"
    assert title == "연구 조사"


def test_parse_ticket_meta_review() -> None:
    dump = _KANBAN_DUMP_TEMPLATE.format(command="review", title="리뷰 작업")
    command, title = _parse_ticket_meta(dump)
    assert command == "review"
    assert title == "리뷰 작업"


def test_parse_ticket_meta_unknown_command_fallback() -> None:
    """미지 command 는 implement 로 fallback (안전 default)."""
    dump = _KANBAN_DUMP_TEMPLATE.format(command="bogus", title="제목")
    command, _ = _parse_ticket_meta(dump)
    assert command == "implement"


def test_parse_ticket_meta_missing_command_default() -> None:
    """Command 라인 누락 시 implement default."""
    dump = "### Metadata\n- Number: T-1\n- Title: 제목\n"
    command, title = _parse_ticket_meta(dump)
    assert command == "implement"
    assert title == "제목"


def test_maybe_create_worktree_research_returns_none() -> None:
    """command=research → worktree 생성 X."""
    fb, wp = _maybe_create_worktree("T-491", "연구", "research")
    assert fb is None
    assert wp is None


def test_maybe_create_worktree_review_returns_none() -> None:
    """command=review → worktree 생성 X."""
    fb, wp = _maybe_create_worktree("T-491", "리뷰", "review")
    assert fb is None
    assert wp is None


def test_init_step_uses_v2_registry_key_env(monkeypatch, tmp_path):
    """T-495 P2 — V2_REGISTRY_KEY env 우선 사용. board 사전 발급 session_id 정합."""
    fake_key = "20260517-204200"
    monkeypatch.setenv("V2_REGISTRY_KEY", fake_key)

    captured = {}

    def fake_kanban_show(ticket_no):
        return (
            "## T-495: 샘플 티켓\n\n### Metadata\n"
            "- Number: T-495\n- Title: dummy\n- Status: Open\n- Command: research\n"
        )

    def fake_kanban_move(ticket_no, target):
        captured["kanban_move"] = (ticket_no, target)

    def fake_session_create(ctx):
        captured["session_id"] = ctx.wf_session_id
        captured["registry_key"] = ctx.registry_key

    def fake_step_start(ctx, step, **kw):
        captured["step_start"] = (step, kw.get("prev_step"))

    def fake_step_end(ctx, step, **kw):
        captured["step_end"] = (step, kw.get("outcome"))

    def fake_make_work_dir(registry_key):
        d = tmp_path / "runs" / registry_key
        (d / "work").mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(init_mod, "kanban_show", fake_kanban_show)
    monkeypatch.setattr(init_mod, "kanban_move", fake_kanban_move)
    monkeypatch.setattr(init_mod, "session_create", fake_session_create)
    monkeypatch.setattr(init_mod, "step_start", fake_step_start)
    monkeypatch.setattr(init_mod, "step_end", fake_step_end)
    monkeypatch.setattr(init_mod, "make_work_dir", fake_make_work_dir)
    # write_status / write_context / update_step / append_log 도 sandbox
    monkeypatch.setattr(init_mod, "write_status", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "write_context", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "update_step", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "append_log", lambda *a, **k: None)
    # new_registry_key 가 호출되면 env 우선 룰이 깨진 것 — 호출 0건 확인
    new_key_called = {"n": 0}

    def fake_new_key():
        new_key_called["n"] += 1
        return "should-not-be-used"

    monkeypatch.setattr(init_mod, "new_registry_key", fake_new_key)

    ctx = init_mod.init_step("T-495")

    assert ctx.registry_key == fake_key
    assert ctx.wf_session_id == f"wf-T-495-{fake_key}"
    assert captured["session_id"] == f"wf-T-495-{fake_key}"
    assert captured["registry_key"] == fake_key
    assert new_key_called["n"] == 0  # env 우선이므로 new_registry_key 미호출


def test_init_step_falls_back_to_new_registry_key_when_env_missing(monkeypatch, tmp_path):
    """V2_REGISTRY_KEY env 미설정 시 new_registry_key() 정상 호출."""
    monkeypatch.delenv("V2_REGISTRY_KEY", raising=False)

    captured = {}

    def fake_kanban_show(ticket_no):
        return (
            "## T-495: 샘플\n\n### Metadata\n"
            "- Number: T-495\n- Title: dummy\n- Status: Open\n- Command: research\n"
        )

    monkeypatch.setattr(init_mod, "kanban_show", fake_kanban_show)
    monkeypatch.setattr(init_mod, "kanban_move", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "session_create", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "step_start", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "step_end", lambda *a, **k: None)
    monkeypatch.setattr(
        init_mod, "make_work_dir",
        lambda rk: ((tmp_path / "runs" / rk / "work").mkdir(parents=True, exist_ok=True)
                    or (tmp_path / "runs" / rk)),
    )
    monkeypatch.setattr(init_mod, "write_status", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "write_context", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "update_step", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "append_log", lambda *a, **k: None)

    monkeypatch.setattr(init_mod, "new_registry_key", lambda: "fresh-fallback-key")

    ctx = init_mod.init_step("T-495")

    assert ctx.registry_key == "fresh-fallback-key"
    assert ctx.wf_session_id == "wf-T-495-fresh-fallback-key"
