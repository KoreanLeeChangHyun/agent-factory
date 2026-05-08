#!/usr/bin/env python3
"""T-449: .history/<key>/<work_name>/<command>/ 폴드 구조를 <key>/ 직속으로 평탄화하는 마이그레이션 스크립트.

Usage:
    migrate_runs_fold.py [--mode {dry-run,apply}] [--root PATH]
                         [--backup] [--verify] [--limit N]

Modes:
    dry-run  (default) 변경 계획을 stdout 에 출력하고 파일을 수정하지 않는다.
    apply    실제 파일 이동을 수행한다. --backup 권장.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# --- 로거 설정 ----------------------------------------------------------------
_logger = logging.getLogger(__name__)
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
_logger.addHandler(_handler)
_logger.setLevel(logging.INFO)


# --- 데이터 클래스 -------------------------------------------------------------

@dataclass
class FoldEntry:
    """단일 폴드 패턴 엔트리 (key/<work_name>/<command>/ → key/)."""

    key: str
    work_name: str
    command: str
    src_dir: Path
    dst_dir: Path
    files: list[Path] = field(default_factory=list)


@dataclass
class MigrationPlan:
    """전체 마이그레이션 계획 요약."""

    total_keys: int = 0
    fold_entries: list[FoldEntry] = field(default_factory=list)
    conflict_keys: list[str] = field(default_factory=list)
    already_flat_keys: list[str] = field(default_factory=list)

    @property
    def fold_count(self) -> int:
        """폴드 패턴 디렉터리 수."""
        return len(self.fold_entries)

    @property
    def conflict_count(self) -> int:
        return len(self.conflict_keys)

    @property
    def workflow_log_count(self) -> int:
        """폴드 엔트리 중 workflow.log 포함 건수."""
        return sum(
            1 for e in self.fold_entries
            if any(f.name == "workflow.log" for f in e.files)
        )


# --- 핵심 로직 -----------------------------------------------------------------

_FOLD_MARKER_FILES = frozenset({".context.json", "init-result.json", "workflow.log"})


def _is_fold_dir(path: Path) -> bool:
    """디렉터리가 폴드 마커 파일을 하나 이상 포함하는지 확인한다.

    Args:
        path: depth=3 디렉터리 경로 (key/work_name/command/).

    Returns:
        마커 파일이 하나 이상 존재하면 True.
    """
    return any((path / marker).exists() for marker in _FOLD_MARKER_FILES)


def _collect_all_files(src_dir: Path) -> list[Path]:
    """src_dir 아래의 모든 파일(재귀)을 수집한다.

    Args:
        src_dir: 이동 대상 소스 디렉터리.

    Returns:
        모든 파일 경로 목록 (절대 경로).
    """
    return list(src_dir.rglob("*") if src_dir.exists() else [])


def build_plan(runs_root: Path, limit: Optional[int] = None) -> MigrationPlan:
    """runs_root 아래의 모든 key/ 를 순회하여 마이그레이션 계획을 수립한다.

    알고리즘:
        1. key/ 직속 하위 항목을 검사한다.
        2. 하위 항목이 디렉터리이고, 그 아래에 command 디렉터리가 존재하면
           폴드 패턴 후보로 판단한다.
        3. 단일 work_name + 단일 command 인 경우: FoldEntry 로 추가.
        4. 다중 work_name 또는 다중 command 인 경우: conflict 로 표시하고 스킵.
        5. key/ 직속에 이미 마커 파일이 있으면 already_flat 으로 처리한다.

    Args:
        runs_root: .history/ 루트 디렉터리 경로.
        limit: 처리할 최대 key 수 (테스트용).

    Returns:
        MigrationPlan 객체.
    """
    plan = MigrationPlan()

    if not runs_root.is_dir():
        _logger.error("runs_root 가 존재하지 않습니다: %s", runs_root)
        return plan

    keys = sorted(p for p in runs_root.iterdir() if p.is_dir())
    if limit is not None:
        keys = keys[:limit]

    plan.total_keys = len(keys)

    for key_dir in keys:
        key = key_dir.name

        # key/ 직속에 이미 마커 파일이 있으면 이미 평탄화된 구조
        has_direct_markers = any(
            (key_dir / m).exists() for m in _FOLD_MARKER_FILES
        )
        if has_direct_markers:
            plan.already_flat_keys.append(key)
            continue

        # key/ 하위 디렉터리를 work_name 후보로 수집
        subdirs = [p for p in key_dir.iterdir() if p.is_dir()]
        if not subdirs:
            # 하위 디렉터리가 없거나 파일만 있는 경우 → 스킵
            continue

        # 각 work_name_dir 아래의 command 디렉터리 수집
        fold_dirs: list[tuple[str, str, Path]] = []  # (work_name, command, path)
        has_conflict = False

        for work_name_dir in subdirs:
            cmd_dirs = [p for p in work_name_dir.iterdir() if p.is_dir()]
            for cmd_dir in cmd_dirs:
                if _is_fold_dir(cmd_dir):
                    fold_dirs.append((work_name_dir.name, cmd_dir.name, cmd_dir))

        if not fold_dirs:
            continue

        # 다중 work_name 또는 다중 command → conflict
        unique_work_names = {wn for wn, _, _ in fold_dirs}
        unique_commands = {cmd for _, cmd, _ in fold_dirs}

        if len(unique_work_names) > 1 or len(unique_commands) > 1:
            _logger.warning(
                "CONFLICT key=%s work_names=%s commands=%s",
                key, sorted(unique_work_names), sorted(unique_commands),
            )
            plan.conflict_keys.append(key)
            has_conflict = True

        if has_conflict:
            continue

        # 단일 폴드 패턴 처리
        for work_name, command, src_dir in fold_dirs:
            files = [f for f in src_dir.rglob("*") if f.is_file()]
            entry = FoldEntry(
                key=key,
                work_name=work_name,
                command=command,
                src_dir=src_dir,
                dst_dir=key_dir,
                files=files,
            )
            plan.fold_entries.append(entry)

    return plan


def _check_dst_conflicts(entry: FoldEntry) -> list[str]:
    """dst_dir 에 이미 동명 파일이 있는지 확인한다.

    Args:
        entry: 마이그레이션 엔트리.

    Returns:
        충돌 파일 상대 경로 목록.
    """
    conflicts: list[str] = []
    for src_file in entry.files:
        rel = src_file.relative_to(entry.src_dir)
        dst_file = entry.dst_dir / rel
        if dst_file.exists():
            conflicts.append(str(rel))
    return conflicts


# --- dry-run 출력 --------------------------------------------------------------

def run_dry(plan: MigrationPlan) -> None:
    """dry-run 모드: 변경 계획을 stdout 에 출력하고 파일을 수정하지 않는다.

    Args:
        plan: build_plan() 으로 생성한 마이그레이션 계획.
    """
    # 샘플 5건 출력
    samples = plan.fold_entries[:5]
    if samples:
        print("[DRY-RUN] sample entries:")
        for e in samples:
            print(f"  {e.key}/{e.work_name}/{e.command}/ -> {e.key}/  ({len(e.files)} files)")

    if plan.conflict_keys:
        print(f"[DRY-RUN] conflict keys ({len(plan.conflict_keys)}):")
        for k in plan.conflict_keys:
            print(f"  {k}")

    if plan.already_flat_keys:
        print(f"[DRY-RUN] already-flat keys: {len(plan.already_flat_keys)}")

    # 파일 충돌 예비 검사
    file_conflicts = 0
    for entry in plan.fold_entries:
        conflicts = _check_dst_conflicts(entry)
        if conflicts:
            file_conflicts += len(conflicts)
            _logger.warning("file conflict in key=%s: %s", entry.key, conflicts[:3])

    print(
        f"[DRY-RUN] total: {plan.total_keys} keys, "
        f"{plan.fold_count} fold-pattern dirs, "
        f"{plan.conflict_count} conflicts, "
        f"{plan.workflow_log_count} workflow.log files"
    )
    if file_conflicts:
        print(f"[DRY-RUN] WARNING: {file_conflicts} file-level conflicts detected (would abort apply)")


# --- apply -------------------------------------------------------------------

def _count_files(directory: Path) -> int:
    """directory 아래 모든 파일 수를 반환한다.

    Args:
        directory: 검사할 디렉터리 경로.

    Returns:
        파일 수 (재귀).
    """
    if not directory.is_dir():
        return 0
    return sum(1 for f in directory.rglob("*") if f.is_file())


def _do_backup(runs_root: Path) -> None:
    """runs_root 를 runs_root.parent/.history.bak/ 로 복제한다 (1회만).

    Args:
        runs_root: 원본 .history/ 경로.
    """
    bak_dir = runs_root.parent / ".history.bak"
    if bak_dir.exists():
        _logger.info("백업 디렉터리가 이미 존재합니다 — 스킵: %s", bak_dir)
        return
    _logger.info("백업 생성 중: %s → %s", runs_root, bak_dir)
    shutil.copytree(str(runs_root), str(bak_dir), symlinks=True)
    _logger.info("백업 완료")


def run_apply(plan: MigrationPlan, runs_root: Path, backup: bool, verify: bool) -> int:
    """apply 모드: 파일을 실제로 이동한다.

    Args:
        plan: build_plan() 으로 생성한 마이그레이션 계획.
        runs_root: .history/ 루트 경로 (백업 기준).
        backup: True 이면 이동 전 .history.bak/ 복제.
        verify: True 이면 이동 전후 파일 수를 비교하여 불일치 시 abort.

    Returns:
        처리된 FoldEntry 수. 오류 시 sys.exit(1) 호출.
    """
    if backup:
        _do_backup(runs_root)

    # 파일 수 기준점
    pre_count = _count_files(runs_root) if verify else 0

    # 파일 충돌 전체 사전 검사 — 하나라도 있으면 abort
    _logger.info("파일 충돌 사전 검사 중 (%d entries)...", plan.fold_count)
    for entry in plan.fold_entries:
        conflicts = _check_dst_conflicts(entry)
        if conflicts:
            _logger.error(
                "ABORT: key=%s 에서 파일 충돌 감지: %s\n"
                "  백업 위치: %s\n"
                "  수동 해결 후 재실행하세요.",
                entry.key, conflicts, runs_root.parent / ".history.bak",
            )
            sys.exit(1)

    _logger.info("충돌 없음 — 마이그레이션 시작")

    processed = 0
    for entry in plan.fold_entries:
        _logger.info(
            "[%d/%d] %s/%s/%s/ 이동 중...",
            processed + 1, plan.fold_count,
            entry.key, entry.work_name, entry.command,
        )
        # 파일 이동: src_dir 내 모든 파일을 dst_dir 에 상대 경로 유지하며 이동
        for src_file in entry.files:
            rel = src_file.relative_to(entry.src_dir)
            dst_file = entry.dst_dir / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_file), str(dst_file))

        # 빈 디렉터리 정리 (src_dir → work_name_dir → 필요시)
        try:
            if not any(entry.src_dir.rglob("*")):
                entry.src_dir.rmdir()
            work_name_dir = entry.src_dir.parent
            if work_name_dir.is_dir() and not any(work_name_dir.iterdir()):
                work_name_dir.rmdir()
        except OSError as exc:
            _logger.warning("빈 디렉터리 정리 실패 (무시): %s", exc)

        processed += 1

    # 파일 수 검증
    if verify:
        post_count = _count_files(runs_root)
        if pre_count != post_count:
            _logger.error(
                "VERIFY FAIL: 전 %d 파일 → 후 %d 파일 (차이 %+d)\n"
                "  백업에서 복구하세요: %s",
                pre_count, post_count, post_count - pre_count,
                runs_root.parent / ".history.bak",
            )
            sys.exit(1)
        _logger.info("VERIFY PASS: 전후 파일 수 %d 동일", pre_count)

    print(
        f"[APPLY] done: {processed} fold dirs migrated, "
        f"{plan.total_keys} keys, "
        f"{plan.conflict_count} conflicts skipped"
    )
    return processed


# --- CLI ---------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """argparse ArgumentParser 를 구성하여 반환한다.

    Returns:
        설정된 ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        description=(
            ".history/<key>/<work_name>/<command>/ 폴드 구조를 "
            "<key>/ 직속으로 평탄화하는 마이그레이션 스크립트"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["dry-run", "apply"],
        default="dry-run",
        help="실행 모드 (기본: dry-run)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="runs_root 경로 (기본: <script_dir>/../runs/.history)",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="apply 실행 전 .history.bak/ 복제 (기본: 비활성)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="마이그레이션 전후 파일 수 비교 검증",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="처리할 최대 key 수 (테스트용)",
    )
    return parser


