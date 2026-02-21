#!/usr/bin/env -S python3 -u
"""
hooks 디렉토리 자기 보호 가드 Hook 스크립트

PreToolUse(Write|Edit|Bash) 이벤트에서 .claude/hooks/ 경로 파일 수정을 차단.

입력: stdin으로 JSON (tool_name, tool_input)
출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력

우회: 환경변수 HOOK_EDIT_ALLOWED=true 설정 시 차단 해제
      (오케스트레이터가 `python3 .claude/scripts/state/update_state.py env <registryKey> set HOOK_EDIT_ALLOWED true` 명령으로 설정/해제)
"""

import json
import os
import re
import sys

# utils 패키지 import 경로 설정
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from utils.env_utils import read_env


def _deny(reason):
    """차단 JSON을 출력하고 종료."""
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


# 읽기 전용 명령 패턴 화이트리스트
READONLY_PATTERNS = [
    r"^\s*git\s",
    r"^\s*python3?\s",
    r"^\s*node\s",
    r"^\s*cat\s",
    r"^\s*ls\b",
    r"^\s*head\s",
    r"^\s*tail\s",
    r"^\s*wc\s",
    r"^\s*grep\s",
    r"^\s*file\s",
    r"^\s*stat\s",
    r"^\s*diff\s",
    r"^\s*bash\s",
    r"^\s*sh\s",
    r"^\s*source\s",
    r"^\s*\.\s",
    r"^\s*exec\s",
    r"^\s*env\s",
    r"^(?:\s*\w+=\S*\s+)*(?:bash|sh|python3?|node)\s",
    r"^\s*\.claude/hooks/.*\.sh\b",
    r"^\s*/.*/\.claude/hooks/.*\.sh\b",
    r"^\s*less\s",
    r"^\s*more\s",
    r"^\s*find\s",
    r"^\s*tree\b",
    r"^\s*realpath\s",
    r"^\s*readlink\s",
    r"^\s*sha256sum\s",
    r"^\s*md5sum\s",
    r"^\s*test\s",
    r"^\s*\[\s",
]

# 수정 가능 패턴 (이 패턴이 보호 대상 경로를 타겟으로 하면 차단)
MODIFY_PATTERNS = [
    r"sed\s+.*-i",
    r"sed\s+-i",
    r"\bcp\b",
    r"\bmv\b",
    r"echo\s.*>\s*",
    r"echo\s.*>>\s*",
    r"printf\s.*>\s*",
    r"printf\s.*>>\s*",
    r"\btee\b",
    r"cat\s.*>\s*",
    r"cat\s.*>>\s*",
    r"\bdd\b",
    r"\binstall\b",
    r"\brsync\b",
    r"\bchmod\b",
    r"\bchown\b",
    r"ln\s+-sf?\b",
    r"rm\s+-rf?\b",
    r"rm\s+-f\b",
    r"\btouch\b",
    r"\bmkdir\b",
    r"\brmdir\b",
    r">\s*\S",
    r">>\s*\S",
]

# 보호 대상 경로 패턴
PROTECTED_PATH_RES = [
    re.compile(r"\.claude/hooks/"),
    re.compile(r"\.workflow/bypass"),
]

# 인라인 코드 쓰기 패턴
INLINE_WRITE_PATTERNS = [
    r"open\s*\(",
    r"write\s*\(",
    r"writeFile",
    r"writeFileSync",
    r"appendFile",
    r"appendFileSync",
    r">\s*",
]


def _refs_protected(text):
    """텍스트가 보호 대상 경로를 참조하는지 확인."""
    for p_re in PROTECTED_PATH_RES:
        if p_re.search(text):
            return True
    return False


def _check_inline_write(subcmd):
    """인라인 코드(-c/-e 플래그) 내에서 보호 대상 경로에 대한 쓰기를 탐지."""
    if not re.search(r"\s+-(c|e)\s", subcmd):
        return False
    if not _refs_protected(subcmd):
        return False
    for wp in INLINE_WRITE_PATTERNS:
        if re.search(wp, subcmd):
            return True
    return False


def _classify_bash_command(bash_cmd):
    """
    Bash 명령을 분류: 'READONLY' 또는 'MODIFY' 반환.

    보호 대상 경로를 참조하지 않으면 None (통과).
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


def main():
    # .claude.env에서 설정 로드
    hook_flag = os.environ.get("HOOK_HOOKS_SELF_PROTECT") or read_env("HOOK_HOOKS_SELF_PROTECT")
    hook_edit_allowed = os.environ.get("HOOK_EDIT_ALLOWED") or read_env("HOOK_EDIT_ALLOWED")

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

        # .workflow/bypass 참조 여부에 따라 차단 메시지 분기
        if re.search(r"\.workflow/bypass", bash_cmd):
            _deny(
                ".workflow/bypass 파일 생성/수정이 차단되었습니다. "
                "이 파일은 워크플로우 가드를 우회하는 보안 민감 파일입니다."
            )
        else:
            _deny(
                "Bash를 통한 hooks 디렉토리 파일 수정이 차단되었습니다. "
                "사용자의 명시적 수정 요청이 필요합니다."
            )

    # --- Write / Edit 도구 분기 ---
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # .workflow/bypass 경로 포함 여부 검사
    if ".workflow/bypass" in file_path:
        # bypass 파일은 환경변수 우회 불가 (무조건 차단)
        _deny(
            ".workflow/bypass 파일 생성/수정이 차단되었습니다. "
            "이 파일은 워크플로우 가드를 우회하는 보안 민감 파일입니다."
        )

    # .claude/hooks/ 경로 포함 여부 검사
    if ".claude/hooks/" in file_path:
        # 환경변수 우회 검사
        if hook_edit_allowed in ("true", "1"):
            sys.exit(0)

        _deny(
            "hooks 디렉토리 파일 수정이 차단되었습니다. "
            "사용자의 명시적 수정 요청이 필요합니다."
        )

    # .claude/hooks/ 경로 미매칭 시 통과
    sys.exit(0)


if __name__ == "__main__":
    main()
