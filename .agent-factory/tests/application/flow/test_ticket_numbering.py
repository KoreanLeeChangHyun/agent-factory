"""test ticket numbering.py - get max ticket number The default function module test (T-417).

Payment Terms:
  1. test default includes debug range: default(exclude debug range=False) → debug max return
  2. test exclude debug range returns normal max: exclude=True → Normal area max return
  3. FAQs test exclude debug range with only debug tickets
  4. test exclude debug range boundary: T-899/T-900/T-999/T-1000 verification
  5. test exclude debug range empty dir: no ticket → 0 return (the same option)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# sys.path: .agent-factory/engine contains → flow package importable
_ENGINE_DIR = str(Path(__file__).resolve().parents[3] / "engine")
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

import flow.ticket_repository as ticket_repo  # noqa: E402


# ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


def _create_ticket_files(directory: Path, ticket_numbers: list[int]) -> None:
    """Create a T-NNN.xml stack file in a temporary directory."""
    directory.mkdir(parents=True, exist_ok=True)
    for num in ticket_numbers:
        (directory / f"T-{num:03d}.xml").touch()


def _patch_kanban_dirs(monkeypatch, tmp_path: Path) -> dict[str, Path]:
    """Replace the kanban directory in the ticket repository module as a temporary directory.

    6 constant(KANBAN TODO DIR, KANBAN OPEN DIR, KANBAN PROGRESS DIR,
    KANBAN REVIEW DIR, KANBAN DONE DIR, KANBAN DIR) tmp path sub
    redirect to each subdirector.

    Returns:
        High Name → Temporary Path Dixie
    """
    dirs: dict[str, Path] = {
        "KANBAN_TODO_DIR": tmp_path / "todo",
        "KANBAN_OPEN_DIR": tmp_path / "open",
        "KANBAN_PROGRESS_DIR": tmp_path / "progress",
        "KANBAN_REVIEW_DIR": tmp_path / "review",
        "KANBAN_DONE_DIR": tmp_path / "done",
        "KANBAN_DIR": tmp_path / "root",
    }
    for attr, path in dirs.items():
        path.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(ticket_repo, attr, str(path))
    return dirs


# ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


def test_default_includes_debug_range(monkeypatch, tmp_path):
    """returns including the default(exclude debug range=False).

    General T-417 + Debug T-905 existence → 905 returns (excellent compatibility verification).
    """
    dirs = _patch_kanban_dirs(monkeypatch, tmp_path)
    _create_ticket_files(dirs["KANBAN_OPEN_DIR"], [417])
    _create_ticket_files(dirs["KANBAN_DONE_DIR"], [905])

    result = ticket_repo.get_max_ticket_number(exclude_debug_range=False)
    assert result == 905, (
        f"exclude debug range=False 905, including Debug Zone(T-905), but   FIELD 0   return"
    )


def test_exclude_debug_range_returns_normal_max(monkeypatch, tmp_path):
    """exclude debug range=True returns normal max except debug area.

    General T-417 + Debug T-905 existence → 417 return.
    """
    dirs = _patch_kanban_dirs(monkeypatch, tmp_path)
    _create_ticket_files(dirs["KANBAN_OPEN_DIR"], [417])
    _create_ticket_files(dirs["KANBAN_DONE_DIR"], [905])

    result = ticket_repo.get_max_ticket_number(exclude_debug_range=True)
    assert result == 417, (
        f"exclude debug range=True I expected the general area max(417) but   FIELD 0   return"
    )


def test_exclude_debug_range_with_only_debug_tickets(monkeypatch, tmp_path):
    """exclude=True → 0 returns only when the debug ticket (T-901, T-905) is present."""
    dirs = _patch_kanban_dirs(monkeypatch, tmp_path)
    _create_ticket_files(dirs["KANBAN_DONE_DIR"], [901, 905])

    result = ticket_repo.get_max_ticket_number(exclude_debug_range=True)
    assert result == 0, (
        f"Debug tickets only exist + exclude=True, but   FIELD 0   return"
    )


def test_exclude_debug_range_boundary(monkeypatch, tmp_path):
    """Verification of boundary value: T-899 (included), T-900/T-999 (excluded), T-1000 (included).

    exclude=True City:
    - T-899, T-900, T-999, T-1000
    - T-899, T-900, T-999 only exists → max=899
    """
    dirs = _patch_kanban_dirs(monkeypatch, tmp_path)

    # Case A: T-899 + T-900 + T-999 + T-1000 → 1000 Return
    _create_ticket_files(dirs["KANBAN_OPEN_DIR"], [899, 1000])
    _create_ticket_files(dirs["KANBAN_DONE_DIR"], [900, 999])

    result_a = ticket_repo.get_max_ticket_number(exclude_debug_range=True)
    assert result_a == 1000, (
        f"Boundary Value Case A: We expect 1000 to include T-1000 but   FIELD 0   Return"
    )

    # Case B: T-899 + T-900 + T-999
    for f in dirs["KANBAN_OPEN_DIR"].iterdir():
        f.unlink()
    for f in dirs["KANBAN_DONE_DIR"].iterdir():
        f.unlink()

    _create_ticket_files(dirs["KANBAN_OPEN_DIR"], [899])
    _create_ticket_files(dirs["KANBAN_DONE_DIR"], [900, 999])

    result_b = ticket_repo.get_max_ticket_number(exclude_debug_range=True)
    assert result_b == 899, (
        f"Perimeter Case B: T-900~T-999 excluding 899 but   FIELD 0   Return"
    )


def test_exclude_debug_range_empty_dir(monkeypatch, tmp_path):
    """When there is no ticket, both options return 0."""
    _patch_kanban_dirs(monkeypatch, tmp_path)

    result_default = ticket_repo.get_max_ticket_number(exclude_debug_range=False)
    result_exclude = ticket_repo.get_max_ticket_number(exclude_debug_range=True)

    assert result_default == 0, (
        f"No ticket + exclude=False 0, but   FIELD 0   Return"
    )
    assert result_exclude == 0, (
        f"No ticket + exclude=True 0, but   FIELD 0   Return"
    )
