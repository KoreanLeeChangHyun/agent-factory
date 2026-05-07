"""test_ticket_numbering.py - get_max_ticket_number 디버그 영역 제외 기능 단위 테스트 (T-417).

검증 항목:
  1. test_default_includes_debug_range: 기본값(exclude_debug_range=False) → 디버그 max 반환
  2. test_exclude_debug_range_returns_normal_max: exclude=True → 일반 영역 max 반환
  3. test_exclude_debug_range_with_only_debug_tickets: 디버그 티켓만 존재 → 0 반환
  4. test_exclude_debug_range_boundary: 경계값 T-899/T-900/T-999/T-1000 검증
  5. test_exclude_debug_range_empty_dir: 티켓 없음 → 0 반환 (양쪽 옵션 동일)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# sys.path: .claude-organic/engine 포함 → flow 패키지 import 가능
_ENGINE_DIR = str(Path(__file__).resolve().parent.parent.parent)
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

import flow.ticket_repository as ticket_repo  # noqa: E402


# ─── 헬퍼 ─────────────────────────────────────────────────────────────────────


def _create_ticket_files(directory: Path, ticket_numbers: list[int]) -> None:
    """임시 디렉터리에 T-NNN.xml 더미 파일을 생성한다."""
    directory.mkdir(parents=True, exist_ok=True)
    for num in ticket_numbers:
        (directory / f"T-{num:03d}.xml").touch()


def _patch_kanban_dirs(monkeypatch, tmp_path: Path) -> dict[str, Path]:
    """ticket_repository 모듈의 칸반 디렉터리 상수를 임시 디렉터리로 교체한다.

    6개 상수(KANBAN_TODO_DIR, KANBAN_OPEN_DIR, KANBAN_PROGRESS_DIR,
    KANBAN_REVIEW_DIR, KANBAN_DONE_DIR, KANBAN_DIR)를 tmp_path 하위
    각 서브디렉터리로 redirect 한다.

    Returns:
        상수명 → 임시 Path 딕셔너리.
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


# ─── 테스트 케이스 ─────────────────────────────────────────────────────────────


def test_default_includes_debug_range(monkeypatch, tmp_path):
    """기본값(exclude_debug_range=False) 시 디버그 영역 max를 포함하여 반환한다.

    일반 T-417 + 디버그 T-905 존재 → 905 반환 (기존 호환성 보장 검증).
    """
    dirs = _patch_kanban_dirs(monkeypatch, tmp_path)
    _create_ticket_files(dirs["KANBAN_OPEN_DIR"], [417])
    _create_ticket_files(dirs["KANBAN_DONE_DIR"], [905])

    result = ticket_repo.get_max_ticket_number(exclude_debug_range=False)
    assert result == 905, (
        f"exclude_debug_range=False 시 디버그 영역(T-905)을 포함한 905를 기대했으나 {result} 반환"
    )


def test_exclude_debug_range_returns_normal_max(monkeypatch, tmp_path):
    """exclude_debug_range=True 시 디버그 영역을 제외한 일반 max를 반환한다.

    일반 T-417 + 디버그 T-905 존재 → 417 반환.
    """
    dirs = _patch_kanban_dirs(monkeypatch, tmp_path)
    _create_ticket_files(dirs["KANBAN_OPEN_DIR"], [417])
    _create_ticket_files(dirs["KANBAN_DONE_DIR"], [905])

    result = ticket_repo.get_max_ticket_number(exclude_debug_range=True)
    assert result == 417, (
        f"exclude_debug_range=True 시 일반 영역 max(417)를 기대했으나 {result} 반환"
    )


def test_exclude_debug_range_with_only_debug_tickets(monkeypatch, tmp_path):
    """디버그 티켓(T-901, T-905)만 존재 시 exclude=True → 0 반환한다."""
    dirs = _patch_kanban_dirs(monkeypatch, tmp_path)
    _create_ticket_files(dirs["KANBAN_DONE_DIR"], [901, 905])

    result = ticket_repo.get_max_ticket_number(exclude_debug_range=True)
    assert result == 0, (
        f"디버그 티켓만 존재 + exclude=True 시 0을 기대했으나 {result} 반환"
    )


def test_exclude_debug_range_boundary(monkeypatch, tmp_path):
    """경계값 검증: T-899(포함), T-900/T-999(제외), T-1000(포함).

    exclude=True 시:
    - T-899, T-900, T-999, T-1000 혼재 → max=1000
    - T-899, T-900, T-999 만 존재 → max=899
    """
    dirs = _patch_kanban_dirs(monkeypatch, tmp_path)

    # Case A: T-899 + T-900 + T-999 + T-1000 → 1000 반환
    _create_ticket_files(dirs["KANBAN_OPEN_DIR"], [899, 1000])
    _create_ticket_files(dirs["KANBAN_DONE_DIR"], [900, 999])

    result_a = ticket_repo.get_max_ticket_number(exclude_debug_range=True)
    assert result_a == 1000, (
        f"경계값 Case A: T-1000 포함 시 1000을 기대했으나 {result_a} 반환"
    )

    # 파일 초기화 후 Case B: T-899 + T-900 + T-999 만 → 899 반환
    for f in dirs["KANBAN_OPEN_DIR"].iterdir():
        f.unlink()
    for f in dirs["KANBAN_DONE_DIR"].iterdir():
        f.unlink()

    _create_ticket_files(dirs["KANBAN_OPEN_DIR"], [899])
    _create_ticket_files(dirs["KANBAN_DONE_DIR"], [900, 999])

    result_b = ticket_repo.get_max_ticket_number(exclude_debug_range=True)
    assert result_b == 899, (
        f"경계값 Case B: T-900~T-999 제외 시 899를 기대했으나 {result_b} 반환"
    )


def test_exclude_debug_range_empty_dir(monkeypatch, tmp_path):
    """티켓이 없을 때 양쪽 옵션 모두 0을 반환한다."""
    _patch_kanban_dirs(monkeypatch, tmp_path)

    result_default = ticket_repo.get_max_ticket_number(exclude_debug_range=False)
    result_exclude = ticket_repo.get_max_ticket_number(exclude_debug_range=True)

    assert result_default == 0, (
        f"티켓 없음 + exclude=False 시 0을 기대했으나 {result_default} 반환"
    )
    assert result_exclude == 0, (
        f"티켓 없음 + exclude=True 시 0을 기대했으나 {result_exclude} 반환"
    )
