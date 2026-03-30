"""constants.py - 프로젝트 공통 상수 및 정적 데이터 통합 모듈.

.claude.workflow/scripts/ 하위 스크립트에서 공통 사용하는 상수, 패턴, 매핑을 한 곳에 정의합니다.
이 모듈은 순수 상수만 정의하며, 다른 모듈을 import하지 않는 leaf 모듈입니다.

주요 상수:
    C_RED, C_BLUE, ..., C_RESET: ANSI 색상 코드
    STEP_COLORS: step별 색상 매핑
    TS_PATTERN: YYYYMMDD-HHMMSS 타임스탬프 정규식
    KST: KST 타임존 (UTC+9)
    TERMINAL_STEPS: 종료 상태 집합
    FSM_TRANSITIONS: FSM 상태 전이 규칙
    DANGER_PATTERNS: 위험 명령어 차단 패턴 목록
    KEEP_COUNT: .workflow/ 디렉터리 유지 최대 갯수 (환경변수 CLAUDE_WORKFLOW_KEEP_COUNT로 오버라이드 가능)
    CHAIN_SEPARATOR: 체인 command 구분자 (">" 문자)
    CHAIN_MAX_RETRY: 체인 스테이지 실패 시 최대 재시도 횟수 (환경변수 CLAUDE_CHAIN_MAX_RETRY로 오버라이드 가능)
"""

import os
import re
from datetime import timezone, timedelta


# =============================================================================
# .settings/.env 파일 로더 — 모든 설정값의 단일 소스
# =============================================================================
def _find_project_root() -> str:
    """scripts/data/constants.py 기준으로 프로젝트 루트를 탐색한다."""
    d = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(d, '..', '..', '..'))


