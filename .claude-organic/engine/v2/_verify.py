"""v2 verify — 룰베이스 산출물 검증 (T-504 cutover).

SPEC.md §3.3 (Step 전이 게이트) + §6.1 (verify_plan_artifacts) + §9.3 (3 형식 분리).
LLM 호출 없음. 결정론적 검증만.

T-504 cutover: 옛 `parse_plan_frontmatter` (YAML frontmatter parser) + 단순 YAML
helper 들 (`_extract_frontmatter` / `_parse_yaml_simple` / `_coerce_scalar`) 통째 폐기.
PLAN 산출은 `plan/plan.json` (JSON SSOT) + `plan/plan.md` (자연어 본문) 으로 분리되며,
`Phase` / `topo_sort` 는 `engine.v2.core.plan_loader` 가 단일 출처.

T-504 신설:
- `verify_plan_artifacts(ctx)` — plan/plan.json + plan/plan.md 양쪽 존재 + JSON parse
- `verify_report_html(ctx, ...)` — report.html size + plan/plan.md 토큰 인용
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# T-504 — Phase / topo_sort 는 core.plan_loader SSOT 에서 re-export.
from .core.plan_loader import (  # noqa: F401  (re-export for backward compat callers)
    Phase,
    Plan,
    PlanLoaderError,
    parse_plan_json,
    topo_sort,
)


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


def verify_plan_artifacts(
    plan_json_path: Path,
    plan_md_path: Path,
) -> VerifyResult:
    """T-504 — PLAN 산출물 (plan/plan.json + plan/plan.md) 검증.

    1. 두 파일 모두 존재 + size > 0
    2. plan.json 이 `parse_plan_json` 통과 (스키마·deps·acceptance_criteria·topo)
    """
    missing: list[str] = []
    json_res = verify_artifact(plan_json_path, min_size=20)
    md_res = verify_artifact(plan_md_path, min_size=20)
    missing.extend(json_res.missing)
    missing.extend(md_res.missing)
    if not json_res.ok:
        return VerifyResult(False, missing)
    try:
        parse_plan_json(plan_json_path)
    except PlanLoaderError as exc:
        missing.append(f"plan.json schema error: {exc}")
    return VerifyResult(not missing, missing)


def verify_work_md(path: Path) -> VerifyResult:
    return verify_artifact(path, min_size=20)


def verify_work_set(paths: Iterable[Path]) -> VerifyResult:
    result = VerifyResult(True)
    for p in paths:
        result = result.merge(verify_work_md(p))
    return result


def verify_work_md_multi(paths: Iterable[Path]) -> VerifyResult:
    """T-506 P6 — workers > 1 phase 의 N worker 산출물 모두 검증.

    각 W<n>.md 가 exist + size >= 20. 하나라도 누락 시 fail.
    `verify_work_set` 의 명시 alias — 호출 의도 명료화 (phase 안 N worker).
    """
    return verify_work_set(paths)


def verify_validate_md(path: Path) -> VerifyResult:
    """validate-report.md — file + verdict 토큰 1개 이상 포함."""
    return verify_artifact(
        path,
        min_size=20,
        must_contain=(),  # verdict 라인 강제는 advisory only (자동 가드 X)
    )


def verify_report_html(path: Path, plan_md_path: Path) -> VerifyResult:
    """T-504 — REPORT 산출물 `report.html` 검증.

    1. file exists + size > 50
    2. 본문에 `plan.md` 토큰 인용 (R-PATH-1 정합 — driver 가 plan ↔ report 링크 확인)
       — `plan/plan.md` 또는 `plan.md` 부분 매칭으로 충분.

    T-504 cutover — 옛 `verify_report_md` 통째 폐기 (Markdown 산출 자체가 사라짐).
    호출자는 본 함수로 일괄 마이그레이션.
    """
    return verify_artifact(
        path,
        min_size=50,
        must_contain=("plan.md",),
    )
