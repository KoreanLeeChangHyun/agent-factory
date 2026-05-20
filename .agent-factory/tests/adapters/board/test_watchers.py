"""Board watcher adapter tests."""

from __future__ import annotations

import os
import time
from pathlib import Path

from engine.adapters.board.watchers import FileWatcher, GitBranchWatcher


class _Logger:
    def __init__(self) -> None:
        self.exceptions: list[str] = []

    def exception(self, message: str) -> None:
        self.exceptions.append(message)


def test_file_watcher_reports_added_files_by_event_type(tmp_path: Path) -> None:
    watched = tmp_path / "tickets" / "open"
    watched.mkdir(parents=True)
    events: list[tuple[str, list[str]]] = []

    watcher = FileWatcher(
        str(tmp_path),
        lambda event_type, files: events.append((event_type, sorted(files))),
        watch_dirs={os.path.join("tickets", "open"): "kanban"},
        interval=0.01,
    )

    (watched / "T-001.xml").write_text("<ticket />", encoding="utf-8")
    watcher.check_changes()

    assert events == [("kanban", ["T-001.xml"])]


def test_git_branch_watcher_reports_branch_change(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    head = git_dir / "HEAD"
    head.write_text("ref: refs/heads/main\n", encoding="utf-8")
    branches = iter(["main", "feature"])
    events: list[str] = []

    watcher = GitBranchWatcher(
        str(tmp_path),
        events.append,
        get_branch=lambda _root: next(branches),
        interval=0.01,
        logger=_Logger(),
    )
    time.sleep(0.01)
    head.write_text("ref: refs/heads/feature\n", encoding="utf-8")

    watcher.check()

    assert events == ["feature"]


def test_git_branch_watcher_swallows_callback_errors(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    head = git_dir / "HEAD"
    head.write_text("ref: refs/heads/main\n", encoding="utf-8")
    branches = iter(["main", "feature"])
    logger = _Logger()

    def fail(_branch: str) -> None:
        raise RuntimeError("boom")

    watcher = GitBranchWatcher(
        str(tmp_path),
        fail,
        get_branch=lambda _root: next(branches),
        interval=0.01,
        logger=logger,
    )
    time.sleep(0.01)
    head.write_text("ref: refs/heads/feature\n", encoding="utf-8")

    watcher.check()

    assert logger.exceptions == ["GitBranchWatcher on change Callback failed"]
