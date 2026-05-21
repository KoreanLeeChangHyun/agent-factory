"""worktree_manager.py - Git worktree isolated execution management module.

Create/delete independent git worktrees for each workflow and create feature branches
Provides the function to merge into develop. Depends on branch_strategy.py.

Data class:
    WorktreeInfo: worktree metadata
    MergeResult: merge result

Public API:
    is_worktree_enabled: Determines whether worktree functionality is enabled
    create_worktree: Create worktree for ticket
    has_uncommitted_changes: Checks for uncommitted changes in the worktree path.
    count_feature_branch_commits: Returns the number of commits in the feature branch (detection of missing worker commits)
    remove_worktree: Remove worktree (idempotent)
    merge_to_develop: Merge feature branch into develop
    list_worktrees: List of active worktrees
    get_worktree_path: Look up the worktree path associated with the ticket.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

# ─── sys.path guaranteed ───────────────────────────────────────────────────────────────

_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
_agent_factory_dir: str = os.path.dirname(_engine_dir)
if _agent_factory_dir not in sys.path:
    sys.path.insert(0, _agent_factory_dir)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from engine.adapters.git.cli import run_git
from engine.core.worktrees.paths import (
    merge_lock_path,
    normalize_ticket_number,
    worktree_dir_name,
    worktree_path_for_branch,
    worktrees_base_dir,
)

from common import acquire_lock, read_env, release_lock, resolve_project_root
from flow.branch_strategy import (
    create_feature_branch,
    delete_feature_branch,
    ensure_develop_branch,
    get_feature_branch_for_ticket,
)

# ─── Data class ───────────────────────────────────────────────────────────────


@dataclass
class WorktreeInfo:
    """A data class that contains worktree metadata.

    Attributes:
        path: absolute path to the worktree.
        branch_name: Connected feature branch name (e.g. feat/T-001-title).
        ticket_number: Ticket number (e.g. T-001).
        created_at: Creation time (ISO 8601 format).
        base_branch: Base branch. Default 'develop'.
    """

    path: str
    branch_name: str
    ticket_number: str
    created_at: str
    base_branch: str = "develop"


@dataclass
class MergeResult:
    """A data class that contains the merge results.

    Attributes:
        success: Whether the merge was successful.
        conflicts: List of conflicting files (in case of failure).
        merged_branch: Merged feature branch name (if successful).
        merge_commit: Merge commit SHA (if successful).
        error_message: Error message (in case of failure).
    """

    success: bool
    conflicts: list[str] = field(default_factory=list)
    merged_branch: str = ""
    merge_commit: str = ""
    error_message: str = ""


# ─── Internal Utilities ────────────────────────────────────────────────────────────────


def _git(
    *args: str, repo_path: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Executes a git command and returns the results.

    Args:
        *args: git subcommands and arguments.
        repo_path: Git repository path. If None, use resolve_project_root().

    Returns:
        CompletedProcess instance.
    """
    cwd = repo_path or resolve_project_root()
    return run_git(*args, repo_path=cwd, timeout=30)


def _get_project_root(repo_path: str | None = None) -> str:
    """Returns the absolute path to the project root."""
    return repo_path or resolve_project_root()


def _worktrees_base_dir(repo_path: str | None = None) -> str:
    """Returns the path to the parent directory where the worktree is stored.

    Returns:
        Absolute path to .worktrees/ under the project root.
    """
    return str(worktrees_base_dir(_get_project_root(repo_path)))


def _merge_lock_path(repo_path: str | None = None) -> str:
    """Returns the merge lock directory path.

    Returns:
        .git/worktree-merge.lockdir absolute path.
    """
    return str(merge_lock_path(_get_project_root(repo_path)))


def _worktree_dir_name(branch_name: str) -> str:
    """Convert the branch name to the worktree directory name.

    feat/T-NNN-title -> feat-T-NNN-title (slash with hyphen).

    Args:
        branch_name: feature branch name.

    Returns:
        Directory name (no slash).
    """
    return worktree_dir_name(branch_name)