def _load_dotenv() -> dict[str, str]:
    """.claude.workflow/.settings(.env 폴백) 파일을 파싱하여 key=value dict로 반환한다.

    .settings를 우선 탐색하고, 없으면 .env로 폴백합니다.

    파싱 규칙:
        - '#'으로 시작하는 행은 주석으로 무시한다.
        - 빈 행은 건너뛴다.
        - '='가 없는 행은 유효한 KEY=VALUE 형식이 아니므로 건너뛴다.
        - '=' 기준 좌측이 KEY, 우측이 VALUE이다 (partition 사용으로 VALUE 안의 '='은 보존).
        - VALUE 우측의 인라인 주석(' # ...')을 제거한다.
          단, 따옴표로 감싼 값(예: KEY="val # not comment")은 '#'을 주석으로 취급하지 않는다.
        - KEY와 VALUE 양쪽 공백을 strip한다.

    우선순위 (상위가 높음):
        1. os.environ (런타임 환경변수)
        2. .settings 파일 (이 함수가 파싱, .env 폴백)
        3. 각 _env()/_env_int()/_env_float() 호출 시 전달하는 default 값

    Returns:
        dict[str, str]: KEY -> VALUE 매핑 딕셔너리
    """
    cw_dir = os.path.join(_find_project_root(), '.claude.workflow')
    settings_path = os.path.join(cw_dir, '.settings')
    env_file = settings_path if os.path.exists(settings_path) else os.path.join(cw_dir, '.env')
    result: dict[str, str] = {}
    if not os.path.exists(env_file):
        return result
    with open(env_file, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # 빈 행 또는 '#'으로 시작하는 전체 주석 행은 건너뛴다
            if not line or line.startswith('#'):
                continue
            # '='가 없으면 유효한 KEY=VALUE 형식이 아니므로 건너뛴다
            if '=' not in line:
                continue
            # partition은 첫 번째 '='만 분리하므로 VALUE 안의 '='은 보존된다
            # 예: KEY=a=b=c → key="KEY", value="a=b=c"
            key, _, value = line.partition('=')
            value = value.strip()
            # 인라인 주석 제거: 따옴표로 감싸지 않은 VALUE의 ' # ...' 패턴을 제거한다
            # 예: 30  # 비활성 판정 시간 → 30
            # 예: "hello # world"      → hello # world (따옴표 내부는 보존)
            if value and not (value.startswith('"') and value.endswith('"')) \
                      and not (value.startswith("'") and value.endswith("'")):
                # ' #' 패턴으로 분리하여 주석 부분을 제거한다
                # 공백 없는 '#'(예: C#code, color=#fff)은 값의 일부로 보존한다
                comment_idx = value.find(' #')
                if comment_idx != -1:
                    value = value[:comment_idx].rstrip()
            else:
                # 따옴표로 감싼 값은 양쪽 따옴표만 벗긴다
                value = value[1:-1]
            result[key.strip()] = value
    return result


_DOTENV = _load_dotenv()


def _env(key: str, default: str) -> str:
    """os.environ > .settings/.env > default 우선순위로 값을 반환한다."""
    return os.environ.get(key, _DOTENV.get(key, default))


def _env_int(key: str, default: int) -> int:
    return int(_env(key, str(default)))


def _env_float(key: str, default: float) -> float:
    return float(_env(key, str(default)))


# =============================================================================
# ANSI 색상 코드 상수
# =============================================================================
C_RED = "\033[0;31m"
C_BLUE = "\033[0;34m"
C_GREEN = "\033[0;32m"
C_PURPLE = "\033[0;35m"
C_YELLOW = "\033[0;33m"
C_CYAN = "\033[0;36m"
C_GRAY = "\033[0;90m"
C_CLAUDE = "\033[38;2;222;115;86m"  # Claude brand Peach #DE7356
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_RESET = "\033[0m"

# =============================================================================
# Step별 색상 매핑
# =============================================================================
STEP_COLORS = {
    "INIT": C_RED,
    "PLAN": C_BLUE,
    "WORK": C_GREEN,
    "REPORT": C_PURPLE,
    "STRATEGY": C_CYAN,
    "DONE": C_YELLOW,
    "STALE": C_GRAY,
    "FAILED": C_RED,
    "CANCELLED": C_GRAY,
}

# 하위 호환 별칭
PHASE_COLORS = STEP_COLORS

# =============================================================================
# YYYYMMDD-HHMMSS 패턴 정규식
# =============================================================================
TS_PATTERN = re.compile(r"^\d{8}-\d{6}$")

# =============================================================================
# KST 타임존 (UTC+9)
# =============================================================================
KST = timezone(timedelta(hours=9))

# =============================================================================
# 공통 타임아웃/제한값
# =============================================================================
STALE_TTL_MINUTES = _env_int("CLAUDE_STALE_TTL_MINUTES", 30)
ZOMBIE_TTL_HOURS = _env_int("CLAUDE_ZOMBIE_TTL_HOURS", 24)
REPORT_TTL_HOURS = _env_int("CLAUDE_REPORT_TTL_HOURS", 1)
KEEP_COUNT = _env_int("CLAUDE_WORKFLOW_KEEP_COUNT", 10)
WORK_NAME_MAX_LEN = _env_int("CLAUDE_WORK_NAME_MAX_LEN", 20)

# =============================================================================
# 터미널 파일명 상수
# =============================================================================
STATUS_FILENAME = "status.json"
CONTEXT_FILENAME = ".context.json"
STOP_BLOCK_COUNTER_FILENAME = ".stop-block-counter"
BYPASS_FILENAME = "bypass"
FSM_TRANSITIONS = {
    "full": {
        "INIT": ["PLAN", "STALE", "FAILED", "CANCELLED"],
        "NONE": ["PLAN", "STALE", "FAILED", "CANCELLED"],
        "PLAN": ["WORK", "STALE", "FAILED", "CANCELLED"],
        "WORK": ["REPORT", "STALE", "FAILED", "CANCELLED"],
        "REPORT": ["DONE", "STALE", "FAILED", "CANCELLED"],
    },
}

# =============================================================================
# 유효 명령어/모드 집합
# =============================================================================
VALID_COMMANDS = {"implement", "review", "research"}
VALID_MODES = {"full"}

# =============================================================================
# 체인 command 관련 상수
# =============================================================================
CHAIN_SEPARATOR = ">"
CHAIN_MAX_RETRY = _env_int("CLAUDE_CHAIN_MAX_RETRY", 2)

# =============================================================================
# 품질 검증 임계값
# =============================================================================
QUALITY_THRESHOLD = _env_float("CLAUDE_QUALITY_THRESHOLD", 0.6)

# =============================================================================
# 예산 임계치 알림 설정
# =============================================================================
BUDGET_CEILING = _env_int("BUDGET_CEILING", 0)  # 0이면 비활성
BUDGET_THRESHOLDS: dict[int, str] = {75: "INFO", 80: "WARN", 90: "HIGH", 100: "CRITICAL"}

# =============================================================================
# Hallucination 로깅 설정
# =============================================================================
HOOK_HALLUCINATION_LOGGER = _env("HOOK_HALLUCINATION_LOGGER", "true")
HALLU_TARGET_AGENT_TYPES: set[str] = {"worker", "explorer"}


def parse_chain_command(raw: str) -> list[str]:
    """체인 command 문자열을 파싱하여 세그먼트 리스트를 반환한다.

    Args:
        raw: command 문자열. 단일("implement") 또는 체인("research>implement>review") 형식.

    Returns:
        유효한 command 세그먼트 리스트. 단일 command도 길이 1 리스트로 반환.

    Raises:
        ValueError: 유효하지 않은 세그먼트가 포함된 경우.

    Note:
        중복 command 세그먼트(예: 'implement>implement')를 허용한다.
        대규모 구현을 여러 사이클로 분할하는 유스케이스를 지원하기 위한 설계 선택이다.

    Examples:
        >>> parse_chain_command("implement")
        ['implement']
        >>> parse_chain_command("research>implement>review")
        ['research', 'implement', 'review']
        >>> parse_chain_command("implement>implement")
        ['implement', 'implement']
    """
    segments = [seg.strip() for seg in raw.split(CHAIN_SEPARATOR)]
    for seg in segments:
        if seg not in VALID_COMMANDS:
            raise ValueError(
                f"유효하지 않은 command 세그먼트: '{seg}'. "
                f"허용 값: {sorted(VALID_COMMANDS)}"
            )
    return segments


# =============================================================================
# 터미널 step 집합
# =============================================================================
TERMINAL_STEPS = {"DONE", "FAILED", "STALE", "CANCELLED"}

# 하위 호환 별칭
TERMINAL_PHASES = TERMINAL_STEPS

# =============================================================================
# 바이트 단위 상수
# =============================================================================
BYTES_GB = 1073741824
BYTES_MB = 1048576
BYTES_KB = 1024

# =============================================================================
# 외부 API URL
# =============================================================================
SLACK_API_URL = _env("CLAUDE_SLACK_API_URL", "https://slack.com/api/chat.postMessage")

# =============================================================================
# 동기화 관련 상수
# =============================================================================
CODE_SYNC_REMOTE_REPO = _env("CLAUDE_REPO_URL", "https://github.com/KoreanLeeChangHyun/claude-workflow.git")
STALE_TTL_SECONDS = STALE_TTL_MINUTES * 60

# =============================================================================
# Slack 에이전트별 이모지 매핑
# =============================================================================
SLACK_EMOJI_MAP = {
    "init": ":large_orange_circle:",
    "planner": ":large_blue_circle:",
    "worker": ":large_green_circle:",
    "reporter": ":purple_circle:",
}

# =============================================================================
# 히스토리 테이블 헤더/구분선
# =============================================================================
HEADER_LINE = "| 날짜 | 작업ID | 제목 & 내용 | 명령어 | 상태 | 질의 | 파일 | 계획 | 작업 | 보고 |"
SEPARATOR_LINE = "|------|--------|------------|--------|------|------|------|------|------|------|"
SKILLS_HEADER_LINE = "| 날짜 | 작업ID | 명령어 | 태스크수 | 고유스킬수 | 스킬 목록 | fallback | 토큰초과 |"
SKILLS_SEPARATOR_LINE = "|------|--------|--------|---------|----------|----------|---------|---------|"
LOGS_HEADER_LINE = "| 날짜 | 작업ID | 제목 | 명령 | WARN | ERROR | HALLU | 크기 | 로그 |"
LOGS_SEPARATOR_LINE = "|------|--------|------|------|------|-------|------|------|------|"
USAGE_HEADER_LINE = "| 날짜 | 작업ID | 제목 | 명령 | ORC | PLN | WRK | EXP | VAL | RPT | 합계 | 예산 |"
USAGE_SEPARATOR_LINE = "|------|--------|------|------|-----|-----|-----|-----|-----|-----|------|------|"

# =============================================================================
# Step → 한글 상태 텍스트 매핑
# =============================================================================
STEP_STATUS_MAP = {
    "DONE": "완료",
    "REPORT": "진행",
    "STALE": "중단",
    "WORK": "진행",
    "STRATEGY": "진행",
    "PLAN": "진행",
    "INIT": "진행",
    "CANCELLED": "중단",
    "FAILED": "중단",
    "UNKNOWN": "불명",
    "NONE": "불명",
}

# 하위 호환 별칭
PHASE_STATUS_MAP = STEP_STATUS_MAP

# =============================================================================
# 위험 명령어 화이트리스트 (허용 패턴)
# =============================================================================
DANGER_WHITELIST = [
    {"pattern": "rm\\s+-r[f]?\\s+/tmp/", "note": None},
    {"pattern": "rm\\s+-r[f]?\\s+.*\\.workflow/", "note": None},
    {"pattern": "sudo\\s+rm\\s+-r[f]?\\s+/tmp/", "note": None},
    {"pattern": "sudo\\s+rm\\s+-r[f]?\\s+.*\\.workflow/", "note": None},
    {"pattern": "git\\s+push\\s+--force-with-lease", "note": None},
]

# =============================================================================
# 위험 명령어 차단 패턴
# =============================================================================
DANGER_PATTERNS = [
    {"pattern": "(sudo\\s+)?rm\\s+-r[f]*\\s+/\\s*$", "blocked": "rm -rf / (루트 디렉토리 삭제)", "alternative": "특정 경로를 지정하거나 rm -ri로 대화형 삭제를 사용하세요."},
    {"pattern": "(sudo\\s+)?rm\\s+--recursive\\s+(-f|--force)\\s+/\\s*$", "blocked": "rm --recursive --force / (루트 디렉토리 삭제)", "alternative": "특정 경로를 지정하거나 rm -ri로 대화형 삭제를 사용하세요."},
    {"pattern": "(sudo\\s+)?rm\\s+(-f|--force)\\s+--recursive\\s+/\\s*$", "blocked": "rm --force --recursive / (루트 디렉토리 삭제)", "alternative": "특정 경로를 지정하거나 rm -ri로 대화형 삭제를 사용하세요."},
    {"pattern": "(sudo\\s+)?rm\\s+--recursive\\s+/\\s*$", "blocked": "rm --recursive / (루트 디렉토리 삭제)", "alternative": "특정 경로를 지정하거나 rm -ri로 대화형 삭제를 사용하세요."},
    {"pattern": "(sudo\\s+)?rm\\s+-r[f]*\\s+~", "blocked": "rm -rf ~ (홈 디렉토리 삭제)", "alternative": "특정 파일/디렉토리를 지정하세요."},
    {"pattern": "(sudo\\s+)?rm\\s+--recursive(\\s+--force)?\\s+~", "blocked": "rm --recursive ~ (홈 디렉토리 삭제)", "alternative": "특정 파일/디렉토리를 지정하세요."},
    {"pattern": "(sudo\\s+)?rm\\s+-r[f]*\\s+\\.\\s*$", "blocked": "rm -rf . (현재 디렉토리 전체 삭제)", "alternative": "특정 파일/디렉토리를 지정하세요."},
    {"pattern": "(sudo\\s+)?rm\\s+--recursive(\\s+--force)?\\s+\\.\\s*$", "blocked": "rm --recursive . (현재 디렉토리 삭제)", "alternative": "특정 파일/디렉토리를 지정하세요."},
    {"pattern": "(sudo\\s+)?rm\\s+-r[f]*\\s+\\*", "blocked": "rm -rf * (와일드카드 전체 삭제)", "alternative": "특정 파일/디렉토리를 지정하거나 ls로 목록을 먼저 확인하세요."},
    {"pattern": "(sudo\\s+)?rm\\s+--recursive(\\s+--force)?\\s+\\*", "blocked": "rm --recursive * (와일드카드 삭제)", "alternative": "특정 파일/디렉토리를 지정하거나 ls로 목록을 먼저 확인하세요."},
    {"pattern": "(sudo\\s+)?git\\s+reset\\s+--hard", "blocked": "git reset --hard (커밋되지 않은 변경사항 전체 삭제)", "alternative": "git stash로 변경사항을 임시 저장하세요."},
    {"pattern": "(sudo\\s+)?git\\s+push\\s+(--force|-f)", "blocked": "git push --force (원격 히스토리 덮어쓰기)", "alternative": "git push --force-with-lease를 사용하세요."},
    {"pattern": "(sudo\\s+)?git\\s+clean\\s+-[fd]*f", "blocked": "git clean -f (추적되지 않는 파일 전체 삭제)", "alternative": "git clean -n으로 드라이런하여 삭제 대상을 먼저 확인하세요."},
    {"pattern": "(sudo\\s+)?git\\s+branch\\s+-D\\s+(main|master)", "blocked": "git branch -D main/master (주요 브랜치 강제 삭제)", "alternative": "주요 브랜치 삭제는 매우 위험합니다. 정말 필요한지 재확인하세요."},
    {"pattern": "(sudo\\s+)?git\\s+(checkout|restore)\\s+\\.\\s*$", "blocked": "git checkout/restore . (모든 변경사항 되돌리기)", "alternative": "git stash로 변경사항을 임시 저장하세요."},
    {"pattern": "(?i)(sudo\\s+)?DROP\\s+(TABLE|DATABASE)", "blocked": "DROP TABLE/DATABASE (데이터베이스/테이블 삭제)", "alternative": "백업을 먼저 수행하고, 트랜잭션 내에서 실행하세요."},
    {"pattern": "(sudo\\s+)?chmod\\s+777", "blocked": "chmod 777 (과도한 권한 부여)", "alternative": "chmod 755 또는 필요한 최소 권한만 부여하세요."},
    {"pattern": "(sudo\\s+)?chmod\\s+a\\+rwx", "blocked": "chmod a+rwx (전체 사용자에게 모든 권한 부여)", "alternative": "chmod 755 또는 필요한 최소 권한만 부여하세요."},
    {"pattern": "(sudo\\s+)?chmod\\s+o\\+w", "blocked": "chmod o+w (기타 사용자에게 쓰기 권한 부여)", "alternative": "chmod 755 또는 필요한 최소 권한만 부여하세요."},
    {"pattern": "(sudo\\s+)?chmod\\s+ugo\\+rwx", "blocked": "chmod ugo+rwx (전체 사용자에게 모든 권한 부여)", "alternative": "chmod 755 또는 필요한 최소 권한만 부여하세요."},
    {"pattern": "(sudo\\s+)?mkfs", "blocked": "mkfs (디스크 포맷)", "alternative": "디스크 포맷은 매우 위험합니다. 대상 디바이스를 재확인하세요."},
    {"pattern": "(sudo\\s+)?dd\\s+if=", "blocked": "dd if= (디스크 덮어쓰기)", "alternative": "dd 명령어는 되돌릴 수 없습니다. 대상 디바이스를 재확인하세요."},
    {"pattern": "(sudo\\s+)?rm\\s+-r[f]*\\s+.*\\.claude\\.workflow/kanban", "blocked": "rm -rf .claude.workflow/kanban (칸반 디렉터리 삭제)", "alternative": "칸반 디렉터리는 워크플로우 핵심 데이터입니다. 삭제하지 마세요."},
]

# =============================================================================
# hooks 자기보호 가드: 읽기 전용 명령어 패턴
# =============================================================================
GUARD_READONLY_PATTERNS = [
    "^\\s*git\\s", "^\\s*python3?\\s", "^\\s*node\\s", "^\\s*cat\\s",
    "^\\s*ls\\b", "^\\s*head\\s", "^\\s*tail\\s", "^\\s*wc\\s",
    "^\\s*grep\\s", "^\\s*file\\s", "^\\s*stat\\s", "^\\s*diff\\s",
    "^\\s*bash\\s", "^\\s*sh\\s", "^\\s*source\\s", "^\\s*\\.\\s",
    "^\\s*exec\\s", "^\\s*env\\s",
    "^(?:\\s*\\w+=\\S*\\s+)*(?:bash|sh|python3?|node)\\s",
    "^\\s*\\.claude\\.workflow/hooks/.*\\.sh\\b", "^\\s*/.*/\\.claude/hooks/.*\\.sh\\b",
    "^\\s*less\\s", "^\\s*more\\s", "^\\s*find\\s", "^\\s*tree\\b",
    "^\\s*realpath\\s", "^\\s*readlink\\s", "^\\s*sha256sum\\s",
    "^\\s*md5sum\\s", "^\\s*test\\s", "^\\s*\\[\\s",
]

# =============================================================================
# hooks 자기보호 가드: 수정 명령어 패턴
# =============================================================================
GUARD_MODIFY_PATTERNS = [
    "sed\\s+.*-i", "sed\\s+-i", "\\bcp\\b", "\\bmv\\b",
    "echo\\s.*>\\s*", "echo\\s.*>>\\s*", "printf\\s.*>\\s*", "printf\\s.*>>\\s*",
    "\\btee\\b", "cat\\s.*>\\s*", "cat\\s.*>>\\s*",
    "\\bdd\\b", "\\binstall\\b", "\\brsync\\b", "\\bchmod\\b", "\\bchown\\b",
    "ln\\s+-sf?\\b", "rm\\s+-rf?\\b", "rm\\s+-f\\b",
    "\\btouch\\b", "\\bmkdir\\b", "\\brmdir\\b", ">\\s*\\S", ">>\\s*\\S",
]

# =============================================================================
# hooks 자기보호 가드: 보호 경로 패턴
# =============================================================================
GUARD_PROTECTED_PATH_PATTERNS = [
    "\\.claude\\.workflow/hooks/",
    "\\.claude\\.workflow/workflow/bypass",
]

# =============================================================================
# hooks 자기보호 가드: 인라인 쓰기 패턴
# =============================================================================
GUARD_INLINE_WRITE_PATTERNS = [
    "open\\s*\\(", "write\\s*\\(", "writeFile", "writeFileSync",
    "appendFile", "appendFileSync", ">\\s*",
]
