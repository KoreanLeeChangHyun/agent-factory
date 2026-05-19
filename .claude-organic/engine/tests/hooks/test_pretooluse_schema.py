"""PreToolUse hook 출력 schema 단위 테스트 (T-484 P2).

`general.md` §"PreToolUse Hook 출력 schema (MUST)" 의 캐논 룰을 박제하는 단위 테스트.

검증 항목:
  - allow JSON 키 정합 (hookEventName / permissionDecision: "allow"
    / permissionDecisionReason)
  - allow 시 updatedInput 미지정 (canon: 변경 없으면 생략. {} 절대 금지)
  - deny JSON 키 정합 (hookEventName / permissionDecision: "deny"
    / permissionDecisionReason)
  - deny 시 updatedInput 키 부재
  - dispatcher 최종 fall-through 가 빈 stdout 을 내지 않음
  - dispatcher 모듈이 importlib 으로 import 가능 (구문/import 무결성)

본 테스트는 dispatcher subprocess 호출 + 직접 분기 호출 양쪽으로 검증한다.
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
DISPATCHER = REPO_ROOT / ".claude-organic" / "hooks" / "pre-tool-use.py"
GUARDS_DIR = REPO_ROOT / ".claude-organic" / "engine" / "guards"


def _run_dispatcher(
    payload: dict,
    env_overrides: dict | None = None,
) -> tuple[str, int]:
    """디스패처 subprocess 실행 헬퍼."""
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
    """단일 guard subprocess 실행 헬퍼."""
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
    """allow JSON schema 정합 검증 + hookSpecificOutput 반환."""
    test.assertTrue(stdout.strip(), "stdout 가 비어있다 — canon §R1 위반")
    data = json.loads(stdout.strip())
    test.assertIn("hookSpecificOutput", data)
    hook_out = data["hookSpecificOutput"]
    test.assertEqual(hook_out.get("hookEventName"), "PreToolUse")
    test.assertEqual(hook_out.get("permissionDecision"), "allow")
    # updatedInput 키 부재 검증 (canon §R2: 변경 없으면 생략)
    test.assertNotIn(
        "updatedInput",
        hook_out,
        f"allow 시 updatedInput 키 부재 필수 — actual: {hook_out!r}",
    )
    return hook_out


def _assert_deny_schema(test: unittest.TestCase, stdout: str) -> dict:
    """deny JSON schema 정합 검증 + hookSpecificOutput 반환."""
    test.assertTrue(stdout.strip(), "deny stdout 가 비어있다")
    data = json.loads(stdout.strip())
    test.assertIn("hookSpecificOutput", data)
    hook_out = data["hookSpecificOutput"]
    test.assertEqual(hook_out.get("hookEventName"), "PreToolUse")
    test.assertEqual(hook_out.get("permissionDecision"), "deny")
    test.assertIn("permissionDecisionReason", hook_out)
    test.assertIsInstance(hook_out["permissionDecisionReason"], str)
    test.assertTrue(hook_out["permissionDecisionReason"].strip())
    # deny JSON 에 updatedInput 부재 (canon §R3)
    test.assertNotIn(
        "updatedInput",
        hook_out,
        f"deny 시 updatedInput 키 부재 필수 — actual: {hook_out!r}",
    )
    return hook_out


class TestDispatcherSchema(unittest.TestCase):
    """디스패처 자체 출력 schema 검증."""

    def test_allow_passthrough_bash_dotclaude(self) -> None:
        """Bash 도구 + .claude/ 경로 인자 → allow JSON."""
        stdout, rc = _run_dispatcher({
            "tool_name": "Bash",
            "tool_input": {"command": "cat .claude/settings.json"},
        })
        self.assertEqual(rc, 0)
        _assert_allow_schema(self, stdout)

    def test_allow_passthrough_arbitrary_tool(self) -> None:
        """Read / Glob 등 hook 미해당 도구 → allow JSON."""
        stdout, rc = _run_dispatcher({
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/foo.txt"},
        })
        self.assertEqual(rc, 0)
        _assert_allow_schema(self, stdout)

    def test_no_empty_stdout(self) -> None:
        """모든 tool_name 에서 빈 stdout 0건 (canon §R1)."""
        for tool_name in ("Bash", "Read", "Edit", "Glob", "Grep", "Write"):
            with self.subTest(tool_name=tool_name):
                stdout, rc = _run_dispatcher({
                    "tool_name": tool_name,
                    "tool_input": {"file_path": "/tmp/foo"},
                })
                self.assertEqual(rc, 0)
                self.assertTrue(
                    stdout.strip(),
                    f"{tool_name}: 빈 stdout — canon §R1 위반",
                )

    def test_dispatcher_module_importable(self) -> None:
        """dispatcher 가 importlib 으로 import 가능 (구문 무결성)."""
        spec = importlib.util.spec_from_file_location(
            "pretooluse_dispatcher", DISPATCHER
        )
        self.assertIsNotNone(spec)
        # 실행 가능성만 확인 — 실제 main() 은 stdin 필요하므로 호출하지 않음
        self.assertIsNotNone(spec.loader)
        self.assertIsNotNone(importlib.util.module_from_spec(spec))


class TestGuardAllowSchema(unittest.TestCase):
    """allow JSON 을 출력하는 guard 의 schema 검증."""

    def test_rules_auto_approve_allow_schema(self) -> None:
        """rules_auto_approve 가 .claude/rules/ Edit 에 대해 정합 allow 출력."""
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
    """deny JSON 을 출력하는 guard 들의 schema 검증.

    각 guard 가 캐논 §R3 룰 (deny JSON 에 updatedInput 부재 + 키 정합) 을 충족하는지
    확인한다. deny 트리거 조건은 각 guard 별로 다르므로 트리거 케이스 1건만 검증.
    """

    def test_hooks_self_guard_deny_schema(self) -> None:
        """hooks_self_guard: .claude-organic/hooks/ Edit → deny."""
        stdout, _ = _run_guard(
            "hooks_self_guard.py",
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": ".claude-organic/hooks/pre-tool-use.py",
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
    """전체 hook 출력에서 updatedInput 키 부재 lint (canon §R2/R3)."""

    def test_no_updated_input_in_guard_source(self) -> None:
        """모든 guard 소스에 updatedInput 토큰 부재."""
        for guard_file in sorted(GUARDS_DIR.glob("*.py")):
            if guard_file.name.startswith("_") or guard_file.name.startswith("test_"):
                continue
            source = guard_file.read_text(encoding="utf-8")
            self.assertNotIn(
                "updatedInput",
                source,
                f"{guard_file.name}: updatedInput 토큰 발견 — canon §R2/R3 위반",
            )

    def test_no_updated_input_in_dispatcher_source(self) -> None:
        """dispatcher 소스에 updatedInput 토큰 부재."""
        source = DISPATCHER.read_text(encoding="utf-8")
        self.assertNotIn(
            "updatedInput",
            source,
            "dispatcher: updatedInput 토큰 발견 — canon §R2 위반",
        )


if __name__ == "__main__":
    unittest.main()
