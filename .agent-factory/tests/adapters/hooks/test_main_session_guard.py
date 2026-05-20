"""main_session_guard.py unit test (blocks T-422 memory whitelist regression)

Guard operation is verified through 12 scenarios:
  TC1-5: allow — memory directory Write/Edit/Bash cp + prompt body text substring
  TC6: allow — 0 workflow session branch regressions observed
  TC7-11: deny — Actual code modification (engine/board/sed/cp) + conservative blocking of mixed memory + code
  TC12: allow — HOOK_MAIN_SESSION_GUARD=false toggle validation
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
GUARD_SCRIPT = REPO_ROOT / ".agent-factory" / "engine" / "guards" / "main_session_guard.py"


def _run_guard(
    tool_name: str,
    tool_input: dict,
    env_overrides: dict | None = None,
) -> tuple[str, int]:
    """Executes the guard script as subprocess and returns (stdout, returncode).

    Default environment:
      - _WF_SESSION_TYPE not set → unknown branch (main session simulation)
      - HOOK_MAIN_SESSION_GUARD=true
      - TMUX_PANE not set → No TMUX fallback
      - WORKFLOW_WORKTREE_PATH, WORKFLOW_WORK_DIR not set → worktree_path_guard
        fallback interference avoidance
    """
    payload = {"tool_name": tool_name, "tool_input": tool_input}
    # Minimum environment configuration: HOME, PATH, PYTHONPATH inheritance + guard toggle ON
    # Remove explicit TMUX_PANE/TMUX → use unknown branch without tmux fallback
    base_env: dict[str, str] = {}

    # Inherit only the minimum required keys from the parent environment
    for key in ("HOME", "PATH", "PYTHONPATH", "LANG", "LC_ALL"):
        if key in os.environ:
            base_env[key] = os.environ[key]

    # Guard Enabled Default
    base_env["HOOK_MAIN_SESSION_GUARD"] = "true"

    # Remove explicit _WF_SESSION_TYPE → get_session_type() = unknown (main simulation)
    # (Except explicitly so that it is not inherited by default if _WF_SESSION_TYPE=workflow exists in the parent environment)

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


class TestMainSessionGuard(unittest.TestCase):
    """main_session_guard.py regression testing.

    - 6 types of allow cases: Memory directory Write/Edit/Bash + prompt text + workflow session
    - 6 types of deny cases: actual code modification (engine/board/sed/cp) + memory + code mixing + toggle
    """

    # ── allow case ─────────────────────────────────────────────────────────────

    def test_01_memory_write_allow(self) -> None:
        """Write memory directory subpath with Write tool → Pass."""
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": "~/.claude/projects/-home-deus-claude/memory/feedback/foo.md",
                "content": "test",
            },
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    def test_02_memory_edit_allow(self) -> None:
        """Modify the absolute path under the memory directory using the Edit tool → Pass."""
        home = os.path.expanduser("~")
        abs_path = f"{home}/.claude/projects/-home-deus-claude/memory/MEMORY.md"
        stdout, _ = _run_guard(
            "Edit",
            {
                "file_path": abs_path,
                "old_string": "old",
                "new_string": "new",
            },
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    def test_03_memory_bash_cp_allow(self) -> None:
        """Copy only to the memory directory using the Bash cp command → Pass."""
        stdout, _ = _run_guard(
            "Bash",
            {
                "command": (
                    "cp /tmp/foo.md ~/.claude/projects/-home-deus-claude/memory/bar.md"
                )
            },
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    def test_04_prompt_text_substring_allow(self) -> None:
        """Memory path text in quotes of Bash flow-kanban update-prompt → Pass.

        Verify that _strip_quoted_args is not subject to pattern matching by leaving the inside of the quotation marks empty.
        """
        stdout, _ = _run_guard(
            "Bash",
            {
                "command": (
                    'flow-kanban update-prompt T-422 --target '
                    '"Edit to: ~/.claude/projects/-home-deus-claude/memory/feedback/"'
                )
            },
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    def test_05_prompt_substring_with_code_path_in_quote_allow(self) -> None:
        """Bash flow-kanban code path substring in quotes → Pass.

        Verifies that the code path is in quotes and is removed with _strip_quoted_args.
        """
        stdout, _ = _run_guard(
            "Bash",
            {
                "command": (
                    "flow-kanban update-prompt T-422 "
                    '--constraints "Modify engine/guards/main_session_guard.py"'
                )
            },
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    def test_06_workflow_session_allow(self) -> None:
        """_WF_SESSION_TYPE=Code modification command in workflow environment → Pass.

        0 existing workflow session branch regressions confirmed.
        """
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": ".agent-factory/engine/guards/main_session_guard.py",
                "content": "# test",
            },
            env_overrides={"_WF_SESSION_TYPE": "workflow"},
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    # ── deny case ───────────────────────────────────────────────────────────────

    def test_07_main_session_write_engine_deny(self) -> None:
        """Modifying the engine directory using the Write tool in the main session → Block."""
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": ".agent-factory/engine/guards/main_session_guard.py",
                "content": "# test",
            },
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_08_main_session_edit_board_deny(self) -> None:
        """Modifying the board directory with the Edit tool in the main session → Block."""
        stdout, _ = _run_guard(
            "Edit",
            {
                "file_path": ".agent-factory/board/server/app.py",
                "old_string": "old",
                "new_string": "new",
            },
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_09_main_session_bash_sed_deny(self) -> None:
        """Bash sed -i command in main session → Block."""
        stdout, _ = _run_guard(
            "Bash",
            {"command": "sed -i 's/a/b/' engine/guards/main_session_guard.py"},
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_10_main_session_bash_cp_to_engine_deny(self) -> None:
        """Copy files to the engine directory using Bash cp in the main session → Block."""
        stdout, _ = _run_guard(
            "Bash",
            {"command": "cp /tmp/foo.py .agent-factory/engine/foo.py"},
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_11_memory_and_engine_mixed_deny(self) -> None:
        """Bash cp memory→engine mixed commands→conservative blocking.

        Preserve blocking if the target is a code path even if the memory path is the source.
        """
        stdout, _ = _run_guard(
            "Bash",
            {
                "command": (
                    "cp ~/.claude/projects/-home-deus-claude/memory/foo.md "
                    ".agent-factory/engine/bar.md"
                )
            },
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_12_guard_disabled_allow(self) -> None:
        """HOOK_MAIN_SESSION_GUARD=false Modify code in environment → Pass with toggle."""
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": ".agent-factory/engine/guards/main_session_guard.py",
                "content": "# test",
            },
            env_overrides={"HOOK_MAIN_SESSION_GUARD": "false"},
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
