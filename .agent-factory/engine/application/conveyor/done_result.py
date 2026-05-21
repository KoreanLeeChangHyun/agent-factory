"""Parse flow-kanban done and undo-done command output."""

from __future__ import annotations

import re


DONE_MERGE_OK_RE = re.compile(
    r"(.+?)\s*->\s*develop\s+Merge\s+Complete\s+\(([0-9a-f]{6,})\)",
)
DONE_CONFLICT_HEADER = re.compile(r"^\[ERROR\]")
DONE_DIRTY_HEADER = re.compile(r"Uncommitted\s+File\s+List\s*:")
DONE_PATH_RE = re.compile(r"^\s+-\s+(.+)$")
DONE_CONFLICT_WARN_RE = re.compile(
    r"\[WARN\].*(merge\s*conflict|merge\s+conflict)",
    re.IGNORECASE,
)

UNDO_STRATEGY_RESET = re.compile(r"\[undo-done\]\s+Strategy\s+1\s*:\s*reset")
UNDO_STRATEGY_REVERT = re.compile(r"\[undo-done\]\s+Strategy\s+2\s*:\s*revert")
UNDO_WORKTREE_RE = re.compile(
    r"\[undo-done\]\s+Worktree\s+Recreate\s+Done\s*:\s*path=(\S+)\s+branch=(\S+)",
)
UNDO_ERROR_RE = re.compile(r"\[undo-done\]\s+ERROR\s*:\s*(.+)")


def classify_done_failure(stdout: str, stderr: str) -> dict:
    """Classify `flow-kanban done` failures for board API responses."""
    lines = stdout.splitlines()
    error_kind = "other"
    conflicts: list[str] = []
    dirty_files: list[str] = []
    error_message = ""
    in_dirty_block = False

    for line in lines:
        if DONE_CONFLICT_HEADER.match(line):
            error_kind = "merge_conflict"
            error_message = line.strip()
            in_dirty_block = False
        elif DONE_CONFLICT_WARN_RE.search(line):
            if error_kind == "other":
                error_kind = "merge_conflict"
            if not error_message:
                error_message = line.strip()
            in_dirty_block = False
        elif DONE_DIRTY_HEADER.search(line):
            error_kind = "dirty_worktree"
            in_dirty_block = True
        elif DONE_PATH_RE.match(line):
            path_val = DONE_PATH_RE.match(line).group(1).strip()
            if error_kind == "merge_conflict":
                conflicts.append(path_val)
            elif in_dirty_block:
                dirty_files.append(path_val)
        else:
            in_dirty_block = False
            if not error_message and line.strip():
                error_message = line.strip()

    stderr_text = stderr.strip()
    if not error_message and stderr_text:
        error_message = stderr_text

    return {
        "error_kind": error_kind,
        "conflicts": conflicts,
        "dirty_files": dirty_files,
        "message": error_message,
    }

