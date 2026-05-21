"""messages.py - User-facing message constants module used by guard scripts.

This module is a leaf module that defines only pure constants and does not import any other modules.
Messages with placeholders are used by replacing them with the .format() method.

Main constant groups:
    MAIN_SESSION_*: messages using main_session_guard.py
    AGENT_INVESTIGATION_*: message using agent_investigation_guard.py
    CONVEYOR_*: conveyor_subcommand_guard.py usage messages
    HOOKS_*: hooks_self_guard.py usage message
    MAIN_BRANCH_*: main_branch_guard.py usage messages
    READONLY_SESSION_*: messages using readonly_session_guard.py
    DIRECT_PATH_*: messages using direct_path_guard.py
    WORKTREE_PATH_*: worktree_path_guard.py usage message
    WORKTREE_REMOVE_*: Messages using worktree_remove_guard.py
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
# conveyor_subcommand_guard.py message
# =============================================================================

CONVEYOR_INVALID_SUBCOMMAND: str = (
    "The invalid subcommand '{subcommand}' of flow-conveyor was blocked. \n"
    "Valid subcommands: {valid_list} \n \n"
    "Correct usage example: \n"
    "  flow-conveyor move WR-001 executing     # target: draft|accepted|executing|verifying|complete\n"
    "flow-conveyor update-title WR-001 'New title' # Change title \n"
    "  flow-conveyor complete WR-001\n"
    "flow-conveyor update-prompt WR-001 --goal 'goal' # Update prompt field \n \n"
    "Please refer to the example above instead of '{subcommand}'."
)
"""Placeholders: {subcommand} - invalid subcommands used, {valid_list} - list of allowed subcommands.

Message format: Block notification + list of valid subcommands + examples of correct use (move/update-title/complete/update-prompt) + modification instructions."""

CONVEYOR_SUBMIT_REMOVED: str = (
    "Submit step has been removed (T-399)."
    "To move the Accepted card directly to Executing, use the DnD + confirm modal in the board UI."
    "(POST /api/conveyor/submit) or use /wf -s N."
    "Only level 5 FSM (Draft → Accepted → Executing → Verifying → Complete) is valid."
)
"""flow-conveyor move WR-NNN submit call blocking message (T-399). For guarding after removing the Submit transient phase."""

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
    "Code modification (Write/Edit) is prohibited in research/verifying workflow sessions."
    "Describe your proposed corrections in your report."
)

READONLY_SESSION_BASH_MODIFY_DENIED: str = (
    "Modifying files via Bash is prohibited in research/verifying workflow sessions."
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
"""Placeholder:
    {worktree_path} - Absolute worktree path (e.g. /home/.../worktrees/feat-WR-NNN-...)
    {file_path} - Absolute path to blocked file
    {suggested_path} - Corresponding path in the work tree (recommended path based on file name)
"""

WORKTREE_PATH_BASH_MODIFY_DENIED: str = (
    "[Worktree Isolation Violation] A file modification command was detected in the main repo path. \n"
    "Operate on the worktree path: {worktree_path} \n"
    "Run the command after cd {worktree_path}."
)
"""Placeholder:
    {worktree_path} - Absolute worktree path (e.g. /home/.../worktrees/feat-WR-NNN-...)
"""

# =============================================================================
# worktree_remove_guard.py message
# =============================================================================

WORKTREE_REMOVE_UNCOMMITTED_DENIED: str = (
    "This is a worktree with uncommitted changes. Complete with the normal path using flow-merge."
)