def _get_current_branch(repo_path: str | None = None) -> str:
    """Returns the currently checked out branch name.

    Args:
        repo_path: Git repository path.

    Returns:
        Current branch name. Empty string if detached HEAD.
    """
    result = _git("rev-parse", "--abbrev-ref", "HEAD", repo_path=repo_path)
    if result.returncode != 0:
        return ""
    branch = result.stdout.strip()
    return "" if branch == "HEAD" else branch


def _warn(msg: str) -> None:
    """Prints a warning message to stderr."""
    print(f"[WARN] worktree_manager: {msg}", file=sys.stderr)


def _info(msg: str) -> None:
    """Prints information messages to stderr."""
    print(f"[INFO] worktree_manager: {msg}", file=sys.stderr)


def _append_worktree_io(
    op: str,
    duration_ms: int,
    outcome: str,
    error_reason: str | None = None,
) -> None:
    """Record worktree.io events in metrics.jsonl.

    work_dir is extracted from the WORKFLOW_WORK_DIR or _WF_WORK_DIR environment variable.
    In case of extraction failure (external call to workflow, etc.), silently skip.
    All exceptions are quietly absorbed and do not affect worktree_manager operation.

    Args:
        op: operation type ('create' | 'remove' | 'merge').
        duration_ms: Time taken for the task (ms).
        outcome: result ('ok' | 'fail').
        error_reason: Exception message on failure (None on success).
    """
    try:
        work_dir: str | None = None
        for key in ("WORKFLOW_WORK_DIR", "_WF_WORK_DIR"):
            val = os.environ.get(key, "").strip()
            if val and os.path.isdir(val):
                work_dir = val
                break
        if not work_dir:
            return

        payload: dict = {
            "op": op,
            "duration_ms": duration_ms,
            "outcome": outcome,
        }
        if error_reason is not None:
            payload["error_reason"] = str(error_reason)[:500]

        from engine.core.metrics import append_event
        append_event(work_dir, "worktree.io", payload)
    except Exception:  # noqa: BLE001
        pass


# ─── Public API ─────────────────────────────────────────────────────────────────────


def is_worktree_enabled(repo_path: str | None = None) -> bool:
    """Determines whether the worktree function is activated.

    Uses the WORKFLOW_WORKTREE value in .agent-factory/.settings as the single source of truth (T-370 successor).

    Removed fallback paths:
      - WORKFLOW_WORKTREE in os.environ — due to dual sources of truth in environment variables and .settings
        Prevent synchronization regression.
      - Inferring the existence of a develop branch — Following the single source of truth principle, eliminating all inference operations.

    Bootstrap guarantee: build.sh + claude-env.tmpl has WORKFLOW_WORKTREE entry in .settings
    Merge automatically (_merge_kv_settings KEY matching). In a normal environment, raise does not occur.

    Activation expression: "true", "1", "yes", "on" -> True.
    Disable expression: "false", "0", "no", "off" -> False.

    Args:
        repo_path: Git repository path (to maintain compatibility — currently unused).

    Returns:
        Whether to enable the worktree feature.

    Raises:
        RuntimeError: When WORKFLOW_WORKTREE is not set in .settings or is an invalid value.
    """
    # .settings Single Source of Truth (T-370 successor) — Remove all inference fallbacks
    setting_val = read_env("WORKFLOW_WORKTREE") or None
    if setting_val is None:
        raise RuntimeError(
            "WORKFLOW_WORKTREE is not set in .agent-factory/.settings."
            "Inference fallbacks (environment variables, presence of develop branch) have been removed in favor of a single source of truth principle."
            "Recovery: Rerun build.sh (automatically enriched with template merge) or"
            "Specify 'WORKFLOW_WORKTREE=true' or 'WORKFLOW_WORKTREE=false' in .settings."
        )

    normalized = setting_val.strip().lower()
    if normalized in ("1", "true", "yes", "on"):
        return True
    if normalized in ("0", "false", "no", "off"):
        return False
    raise RuntimeError(
        f"The WORKFLOW_WORKTREE value is invalid (.settings value: {setting_val!r})."
        "Allowed values: true / false / 1 / 0 / yes / no / on / off"
    )


