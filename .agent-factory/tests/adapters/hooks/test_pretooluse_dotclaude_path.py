"""PreToolUse `.claude/` path argument Bash command unified regression matrix (T-484 P3).

Stuffing the passing rules of `general.md` §".claude/ (MUST)" into 4 scenarios:

| # | Scenario | Example | expectations |
|---|---------|------|------|
| 1 | sed -i returns .claude/ path argument | `sed -i 's/X/Y/g' .claude/rules/...` | allow |
| 2 | Reading .claude/ files with cat | `cat .claude/settings.json` | allow |
| 3 | Search the .claude/ tree with grep -r | `grep -r "PreToolUse" .claude/` | allow |
| 4 | mixed (.claude/ + .agent-factory/) | `sed -i ... .claude/foo .agent-factory/bar` | allow |

Canon decision (`plan.md` §decision table): Bash `.claude/` path argument = **Pass (allow JSON)**.
Only Edit/Write is blocked by Claude Code hardcoding protection, Bash indirect tools are passed.
The flow-claude-edit route is a formal route and is compatible with the main guard flow.

This vehicle is a forward regression blocking network that extends the single scenario vehicle of P1 to 4 scenarios.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DISPATCHER = REPO_ROOT / ".agent-factory" / "hooks" / "pre-tool-use.py"


def _run_dispatcher(payload: dict) -> tuple[str, int]:
    base_env: dict[str, str] = {}
    for key in ("HOME", "PATH", "PYTHONPATH", "LANG", "LC_ALL"):
        if key in os.environ:
            base_env[key] = os.environ[key]
    base_env["CLAUDE_PROJECT_DIR"] = str(REPO_ROOT)
    proc = subprocess.run(
        [sys.executable, "-u", str(DISPATCHER)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=base_env,
        timeout=15,
    )
    return proc.stdout, proc.returncode


def _assert_allow(test: unittest.TestCase, stdout: str, rc: int) -> None:
    """allow schema + returncode matching verification."""
    test.assertEqual(rc, 0)
    test.assertTrue(stdout.strip(), "Empty stdout — violation of canon §R1")
    data = json.loads(stdout.strip())
    hook_out = data.get("hookSpecificOutput", {})
    test.assertEqual(hook_out.get("hookEventName"), "PreToolUse")
    test.assertEqual(
        hook_out.get("permissionDecision"),
        "allow",
        f"non-allow decision: {hook_out!r}",
    )
    test.assertNotIn("updatedInput", hook_out)


class TestDotClaudePathScenarios(unittest.TestCase):
    """plan §P3 4 Scenario Matrix."""

    def test_scenario_1_sed_inline_dotclaude(self) -> None:
        """Edit .claude/rules/workflow/general.md with sed -i → allow."""
        stdout, rc = _run_dispatcher({
            "tool_name": "Bash",
            "tool_input": {
                "command": "sed -i 's/X/Y/g' .claude/rules/workflow/general.md",
            },
        })
        _assert_allow(self, stdout, rc)

    def test_scenario_2_cat_dotclaude_settings(self) -> None:
        """cat .claude/settings.json → allow (read-only)."""
        stdout, rc = _run_dispatcher({
            "tool_name": "Bash",
            "tool_input": {"command": "cat .claude/settings.json"},
        })
        _assert_allow(self, stdout, rc)

    def test_scenario_3_grep_dotclaude_tree(self) -> None:
        """grep -r "PreToolUse" .claude/ → allow."""
        stdout, rc = _run_dispatcher({
            "tool_name": "Bash",
            "tool_input": {"command": 'grep -r "PreToolUse" .claude/'},
        })
        _assert_allow(self, stdout, rc)

    def test_scenario_4_sed_mixed_paths(self) -> None:
        """Simultaneous modification of .claude/ + .agent-factory/ with sed -i → allow."""
        stdout, rc = _run_dispatcher({
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    "sed -i 's/X/Y/g' .claude/rules/foo.md "
                    ".agent-factory/test.md"
                ),
            },
        })
        _assert_allow(self, stdout, rc)


class TestFlowClaudeEditCoexistence(unittest.TestCase):
    """flow-claude-edit Movement line (user canonical path) regression safety net.

    The official path for editing `.claude/` is `flow-claude-edit open/save`,
    This Bash passing rule does not interfere with user movement (separate traffic).
    """

    def test_flow_claude_edit_open_passes(self) -> None:
        """`flow-claude-edit open rules/workflow/general.md` Bash → allow."""
        stdout, rc = _run_dispatcher({
            "tool_name": "Bash",
            "tool_input": {
                "command": ".agent-factory/bin/flow-claude-edit open rules/workflow/general.md",
            },
        })
        _assert_allow(self, stdout, rc)

    def test_flow_claude_edit_save_passes(self) -> None:
        """`flow-claude-edit save rules/workflow/general.md` Bash → allow."""
        stdout, rc = _run_dispatcher({
            "tool_name": "Bash",
            "tool_input": {
                "command": ".agent-factory/bin/flow-claude-edit save rules/workflow/general.md",
            },
        })
        _assert_allow(self, stdout, rc)


if __name__ == "__main__":
    unittest.main()
