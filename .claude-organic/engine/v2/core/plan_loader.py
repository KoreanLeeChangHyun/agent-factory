"""T-504 — `plan/plan.json` SSOT 파서.

산출물 형식 결정 캐논 (T-504):
- driver (기계) 는 **JSON** 파일을 읽는다 — json.loads + dataclass 검증 결정론.
- LLM ↔ LLM 인계용 자연어 본문은 **plan/plan.md** 가 별도로 박제 (PLAN LLM 동시 산출).
- 본 모듈은 JSON 만 책임.

cutover: 옛 `_verify.py` 의 `parse_plan_frontmatter` (YAML frontmatter) 는 통째 폐기.
T-489 v2 cutover 정책과 동일 — backward compat shim 0건.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class PlanLoaderError(ValueError):
    """`plan/plan.json` 파싱·검증 실패. driver 가 잡아 PLAN 재시도 trigger."""


@dataclass
class Phase:
    """plan.json 의 phases[] 1개.

    필드:
    - id: 영문+숫자 (P1, P2, ...). Phase 그래프 안에서 unique.
    - title: 짧은 한 줄.
    - deps: 의존 Phase id 리스트. 빈 list 허용. 자기참조/미존재 ID 금지.
    - deliverable: `work/<id>/W<n>.md` (nested) 또는 `work/<id>.md` (flat backward compat).
    - spawn_mode: in_place (default) | subprocess.
    - workers: 본 phase 안에서 spawn 할 worker 수 (default 1, 2+ 는 별 트랙).
    - acceptance_criteria: command=implement 한정 의무. list[str], 1+ 항목.
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
    """plan.json 의 top-level."""

    schema_version: int
    ticket: str
    command: str
    mode: str
    phases: list[Phase]


def parse_plan_json(path: Path) -> Plan:
    """`plan/plan.json` 을 읽어 검증된 `Plan` 반환.

    실패 시 `PlanLoaderError` raise. driver 가 PLAN 재시도 trigger 로 사용.

    검증 항목:
    1. 파일 존재 + JSON parse 성공
    2. 필수 키 (schema_version / ticket / command / mode / phases) 존재
    3. phases 빈 list 금지
    4. Phase id unique
    5. deps 가 phases 안에 존재 + 자기 자신 참조 금지
    6. command=implement 인 경우 acceptance_criteria 1+ 항목 의무 (빈 list 금지)
    7. deps 그래프 순환 없음 (Kahn topological sort)
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

    # deps 가 phases 안에 존재해야 함
    for ph in phases:
        for d in ph.deps:
            if d not in seen_ids:
                raise PlanLoaderError(
                    f"phases[{ph.id}].deps references unknown id: {d!r}"
                )

    # command=implement 면 acceptance_criteria 의무 1+
    if command == "implement":
        for ph in phases:
            if not ph.acceptance_criteria:
                raise PlanLoaderError(
                    f"phases[{ph.id}].acceptance_criteria empty "
                    "(implement 한정 의무)"
                )

    # 순환 의존 검출 — Kahn topo sort
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
    """Kahn topological sort 가 모든 phase 를 소진하면 True (순환 없음)."""
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
    """Kahn topological sort — 실행 순서 결정.

    `parse_plan_json` 통과한 plan 은 순환 없음 보장. 본 함수는 driver 가
    WORK Step 에서 실행 순서 결정 용도.

    Returns:
        topologically sorted Phase 리스트. 순환 발견 시 None.
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
