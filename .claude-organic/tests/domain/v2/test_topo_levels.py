"""test_topo_levels.py — T-506 P2.

`engine.v2.core.plan_loader.topo_levels` 가 Kahn 알고리즘 확장으로 phase 들을
[level_0_phases, level_1_phases, ...] 형태로 반환.

driver 가 같은 level 동시 spawn → 다음 level 진입 패턴에 사용.
"""

from __future__ import annotations

from engine.v2.core.plan_loader import Phase, topo_levels


def _phase(pid: str, deps: list[str] | None = None) -> Phase:
    return Phase(id=pid, title=pid, deps=deps or [], deliverable=f"work/{pid}/W1.md")


def _ids(levels: list[list[Phase]]) -> list[list[str]]:
    return [sorted(p.id for p in lvl) for lvl in levels]


def test_topo_levels_linear_chain() -> None:
    """P1 → P2 → P3 → P4 — 각 level 1 phase."""
    phases = [
        _phase("P1"),
        _phase("P2", ["P1"]),
        _phase("P3", ["P2"]),
        _phase("P4", ["P3"]),
    ]
    assert _ids(topo_levels(phases)) == [["P1"], ["P2"], ["P3"], ["P4"]]


def test_topo_levels_parallel_siblings() -> None:
    """deps=[] siblings — 모두 level 0."""
    phases = [
        _phase("P1"),
        _phase("P2"),
        _phase("P3"),
    ]
    levels = topo_levels(phases)
    assert len(levels) == 1
    assert _ids(levels) == [["P1", "P2", "P3"]]


def test_topo_levels_diamond() -> None:
    """P1 → (P2, P3) → P4 — 3 level."""
    phases = [
        _phase("P1"),
        _phase("P2", ["P1"]),
        _phase("P3", ["P1"]),
        _phase("P4", ["P2", "P3"]),
    ]
    assert _ids(topo_levels(phases)) == [["P1"], ["P2", "P3"], ["P4"]]


def test_topo_levels_single_phase() -> None:
    """phase 1 개 → level 0 에 1 phase."""
    phases = [_phase("P1")]
    assert _ids(topo_levels(phases)) == [["P1"]]


def test_topo_levels_empty_input() -> None:
    """phases=[] → 빈 list (no-op)."""
    assert topo_levels([]) == []


def test_topo_levels_mixed_multi_deps() -> None:
    """P1, P2 (deps=[]) / P3 deps=[P1] / P4 deps=[P2] / P5 deps=[P3, P4]
    → level 0=[P1,P2], level 1=[P3,P4], level 2=[P5]."""
    phases = [
        _phase("P1"),
        _phase("P2"),
        _phase("P3", ["P1"]),
        _phase("P4", ["P2"]),
        _phase("P5", ["P3", "P4"]),
    ]
    levels = topo_levels(phases)
    assert _ids(levels) == [["P1", "P2"], ["P3", "P4"], ["P5"]]


def test_topo_levels_circular_returns_empty() -> None:
    """parse_plan_json 이 선검증하지만 안전망: 순환 발견 시 빈 list."""
    phases = [
        _phase("A", ["B"]),
        _phase("B", ["A"]),
    ]
    assert topo_levels(phases) == []


def test_topo_levels_preserves_input_order_within_level() -> None:
    """같은 level 안에서는 입력 phase 순서 보존 (deterministic)."""
    phases = [
        _phase("P3"),
        _phase("P1"),
        _phase("P2"),
    ]
    levels = topo_levels(phases)
    # level 0: 입력 순서 (P3, P1, P2)
    assert [p.id for p in levels[0]] == ["P3", "P1", "P2"]
