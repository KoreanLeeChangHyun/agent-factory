"""GC 사이클 오케스트레이터 + 실행 결과 영속화.

run(): 점수 → dedup → reflection → 인덱스 재생성 → last_run.json 기록
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .core import scan_memories, regenerate_index
from .dedup import find_duplicates, apply_dedup
from .paths import GCConfig, ensure_skeleton
from .reflection import run_reflection
from .tier import score_memories, select_hot


@dataclass
class GCRunReport:
    started_at: str
    finished_at: str
    total_memories: int
    hot_count: int
    dedup_candidates: int
    dedup_applied: int
    reflection_clusters: int
    reflection_synthesized: int
    apply: bool
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        verb = 'apply' if self.apply else 'dry-run'
        return (
            f'[{verb}] total={self.total_memories} hot={self.hot_count} '
            f'dedup={self.dedup_applied}/{self.dedup_candidates} '
            f'synth={self.reflection_synthesized}/{self.reflection_clusters}'
        )


def _persist(cfg: GCConfig, report: GCRunReport) -> None:
    cfg.gc_meta_dir.mkdir(parents=True, exist_ok=True)
    cfg.last_run_path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def run_cycle(cfg: GCConfig, *, apply: bool, with_reflection: bool = True) -> GCRunReport:
    """전체 GC 사이클.

    Args:
        apply: True 면 dedup·reflection 결과 실제 반영. False 면 후보 집계만.
        with_reflection: False 면 reflection LLM 호출 스킵.
    """
    started = dt.datetime.now().isoformat(timespec='seconds')
    ensure_skeleton(cfg)
    errors: list[str] = []

    memories = scan_memories(cfg)
    scored = score_memories(memories)
    hot = select_hot(scored, cfg.hot_limit)

    # 1) dedup
    dedup_cands = find_duplicates(memories)
    dedup_applied: list[Path] = []
    if apply and dedup_cands:
        try:
            dedup_applied = apply_dedup(cfg, dedup_cands)
        except OSError as exc:
            errors.append(f'dedup_failed: {exc}')

    # dedup 후 메모리 재스캔 (반영 시)
    memories_after = scan_memories(cfg) if apply and dedup_applied else memories

    # 2) reflection
    refl = type('R', (), {'cluster_count': 0, 'synthesized': [], 'skipped': 0})()  # placeholder
    if with_reflection:
        try:
            refl = run_reflection(cfg, memories_after, apply=apply)
        except Exception as exc:  # noqa: BLE001 — silent fail 정책
            errors.append(f'reflection_failed: {exc!r}')

    # 3) 인덱스 재생성 (apply 시)
    final_memories = scan_memories(cfg) if apply else memories
    if apply:
        try:
            regenerate_index(cfg, final_memories)
        except OSError as exc:
            errors.append(f'index_regen_failed: {exc}')

    finished = dt.datetime.now().isoformat(timespec='seconds')
    report = GCRunReport(
        started_at=started,
        finished_at=finished,
        total_memories=len(final_memories),
        hot_count=len(hot),
        dedup_candidates=len(dedup_cands),
        dedup_applied=len(dedup_applied),
        reflection_clusters=getattr(refl, 'cluster_count', 0),
        reflection_synthesized=len(getattr(refl, 'synthesized', [])),
        apply=apply,
        errors=errors,
    )
    if apply:
        _persist(cfg, report)
    return report


def load_last_run(cfg: GCConfig) -> dict | None:
    if not cfg.last_run_path.exists():
        return None
    try:
        return json.loads(cfg.last_run_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
