"""Filesystem and git watchers for board event fan-out."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from typing import Any


class FileWatcher:
    """Poll configured directories and report changed file names by event type."""

    def __init__(
        self,
        project_root: str,
        on_change: Callable[[str, list[str]], None],
        *,
        watch_dirs: Mapping[str, str],
        interval: float,
    ) -> None:
        self._project_root = project_root
        self._watch_dirs = dict(watch_dirs)
        self._interval = interval
        self._snapshots: dict[str, dict[str, float]] = {}
        self._on_change = on_change
        self._running = False
        self._build_initial_snapshots()

    def _build_initial_snapshots(self) -> None:
        for rel_dir in self._watch_dirs:
            abs_dir = os.path.join(self._project_root, rel_dir)
            self._snapshots[rel_dir] = self._scan_dir(abs_dir)

    def _scan_dir(self, abs_dir: str) -> dict[str, float]:
        result: dict[str, float] = {}
        if not os.path.isdir(abs_dir):
            return result
        try:
            result["__dir__"] = os.stat(abs_dir).st_mtime
            with os.scandir(abs_dir) as entries:
                for entry in entries:
                    try:
                        result[entry.path] = entry.stat().st_mtime
                    except OSError:
                        pass
        except OSError:
            pass
        return result

    def run(self) -> None:
        self._running = True
        while self._running:
            time.sleep(self._interval)
            self.check_changes()

    def stop(self) -> None:
        self._running = False

    def check_changes(self) -> None:
        changed_files: dict[str, list[str]] = {}
        for rel_dir, event_type in self._watch_dirs.items():
            abs_dir = os.path.join(self._project_root, rel_dir)
            old_snapshot = self._snapshots[rel_dir]
            new_snapshot = self._scan_dir(abs_dir)
            if new_snapshot == old_snapshot:
                continue

            self._snapshots[rel_dir] = new_snapshot
            old_paths = {p for p in old_snapshot if p != "__dir__"}
            new_paths = {p for p in new_snapshot if p != "__dir__"}
            modified = {
                p for p in old_paths & new_paths
                if old_snapshot[p] != new_snapshot[p]
            }
            added = new_paths - old_paths
            removed = old_paths - new_paths
            changed_files.setdefault(event_type, []).extend(
                os.path.basename(p) for p in modified | added | removed
            )

        for event_type, files in changed_files.items():
            self._on_change(event_type, files)


class GitBranchWatcher:
    """Poll `.git/HEAD` and report branch changes."""

    def __init__(
        self,
        project_root: str,
        on_change: Callable[[str], None],
        *,
        get_branch: Callable[[str], str],
        interval: float,
        logger: Any,
    ) -> None:
        self._project_root = project_root
        self._on_change = on_change
        self._get_branch = get_branch
        self._interval = interval
        self._logger = logger
        self._running = False
        self._last_branch = get_branch(project_root)
        self._head_path = os.path.join(project_root, ".git", "HEAD")
        self._last_head_mtime = self._read_head_mtime()

    def _read_head_mtime(self) -> float:
        try:
            return os.stat(self._head_path).st_mtime
        except OSError:
            return 0.0

    def run(self) -> None:
        self._running = True
        while self._running:
            time.sleep(self._interval)
            self.check()

    def stop(self) -> None:
        self._running = False

    def check(self) -> None:
        mtime = self._read_head_mtime()
        if mtime == self._last_head_mtime:
            return
        self._last_head_mtime = mtime
        new_branch = self._get_branch(self._project_root)
        if new_branch and new_branch != self._last_branch:
            self._last_branch = new_branch
            try:
                self._on_change(new_branch)
            except Exception:  # noqa: BLE001
                self._logger.exception("GitBranchWatcher on_change 콜백 실패")


__all__ = ["FileWatcher", "GitBranchWatcher"]
