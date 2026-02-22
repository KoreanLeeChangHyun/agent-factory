"""
danger_patterns.py - 위험 명령어 패턴 - 화이트리스트 및 차단 규칙 정의

dangerous_command_guard에서 사용하는 위험 명령어 탐지 패턴을 정의합니다.
WHITELIST는 허용되는 안전한 명령어 패턴, DANGER_PATTERNS는 차단 대상 위험 명령어 패턴입니다.
이 모듈은 순수 상수만 정의하며, 다른 모듈을 import하지 않는 leaf 모듈입니다.

카테고리:
    화이트리스트  - WHITELIST (5개 항목)
    차단 패턴     - DANGER_PATTERNS (22개 항목)
"""

# =============================================================================
# 화이트리스트 - 허용되는 명령어 패턴
# =============================================================================
WHITELIST = [
    {"pattern": "rm\\s+-r[f]?\\s+/tmp/", "note": None},                # /tmp/ 하위 재귀 삭제 허용
    {"pattern": "rm\\s+-r[f]?\\s+.*\\.workflow/", "note": None},        # .workflow/ 하위 재귀 삭제 허용
    {"pattern": "sudo\\s+rm\\s+-r[f]?\\s+/tmp/", "note": None},        # sudo /tmp/ 하위 재귀 삭제 허용
    {"pattern": "sudo\\s+rm\\s+-r[f]?\\s+.*\\.workflow/", "note": None},  # sudo .workflow/ 하위 재귀 삭제 허용
    {"pattern": "git\\s+push\\s+--force-with-lease", "note": None},     # force-with-lease push 허용
]

