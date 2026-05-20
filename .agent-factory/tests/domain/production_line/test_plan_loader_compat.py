"""Compatibility tests for the production-line plan loader export surface."""

from __future__ import annotations

from engine.core.planning import loader as core_loader
from engine.apps.production_line.core import plan_loader as production_line_loader


def test_production_line_plan_loader_re_exports_core_types() -> None:
    assert production_line_loader.Phase is core_loader.Phase
    assert production_line_loader.Plan is core_loader.Plan
    assert production_line_loader.PlanLoaderError is core_loader.PlanLoaderError


def test_production_line_plan_loader_re_exports_core_functions() -> None:
    assert production_line_loader.parse_plan_json is core_loader.parse_plan_json
    assert production_line_loader.topo_sort is core_loader.topo_sort
    assert production_line_loader.topo_levels is core_loader.topo_levels

