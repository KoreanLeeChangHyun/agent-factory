"""Redundant memory clustering + simple dedup.

Separate from reflection composition: here we only handle “When the same information is written twice”.
To avoid the risk of information loss, move only the older page to archive/merged/ and keep the new page.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .core import MemoryFile
from .paths import GCConfig

OVERLAP_THRESHOLD: float = 0.6  # If tokens overlap by more than 60%, they are duplicate candidates.
TOKEN_RE = re.compile(r'[\wga-hee]+')


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text or '') if len(t) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


@dataclass(frozen=True)
class DedupCandidate:
    keep: MemoryFile
    drop: MemoryFile
    overlap: float


def find_duplicates(memories: list[MemoryFile]) -> list[DedupCandidate]:
    """Extract the description token jaccard >= threshold pair within the same type."""
    by_type: dict[str, list[MemoryFile]] = {}
    for m in memories:
        by_type.setdefault(m.type, []).append(m)
    cands: list[DedupCandidate] = []
    for items in by_type.values():
        n = len(items)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = items[i], items[j]
                if a.path == b.path:
                    continue
                ta = _tokens(a.description) | _tokens(a.name)
                tb = _tokens(b.description) | _tokens(b.name)
                ov = _jaccard(ta, tb)
                if ov >= OVERLAP_THRESHOLD:
                    keep, drop = (a, b) if a.path.stat().st_mtime >= b.path.stat().st_mtime else (b, a)
                    cands.append(DedupCandidate(keep=keep, drop=drop, overlap=ov))
    return cands


def apply_dedup(cfg: GCConfig, candidates: list[DedupCandidate]) -> list[Path]:
    """Move the drop side of duplicate candidates to archive/merged/. reversible.

    Returns: List of moved archive paths.
    """
    moved: list[Path] = []
    target_dir = cfg.archive_subdir('merged')
    target_dir.mkdir(parents=True, exist_ok=True)
    seen_paths: set[Path] = set()
    for c in candidates:
        src = c.drop.path
        if src in seen_paths or not src.exists():
            continue
        dest = target_dir / src.name
        # timestamp suffix on collision
        if dest.exists():
            stem = src.stem
            suffix = src.suffix
            ts = src.stat().st_mtime
            dest = target_dir / f'{stem}.{int(ts)}{suffix}'
        shutil.move(str(src), str(dest))
        moved.append(dest)
        seen_paths.add(src)
    return moved
