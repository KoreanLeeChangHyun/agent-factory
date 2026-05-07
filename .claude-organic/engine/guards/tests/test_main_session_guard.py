"""main_session_guard.py 단위 테스트 (T-422 메모리 화이트리스트 회귀 차단)

12개 시나리오를 통해 가드 동작을 검증한다:
  TC1-5:  allow — 메모리 디렉터리 Write/Edit/Bash cp + prompt 본문 텍스트 substring
  TC6:    allow — 워크플로우 세션 분기 회귀 0건 확인
  TC7-11: deny  — 실제 코드 수정(engine/board/sed/cp) + 메모리+코드 혼재 보수적 차단
  TC12:   allow — HOOK_MAIN_SESSION_GUARD=false 토글 검증
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

GUARD_SCRIPT = Path(__file__).resolve().parent.parent / "main_session_guard.py"


def _run_guard(
    tool_name: str,
    tool_input: dict,
    env_overrides: dict | None = None,
) -> tuple[str, int]:
    """가드 스크립트를 subprocess 로 실행하고 (stdout, returncode) 반환.

    기본 환경:
      - _WF_SESSION_TYPE 미설정 → unknown 분기 (메인 세션 시뮬레이션)
      - HOOK_MAIN_SESSION_GUARD=true
      - TMUX_PANE 미설정 → TMUX 폴백 없음
      - WORKFLOW_WORKTREE_PATH, WORKFLOW_WORK_DIR 미설정 → worktree_path_guard
        fallback 간섭 회피
    """
    payload = {"tool_name": tool_name, "tool_input": tool_input}
    # 최소 환경 구성: HOME, PATH, PYTHONPATH 계승 + 가드 토글 ON
    # TMUX_PANE/TMUX 명시 제거 → tmux 폴백 없이 unknown 분기 사용
    base_env: dict[str, str] = {}

    # 부모 환경에서 최소 필수 키만 계승
    for key in ("HOME", "PATH", "PYTHONPATH", "LANG", "LC_ALL"):
        if key in os.environ:
            base_env[key] = os.environ[key]

    # 가드 활성화 기본값
    base_env["HOOK_MAIN_SESSION_GUARD"] = "true"

    # _WF_SESSION_TYPE 명시 제거 → get_session_type() = unknown (메인 시뮬레이션)
    # (부모 환경에 _WF_SESSION_TYPE=workflow 가 있으면 기본으로 상속되지 않도록 명시 제외)

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


class TestMainSessionGuard(unittest.TestCase):
    """main_session_guard.py 회귀 테스트.

    - allow 케이스 6종: 메모리 디렉터리 Write/Edit/Bash + prompt 텍스트 + 워크플로우 세션
    - deny  케이스 6종: 실제 코드 수정(engine/board/sed/cp) + 메모리+코드 혼재 + 토글
    """

    # ── allow 케이스 ──────────────────────────────────────────────────────────

    def test_01_memory_write_allow(self) -> None:
        """Write 도구로 메모리 디렉터리 하위 경로 작성 → 통과."""
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": "~/.claude/projects/-home-deus-claude/memory/feedback/foo.md",
                "content": "test",
            },
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    def test_02_memory_edit_allow(self) -> None:
        """Edit 도구로 메모리 디렉터리 하위 절대 경로 수정 → 통과."""
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
        """Bash cp 명령으로 메모리 디렉터리에만 복사 → 통과."""
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
        """Bash flow-kanban update-prompt 의 따옴표 안 메모리 경로 텍스트 → 통과.

        _strip_quoted_args 가 따옴표 내부를 비워 패턴 매칭 대상 외가 됨을 검증.
        """
        stdout, _ = _run_guard(
            "Bash",
            {
                "command": (
                    'flow-kanban update-prompt T-422 --target '
                    '"수정 대상: ~/.claude/projects/-home-deus-claude/memory/feedback/"'
                )
            },
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    def test_05_prompt_substring_with_code_path_in_quote_allow(self) -> None:
        """Bash flow-kanban 의 따옴표 안 코드 경로 substring → 통과.

        코드 경로가 따옴표 안에 있어 _strip_quoted_args 로 제거됨을 검증.
        """
        stdout, _ = _run_guard(
            "Bash",
            {
                "command": (
                    "flow-kanban update-prompt T-422 "
                    '--constraints "engine/guards/main_session_guard.py 수정"'
                )
            },
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    def test_06_workflow_session_allow(self) -> None:
        """_WF_SESSION_TYPE=workflow 환경에서 코드 수정 명령 → 통과.

        기존 워크플로우 세션 분기 회귀 0건 확인.
        """
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": ".claude-organic/engine/guards/main_session_guard.py",
                "content": "# test",
            },
            env_overrides={"_WF_SESSION_TYPE": "workflow"},
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")

    # ── deny 케이스 ───────────────────────────────────────────────────────────

    def test_07_main_session_write_engine_deny(self) -> None:
        """메인 세션에서 Write 도구로 engine 디렉터리 수정 → 차단."""
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": ".claude-organic/engine/guards/main_session_guard.py",
                "content": "# test",
            },
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_08_main_session_edit_board_deny(self) -> None:
        """메인 세션에서 Edit 도구로 board 디렉터리 수정 → 차단."""
        stdout, _ = _run_guard(
            "Edit",
            {
                "file_path": ".claude-organic/board/server/app.py",
                "old_string": "old",
                "new_string": "new",
            },
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_09_main_session_bash_sed_deny(self) -> None:
        """메인 세션에서 Bash sed -i 명령 → 차단."""
        stdout, _ = _run_guard(
            "Bash",
            {"command": "sed -i 's/a/b/' engine/guards/main_session_guard.py"},
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_10_main_session_bash_cp_to_engine_deny(self) -> None:
        """메인 세션에서 Bash cp로 engine 디렉터리에 파일 복사 → 차단."""
        stdout, _ = _run_guard(
            "Bash",
            {"command": "cp /tmp/foo.py .claude-organic/engine/foo.py"},
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_11_memory_and_engine_mixed_deny(self) -> None:
        """Bash cp 메모리→engine 혼재 명령 → 보수적 차단.

        메모리 경로가 원본이더라도 대상이 코드 경로이면 차단을 보존.
        """
        stdout, _ = _run_guard(
            "Bash",
            {
                "command": (
                    "cp ~/.claude/projects/-home-deus-claude/memory/foo.md "
                    ".claude-organic/engine/bar.md"
                )
            },
        )
        self.assertTrue(_is_deny(stdout), f"expected deny: {stdout!r}")

    def test_12_guard_disabled_allow(self) -> None:
        """HOOK_MAIN_SESSION_GUARD=false 환경에서 코드 수정 → 토글로 통과."""
        stdout, _ = _run_guard(
            "Write",
            {
                "file_path": ".claude-organic/engine/guards/main_session_guard.py",
                "content": "# test",
            },
            env_overrides={"HOOK_MAIN_SESSION_GUARD": "false"},
        )
        self.assertFalse(_is_deny(stdout), f"unexpected deny: {stdout!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
