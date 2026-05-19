"""PreToolUse `.claude/` 경로 인자 Bash 명령 통합 회귀 매트릭스 (T-484 P3).

`general.md` §".claude/ 편집 (MUST)" 의 통과 룰을 4 시나리오로 박제:

| # | 시나리오 | 예시 | 기대 |
|---|---------|------|------|
| 1 | sed -i 가 .claude/ 경로 인자 | `sed -i 's/X/Y/g' .claude/rules/...` | allow |
| 2 | cat 으로 .claude/ 파일 읽기 | `cat .claude/settings.json` | allow |
| 3 | grep -r 으로 .claude/ 트리 검색 | `grep -r "PreToolUse" .claude/` | allow |
| 4 | mixed (.claude/ + .claude-organic/) | `sed -i ... .claude/foo .claude-organic/bar` | allow |

캐논 결정 (`plan.md` §결정 표): Bash `.claude/` 경로 인자 = **통과 (allow JSON)**.
Edit/Write 만 Claude Code 하드코딩 보호로 차단되고, Bash 간접 도구는 통과.
flow-claude-edit 동선이 정식 경로이며 본 가드 흐름과 양립한다.

본 vehicle 은 P1 의 단일 시나리오 vehicle 을 4 시나리오로 확장한 forward 회귀 차단망.
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
    """allow schema + returncode 정합 검증."""
    test.assertEqual(rc, 0)
    test.assertTrue(stdout.strip(), "빈 stdout — canon §R1 위반")
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
    """plan §P3 4 시나리오 매트릭스."""

    def test_scenario_1_sed_inline_dotclaude(self) -> None:
        """sed -i 로 .claude/rules/workflow/general.md 수정 → allow."""
        stdout, rc = _run_dispatcher({
            "tool_name": "Bash",
            "tool_input": {
                "command": "sed -i 's/X/Y/g' .claude/rules/workflow/general.md",
            },
        })
        _assert_allow(self, stdout, rc)

    def test_scenario_2_cat_dotclaude_settings(self) -> None:
        """cat .claude/settings.json → allow (읽기 전용)."""
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
        """sed -i 로 .claude/ + .claude-organic/ 동시 수정 → allow."""
        stdout, rc = _run_dispatcher({
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    "sed -i 's/X/Y/g' .claude/rules/foo.md "
                    ".claude-organic/test.md"
                ),
            },
        })
        _assert_allow(self, stdout, rc)


class TestFlowClaudeEditCoexistence(unittest.TestCase):
    """flow-claude-edit 동선 (사용자 정식 경로) 회귀 안전망.

    `.claude/` 편집의 정식 경로는 `flow-claude-edit open/save` 이며,
    본 Bash 통과 룰은 사용자 동선을 방해하지 않는다 (별도 트래픽).
    """

    def test_flow_claude_edit_open_passes(self) -> None:
        """`flow-claude-edit open rules/workflow/general.md` Bash → allow."""
        stdout, rc = _run_dispatcher({
            "tool_name": "Bash",
            "tool_input": {
                "command": ".claude-organic/bin/flow-claude-edit open rules/workflow/general.md",
            },
        })
        _assert_allow(self, stdout, rc)

    def test_flow_claude_edit_save_passes(self) -> None:
        """`flow-claude-edit save rules/workflow/general.md` Bash → allow."""
        stdout, rc = _run_dispatcher({
            "tool_name": "Bash",
            "tool_input": {
                "command": ".claude-organic/bin/flow-claude-edit save rules/workflow/general.md",
            },
        })
        _assert_allow(self, stdout, rc)


if __name__ == "__main__":
    unittest.main()
