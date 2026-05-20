#!/usr/bin/env -S python3 -u
"""hooks 디렉토리 자기 보호 가드 Hook 스크립트.

PreToolUse(Write|Edit|Bash) 이벤트에서 .agent-factory/hooks/ 경로 파일 수정을 차단.

주요 함수:
    main: Hook 진입점, stdin JSON 파싱 후 보호 경로 수정 차단

입력: stdin으로 JSON (tool_name, tool_input)
출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력

우회: 환경변수 HOOKS_EDIT_ALLOWED=1 설정 시 차단 해제
      (오케스트레이터가 `.agent-factory/engine/flow/update_state.py env <registryKey> set HOOKS_EDIT_ALLOWED 1` 명령으로 설정/해제)
"""

from __future__ import annotations

import json
import os
import re
import sys

# Set utils package import path
_engine_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

# Guard message module import path setting
_guards_dir = os.path.dirname(os.path.abspath(__file__))
if _guards_dir not in sys.path:
    sys.path.insert(0, _guards_dir)

from common import read_env
from messages import (
    HOOKS_BYPASS_FILE_DENIED,
    HOOKS_BASH_MODIFY_DENIED,
    HOOKS_WRITE_EDIT_DENIED,
)

# Load guard pattern (security first: conservative fallback on import failure)
try:
    from constants import (
        GUARD_READONLY_PATTERNS as READONLY_PATTERNS,
        GUARD_MODIFY_PATTERNS as MODIFY_PATTERNS,
        GUARD_PROTECTED_PATH_PATTERNS as PROTECTED_PATH_PATTERNS,
        GUARD_INLINE_WRITE_PATTERNS as INLINE_WRITE_PATTERNS,
    )
    PROTECTED_PATH_RES: list[re.Pattern[str]] = [re.compile(p) for p in PROTECTED_PATH_PATTERNS]
except ImportError:
    print(
        "[hooks_self_guard] CRITICAL: data.constants guard patterns import failed - apply security fallback",
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

    # Separate pipeline/connection commands
    subcmds = re.split(r"\s*(?:&&|\|\||[;|])\s*", bash_cmd)
    # $() and backtick internal commands are also extracted
    subcmds += re.findall(r"\$\(([^)]+)\)", bash_cmd)
    subcmds += re.findall(r"\x60([^\x60]+)\x60", bash_cmd)

    for sc in subcmds:
        sc = sc.strip()
        if not sc:
            continue
        if not _refs_protected(sc):
            continue

        # Check if a command is read-only
        is_ro = False
        for ro_pat in READONLY_PATTERNS:
            if re.match(ro_pat, sc):
                is_ro = True
                break

        if is_ro:
            # MODIFY if there is an inline code writing pattern, even if it is read-only
            if _check_inline_write(sc):
                return "MODIFY"
            continue

        # Correction pattern inspection
        for mod_pat in MODIFY_PATTERNS:
            if re.search(mod_pat, sc):
                return "MODIFY"

        # Even if it does not match an explicit modification pattern,
        # Safe blocking if not in read-only whitelist (conservative approach)
        return "MODIFY"

    # All subcommands are read-only or do not reference the protected path
    return "READONLY"


def main() -> None:
    """hooks 디렉토리 자기 보호 가드 Hook의 진입점.

    stdin에서 JSON을 읽어 Write/Edit/Bash 도구 실행 시 보호 경로 수정을 차단한다.
    HOOKS_EDIT_ALLOWED 환경변수가 설정된 경우 차단을 우회할 수 있다.
    .agent-factory/runs/bypass 경로는 환경변수 우회 없이 항상 차단된다.
    """
    # Load settings from .agent-factory/.settings
    hook_flag = os.environ.get("HOOK_HOOKS_SELF_PROTECT") or read_env("HOOK_HOOKS_SELF_PROTECT")
    hook_edit_allowed = os.environ.get("HOOKS_EDIT_ALLOWED") or read_env("HOOKS_EDIT_ALLOWED")

    # Hook disable check (false = disabled)
    if hook_flag in ("false", "0"):
        sys.exit(0)

    # Reading JSON from stdin
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    # Pass if not Write, Edit, or Bash
    if tool_name not in ("Write", "Edit", "Bash"):
        sys.exit(0)

    tool_input = data.get("tool_input", {})

    # --- Bash tools branch ---
    if tool_name == "Bash":
        bash_cmd = tool_input.get("command", "")
        if not bash_cmd:
            sys.exit(0)

        # Passes if there is no protected path in the command
        if not _refs_protected(bash_cmd):
            sys.exit(0)

        # Environment variable bypass check
        if hook_edit_allowed in ("true", "1"):
            sys.exit(0)

        classification = _classify_bash_command(bash_cmd)
        if classification == "READONLY":
            sys.exit(0)

        # Branch blocking messages depending on whether .agent-factory/runs/bypass is referenced or not
        if re.search(r"\.claude\.workflow/workflow/bypass", bash_cmd):
            _deny(HOOKS_BYPASS_FILE_DENIED)
        else:
            _deny(HOOKS_BASH_MODIFY_DENIED)

    # --- Write/Edit tools branch ---
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Check whether .agent-factory/runs/bypass path is included
    if ".agent-factory/runs/bypass" in file_path:
        # Bypass files cannot bypass environment variables (unconditionally blocked)
        _deny(HOOKS_BYPASS_FILE_DENIED)

    # Check whether .agent-factory/hooks/ path is included
    if ".agent-factory/hooks/" in file_path:
        # Environment variable bypass check
        if hook_edit_allowed in ("true", "1"):
            sys.exit(0)

        _deny(HOOKS_WRITE_EDIT_DENIED)

    # Passes when .agent-factory/hooks/ path does not match.
    sys.exit(0)


if __name__ == "__main__":
    main()