def create_worktree(
    ticket_number: str,
    title: str,
    base_branch: str = "develop",
    repo_path: str | None = None,
    command: str = "implement",
) -> WorktreeInfo | None:
    """Create a worktree for tickets.

    After securing the develop branch and creating the feature branch,
    Create an isolated working directory with git worktree add.

    Args:
        ticket_number: Ticket number (e.g. 'T-001').
        title: Ticket title.
        base_branch: Base branch. Default 'develop'.
        repo_path: Git repository path. If None, use the project root.
        command: Workflow command. If it is not 'implement', the creation is refused.

    Returns:
        Created WorktreeInfo. None + warning output in case of failure.
    """
    _t0 = time.monotonic()
    try:
        result = _create_worktree_impl(
            ticket_number, title, base_branch, repo_path, command
        )
        duration_ms = int((time.monotonic() - _t0) * 1000)
        if result is not None:
            _append_worktree_io("create", duration_ms, "ok")
        else:
            _append_worktree_io("create", duration_ms, "fail")
        return result
    except Exception as exc:
        duration_ms = int((time.monotonic() - _t0) * 1000)
        _append_worktree_io("create", duration_ms, "fail", str(exc))
        raise


def _create_worktree_impl(
    ticket_number: str,
    title: str,
    base_branch: str = "develop",
    repo_path: str | None = None,
    command: str = "implement",
) -> WorktreeInfo | None:
    """create_worktree Actual implementation (separate from metrics timing wrapper).

    Args:
        ticket_number: Ticket number (e.g. 'T-001').
        title: Ticket title.
        base_branch: Base branch. Default 'develop'.
        repo_path: Git repository path. If None, use the project root.
        command: Workflow command. If it is not 'implement', the creation is refused.

    Returns:
        Created WorktreeInfo. None + warning output in case of failure.
    """
    # Command defense: Refuse to create worktrees other than implement.
    if command not in ("implement",):
        _warn(
            f"Worktree creation is only for implement workflows"
            f"(requested command: {command})"
        )
        return None

    # Ticket number normalization
    ticket_number = normalize_ticket_number(ticket_number)

    # Secure the develop branch
    if not ensure_develop_branch(repo_path):
        _warn("Failed to create develop branch, unable to create worktree")
        return None

    # Create feature branch
    branch_name = create_feature_branch(
        ticket_number, title, base=base_branch, repo_path=repo_path
    )
    if not branch_name:
        _warn("Feature branch creation failed, unable to create worktree")
        return None

    # worktree directory path
    base_dir = _worktrees_base_dir(repo_path)
    wt_path = str(worktree_path_for_branch(_get_project_root(repo_path), branch_name))

    # Check for already existing worktree
    if os.path.isdir(wt_path):
        _info(f"worktree already exists: {wt_path}")
        return WorktreeInfo(
            path=wt_path,
            branch_name=branch_name,
            ticket_number=ticket_number,
            created_at=datetime.now().isoformat(),
            base_branch=base_branch,
        )

    # Secure parent directory
    os.makedirs(base_dir, exist_ok=True)

    # git worktree add --lock
    git_result = _git(
        "worktree", "add", "--lock", wt_path, branch_name,
        repo_path=repo_path,
    )
    if git_result.returncode != 0:
        _warn(f"Failed to create worktree: {git_result.stderr.strip()}")
        return None

    created_at = datetime.now().isoformat()
    _info(f"Create worktree: {wt_path} (branch: {branch_name})")

    return WorktreeInfo(
        path=wt_path,
        branch_name=branch_name,
        ticket_number=ticket_number,
        created_at=created_at,
        base_branch=base_branch,
    )


def has_uncommitted_changes(worktree_path: str) -> bool:
    """Check whether there are uncommitted changes in the worktree path.

    ``git status --porcelain`` If the output is not empty, it means there are uncommitted changes.
    It means. False if the path does not exist or the git command execution failed.
    Return to prevent false positives.

    Args:
        worktree_path: Worktree directory path to check.

    Returns:
        True if there are uncommitted changes, False if there are none or inspection is not possible.
    """
    result = _git("status", "--porcelain", repo_path=worktree_path)
    if result.returncode != 0:
        return False
    return bool(result.stdout.strip())


