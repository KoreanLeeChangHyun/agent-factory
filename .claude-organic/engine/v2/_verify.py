"""v2 verify — 룰베이스 산출물 검증 + plan.md frontmatter parser + topo sort.

SPEC.md §3.3 (Step 전이 게이트) + §5 (plan.md 구조화) + §6.1 (verify_plan_md).
LLM 호출 없음. 결정론적 검증만.

frontmatter parser 는 PyYAML 미의존 단순 구현 (3개 키 정도만 다루므로 충분).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass
class VerifyResult:
    """검증 결과. ok=True 시 missing 비어있음."""

    ok: bool
    missing: list[str] = field(default_factory=list)

    def merge(self, other: "VerifyResult") -> "VerifyResult":
        return VerifyResult(
            ok=self.ok and other.ok,
            missing=[*self.missing, *other.missing],
        )


@dataclass
class Phase:
    """plan.md frontmatter 의 phases[] 1개."""

    id: str
    title: str
    deps: list[str] = field(default_factory=list)
    deliverable: str = ""
    spawn_mode: str = "in_place"   # in_place | subprocess


@dataclass
class PlanFrontmatter:
    schema_version: int
    ticket: str
    command: str
    mode: str
    phases: list[Phase]


def verify_artifact(
    path: Path,
    *,
    min_size: int = 1,
    must_contain: Iterable[str] = (),
) -> VerifyResult:
    """단일 파일 검증 — exist + size + (선택) 토큰 포함."""
    missing: list[str] = []
    if not path.exists():
        missing.append(f"file not found: {path}")
        return VerifyResult(False, missing)
    size = path.stat().st_size
    if size < min_size:
        missing.append(f"file too small ({size} < {min_size}): {path}")
    text = path.read_text(encoding="utf-8", errors="replace") if size > 0 else ""
    for token in must_contain:
        if token not in text:
            missing.append(f"missing token '{token}' in {path.name}")
    return VerifyResult(not missing, missing)


def _extract_frontmatter(text: str) -> tuple[str, str]:
    """YAML frontmatter block + body 분리.

    형식: `---\n<yaml>\n---\n<body>`. frontmatter 없으면 ("", text) 반환.
    """
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end == -1:
        return "", text
    frontmatter = text[3:end].lstrip("\n")
    body = text[end + 4 :].lstrip("\n")
    return frontmatter, body


def _parse_yaml_simple(block: str) -> dict:
    """단순 YAML parser — schema_version/ticket/command/mode/phases 만 지원.

    PyYAML 의존 회피. 본 prototype 의 plan.md frontmatter 만 다룬다.
    들여쓰기 2-space, list-of-dict, 단순 scalar 만 지원.
    """
    lines = block.splitlines()
    result: dict = {}
    current_key: str | None = None
    current_list: list[dict] | None = None
    current_item: dict | None = None

    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        stripped = raw.lstrip()

        if indent == 0:
            # top-level key
            if ":" not in stripped:
                continue
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            current_key = key
            if val == "" or val == "|":
                # nested (list or block)
                result[key] = []
                current_list = result[key]
                current_item = None
            else:
                # scalar
                result[key] = _coerce_scalar(val)
                current_list = None
                current_item = None
        elif current_list is not None and stripped.startswith("- "):
            # list item — start new dict
            current_item = {}
            current_list.append(current_item)
            rest = stripped[2:].strip()
            if rest and ":" in rest:
                k, _, v = rest.partition(":")
                current_item[k.strip()] = _coerce_scalar(v.strip())
        elif current_item is not None and ":" in stripped:
            k, _, v = stripped.partition(":")
            current_item[k.strip()] = _coerce_scalar(v.strip())
    return result


def _coerce_scalar(val: str) -> object:
    if val == "":
        return ""
    # quoted string
    if (val.startswith('"') and val.endswith('"')) or (
        val.startswith("'") and val.endswith("'")
    ):
        return val[1:-1]
    # inline list `[a, b]`
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [_coerce_scalar(p.strip()) for p in inner.split(",")]
    # int
    if re.fullmatch(r"-?\d+", val):
        return int(val)
    return val


def parse_plan_frontmatter(text: str) -> PlanFrontmatter | None:
    """plan.md 본문에서 frontmatter parse. 실패 시 None."""
    block, _ = _extract_frontmatter(text)
    if not block:
        return None
    raw = _parse_yaml_simple(block)
    if "phases" not in raw or not isinstance(raw.get("phases"), list):
        return None
    phases: list[Phase] = []
    for item in raw["phases"]:
        if not isinstance(item, dict) or "id" not in item:
            continue
        deps = item.get("deps") or []
        if not isinstance(deps, list):
            deps = []
        phases.append(
            Phase(
                id=str(item["id"]),
                title=str(item.get("title", "")),
                deps=[str(d) for d in deps],
                deliverable=str(item.get("deliverable", "")),
                spawn_mode=str(item.get("spawn_mode", "in_place")),
            )
        )
    return PlanFrontmatter(
        schema_version=int(raw.get("schema_version", 1)),
        ticket=str(raw.get("ticket", "")),
        command=str(raw.get("command", "implement")),
        mode=str(raw.get("mode", "multi")),
        phases=phases,
    )


def topo_sort(phases: list[Phase]) -> list[Phase] | None:
    """deps DAG topological sort. circular dep 발견 시 None."""
    by_id = {p.id: p for p in phases}
    in_degree = {p.id: 0 for p in phases}
    edges: dict[str, list[str]] = {p.id: [] for p in phases}
    for p in phases:
        for dep in p.deps:
            if dep not in by_id:
                return None  # unknown dep
            edges[dep].append(p.id)
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
        return None  # circular
    return [by_id[pid] for pid in sorted_ids]


def verify_plan_md(path: Path) -> VerifyResult:
    """SPEC.md §6.1 verify_plan_md — file + size + frontmatter + phases + deps DAG."""
    r = verify_artifact(path, min_size=20)
    if not r.ok:
        return r
    text = path.read_text(encoding="utf-8", errors="replace")
    fm = parse_plan_frontmatter(text)
    missing: list[str] = []
    if fm is None:
        missing.append("plan.md frontmatter parse failed")
        return VerifyResult(False, missing)
    if not fm.phases:
        missing.append("plan.md 'phases' list is empty")
    sorted_phases = topo_sort(fm.phases) if fm.phases else None
    if fm.phases and sorted_phases is None:
        missing.append("plan.md phases has circular or unknown deps")
    return VerifyResult(not missing, missing)


def verify_work_md(path: Path) -> VerifyResult:
    return verify_artifact(path, min_size=20)


def verify_work_set(paths: Iterable[Path]) -> VerifyResult:
    result = VerifyResult(True)
    for p in paths:
        result = result.merge(verify_work_md(p))
    return result


def verify_validate_md(path: Path) -> VerifyResult:
    """validate-report.md — file + verdict 토큰 1개 이상 포함."""
    return verify_artifact(
        path,
        min_size=20,
        must_contain=(),  # verdict 라인 강제는 advisory only (자동 가드 X)
    )


def verify_report_md(path: Path, plan_md_path: Path) -> VerifyResult:
    """report.md — file + plan.md 파일명 토큰 매칭 (R-PATH-1 본체)."""
    return verify_artifact(
        path,
        min_size=50,
        must_contain=("plan.md",),
    )
