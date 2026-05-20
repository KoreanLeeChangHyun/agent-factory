"""Core validation artifact rules.

These checks are deterministic and do not call an LLM. They validate artifact
existence, minimum size, required tokens, and plan schema compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from engine.core.planning.loader import (
    Phase,
    Plan,
    PlanLoaderError,
    parse_plan_json,
    topo_sort,
)


@dataclass
class VerifyResult:
    """Validation result. When ok=True, missing is empty."""

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
    """Validate one file by existence, minimum size, and optional tokens."""
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
    """Validate PLAN artifacts: plan.json, plan.md, and plan.json schema."""
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
    """Validate every worker artifact for a multi-worker phase."""
    return verify_work_set(paths)


def verify_validate_md(path: Path) -> VerifyResult:
    """Validate validate-report.md by file existence and minimum size."""
    return verify_artifact(
        path,
        min_size=20,
        must_contain=(),
    )


def verify_report_html(path: Path, plan_md_path: Path) -> VerifyResult:
    """Validate report.html existence, size, and plan.md reference."""
    _ = plan_md_path
    return verify_artifact(
        path,
        min_size=50,
        must_contain=("plan.md",),
    )


__all__ = [
    "Phase",
    "Plan",
    "PlanLoaderError",
    "VerifyResult",
    "parse_plan_json",
    "topo_sort",
    "verify_artifact",
    "verify_plan_artifacts",
    "verify_report_html",
    "verify_validate_md",
    "verify_work_md",
    "verify_work_md_multi",
    "verify_work_set",
]
