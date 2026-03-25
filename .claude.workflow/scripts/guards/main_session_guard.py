#!/usr/bin/env -S python3 -u
"""메인 세션 Write/Edit/Bash 차단 가드 Hook 스크립트.

PreToolUse(Write|Edit|Bash) 이벤트에서 현재 tmux 윈도우가 워크플로우 세션
(P:T-* 접두사)이 아닌 메인 세션이면 코드 수정을 차단한다.
비tmux 환경(TMUX_PANE 미설정)에서도 차단한다.
Bash 도구의 경우 파일 수정 패턴이 포함된 명령만 차단한다.

주요 함수:
    main: Hook 진입점, stdin JSON 파싱 후 메인 세션 Write/Edit/Bash 차단

입력: stdin으로 JSON (tool_name, tool_input)
출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력

토글: 환경변수 HOOK_MAIN_SESSION_GUARD (false/0 = 비활성, 기본 활성)
"""

from __future__ import annotations

import json
import os
import re
import sys

# utils 패키지 import 경로 설정
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

# prompt 패키지 import 경로 설정
_prompt_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../prompt"))
if _prompt_dir not in sys.path:
    sys.path.insert(0, _prompt_dir)

from common import read_env
from messages import (
    MAIN_SESSION_BASH_FILE_MODIFY_DENIED,
    MAIN_SESSION_NO_TMUX_DENIED,
    MAIN_SESSION_WINDOW_QUERY_FAILED,
    MAIN_SESSION_WRITE_EDIT_DENIED,
)

# 워크플로우 세션 윈도우명 접두사
_WORKFLOW_WINDOW_PREFIX = "P:T-"

# Bash 도구에서 파일을 수정할 수 있는 명령 패턴 (블랙리스트)
_BASH_FILE_MODIFY_PATTERNS: list[str] = [
    r"\bsed\s+-i",                               # sed inplace
    r"\bawk\s+.*-i\s+inplace",                   # awk inplace
    r"\b(echo|printf)\s+.*\s*>{1,2}\s*\S",       # echo/printf 리다이렉트
    r"\btee\s+(-a\s+)?\S",                       # tee 쓰기
    r"\bcat\s*<<",                               # heredoc 리다이렉트
    r"\bcp\s+",                                  # 파일 복사
    r"\bmv\s+",                                  # 파일 이동
    r"\bpython3?\s+(-c\s+|.*\bopen\b.*\bwrite\b)",  # python -c open write
    r"\bperl\s+-.*[pi]",                         # perl inplace
    r"(?:^|[;&|]\s*)\binstall\s+",               # install 명령 (서브커맨드 제외)
    r"\bdd\s+",                                  # dd 명령
]


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


