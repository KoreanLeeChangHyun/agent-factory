"""3-axis score calculation + Hot/Warm/Cold tier determination.

Hot = index top hot_limit (automatically exposed to user context)
Warm = resides in other type directories
Cold = archive resident (excluding index)

It does not change the file location — Hot is just a sorting/notation criterion.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

from .core import MemoryFile

DECAY_RATE: float = 0.005  # Unit of days, half-life of approximately 138 days (138 ≈ ln(2)/0.005)


def _days_since(date_str: str) -> float:
    if not date_str:
        return 365.0
    try:
        d = dt.date.fromisoformat(date_str.strip())
    except ValueError:
        return 365.0
    return max((dt.date.today() - d).days, 0)


def recency_score(date_str: str) -> float:
    return math.exp(-DECAY_RATE * _days_since(date_str))


def importance_score(importance: int) -> float:
    return max(0, min(importance, 10)) / 10.0


def access_score(access_count: int, max_access: int) -> float:
    if max_access <= 0:
        return 0.0
    return math.log1p(max(access_count, 0)) / math.log1p(max_access)


@dataclass(frozen=True)
class ScoredMemory:
    memory: MemoryFile
    score: float
    importance: float
    recency: float
    access: float


def score_memories(memories: list[MemoryFile]) -> list[ScoredMemory]:
    if not memories:
        return []
    max_access = max((m.access_count for m in memories), default=0)
    out: list[ScoredMemory] = []
    for m in memories:
        i = importance_score(m.importance)
        r = recency_score(m.last_accessed)
        a = access_score(m.access_count, max_access)
        score = 0.4 * i + 0.4 * r + 0.2 * a
        out.append(ScoredMemory(memory=m, score=score, importance=i, recency=r, access=a))
    out.sort(key=lambda s: s.score, reverse=True)
    return out


def select_hot(scored: list[ScoredMemory], hot_limit: int) -> list[ScoredMemory]:
    return scored[:max(hot_limit, 0)]
