"""T-509 — init.py work_dir 위치 회귀 정정 단위 테스트.

회귀 origin: a473334 (PROJECT_ROOT 를 git common-dir 기준으로 결정) 에서
`_common.py` 의 PROJECT_ROOT / RUNS_DIR 만 정정되고 `steps/init.py:104-108` 의
`if worktree_path is not None: work_dir = worktree_path / .claude-organic / runs / ...`
분기는 정정 누락 — 워크트리에서 호출 시 work_dir 가 worktree 안쪽에 박혀
finalization R-EXIST / history sync / SSE 인덱스가 산출물을 못 찾는 회귀.

본 fix 후의 불변식:
  1. make_work_dir(registry_key) 결과 = <PROJECT_ROOT>/.claude-organic/runs/<key>
     (PROJECT_ROOT 는 git common-dir 의 부모 = 메인 워크트리 root)
  2. init_step 결과 ctx.work_dir 는 worktree_path 유무와 무관하게 1번과 동일.
  3. ctx.worktree_path 는 별개 의미로 유지 (auto_commit / verify_code 가 사용).

driver self-reference 회피: driver 가 driver 검증 트리거하면 무한 재귀.
make_work_dir / init_step 결정 로직만 단위 테스트로 격리한다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from engine.v2._common import PROJECT_ROOT, RUNS_DIR, make_work_dir
from engine.v2.steps import init as init_mod


def _kanban_dump(command: str = "implement", title: str = "T-509 worktree fix") -> str:
    return (
        f"## T-509: {title}\n\n### Metadata\n"
        f"- Number: T-509\n- Title: {title}\n- Status: Open\n- Command: {command}\n"
    )


def test_project_root_resolves_to_main_git_root() -> None:
    """PROJECT_ROOT 는 git common-dir 의 부모 (= 메인 워크트리 root) 여야 한다.

    워크트리에서 본 테스트가 실행돼도 PROJECT_ROOT 는 메인 측을 가리킨다.
    a473334 commit 의 핵심 불변식 — 본 테스트가 깨지면 회귀 origin 자체가 회귀.
    """
    expected = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=str(Path(__file__).resolve().parent),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    expected_path = Path(expected)
    if not expected_path.is_absolute():
        expected_path = (Path(__file__).resolve().parent / expected_path).resolve()
    assert PROJECT_ROOT == expected_path.parent
    assert RUNS_DIR == PROJECT_ROOT / ".claude-organic" / "runs"


def test_make_work_dir_uses_project_root_main_side() -> None:
    """make_work_dir 는 항상 PROJECT_ROOT 기준 경로 반환 — worktree 안쪽 가능성 0."""
    key = "test-T-509-make-work-dir"
    work_dir = make_work_dir(key)
    try:
        assert work_dir == RUNS_DIR / key
        assert work_dir.parent == RUNS_DIR
        assert (work_dir / "work").is_dir()
        # 메인 측 검증: PROJECT_ROOT 가 worktrees/<...> 안쪽이면 안 됨
        assert "/worktrees/" not in str(work_dir), (
            f"work_dir leaked into worktree: {work_dir}"
        )
    finally:
        # cleanup: 본 테스트가 메인 측 runs/ 에 잔재를 남기지 않도록
        if (work_dir / "work").is_dir():
            (work_dir / "work").rmdir()
        if work_dir.is_dir():
            work_dir.rmdir()


def test_init_step_work_dir_ignores_worktree_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """본 fix 의 핵심 — _maybe_create_worktree 가 worktree_path 를 반환해도
    work_dir 는 make_work_dir(registry_key) 결과 = 메인 측 경로여야 한다.

    Red phase (fix 적용 전): init.py:104-108 의 if worktree_path 분기로 인해
    work_dir = worktree_path / .claude-organic / runs / <key> 가 되어 본 assert 실패.
    Green phase (fix 적용 후): work_dir = make_work_dir(<key>) = RUNS_DIR / <key>.
    """
    fake_key = "20260519-T509-WORK"
    fake_worktree = tmp_path / "worktrees" / "feat-T-509-test"
    fake_worktree.mkdir(parents=True, exist_ok=True)
    expected_work_dir = tmp_path / "main-runs" / fake_key

    monkeypatch.delenv("V2_REGISTRY_KEY", raising=False)
    monkeypatch.setattr(init_mod, "kanban_show", lambda t: _kanban_dump("implement"))
    monkeypatch.setattr(init_mod, "kanban_move", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "session_create", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "step_start", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "step_end", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "update_step", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "append_log", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "write_status", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "write_context", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "write_metadata", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "new_registry_key", lambda: fake_key)

    monkeypatch.setattr(
        init_mod,
        "_maybe_create_worktree",
        lambda tn, ti, cm: ("feat/T-509-test", fake_worktree),
    )

    def fake_make_work_dir(rk: str) -> Path:
        d = tmp_path / "main-runs" / rk
        (d / "work").mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(init_mod, "make_work_dir", fake_make_work_dir)
    # user_prompt.txt 가 work_dir 에 쓰여야 하므로 fake_make_work_dir 의 디렉터리는
    # 실제로 존재. user_prompt_path() 는 work_dir/user_prompt.txt — 부모 디렉터리
    # 이미 mkdir 된 상태이므로 write_text 가능.

    ctx = init_mod.init_step("T-509")

    # 핵심 assertion: worktree_path 가 fake_worktree 인데도 work_dir 는 메인 측
    assert ctx.work_dir == expected_work_dir, (
        f"work_dir leaked into worktree:\n"
        f"  expected: {expected_work_dir}\n"
        f"  got:      {ctx.work_dir}\n"
        f"  worktree_path: {ctx.worktree_path}"
    )
    # worktree_path 는 보존 — auto_commit / verify_code 가 사용
    assert ctx.worktree_path == fake_worktree
    assert ctx.feature_branch == "feat/T-509-test"
    # 산출물 디렉터리 메인 측에 실제로 mkdir 됐는지
    assert (expected_work_dir / "work").is_dir()


def test_init_step_research_command_no_worktree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """research command — worktree 0건. 본 fix 와 무관한 경로 보존 검증."""
    fake_key = "20260519-T509-RESEARCH"
    monkeypatch.delenv("V2_REGISTRY_KEY", raising=False)
    monkeypatch.setattr(init_mod, "kanban_show", lambda t: _kanban_dump("research"))
    monkeypatch.setattr(init_mod, "kanban_move", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "session_create", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "step_start", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "step_end", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "update_step", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "append_log", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "write_status", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "write_context", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "write_metadata", lambda *a, **k: None)
    monkeypatch.setattr(init_mod, "new_registry_key", lambda: fake_key)

    def fake_make_work_dir(rk: str) -> Path:
        d = tmp_path / "main-runs" / rk
        (d / "work").mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(init_mod, "make_work_dir", fake_make_work_dir)

    ctx = init_mod.init_step("T-509")

    assert ctx.worktree_path is None
    assert ctx.feature_branch is None
    assert ctx.work_dir == tmp_path / "main-runs" / fake_key
    assert ctx.command == "research"
