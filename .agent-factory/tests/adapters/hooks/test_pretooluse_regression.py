"""PreToolUse Disk Regression Vehicle (T-484).

This file will block the operation of the following two cannon rules. NEWS

  1. FAQ schema (MUST)
     - Empty stdout ban on passing → permissionDecision: "allow" JSON required
     - allow JSON updatedInput field for full tool input replacement; omit without change
     - "updatedInput": {} ban

  2. `.claude/rules/workflow/general.md` §.claude/edit (MUST)'
     - Edit/Write only blocking target — Bash `sed -i`, `cat`, `grep` is not blocked
     - `.claude/` path argument Bash command should pass PreToolUse Defender

Mobile Site
    test regression reproduction — Regression scenarios set out in the user canon
    1st thread. fix pre: schema violation / blank stdout / wrong behavior field.
    after fix (current status): hookSpecificOutput.permissionDecision == "allow".

Plan route correction (T-484 plan of stale path correction):
    - Plan with `.agent-factory/engine/hooks/dispatcher/pre-tool-use.py`
      `.agent-factory/engine/workflow hooks/pretooluse task.py`
      .agent-factory/hooks/pre-tool-use.py
      T-486 Phase 6-1 (commit 9fd9050)
      pulmonary waste. This test uses the actual dispatcher path.
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


def _run_dispatcher(payload: dict, env_overrides: dict | None = None) -> tuple[str, int]:
    """execute PreToolUse Defender as subprocess (stdout, returncode) return."""
    base_env: dict[str, str] = {}
    for key in ("HOME", "PATH", "PYTHONPATH", "LANG", "LC_ALL"):
        if key in os.environ:
            base_env[key] = os.environ[key]
    base_env["CLAUDE_PROJECT_DIR"] = str(REPO_ROOT)

    if env_overrides:
        for k, v in env_overrides.items():
            if v is None:
                base_env.pop(k, None)
            else:
                base_env[k] = v

    proc = subprocess.run(
        [sys.executable, "-u", str(DISPATCHER)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=base_env,
        timeout=15,
    )
    return proc.stdout, proc.returncode


def _parse_hook_output(stdout: str) -> dict:
    """parsing hookSpecificOutput JSON in stdout."""
    data = json.loads(stdout.strip())
    return data.get("hookSpecificOutput", {})


class TestPreToolUseRegression(unittest.TestCase):
    """Reproduction vehicle — T-484 plan of core scenarios."""

    def test_dispatcher_path_exists(self) -> None:
        """The actual dispatcher file exists in the path known."""
        self.assertTrue(DISPATCHER.exists(), f"dispatcher missing: {DISPATCHER}")

    def test_regression_reproduction(self) -> None:
        """plan's regression scenario — sed -i by .claude/ path argument Bash command.

        Example (fix = current GREEN):
          - stdout not empty (schema rule §1: empty stdout ban)
          - hookSpecificOutput.hookEventName == "PreToolUse"
          - hookSpecificOutput.permissionDecision == "allow"
          - updatedInput key absence (schema rule §1: omitted without change)
          - returncode 0
        """
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "sed -i 's/A/B/g' .claude/rules/workflow/general.md",
            },
        }
        stdout, rc = _run_dispatcher(payload)

        # Empty stdout ban (canon §1)
        self.assertTrue(
            stdout.strip(),
            "PreToolUse Defender returned empty stdout — violation of schema",
        )

        # JSON parse + schema verification
        hook_out = _parse_hook_output(stdout)
        self.assertEqual(hook_out.get("hookEventName"), "PreToolUse")
        self.assertEqual(
            hook_out.get("permissionDecision"),
            "allow",
            f"unexpected decision: {hook_out!r}",
        )

        # updatedInput absence (canon §1: omitted without changing)
        self.assertNotIn(
            "updatedInput",
            hook_out,
            "Upon passing, the updatedInput must be omitted — schema violation risk",
        )

        # returncode 0
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