# =============================================================================
# 차단 패턴 - 위험 명령어 탐지 규칙
# =============================================================================
DANGER_PATTERNS = [
    {  # rm -rf / (루트 디렉토리 삭제)
        "pattern": "(sudo\\s+)?rm\\s+-r[f]*\\s+/\\s*$",
        "blocked": "rm -rf / (루트 디렉토리 삭제)",
        "alternative": "특정 경로를 지정하거나 rm -ri로 대화형 삭제를 사용하세요.",
    },
    {  # rm --recursive --force / (루트 디렉토리 삭제)
        "pattern": "(sudo\\s+)?rm\\s+--recursive\\s+(-f|--force)\\s+/\\s*$",
        "blocked": "rm --recursive --force / (루트 디렉토리 삭제)",
        "alternative": "특정 경로를 지정하거나 rm -ri로 대화형 삭제를 사용하세요.",
    },
    {  # rm --force --recursive / (루트 디렉토리 삭제)
        "pattern": "(sudo\\s+)?rm\\s+(-f|--force)\\s+--recursive\\s+/\\s*$",
        "blocked": "rm --force --recursive / (루트 디렉토리 삭제)",
        "alternative": "특정 경로를 지정하거나 rm -ri로 대화형 삭제를 사용하세요.",
    },
    {  # rm --recursive / (루트 디렉토리 삭제)
        "pattern": "(sudo\\s+)?rm\\s+--recursive\\s+/\\s*$",
        "blocked": "rm --recursive / (루트 디렉토리 삭제)",
        "alternative": "특정 경로를 지정하거나 rm -ri로 대화형 삭제를 사용하세요.",
    },
    {  # rm -rf ~ (홈 디렉토리 삭제)
        "pattern": "(sudo\\s+)?rm\\s+-r[f]*\\s+~",
        "blocked": "rm -rf ~ (홈 디렉토리 삭제)",
        "alternative": "특정 파일/디렉토리를 지정하세요.",
    },
    {  # rm --recursive ~ (홈 디렉토리 삭제)
        "pattern": "(sudo\\s+)?rm\\s+--recursive(\\s+--force)?\\s+~",
        "blocked": "rm --recursive ~ (홈 디렉토리 삭제)",
        "alternative": "특정 파일/디렉토리를 지정하세요.",
    },
    {  # rm -rf . (현재 디렉토리 전체 삭제)
        "pattern": "(sudo\\s+)?rm\\s+-r[f]*\\s+\\.\\s*$",
        "blocked": "rm -rf . (현재 디렉토리 전체 삭제)",
        "alternative": "특정 파일/디렉토리를 지정하세요.",
    },
    {  # rm --recursive . (현재 디렉토리 삭제)
        "pattern": "(sudo\\s+)?rm\\s+--recursive(\\s+--force)?\\s+\\.\\s*$",
        "blocked": "rm --recursive . (현재 디렉토리 삭제)",
        "alternative": "특정 파일/디렉토리를 지정하세요.",
    },
    {  # rm -rf * (와일드카드 전체 삭제)
        "pattern": "(sudo\\s+)?rm\\s+-r[f]*\\s+\\*",
        "blocked": "rm -rf * (와일드카드 전체 삭제)",
        "alternative": "특정 파일/디렉토리를 지정하거나 ls로 목록을 먼저 확인하세요.",
    },
    {  # rm --recursive * (와일드카드 삭제)
        "pattern": "(sudo\\s+)?rm\\s+--recursive(\\s+--force)?\\s+\\*",
        "blocked": "rm --recursive * (와일드카드 삭제)",
        "alternative": "특정 파일/디렉토리를 지정하거나 ls로 목록을 먼저 확인하세요.",
    },
    {  # git reset --hard (커밋되지 않은 변경사항 전체 삭제)
        "pattern": "(sudo\\s+)?git\\s+reset\\s+--hard",
        "blocked": "git reset --hard (커밋되지 않은 변경사항 전체 삭제)",
        "alternative": "git stash로 변경사항을 임시 저장하세요.",
    },
    {  # git push --force (원격 히스토리 덮어쓰기)
        "pattern": "(sudo\\s+)?git\\s+push\\s+(--force|-f)",
        "blocked": "git push --force (원격 히스토리 덮어쓰기)",
        "alternative": "git push --force-with-lease를 사용하세요.",
    },
    {  # git clean -f (추적되지 않는 파일 전체 삭제)
        "pattern": "(sudo\\s+)?git\\s+clean\\s+-[fd]*f",
        "blocked": "git clean -f (추적되지 않는 파일 전체 삭제)",
        "alternative": "git clean -n으로 드라이런하여 삭제 대상을 먼저 확인하세요.",
    },
    {  # git branch -D main/master (주요 브랜치 강제 삭제)
        "pattern": "(sudo\\s+)?git\\s+branch\\s+-D\\s+(main|master)",
        "blocked": "git branch -D main/master (주요 브랜치 강제 삭제)",
        "alternative": "주요 브랜치 삭제는 매우 위험합니다. 정말 필요한지 재확인하세요.",
    },
    {  # git checkout/restore . (모든 변경사항 되돌리기)
        "pattern": "(sudo\\s+)?git\\s+(checkout|restore)\\s+\\.\\s*$",
        "blocked": "git checkout/restore . (모든 변경사항 되돌리기)",
        "alternative": "git stash로 변경사항을 임시 저장하세요.",
    },
    {  # DROP TABLE/DATABASE (데이터베이스/테이블 삭제)
        "pattern": "(?i)(sudo\\s+)?DROP\\s+(TABLE|DATABASE)",
        "blocked": "DROP TABLE/DATABASE (데이터베이스/테이블 삭제)",
        "alternative": "백업을 먼저 수행하고, 트랜잭션 내에서 실행하세요.",
    },
    {  # chmod 777 (과도한 권한 부여)
        "pattern": "(sudo\\s+)?chmod\\s+777",
        "blocked": "chmod 777 (과도한 권한 부여)",
        "alternative": "chmod 755 또는 필요한 최소 권한만 부여하세요.",
    },
    {  # chmod a+rwx (전체 사용자에게 모든 권한 부여)
        "pattern": "(sudo\\s+)?chmod\\s+a\\+rwx",
        "blocked": "chmod a+rwx (전체 사용자에게 모든 권한 부여)",
        "alternative": "chmod 755 또는 필요한 최소 권한만 부여하세요.",
    },
    {  # chmod o+w (기타 사용자에게 쓰기 권한 부여)
        "pattern": "(sudo\\s+)?chmod\\s+o\\+w",
        "blocked": "chmod o+w (기타 사용자에게 쓰기 권한 부여)",
        "alternative": "chmod 755 또는 필요한 최소 권한만 부여하세요.",
    },
    {  # chmod ugo+rwx (전체 사용자에게 모든 권한 부여)
        "pattern": "(sudo\\s+)?chmod\\s+ugo\\+rwx",
        "blocked": "chmod ugo+rwx (전체 사용자에게 모든 권한 부여)",
        "alternative": "chmod 755 또는 필요한 최소 권한만 부여하세요.",
    },
    {  # mkfs (디스크 포맷)
        "pattern": "(sudo\\s+)?mkfs",
        "blocked": "mkfs (디스크 포맷)",
        "alternative": "디스크 포맷은 매우 위험합니다. 대상 디바이스를 재확인하세요.",
    },
    {  # dd if= (디스크 덮어쓰기)
        "pattern": "(sudo\\s+)?dd\\s+if=",
        "blocked": "dd if= (디스크 덮어쓰기)",
        "alternative": "dd 명령어는 되돌릴 수 없습니다. 대상 디바이스를 재확인하세요.",
    },
]
