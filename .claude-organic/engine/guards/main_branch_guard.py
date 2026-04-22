#!/usr/bin/env -S python3 -u
"""main 브랜치 커밋 차단 가드 Hook 스크립트.

PreToolUse(Bash) 이벤트에서 git commit 명령 감지 시 현재 브랜치가
main 또는 master이면 차단한다.

주요 함수:
    main: Hook 진입점, stdin JSON 파싱 후 main/master 브랜치 커밋 차단

입력: stdin으로 JSON (tool_name, tool_input)
출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력

토글: 환경변수 HOOK_MAIN_BRANCH_GUARD (false/0 = 비활성, 기본 활성)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

# utils 패키지 import 경로 설정
_engine_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

# prompt 패키지 import 경로 설정
_prompt_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../prompt"))
if _prompt_dir not in sys.path:
    sys.path.insert(0, _prompt_dir)

from common import read_env
from messages import MAIN_BRANCH_COMMIT_DENIED

# main/master 브랜치에서 차단할 git commit 패턴
_GIT_COMMIT_PATTERN = re.compile(r"\bgit\s+commit\b")

# 보호 대상 브랜치 집합
_PROTECTED_BRANCHES: frozenset[str] = frozenset({"main", "master"})


def _deny(reason: str) -> None:
    """차단 JSON을 stdout에 출력하고 프로세스를 종료한다.

    Args:
        reason: 차단 사유 문자열
    """
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


def _get_current_branch() -> str | None:
    """현재 git 브랜치명을 반환한다.

    Returns:
        현재 브랜치명 문자열. git 실행 실패 시 None.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def main() -> None:
    """main/master 브랜치 커밋 차단 Hook의 진입점.

    stdin에서 JSON을 읽어 Bash 도구의 git commit 명령을 감지하고,
    현재 브랜치가 main 또는 master이면 deny 응답을 출력하여 차단한다.
    git 실행 실패 시 안전 통과(exit 0)로 처리한다.
    """
    # .claude-organic/.settings에서 설정 로드
    hook_flag = os.environ.get("HOOK_MAIN_BRANCH_GUARD") or read_env("HOOK_MAIN_BRANCH_GUARD")

    # Hook disable check (false = disabled)
    if hook_flag in ("false", "0"):
        sys.exit(0)

    # stdin에서 JSON 읽기
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    # Bash가 아니면 통과
    if tool_name != "Bash":
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    # git commit 패턴 매칭
    if not _GIT_COMMIT_PATTERN.search(command):
        sys.exit(0)

    # 현재 브랜치 조회
    branch = _get_current_branch()
    if branch is None:
        # git 실행 실패 시 안전 통과
        sys.exit(0)

    # main/master 브랜치이면 차단
    if branch in _PROTECTED_BRANCHES:
        _deny(MAIN_BRANCH_COMMIT_DENIED.format(branch=branch))

    # 보호 대상 브랜치가 아니면 통과
    sys.exit(0)


if __name__ == "__main__":
    main()
