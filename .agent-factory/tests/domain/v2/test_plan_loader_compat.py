"""Compatibility tests for the V2 plan loader export surface."""

from __future__ import annotations

from engine.core.planning import loader as core_loader
from engine.v2.core import plan_loader as v2_loader


def test_v2_plan_loader_re_exports_core_types() -> None:
    assert v2_loader.Phase is core_loader.Phase
    assert v2_loader.Plan is core_loader.Plan
    assert v2_loader.PlanLoaderError is core_loader.PlanLoaderError


def test_v2_plan_loader_re_exports_core_functions() -> None:
    assert v2_loader.parse_plan_json is core_loader.parse_plan_json
    assert v2_loader.topo_sort is core_loader.topo_sort
    assert v2_loader.topo_levels is core_loader.topo_levels

