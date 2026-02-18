#!/usr/bin/env -S python3 -u
"""
위험한 명령어 차단 Hook 스크립트

PreToolUse(Bash) 이벤트에서 위험 명령어 패턴 매칭 후 차단.

입력: stdin으로 JSON (tool_name, tool_input)
출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력
"""

import json
import os
import re
import sys

# _utils 패키지 import 경로 설정
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from _utils.env_utils import read_env


def _deny(blocked, alternative):
    """차단 JSON을 출력하고 종료."""
    reason = f"위험한 명령어가 감지되었습니다: {blocked}. 안전한 대안: {alternative}"
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


# 화이트리스트 패턴 (안전한 패턴은 통과)
WHITELIST_PATTERNS = [
    (r"rm\s+-r[f]?\s+/tmp/", None),
    (r"rm\s+-r[f]?\s+.*\.workflow/", None),
    (r"sudo\s+rm\s+-r[f]?\s+/tmp/", None),
    (r"sudo\s+rm\s+-r[f]?\s+.*\.workflow/", None),
    (r"git\s+push\s+--force-with-lease", None),
]

# 위험 패턴 목록: (regex_pattern, blocked_msg, alternative_msg)
DANGER_PATTERNS = [
    # 1. rm -rf / (루트 삭제)
    (
        r"(sudo\s+)?rm\s+-r[f]*\s+/\s*$",
        "rm -rf / (루트 디렉토리 삭제)",
        "특정 경로를 지정하거나 rm -ri로 대화형 삭제를 사용하세요.",
    ),
    # 1b. rm --recursive / (장형 옵션 루트 삭제 - 모든 조합)
    (
        r"(sudo\s+)?rm\s+--recursive\s+(-f|--force)\s+/\s*$",
        "rm --recursive --force / (루트 디렉토리 삭제)",
        "특정 경로를 지정하거나 rm -ri로 대화형 삭제를 사용하세요.",
    ),
    # 1c. rm -f/--force --recursive / (역순 장형 옵션 루트 삭제)
    (
        r"(sudo\s+)?rm\s+(-f|--force)\s+--recursive\s+/\s*$",
        "rm --force --recursive / (루트 디렉토리 삭제)",
        "특정 경로를 지정하거나 rm -ri로 대화형 삭제를 사용하세요.",
    ),
    # 1d. rm --recursive / (장형 옵션, --force 없이)
    (
        r"(sudo\s+)?rm\s+--recursive\s+/\s*$",
        "rm --recursive / (루트 디렉토리 삭제)",
        "특정 경로를 지정하거나 rm -ri로 대화형 삭제를 사용하세요.",
    ),
    # 2. rm -rf ~ (홈 디렉토리 삭제)
    (
        r"(sudo\s+)?rm\s+-r[f]*\s+~",
        "rm -rf ~ (홈 디렉토리 삭제)",
        "특정 파일/디렉토리를 지정하세요.",
    ),
    # 2b. rm --recursive ~ (장형 옵션 홈 디렉토리 삭제)
    (
        r"(sudo\s+)?rm\s+--recursive(\s+--force)?\s+~",
        "rm --recursive ~ (홈 디렉토리 삭제)",
        "특정 파일/디렉토리를 지정하세요.",
    ),
    # 3. rm -rf . (현재 디렉토리 전체 삭제)
    (
        r"(sudo\s+)?rm\s+-r[f]*\s+\.\s*$",
        "rm -rf . (현재 디렉토리 전체 삭제)",
        "특정 파일/디렉토리를 지정하세요.",
    ),
    # 3b. rm --recursive . (장형 옵션 현재 디렉토리 삭제)
    (
        r"(sudo\s+)?rm\s+--recursive(\s+--force)?\s+\.\s*$",
        "rm --recursive . (현재 디렉토리 전체 삭제)",
        "특정 파일/디렉토리를 지정하세요.",
    ),
    # 4. rm -rf * (와일드카드 전체 삭제)
    (
        r"(sudo\s+)?rm\s+-r[f]*\s+\*",
        "rm -rf * (와일드카드 전체 삭제)",
        "특정 파일/디렉토리를 지정하거나 ls로 목록을 먼저 확인하세요.",
    ),
    # 4b. rm --recursive * (장형 옵션 와일드카드 삭제)
    (
        r"(sudo\s+)?rm\s+--recursive(\s+--force)?\s+\*",
        "rm --recursive * (와일드카드 전체 삭제)",
        "특정 파일/디렉토리를 지정하거나 ls로 목록을 먼저 확인하세요.",
    ),
    # 5. git reset --hard
    (
        r"(sudo\s+)?git\s+reset\s+--hard",
        "git reset --hard (커밋되지 않은 변경사항 전체 삭제)",
        "git stash로 변경사항을 임시 저장하세요.",
    ),
    # 6. git push --force / git push -f (--force-with-lease 제외)
    (
        r"(sudo\s+)?git\s+push\s+(--force|-f)",
        "git push --force (원격 히스토리 덮어쓰기)",
        "git push --force-with-lease를 사용하세요.",
    ),
    # 7. git clean -f / git clean -fd
    (
        r"(sudo\s+)?git\s+clean\s+-[fd]*f",
        "git clean -f (추적되지 않는 파일 전체 삭제)",
        "git clean -n으로 드라이런하여 삭제 대상을 먼저 확인하세요.",
    ),
    # 8. git branch -D main/master
    (
        r"(sudo\s+)?git\s+branch\s+-D\s+(main|master)",
        "git branch -D main/master (주요 브랜치 강제 삭제)",
        "주요 브랜치 삭제는 매우 위험합니다. 정말 필요한지 재확인하세요.",
    ),
    # 9. git checkout . / git restore .
    (
        r"(sudo\s+)?git\s+(checkout|restore)\s+\.\s*$",
        "git checkout/restore . (모든 변경사항 되돌리기)",
        "git stash로 변경사항을 임시 저장하세요.",
    ),
    # 10. DROP TABLE / DROP DATABASE (대소문자 무시)
    (
        r"(?i)(sudo\s+)?DROP\s+(TABLE|DATABASE)",
        "DROP TABLE/DATABASE (데이터베이스/테이블 삭제)",
        "백업을 먼저 수행하고, 트랜잭션 내에서 실행하세요.",
    ),
    # 11. chmod 777
    (
        r"(sudo\s+)?chmod\s+777",
        "chmod 777 (과도한 권한 부여)",
        "chmod 755 또는 필요한 최소 권한만 부여하세요.",
    ),
    # 11b. chmod a+rwx
    (
        r"(sudo\s+)?chmod\s+a\+rwx",
        "chmod a+rwx (전체 사용자에게 모든 권한 부여)",
        "chmod 755 또는 필요한 최소 권한만 부여하세요.",
    ),
    # 11c. chmod o+w
    (
        r"(sudo\s+)?chmod\s+o\+w",
        "chmod o+w (기타 사용자에게 쓰기 권한 부여)",
        "chmod 755 또는 필요한 최소 권한만 부여하세요.",
    ),
    # 11d. chmod ugo+rwx
    (
        r"(sudo\s+)?chmod\s+ugo\+rwx",
        "chmod ugo+rwx (전체 사용자에게 모든 권한 부여)",
        "chmod 755 또는 필요한 최소 권한만 부여하세요.",
    ),
    # 12. mkfs (디스크 포맷)
    (
        r"(sudo\s+)?mkfs",
        "mkfs (디스크 포맷)",
        "디스크 포맷은 매우 위험합니다. 대상 디바이스를 재확인하세요.",
    ),
    # 13. dd if= (디스크 덮어쓰기)
    (
        r"(sudo\s+)?dd\s+if=",
        "dd if= (디스크 덮어쓰기)",
        "dd 명령어는 되돌릴 수 없습니다. 대상 디바이스를 재확인하세요.",
    ),
]


def main():
    # .claude.env에서 설정 로드
    guard_dangerous = os.environ.get("GUARD_DANGEROUS_COMMAND") or read_env("GUARD_DANGEROUS_COMMAND")

    # Guard disable check
    if guard_dangerous == "0":
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

    # 화이트리스트 검사 (안전한 패턴은 통과)
    for wl_pattern, _ in WHITELIST_PATTERNS:
        if re.search(wl_pattern, command):
            sys.exit(0)

    # 위험 패턴 검사
    for pattern, blocked, alternative in DANGER_PATTERNS:
        if re.search(pattern, command):
            _deny(blocked, alternative)

    # 위험 패턴 미매칭 시 통과
    sys.exit(0)


if __name__ == "__main__":
    main()
