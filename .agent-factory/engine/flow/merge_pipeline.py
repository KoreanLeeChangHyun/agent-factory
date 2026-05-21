#!/usr/bin/env -S python3 -u
"""merge_pipeline.py - Worktree merge pipeline automation script.

Merging and organizing feature branches into develop in a worktree environment
Run the 5-step pipeline with a single command.

Usage:
  flow-merge <ticket_number> [--dry-run] [--force]

Pipeline stages:
  1. Detect uncommitted changes and automatically commit them
  2. Merge feature branch into develop with --no-ff
  2.5. Merge anchor verification (active only when WORKFLOW_WORKTREE=true)
  3. worktree unlock + remove (+ delete feature branch)
  4. Kanban done processing (prevent worktree merge hook duplication)
  5. (Delete feature branch is handled in step 3)

Options:
  --dry-run Prints only the expected behavior of each step and does not actually perform it.
  --force merge Bypass approval checking (when called directly)

Exit code:
  0 success
  1 Merge conflict or failure
  2 Input error or lack of approval
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

# ─── sys.path guaranteed ───────────────────────────────────────────────────────────────

# Symlink/relative path analysis correction (worktree environment response)
__file__ = os.path.realpath(__file__)

_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import resolve_project_root

# ─── Constant ───────────────────────────────────────────────────────────────────────

_MERGE_APPROVED_ENV: str = "WORKFLOW_MERGE_APPROVED"
_ANCHOR_FAILURE_LOG: str = os.path.join(
    ".agent-factory", "logs", "merge-anchor-failures.log"
)

# KST (UTC+9)
_KST = timezone(timedelta(hours=9))


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
    cmd = ["git", "-C", cwd] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def _info(msg: str) -> None:
    """Prints information messages to stderr."""
    print(f"[INFO] flow-merge: {msg}", file=sys.stderr, flush=True)


def _error(msg: str) -> None:
    """Prints error messages to stderr."""
    print(f"[ERROR] flow-merge: {msg}", file=sys.stderr, flush=True)


def _step(num: int, desc: str) -> None:
    """Prints pipeline stage headers."""
    print(f"\n── Stage {num}: {desc} ──", flush=True)


# ─── Pipeline stages ──────────────────────────────────────────────────────────────


def _normalize_ticket(ticket_number: str) -> str:
    """Normalize the ticket number to T-NNN format.

    Args:
        ticket_number: Original ticket number. If you only need numbers, add the T- prefix.

    Returns:
        Ticket number in T-NNN format.
    """
    if not ticket_number.startswith("T-"):
        ticket_number = f"T-{ticket_number}"
    return ticket_number


def _check_merge_approval(force: bool) -> bool:
    """Check whether the merge is approved.

    When calling flow-merge directly, the WORKFLOW_MERGE_APPROVED environment variable is set to
    Execution is allowed only if it is set or the --force option is present.

    Args:
        force: Whether to use the --force option.

    Returns:
        True if approved, False if not approved.
    """
    if force:
        return True
    if os.environ.get(_MERGE_APPROVED_ENV) == "1":
        return True
    return False


def _count_commits_ahead(branch: str, base: str = "develop") -> int | None:
    """`git rev-list base..branch --count` returns the result.

    Args:
        branch: Name of feature branch to be inspected.
        base: Base branch name (default develop).

    Returns:
        Number of commits ahead. None in case of command failure (branch absence, etc.).
    """
    result = _git("rev-list", f"{base}..{branch}", "--count")
    if result.returncode != 0:
        return None
    raw = result.stdout.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _branch_exists(branch: str) -> bool:
    """Check whether a feature branch exists locally.

    Args:
        branch: Branch name to check.

    Returns:
        True if present, False if not.
    """
    if not branch:
        return False
    result = _git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
    return result.returncode == 0


def _stage1_5_premerge_state_guard(
    ticket_number: str,
    worktree_path: str | None,
    force: bool,
) -> tuple[bool, str]:
    """Stage 1.5: Guard the worktree/feature branch state just before entering jammerge.

    Regression blocking: After Done rollback (undo_done), the worktree/feature branch is
    Remerge is carried out in an empty state (recreated without changes) or absent.
    Separately, anchor failed on commit → `reset --hard pre_merge_develop_sha`
    Separately, a regression occurred where changes were reset together.

    This guard verifies the following before entering Stage 2 (`merge_to_develop`):

    1. Absence of feature branch → Always blocked (regardless of force). Regenerate immediately after undo_done
       Cases where steps are missing or the work tree itself does not exist.
    2. Feature branch exists + commits ahead == 0 (empty branch) →
       force=False: block + clear error
       force=True: Block + reflog fallback guidance (auto trigger prohibited)
    3. Normal (commits ahead > 0) → Pass

    Guaranteed regression 0:

        Passes because commits ahead > 0.

        Only works in the jammer phase.
      - Prohibit application of auto regression/auto reflog (feedback_no_speculative_guards
        2026-05-08 Canon). Only messages with user-specified consent are displayed.

    Args:
        ticket_number: Ticket number (T-NNN).
        worktree_path: get_worktree_path return value. None when absent.
        force: Whether to use the --force option.

    Returns:
        (ok, message) tuple. If ok=True, it passes, if False, the caller terminates immediately.
        message is for stderr log purposes (empty string when passed).
    """
    _step(1, "Jammer state guard (Stage 1.5)")

    # branch_strategy has a high call cost, so it is lazy imported.
    try:
        from flow.branch_strategy import get_feature_branch_for_ticket
    except Exception as exc:  # pragma: no cover - import path abnormal
        _error(f"[GUARD] branch_strategy import failed: {exc}")
        return False, "branch_strategy import failed"

    branch_name = get_feature_branch_for_ticket(ticket_number)

    # ── 1. Absence of feature branch ──
    if not branch_name or not _branch_exists(branch_name):
        wt_status = "absence" if not worktree_path else f"exists({worktree_path})"
        msg = (
            f"Absence of feature branch: ticket={ticket_number}"
            f"branch={branch_name or '<unresolved>'} worktree={wt_status}"
        )
        _error(f"[GUARD] {msg}")
        if force:
            print(
                "force mode allows destructive behavior and therefore requires explicit user consent."
                "You need it. \n"
                "Recovery Options (Manual): \n"
                "1) Regenerate work tree/branch with `flow-undo-done <T-NNN> --force` \n"
                "2) Check the original merge commit SHA in the develop reflog: \n"
                "       git reflog develop --grep-reflog='merge.*' | grep "
                f"feat/{ticket_number}\n"
                "3) Cherry-pick the SHA containing the changes to a new branch and remerge it.",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(
                "An empty merge was blocked because the feature branch could not be found. \n"
                "Recreate it with `flow-undo-done <T-NNN> --force` and retry.",
                file=sys.stderr,
                flush=True,
            )
        return False, msg

    # ── 2. Existence of feature branch + empty branch (commits ahead == 0) ──
    ahead = _count_commits_ahead(branch_name, base="develop")
    if ahead is None:
        # rev-list failure — abnormal, such as absence of develop. block.
        msg = (
            f"Failed to calculate commits ahead: branch={branch_name} base=develop"
            "(develop branch missing or rev-list failed)"
        )
        _error(f"[GUARD] {msg}")
        return False, msg

    if ahead == 0:
        msg = (
            f"Empty branch detected: feature '{branch_name}' has no commits "
            "ahead of develop. Refusing empty merge."
        )
        _error(f"[GUARD] {msg}")
        if force:
            print(
                "Even in force mode, empty branches are not automatically merged."
                "(User express consent Canon). \n"
                "Recovery Options (Manual): \n"
                "1) Check the original merge commit SHA in the develop reflog: \n"
                "       git reflog develop --grep-reflog='merge.*' | grep "
                f"feat/{ticket_number}\n"
                "2) Cherry-pick the SHA containing the changes to a new branch and remerge \n"
                "3) Or, after regenerating the work tree with `flow-undo-done <T-NNN> --force`, \n"
                "Commit the work again and remerge it",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(
                "Merging empty branches is blocked due to the risk of reproducing regressions. \n"
                "Commit the changes to the work tree and retry.",
                file=sys.stderr,
                flush=True,
            )
        return False, msg

    # ── 3. Normal pass ──
    print(
        f"Feature branch top: {branch_name} ({ahead} commit ahead of develop)",
        flush=True,
    )
    return True, ""


def _stage1_auto_commit(
    ticket_number: str, worktree_path: str, dry_run: bool
) -> bool:
    """Stage 1: Detect uncommitted changes in the worktree and automatically commit them.

    Args:
        ticket_number: Ticket number (T-NNN).
        worktree_path: Absolute path to worktree.
        dry_run: If True, only the list of changed files is output.

    Returns:
        True on success, False on failure.
    """
    _step(1, "Detect uncommitted changes and automatically commit them")

    # Detect changes with git status --porcelain
    result = _git("status", "--porcelain", repo_path=worktree_path)
    if result.returncode != 0:
        _error(f"git status failed: {result.stderr.strip()}")
        return False

    changed_files = [
        line.strip() for line in result.stdout.splitlines() if line.strip()
    ]

    if not changed_files:
        print("No changes (no commit required)", flush=True)
        return True

    print(f"Detect {len(changed_files)} uncommitted files:", flush=True)
    for f in changed_files:
        print(f"    {f}", flush=True)

    if dry_run:
        print("[DRY-RUN] Skip autocommit", flush=True)
        return True

    # git add -A + commit
    add_result = _git("add", "-A", repo_path=worktree_path)
    if add_result.returncode != 0:
        _error(f"git add failed: {add_result.stderr.strip()}")
        return False

    commit_msg = f"chore: auto-commit before merge ({ticket_number})"
    commit_result = _git(
        "commit", "-m", commit_msg, repo_path=worktree_path
    )
    if commit_result.returncode != 0:
        _error(f"git commit failed: {commit_result.stderr.strip()}")
        return False

    print(f"Autocommit completed: {commit_msg}", flush=True)
    return True


def _stage2_merge_to_develop(
    ticket_number: str, dry_run: bool
) -> tuple[bool, str, str]:
    """Stage 2: Merge the feature branch into develop with --no-ff.

    Reuse worktree_manager.merge_to_develop().
    In case of merge conflict, abort and output the list of conflicting files.

    Args:
        ticket_number: Ticket number (T-NNN).
        dry_run: If True, only expected actions are output.

    Returns:
        (success, merge_commit_sha, feature_branch) tuple.
        On success (True, sha, branch), on failure (False, "", "").
    """
    _step(2, "Feature branch -> develop merge")

    from flow.branch_strategy import get_feature_branch_for_ticket
    from flow.worktree_manager import merge_to_develop

    branch_name = get_feature_branch_for_ticket(ticket_number)
    if not branch_name:
        _error(f"The feature branch linked to {ticket_number} could not be found")
        return False, "", ""

    print(f"Target branch: {branch_name}", flush=True)

    if dry_run:
        print(
            f"  [DRY-RUN] git merge --no-ff {branch_name} into develop",
            flush=True,
        )
        return True, "", branch_name

    merge_result = merge_to_develop(ticket_number)
    if not merge_result.success:
        if merge_result.conflicts:
            _error("Merge conflict occurred (merge --abort completed)")
            print("Conflicting files:", flush=True)
            for cf in merge_result.conflicts:
                print(f"    - {cf}", flush=True)
            print(
                "Please resolve the conflict in the worktree and try again.",
                flush=True,
            )
        else:
            _error(f"Merge failed: {merge_result.error_message}")
        return False, "", ""

    print(
        f"Merge completed: {merge_result.merged_branch} -> develop"
        f"({merge_result.merge_commit[:8]})",
        flush=True,
    )
    return True, merge_result.merge_commit, merge_result.merged_branch


def _handle_anchor_failure(
    merge_commit: str,
    feature_branch: str,
    reason: str,
    pre_merge_develop_sha: str = "",
) -> None:
    """If merge anchor verification fails, rollback and log recording are performed.

    Explicit SHA reset (`pre_merge_develop_sha`) if current HEAD matches merge_commit
    Or perform a `HEAD^` reset with fallback,
    Record in JSONL format in .agent-factory/logs/merge-anchor-failures.log.

    Args:
        merge_commit: Merge commit SHA.
        feature_branch: Feature branch name.
        reason: Reason for failure.
        pre_merge_develop_sha: develop HEAD SHA captured just before entering Stage 2.
            If it is not empty, use `git reset --hard <pre_merge_develop_sha>`
            Perform an explicit SHA reset (avoid T-403 regression: dictionary of develop
            ahead commit is automatically preserved).
            If the string is empty, the existing `HEAD^` relative path is used as a fallback for capture failure.
            Perform a reset and output a warning log.
    """
    project_root = resolve_project_root()

    # Forensics 1: Record develop HEAD before running reset
    head_before_result = _git("rev-parse", "HEAD")
    head_before = (
        head_before_result.stdout.strip()
        if head_before_result.returncode == 0
        else ""
    )

    # Rollback SHA decision: pre_merge_develop_sha first, HEAD^ fallback if not reserved
    if pre_merge_develop_sha:
        reset_target = pre_merge_develop_sha
    else:
        _error(
            "[ANCHOR] Do not have pre_merge_develop_sha — Do not have accurate SHA;"
            "Perform relative reset (HEAD^ fallback)"
        )
        reset_target = "HEAD^"

    # Forensics 1.5: Check if reset_target matches the first parent of merge commit.
    # A separate commit (`6efc6ef` revert, etc.) had been added, and pre_merge_develop_sha had been added.
    # That separate thing is captured as a commit and `reset --hard <commit separately>` is executed.
    # Reset to a different location from the develop state just before merging → Possibility of loss of changes.
    # If parent1 == reset_target, normal (reverts to the state just before merging),
    # Otherwise, it is a suspicious case captured above the commit, so the warning log is strengthened.
    # However, this test only performs advisory and does not block the reset itself.
    # (Canon prohibits introduction of automatic enforcement policy).
    parent1_mismatch = False
    if reset_target and reset_target != "HEAD^":
        parent1_result = _git("rev-parse", f"{merge_commit}^1")
        if parent1_result.returncode == 0:
            parent1_sha = parent1_result.stdout.strip()
            if parent1_sha and parent1_sha != reset_target:
                parent1_mismatch = True
                _error(
                    f"[ANCHOR][T-441] Suspicious case: reset_target"
                    f"({reset_target[:8]}) != merge_commit^1 "
                    f"({parent1_sha[:8]}). "
                    "Separately, pre_merge_develop_sha was captured above the commit."
                    "possibility. After reset, you need to check the develop changes."
                )

    # Rollback after checking HEAD matches merge_commit
    rollback_executed = False
    rollback_succeeded = False
    if head_before_result.returncode == 0 and head_before == merge_commit:
        reset_result = _git("reset", "--hard", reset_target)
        rollback_executed = True
        if reset_result.returncode == 0:
            rollback_succeeded = True
            _error(
                f"Merge rollback completed due to anchor verification failure"
                f"(reason: {reason}, reset_target: {reset_target})"
            )
            if parent1_mismatch:
                _error(
                    "[ANCHOR][T-441] Additional commits may be lost after rollback —"
                    "Check the develop reflog and work tree changes directly."
                )
        else:
            _error(
                f"anchor verification failure + rollback failure"
                f"(reset_target: {reset_target}): "
                f"{reset_result.stderr.strip()}"
            )
    else:
        _error(
            f"anchor verification failed (HEAD != merge_commit, rollback skipped): {reason}"
        )

    # Forensics 2: Record develop HEAD after executing reset
    head_after_result = _git("rev-parse", "HEAD")
    head_after = (
        head_after_result.stdout.strip()
        if head_after_result.returncode == 0
        else ""
    )

    # JSONL log history — pre_merge_develop_sha / reset_target / head_before /
    log_path = os.path.join(project_root, _ANCHOR_FAILURE_LOG)
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        ts = datetime.now(_KST).strftime("%Y-%m-%dT%H:%M:%S")
        record = {
            "timestamp": ts,
            "merge_commit": merge_commit,
            "feature_branch": feature_branch,
            "reason": reason,
            "pre_merge_develop_sha": pre_merge_develop_sha,
            "reset_target": reset_target,
            "head_before_reset": head_before,
            "head_after_reset": head_after,
            "rollback_executed": rollback_executed,
            "rollback_succeeded": rollback_succeeded,
            "parent1_mismatch": parent1_mismatch,
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        _error(f"anchor failure Logging failure: {e}")


def _stage2_5_verify_merge_anchor(
    merge_commit: str,
    feature_branch: str,
    dry_run: bool,
    pre_merge_develop_sha: str = "",
) -> bool:
    """Stage 2.5: Perform merge anchor verification.

    If WORKFLOW_WORKTREE=false (default value), it immediately returns True and is skipped.
    Upon activation, two verifications are performed:
      1. Second parent (^2) SHA of merge commit == feature_branch HEAD SHA
      2. git diff {merge_commit}^2 {merge_commit} output should be empty

    Args:
        merge_commit: Merge commit SHA generated in Stage 2.
        feature_branch: Merged feature branch name.
        dry_run: If True, only expected actions are output.
        pre_merge_develop_sha: develop HEAD SHA captured just before entering Stage 2.
            T-410: If merge_commit == pre_merge_develop_sha, git merge
            Since --no-ff is an already-up-to-date case that did not create a new commit,
            Skip the anchor verification itself (avoiding the ^2 call).
            If the string is empty, it is considered to be in an uncaptured state and the existing branch is followed.

    Returns:
        True if verification is successful (or skipped), False if verification fails (rollback complete).
    """
    _step(2, "Merge anchor verification (Stage 2.5)")

    from flow.worktree_manager import is_worktree_enabled

    if not is_worktree_enabled():
        print(
            "[ANCHOR] WORKFLOW_WORKTREE=false — Skip anchor verification",
            flush=True,
        )
        return True

    if dry_run:
        print(
            f"[ANCHOR] [DRY-RUN] merge anchor verification:"
            f"{merge_commit[:8]} / {feature_branch}",
            flush=True,
        )
        return True

    if not merge_commit:
        _error("anchor verification: unable to verify because merge_commit is empty")
        return True  # Non-blocking: Pass if verification is not possible

    # `git merge --no-ff` creates a new commit when the feature is the ancestor of develop
    # Returns the existing develop HEAD as is without creating it. In this case merge_commit is
    # It is the same as pre_merge_develop_sha, and anchor verification (^2 comparison) is meaningless.
    # By avoiding the `^2` call itself, the possibility of false-fail due to fall-through is blocked.
    if pre_merge_develop_sha and merge_commit == pre_merge_develop_sha:
        print(
            f"[ANCHOR] already-up-to-date — Skip anchor verification"
            f"(merge_commit {merge_commit[:8]} == "
            f"pre_merge_develop_sha {pre_merge_develop_sha[:8]})",
            flush=True,
        )
        return True

    # Verification 1: merge_commit^2 == feature_branch HEAD
    parent2_result = _git("rev-parse", f"{merge_commit}^2")
    if parent2_result.returncode != 0:
        # fast-forward or already-up-to-date case (1 parent).
        # There is no additional merge commit in develop, so anchor verification is meaningless → skip.
        # Data loss regression occurs even before the develop commit.
        # Structure the reason for the branch (distinguish between capture failure and SHA mismatch).
        if not pre_merge_develop_sha:
            sha_compare = "pre_merge_develop_sha not captured"
        elif merge_commit == pre_merge_develop_sha:
            # This path should have already been processed in the explicit branch above, but is marked defensively.
            sha_compare = (
                f"== pre_merge_develop_sha {pre_merge_develop_sha[:8]} "
                f"(up-to-date)"
            )
        else:
            sha_compare = (
                f"!= pre_merge_develop_sha {pre_merge_develop_sha[:8]} "
                f"(ff merge estimation)"
            )
        print(
            f"[ANCHOR] fast-forward / up-to-date — skip anchor verification"
            f"(merge_commit {merge_commit[:8]} 1 parent, {sha_compare})",
            flush=True,
        )
        return True

    fb_head_result = _git("rev-parse", feature_branch)
    if fb_head_result.returncode != 0:
        # Skip verification if feature branch has already been deleted (non-blocking)
        _info(
            f"[ANCHOR] Skip anchor verification: feature_branch {feature_branch}"
            f"Not found (already deleted)"
        )
        return True

    parent2_sha = parent2_result.stdout.strip()
    fb_head_sha = fb_head_result.stdout.strip()

    if parent2_sha != fb_head_sha:
        reason = (
            f"^2 SHA ({parent2_sha[:8]}) != feature HEAD ({fb_head_sha[:8]})"
        )
        _error(f"[ANCHOR] anchor validation failed: {reason}")
        _handle_anchor_failure(
            merge_commit, feature_branch, reason, pre_merge_develop_sha
        )
        return False

    # Verification 2: git diff {merge_commit}^2 {merge_commit} must be empty
    diff_result = _git(
        "diff", f"{merge_commit}^2", merge_commit
    )
    if diff_result.returncode != 0:
        _error(
            f"[ANCHOR] anchor validation failed: git diff command failed —"
            f"{diff_result.stderr.strip()}"
        )
        _handle_anchor_failure(
            merge_commit,
            feature_branch,
            "git diff command failed",
            pre_merge_develop_sha,
        )
        return False

    if diff_result.stdout.strip():
        reason = (
            f"diff {merge_commit[:8]}^2..{merge_commit[:8]} output is not empty"
        )
        _error(f"[ANCHOR] anchor validation failed: {reason}")
        _handle_anchor_failure(
            merge_commit, feature_branch, reason, pre_merge_develop_sha
        )
        return False

    print(
        f"[ANCHOR] anchor validation passed: {merge_commit[:8]} / {feature_branch}",
        flush=True,
    )
    return True


def _stage3_remove_worktree(
    ticket_number: str, dry_run: bool
) -> bool:
    """Stage 3: worktree unlock + remove (+ delete feature branch).

    Reuse worktree_manager.remove_worktree().
    Since merge_to_develop() already calls remove_worktree,
    Prune only if there is a remaining worktree (idempotent).

    Args:
        ticket_number: Ticket number (T-NNN).
        dry_run: If True, only expected actions are output.

    Returns:
        True on success, False on failure.
    """
    _step(3, "Remove worktree + delete feature branch")

    from flow.worktree_manager import get_worktree_path, remove_worktree

    wt_path = get_worktree_path(ticket_number)
    if wt_path:
        print(f"worktree path: {wt_path}", flush=True)
    else:
        print(
            "worktree already removed (cleanup completed in Stage 2)",
            flush=True,
        )
        return True

    if dry_run:
        print(
            f"  [DRY-RUN] worktree unlock + remove: {wt_path}",
            flush=True,
        )
        print("[DRY-RUN] Delete feature branch", flush=True)
        return True

    success = remove_worktree(
        ticket_number, delete_branch=True
    )
    if not success:
        _error("Worktree removal failed")
        return False

    print("worktree removal complete", flush=True)
    return True


def _stage4_kanban_done(
    ticket_number: str, dry_run: bool
) -> bool:
    """Stage 4: Kanban done processing.

    Call kanban_cli.cmd_done(). worktree inside cmd_done()
    The merge hook is because the feature branch has already been deleted.
    get_feature_branch_for_ticket() returns None, automatically
    Skip duplicate merges.

    Args:
        ticket_number: Ticket number (T-NNN).
        dry_run: If True, only expected actions are output.

    Returns:
        True on success, False on failure.
    """
    _step(4, "kanban done processing")

    if dry_run:
        print(
            f"  [DRY-RUN] kanban done {ticket_number}",
            flush=True,
        )
        print(
            "[DRY-RUN] Worktree merge hook is skipped due to non-existence of feature branch",
            flush=True,
        )
        return True

    try:
        from flow.kanban_cli import cmd_done

        cmd_done(ticket_number)
        print(f"kanban done done: {ticket_number}", flush=True)
        return True
    except SystemExit as e:
        if e.code and e.code != 0:
            _error(f"kanban done failed (exit code: {e.code})")
            return False
        return True
    except Exception as e:
        _error(f"kanban done failed: {e}")
        return False


# ─── Main pipeline ──────────────────────────────────────────────────────────────


def run_pipeline(
    ticket_number: str, dry_run: bool = False, force: bool = False
) -> int:
    """Execute the five-stage merge pipeline sequentially.

    Args:
        ticket_number: Ticket number (T-NNN format or number).
        dry_run: If True, only the expected operation of each step is output.
        force: If True, bypass merge approval check.

    Returns:
        Exit code. 0=Success, 1=Merge failed, 2=Not approved.
    """
    ticket_number = _normalize_ticket(ticket_number)

    print(f"=== flow-merge: {ticket_number} ===", flush=True)
    if dry_run:
        print("[DRY-RUN mode] Does not actually run \n", flush=True)

    # ── Approval inspection ──
    if not _check_merge_approval(force):
        _error(
            "Merge approval is required."
            "Use the /wf -d command or add the --force option."
        )
        return 2

    # ── Worktree path navigation ──
    from flow.worktree_manager import get_worktree_path

    worktree_path = get_worktree_path(ticket_number)

    # ── Stage 1: Automatically commit uncommitted changes ──
    if worktree_path:
        if not _stage1_auto_commit(ticket_number, worktree_path, dry_run):
            return 1
    else:
        _step(1, "Detect uncommitted changes and automatically commit them")
        print("No worktree (Skip Stage 1)", flush=True)

    # Since dry-run does not perform actual merge, the guard result is marked as advisory and passes.
    guard_ok, _guard_msg = _stage1_5_premerge_state_guard(
        ticket_number, worktree_path, force
    )
    if not guard_ok:
        if dry_run:
            print(
                "[DRY-RUN] Guard failure — would have been blocked in real merge (continued)",
                flush=True,
            )
        else:
            return 1

    # already-up-to-date / ff Case specification Used to specify branch + rollback SHA.
    # Fallback to an empty string if the develop branch does not exist or rev-parse fails —
    # Both _stage2_5_verify_merge_anchor and _handle_anchor_failure
    # Maintain existing behavior with backward-compat default("").
    pre_merge_develop_sha_result = _git("rev-parse", "develop")
    if pre_merge_develop_sha_result.returncode == 0:
        pre_merge_develop_sha = pre_merge_develop_sha_result.stdout.strip()
    else:
        pre_merge_develop_sha = ""
        _info(
            "[ANCHOR] pre_merge_develop_sha capture failed — develop branch not present or"
            f"rev-parse failed: {pre_merge_develop_sha_result.stderr.strip()}"
        )

    # ── Stage 2: feature -> develop merge ──
    stage2_success, merge_commit, feature_branch = _stage2_merge_to_develop(
        ticket_number, dry_run
    )
    if not stage2_success:
        return 1

    # ── Stage 2.5: Merge anchor verification ──
    if not _stage2_5_verify_merge_anchor(
        merge_commit, feature_branch, dry_run, pre_merge_develop_sha
    ):
        return 1

    # ── Stage 3: Worktree removal + branch deletion ──
    if not _stage3_remove_worktree(ticket_number, dry_run):
        # If worktree removal fails, just output a warning and continue.
        _info("Removal of the worktree failed, but the merge was completed, so continue.")

    # ── Stage 4: kanban done ──
    if not _stage4_kanban_done(ticket_number, dry_run):
        # If kanban done fails, only a warning is output.
        _info("kanban done failed, but merge was completed")

    # ── Stage 5: Delete feature branch (processing completed in Stage 3) ──
    _step(5, "Delete feature branch")
    print("Processing completed in Stage 3 (delete_branch=True)", flush=True)

    print(f"\n === flow-merge completed: {ticket_number} ===", flush=True)
    return 0


# ─── CLI ──────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Configure the CLI argument parser.

    Returns:
        A configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="flow-merge",
        description="Worktree Merge Pipeline Automation",
    )
    parser.add_argument(
        "ticket_number",
        help="Ticket number (T-NNN or numeric)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Prints only expected behavior and does not actually perform it",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Bypass merge approval check (when calling directly)",
    )
    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    exit_code = run_pipeline(
        ticket_number=args.ticket_number,
        dry_run=args.dry_run,
        force=args.force,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
