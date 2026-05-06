#!/usr/bin/env -S python3 -u
"""Workflow Review Auditor — Phase 1 (T-413).

Review 컬럼에 진입한 티켓의 산출물·코드 실재성을 자동 검증한다.

격리 원칙:
    워크플로우 엔진(.claude-organic/engine/*) 모듈을 import 하지 않는다.
    표준 라이브러리만 사용한다 (Phase 3 LLM 단계에서만 anthropic SDK 추가 예정).

Phase 1 (본 모듈) 범위:
    T1 정형 검증: 워크플로우 산출물(workdir/plan/report) 파일 실재 +
    status.json step == DONE 검증.
    T2/T3 는 Phase 2/3 에서 추가.

CLI:
    python3 .claude-organic/audit/auditor.py T-NNN [--tier 1|2|3] [--no-save]
    flow-audit T-NNN [--tier N]   # bin wrapper

출력:
    stdout: 사람용 요약
    파일:   .claude-organic/audit/results/T-NNN-{YYYYMMDD-HHMMSS}.json
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

# 격리: project_root 를 자체 결정 (workflow common 모듈 의존 X).
# audit/auditor.py 의 부모(audit) → 부모(.claude-organic) → 부모(project root).
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
_KST = timezone(timedelta(hours=9))


def _now_iso() -> str:
    return datetime.now(_KST).strftime("%Y-%m-%dT%H:%M:%S%z")


def _now_compact() -> str:
    return datetime.now(_KST).strftime("%Y%m%d-%H%M%S")


def _find_ticket_xml(ticket_number: str) -> Optional[Path]:
    """모든 칸반 컬럼에서 티켓 XML 파일을 탐색."""
    tickets_root = _PROJECT_ROOT / ".claude-organic" / "tickets"
    for column in ("review", "done", "open", "progress", "todo"):
        candidate = tickets_root / column / f"{ticket_number}.xml"
        if candidate.is_file():
            return candidate
    return None


def _load_ticket(ticket_number: str) -> Optional[dict[str, Any]]:
    """티켓 XML 을 dict 로 로드."""
    ticket_path = _find_ticket_xml(ticket_number)
    if not ticket_path:
        return None
    try:
        tree = ET.parse(ticket_path)
        root = tree.getroot()
    except ET.ParseError:
        return None

    metadata: dict[str, str] = {}
    metadata_el = root.find("metadata")
    if metadata_el is not None:
        for child in metadata_el:
            metadata[child.tag] = (child.text or "").strip()

    result: dict[str, str] = {}
    result_el = root.find("result")
    if result_el is not None:
        for child in result_el:
            result[child.tag] = (child.text or "").strip()

    return {
        "_path": str(ticket_path),
        "_column": ticket_path.parent.name,
        "metadata": metadata,
        "result": result,
    }


def _t1_formal(ticket: dict[str, Any]) -> dict[str, Any]:
    """T1 정형 검증.

    워크플로우 result 가 비어있으면 메인 직접 작업으로 분류 → SKIP.
    채워진 경우 다음을 확인한다:
        1. workdir 디렉터리 실재
        2. plan 파일 실재
        3. report 파일 실재
        4. status.json 의 step == "DONE"
    """
    result = ticket.get("result") or {}
    if not result:
        return {
            "status": "skip",
            "reason": "manual_edit (workflow result fields empty)",
            "checks": [],
        }

    checks: list[dict[str, Any]] = []

    workdir = result.get("workdir", "")
    workdir_abs = (_PROJECT_ROOT / workdir) if workdir else None
    workdir_ok = workdir_abs is not None and workdir_abs.is_dir()
    checks.append({
        "name": "workdir_exists",
        "ok": workdir_ok,
        "value": str(workdir_abs.relative_to(_PROJECT_ROOT)) if workdir_abs else None,
    })

    plan = result.get("plan", "")
    plan_abs = (_PROJECT_ROOT / plan) if plan else None
    plan_ok = plan_abs is not None and plan_abs.is_file()
    checks.append({
        "name": "plan_exists",
        "ok": plan_ok,
        "value": str(plan_abs.relative_to(_PROJECT_ROOT)) if plan_abs else None,
    })

    report = result.get("report", "")
    report_abs = (_PROJECT_ROOT / report) if report else None
    report_ok = report_abs is not None and report_abs.is_file()
    checks.append({
        "name": "report_exists",
        "ok": report_ok,
        "value": str(report_abs.relative_to(_PROJECT_ROOT)) if report_abs else None,
    })

    status_step: Optional[str] = None
    status_ok = False
    if workdir_ok and workdir_abs is not None:
        status_path = workdir_abs / "status.json"
        if status_path.is_file():
            try:
                status_data = json.loads(status_path.read_text(encoding="utf-8"))
                status_step = status_data.get("step")
                status_ok = status_step == "DONE"
            except Exception:
                status_step = "<parse_error>"
    checks.append({
        "name": "status_done",
        "ok": status_ok,
        "value": status_step,
    })

    all_ok = all(c["ok"] for c in checks)
    return {
        "status": "pass" if all_ok else "fail",
        "checks": checks,
    }


def audit_ticket(ticket_number: str, tier: int = 1) -> dict[str, Any]:
    """티켓을 tier 까지 검증하고 결과 dict 반환."""
    ticket = _load_ticket(ticket_number)
    if not ticket:
        return {
            "$schema": "audit-v1",
            "ticket_number": ticket_number,
            "audited_at": _now_iso(),
            "verdict": "fail",
            "error": "ticket_not_found",
        }

    tiers: dict[str, dict[str, Any]] = {}
    if tier >= 1:
        tiers["t1_formal"] = _t1_formal(ticket)
    if tier >= 2:
        tiers["t2_structural"] = {"status": "skip", "reason": "phase2_not_implemented"}
    if tier >= 3:
        tiers["t3_quality"] = {"status": "skip", "reason": "phase3_not_implemented"}

    statuses = [t.get("status") for t in tiers.values()]
    if "fail" in statuses:
        verdict = "fail"
    elif "pass" in statuses:
        verdict = "pass"
    else:
        verdict = "skip"

    return {
        "$schema": "audit-v1",
        "ticket_number": ticket_number,
        "ticket_status": ticket["metadata"].get("status"),
        "ticket_command": ticket["metadata"].get("command"),
        "ticket_column": ticket["_column"],
        "audited_at": _now_iso(),
        "tiers": tiers,
        "verdict": verdict,
    }


def save_result(result: dict[str, Any]) -> Path:
    """results/T-NNN-{ts}.json 으로 결과를 저장하고 절대 경로 반환."""
    results_dir = _PROJECT_ROOT / ".claude-organic" / "audit" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{result['ticket_number']}-{_now_compact()}.json"
    fpath = results_dir / fname
    fpath.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return fpath


def _format_summary(result: dict[str, Any]) -> str:
    lines: list[str] = []
    header = f"=== Audit: {result['ticket_number']}"
    if result.get("ticket_status"):
        header += f" ({result['ticket_status']}/{result.get('ticket_command', '?')})"
    header += " ==="
    lines.append(header)
    lines.append(f"Verdict: {result['verdict'].upper()}")
    if result.get("error"):
        lines.append(f"Error:   {result['error']}")

    for tier_name, tier_data in (result.get("tiers") or {}).items():
        lines.append(f"\n[{tier_name}] {tier_data.get('status', '?').upper()}")
        if tier_data.get("reason"):
            lines.append(f"  reason: {tier_data['reason']}")
        for check in tier_data.get("checks", []):
            mark = "OK " if check.get("ok") else "FAIL"
            val = check.get("value")
            val_str = f" ({val})" if val else ""
            lines.append(f"  [{mark}] {check['name']}{val_str}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Workflow Review Auditor (Phase 1: T1 정형 검증)",
    )
    parser.add_argument("ticket", help="티켓 번호 (예: T-407)")
    parser.add_argument(
        "--tier", type=int, default=1, choices=[1, 2, 3],
        help="검증 tier (1=정형, 2=+구조, 3=+품질). 기본 1.",
    )
    parser.add_argument(
        "--no-save", action="store_true",
        help="결과 파일을 저장하지 않고 stdout 만 출력",
    )
    args = parser.parse_args()

    result = audit_ticket(args.ticket, tier=args.tier)
    print(_format_summary(result))

    if not args.no_save:
        path = save_result(result)
        print(f"\nSaved: {path.relative_to(_PROJECT_ROOT)}")

    # exit code: pass=0, fail=1, skip=0 (검증 대상 아님)
    return 1 if result["verdict"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
