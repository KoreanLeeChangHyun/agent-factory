"""messages.py - guard 스크립트에서 사용하는 사용자 대면 메시지 상수 모듈.

이 모듈은 순수 상수만 정의하며, 다른 모듈을 import하지 않는 leaf 모듈입니다.
플레이스홀더가 있는 메시지는 .format() 메서드로 치환하여 사용합니다.

주요 상수 그룹:
    MAIN_SESSION_*: main_session_guard.py 사용 메시지
    AGENT_INVESTIGATION_*: agent_investigation_guard.py 사용 메시지
    KANBAN_*: kanban_subcommand_guard.py 사용 메시지
    HOOKS_*: hooks_self_guard.py 사용 메시지
    MAIN_BRANCH_*: main_branch_guard.py 사용 메시지
    READONLY_SESSION_*: readonly_session_guard.py 사용 메시지
    DIRECT_PATH_*: direct_path_guard.py 사용 메시지
    WORKTREE_PATH_*: worktree_path_guard.py 사용 메시지
    WORKTREE_REMOVE_*: worktree_remove_guard.py 사용 메시지
"""

from __future__ import annotations

# =============================================================================
# main_session_guard.py message
# =============================================================================

MAIN_SESSION_BASH_FILE_MODIFY_DENIED: str = (
    "Modifying files via Bash in the main session is blocked."
    "(Matching pattern: {pattern})"
    "Work in a workflow session (_WF_SESSION_TYPE=workflow)."
)
"""Placeholders: {pattern} - Matched Bash file modification pattern string."""

MAIN_SESSION_NO_TMUX_DENIED: str = (
    "Code modifications in non-workflow environments are blocked."
    "Work in a workflow session (_WF_SESSION_TYPE=workflow)."
)

MAIN_SESSION_WINDOW_QUERY_FAILED: str = (
    "Code modification was blocked because session type determination failed."
    "Work in a workflow session (_WF_SESSION_TYPE=workflow)."
)

MAIN_SESSION_WRITE_EDIT_DENIED: str = (
    "Code modification in the main session (window: {window_name}) is blocked."
    "Work in a workflow session (_WF_SESSION_TYPE=workflow)."
)
"""Placeholder: {window_name} - Current session identifier."""

# =============================================================================
# agent_investigation_guard.py message
# =============================================================================

AGENT_INVESTIGATION_MAIN_SESSION_DENIED: str = (
    "A call to the investigative subagent (subagent_type: {subagent_type}) in the main session was blocked."
    "Run it in a workflow session (_WF_SESSION_TYPE=workflow), or have the main agent investigate directly using the tool."
)
"""Placeholders: {subagent_type} - Blocked subagent type string (including repr)."""

AGENT_INVESTIGATION_WINDOW_QUERY_FAILED: str = (
    "A call to the investigative subagent (subagent_type: {subagent_type}) was blocked because session type determination failed."
    "Run it in a workflow session (_WF_SESSION_TYPE=workflow), or have the main agent investigate directly using the tool."
)
"""Placeholders: {subagent_type} - Blocked subagent type string (including repr)."""

# =============================================================================
# kanban_subcommand_guard.py message
# =============================================================================

KANBAN_INVALID_SUBCOMMAND: str = (
    "The invalid subcommand '{subcommand}' of flow-kanban was blocked. \n"
    "Valid subcommands: {valid_list} \n \n"
    "Correct usage example: \n"
    "  flow-kanban move T-001 progress     # target: open|progress|review|done\n"
    "flow-kanban update-title T-001 'New title' # Change title \n"
    "  flow-kanban done T-001\n"
    "flow-kanban update-prompt T-001 --goal 'goal' # Update prompt field \n \n"
    "Please refer to the example above instead of '{subcommand}'."
)
"""플레이스홀더: {subcommand} - 사용된 유효하지 않은 서브커맨드, {valid_list} - 허용 서브커맨드 목록.

메시지 포맷: 차단 알림 + 유효 서브커맨드 목록 + 올바른 사용 예시(move/update-title/done/update-prompt) + 수정 안내."""

KANBAN_SUBMIT_REMOVED: str = (
    "Submit step has been removed (T-399)."
    "To move the Open card directly to In Progress, use the DnD + confirm modal in the board UI."
    "(POST /api/kanban/submit) or use /wf -s N."
    "Only level 5 FSM (To Do → Open → In Progress → Review → Done) is valid."
)
"""flow-kanban move T-NNN submit call blocking message (T-399). For guarding after removing the Submit transient phase."""

# =============================================================================
# hooks_self_guard.py message
# =============================================================================

HOOKS_BYPASS_FILE_DENIED: str = (
    "Creation/modification of .agent-factory/runs/bypass file blocked."
    "This file is a security-sensitive file that bypasses workflow guards."
)

HOOKS_BASH_MODIFY_DENIED: str = (
    "Modification of hooks directory file via Bash is blocked."
    "Requires explicit modification request from user."
)

HOOKS_WRITE_EDIT_DENIED: str = (
    "Modification of hooks directory file was blocked."
    "Requires explicit modification request from user."
)

# =============================================================================
# main_branch_guard.py message
# =============================================================================

MAIN_BRANCH_COMMIT_DENIED: str = (
    "Direct commits blocked on main/master branch ({branch})."
    "Create feature branches to work on."
)
"""Placeholder: {branch} - Current branch name."""

# =============================================================================
# readonly_session_guard.py message
# =============================================================================

READONLY_SESSION_WRITE_EDIT_DENIED: str = (
    "Code modification (Write/Edit) is prohibited in research/review workflow sessions."
    "Describe your proposed corrections in your report."
)

READONLY_SESSION_BASH_MODIFY_DENIED: str = (
    "Modifying files via Bash is prohibited in research/review workflow sessions."
    "Describe your proposed corrections in your report."
)

# =============================================================================
# direct_path_guard.py message
# =============================================================================

DIRECT_PATH_CALL_DENIED: str = (
    "python3 direct path call blocked \n"
    "Use alias '{alias_name}' instead of '{script_name}'."
)
"""Placeholders: {script_name} - blocked script file name, {alias_name} - alternative alias name."""

# =============================================================================
# worktree_path_guard.py message
# =============================================================================

WORKTREE_PATH_WRITE_EDIT_DENIED: str = (
    "[Worktree isolation violation] Cannot modify directly in the main repo path. \n"
    "Use the worktree path: {worktree_path} \n"
    "Current file: {file_path} \n"
    "Path in worktree: {suggested_path}"
)
"""플레이스홀더:
    {worktree_path}   - 워크트리 절대경로 (예: /home/.../worktrees/feat-T-NNN-...)
    {file_path}       - 차단된 파일 절대경로
    {suggested_path}  - 워크트리 내 대응 경로 (파일명 기준 추천 경로)
"""

WORKTREE_PATH_BASH_MODIFY_DENIED: str = (
    "[Worktree Isolation Violation] A file modification command was detected in the main repo path. \n"
    "Operate on the worktree path: {worktree_path} \n"
    "Run the command after cd {worktree_path}."
)
"""플레이스홀더:
    {worktree_path} - 워크트리 절대경로 (예: /home/.../worktrees/feat-T-NNN-...)
"""

# =============================================================================
# worktree_remove_guard.py message
# =============================================================================

WORKTREE_REMOVE_UNCOMMITTED_DENIED: str = (
    "This is a worktree with uncommitted changes. Complete with the normal path using flow-merge."
)