def count_feature_branch_commits(
    branch_name: str,
    base_branch: str = "develop",
    repo_path: str | None = None,
) -> int:
    """Returns the number of commits accumulated since base_branch in the feature branch.

    Run ``git rev-list --count <base_branch>..<branch_name>``
    Calculate the number of commits the feature branch made after the base_branch branch point.

    It is used as a worker commit missing detection signal:
      - 0: State in which the worker has not made a single commit (commit missing signal)
      - Positive number: normal (commit exists)
      - -1: Cannot be checked (branch does not exist, base_branch does not exist, etc.) — the caller must
            In this case, it must be passed rather than blocked (preventing false-positives).

    Args:
        branch_name: The feature branch name to count the number of commits (e.g. 'feat/T-001-title').
        base_branch: Base branch. Default 'develop'.
        repo_path: Git repository path. If None, use the project root.

    Returns:
        Number of commits (an integer greater than or equal to 0). -1 if inspection is not possible.
    """
    result = _git(
        "rev-list", "--count", f"{base_branch}..{branch_name}",
        repo_path=repo_path,
    )
    if result.returncode != 0:
        return -1
    try:
        return int(result.stdout.strip())
    except (ValueError, AttributeError):
        return -1


def remove_worktree(
    ticket_number: str,
    delete_branch: bool = True,
    repo_path: str | None = None,
) -> bool:
    """Removes the worktree connected to the ticket.

    Idempotent behavior: returns True if it has already been removed.
    If delete_branch=True, the feature branch is also deleted.
    In case of failure, only False + warning is output and the process is not terminated.

    Args:
        ticket_number: Ticket number (e.g. 'T-001').
        delete_branch: Whether to also delete the feature branch. Default True.
        repo_path: Git repository path. If None, use the project root.

    Returns:
        True if the removal was successful (or not already there), False if it failed.
    """
    _t0 = time.monotonic()
    try:
        result = _remove_worktree_impl(ticket_number, delete_branch, repo_path)
        duration_ms = int((time.monotonic() - _t0) * 1000)
        outcome = "ok" if result else "fail"
        _append_worktree_io("remove", duration_ms, outcome)
        return result
    except Exception as exc:
        duration_ms = int((time.monotonic() - _t0) * 1000)
        _append_worktree_io("remove", duration_ms, "fail", str(exc))
        raise


def _remove_worktree_impl(
    ticket_number: str,
    delete_branch: bool = True,
    repo_path: str | None = None,
) -> bool:
    """remove_worktree Actual implementation (separate from metrics timing wrapper).

    Args:
        ticket_number: Ticket number (e.g. 'T-001').
        delete_branch: Whether to also delete the feature branch. Default True.
        repo_path: Git repository path. If None, use the project root.

    Returns:
        True if the removal was successful (or not already there), False if it failed.
    """
    ticket_number = normalize_ticket_number(ticket_number)

    branch_name = get_feature_branch_for_ticket(ticket_number, repo_path)
    if not branch_name:
        # If there is no feature branch, there will be no worktree, so success is processed.
        return True

    wt_path = str(worktree_path_for_branch(_get_project_root(repo_path), branch_name))

    # Unlock the worktree (since you created it with --lock)
    unlock_result = _git("worktree", "unlock", wt_path, repo_path=repo_path)

    # remove worktree
    if os.path.isdir(wt_path):
        if unlock_result.returncode == 0:
            # Unlock success: --force 1 time (force processing of dirty state)
            result = _git(
                "worktree", "remove", "--force", wt_path, repo_path=repo_path
            )
        else:
            # Unlock failure: Assume locked state, --force --force (force locked + dirty processing)
            result = _git(
                "worktree", "remove", "--force", "--force", wt_path,
                repo_path=repo_path,
            )
        if result.returncode != 0:
            _warn(f"Failed to remove worktree: {result.stderr.strip()}")
            return False

    # git worktree prune (prune residual information)
    _git("worktree", "prune", repo_path=repo_path)

    _info(f"Remove worktree: {wt_path}")

    # Delete feature branch
    if delete_branch and branch_name:
        delete_feature_branch(branch_name, repo_path)

    return True


