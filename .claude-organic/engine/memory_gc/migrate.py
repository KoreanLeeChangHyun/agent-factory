"""1회성 마이그레이션 — 평탄 디렉터리 → type 별 디렉터리 + frontmatter 확장.

멱등: 이미 type 디렉터리에 있는 파일은 건너뛴다. 재실행 안전.
"""
from __future__ import annotations

import datetime as dt
import shutil
from dataclasses import dataclass
from pathlib import Path

from .core import MemoryFile, parse_memory_file, write_memory_file, regenerate_index, scan_memories
from .paths import GCConfig, TYPE_DIRS, ensure_skeleton

DEFAULT_IMPORTANCE: int = 5


@dataclass
class MigrationReport:
    moved_files: list[tuple[Path, Path]]   # (src, dest)
    extended_frontmatter: list[Path]
    skipped_files: list[Path]
    cleaned_locks: list[Path]
    index_regenerated: bool

    def summary(self) -> str:
        return (
            f'moved={len(self.moved_files)} '
            f'frontmatter_extended={len(self.extended_frontmatter)} '
            f'skipped={len(self.skipped_files)} '
            f'locks_cleaned={len(self.cleaned_locks)} '
            f'index_regenerated={self.index_regenerated}'
        )


def _mtime_iso(path: Path) -> str:
    ts = path.stat().st_mtime
    return dt.date.fromtimestamp(ts).isoformat()


def _ensure_extended_frontmatter(mem: MemoryFile) -> bool:
    """importance·last_accessed·access_count 가 없으면 기본값으로 채우고 True 반환."""
    fm = mem.raw_frontmatter
    changed = False
    if 'importance' not in fm:
        mem.importance = DEFAULT_IMPORTANCE
        changed = True
    if 'last_accessed' not in fm:
        mem.last_accessed = _mtime_iso(mem.path)
        changed = True
    if 'access_count' not in fm:
        mem.access_count = 0
        changed = True
    return changed


def _move_to_type_dir(cfg: GCConfig, mem: MemoryFile) -> Path | None:
    """평탄 위치(=memory_dir 직접 자식) 인 파일을 type/ 디렉터리로 이동.

    이미 type 디렉터리에 있으면 None 반환 (스킵).
    """
    parent = mem.path.parent
    if parent.name in TYPE_DIRS:
        return None
    if mem.type not in TYPE_DIRS:
        # type 미상 → project 로 폴백
        mem.type = 'project'
    dest_dir = cfg.type_dir(mem.type)
    dest = dest_dir / mem.path.name
    if dest.exists() and dest.resolve() != mem.path.resolve():
        # 충돌 — timestamp suffix
        dest = dest_dir / f'{mem.path.stem}.dup{int(mem.path.stat().st_mtime)}{mem.path.suffix}'
    shutil.move(str(mem.path), str(dest))
    mem.path = dest
    return dest


def _clean_stale_locks(cfg: GCConfig) -> list[Path]:
    """오래된 락 파일 정리 (.consolidate-lock 등)."""
    cleaned: list[Path] = []
    for name in ('.consolidate-lock',):
        p = cfg.memory_dir / name
        if p.exists():
            try:
                p.unlink()
                cleaned.append(p)
            except OSError:
                pass
    return cleaned


def run_migration(cfg: GCConfig) -> MigrationReport:
    ensure_skeleton(cfg)
    moved: list[tuple[Path, Path]] = []
    extended: list[Path] = []
    skipped: list[Path] = []

    # 평탄 파일 우선 — type 디렉터리로 이동 + frontmatter 확장
    for path in sorted(cfg.memory_dir.glob('*.md')):
        if path.name == 'MEMORY.md':
            continue
        mem = parse_memory_file(path)
        if mem is None:
            skipped.append(path)
            continue
        original = mem.path
        moved_dest = _move_to_type_dir(cfg, mem)
        fm_changed = _ensure_extended_frontmatter(mem)
        if moved_dest is not None or fm_changed:
            write_memory_file(mem)
        if moved_dest is not None:
            moved.append((original, moved_dest))
        if fm_changed and moved_dest is None:
            extended.append(mem.path)

    # 이미 type 디렉터리에 있는 파일들도 frontmatter 점검
    for t in TYPE_DIRS:
        d = cfg.type_dir(t)
        if not d.is_dir():
            continue
        for path in sorted(d.glob('*.md')):
            mem = parse_memory_file(path)
            if mem is None:
                skipped.append(path)
                continue
            if _ensure_extended_frontmatter(mem):
                write_memory_file(mem)
                extended.append(path)

    cleaned = _clean_stale_locks(cfg)

    # 인덱스 재생성
    memories = scan_memories(cfg)
    regenerate_index(cfg, memories)

    return MigrationReport(
        moved_files=moved,
        extended_frontmatter=extended,
        skipped_files=skipped,
        cleaned_locks=cleaned,
        index_regenerated=True,
    )
