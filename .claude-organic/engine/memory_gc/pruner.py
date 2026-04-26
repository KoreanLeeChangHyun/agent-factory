"""Archive 영구 prune — TTL(archive_ttl_days) 초과 파일 영구 삭제.

사용자 명시 호출만. 자동 트리거 X.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from .paths import GCConfig, ARCHIVE_SUBDIRS


@dataclass
class PruneResult:
    candidates: list[Path]
    deleted: list[Path]

    def summary(self) -> str:
        return f'candidates={len(self.candidates)} deleted={len(self.deleted)}'


def _is_expired(path: Path, ttl_days: int) -> bool:
    age = (dt.datetime.now() - dt.datetime.fromtimestamp(path.stat().st_mtime)).days
    return age >= ttl_days


def find_prune_candidates(cfg: GCConfig) -> list[Path]:
    out: list[Path] = []
    for k in ARCHIVE_SUBDIRS:
        d = cfg.archive_subdir(k)
        if not d.is_dir():
            continue
        for p in sorted(d.glob('*.md')):
            if _is_expired(p, cfg.archive_ttl_days):
                out.append(p)
    return out


def prune_archive(cfg: GCConfig, *, apply: bool) -> PruneResult:
    cands = find_prune_candidates(cfg)
    if not apply:
        return PruneResult(candidates=cands, deleted=[])
    deleted: list[Path] = []
    for p in cands:
        try:
            p.unlink()
            deleted.append(p)
        except OSError:
            continue
    return PruneResult(candidates=cands, deleted=deleted)