def merge_to_develop(
    ticket_number: str, repo_path: str | None = None
) -> MergeResult:
    """Merge the feature branch into develop with --no-ff.

    Prevents simultaneous merges with mkdir-based locking, and automatically
    Execute git merge --abort. After a successful merge, the worktree and
    Organize the feature branch.

    Args:
        ticket_number: Ticket number (e.g. 'T-001').
        repo_path: Git repository path. If None, use the project root.

    Returns:
        MergeResult instance.
    """
    _t0 = time.monotonic()
    try:
        merge_result = _merge_to_develop_impl(ticket_number, repo_path)
        duration_ms = int((time.monotonic() - _t0) * 1000)
        outcome = "ok" if merge_result.success else "fail"
        error_reason = merge_result.error_message if not merge_result.success else None
        _append_worktree_io("merge", duration_ms, outcome, error_reason)
        return merge_result
    except Exception as exc:
        duration_ms = int((time.monotonic() - _t0) * 1000)
        _append_worktree_io("merge", duration_ms, "fail", str(exc))
        raise


def _merge_to_develop_impl(
    ticket_number: str, repo_path: str | None = None
) -> MergeResult:
    """merge_to_develop actual implementation (separate from metrics timing wrapper).

    Args:
        ticket_number: Ticket number (e.g. 'T-001').
        repo_path: Git repository path. If None, use the project root.

    Returns:
        MergeResult instance.
    """
    ticket_number = normalize_ticket_number(ticket_number)

    # When called in an environment where WORKFLOW_WORKTREE=false, the main storage HEAD is
    # Instructs users on the manual merge command.
    if not is_worktree_enabled(repo_path):
        _warn(
            "merge_to_develop() in non-worktree mode (WORKFLOW_WORKTREE=false)"
            "You have been called. Main storage HEAD is blocked to prevent contamination."
        )
        _warn(
            "Manual merge procedure:"
            "git checkout develop && "
            f"git merge --no-ff <feature-branch-of-{ticket_number}>"
        )
        return MergeResult(
            success=False,
            error_message=(
                f"Non-worktree mode — merge_to_develop({ticket_number}) blocked."
                "WORKFLOW_WORKTREE=true Requires activation or manual merge."
            ),
        )

    branch_name = get_feature_branch_for_ticket(ticket_number, repo_path)
    if not branch_name:
        return MergeResult(
            success=False,
            error_message=f"The feature branch linked to {ticket_number} could not be found",
        )

    lock_path = _merge_lock_path(repo_path)
    original_branch = _get_current_branch(repo_path)

    # acquire lock
    if not acquire_lock(lock_path, max_wait=10, stale_timeout=300):
        return MergeResult(
            success=False,
            error_message="Failed to acquire merge lock (another merge may be in progress)",
        )

    try:
        # Secure the develop branch
        if not ensure_develop_branch(repo_path):
            return MergeResult(
                success=False,
                error_message="Failed to create develop branch",
            )

        # develop checkout
        checkout_result = _git("checkout", "develop", repo_path=repo_path)
        if checkout_result.returncode != 0:
            return MergeResult(
                success=False,
                error_message=f"develop checkout failed: {checkout_result.stderr.strip()}",
            )

        # --no-ff merge
        merge_msg = f"Merge {branch_name} into develop"
        merge_result = _git(
            "merge", "--no-ff", "-m", merge_msg, branch_name,
            repo_path=repo_path,
        )

        if merge_result.returncode != 0:
            # collision detection
            conflicts = _detect_conflicts(repo_path)
            # merge --abort
            _git("merge", "--abort", repo_path=repo_path)

            return MergeResult(
                success=False,
                conflicts=conflicts,
                merged_branch=branch_name,
                error_message=f"Merge conflicts occur: {', '.join(conflicts) if conflicts else merge_result.stderr.strip()}",
            )

        # Obtain merge commit SHA
        sha_result = _git("rev-parse", "HEAD", repo_path=repo_path)
        merge_commit = sha_result.stdout.strip() if sha_result.returncode == 0 else ""

        _info(f"Merge successful: {branch_name} -> develop ({merge_commit[:8]})")

        # Organize worktree + feature branches
        remove_worktree(ticket_number, delete_branch=True, repo_path=repo_path)

        return MergeResult(
            success=True,
            merged_branch=branch_name,
            merge_commit=merge_commit,
        )

    finally:
        # Restore original branch (if not develop)
        if original_branch and original_branch != "develop":
            # If the original branch has been deleted (the feature branch you just merged and cleaned up)
            # It's safe to remain in develop
            restore_result = _git(
                "checkout", original_branch, repo_path=repo_path
            )
            if restore_result.returncode != 0:
                # Stay in develop if original branch restoration fails
                _warn(
                    f"Failed to restore original branch ({original_branch}),"
                    f"keep in develop"
                )

        # unlocked
        release_lock(lock_path)


