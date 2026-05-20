"""중복 메모리 클러스터링 + 단순 dedup.

reflection 합성과 분리: 여기서는 "같은 정보를 두 번 적은 경우" 만 처리.
정보 손실 위험을 피해 더 오래된 쪽만 archive/merged/ 로 이동, 새 쪽 유지.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .core import MemoryFile
from .paths import GCConfig

OVERLAP_THRESHOLD: float = 0.6  # 토큰 60% 이상 겹치면 중복 후보
TOKEN_RE = re.compile(r'[\w가-힣]+')


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
    """같은 type 안에서 description 토큰 jaccard >= threshold 페어를 추출."""
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
    """중복 후보의 drop 측을 archive/merged/ 로 이동. reversible.

    Returns: 이동된 archive 경로 리스트.
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
        # 충돌 시 timestamp suffix
        if dest.exists():
            stem = src.stem
            suffix = src.suffix
            ts = src.stat().st_mtime
            dest = target_dir / f'{stem}.{int(ts)}{suffix}'
        shutil.move(str(src), str(dest))
        moved.append(dest)
        seen_paths.add(src)
    return moved
