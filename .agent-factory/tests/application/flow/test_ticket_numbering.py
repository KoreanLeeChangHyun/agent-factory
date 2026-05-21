"""test work request numbering.py - get max work_request number The default function module test (WR-417).

Payment Terms:
  1. test default includes debug range: default(exclude debug range=False) → debug max return
  2. test exclude debug range returns normal max: exclude=True → Normal area max return
  3. FAQs test exclude debug range with only debug work_requests
  4. test exclude debug range boundary: WR-899/WR-900/WR-999/WR-1000 verification
  5. test exclude debug range empty dir: no work_request → 0 return (the same option)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# sys.path: .agent-factory/engine contains → flow package importable
_ENGINE_DIR = str(Path(__file__).resolve().parents[3] / "engine")
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

import flow.work_request_repository as work_request_repo  # noqa: E402


# ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


def _create_work_request_files(directory: Path, work_request_numbers: list[int]) -> None:
    """Create a WR-NNN.xml stack file in a temporary directory."""
    directory.mkdir(parents=True, exist_ok=True)
    for num in work_request_numbers:
        (directory / f"WR-{num:03d}.xml").touch()


def _patch_conveyor_dirs(monkeypatch, tmp_path: Path) -> dict[str, Path]:
    """Replace the conveyor directory in the work_request repository module as a temporary directory.

    6 constant(CONVEYOR DRAFT DIR, CONVEYOR ACCEPTED DIR, CONVEYOR EXECUTING DIR,
    CONVEYOR VERIFYING DIR, CONVEYOR COMPLETE DIR, CONVEYOR DIR) tmp path sub
    redirect to each subdirector.

    Returns:
        High Name → Temporary Path Dixie
    """
    dirs: dict[str, Path] = {
        "CONVEYOR_DRAFT_DIR": tmp_path / "draft",
        "CONVEYOR_ACCEPTED_DIR": tmp_path / "accepted",
        "CONVEYOR_EXECUTING_DIR": tmp_path / "executing",
        "CONVEYOR_VERIFYING_DIR": tmp_path / "verifying",
        "CONVEYOR_COMPLETE_DIR": tmp_path / "complete",
        "CONVEYOR_DIR": tmp_path / "root",
    }
    for attr, path in dirs.items():
        path.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(work_request_repo, attr, str(path))
    return dirs


# ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


def test_default_includes_debug_range(monkeypatch, tmp_path):
    """returns including the default(exclude debug range=False).

    General WR-417 + Debug WR-905 existence → 905 returns (excellent compatibility verification).
    """
    dirs = _patch_conveyor_dirs(monkeypatch, tmp_path)
    _create_work_request_files(dirs["CONVEYOR_ACCEPTED_DIR"], [417])
    _create_work_request_files(dirs["CONVEYOR_COMPLETE_DIR"], [905])

    result = work_request_repo.get_max_work_request_number(exclude_debug_range=False)
    assert result == 905, (
        f"exclude debug range=False 905, including Debug Zone(WR-905), but   FIELD 0   return"
    )


def test_exclude_debug_range_returns_normal_max(monkeypatch, tmp_path):
    """exclude debug range=True returns normal max except debug area.

    General WR-417 + Debug WR-905 existence → 417 return.
    """
    dirs = _patch_conveyor_dirs(monkeypatch, tmp_path)
    _create_work_request_files(dirs["CONVEYOR_ACCEPTED_DIR"], [417])
    _create_work_request_files(dirs["CONVEYOR_COMPLETE_DIR"], [905])

    result = work_request_repo.get_max_work_request_number(exclude_debug_range=True)
    assert result == 417, (
        f"exclude debug range=True I expected the general area max(417) but   FIELD 0   return"
    )


def test_exclude_debug_range_with_only_debug_work_requests(monkeypatch, tmp_path):
    """exclude=True → 0 returns only when the debug work_request (WR-901, WR-905) is present."""
    dirs = _patch_conveyor_dirs(monkeypatch, tmp_path)
    _create_work_request_files(dirs["CONVEYOR_COMPLETE_DIR"], [901, 905])

    result = work_request_repo.get_max_work_request_number(exclude_debug_range=True)
    assert result == 0, (
        f"Debug work_requests only exist + exclude=True, but   FIELD 0   return"
    )


def test_exclude_debug_range_boundary(monkeypatch, tmp_path):
    """Verification of boundary value: WR-899 (included), WR-900/WR-999 (excluded), WR-1000 (included).

    exclude=True City:
    - WR-899, WR-900, WR-999, WR-1000
    - WR-899, WR-900, WR-999 only exists → max=899
    """
    dirs = _patch_conveyor_dirs(monkeypatch, tmp_path)

    # Case A: WR-899 + WR-900 + WR-999 + WR-1000 → 1000 Return
    _create_work_request_files(dirs["CONVEYOR_ACCEPTED_DIR"], [899, 1000])
    _create_work_request_files(dirs["CONVEYOR_COMPLETE_DIR"], [900, 999])

    result_a = work_request_repo.get_max_work_request_number(exclude_debug_range=True)
    assert result_a == 1000, (
        f"Boundary Value Case A: We expect 1000 to include WR-1000 but   FIELD 0   Return"
    )

    # Case B: WR-899 + WR-900 + WR-999
    for f in dirs["CONVEYOR_ACCEPTED_DIR"].iterdir():
        f.unlink()
    for f in dirs["CONVEYOR_COMPLETE_DIR"].iterdir():
        f.unlink()

    _create_work_request_files(dirs["CONVEYOR_ACCEPTED_DIR"], [899])
    _create_work_request_files(dirs["CONVEYOR_COMPLETE_DIR"], [900, 999])

    result_b = work_request_repo.get_max_work_request_number(exclude_debug_range=True)
    assert result_b == 899, (
        f"Perimeter Case B: WR-900~WR-999 excluding 899 but   FIELD 0   Return"
    )


def test_exclude_debug_range_empty_dir(monkeypatch, tmp_path):
    """When there is no work_request, both options return 0."""
    _patch_conveyor_dirs(monkeypatch, tmp_path)

    result_default = work_request_repo.get_max_work_request_number(exclude_debug_range=False)
    result_exclude = work_request_repo.get_max_work_request_number(exclude_debug_range=True)

    assert result_default == 0, (
        f"No work_request + exclude=False 0, but   FIELD 0   Return"
    )
    assert result_exclude == 0, (
        f"No work_request + exclude=True 0, but   FIELD 0   Return"
    )
