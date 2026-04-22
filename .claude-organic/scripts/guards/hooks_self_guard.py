#!/usr/bin/env -S python3 -u
"""hooks 디렉토리 자기 보호 가드 Hook 스크립트.

PreToolUse(Write|Edit|Bash) 이벤트에서 .claude-organic/hooks/ 경로 파일 수정을 차단.

주요 함수:
    main: Hook 진입점, stdin JSON 파싱 후 보호 경로 수정 차단

입력: stdin으로 JSON (tool_name, tool_input)
출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력

우회: 환경변수 HOOKS_EDIT_ALLOWED=1 설정 시 차단 해제
      (오케스트레이터가 `.claude-organic/scripts/flow/update_state.py env <registryKey> set HOOKS_EDIT_ALLOWED 1` 명령으로 설정/해제)
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
    HOOKS_BYPASS_FILE_DENIED,
    HOOKS_BASH_MODIFY_DENIED,
    HOOKS_WRITE_EDIT_DENIED,
)

# 가드 패턴 로드 (보안 우선: import 실패 시 보수적 폴백)
try:
    from data.constants import (
        GUARD_READONLY_PATTERNS as READONLY_PATTERNS,
        GUARD_MODIFY_PATTERNS as MODIFY_PATTERNS,
        GUARD_PROTECTED_PATH_PATTERNS as PROTECTED_PATH_PATTERNS,
        GUARD_INLINE_WRITE_PATTERNS as INLINE_WRITE_PATTERNS,
    )
    PROTECTED_PATH_RES: list[re.Pattern[str]] = [re.compile(p) for p in PROTECTED_PATH_PATTERNS]
except ImportError:
    print(
        "[hooks_self_guard] CRITICAL: data.constants guard patterns import 실패 - 보안 폴백 적용",
        file=sys.stderr,
    )
    READONLY_PATTERNS: list[str] = []
    MODIFY_PATTERNS: list[str] = [r"."]
    PROTECTED_PATH_RES = [re.compile(r"\.claude\.workflow/hooks/"), re.compile(r"\.claude\.workflow/workflow/bypass")]
    INLINE_WRITE_PATTERNS: list[str] = [r"."]


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


def _refs_protected(text: str) -> bool:
    """텍스트가 보호 대상 경로를 참조하는지 확인한다.

    Args:
        text: 검사할 텍스트 문자열

    Returns:
        보호 대상 경로 패턴에 매칭되면 True, 그렇지 않으면 False
    """
    for p_re in PROTECTED_PATH_RES:
        if p_re.search(text):
            return True
    return False


def _check_inline_write(subcmd: str) -> bool:
    """인라인 코드(-c/-e 플래그) 내에서 보호 대상 경로에 대한 쓰기를 탐지한다.

    Args:
        subcmd: 검사할 서브커맨드 문자열

    Returns:
        인라인 쓰기 패턴이 감지되면 True, 그렇지 않으면 False
    """
    if not re.search(r"\s+-(c|e)\s", subcmd):
        return False
    if not _refs_protected(subcmd):
        return False
    for wp in INLINE_WRITE_PATTERNS:
        if re.search(wp, subcmd):
            return True
    return False


def _classify_bash_command(bash_cmd: str) -> str | None:
    """Bash 명령을 분류하여 'READONLY' 또는 'MODIFY'를 반환한다.

    보호 대상 경로를 참조하지 않으면 None (통과).

    Args:
        bash_cmd: 분류할 Bash 명령 문자열

    Returns:
        'READONLY': 읽기 전용 명령만 포함된 경우
        'MODIFY': 수정 작업이 감지된 경우
        None: 보호 대상 경로를 참조하지 않는 경우
    """
    if not _refs_protected(bash_cmd):
        return None

    # 파이프라인/연결 명령 분리
    subcmds = re.split(r"\s*(?:&&|\|\||[;|])\s*", bash_cmd)
    # $() 와 backtick 내부 명령도 추출
    subcmds += re.findall(r"\$\(([^)]+)\)", bash_cmd)
    subcmds += re.findall(r"\x60([^\x60]+)\x60", bash_cmd)

    for sc in subcmds:
        sc = sc.strip()
        if not sc:
            continue
        if not _refs_protected(sc):
            continue

        # 읽기 전용 명령인지 검사
        is_ro = False
        for ro_pat in READONLY_PATTERNS:
            if re.match(ro_pat, sc):
                is_ro = True
                break

        if is_ro:
            # 읽기 전용이라도 인라인 코드 쓰기 패턴이 있으면 MODIFY
            if _check_inline_write(sc):
                return "MODIFY"
            continue

        # 수정 패턴 검사
        for mod_pat in MODIFY_PATTERNS:
            if re.search(mod_pat, sc):
                return "MODIFY"

        # 명시적 수정 패턴에 매칭되지 않아도,
        # 읽기 전용 화이트리스트에도 없으면 안전 차단 (보수적 접근)
        return "MODIFY"

    # 모든 서브커맨드가 읽기 전용이거나 보호 대상 경로를 참조하지 않음
    return "READONLY"


def main() -> None:
    """hooks 디렉토리 자기 보호 가드 Hook의 진입점.

    stdin에서 JSON을 읽어 Write/Edit/Bash 도구 실행 시 보호 경로 수정을 차단한다.
    HOOKS_EDIT_ALLOWED 환경변수가 설정된 경우 차단을 우회할 수 있다.
    .claude-organic/workflow/bypass 경로는 환경변수 우회 없이 항상 차단된다.
    """
    # .claude-organic/.settings에서 설정 로드
    hook_flag = os.environ.get("HOOK_HOOKS_SELF_PROTECT") or read_env("HOOK_HOOKS_SELF_PROTECT")
    hook_edit_allowed = os.environ.get("HOOKS_EDIT_ALLOWED") or read_env("HOOKS_EDIT_ALLOWED")

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

    tool_input = data.get("tool_input", {})

    # --- Bash 도구 분기 ---
    if tool_name == "Bash":
        bash_cmd = tool_input.get("command", "")
        if not bash_cmd:
            sys.exit(0)

        # command에 보호 대상 경로가 없으면 통과
        if not _refs_protected(bash_cmd):
            sys.exit(0)

        # 환경변수 우회 검사
        if hook_edit_allowed in ("true", "1"):
            sys.exit(0)

        classification = _classify_bash_command(bash_cmd)
        if classification == "READONLY":
            sys.exit(0)

        # .claude-organic/workflow/bypass 참조 여부에 따라 차단 메시지 분기
        if re.search(r"\.claude\.workflow/workflow/bypass", bash_cmd):
            _deny(HOOKS_BYPASS_FILE_DENIED)
        else:
            _deny(HOOKS_BASH_MODIFY_DENIED)

    # --- Write / Edit 도구 분기 ---
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # .claude-organic/workflow/bypass 경로 포함 여부 검사
    if ".claude-organic/workflow/bypass" in file_path:
        # bypass 파일은 환경변수 우회 불가 (무조건 차단)
        _deny(HOOKS_BYPASS_FILE_DENIED)

    # .claude-organic/hooks/ 경로 포함 여부 검사
    if ".claude-organic/hooks/" in file_path:
        # 환경변수 우회 검사
        if hook_edit_allowed in ("true", "1"):
            sys.exit(0)

        _deny(HOOKS_WRITE_EDIT_DENIED)

    # .claude-organic/hooks/ 경로 미매칭 시 통과
    sys.exit(0)


if __name__ == "__main__":
    main()
