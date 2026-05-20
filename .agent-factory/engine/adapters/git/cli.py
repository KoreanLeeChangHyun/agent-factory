"""Subprocess gateway for Git commands."""

from __future__ import annotations

import subprocess
from pathlib import Path


def run_git(
    *args: str,
    repo_path: str | Path,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    """Run `git -C <repo_path> ...` and return the completed process."""
    cmd = ["git", "-C", str(repo_path), *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