def _resolve_root(args_root: Optional[Path]) -> Path:
    """runs_root 경로를 결정한다.

    Args:
        args_root: CLI 에서 전달된 --root 값 (None 이면 기본값 사용).

    Returns:
        최종 runs_root 경로.
    """
    if args_root is not None:
        return args_root.resolve()
    # 스크립트 위치: .claude-organic/scripts/
    script_dir = Path(__file__).resolve().parent
    return (script_dir / ".." / "runs" / ".history").resolve()


def main() -> None:
    """CLI 진입점."""
    parser = _build_parser()
    args = parser.parse_args()

    runs_root = _resolve_root(args.root)
    _logger.info("runs_root: %s", runs_root)

    plan = build_plan(runs_root, limit=args.limit)
    _logger.info(
        "계획 수립 완료: %d keys, %d fold dirs, %d conflicts, %d already-flat",
        plan.total_keys, plan.fold_count, plan.conflict_count,
        len(plan.already_flat_keys),
    )

    if args.mode == "dry-run":
        run_dry(plan)
    else:
        if not runs_root.is_dir():
            _logger.error("runs_root 가 존재하지 않습니다: %s", runs_root)
            sys.exit(1)
        run_apply(plan, runs_root, backup=args.backup, verify=args.verify)


if __name__ == "__main__":
    main()
