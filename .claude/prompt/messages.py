"""messages.py - guard 스크립트 및 wf 명령어에서 사용하는 사용자 대면 메시지 상수 모듈.

이 모듈은 순수 상수만 정의하며, 다른 모듈을 import하지 않는 leaf 모듈입니다.
플레이스홀더가 있는 메시지는 .format() 메서드로 치환하여 사용합니다.

주요 상수 그룹:
    MAIN_SESSION_*: main_session_guard.py 사용 메시지
    AGENT_INVESTIGATION_*: agent_investigation_guard.py 사용 메시지
    KANBAN_*: kanban_subcommand_guard.py 사용 메시지
    HOOKS_*: hooks_self_guard.py 사용 메시지
    MAIN_BRANCH_*: main_branch_guard.py 사용 메시지
    READONLY_SESSION_*: readonly_session_guard.py 사용 메시지
"""

# =============================================================================
# main_session_guard.py 메시지
# =============================================================================

MAIN_SESSION_BASH_FILE_MODIFY_DENIED: str = (
    "메인 세션에서 Bash를 통한 파일 수정이 차단되었습니다. "
    "(매칭 패턴: {pattern}) "
    "워크플로우 세션(tmux P:T-* 윈도우)에서 작업하세요."
)
"""플레이스홀더: {pattern} - 매칭된 Bash 파일 수정 패턴 문자열."""

MAIN_SESSION_NO_TMUX_DENIED: str = (
    "비tmux 환경에서의 코드 수정이 차단되었습니다. "
    "워크플로우 세션(tmux P:T-* 윈도우)에서 작업하세요."
)

MAIN_SESSION_WINDOW_QUERY_FAILED: str = (
    "tmux 윈도우명 조회에 실패하여 코드 수정이 차단되었습니다. "
    "워크플로우 세션(tmux P:T-* 윈도우)에서 작업하세요."
)

MAIN_SESSION_WRITE_EDIT_DENIED: str = (
    "메인 세션(윈도우: {window_name})에서의 코드 수정이 차단되었습니다. "
    "워크플로우 세션(tmux P:T-* 윈도우)에서 작업하세요."
)
"""플레이스홀더: {window_name} - 현재 tmux 윈도우명."""

# =============================================================================
# agent_investigation_guard.py 메시지
# =============================================================================

AGENT_INVESTIGATION_MAIN_SESSION_DENIED: str = (
    "메인 세션에서의 조사 목적 서브에이전트(subagent_type: {subagent_type}) 호출이 차단되었습니다. "
    "워크플로우 세션(tmux P:T-* 윈도우)에서 실행하거나, 메인 에이전트가 직접 도구를 사용하여 조사하세요."
)
"""플레이스홀더: {subagent_type} - 차단된 서브에이전트 타입 문자열 (repr 포함)."""

AGENT_INVESTIGATION_WINDOW_QUERY_FAILED: str = (
    "tmux 윈도우명 조회에 실패하여 조사 목적 서브에이전트(subagent_type: {subagent_type}) 호출이 차단되었습니다. "
    "워크플로우 세션(tmux P:T-* 윈도우)에서 실행하거나, 메인 에이전트가 직접 도구를 사용하여 조사하세요."
)
"""플레이스홀더: {subagent_type} - 차단된 서브에이전트 타입 문자열 (repr 포함)."""

# =============================================================================
# kanban_subcommand_guard.py 메시지
# =============================================================================

KANBAN_INVALID_SUBCOMMAND: str = (
    "flow-kanban의 유효하지 않은 서브커맨드 '{subcommand}'가 차단되었습니다.\n"
    "유효한 서브커맨드: {valid_list}\n\n"
    "올바른 사용 예시:\n"
    "  flow-kanban move T-001 progress     # target: open|progress|review|done\n"
    "  flow-kanban update-title T-001 '새 제목'  # 제목 변경\n"
    "  flow-kanban done T-001\n"
    "  flow-kanban add-subnumber T-001 --command implement --goal '목표'\n\n"
    "'{subcommand}' 대신 위 예시를 참고하세요."
)
"""플레이스홀더: {subcommand} - 사용된 유효하지 않은 서브커맨드, {valid_list} - 허용 서브커맨드 목록.

메시지 포맷: 차단 알림 + 유효 서브커맨드 목록 + 올바른 사용 예시(move/update-title/done/add-subnumber) + 수정 안내."""

# =============================================================================
# hooks_self_guard.py 메시지
# =============================================================================

HOOKS_BYPASS_FILE_DENIED: str = (
    ".workflow/bypass 파일 생성/수정이 차단되었습니다. "
    "이 파일은 워크플로우 가드를 우회하는 보안 민감 파일입니다."
)

HOOKS_BASH_MODIFY_DENIED: str = (
    "Bash를 통한 hooks 디렉토리 파일 수정이 차단되었습니다. "
    "사용자의 명시적 수정 요청이 필요합니다."
)

HOOKS_WRITE_EDIT_DENIED: str = (
    "hooks 디렉토리 파일 수정이 차단되었습니다. "
    "사용자의 명시적 수정 요청이 필요합니다."
)

# =============================================================================
# main_branch_guard.py 메시지
# =============================================================================

MAIN_BRANCH_COMMIT_DENIED: str = (
    "main/master 브랜치({branch})에서 직접 커밋이 차단되었습니다. "
    "피처 브랜치를 생성하여 작업하세요."
)
"""플레이스홀더: {branch} - 현재 브랜치명."""

# =============================================================================
# readonly_session_guard.py 메시지
# =============================================================================

READONLY_SESSION_WRITE_EDIT_DENIED: str = (
    "research/review 워크플로우 세션에서는 코드 수정(Write/Edit)이 금지되어 있습니다. "
    "보고서에 수정 방안을 기술하세요."
)

READONLY_SESSION_BASH_MODIFY_DENIED: str = (
    "research/review 워크플로우 세션에서는 Bash를 통한 파일 수정이 금지되어 있습니다. "
    "보고서에 수정 방안을 기술하세요."
)
