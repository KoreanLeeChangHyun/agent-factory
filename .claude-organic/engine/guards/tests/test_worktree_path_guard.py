"""worktree_path_guard.py 단위 테스트 (T-408 회귀 차단)

12개 시나리오를 통해 가드 동작을 검증한다:
  TC1-6: Write/Edit/MultiEdit/NotebookEdit 분기 — 메인 리포 직격 차단,
         워크트리 / 산출물 경로 통과
  TC7-9: Bash 분기 — sed -i, cross-tree cp, 산출물 경로 cp
  TC10:  research command — implement 가드 비대상으로 통과
  TC11:  HOOK_WORKTREE_PATH_GUARD=false — 가드 비활성
  TC12:  WORKFLOW_COMMAND 미설정 + WORKFLOW_WORKTREE_PATH 만 — implement 가정 deny
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD_SCRIPT = Path(__file__).resolve().parent.parent / "worktree_path_guard.py"
# .claude-organic/engine/guards/worktree_path_guard.py → <repo_root>
ACTUAL_MAIN_ROOT = str(GUARD_SCRIPT.parent.parent.parent.parent)


def _run_guard(
    tool_name: str,
    tool_input: dict,
    env_overrides: dict | None = None,
) -> tuple[str, int]:
    """가드 스크립트를 subprocess 로 실행하고 (stdout, returncode) 반환."""
    payload = {"tool_name": tool_name, "tool_input": tool_input}
    base_env = {
        **os.environ,
        "_WF_SESSION_TYPE": "workflow",
        "WORKFLOW_COMMAND": "implement",
        "HOOK_WORKTREE_PATH_GUARD": "true",
        # 디스크 fallback 회피 — 환경변수 우선 분기로만 결정
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
    """stdout 에 deny JSON 이 출력됐는지 확인."""
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

    # ── Write/Edit/MultiEdit/NotebookEdit 분기 ────────────────────────────

    def test_01_main_source_absolute_deny(self) -> None:
        """메인 리포 절대 경로(board/server) 차단."""
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": f"{self.tmp_main}/.claude-organic/board/server/app.py",
                "content": "",
            },
            env_overrides={"WORKFLOW_WORKTREE_PATH": self.tmp_wt},
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_02_worktree_absolute_allow(self) -> None:
        """워크트리 내 절대 경로 통과."""
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": f"{self.tmp_wt}/.claude-organic/board/server/app.py",
                "content": "",
            },
            env_overrides={"WORKFLOW_WORKTREE_PATH": self.tmp_wt},
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    def test_03_main_artifact_runs_allow(self) -> None:
        """메인 산출물 .claude-organic/runs/ 통과."""
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": (
                    f"{self.tmp_main}/.claude-organic/runs/20260507-105931/plan.md"
                ),
                "content": "",
            },
            env_overrides={"WORKFLOW_WORKTREE_PATH": self.tmp_wt},
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    def test_04_main_relative_deny(self) -> None:
        """메인 리포 상대 경로 (cwd=메인) 차단."""
        stdout, _ = _run_guard(
            "Edit",
            {"file_path": "board/server/app.py"},
            env_overrides={"WORKFLOW_WORKTREE_PATH": self.tmp_wt},
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_05_multiedit_main_deny(self) -> None:
        """MultiEdit 메인 절대 경로 차단."""
        stdout, _ = _run_guard(
            "MultiEdit",
            {"file_path": f"{self.tmp_main}/.claude-organic/engine/foo.py"},
            env_overrides={"WORKFLOW_WORKTREE_PATH": self.tmp_wt},
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_06_notebookedit_main_deny(self) -> None:
        """NotebookEdit notebook_path 키 메인 절대 경로 차단."""
        stdout, _ = _run_guard(
            "NotebookEdit",
            {"notebook_path": f"{self.tmp_main}/foo.ipynb"},
            env_overrides={"WORKFLOW_WORKTREE_PATH": self.tmp_wt},
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    # ── Bash 분기 ─────────────────────────────────────────────────────────

    def test_07_bash_sed_main_deny(self) -> None:
        """Bash sed -i 메인 리포 경로 차단."""
        stdout, _ = _run_guard(
            "Bash",
            {
                "command": (
                    f"sed -i 's/a/b/' "
                    f"{ACTUAL_MAIN_ROOT}/.claude-organic/board/server/app.py"
                )
            },
            env_overrides={"WORKFLOW_WORKTREE_PATH": self.tmp_wt},
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_08_bash_cp_cross_tree_deny(self) -> None:
        """Bash cp 워크트리→메인 cross-tree 차단."""
        stdout, _ = _run_guard(
            "Bash",
            {
                "command": (
                    f"cp {self.tmp_wt}/foo.py "
                    f"{ACTUAL_MAIN_ROOT}/.claude-organic/board/server/app.py"
                )
            },
            env_overrides={"WORKFLOW_WORKTREE_PATH": self.tmp_wt},
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_09_bash_cp_to_artifact_allow(self) -> None:
        """Bash cp 워크트리→메인 산출물 경로 통과."""
        stdout, _ = _run_guard(
            "Bash",
            {
                "command": (
                    f"cp {self.tmp_wt}/foo.md "
                    f"{ACTUAL_MAIN_ROOT}/.claude-organic/runs/20260507-105931/bar.md"
                )
            },
            env_overrides={"WORKFLOW_WORKTREE_PATH": self.tmp_wt},
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    # ── command / 토글 분기 ──────────────────────────────────────────────

    def test_10_research_session_allow(self) -> None:
        """research command 는 implement 가드 비대상이라 통과."""
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": f"{self.tmp_main}/.claude-organic/board/server/app.py",
                "content": "",
            },
            env_overrides={
                "WORKFLOW_COMMAND": "research",
                "WORKFLOW_WORKTREE_PATH": self.tmp_wt,
            },
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    def test_11_guard_disabled_allow(self) -> None:
        """HOOK_WORKTREE_PATH_GUARD=false 면 가드 비활성 — 통과."""
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": f"{self.tmp_main}/.claude-organic/board/server/app.py",
                "content": "",
            },
            env_overrides={
                "HOOK_WORKTREE_PATH_GUARD": "false",
                "WORKFLOW_WORKTREE_PATH": self.tmp_wt,
            },
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    def test_12_command_missing_worktree_path_present_deny(self) -> None:
        """WORKFLOW_COMMAND 미설정 + WORKFLOW_WORKTREE_PATH 만 → implement 가정 deny."""
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": f"{self.tmp_main}/.claude-organic/board/server/app.py",
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
