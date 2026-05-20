#!/usr/bin/env -S python3 -u
"""review verdict.py - Review Phase 1 rulebase automatic verification.

advisory only kanban move / status
Yes. This module is only (optional) review-verdict.json
Only the file IO and git rev-list subprocess call.

Tag:
    - feedback_no_speculative_guards_2026-05-08



based on W11 §A: finalization.py L861 hook insertion (W04 revolving pattern capture)
right after step 4 kanban move review position). phase verifier. py
VerifyResult Pattern( find git root /  check commits ahead).

12 Rule catalog (workflow.) md §3 and motivation — single truth source):
    - R-EXIST-1 ~ R-EXIST-4 : Verified output exist (4 rules)
    - R-METRIC-2, R-METRIC-3: metrics.jsonl event type saturation (2 rules)
    News R-GUARD-1 ~ R-GUARD-3 : 4 types of guard (3 rules)
    - R-PATH-1
    - R-FSM-1 : FSM Diffraction (1 rule)
    - R-WT-1: change of work tree (1 rule)

WARN/FAIL:
    - PASS = 0
    - WARN = 1~2 violation (hard-fail 0)
    (R-EXIST-1, R-METRIC-2)
    - SKIP = workflow phase

Advisory Quarantine Section 8 (plan.md §10):
    1. FAQ kanban cli 0 calls (grep available)
    2. update state.py call 0
    3. FAQs sentinel generated 0
    4. status.json 0 (read-only)
    5. FAQs metrics emit 0 (advisory flow separation)
    6. FAQs POST/PUT/DELETE 0
    7. OEM Automatic Revolving Trigger 0
    8. FAQs LLM Call 0

CLI:
    python3 review_verdict.py <registry_key> [--workdir PATH] [--project-root PATH]

    End code: always 0 - verdict results return to stdout's JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

try:
    from common import resolve_abs_work_dir, resolve_project_root
except Exception:
    resolve_abs_work_dir = None
    resolve_project_root = None


PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
SKIP = "SKIP"

HARD_FAIL_RULES: frozenset[str] = frozenset({"R-EXIST-1", "R-METRIC-2"})

SEV_WARN = "warn"
SEV_FAIL = "fail"

_RESEARCH_COMMANDS = frozenset({"research"})
_REVIEW_COMMANDS = frozenset({"review", "analyze"})

_GIT_TIMEOUT_S = 5


@dataclass
class Violation:
    rule_id: str
    severity: str
    message: str


@dataclass
class VerdictResult:
    verdict: str
    reason: str
    details: dict = field(default_factory=dict)
    violations: list[Violation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "reason": self.reason,
            "details": self.details,
            "violations": [
                {"rule_id": v.rule_id, "severity": v.severity, "message": v.message}
                for v in self.violations
            ],
        }


RuleFn = Callable[[Path, dict], Optional[Violation]]


def compute_review_verdict(
    registry_key: str,
    project_root: Optional[Path] = None,
    workdir: Optional[Path] = None,
) -> VerdictResult:
    """13 After verifying the rule, a verdict is returned (advisory only)."""
    if workdir is None:
        workdir = _resolve_workdir(registry_key, project_root)

    if workdir is None or not workdir.is_dir():
        return VerdictResult(
            verdict=SKIP,
            reason=f"workdir not found: registry_key={registry_key}",
            details={"registry_key": registry_key},
        )

    fsm_ctx = _read_fsm_context(workdir)
    phase = fsm_ctx.get("workflow_phase")
    if phase not in ("DONE", "FAILED"):
        return VerdictResult(
            verdict=SKIP,
            reason=f"workflow_phase={phase!r} not in DONE/FAILED - finalize not completed",
            details={"workflow_phase": phase, "registry_key": registry_key},
        )

    command = _read_command(workdir)
    cmd_lower = (command or "").strip().lower()

    ctx: dict = {
        "registry_key": registry_key,
        "command": cmd_lower,
        "workflow_phase": phase,
        "metrics_lines": _read_metrics_lines(workdir),
        "context_json": _read_context_json(workdir),
    }

    rule_fns: list[tuple[str, RuleFn]] = [
        ("R-EXIST-1", _check_exist_1),
        ("R-EXIST-2", _check_exist_2),
        ("R-EXIST-3", _check_exist_3),
        ("R-EXIST-4", _check_exist_4),
        ("R-METRIC-2", _check_metric_2),
        ("R-METRIC-3", _check_metric_3),
        ("R-GUARD-1", _check_guard_1),
        ("R-GUARD-2", _check_guard_2),
        ("R-GUARD-3", _check_guard_3),
        ("R-PATH-1", _check_path_1),
        ("R-FSM-1", _check_fsm_1),
        ("R-WT-1", _check_wt_1),
    ]

    violations: list[Violation] = []
    for _rule_id, fn in rule_fns:
        try:
            v = fn(workdir, ctx)
        except Exception as exc:
            v = Violation(
                rule_id=_rule_id,
                severity=SEV_WARN,
                message=f"rule check raised: {exc}",
            )
        if v is not None:
            violations.append(v)

    return _resolve_verdict(violations, ctx)


def _resolve_verdict(violations: list[Violation], ctx: dict) -> VerdictResult:
    """List of violations -> verdict branch.

    PASS: 0 items. WARN: 1~2 times (not hard-fail). FAIL: 3+ guns or hard-fail included.
    """
    n = len(violations)
    hard_fail_hits = [v for v in violations if v.rule_id in HARD_FAIL_RULES]

    if n == 0:
        verdict = PASS
        reason = "13 rules all passed"
    elif hard_fail_hits:
        verdict = FAIL
        reason = (
            "hard-fail rule violated: "
            + ",".join(v.rule_id for v in hard_fail_hits)
        )
    elif n >= 3:
        verdict = FAIL
        reason = f"{n} rule violations (>= 3)"
    else:
        verdict = WARN
        reason = f"{n} rule violation(s)"

    return VerdictResult(
        verdict=verdict,
        reason=reason,
        details={
            "registry_key": ctx.get("registry_key"),
            "command": ctx.get("command"),
            "workflow_phase": ctx.get("workflow_phase"),
            "violations_total": n,
            "hard_fail_count": len(hard_fail_hits),
        },
        violations=violations,
    )


def _check_exist_1(workdir: Path, ctx: dict) -> Optional[Violation]:
    """R-EXIST-1: report.md exists + size > 0 (hard-fail)."""
    p = workdir / "report.md"
    if not p.is_file():
        return Violation(
            rule_id="R-EXIST-1",
            severity=SEV_FAIL,
            message=f"report.md not found at {p}",
        )
    try:
        if p.stat().st_size == 0:
            return Violation(
                rule_id="R-EXIST-1",
                severity=SEV_FAIL,
                message="report.md exists but empty (size=0)",
            )
    except OSError as exc:
        return Violation(
            rule_id="R-EXIST-1",
            severity=SEV_FAIL,
            message=f"report.md stat failed: {exc}",
        )
    return None


def _check_exist_2(workdir: Path, ctx: dict) -> Optional[Violation]:
    """R-EXIST-2: plan.md exists + size > 0 (research command is SKIP)."""
    if ctx.get("command") in _RESEARCH_COMMANDS:
        return None
    p = workdir / "plan.md"
    if not p.is_file():
        return Violation(
            rule_id="R-EXIST-2",
            severity=SEV_WARN,
            message=f"plan.md not found at {p}",
        )
    try:
        if p.stat().st_size == 0:
            return Violation(
                rule_id="R-EXIST-2",
                severity=SEV_WARN,
                message="plan.md exists but empty (size=0)",
            )
    except OSError as exc:
        return Violation(
            rule_id="R-EXIST-2",
            severity=SEV_WARN,
            message=f"plan.md stat failed: {exc}",
        )
    return None


def _check_exist_3(workdir: Path, ctx: dict) -> Optional[Violation]:
    """R-EXIST-3: status.json exists + JSON parse + workflow_phase key."""
    p = workdir / "status.json"
    if not p.is_file():
        return Violation(
            rule_id="R-EXIST-3",
            severity=SEV_WARN,
            message=f"status.json not found at {p}",
        )
    try:
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return Violation(
            rule_id="R-EXIST-3",
            severity=SEV_WARN,
            message=f"status.json parse failed: {exc}",
        )
    if not isinstance(data, dict) or "workflow_phase" not in data:
        return Violation(
            rule_id="R-EXIST-3",
            severity=SEV_WARN,
            message="status.json missing 'workflow_phase' key",
        )
    return None


def _check_exist_4(workdir: Path, ctx: dict) -> Optional[Violation]:
    """R-EXIST-4: metrics.jsonl exists + number of lines >= 1."""
    p = workdir / "metrics.jsonl"
    if not p.is_file():
        return Violation(
            rule_id="R-EXIST-4",
            severity=SEV_WARN,
            message=f"metrics.jsonl not found at {p}",
        )
    lines = ctx.get("metrics_lines") or []
    if len(lines) < 1:
        return Violation(
            rule_id="R-EXIST-4",
            severity=SEV_WARN,
            message="metrics.jsonl is empty (line_count=0)",
        )
    return None


def _check_metric_2(workdir: Path, ctx: dict) -> Optional[Violation]:
    """R-METRIC-2: last step.end{step=DONE}.outcome =="ok" (hard-fail).

    DONE step.end 0 results
    """
    lines = ctx.get("metrics_lines") or []
    last_done_outcome: Optional[str] = None
    for ev in lines:
        if ev.get("event_type") != "step.end":
            continue
        payload = ev.get("payload") or {}
        if payload.get("step") != "DONE":
            continue
        last_done_outcome = payload.get("outcome")
    if last_done_outcome is None:
        return Violation(
            rule_id="R-METRIC-2",
            severity=SEV_FAIL,
            message="step.end{step=DONE} not emitted",
        )
    if last_done_outcome != "ok":
        return Violation(
            rule_id="R-METRIC-2",
            severity=SEV_FAIL,
            message=f"step.end DONE outcome={last_done_outcome!r} != 'ok'",
        )
    return None


def _check_metric_3(workdir: Path, ctx: dict) -> Optional[Violation]:
    """R-METRIC-3: 0 tool.deny events."""
    lines = ctx.get("metrics_lines") or []
    deny_count = sum(1 for ev in lines if ev.get("event_type") == "tool.deny")
    if deny_count >= 1:
        return Violation(
            rule_id="R-METRIC-3",
            severity=SEV_WARN,
            message=f"tool.deny events emitted: count={deny_count}",
        )
    return None


def _check_guard_1(workdir: Path, ctx: dict) -> Optional[Violation]:
    """R-GUARD-1: .context.json:worktree.enabled == true."""
    cj = ctx.get("context_json") or {}
    wt = cj.get("worktree") if isinstance(cj, dict) else None
    if not isinstance(wt, dict) or wt.get("enabled") is not True:
        return Violation(
            rule_id="R-GUARD-1",
            severity=SEV_WARN,
            message="worktree.enabled != true (HOOK_WORKTREE_PATH_GUARD guard disabled)",
        )
    return None


def _check_guard_2(workdir: Path, ctx: dict) -> Optional[Violation]:
    """R-GUARD-2: .context.json:worktree.featureBranch exists + git branch --list matching."""
    cj = ctx.get("context_json") or {}
    wt = cj.get("worktree") if isinstance(cj, dict) else None
    fb = wt.get("featureBranch") if isinstance(wt, dict) else None
    if not isinstance(fb, str) or not fb.strip():
        return Violation(
            rule_id="R-GUARD-2",
            severity=SEV_WARN,
            message="worktree.featureBranch missing",
        )

    git_root = _find_git_root(str(workdir))
    if git_root is None:
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", git_root, "branch", "--list", fb],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if proc.returncode != 0:
        return None
    if not any(line.strip().lstrip("* ").strip() == fb for line in proc.stdout.splitlines()):
        return Violation(
            rule_id="R-GUARD-2",
            severity=SEV_WARN,
            message=f"featureBranch={fb!r} not found in git branch --list",
        )
    return None


def _check_guard_3(workdir: Path, ctx: dict) -> Optional[Violation]:
    """R-GUARD-3: 0 regression.pattern events in metrics.jsonl."""
    lines = ctx.get("metrics_lines") or []
    reg_count = sum(
        1 for ev in lines if ev.get("event_type") == "regression.pattern"
    )
    if reg_count >= 1:
        kinds: list[str] = []
        for ev in lines:
            if ev.get("event_type") == "regression.pattern":
                k = (ev.get("payload") or {}).get("kind")
                if isinstance(k, str):
                    kinds.append(k)
        return Violation(
            rule_id="R-GUARD-3",
            severity=SEV_WARN,
            message=f"regression.pattern emitted: count={reg_count} kinds={kinds}",
        )
    return None


_PLAN_MD_TOKEN_PATTERN = re.compile(r"\bplan\.md\b")


def _check_path_1(workdir: Path, ctx: dict) -> Optional[Violation]:
    """R-PATH-1: report.md body plan.md link matching (research, etc.)."""
    if ctx.get("command") in _RESEARCH_COMMANDS:
        return None
    rep = workdir / "report.md"
    if not rep.is_file():
        return None
    try:
        text = rep.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return Violation(
            rule_id="R-PATH-1",
            severity=SEV_WARN,
            message=f"report.md read failed: {exc}",
        )
    if not _PLAN_MD_TOKEN_PATTERN.search(text):
        return None
    plan = workdir / "plan.md"
    if not plan.is_file():
        return Violation(
            rule_id="R-PATH-1",
            severity=SEV_WARN,
            message=(
                "report.md references 'plan.md' but plan.md not found "
                f"at {plan}"
            ),
        )
    return None


def _check_fsm_1(workdir: Path, ctx: dict) -> Optional[Violation]:
    """R-FSM-1: status.json workflow_phase in {DONE, FAILED}."""
    phase = ctx.get("workflow_phase")
    if phase not in ("DONE", "FAILED"):
        return Violation(
            rule_id="R-FSM-1",
            severity=SEV_WARN,
            message=f"workflow_phase={phase!r} not in DONE/FAILED",
        )
    return None


def _check_wt_1(workdir: Path, ctx: dict) -> Optional[Violation]:
    """R-WT-1: git rev-list --count develop..HEAD >= 1 (research/review SKIP)."""
    cmd = ctx.get("command")
    if cmd in _RESEARCH_COMMANDS or cmd in _REVIEW_COMMANDS:
        return None

    cj = ctx.get("context_json") or {}
    wt = cj.get("worktree") if isinstance(cj, dict) else None
    wt_path: Optional[str] = None
    if isinstance(wt, dict):
        cand = wt.get("absPath") or wt.get("path")
        if isinstance(cand, str) and cand.strip():
            if os.path.isabs(cand):
                wt_path = cand
            elif resolve_project_root is not None:
                try:
                    wt_path = os.path.join(resolve_project_root(), cand)
                except Exception:
                    wt_path = None

    git_root = wt_path if wt_path and os.path.isdir(wt_path) else _find_git_root(
        str(workdir)
    )
    if git_root is None:
        return None

    try:
        proc = subprocess.run(
            ["git", "-C", git_root, "rev-list", "--count", "develop..HEAD"],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if proc.returncode != 0:
        return None
    try:
        ahead = int(proc.stdout.strip())
    except ValueError:
        return None
    if ahead < 1:
        return Violation(
            rule_id="R-WT-1",
            severity=SEV_WARN,
            message=f"develop..HEAD commits = {ahead} (missing worker commit)",
        )
    return None


def _resolve_workdir(
    registry_key: str, project_root: Optional[Path]
) -> Optional[Path]:
    """registry_key -> workdir absolute Path. Utilizing common.resolve_abs_work_dir."""
    if resolve_abs_work_dir is None:
        root = project_root or Path.cwd()
        cand = Path(root) / ".agent-factory" / "runs" / registry_key
        return cand if cand.is_dir() else None
    try:
        pr_str = str(project_root) if project_root is not None else None
        abs_dir = resolve_abs_work_dir(registry_key, project_root=pr_str)
    except Exception:
        return None
    return Path(abs_dir) if abs_dir else None


def _read_fsm_context(workdir: Path) -> dict:
    """Read FSM context such as workflow_phase in status.json."""
    p = workdir / "status.json"
    if not p.is_file():
        return {}
    try:
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_command(workdir: Path) -> Optional[str]:
    """Extract command from init-result.json or .context.json."""
    for fname in ("init-result.json", ".context.json"):
        p = workdir / fname
        if not p.is_file():
            continue
        try:
            with p.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            cmd = data.get("command")
            if isinstance(cmd, str) and cmd.strip():
                return cmd
    return None


def _read_context_json(workdir: Path) -> dict:
    """Parsing .context.json (empty dict on failure)."""
    p = workdir / ".context.json"
    if not p.is_file():
        return {}
    try:
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_metrics_lines(workdir: Path) -> list[dict]:
    """Parse metrics.jsonl line by line (skip failed lines)."""
    p = workdir / "metrics.jsonl"
    if not p.is_file():
        return []
    out: list[dict] = []
    try:
        with p.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    out.append(obj)
    except OSError:
        return []
    return out


def _find_git_root(start_dir: str) -> Optional[str]:
    """Navigate .git directories/files starting from start_dir upwards."""
    current = os.path.abspath(start_dir)
    while True:
        marker = os.path.join(current, ".git")
        if os.path.isdir(marker) or os.path.isfile(marker):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point - call flow-review-verdict wrapper.

    Output: JSON dump (stdout) in VerdictResult.to dict().
    End code: always 0 (advisory) - judged by verdict itself.
    """
    parser = argparse.ArgumentParser(
        prog="review_verdict",
        description="Review stage 1st rule base automatic verification (advisory)",
    )
    parser.add_argument(
        "registry_key",
        help="Workflow registry key (e.g. 20260510-200712)",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=None,
        help="Specify workdir directly (bypass registry_key interpretation)",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Specify project root (default: automatic interpretation)",
    )
    args = parser.parse_args(argv)

    result = compute_review_verdict(
        registry_key=args.registry_key,
        project_root=args.project_root,
        workdir=args.workdir,
    )
    json.dump(
        result.to_dict(),
        sys.stdout,
        ensure_ascii=False,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