_PORCELAIN_CONFLICT_CODES: frozenset[str] = frozenset(
    {"UU", "AA", "DD", "AU", "UA", "DU", "UD"}
)
"""Set of conflicting codes from git status --porcelain ."""

_SENTINEL_UNKNOWN_CONFLICT: str = "<unknown-conflict>"
"""The sentinel value returned when both git sources fail."""


def _parse_porcelain_conflicts(stdout: str) -> list[str]:
    """Parse the list of conflicting files from the ``git status --porcelain`` output.

    Among the porcelain status codes in XY format, the conflict codes (UU, AA, DD, AU, UA, DU, UD) are
    Returns the file path by filtering only the included rows.

    Args:
        stdout: The standard output string of ``git status --porcelain``.

    Returns:
        List of conflicting file paths. An empty list if there are no conflicts.

    Examples:
        >>> _parse_porcelain_conflicts("UU foo.py\\nAA bar.py\\n M baz.py\\n")
        ['foo.py', 'bar.py']
    """
    conflicts: list[str] = []
    for line in stdout.splitlines():
        if len(line) < 4:
            continue
        # porcelain v1 format: "XY <path>" (XY = 2 characters, 1 space, path)
        xy = line[:2]
        path = line[3:].strip()
        if xy in _PORCELAIN_CONFLICT_CODES and path:
            conflicts.append(path)
    return conflicts


def _detect_conflicts(repo_path: str | None = None) -> list[str]:
    """Returns a list of merge conflict files.

    Conflicting files are detected with a two-step source, and a sentinel is returned if all sources fail.

    | steps | Source | Conditions |
    |------|------|------|
    | 1st | ``git diff --name-only --diff-filter=U`` | Always try. If the result is empty, proceed to the second round |
    | 2nd | ``git status --porcelain`` (UU/AA/DD/AU/UA/DU/UD) | Try only if the primary result is an empty list |
    | sentinel | ``["<unknown-conflict>"]`` | Both sources return when returncode != 0 |

    Return immediately when the primary source returns a result (no secondary attempt).
    1st success + 2nd attempt if empty list. If the second round is also successful, the two results are combined (removing duplicates).
    If returncode != 0 for both the first and second, ``["<unknown-conflict>"]`` sentinel is returned.

    sentinel Meaning: A conflict has occurred, but the file list cannot be checked.
    The caller can distinguish sentinels with ``"<unknown-conflict>" in conflicts``.

    Args:
        repo_path: Git repository path.

    Returns:
        List of conflicting file paths. sentinel ``["<unknown-conflict>"]`` if any git command fails.
    """
    # Primary source: git diff --name-only --diff-filter=U
    diff_result = _git(
        "diff", "--name-only", "--diff-filter=U", repo_path=repo_path
    )
    diff_ok = diff_result.returncode == 0
    diff_files: list[str] = []
    if diff_ok:
        diff_files = [
            line.strip()
            for line in diff_result.stdout.splitlines()
            if line.strip()
        ]
        if diff_files:
            # If there is a result in the primary source, it is returned immediately
            return diff_files

    # Secondary source: git status --porcelain (when primary is empty list or fails)
    porcelain_result = _git("status", "--porcelain", repo_path=repo_path)
    porcelain_ok = porcelain_result.returncode == 0

    if not diff_ok and not porcelain_ok:
        # Both sources fail → sentinel returns
        return [_SENTINEL_UNKNOWN_CONFLICT]

    porcelain_files: list[str] = []
    if porcelain_ok:
        porcelain_files = _parse_porcelain_conflicts(porcelain_result.stdout)

    # Union (1st result + 2nd result, maintain order + remove duplicates)
    seen: set[str] = set()
    merged: list[str] = []
    for f in diff_files + porcelain_files:
        if f not in seen:
            seen.add(f)
            merged.append(f)
    return merged


