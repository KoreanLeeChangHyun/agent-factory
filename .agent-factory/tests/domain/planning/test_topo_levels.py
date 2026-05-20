"""Tests for topological planning levels.

`engine.core.planning.loader.topo levels` to expand the Kahn algorithm
[level 0 phases, level 1 phases, ...] return to form.

same level simultaneous spawn with driver → used in the next level entry pattern.
"""

from __future__ import annotations

from engine.core.planning.loader import Phase, topo_levels


def _phase(pid: str, deps: list[str] | None = None) -> Phase:
    return Phase(id=pid, title=pid, deps=deps or [], deliverable=f"work/{pid}/W1.md")


def _ids(levels: list[list[Phase]]) -> list[list[str]]:
    return [sorted(p.id for p in lvl) for lvl in levels]


def test_topo_levels_linear_chain() -> None:
    """P1 → P2 → P3 → P4"""
    phases = [
        _phase("P1"),
        _phase("P2", ["P1"]),
        _phase("P3", ["P2"]),
        _phase("P4", ["P3"]),
    ]
    assert _ids(topo_levels(phases)) == [["P1"], ["P2"], ["P3"], ["P4"]]


def test_topo_levels_parallel_siblings() -> None:
    """deps=[] siblings — all levels 0."""
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
    """Phase 1 → level 0 to 1 phase."""
    phases = [_phase("P1")]
    assert _ids(topo_levels(phases)) == [["P1"]]


def test_topo_levels_empty_input() -> None:
    """phases=[]"""
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
    """parse plan json This is a validation but a safety net: empty list when the circulation is found."""
    phases = [
        _phase("A", ["B"]),
        _phase("B", ["A"]),
    ]
    assert topo_levels(phases) == []


def test_topo_levels_preserves_input_order_within_level() -> None:
    """In the same level the input phase sequence retention (deterministic)."""
    phases = [
        _phase("P3"),
        _phase("P1"),
        _phase("P2"),
    ]
    levels = topo_levels(phases)
    # level 0: Input order (P3, P1, P2)
    assert [p.id for p in levels[0]] == ["P3", "P1", "P2"]
