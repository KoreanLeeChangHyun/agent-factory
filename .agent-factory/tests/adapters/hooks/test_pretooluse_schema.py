"""PreToolUse Hook Output Schema Module Test (T-484 P2).

The test of the Canon rule of `general.md` "PreToolUse Hook output schema (MUST)".

Payment Terms:
  - allow JSON key component (hookEventName / permissionDecision: "allow"
    / permissionDecisionReason)
  - allow updatedInput limit (canon: omitted without changing. {} Absolute Prohibition
  - deny JSON key (hookEventName / permissionDecision: "deny"
    / permissionDecisionReason)
  - deny time updatedInput key
  - dispatcher end fall-through does not end empty stdout
  - The dispatcher module can be imported into importlib

This test is valid for both dispatcher subprocess calls + direct branch calls.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DISPATCHER = REPO_ROOT / ".agent-factory" / "hooks" / "pre-tool-use.py"
GUARDS_DIR = REPO_ROOT / ".agent-factory" / "engine" / "guards"


def _run_dispatcher(
    payload: dict,
    env_overrides: dict | None = None,
) -> tuple[str, int]:
    """Defender subprocess execution helper."""
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


def _run_guard(
    guard_name: str,
    payload: dict,
    env_overrides: dict | None = None,
) -> tuple[str, int]:
    """Single guard subprocess execution helper."""
    base_env: dict[str, str] = {}
    for key in ("HOME", "PATH", "PYTHONPATH", "LANG", "LC_ALL"):
        if key in os.environ:
            base_env[key] = os.environ[key]
    if env_overrides:
        for k, v in env_overrides.items():
            if v is None:
                base_env.pop(k, None)
            else:
                base_env[k] = v
    proc = subprocess.run(
        [sys.executable, str(GUARDS_DIR / guard_name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=base_env,
        timeout=15,
    )
    return proc.stdout, proc.returncode


def _assert_allow_schema(test: unittest.TestCase, stdout: str) -> dict:
    """allow JSON schema correction verification + hookSpecificOutput return."""
    test.assertTrue(stdout.strip(), "stdout is empty — canon §R1 violation")
    data = json.loads(stdout.strip())
    test.assertIn("hookSpecificOutput", data)
    hook_out = data["hookSpecificOutput"]
    test.assertEqual(hook_out.get("hookEventName"), "PreToolUse")
    test.assertEqual(hook_out.get("permissionDecision"), "allow")
    # updatedInput Key Renewal Verification (canon §R2: No changes)
    test.assertNotIn(
        "updatedInput",
        hook_out,
        f"allow the updatedInput key binding required — actual:   FIELD 0  ",
    )
    return hook_out


def _assert_deny_schema(test: unittest.TestCase, stdout: str) -> dict:
    """deny JSON schema correction verification + hookSpecificOutput return."""
    test.assertTrue(stdout.strip(), "deny stdout is empty")
    data = json.loads(stdout.strip())
    test.assertIn("hookSpecificOutput", data)
    hook_out = data["hookSpecificOutput"]
    test.assertEqual(hook_out.get("hookEventName"), "PreToolUse")
    test.assertEqual(hook_out.get("permissionDecision"), "deny")
    test.assertIn("permissionDecisionReason", hook_out)
    test.assertIsInstance(hook_out["permissionDecisionReason"], str)
    test.assertTrue(hook_out["permissionDecisionReason"].strip())
    # deny JSON to updatedInput absence (canon §R3)
    test.assertNotIn(
        "updatedInput",
        hook_out,
        f"deny time updatedInput key absence required — actual:   FIELD 0  ",
    )
    return hook_out


class TestDispatcherSchema(unittest.TestCase):
    """schema validation of the detector itself output."""

    def test_allow_passthrough_bash_dotclaude(self) -> None:
        """Bash tool + .claude/ path argument → allow JSON."""
        stdout, rc = _run_dispatcher({
            "tool_name": "Bash",
            "tool_input": {"command": "cat .claude/settings.json"},
        })
        self.assertEqual(rc, 0)
        _assert_allow_schema(self, stdout)

    def test_allow_passthrough_arbitrary_tool(self) -> None:
        """Read / Glob etc hook Unloader tool → allow JSON."""
        stdout, rc = _run_dispatcher({
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/foo.txt"},
        })
        self.assertEqual(rc, 0)
        _assert_allow_schema(self, stdout)

    def test_no_empty_stdout(self) -> None:
        """bin stdout 0 from all tool name (canon §R1)."""
        for tool_name in ("Bash", "Read", "Edit", "Glob", "Grep", "Write"):
            with self.subTest(tool_name=tool_name):
                stdout, rc = _run_dispatcher({
                    "tool_name": tool_name,
                    "tool_input": {"file_path": "/tmp/foo"},
                })
                self.assertEqual(rc, 0)
                self.assertTrue(
                    stdout.strip(),
                    f" FIELD 0  : empty stdout — canon §R1 violation",
                )

    def test_dispatcher_module_importable(self) -> None:
        """The dispatcher can be imported into importlib."""
        spec = importlib.util.spec_from_file_location(
            "pretooluse_dispatcher", DISPATCHER
        )
        self.assertIsNotNone(spec)
        # Executable Only Check — Actual main() is not called as stdin is required
        self.assertIsNotNone(spec.loader)
        self.assertIsNotNone(importlib.util.module_from_spec(spec))


class TestGuardAllowSchema(unittest.TestCase):
    """allow schema validation of the guard to output JSON."""

    def test_rules_auto_approve_allow_schema(self) -> None:
        """.claude/rules/ Edit"""
        stdout, _ = _run_guard(
            "rules_auto_approve.py",
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": ".claude/rules/workflow/general.md",
                    "old_string": "A",
                    "new_string": "B",
                },
            },
            env_overrides={"HOOK_RULES_AUTO_APPROVE": "true"},
        )
        _assert_allow_schema(self, stdout)


class TestGuardDenySchema(unittest.TestCase):
    """schema validation of guards to output deny JSON.

    Each guard meets the cadon §R3 rule (deny JSON to updatedInput + key complications)
    Notice deny trigger conditions are different by each guard, so only one trigger case is valid.
    """

    def test_hooks_self_guard_deny_schema(self) -> None:
        """hooks_self_guard: .agent-factory/hooks/ Edit → deny."""
        stdout, _ = _run_guard(
            "hooks_self_guard.py",
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": ".agent-factory/hooks/pre-tool-use.py",
                    "old_string": "A",
                    "new_string": "B",
                },
            },
            env_overrides={"HOOK_HOOKS_SELF_PROTECT": "true"},
        )
        _assert_deny_schema(self, stdout)

    def test_dangerous_command_guard_deny_schema(self) -> None:
        """dangerous_command_guard: rm -rf / → deny."""
        stdout, _ = _run_guard(
            "dangerous_command_guard.py",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "sudo rm -rf /"},
            },
            env_overrides={"HOOK_DANGEROUS_COMMAND": "true"},
        )
        _assert_deny_schema(self, stdout)


class TestUpdatedInputAbsence(unittest.TestCase):
    """updatedInput key binding lint (canon §R2/R3) from full hook output."""

    def test_no_updated_input_in_guard_source(self) -> None:
        """updatedInput token in all guard sources."""
        for guard_file in sorted(GUARDS_DIR.glob("*.py")):
            if guard_file.name.startswith("_") or guard_file.name.startswith("test_"):
                continue
            source = guard_file.read_text(encoding="utf-8")
            self.assertNotIn(
                "updatedInput",
                source,
                f" FIELD 0  : updatedInput Token Discovery — canon §R2/R3 violations",
            )

    def test_no_updated_input_in_dispatcher_source(self) -> None:
        """the updatedInput token in the dispatcher source."""
        source = DISPATCHER.read_text(encoding="utf-8")
        self.assertNotIn(
            "updatedInput",
            source,
            "dispatcher: updatedInput Token Discovery — canon §R2 violation",
        )


if __name__ == "__main__":
    unittest.main()