def _get_current_window_name() -> str | None:
    """현재 tmux 윈도우 이름을 반환한다.

    TMUX_PANE 환경변수가 없으면 None을 반환한다.
    tmux 명령 실행 실패 시에도 None을 반환한다.

    Returns:
        현재 윈도우명 문자열. 비tmux 환경 또는 실행 실패 시 None.
    """
    import subprocess

    tmux_pane = os.environ.get("TMUX_PANE")
    if not tmux_pane:
        return None

    try:
        result = subprocess.run(
            ["tmux", "display-message", "-t", tmux_pane, "-p", "#W"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _strip_quoted_args(command: str) -> str:
    """명령 문자열에서 따옴표로 감싼 영역의 내용을 빈 문자열로 치환한다.

    작은따옴표('...') 및 큰따옴표("...") 내부 텍스트를 제거하여
    인자 값에 위험 명령어 텍스트가 포함되어도 패턴 매칭 대상에서
    제외되도록 전처리한다. 이스케이프된 따옴표(\\", \\')는 따옴표
    종료로 인식하지 않는다.

    Args:
        command: Bash 도구의 원본 command 문자열

    Returns:
        따옴표 내부 내용이 제거된 문자열. 따옴표 기호 자체는 유지된다.
    """
    # 큰따옴표: 이스케이프된 \" 를 건너뛰고 내용을 빈 문자열로 치환
    command = re.sub(r'"(?:[^"\\]|\\.)*"', '""', command)
    # 작은따옴표: 이스케이프된 \' 를 건너뛰고 내용을 빈 문자열로 치환
    command = re.sub(r"'(?:[^'\\]|\\.)*'", "''", command)
    return command


def _extract_command_positions(command: str) -> list[str]:
    """명령 문자열을 파이프/체인 구분자로 분할하여 세그먼트 목록을 반환한다.

    따옴표 strip 후의 명령 문자열을 파이프(|), 세미콜론(;), AND(&&),
    OR(||) 구분자로 분할한다. 각 세그먼트 선행 공백을 제거하여
    명령어 토큰이 세그먼트 시작 위치에 오도록 한다.

    분할 순서: &&, ||를 먼저 처리하고, 이후 |, ; 순으로 분할한다.
    단일 | 는 || 와 구별하기 위해 (?<!|)\\|(?!|) 패턴으로 매칭한다.

    Args:
        command: 따옴표 strip이 완료된 명령 문자열

    Returns:
        각 세그먼트의 선행 공백이 제거된 문자열 목록.
        빈 문자열 세그먼트는 제외된다.
    """
    # &&, ||, 단일 |, ; 구분자로 분할 (|| 를 | 보다 먼저 처리)
    parts = re.split(r'&&|\|\||(?<!\|)\|(?!\|)|;', command)
    return [part.lstrip() for part in parts if part.strip()]


def _check_bash_file_modify(command: str) -> None:
    """Bash 명령에서 파일 수정 패턴을 검사하고 매칭 시 차단한다.

    따옴표로 감싼 인자 영역을 먼저 제거(_strip_quoted_args)한 뒤,
    파이프/체인 구분자로 세그먼트를 분할(_extract_command_positions)하여
    각 세그먼트에서 _BASH_FILE_MODIFY_PATTERNS 패턴을 검사한다.
    하나라도 매칭되면 _deny()를 호출한다.
    매칭되지 않으면 sys.exit(0)으로 통과한다.

    Args:
        command: Bash 도구의 command 문자열
    """
    stripped = _strip_quoted_args(command)
    segments = _extract_command_positions(stripped)
    for segment in segments:
        for pattern in _BASH_FILE_MODIFY_PATTERNS:
            if re.search(pattern, segment):
                _deny(MAIN_SESSION_BASH_FILE_MODIFY_DENIED.format(pattern=pattern))
    # 파일 수정 패턴이 없으면 통과
    sys.exit(0)


def main() -> None:
    """메인 세션 Write/Edit/Bash 차단 Hook의 진입점.

    stdin에서 JSON을 읽어 Write/Edit/Bash 도구 사용 시 현재 세션이
    워크플로우 세션(P:T-* 윈도우)인지 확인하고,
    메인 세션이면 deny 응답을 출력하여 코드 수정을 차단한다.
    비tmux 환경에서도 차단한다.
    Bash 도구의 경우 파일 수정 패턴이 포함된 명령만 차단한다.
    """
    # .claude.workflow/.env에서 설정 로드
    hook_flag = os.environ.get("HOOK_MAIN_SESSION_GUARD") or read_env("HOOK_MAIN_SESSION_GUARD")

    # Hook disable check (false = disabled)
    if hook_flag in ("false", "0"):
        sys.exit(0)

    # stdin에서 JSON 읽기
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    # Write, Edit, Bash가 아니면 통과
    if tool_name not in ("Write", "Edit", "Bash"):
        sys.exit(0)

    # .claude.workflow/.version 파일은 메인 세션에서도 수정 허용
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if file_path.endswith(".claude.workflow/.version"):
        sys.exit(0)

    # TMUX_PANE 환경변수 확인
    tmux_pane = os.environ.get("TMUX_PANE")
    if not tmux_pane:
        # 비tmux 환경에서는 차단 (Bash는 파일 수정 패턴만 차단)
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            _check_bash_file_modify(command)
        _deny(MAIN_SESSION_NO_TMUX_DENIED)

    # tmux 윈도우명 조회
    window_name = _get_current_window_name()

    # 윈도우명 조회 실패 시 안전 차단 (보수적 접근)
    if window_name is None:
        # Bash는 파일 수정 패턴만 차단
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            _check_bash_file_modify(command)
        _deny(MAIN_SESSION_WINDOW_QUERY_FAILED)

    # 워크플로우 세션(P:T-* 접두사)이면 통과
    if window_name.startswith(_WORKFLOW_WINDOW_PREFIX):
        sys.exit(0)

    # 메인 세션에서 Bash는 파일 수정 패턴만 차단
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        _check_bash_file_modify(command)

    # 메인 세션에서 Write/Edit는 차단
    _deny(MAIN_SESSION_WRITE_EDIT_DENIED.format(window_name=window_name))


if __name__ == "__main__":
    main()
