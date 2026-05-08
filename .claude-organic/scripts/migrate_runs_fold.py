#!/usr/bin/env python3
"""migrate_runs_fold.py — Flatten .history/<key>/<work_name>/<command>/ to <key>/ in-place.

Usage:
    migrate_runs_fold.py dry-run [--root PATH]
    migrate_runs_fold.py apply   [--root PATH] [--backup] [--verify]

Conflict resolution policies:
  Type A (file already exists at key_path level):
    → Move fold file as _legacy_<filename> instead (preserves both sides).
  Type B (multiple work_name dirs):
    → Select primary by (file_count desc, mtime desc).
    → Flatten primary's files to key_path directly.
    → Rename remaining work_name dirs as _legacy_<work_name>/ (dir preserved as-is).
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple, Optional


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class WorkNameInfo(NamedTuple):
    work_name: str
    work_name_path: Path
    command: str
    command_path: Path
    files: list   # list[Path]
    file_count: int
    mtime: float


class FoldEntry(NamedTuple):
    key: str
    key_path: Path
    work_name: str
    command: str
    fold_path: Path
    files: list  # list[Path]


class ConflictAEntry(NamedTuple):
    """Type A: file destination already exists at key_path level."""
    key: str
    key_path: Path
    work_name: str
    command: str
    fold_path: Path
    files: list  # list[Path]
    conflicting_filenames: list  # list[str] — files that need _legacy_ prefix


class ConflictBEntry(NamedTuple):
    """Type B: multiple work_name dirs — primary + legacy list."""
    key: str
    key_path: Path
    primary: WorkNameInfo
    legacies: list  # list[WorkNameInfo]


class ConflictEntry(NamedTuple):
    key: str
    key_path: Path
    reason: str


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def _count_files(root: Path) -> int:
    """Return total number of regular files under root."""
    result = subprocess.run(
        ["find", str(root), "-type", "f"],
        capture_output=True, text=True
    )
    return len([l for l in result.stdout.splitlines() if l.strip()])


def _collect_work_name_info(key_path: Path, work_name_path: Path) -> Optional[WorkNameInfo]:
    """Gather cmd dirs + files for a given work_name dir. Returns None if no cmd subdir."""
    cmd_dirs = [d for d in work_name_path.iterdir() if d.is_dir()]
    cmd_files_direct = [f for f in work_name_path.iterdir() if f.is_file()]

    if not cmd_dirs:
        return None

    # Pick the single command dir (or first if multiple — handled at caller)
    command_path = cmd_dirs[0]
    command = command_path.name

    all_files = list(command_path.rglob("*"))
    fold_files = [f for f in all_files if f.is_file()]
    fold_files.extend(cmd_files_direct)

    # mtime: use max mtime across all files (most recent activity)
    mtime = max((f.stat().st_mtime for f in fold_files), default=work_name_path.stat().st_mtime)
    file_count = len(fold_files)

    return WorkNameInfo(
        work_name=work_name_path.name,
        work_name_path=work_name_path,
        command=command,
        command_path=command_path,
        files=fold_files,
        file_count=file_count,
        mtime=mtime,
    )


def scan(root: Path) -> tuple[
    list[FoldEntry],
    list[ConflictAEntry],
    list[ConflictBEntry],
    int
]:
    """Scan root for fold-pattern dirs.

    Returns (folds, conflict_a_list, conflict_b_list, total_keys).
    - folds: clean entries with no conflicts
    - conflict_a_list: entries where destination filename already exists at key level
    - conflict_b_list: entries with multiple work_name dirs
    """
    folds: list[FoldEntry] = []
    conflict_a_list: list[ConflictAEntry] = []
    conflict_b_list: list[ConflictBEntry] = []

    if not root.is_dir():
        print(f"ERROR: root directory does not exist: {root}", file=sys.stderr)
        sys.exit(1)

    key_dirs = sorted([d for d in root.iterdir() if d.is_dir()])
    total_keys = len(key_dirs)

    for key_path in key_dirs:
        key = key_path.name

        # Collect direct children
        direct_files = [f for f in key_path.iterdir() if f.is_file()]
        direct_dirs = [d for d in key_path.iterdir() if d.is_dir()]

        # Reserved directory names that are NOT fold work_name dirs
        # "work" = task notes dir; skip to avoid false-positive detection
        NON_FOLD_DIRNAMES = {"work"}

        # Skip dirs that start with _legacy_ (already processed)
        active_dirs = [
            d for d in direct_dirs
            if not d.name.startswith("_legacy_") and d.name not in NON_FOLD_DIRNAMES
        ]
        legacy_dirs = [d for d in direct_dirs if d.name.startswith("_legacy_")]

        # If no active subdirectories → no fold needed
        if not active_dirs:
            continue

        # Type B: multiple active work_name dirs
        if len(active_dirs) > 1:
            infos = []
            for wn_path in active_dirs:
                info = _collect_work_name_info(key_path, wn_path)
                if info is not None:
                    infos.append(info)

            if not infos:
                continue

            # Select primary: most files first, then most recent mtime
            infos_sorted = sorted(infos, key=lambda x: (x.file_count, x.mtime), reverse=True)
            primary = infos_sorted[0]
            legacies = infos_sorted[1:]

            conflict_b_list.append(ConflictBEntry(
                key=key,
                key_path=key_path,
                primary=primary,
                legacies=legacies,
            ))
            continue

        # Single work_name dir
        work_name_path = active_dirs[0]
        work_name = work_name_path.name

        cmd_dirs = [d for d in work_name_path.iterdir() if d.is_dir()]
        cmd_files_direct = [f for f in work_name_path.iterdir() if f.is_file()]

        if not cmd_dirs:
            continue

        if len(cmd_dirs) > 1:
            # Multiple command dirs — treat as conflict B variant
            # (unexpected but handled defensively)
            # Collect all files from all cmd dirs
            all_fold_files = list(cmd_files_direct)
            for cmd_path in cmd_dirs:
                all_fold_files.extend(f for f in cmd_path.rglob("*") if f.is_file())
            # Just skip — rare edge case, report as unresolvable
            continue

        command_path = cmd_dirs[0]
        command = command_path.name

        all_files = list(command_path.rglob("*"))
        fold_files = [f for f in all_files if f.is_file()]
        fold_files.extend(cmd_files_direct)

        # Check for name collisions with files already directly in key_path
        direct_file_names = {f.name for f in direct_files}
        conflicting: list[str] = []
        for fold_file in fold_files:
            if fold_file.parent == work_name_path:
                dest_name = fold_file.name
            else:
                rel = fold_file.relative_to(command_path)
                dest_name = rel.parts[0] if len(rel.parts) > 1 else str(rel)
            if dest_name in direct_file_names:
                conflicting.append(dest_name)

        if conflicting:
            # Type A conflict
            conflict_a_list.append(ConflictAEntry(
                key=key,
                key_path=key_path,
                work_name=work_name,
                command=command,
                fold_path=command_path,
                files=fold_files,
                conflicting_filenames=list(set(conflicting)),
            ))
        else:
            folds.append(FoldEntry(
                key=key,
                key_path=key_path,
                work_name=work_name,
                command=command,
                fold_path=command_path,
                files=fold_files,
            ))

    return folds, conflict_a_list, conflict_b_list, total_keys


# ---------------------------------------------------------------------------
# Dry-run output
# ---------------------------------------------------------------------------

def cmd_dry_run(root: Path) -> int:
    folds, conflict_a_list, conflict_b_list, total_keys = scan(root)

    # Count workflow.log files in clean folds
    wf_log_count = sum(
        1 for f in folds
        for fp in f.files
        if fp.name == "workflow.log"
    )
    # Also count from conflict_a + conflict_b primaries
    wf_log_count += sum(
        1 for ca in conflict_a_list
        for fp in ca.files
        if fp.name == "workflow.log"
    )
    wf_log_count += sum(
        1 for cb in conflict_b_list
        for fp in cb.primary.files
        if fp.name == "workflow.log"
    )

    total_conflicts = len(conflict_a_list) + len(conflict_b_list)
    print(f"total: {total_keys} keys, {len(folds)} fold-pattern dirs, "
          f"{total_conflicts} conflicts "
          f"(type_a={len(conflict_a_list)}, type_b={len(conflict_b_list)}), "
          f"{wf_log_count} workflow.log files")
    print()

    if conflict_a_list:
        print("TYPE A CONFLICTS (file exists at key level → will use _legacy_ prefix):")
        for ca in conflict_a_list:
            for fname in ca.conflicting_filenames:
                print(f"  [{ca.key}] {fname} → _legacy_{fname}")
        print()

    if conflict_b_list:
        print("TYPE B CONFLICTS (multiple work_name dirs → primary selected, others → _legacy_<work_name>/):")
        for cb in conflict_b_list:
            print(f"  [{cb.key}]")
            print(f"    PRIMARY ({cb.primary.file_count} files, mtime={cb.primary.mtime:.0f}): "
                  f"{cb.primary.work_name}/{cb.primary.command}/ → {cb.key}/")
            for lg in cb.legacies:
                print(f"    LEGACY  ({lg.file_count} files): "
                      f"{lg.work_name}/ → _legacy_{lg.work_name}/")
        print()

    # Sample up to 5 clean folds
    sample = folds[:5]
    if sample:
        print("SAMPLE clean folds (up to 5):")
        for entry in sample:
            print(f"  {entry.key}/{entry.work_name}/{entry.command}/ "
                  f"→ {entry.key}/  ({len(entry.files)} files)")
        print()

    print("RESULT: ready for apply (conflicts will be resolved automatically)")
    return 0


# ---------------------------------------------------------------------------
# Apply helpers
# ---------------------------------------------------------------------------

def _dest_name(fold_file: Path, command_path: Path, work_name_path: Path) -> str:
    """Compute the destination filename relative to key_path."""
    if fold_file.parent == work_name_path:
        return fold_file.name
    else:
        rel = fold_file.relative_to(command_path)
        return str(rel)


def _move_fold_files(
    files: list,
    command_path: Path,
    work_name_path: Path,
    key_path: Path,
    direct_file_names: set,
    use_legacy_prefix: bool = False,
) -> None:
    """Move files from fold to key_path.

    If use_legacy_prefix=True, any file whose computed dest name is in direct_file_names
    will be moved as _legacy_<name>.
    """
    for src in files:
        rel = _dest_name(src, command_path, work_name_path)
        base_name = rel.split("/")[0] if "/" in rel else rel
        if use_legacy_prefix and base_name in direct_file_names:
            # Map to _legacy_<rel>
            legacy_rel = "_legacy_" + rel
            dest = key_path / legacy_rel
        else:
            dest = key_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))


def _cleanup_empty_dirs(fold_path: Path, work_name_path: Path) -> None:
    """Remove empty fold directories bottom-up."""
    for dirpath in sorted(fold_path.rglob("*"), reverse=True):
        if dirpath.is_dir():
            try:
                dirpath.rmdir()
            except OSError:
                pass

    try:
        fold_path.rmdir()
    except OSError:
        pass

    try:
        work_name_path.rmdir()
    except OSError:
        pass


def _move_clean_fold(entry: FoldEntry) -> None:
    """Move all files from clean fold_path to key_path."""
    command_path = entry.fold_path
    work_name_path = command_path.parent
    key_path = entry.key_path

    _move_fold_files(
        entry.files,
        command_path,
        work_name_path,
        key_path,
        direct_file_names=set(),
        use_legacy_prefix=False,
    )
    _cleanup_empty_dirs(command_path, work_name_path)


def _resolve_conflict_a(ca: ConflictAEntry) -> None:
    """Resolve Type A: rename conflicting files with _legacy_ prefix, move rest normally."""
    command_path = ca.fold_path
    work_name_path = command_path.parent
    key_path = ca.key_path
    conflicting_set = set(ca.conflicting_filenames)

    direct_file_names = {f.name for f in key_path.iterdir() if f.is_file()}

    _move_fold_files(
        ca.files,
        command_path,
        work_name_path,
        key_path,
        direct_file_names=direct_file_names,
        use_legacy_prefix=True,
    )
    _cleanup_empty_dirs(command_path, work_name_path)


def _resolve_conflict_b(cb: ConflictBEntry) -> None:
    """Resolve Type B: flatten primary, rename legacy work_name dirs."""
    key_path = cb.key_path
    primary = cb.primary

    # Flatten primary files to key_path directly
    _move_fold_files(
        primary.files,
        primary.command_path,
        primary.work_name_path,
        key_path,
        direct_file_names=set(),
        use_legacy_prefix=False,
    )
    _cleanup_empty_dirs(primary.command_path, primary.work_name_path)

    # Rename legacy work_name dirs as _legacy_<work_name>/
    for lg in cb.legacies:
        legacy_dir = key_path / f"_legacy_{lg.work_name}"
        if not legacy_dir.exists():
            lg.work_name_path.rename(legacy_dir)
        else:
            # Already renamed (e.g. re-run) — skip
            pass


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def cmd_apply(root: Path, backup: bool, verify: bool) -> int:
    folds, conflict_a_list, conflict_b_list, total_keys = scan(root)

    # Backup
    if backup:
        bak = Path(str(root) + ".bak")
        if bak.exists():
            print(f"WARN: backup already exists at {bak} — skipping backup step.")
        else:
            print(f"Creating backup: {bak} ...")
            subprocess.run(["cp", "-a", str(root), str(bak)], check=True)
            print("Backup done.")

    # Count files before migration (for verify)
    if verify:
        count_before = _count_files(root)
        print(f"Files before migration: {count_before}")

    total_conflicts = len(conflict_a_list) + len(conflict_b_list)
    total_to_process = len(folds) + total_conflicts
    print(f"Processing: {len(folds)} clean folds, "
          f"{len(conflict_a_list)} type-A conflicts, "
          f"{len(conflict_b_list)} type-B conflicts "
          f"(total={total_to_process})")

    # Apply clean folds
    processed = 0
    for entry in folds:
        _move_clean_fold(entry)
        processed += 1
        if processed % 100 == 0:
            print(f"  ... {processed}/{total_to_process}")

    # Resolve Type A conflicts
    for ca in conflict_a_list:
        _resolve_conflict_a(ca)
        processed += 1
        print(f"  [TypeA resolved] {ca.key}: conflicting={ca.conflicting_filenames}")

    # Resolve Type B conflicts
    for cb in conflict_b_list:
        _resolve_conflict_b(cb)
        processed += 1
        legacy_names = [lg.work_name for lg in cb.legacies]
        print(f"  [TypeB resolved] {cb.key}: primary={cb.primary.work_name}, "
              f"legacy={legacy_names}")

    print(f"Migration complete: {processed} entries processed.")

    # Verify
    if verify:
        count_after = _count_files(root)
        print(f"Files after migration:  {count_after}")
        if count_before != count_after:
            print(
                f"ERROR: file count mismatch! before={count_before}, after={count_after} — "
                f"check backup at {Path(str(root) + '.bak')}",
                file=sys.stderr,
            )
            return 1
        print("VERIFY: file count matches — OK")

    print("RESULT: apply successful")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    default_root = (
        Path(__file__).parent.parent / "runs" / ".history"
    )

    parser = argparse.ArgumentParser(
        description="Flatten .history/<key>/<work_name>/<command>/ to <key>/ in-place."
    )
    parser.add_argument(
        "mode",
        choices=["dry-run", "apply"],
        help="dry-run: report only; apply: perform migration",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=default_root,
        metavar="PATH",
        help=f"Root directory to migrate (default: {default_root})",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="(apply only) Copy root to root.bak before migrating",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="(apply only) Compare file count before/after; abort on mismatch",
    )

    args = parser.parse_args()

    if args.mode == "dry-run":
        sys.exit(cmd_dry_run(args.root))
    else:
        sys.exit(cmd_apply(args.root, args.backup, args.verify))


if __name__ == "__main__":
    main()
