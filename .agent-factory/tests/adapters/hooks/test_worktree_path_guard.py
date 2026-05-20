"""unit test worktree_path_guard.py (blocks T-408 regression)

Guard operation is verified through 12 scenarios:
  TC1-6: Write/Edit/MultiEdit/NotebookEdit branch — blocks direct hit to main repo,
         Pass work tree/output path
  TC7-9: Bash branch — sed -i, cross-tree cp, output path cp
  TC10: research command — implement guard passed as non-target
  TC11: HOOK_WORKTREE_PATH_GUARD=false — Guard disabled
  TC12: WORKFLOW_COMMAND not set + WORKFLOW_WORKTREE_PATH only — Assume implement deny
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
GUARD_SCRIPT = REPO_ROOT / ".agent-factory" / "engine" / "guards" / "worktree_path_guard.py"
# .agent-factory/engine/guards/worktree_path_guard.py → <repo_root>
ACTUAL_MAIN_ROOT = str(GUARD_SCRIPT.parent.parent.parent.parent)


def _run_guard(
    tool_name: str,
    tool_input: dict,
    env_overrides: dict | None = None,
) -> tuple[str, int]:
    """Executes the guard script as subprocess and returns (stdout, returncode)."""
    payload = {"tool_name": tool_name, "tool_input": tool_input}
    base_env = {
        **os.environ,
        "_WF_SESSION_TYPE": "workflow",
        "WORKFLOW_COMMAND": "implement",
        "HOOK_WORKTREE_PATH_GUARD": "true",
        # Disk fallback avoidance — Decision only on environment variable priority branches
        "WORKFLOW_WORK_DIR": "",
    }
    if env_overrides:
        for k, v in env_overrides.items():
            if v is None:
                base_env.pop(k, None)
            else:
                base_env[k] = v
    proc = subprocess.run(
        [sys.executable, str(GUARD_SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=base_env,
    )
    return proc.stdout, proc.returncode


def _is_deny(stdout: str) -> bool:
    """Check whether deny JSON is output to stdout."""
    if not stdout.strip():
        return False
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return False
    hook_output = result.get("hookSpecificOutput", {})
    return hook_output.get("permissionDecision") == "deny"


class TestWorktreePathGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp_main = tempfile.mkdtemp(prefix="tmp_main_")
        cls.tmp_wt = tempfile.mkdtemp(prefix="tmp_wt_")

    # ── Write/Edit/MultiEdit/NotebookEdit branch ─────────────────────────────

    def test_01_main_source_absolute_deny(self) -> None:
        """Block main repo absolute path (board/server)."""
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": f"{self.tmp_main}/.agent-factory/board/server/app.py",
                "content": "",
            },
            env_overrides={"WORKFLOW_WORKTREE_PATH": self.tmp_wt},
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_02_worktree_absolute_allow(self) -> None:
        """Passing absolute path in work tree."""
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": f"{self.tmp_wt}/.agent-factory/board/server/app.py",
                "content": "",
            },
            env_overrides={"WORKFLOW_WORKTREE_PATH": self.tmp_wt},
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    def test_03_main_artifact_runs_allow(self) -> None:
        """Passing main output .agent-factory/runs/."""
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": (
                    f"{self.tmp_main}/.agent-factory/runs/20260507-105931/plan.md"
                ),
                "content": "",
            },
            env_overrides={"WORKFLOW_WORKTREE_PATH": self.tmp_wt},
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    def test_04_main_relative_deny(self) -> None:
        """Block the main repo relative path (cwd=main)."""
        stdout, _ = _run_guard(
            "Edit",
            {"file_path": "board/server/app.py"},
            env_overrides={"WORKFLOW_WORKTREE_PATH": self.tmp_wt},
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_05_multiedit_main_deny(self) -> None:
        """Block MultiEdit main absolute path."""
        stdout, _ = _run_guard(
            "MultiEdit",
            {"file_path": f"{self.tmp_main}/.agent-factory/engine/foo.py"},
            env_overrides={"WORKFLOW_WORKTREE_PATH": self.tmp_wt},
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_06_notebookedit_main_deny(self) -> None:
        """NotebookEdit notebook_path key main block absolute path."""
        stdout, _ = _run_guard(
            "NotebookEdit",
            {"notebook_path": f"{self.tmp_main}/foo.ipynb"},
            env_overrides={"WORKFLOW_WORKTREE_PATH": self.tmp_wt},
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    # ── Bash branch ────────────────────────────────────────────────────────────

    def test_07_bash_sed_main_deny(self) -> None:
        """Bash sed -i blocks main repo path."""
        stdout, _ = _run_guard(
            "Bash",
            {
                "command": (
                    f"sed -i 's/a/b/' "
                    f"{ACTUAL_MAIN_ROOT}/.agent-factory/board/server/app.py"
                )
            },
            env_overrides={"WORKFLOW_WORKTREE_PATH": self.tmp_wt},
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_08_bash_cp_cross_tree_deny(self) -> None:
        """Bash cp work tree → main cross-tree blocking."""
        stdout, _ = _run_guard(
            "Bash",
            {
                "command": (
                    f"cp {self.tmp_wt}/foo.py "
                    f"{ACTUAL_MAIN_ROOT}/.agent-factory/board/server/app.py"
                )
            },
            env_overrides={"WORKFLOW_WORKTREE_PATH": self.tmp_wt},
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_09_bash_cp_to_artifact_allow(self) -> None:
        """Bash cp work tree → main output path passed."""
        stdout, _ = _run_guard(
            "Bash",
            {
                "command": (
                    f"cp {self.tmp_wt}/foo.md "
                    f"{ACTUAL_MAIN_ROOT}/.agent-factory/runs/20260507-105931/bar.md"
                )
            },
            env_overrides={"WORKFLOW_WORKTREE_PATH": self.tmp_wt},
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    # ── command / toggle branch ────────────────────────────────────────────────

    def test_10_research_session_allow(self) -> None:
        """The research command passes because it is not subject to the implement guard."""
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": f"{self.tmp_main}/.agent-factory/board/server/app.py",
                "content": "",
            },
            env_overrides={
                "WORKFLOW_COMMAND": "research",
                "WORKFLOW_WORKTREE_PATH": self.tmp_wt,
            },
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    def test_11_guard_disabled_allow(self) -> None:
        """HOOK_WORKTREE_PATH_GUARD=false Disable Face Guard — Pass."""
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": f"{self.tmp_main}/.agent-factory/board/server/app.py",
                "content": "",
            },
            env_overrides={
                "HOOK_WORKTREE_PATH_GUARD": "false",
                "WORKFLOW_WORKTREE_PATH": self.tmp_wt,
            },
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    def test_12_command_missing_worktree_path_present_deny(self) -> None:
        """WORKFLOW_COMMAND not set + WORKFLOW_WORKTREE_PATH only → Assume implement deny."""
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": f"{self.tmp_main}/.agent-factory/board/server/app.py",
                "content": "",
            },
            env_overrides={
                "WORKFLOW_COMMAND": None,
                "WORKFLOW_WORKTREE_PATH": self.tmp_wt,
            },
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
