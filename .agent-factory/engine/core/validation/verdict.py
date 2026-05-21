"""Core validation verdict payloads and gate registry.

This module is deterministic and infrastructure-free. It accepts a
workflow-like context object by duck type so runtime packages can keep their
existing context implementation while core owns the validation payload model.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from engine.core.validation import code_checks
from engine.core.validation.artifact_rules import (
    VerifyResult,
    verify_plan_artifacts,
    verify_validate_md,
    verify_work_set,
)


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Gate:
    rule_id: str
    title: str
    severity: str
    source: str


GATE_REGISTRY: tuple[Gate, ...] = (
    Gate("R-EXIST-1", "report artifact exists", "blocking", "artifact"),
    Gate("R-EXIST-2", "plan artifact exists", "advisory", "artifact"),
    Gate("R-EXIST-3", "status has workflow step", "advisory", "artifact"),
    Gate("R-EXIST-4", "metrics stream exists", "advisory", "artifact"),
    Gate("R-METRIC-2", "complete step ended ok", "blocking", "metric"),
    Gate("R-METRIC-3", "tool denies absent", "advisory", "metric"),
    Gate("R-GUARD-1", "worktree mode is active when required", "advisory", "guard"),
    Gate("R-GUARD-2", "feature branch exists", "advisory", "guard"),
    Gate("R-GUARD-3", "regression patterns absent", "advisory", "guard"),
    Gate("R-PATH-1", "report links plan artifact", "advisory", "path"),
    Gate("R-FSM-1", "workflow reached terminal stage", "advisory", "fsm"),
    Gate("R-WT-1", "implementation has commits ahead", "blocking", "guard"),
    Gate("R-CODE-1", "pytest passed or was skipped", "blocking", "code"),
    Gate("R-CODE-2", "ruff diagnostics clean", "advisory", "code"),
)


def gate_registry_payload() -> list[dict[str, str]]:
    return [asdict(g) for g in GATE_REGISTRY]


def get_blocking_rule_ids() -> tuple[str, ...]:
    return tuple(g.rule_id for g in GATE_REGISTRY if g.severity == "blocking")


def result_payload(name: str, result: VerifyResult, path: Path | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": name,
        "ok": result.ok,
        "issues": list(result.missing),
    }
    if path is not None:
        payload["path"] = str(path)
    return payload


def compute_preliminary_verdict(checks: Iterable[dict[str, Any]]) -> str:
    failed = [check for check in checks if not check.get("ok")]
    if not failed:
        return "PASS"
    blocking = [check for check in failed if check.get("blocking")]
    if blocking or len(failed) >= 3:
        return "FAIL"
    return "WARN"


def write_verify_verdict(ctx: Any) -> Path:
    """Write VERIFY-stage structured verdict data."""
    work_paths = sorted((ctx.work_dir / "work").glob("**/*.md"))
    work_result = (
        verify_work_set(work_paths)
        if work_paths
        else VerifyResult(False, ["no work/**/*.md artifacts found"])
    )
    plan_result = verify_plan_artifacts(ctx.plan_json_path(), ctx.plan_md_path())
    semantic_result = verify_validate_md(ctx.validate_report_md_path())
    code_payload = code_checks.read_code_json(ctx)

    code_failed = False
    code_issues: list[str] = []
    for tool in code_payload.get("tools", []) if isinstance(code_payload, dict) else []:
        if not isinstance(tool, dict):
            continue
        if tool.get("status") == "fail":
            code_failed = True
            code_issues.append(f"{tool.get('tool', 'unknown')} failed")

    checks = [
        {**result_payload("plan_artifacts", plan_result, ctx.plan_dir()), "blocking": False},
        {**result_payload("work_artifacts", work_result, ctx.work_dir / "work"), "blocking": False},
        {
            **result_payload(
                "semantic_evaluation_artifact",
                semantic_result,
                ctx.validate_report_md_path(),
            ),
            "blocking": False,
        },
        {
            "name": "code_checks",
            "ok": not code_failed,
            "issues": code_issues,
            "path": str(ctx.validate_code_json_path()),
            "blocking": ctx.command == "implement",
        },
    ]

    payload = {
        "schema_version": SCHEMA_VERSION,
        "stage": "VERIFY",
        "work_request_no": ctx.work_request_no,
        "registry_key": ctx.registry_key,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "deterministic_artifacts": checks[:2],
        "semantic_evaluation": {
            "artifact": str(ctx.validate_report_md_path()),
            "ok": semantic_result.ok,
            "issues": semantic_result.missing,
            "owner": "validate LLM",
        },
        "code_checks": code_payload or {
            "schema_version": 1,
            "command": ctx.command,
            "tools": [],
            "missing": True,
        },
        "preliminary_verdict": compute_preliminary_verdict(checks),
        "refinement": {
            "suggested": any(not c.get("ok") for c in checks),
            "reason": "; ".join(i for c in checks for i in c.get("issues", []))[:500],
        },
    }
    path = ctx.validate_verdict_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_verify_verdict(ctx: Any) -> dict[str, Any]:
    path = ctx.validate_verdict_json_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_report_manifest(ctx: Any) -> Path:
    """Write a consistent report manifest consumed by downstream UI/review."""
    verify_payload = read_verify_verdict(ctx)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "stage": "REPORT",
        "work_request_no": ctx.work_request_no,
        "registry_key": ctx.registry_key,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "request": str(ctx.user_prompt_path()),
        "plan": {
            "json": str(ctx.plan_json_path()),
            "markdown": str(ctx.plan_md_path()),
        },
        "artifacts": {
            "work": str(ctx.work_dir / "work"),
            "report_html": str(ctx.report_html_path()),
            "validate_report": str(ctx.validate_report_md_path()),
            "validate_verdict": str(ctx.validate_verdict_json_path()),
            "code_checks": str(ctx.validate_code_json_path()),
        },
        "checks": {
            "verify_stage": verify_payload,
        },
        "final_decision": {
            "status": "pending_complete",
            "path": str(ctx.final_verdict_json_path()),
        },
    }
    path = ctx.report_manifest_json_path()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_final_verdict(ctx: Any, verdict_report: Any) -> dict[str, Any]:
    """Build COMPLETE-stage final verdict from rule results."""
    rules = getattr(verdict_report, "rules", [])
    blocking_ids = set(get_blocking_rule_ids())
    failures: list[dict[str, Any]] = []
    advisory_failures: list[dict[str, Any]] = []
    for rule in rules:
        if getattr(rule, "ok", False) or getattr(rule, "skip", False):
            continue
        item = {
            "rule_id": getattr(rule, "rule_id", ""),
            "detail": getattr(rule, "detail", ""),
        }
        if item["rule_id"] in blocking_ids:
            failures.append(item)
        else:
            advisory_failures.append(item)

    complete_outcome = "blocked" if failures else "pass"
    refinement_reasons = [f"{f['rule_id']}: {f['detail']}" for f in failures]
    return {
        "schema_version": SCHEMA_VERSION,
        "stage": "COMPLETE",
        "work_request_no": ctx.work_request_no,
        "registry_key": ctx.registry_key,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": getattr(verdict_report, "verdict", "FAIL"),
        "complete_outcome": complete_outcome,
        "blocking_failures": failures,
        "advisory_failures": advisory_failures,
        "work_request_refinement": {
            "suggested": bool(failures),
            "work_request": ctx.work_request_no,
            "reason": "; ".join(refinement_reasons)[:500],
            "fields": {
                "context": f"Verification blocked COMPLETE. See {ctx.final_verdict_json_path()}",
                "criteria": "Address blocking verification gates before accepting COMPLETE.",
            } if failures else {},
        },
        "gate_registry": gate_registry_payload(),
        "links": {
            "request": str(ctx.user_prompt_path()),
            "plan": str(ctx.plan_md_path()),
            "report": str(ctx.report_html_path()),
            "report_manifest": str(ctx.report_manifest_json_path()),
            "verify_verdict": str(ctx.validate_verdict_json_path()),
            "rules": str(ctx.validate_rules_json_nested_path()),
            "code": str(ctx.validate_code_json_path()),
        },
    }


def save_final_verdict(ctx: Any, payload: dict[str, Any]) -> Path:
    path = ctx.final_verdict_json_path()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


__all__ = [
    "GATE_REGISTRY",
    "SCHEMA_VERSION",
    "Gate",
    "build_final_verdict",
    "compute_preliminary_verdict",
    "gate_registry_payload",
    "get_blocking_rule_ids",
    "read_verify_verdict",
    "result_payload",
    "save_final_verdict",
    "write_report_manifest",
    "write_verify_verdict",
]
