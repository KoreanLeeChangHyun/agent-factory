"""PreToolUse 디스패처 회귀 재현 vehicle (T-484).

본 파일은 다음 두 캐논 룰의 동작을 회귀 차단한다:

  1. `.claude/rules/workflow/general.md` §"PreToolUse Hook 출력 schema (MUST)"
     - 통과 시 빈 stdout 금지 → permissionDecision: "allow" JSON 필수
     - allow JSON 의 updatedInput 필드는 전체 tool_input 교체용; 변경 없으면 생략
     - "updatedInput": {} 금지

  2. `.claude/rules/workflow/general.md` §".claude/ 편집 (MUST)"
     - Edit/Write 만 차단 대상 — Bash `sed -i`, `cat`, `grep` 은 차단 안 함
     - `.claude/` 경로 인자 Bash 명령은 PreToolUse 디스패처를 통과해야 한다

재현 vehicle:
    test_regression_reproduction — 사용자 캐논에 명시된 회귀 시나리오를
    1건 실측한다. fix 전: schema 위반 / 빈 stdout / 잘못된 behavior 필드.
    fix 후 (현재 상태): hookSpecificOutput.permissionDecision == "allow".

플랜 경로 정정 (T-484 plan 의 stale 경로 보정):
    - 플랜은 `.claude-organic/engine/hooks/dispatcher/pre-tool-use.py` 와
      `.claude-organic/engine/workflow_hooks/pretooluse_task.py` 를
      참조했으나, 실제 dispatcher 는 `.claude-organic/hooks/pre-tool-use.py`
      에 있고 `workflow_hooks/` 는 T-486 Phase 6-1 (commit 9fd9050) 에서
      통째 폐기됨. 본 테스트는 실제 디스패처 경로를 사용한다.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DISPATCHER = REPO_ROOT / ".claude-organic" / "hooks" / "pre-tool-use.py"


def _run_dispatcher(payload: dict, env_overrides: dict | None = None) -> tuple[str, int]:
    """PreToolUse 디스패처를 subprocess 로 실행하고 (stdout, returncode) 반환."""
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
    """stdout 의 hookSpecificOutput JSON 을 파싱한다."""
    data = json.loads(stdout.strip())
    return data.get("hookSpecificOutput", {})


class TestPreToolUseRegression(unittest.TestCase):
    """회귀 재현 vehicle — T-484 plan 의 핵심 시나리오 1건."""

    def test_dispatcher_path_exists(self) -> None:
        """실제 디스패처 파일이 알려진 경로에 존재한다."""
        self.assertTrue(DISPATCHER.exists(), f"dispatcher missing: {DISPATCHER}")

    def test_regression_reproduction(self) -> None:
        """plan 의 회귀 시나리오 — sed -i 로 .claude/ 경로 인자 Bash 명령.

        기대 (fix 후 = 현재 GREEN):
          - stdout 비어있지 않음 (schema 룰 §1: 빈 stdout 금지)
          - hookSpecificOutput.hookEventName == "PreToolUse"
          - hookSpecificOutput.permissionDecision == "allow"
          - updatedInput 키 부재 (schema 룰 §1: 변경 없으면 생략)
          - returncode 0
        """
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "sed -i 's/A/B/g' .claude/rules/workflow/general.md",
            },
        }
        stdout, rc = _run_dispatcher(payload)

        # 빈 stdout 금지 (canon §1)
        self.assertTrue(
            stdout.strip(),
            "PreToolUse 디스패처가 빈 stdout 을 반환했다 — schema 위반",
        )

        # JSON parse + schema 검증
        hook_out = _parse_hook_output(stdout)
        self.assertEqual(hook_out.get("hookEventName"), "PreToolUse")
        self.assertEqual(
            hook_out.get("permissionDecision"),
            "allow",
            f"unexpected decision: {hook_out!r}",
        )

        # updatedInput 부재 (canon §1: 변경 없으면 생략)
        self.assertNotIn(
            "updatedInput",
            hook_out,
            "통과 시 updatedInput 은 생략돼야 한다 — schema 룰 위반 위험",
        )

        # 통과 시 returncode 0
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
