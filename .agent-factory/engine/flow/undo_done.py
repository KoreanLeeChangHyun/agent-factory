"""undo done.py - a module that automatically rolls the Done processed workflow to the Review phase.

Done will perform following steps to clean the deadly bugs found after NEWS

  1. FAQ Pre Verification — Ticket Done Status / merge commit existence / merge anchor /
     Branding + worktree oil inspection
  2. FAQ git branch --contains <merge commit> output
     local-only identifies whether origin/develop is reached/main reach
  3. FAQs development —
       - Strategic 1 reset: 0 before push + follow-up commit → `git reset --hard merge commit^`
       - Strategies 2 revert: push or follow-up commit accumulation → git revert -m 1 --no-edit
  4. FAQs Worktree Regeneration — call `worktree manager.create worktree()`
  5. FAQs Before the Kanban force — go to the ticket XML as `done/T-NNN.xml` → `review/T-NNN.xml` +
     "Review"
  6. Post-Output — git status / log / next procedure

Public API:
    main: argparse entry point (flow-undo-done wrapper call)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Literal

# ─── sys.path guaranteed ───────────────────────────────────────────────────────────────

_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import resolve_project_root
from flow.branch_strategy import get_feature_branch_for_ticket
from flow.cli_utils import build_common_epilog, ticket_type
from flow.ticket_repository import (
    KANBAN_DONE_DIR,
    find_ticket_file,
    move_ticket_to_status_dir,
    parse_ticket_xml,
    update_ticket_status,
)
from flow.worktree_manager import (
    WorktreeInfo,
    create_worktree,
    get_worktree_path,
)

# ─── Type Alias ​​────────────────────────────────────────────────────────────────────

PushState = Literal["local", "pushed", "main"]


# ─── Logging ────────────────────────────────────────────────────────────────────────


def _log(msg: str) -> None:
    """Outputs step-by-step progress logs to stdout."""
    print(f"[undo-done] {msg}", flush=True)


def _err(msg: str) -> None:
    """Prints the error log to stderr and throws SystemExit(2)."""
    print(f"[undo-done] ERROR: {msg}", file=sys.stderr, flush=True)
    raise SystemExit(2)


def _warn(msg: str) -> None:
    """Print warning log to stderr (continue)."""
    print(f"[undo-done] WARN: {msg}", file=sys.stderr, flush=True)


# ─── git helper ────────────────────────────────────────────────────────────────────


def _git(
    *args: str, repo_path: str | None = None, check: bool = False
) -> subprocess.CompletedProcess[str]:
    """execute git command.

    Args:
        *args: git sub-mand and arguments.
        repo path: repository path. None if the project root.
        check: true returncode != 0 o'clock  err by abort.

    Returns:
        CompletedProcess instance.
    """
    cwd = repo_path or resolve_project_root()
    cmd = ["git", "-C", cwd] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if check and result.returncode != 0:
        _err(
            f"git {' '.join(args)} failed (exit={result.returncode}):"
            f"{result.stderr.strip()}"
        )
    return result


# ─── Pre-verification (T2.2) ─────────────────────────────────────────────────────────


def _validate_ticket_done(ticket_id: str) -> str:
    """The ticket exists in the Done directory and status="Done".

    Args:
        Ticket id: T-NNN type ticket number.

    Returns:
        Ticket XML file absolute path.

    Raises:
        SystemExit: No Done status or no file.
    """
    ticket_file = find_ticket_file(ticket_id)
    if ticket_file is None:
        _err(f"Ticket file {ticket_id} not found")

    ticket_data = parse_ticket_xml(ticket_file)
    status = ticket_data.get("status", "")
    if status != "Done":
        _err(
            f"{ticket_id} is not in Done status (currently: {status!r})."
            "undo-done is for Done tickets only."
        )

    # Verify that the file is located in the done directory (defensive verification)
    if os.path.normpath(os.path.dirname(ticket_file)) != os.path.normpath(
        KANBAN_DONE_DIR
    ):
        _warn(
            f"Ticket status is Done but the file is outside done/:"
            f"{ticket_file}"
        )

    _log(f"Ticket validation passed: {ticket_id} status=Done file={ticket_file}")
    return ticket_file


def _load_merge_commit(ticket_id: str, ticket_file: str, force: bool) -> str:
    """Load the ticket result.merge commit and try reflog fallback when missing.

    Args:
        ticket id: T-NNN format.
        ticket file: ticket XML absolute path.
        force: True attempt to estimate from reflog when missing.

    Returns:
        merge commit SHA (40 digit hex or short format).

    Raises:
        SystemExit: merge commit and force fails False or fallback.
    """
    ticket_data = parse_ticket_xml(ticket_file)
    result = ticket_data.get("result") or {}
    merge_commit = (result.get("merge_commit") or "").strip()

    if merge_commit:
        _log(f"load merge_commit: {merge_commit[:8]} (from ticket result)")
        return merge_commit

    if not force:
        _err(
            f"{ticket_id} result.merge_commit is empty."
            "This may be a ticket that was Done prior to the introduction of Phase 1 infrastructure."
            "Try reflog fallback with the --force flag, or"
            f"Manually augment with flow-kanban update-result {ticket_id} --merge-commit <SHA>."
        )

    # reflog fallback: feat/T-NNN-* Merge message navigation
    _warn("merge_commit missing, try reflog fallback with --force")
    reflog_result = _git(
        "reflog",
        "--grep-reflog=" + f"merge.*feat/{ticket_id}",
        "--format=%H %gs",
        "develop",
    )
    if reflog_result.returncode != 0 or not reflog_result.stdout.strip():
        _err(
            "No candidate merge commit found in reflog."
            "It is assumed that the reflog has expired or been merged into another branch."
            "Manually identify the SHA in git log and then specify it with --merge-commit."
        )

    candidate = reflog_result.stdout.strip().splitlines()[0].split(" ", 1)[0]
    _warn(
        f"reflog fallback candidate SHA={candidate[:8]} — Reliability is low, so be sure to review git log afterwards"
    )
    return candidate


def _verify_merge_anchor(merge_commit: str, expected_branch: str) -> None:
    """merge commit^2 == feature validation of the branch tip.

    merge pipeline. stage2 5 verify merge anchor
    If the feature brand is already deleted, the non-block (the status after correction).

    Args:
        merge commit: validation target migration commit SHA.
        expected branch: feat/T-NNN-* format feature brand name (or empty string).

    Raises:
        SystemExit: parent2 is expected branch tip and other cases (anchor broken).
    """
    parent2 = _git("rev-parse", f"{merge_commit}^2")
    if parent2.returncode != 0:
        # fast-forward or non-merge commit. Only possible with revert strategy.
        _warn(
            f"merge_commit {merge_commit[:8]} has 1 parent."
            "It appears to be a fast-forward merge and the reset strategy is risky."
            "The revert strategy is forced."
        )
        return

    parent2_sha = parent2.stdout.strip()
    if not expected_branch:
        # Normal path where the feature branch has already been deleted.
        _log(f"Skip anchor verification: feature branch does not exist (parent2={parent2_sha[:8]})")
        return

    fb_head = _git("rev-parse", expected_branch)
    if fb_head.returncode != 0:
        _log(
            f"Skip anchor verification: feature branch {expected_branch} has already been deleted"
            f"(parent2={parent2_sha[:8]})"
        )
        return

    fb_sha = fb_head.stdout.strip()
    if parent2_sha != fb_sha:
        _err(
            f"anchor validation failed: merge_commit^2 ({parent2_sha[:8]}) ≠"
            f"{expected_branch} tip ({fb_sha[:8]}). "
            "Other branches may have been merged or history may have been altered. Manual investigation required."
        )

    _log(f"anchor validation passed: parent2={parent2_sha[:8]} == {expected_branch} tip")


def _check_branch_worktree_clear(
    ticket_id: str, force: bool = False
) -> tuple[str | None, str | None]:
    """feature Brands + worktree checks that are not occupied.

    Args:
        ticket id: T-NNN format.
        force: True displacement only output warning (the actual clearance is user).

    Returns:
        (existing branch, existing worktree path) tuple. (None, None).

    Raises:
        SystemExit: Gas Detector + force=False.
    """
    existing_branch = get_feature_branch_for_ticket(ticket_id)
    existing_wt = get_worktree_path(ticket_id)

    if existing_branch is None and existing_wt is None:
        _log("Branch/worktree occupancy check passed (both empty)")
        return (None, None)

    msg_parts = []
    if existing_branch:
        msg_parts.append(f"feature branch {existing_branch} exists")
    if existing_wt:
        msg_parts.append(f"worktree {existing_wt} exists")
    msg = ", ".join(msg_parts)

    if force:
        _warn(f"Occupancy found (force passed): {msg}")
        return (existing_branch, existing_wt)

    _err(
        f"Branch/worktree occupancy detection — {msg}."
        "You can proceed with --force, but there is a high possibility of conflict."
        f"First, organize it with ‘git worktree remove’ and ‘git branch -D {existing_branch}’."
    )
    return (existing_branch, existing_wt)  # Unreachable (defensive)


# ─── Branch to push or not to push (T2.3) ─────────────────────────────────────────────────────


def _detect_push_state(merge_commit: str) -> PushState:
    """identify the push status of merge commit.

    `git branch -r --contains <merge commit> output
    sort as origin/develop / origin/main matching or whether.

    Args:
        merge commit: scan target SHA.

    Returns:
        - "main": reach to origin/main (or origin/master)
        - "pushed": origin/develop only reach
        - "local": origin/* to midway
    """
    result = _git("branch", "-r", "--contains", merge_commit)
    if result.returncode != 0:
        _warn(
            f"git branch -r --contains failed — assumed local: {result.stderr.strip()}"
        )
        return "local"

    remote_refs = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    has_main = any(
        ref in ("origin/main", "origin/master") for ref in remote_refs
    )
    has_develop = "origin/develop" in remote_refs

    if has_main:
        _log(f"push state: main (refs={remote_refs})")
        return "main"
    if has_develop:
        _log(f"push state: pushed (refs={remote_refs})")
        return "pushed"

    _log(f"push state: local (no refs or origin/* included)")
    return "local"


def _has_followup_commits(merge_commit: str) -> bool:
    """The head of development checks if it is ahead of merge commit (the follow-up commit accumulation).

    `git rev-list develop ^merge commit --count` > 0 if the follow-up commit exists.

    Args:
        merge commit: standard SHA.

    Returns:
        True if there is more than one end commit.
    """
    result = _git("rev-list", "develop", f"^{merge_commit}", "--count")
    if result.returncode != 0:
        _warn(
            f"Subsequent commit check fails — safely returns True: {result.stderr.strip()}"
        )
        return True
    try:
        count = int(result.stdout.strip())
    except ValueError:
        return True
    _log(f"Number of subsequent commits (develop ^merge_commit): {count}")
    return count > 0


# ─── Strategy 1: reset (T2.4) ─────────────────────────────────────────────────────


def _strategy_reset(merge_commit: str, ticket_id: str) -> None:
    """merge commit

    Pre-write backup reflog marker(`refs/backup/undo-T-NNN`)
    Recovers the possibility of recovering incorrect inputs.

    Args:
        merge commit: thumb commits to remove SHA.
        ticket id: T-NNN (used for back-up ref name).

    Raises:
        SystemExit: After-speed commit accumulation (automatic revert quarterly force).
    """
    if _has_followup_commits(merge_commit):
        _err(
            "The reset strategy cannot be used because develop has accumulated subsequent commits"
            "(Risk of data loss). Only possible with revert strategy —"
            "The main() flow ensures that _strategy_revert is automatically called regardless of whether there is a push or not."
        )

    _log("Strategy 1: proceed with reset --hard")

    # develop checkout
    _git("checkout", "develop", check=True)

    # Backup reflog marker
    backup_ref = f"refs/backup/undo-{ticket_id}"
    update_ref = _git(
        "update-ref",
        "-m",
        f"undo-done {ticket_id} backup before reset",
        backup_ref,
        "HEAD",
    )
    if update_ref.returncode == 0:
        _log(f"Create backup ref: {backup_ref} -> HEAD")
    else:
        _warn(
            f"Failed to create backup ref (continue): {update_ref.stderr.strip()}"
        )

    # reset --hard merge_commit^
    _git("reset", "--hard", f"{merge_commit}^", check=True)
    _log(f"complete develop reset: HEAD = {merge_commit}^ (remove merge commit)")


# ─── Strategy 2: revert (T2.5) ────────────────────────────────────────────────────


def _strategy_revert(merge_commit: str) -> None:
    """add a reverse change of merge commit to develop (revert -m 1).

    Args:
        merge commit: rendrilling mitt SHA.
    """
    _log("Strategy 2: revert -m 1 proceed")

    _git("checkout", "develop", check=True)
    revert = _git(
        "revert", "-m", "1", "--no-edit", merge_commit
    )
    if revert.returncode != 0:
        # Abort in case of collision
        _git("revert", "--abort")
        _err(
            f"revert fails — may be a crash or no change: {revert.stderr.strip()}"
        )

    head = _git("rev-parse", "HEAD")
    new_head = head.stdout.strip() if head.returncode == 0 else "?"
    _log(f"revert done: new HEAD = {new_head[:8]}")


# ─── Work tree regeneration (T2.6) ───────────────────────────────────────────────────


def _recreate_worktree(ticket_id: str, ticket_file: str) -> WorktreeInfo:
    """worktree manager.create worktree()

    Args:
        ticket id: T-NNN format.
        ticket file: ticket XML path (title for extraction).

    Returns:
        Created WorktreeInfo.

    Raises:
        SystemExit: generate failure.
    """
    ticket_data = parse_ticket_xml(ticket_file)
    title = ticket_data.get("title", "") or "untitled"

    _log(f"Start work tree regeneration: {ticket_id} (title={title!r})")
    info = create_worktree(ticket_id, title, command="implement")
    if info is None:
        _err(
            f"Failed to recreate worktree ({ticket_id})."
            "Feature branch or directory occupancy potential."
            "Please clean up manually and retry."
        )
    _log(f"Work tree regeneration completed: path={info.path} branch={info.branch_name}")
    return info


# ─── Kanban force transition (T2.7) ────────────────────────────────────────────────────


def _force_done_to_review(ticket_id: str, ticket_file: str) -> str:
    """Go to the ticket XML file done/ review ->/ and update status.

    Args:
        ticket id: T-NNN format.
        ticket file: Currently done/ in the ticket file path.

    Returns:
        New file path after moving.
    """
    _log(f"Kanban force transition: Done → Review ({ticket_id})")

    # 1. Update XML <status> to Review (file still in done/ location)
    update_ticket_status(ticket_file, "Review")
    _log(f"XML <status> update: Review")

    # 2. Move the file to the review/ directory
    new_path = move_ticket_to_status_dir(ticket_file, "Review")
    _log(f"Move file: {ticket_file} → {new_path}")

    return new_path


# ─── Post-output (T2.8) ────────────────────────────────────────────────────────


def _print_postscript(ticket_id: str, worktree: WorktreeInfo) -> None:
    """git status / log + Prints the following procedure instructions."""
    _log("=" * 60)
    _log("Rollback complete — post-state")
    _log("=" * 60)

    status_result = _git("status", "--short", "--branch")
    if status_result.returncode == 0:
        _log("git status:")
        for line in status_result.stdout.rstrip().splitlines():
            print(f"  {line}", flush=True)

    log_result = _git("log", "--oneline", "-5")
    if log_result.returncode == 0:
        _log("git log (last 5):")
        for line in log_result.stdout.rstrip().splitlines():
            print(f"  {line}", flush=True)

    print("", flush=True)
    _log(f"Next steps:")
    _log(f"1. Go to the worktree: cd {worktree.path}")
    _log(f"(feature branch {worktree.branch_name} has been recreated)")
    _log(f"2. Edit ticket: /wf -e {ticket_id}")
    _log(f"3. Rerun the workflow: /wf -s {ticket_id}")
    _log("")
    _log(
        f"Kanban status: {ticket_id} is back in the Review column."
        "You can demote Open with /wf -e or modify it directly and re-complete with /wf -d."
    )


# ─── main entry (T2.1) ──────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """argparse entry point. flow-undo-done wrapper is called.

    Args:
        argv: List of arguments for testing (using None sys.argv).

    Returns:
        0 (Property) / 2 (Property)
    """
    parser = argparse.ArgumentParser(
        prog="flow-undo-done",
        description=(
            "Automatically rolls back finished workflows to the Review stage."
            "Return the merge result of develop with reset or revert,"
            "After regenerating the feature branch + worktree, move Kanban to Done → Review."
        ),
        epilog=build_common_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "ticket",
        type=ticket_type,
        help="Done ticket number to roll back to (in the format T-NNN, NNN, #N).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Occupancy/omissions discovered during the verification stage are downgraded to warnings."
            "If merge_commit is missed, reflog fallback is also activated."
        ),
    )
    args = parser.parse_args(argv)
    ticket_id: str = args.ticket
    force: bool = args.force

    _log(f"=== Done Start rollback: {ticket_id} (force={force}) ===")

    # T2.2 — Pre-validation
    ticket_file = _validate_ticket_done(ticket_id)

    # Case without merge (merge_skipped): Without work tree/branch such as research/document
    # cmd_done This is a ticket for simple file movement only. result.merge_commit empty.
    # Skip all reset/revert strategy + work tree regeneration and only perform file movement.
    _ticket_data = parse_ticket_xml(ticket_file)
    _result = _ticket_data.get("result") or {}
    if not (_result.get("merge_commit") or "").strip():
        _log(
            "No merge_commit — Simple file move branch (Done case without merge like research/documents etc.)"
        )
        _force_done_to_review(ticket_id, ticket_file)
        _log(
            f"Kanban status: {ticket_id} is back in the Review column."
            "You can demote Open with /wf -e or modify it directly and re-complete with /wf -d."
        )
        return 0

    merge_commit = _load_merge_commit(ticket_id, ticket_file, force)

    # Existing feature branch (if present, use for anchor verification)
    existing_branch = get_feature_branch_for_ticket(ticket_id) or ""
    _verify_merge_anchor(merge_commit, existing_branch)

    # occupancy inspection
    _check_branch_worktree_clear(ticket_id, force=force)

    # T2.3 — Branch to push or not to push
    push_state = _detect_push_state(merge_commit)
    has_followup = _has_followup_commits(merge_commit)

    if push_state == "main":
        if not force:
            _err(
                f"merge_commit {merge_commit[:8]} reached origin/main ."
                "To avoid violating the main direct commit rule, the reset strategy cannot be used."
                "Only revert strategy is possible. Specify --force to proceed."
            )
        _log("main reach case — force revert strategy + force confirm agreement")
        _strategy_revert(merge_commit)
    elif push_state == "pushed" or has_followup:
        # Force revert strategy when pushed or when subsequent commits are accumulated (force-push avoidance + data loss prevention)
        if push_state == "pushed":
            _log("origin/develop reach — revert strategy (force-push avoidance)")
        else:
            _log("Accumulate subsequent commits — revert strategy (to prevent data loss)")
        _strategy_revert(merge_commit)
    else:
        # local-only + no subsequent commit → reset possible
        _log("local-only + no subsequent commits — reset strategy")
        _strategy_reset(merge_commit, ticket_id)

    # T2.6 — Regenerate the work tree
    worktree = _recreate_worktree(ticket_id, ticket_file)

    # T2.7 — Kanban force transition (Done → Review)
    _force_done_to_review(ticket_id, ticket_file)

    # T2.8 — Post-output
    _print_postscript(ticket_id, worktree)

    _log(f"=== Done Rollback completed: {ticket_id} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