def list_worktrees(repo_path: str | None = None) -> list[WorktreeInfo]:
    """Returns a list of active worktrees.

    git worktree list --porcelain Parse the output and place it within your project.
    Filter only the feature worktree.

    Args:
        repo_path: Git repository path. If None, use the project root.

    Returns:
        WorktreeInfo list. Empty list if parsing fails.
    """
    result = _git("worktree", "list", "--porcelain", repo_path=repo_path)
    if result.returncode != 0:
        return []

    worktrees: list[WorktreeInfo] = []
    base_dir = _worktrees_base_dir(repo_path)

    # Parsing porcelain output: blocks separated by blank lines
    current: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            wt_info = _parse_worktree_block(current, base_dir)
            if wt_info:
                worktrees.append(wt_info)
            current = {}
            continue

        if line.startswith("worktree "):
            current["path"] = line[len("worktree "):]
        elif line.startswith("branch "):
            current["branch"] = line[len("branch "):]

    # Last block processing
    if current:
        wt_info = _parse_worktree_block(current, base_dir)
        if wt_info:
            worktrees.append(wt_info)

    return worktrees


def _parse_worktree_block(
    block: dict[str, str], base_dir: str
) -> WorktreeInfo | None:
    """Parse the porcelain block into WorktreeInfo.

    Only the feature worktree is returned (feat/T-NNN-* pattern), and the main worktree is
    Filter.

    Args:
        block: porcelain parsing intermediate result dictionary.
        base_dir: Absolute path to the .worktrees/ directory.

    Returns:
        WorktreeInfo or None (if not a feature worktree).
    """
    wt_path = block.get("path", "")
    branch_ref = block.get("branch", "")

    if not wt_path or not branch_ref:
        return None

    # Remove refs/heads/
    branch_name = branch_ref
    if branch_name.startswith("refs/heads/"):
        branch_name = branch_name[len("refs/heads/"):]

    # Filter only feature branches
    match = re.match(r"^feat/(T-\d+)-", branch_name)
    if not match:
        return None

    ticket_number = match.group(1)

    return WorktreeInfo(
        path=wt_path,
        branch_name=branch_name,
        ticket_number=ticket_number,
        created_at="",  # porcelain output has no creation time
    )


def get_worktree_path(
    ticket_number: str, repo_path: str | None = None
) -> str | None:
    """Returns the absolute path to the worktree connected to the ticket.

    Search by ticket number in list_worktrees() results, or
    Infer the path from the feature branch name.

    Args:
        ticket_number: Ticket number (e.g. 'T-001').
        repo_path: Git repository path. If None, use the project root.

    Returns:
        worktree absolute path or None.
    """
    ticket_number = normalize_ticket_number(ticket_number)

    # Search in list of active worktrees
    for wt in list_worktrees(repo_path):
        if wt.ticket_number == ticket_number:
            return wt.path

    # If not in the list, infer the path using the feature branch name.
    branch_name = get_feature_branch_for_ticket(ticket_number, repo_path)
    if branch_name:
        candidate = str(
            worktree_path_for_branch(_get_project_root(repo_path), branch_name)
        )
        if os.path.isdir(candidate):
            return candidate

    return None
