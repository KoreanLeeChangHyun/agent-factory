"""Tests for the Git subprocess adapter."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest import mock

from engine.adapters.git.cli import run_git


def test_run_git_uses_git_c_with_text_capture() -> None:
    completed = subprocess.CompletedProcess(
        args=["git"],
        returncode=0,
        stdout="develop\n",
        stderr="",
    )

    with mock.patch("engine.adapters.git.cli.subprocess.run", return_value=completed) as run:
        result = run_git("branch", "--show-current", repo_path=Path("/repo"), timeout=7)

    assert result is completed
    run.assert_called_once_with(
        ["git", "-C", "/repo", "branch", "--show-current"],
        capture_output=True,
        text=True,
        timeout=7,
    )

