"""branch strategy.py - Git brand strategy management module.

Create/delete/Search and develop/main Brands by workflow
Detecting. worktree manager.py

Public API:
    get main branch: main or master branch detection
    ensure develop branch: create a development brand if there is no local
    create feature branch: feat/T-NNN - Create a new brand
    delete feature branch: feature Delete Brand Name (Local)
    sanitize branch name: Brand Name Safety Conversion
    get feature branch for ticket: Search feature brand name associated with the ticket
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

# ─── sys.path guaranteed ───────────────────────────────────────────────────────────────

_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import resolve_project_root

# ─── Constant ───────────────────────────────────────────────────────────────────────

_BRANCH_NAME_MAX_LEN: int = 50
_FEATURE_PREFIX: str = "feat/"

# Character patterns that cannot be used in git branch names (Korean characters are allowed)
# ~ ^ : ? * [\ and space, control characters, DEL
_GIT_FORBIDDEN_CHARS: re.Pattern[str] = re.compile(r"[~^:?*\[\]\\@{}\x00-\x1f\x7f]")


# ─── Internal Utilities ────────────────────────────────────────────────────────────────


def _git(
    *args: str, repo_path: str | None = None
) -> subprocess.CompletedProcess[str]:
    """execute git command and return the result.

    Args:
        *args: git sub-mand and arguments.
        repo path: git repository path. use resolve project root() if None.

    Returns:
        CompletedProcess instance.
    """
    cwd = repo_path or resolve_project_root()
    cmd = ["git", "-C", cwd] + list(args)
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=30
    )


def _get_local_branches(repo_path: str | None = None) -> list[str]:
    """Returns the local brand list.

    Args:
        repo path: git repository path. Use the project root if None.

    Returns:
        local brand name list (refs/heads/ excluded).
    """
    result = _git("branch", "--list", "--format=%(refname:short)", repo_path=repo_path)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _warn(msg: str) -> None:
    """Prints a warning message to stderr."""
    print(f"[WARN] branch_strategy: {msg}", file=sys.stderr)


# ─── Public API ─────────────────────────────────────────────────────────────────────


def sanitize_branch_name(raw: str) -> str:
    """git converts a brand name into a safe format.

    Hangle is allowed, converting blank/underscour into hyphen
    Remove git ban character. We are working together with our customers.
    Limits up to 50 characters.

    Args:
        raw: original string (ticket title etc.).

    Returns:
        Secure strings in git brand name (up to 50 characters).
    """
    name: str = raw.strip()

    # Space, underscore → hyphen
    name = re.sub(r"[\s_]+", "-", name)

    # Remove git banned characters
    name = _GIT_FORBIDDEN_CHARS.sub("", name)

    # Starts/ends with a dot (.) or avoid consecutive dots (..)
    name = re.sub(r"\.{2,}", ".", name)

    # Remove slashes (avoid slashes other than feature prefix)
    name = name.replace("/", "-")

    # Serial hyphen → single hyphen
    name = re.sub(r"-{2,}", "-", name)

    # Remove leading/trailing hyphens and dots
    name = name.strip("-.")

    # maximum length limit
    if len(name) > _BRANCH_NAME_MAX_LEN:
        name = name[:_BRANCH_NAME_MAX_LEN].rstrip("-.")

    return name


def get_main_branch(repo_path: str | None = None) -> str:
    """returns by detecting the main or master branch.

    If you're looking for 'main' in the local brand list, you'll find 'master'.
    returns the default 'main' without both.

    Args:
        repo path: git repository path. Use the project root if None.

    Returns:
        Detected main brand name ('main' or 'master'). 'main' without both.
    """
    branches = _get_local_branches(repo_path)
    if "main" in branches:
        return "main"
    if "master" in branches:
        return "master"
    return "main"


def ensure_develop_branch(repo_path: str | None = None) -> bool:
    """If you don't have a develop brand, you can create locally based on main.

    If you already have a development branch, return true without any work.
    create a develop brand based on the main/master brand.

    Args:
        repo path: git repository path. Use the project root if None.

    Returns:
        True if develop brand exists or successfully generates.
        False.
    """
    branches = _get_local_branches(repo_path)
    if "develop" in branches:
        return True

    main_branch = get_main_branch(repo_path)
    result = _git("branch", "develop", main_branch, repo_path=repo_path)
    if result.returncode != 0:
        _warn(f"Failed to create develop branch: {result.stderr.strip()}")
        return False
    return True


def create_feature_branch(
    ticket_number: str,
    title: str,
    base: str = "develop",
    repo_path: str | None = None,
) -> str:
    """create a feature brand and return a brand name.

    feat/T-NNN - Create a brand based on the base brand.
    If you already have the feature brand of the same ticket, you will return the existing brand name.

    Args:
        ticket number: ticket number (e.g. 'T-001', '001').
        title: ticket title. sanitize branch name is refined.
        base: standard brand. default 'develop'
        repo path: git repository path. Use the project root if None.

    Returns:
        Created or existing feature brand name (e.g. 'feat/T-001-title').
        empty strings when the creation fails.
    """
    # Ticket number normalization: ensures 'T-001' format
    if not ticket_number.startswith("T-"):
        ticket_number = f"T-{ticket_number}"

    # Search for existing feature branches
    existing = get_feature_branch_for_ticket(ticket_number, repo_path)
    if existing:
        return existing

    sanitized = sanitize_branch_name(title)
    branch_name = f"{_FEATURE_PREFIX}{ticket_number}-{sanitized}"

    result = _git("branch", branch_name, base, repo_path=repo_path)
    if result.returncode != 0:
        _warn(f"Failed to create feature branch: {result.stderr.strip()}")
        return ""

    return branch_name


def delete_feature_branch(
    branch_name: str, repo_path: str | None = None
) -> bool:
    """Delete local feature brand.

    Use Force Delete(-D) and output warning only when deletion failed
    returns False (not ending process).
    merge to develop() is only called in the success path, so the merge completion is guaranteed.

    Args:
        branch name: Brand name to delete (e.g. 'feat/T-001-title').
        repo path: git repository path. Use the project root if None.

    Returns:
        True, False fails when deleting success.
    """
    result = _git("branch", "-D", branch_name, repo_path=repo_path)
    if result.returncode != 0:
        _warn(
            f"Failed to delete branch ({branch_name}): {result.stderr.strip()}"
        )
        return False
    return True


def get_feature_branch_for_ticket(
    ticket_number: str, repo_path: str | None = None
) -> str | None:
    """Search the feature branch connected to the ticket number.

    The first brand matching "feat/T-NNN-*" pattern during local branding
    return. None.

    Args:
        ticket number: ticket number (e.g. 'T-001').
        repo path: git repository path. Use the project root if None.

    Returns:
        Match Brand Name or None.
    """
    if not ticket_number.startswith("T-"):
        ticket_number = f"T-{ticket_number}"

    prefix = f"{_FEATURE_PREFIX}{ticket_number}-"
    branches = _get_local_branches(repo_path)
    for branch in branches:
        if branch.startswith(prefix):
            return branch
    return None
