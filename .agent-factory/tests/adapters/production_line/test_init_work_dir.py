"""WR-509 — init.py work dir location regression set test.

Regression origin: in a473334 (PROJECT ROOT git common-dir)
` common.py` of PROJECT ROOT / RUNS DIR Only corrected and `steps/init.py:104-108`
`if worktree_path is not None: work_dir = worktree_path / .agent-factory / runs / ...`
Branches are missing — work dir is stuck inside worktree when calling on worktree
the finalization R-EXIST / history sync / SSE index to find the output.

Unvariable after this fix:
  1. FAQ make work dir(registry key) result = <PROJECT ROOT>/.agent-factory/runs/<key>
     git common-dir
  2. init step result ctx.work dir is the same as worktree path liberty and unparalleled one.
  3. FAQs ctx.worktree path maintains a distinct meaning (auto commit / verification code is used).

driver self-reference evacuation: infinite recurring if driver is validated.
make work dir / init step crystal logic only insulates unit test.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from engine.apps.production_line._common import PROJECT_ROOT, RUNS_DIR, make_work_dir
from engine.apps.production_line.stations import init as init_mod


def _conveyor_dump(command: str = "implement", title: str = "WR-509 worktree fix") -> str:
    return (
        f"## WR-509: {title}\n\n### Metadata\n"
        f"- Number: WR-509\n- Title: {title}\n- Status: Open\n- Command: {command}\n"
    )


def test_project_root_resolves_to_main_git_root() -> None:
    """git common-dir

    Project ROOT is the main side.
    a473334 Commit's core unchanged — the regression origin itself when the test is broken.
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
    assert RUNS_DIR == PROJECT_ROOT / ".agent-factory" / "runs"


def test_make_work_dir_uses_project_root_main_side() -> None:
    """make work dir always returns the project ROOT standard path — the possibility inside worktree 0."""
    key = "test-WR-509-make-work-dir"
    work_dir = make_work_dir(key)
    try:
        assert work_dir == RUNS_DIR / key
        assert work_dir.parent == RUNS_DIR
        assert (work_dir / "work").is_dir()
        # Main side verification: PROJECT ROOT is not inside worktrees/<...>
        assert "/worktrees/" not in str(work_dir), (
            f"work_dir leaked into worktree: {work_dir}"
        )
    finally:
        # cleanup: This test does not leave a residual on the main side runs/
        if (work_dir / "work").is_dir():
            (work_dir / "work").rmdir()
        if work_dir.is_dir():
            work_dir.rmdir()


def test_init_step_work_dir_ignores_worktree_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """maybe create worktree returns worktree path
    make work dir(registry key)

    Red phase (fix before application): init.py:104-108 if worktree path branch
    work dir = worktree path / .agent-factory / run / <key>
    RUNS DIR / <key>
    """
    fake_key = "20260519-WR509-WORK"
    fake_worktree = tmp_path / "worktrees" / "feat-WR-509-test"
    fake_worktree.mkdir(parents=True, exist_ok=True)
    expected_work_dir = tmp_path / "main-runs" / fake_key

    monkeypatch.delenv("V2_REGISTRY_KEY", raising=False)
    monkeypatch.setattr(init_mod, "conveyor_show", lambda t: _conveyor_dump("implement"))
    monkeypatch.setattr(init_mod, "conveyor_move", lambda *a, **k: None)
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
        lambda tn, ti, cm: ("feat/WR-509-test", fake_worktree),
    )

    def fake_make_work_dir(rk: str) -> Path:
        d = tmp_path / "main-runs" / rk
        (d / "work").mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(init_mod, "make_work_dir", fake_make_work_dir)
    # user prompt.txt is a directory of fake make work dir
    # Indeed. user prompt path() work dir/user prompt.txt — parent directory
    # You can write text because it is already mkdir.

    ctx = init_mod.init_step("WR-509")

    # key assertion: worktree path is fake worktree but also work dir is the main side
    assert ctx.work_dir == expected_work_dir, (
        f"work_dir leaked into worktree:\n"
        f"  expected: {expected_work_dir}\n"
        f"  got:      {ctx.work_dir}\n"
        f"  worktree_path: {ctx.worktree_path}"
    )
    # worktree path is preserved — using auto commit / verification code
    assert ctx.worktree_path == fake_worktree
    assert ctx.feature_branch == "feat/WR-509-test"
    # The output directory is actually mkdir on the main side
    assert (expected_work_dir / "work").is_dir()


def test_init_step_research_command_no_worktree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Research command — worktree 0. This fix and unparalleled path conservation verification."""
    fake_key = "20260519-WR509-RESEARCH"
    monkeypatch.delenv("V2_REGISTRY_KEY", raising=False)
    monkeypatch.setattr(init_mod, "conveyor_show", lambda t: _conveyor_dump("research"))
    monkeypatch.setattr(init_mod, "conveyor_move", lambda *a, **k: None)
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

    ctx = init_mod.init_step("WR-509")

    assert ctx.worktree_path is None
    assert ctx.feature_branch is None
    assert ctx.work_dir == tmp_path / "main-runs" / fake_key
    assert ctx.command == "research"
