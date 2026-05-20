"""T-513 P1 — driver fail_step 실측 (SPEC.md §12.4 정합).

acceptance_criteria #4 — "driver fail_step → kanban Open 회귀 + worktree 보존
동작 실측". SPEC.md §12.4 + feedback_no_speculative_guards_2026-05-08 룰에 따라
실제 채택된 정책은 "kanban 자동 회귀 X" (auto regression OFF). 본 테스트는 그
정책을 박제한다:

  - status.json workflow_phase → FAILED 도달
  - failure.md 작성
  - metadata.json failure 필드 채움
  - kanban_move NOT 호출 (자동 회귀 X — Open 회귀는 사용자 명시 트리거만)
  - worktree 디렉터리 보존 (자동 정리 X)

production endpoint 호출 0건. 단위 테스트만 — monkeypatch + tempfile 사용.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.v2._common import WorkflowContext
from engine.v2.steps import done as done_mod


def _make_ctx(tmp_path: Path) -> WorkflowContext:
    work_dir = tmp_path / "runs" / "20260520-000000"
    (work_dir / "work").mkdir(parents=True, exist_ok=True)
    worktree_dir = tmp_path / "worktrees" / "feat-T-513-test"
    worktree_dir.mkdir(parents=True, exist_ok=True)
    sentinel = worktree_dir / "sentinel.txt"
    sentinel.write_text("preserve me", encoding="utf-8")
    return WorkflowContext(
        ticket_no="T-513",
        registry_key="20260520-000000",
        work_dir=work_dir,
        command="implement",
        mode="multi",
        current_step="WORK",
        feature_branch="feat/T-513-test",
        worktree_path=worktree_dir,
        title="fail_step 실측",
    )


def _patch_externals(monkeypatch, kanban_calls: list, finish_calls: list) -> None:
    monkeypatch.setattr(
        done_mod,
        "load_template",
        lambda name: (
            "ticket={ticket_no} key={registry_key} reason={reason} ts={ts}"
        ),
    )
    monkeypatch.setattr(
        done_mod,
        "kanban_move",
        lambda *args, **kwargs: kanban_calls.append(args) or 0,
    )
    monkeypatch.setattr(done_mod, "regression", lambda *a, **k: None)
    monkeypatch.setattr(
        done_mod,
        "workflow_finish",
        lambda *a, **k: finish_calls.append((a, k)),
    )
    # update_step 은 status.json 을 실제 쓰도록 원본 유지


def test_fail_step_status_json_workflow_phase_failed(monkeypatch, tmp_path):
    """fail_step → status.json workflow_phase=FAILED 도달."""
    ctx = _make_ctx(tmp_path)
    _patch_externals(monkeypatch, [], [])

    done_mod.fail_step(ctx, reason="WORK Step 강제 실패")

    status_path = ctx.status_json_path()
    assert status_path.exists()
    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["workflow_step"] == "FAILED"
    transitions = status["transitions"]
    assert len(transitions) >= 1
    last = transitions[-1]
    assert last["to"] == "FAILED"
    assert last["note"] == "WORK Step 강제 실패"


def test_fail_step_writes_failure_md(monkeypatch, tmp_path):
    """fail_step → failure.md 작성 + reason 본문 포함."""
    ctx = _make_ctx(tmp_path)
    _patch_externals(monkeypatch, [], [])

    done_mod.fail_step(ctx, reason="phases empty")

    failure_path = ctx.failure_md_path()
    assert failure_path.exists()
    assert "phases empty" in failure_path.read_text(encoding="utf-8")


def test_fail_step_metadata_failure_field(monkeypatch, tmp_path):
    """fail_step → metadata.json failure 필드 채움 (reason + ts)."""
    ctx = _make_ctx(tmp_path)
    _patch_externals(monkeypatch, [], [])

    done_mod.fail_step(ctx, reason="subprocess timeout")

    metadata_path = ctx.metadata_json_path()
    assert metadata_path.exists()
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["failure"] is not None
    assert payload["failure"]["reason"] == "subprocess timeout"
    assert "ts" in payload["failure"]


def test_fail_step_does_not_auto_regress_kanban(monkeypatch, tmp_path):
    """fail_step → kanban_move 호출 0건 (자동 회귀 X — SPEC.md §12.4)."""
    ctx = _make_ctx(tmp_path)
    kanban_calls: list = []
    _patch_externals(monkeypatch, kanban_calls, [])

    done_mod.fail_step(ctx, reason="auto regression off check")

    assert kanban_calls == [], (
        "fail_step 이 kanban_move 를 호출하면 안 됨 — "
        "feedback_no_speculative_guards_2026-05-08 + SPEC.md §12.4 정합"
    )


def test_fail_step_preserves_worktree(monkeypatch, tmp_path):
    """fail_step → ctx.worktree_path 디렉터리 + 산출물 보존 (자동 정리 X)."""
    ctx = _make_ctx(tmp_path)
    _patch_externals(monkeypatch, [], [])
    assert ctx.worktree_path is not None
    sentinel = ctx.worktree_path / "sentinel.txt"

    done_mod.fail_step(ctx, reason="worktree preservation check")

    assert ctx.worktree_path.exists(), (
        "fail_step 이 worktree 디렉터리를 자동 삭제하면 안 됨"
    )
    assert sentinel.exists(), "worktree 안 산출물도 보존"
    assert sentinel.read_text(encoding="utf-8") == "preserve me"


def test_fail_step_emits_workflow_finish_fail(monkeypatch, tmp_path):
    """fail_step → workflow_finish(outcome='fail', verdict='FAIL') 발화."""
    ctx = _make_ctx(tmp_path)
    finish_calls: list = []
    _patch_externals(monkeypatch, [], finish_calls)

    done_mod.fail_step(ctx, reason="finish emit check")

    assert len(finish_calls) == 1
    args, kwargs = finish_calls[0]
    assert kwargs.get("outcome") == "fail"
    assert kwargs.get("verdict") == "FAIL"
