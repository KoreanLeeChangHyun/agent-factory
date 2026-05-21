"""Parse flow-conveyor complete and undo-complete command output."""

from __future__ import annotations

import re


COMPLETE_MERGE_OK_RE = re.compile(
    r"(.+?)\s*->\s*(?:develop\s+Merge\s+Complete|Complete\s+development\s+merge|Development\s+completion)\s+\(([0-9a-f]{6,})\)",
)
COMPLETE_CONFLICT_HEADER = re.compile(r"^\[ERROR\].*(merge|conflict|collision)", re.IGNORECASE)
COMPLETE_DIRTY_HEADER = re.compile(r"(Uncommitted|Micommit)\s+File\s+List\s*:|Crash\s+file\s*:", re.IGNORECASE)
COMPLETE_PATH_RE = re.compile(r"^\s+-\s+(.+)$")
COMPLETE_CONFLICT_WARN_RE = re.compile(
    r"\[WARN\].*(merge\s*conflict|merge\s+conflict|merging\s+conflict)",
    re.IGNORECASE,
)

UNDO_STRATEGY_RESET = re.compile(r"\[undo-complete\]\s+Strategy\s+1\s*:\s*reset")
UNDO_STRATEGY_REVERT = re.compile(r"\[undo-complete\]\s+Strategy\s+2\s*:\s*revert")
UNDO_WORKTREE_RE = re.compile(
    r"\[undo-complete\]\s+Worktree\s+(?:Recreate\s+Complete|Regeneration)\s*:\s*path=(\S+)\s+branch=(\S+)",
)
UNDO_ERROR_RE = re.compile(r"\[undo-complete\]\s+ERROR\s*:\s*(.+)")


def classify_complete_failure(stdout: str, stderr: str) -> dict:
    """Classify `flow-conveyor complete` failures for board API responses."""
    stdout = stdout.replace("\\n", "\n")
    stderr = stderr.replace("\\n", "\n")
    lines = stdout.splitlines()
    error_kind = "other"
    conflicts: list[str] = []
    dirty_files: list[str] = []
    error_message = ""
    in_dirty_block = False

    for line in lines:
        if COMPLETE_CONFLICT_HEADER.match(line):
            error_kind = "merge_conflict"
            error_message = line.strip()
            in_dirty_block = False
        elif COMPLETE_CONFLICT_WARN_RE.search(line):
            if error_kind == "other":
                error_kind = "merge_conflict"
            if not error_message:
                error_message = line.strip()
            in_dirty_block = False
        elif COMPLETE_DIRTY_HEADER.search(line):
            if error_kind == "merge_conflict":
                in_dirty_block = False
            else:
                error_kind = "dirty_worktree"
                in_dirty_block = True
        elif COMPLETE_PATH_RE.match(line):
            path_val = COMPLETE_PATH_RE.match(line).group(1).strip()
            if error_kind == "merge_conflict":
                conflicts.append(path_val)
            elif in_dirty_block:
                dirty_files.append(path_val)
        elif error_kind == "other" and line.strip() and not line.lstrip().startswith("["):
            error_kind = "dirty_worktree"
            dirty_files.append(line.strip())
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
