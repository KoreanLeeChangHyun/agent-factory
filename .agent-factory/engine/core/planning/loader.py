"""Core planning loader for `plan/plan.json`.

Output Format Determination Canon (T-504):
- driver (machine) reads **JSON** file — json.loads + dataclass validation determinism.
- Natural language text for LLM ↔ LLM handover is stuffed separately in **plan/plan.md** (PLAN LLM is calculated simultaneously).
- This module is only responsible for JSON.

The production-line runtime keeps a compatibility wrapper at `engine.apps.production_line.core.plan_loader`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class PlanLoaderError(ValueError):
    """`plan/plan.json` parsing/verification failed. The driver catches the PLAN retry trigger."""


@dataclass
class Phase:
    """1 phases[] in plan.json.

    Field:
    - id: English letters + numbers (P1, P2, ...). Unique within the Phase graph.
    - title: A short line.
    - deps: Dependent Phase id list. Allow empty list. No self-referencing/non-existent IDs.
    - deliverable: `work/<id>/W<n>.md` (nested) or `work/<id>.md` (flat backward compat).
    - spawn_mode: in_place (default) | subprocess.
    - workers: Number of workers to spawn within this phase (default 1, 2+ are separate tracks).
    - acceptance_criteria: command=implement qualified obligation. list[str], 1+ items.
    """

    id: str
    title: str
    deps: list[str] = field(default_factory=list)
    deliverable: str = ""
    spawn_mode: str = "in_place"
    workers: int = 1
    acceptance_criteria: list[str] = field(default_factory=list)


@dataclass
class Plan:
    """top-level of plan.json."""

    schema_version: int
    ticket: str
    command: str
    mode: str
    phases: list[Phase]


def parse_plan_json(path: Path) -> Plan:
    """Reads `plan/plan.json` and returns verified `Plan`.

    On failure, raise `PlanLoaderError`. The driver is used as a PLAN retry trigger.

    Verification items:
    1. File exists + JSON parse success
    2. Required keys (schema_version / ticket / command / mode / phases) exist
    3. No empty list of phases
    4. Phase id unique
    5. deps exist within phases + self-reference is prohibited
    6. If command=implement, acceptance_criteria 1+ item obligation (no empty list)
    7. No deps graph rotation (Kahn topological sort)
    """
    if not path.exists():
        raise PlanLoaderError(f"plan.json not found: {path}")
    try:
        raw_text = path.read_text(encoding="utf-8")
        raw: Any = json.loads(raw_text)
    except (OSError, UnicodeDecodeError) as exc:
        raise PlanLoaderError(f"plan.json read error: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PlanLoaderError(f"plan.json invalid JSON: {exc}") from exc
    return _build_plan(raw)


def _build_plan(raw: Any) -> Plan:
    if not isinstance(raw, dict):
        raise PlanLoaderError("plan.json root must be a JSON object")

    if "schema_version" not in raw:
        raise PlanLoaderError("plan.json missing 'schema_version'")
    schema_version = raw["schema_version"]
    if not isinstance(schema_version, int):
        raise PlanLoaderError("plan.json 'schema_version' must be int")

    ticket = str(raw.get("ticket", "")).strip()
    if not ticket:
        raise PlanLoaderError("plan.json missing 'ticket'")
    command = str(raw.get("command", "implement")).strip() or "implement"
    mode = str(raw.get("mode", "multi")).strip() or "multi"

    phases_raw = raw.get("phases")
    if not isinstance(phases_raw, list) or not phases_raw:
        raise PlanLoaderError("plan.json 'phases' must be a non-empty list")

    phases: list[Phase] = []
    seen_ids: set[str] = set()
    for idx, item in enumerate(phases_raw):
        if not isinstance(item, dict):
            raise PlanLoaderError(f"phases[{idx}] is not an object")
        pid = item.get("id")
        if not isinstance(pid, str) or not pid:
            raise PlanLoaderError(f"phases[{idx}] missing 'id'")
        if pid in seen_ids:
            raise PlanLoaderError(f"phases[{idx}] duplicate id: {pid!r}")
        seen_ids.add(pid)
        deps_raw = item.get("deps", [])
        if not isinstance(deps_raw, list):
            raise PlanLoaderError(f"phases[{idx}].deps must be a list")
        deps = [str(d) for d in deps_raw]
        if pid in deps:
            raise PlanLoaderError(f"phases[{idx}] self-reference in deps: {pid!r}")
        ac_raw = item.get("acceptance_criteria", [])
        if not isinstance(ac_raw, list):
            raise PlanLoaderError(
                f"phases[{idx}].acceptance_criteria must be a list"
            )
        acceptance_criteria = [str(a) for a in ac_raw]
        phases.append(
            Phase(
                id=pid,
                title=str(item.get("title", "")),
                deps=deps,
                deliverable=str(item.get("deliverable", "")),
                spawn_mode=str(item.get("spawn_mode", "in_place") or "in_place"),
                workers=int(item.get("workers", 1) or 1),
                acceptance_criteria=acceptance_criteria,
            )
        )

    # deps must exist within phases
    for ph in phases:
        for d in ph.deps:
            if d not in seen_ids:
                raise PlanLoaderError(
                    f"phases[{ph.id}].deps references unknown id: {d!r}"
                )

    # command=implement if acceptance_criteria obligation 1+
    if command == "implement":
        for ph in phases:
            if not ph.acceptance_criteria:
                raise PlanLoaderError(
                    f"phases[{ph.id}].acceptance_criteria empty "
                    "(implement limited obligation)"
                )

    # Cycle-dependent detection — Kahn topo sort
    if not _has_topo_order(phases):
        raise PlanLoaderError("plan.json phases has circular deps")

    return Plan(
        schema_version=schema_version,
        ticket=ticket,
        command=command,
        mode=mode,
        phases=phases,
    )


def _has_topo_order(phases: list[Phase]) -> bool:
    """True if the Kahn topological sort exhausts all phases (no cycles)."""
    by_id = {p.id: p for p in phases}
    in_degree: dict[str, int] = {p.id: 0 for p in phases}
    edges: dict[str, list[str]] = {p.id: [] for p in phases}
    for p in phases:
        for d in p.deps:
            edges[d].append(p.id)
            in_degree[p.id] += 1
    queue = [pid for pid, deg in in_degree.items() if deg == 0]
    visited = 0
    while queue:
        pid = queue.pop(0)
        visited += 1
        for nxt in edges[pid]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)
    return visited == len(by_id)


def topo_sort(phases: list[Phase]) -> list[Phase] | None:
    """Kahn topological sort — determining execution order.

    Plans that pass `parse_plan_json` are guaranteed to have no cycles. This function has a driver
    Used to determine execution order in WORK Step.

    Returns:
        A topologically sorted Phase list. None if cycle is detected.
    """
    by_id = {p.id: p for p in phases}
    in_degree: dict[str, int] = {p.id: 0 for p in phases}
    edges: dict[str, list[str]] = {p.id: [] for p in phases}
    for p in phases:
        for d in p.deps:
            if d not in by_id:
                return None
            edges[d].append(p.id)
            in_degree[p.id] += 1
    queue = [pid for pid, deg in in_degree.items() if deg == 0]
    sorted_ids: list[str] = []
    while queue:
        pid = queue.pop(0)
        sorted_ids.append(pid)
        for nxt in edges[pid]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)
    if len(sorted_ids) != len(phases):
        return None
    return [by_id[pid] for pid in sorted_ids]


def topo_levels(phases: list[Phase]) -> list[list[Phase]]:
    """T-506 P2 — Kahn extension. Returns the phases grouped by topological level.

    The maximum level of the phase of level k is k-1 among the phases indicated by deps.
    deps=[] phase is level 0. Driver spawns at the same level → all phases
    Used for patterns that enter the next level after completion.

    Returns:
        `[[level_0_phases], [level_1_phases], ...]`. Phase order within the same level
        Preserves the order of the input phase list (deterministic).
        In case of circular dependency or unknown dep, an empty list is returned (parse_plan_json pre-verifies).
    """
    if not phases:
        return []
    by_id = {p.id: p for p in phases}
    # unknown dep detection — safe blocking even if not circulating
    for p in phases:
        for d in p.deps:
            if d not in by_id:
                return []
    level_of: dict[str, int] = {}
    # Iterative resolution — Process starting from the phase when all deps levels are confirmed
    remaining = list(phases)
    while remaining:
        progressed = False
        next_remaining: list[Phase] = []
        for p in remaining:
            if all(d in level_of for d in p.deps):
                dep_max = max((level_of[d] for d in p.deps), default=-1)
                level_of[p.id] = dep_max + 1
                progressed = True
            else:
                next_remaining.append(p)
        if not progressed:
            # Circular dependence — remaining phases point to each other
            return []
        remaining = next_remaining
    max_level = max(level_of.values())
    levels: list[list[Phase]] = [[] for _ in range(max_level + 1)]
    for p in phases:  # Preserve input order
        levels[level_of[p.id]].append(p)
    return levels
