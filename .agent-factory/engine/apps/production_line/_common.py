"""Production-line utilities: WorkRequest context, status I/O, conveyor wrapper, paths.

SPEC.md §13 (directory) + §4 (output) + §3.4 (retry limit) + §8 (claude -p) absorption.
No LLM calls. Rule base decision only.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from engine.core.reporting.templates import load_report_template
from engine.core.workflows import (
    PRODUCTION_LINE_STEP_TO_STAGE,
    assert_valid_stage_transition,
    canonicalize_production_line_step,
    stage_from_production_line_step,
)


def _resolve_project_root() -> Path:
    """Parent of git common dir = main worktree root. Even if it is called from the work tree, it points to the main side."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            check=True,
        )
        git_common = Path(result.stdout.strip())
        if not git_common.is_absolute():
            git_common = (Path(__file__).resolve().parent / git_common).resolve()
        return git_common.parent
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path(__file__).resolve().parents[3]


PROJECT_ROOT = _resolve_project_root()
RUNS_DIR = PROJECT_ROOT / ".agent-factory" / "runs"
CONVEYOR_BIN = PROJECT_ROOT / ".agent-factory" / "bin" / "flow-conveyor"
PRODUCTION_LINE_DIR = Path(__file__).resolve().parent
PRODUCTION_LINE_ENGINE_DIR = PRODUCTION_LINE_DIR  # compatibility alias
PROMPTS_DIR = PRODUCTION_LINE_DIR / "prompts"
TEMPLATES_DIR = PRODUCTION_LINE_DIR / "templates"


WORKFLOW_STEPS = tuple(PRODUCTION_LINE_STEP_TO_STAGE)
TERMINAL_STEPS = ("DONE", "FAILED")


def load_prompt(name: str) -> str:
    """SPEC.md §8.3 — Externalization of system prompt for each step (matching less than 10KB)."""
    path = PROMPTS_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8")


def load_template(name: str) -> str:
    """driver fill template (retry_prompt / summary / failure)."""
    if name == "report.html":
        return load_report_template()
    path = TEMPLATES_DIR / name
    return path.read_text(encoding="utf-8")


# SPEC.md §3.4 — Retry limit per step (default)
# Can be overridden with the V2_RETRY_<STEP> environment variable in .agent-factory/.settings.
_N_MAX_DEFAULT: dict[str, int] = {
    "INIT": 0,
    "PLAN": 2,
    "WORK": 3,
    "VALIDATE": 1,
    "REPORT": 2,
    "DONE": 0,
}


def _load_settings() -> dict[str, str]:
    """Read `.agent-factory/.settings` (KEY=value, # comment) as a dict.

    Silent skip for file non-existence or parsing failure — the driver guarantees operation as default.
    """
    settings_path = PROJECT_ROOT / ".agent-factory" / ".settings"
    if not settings_path.is_file():
        return {}
    result: dict[str, str] = {}
    try:
        for raw in settings_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    except (OSError, UnicodeDecodeError):
        return {}
    return result


def get_n_max(step: str) -> int:
    """Returns the retry limit for each step. `V2_RETRY_<STEP>` env override takes priority.

    Priority: os.environ > .settings > _N_MAX_DEFAULT > 0.
    """
    env_key = f"V2_RETRY_{step.upper()}"
    raw = os.environ.get(env_key) or _load_settings().get(env_key)
    if raw is not None:
        try:
            v = int(raw)
            if v >= 0:
                return v
        except ValueError:
            pass
    return _N_MAX_DEFAULT.get(step, 0)


# Backward compatibility — Preserve N_MAX_BY_STEP.get(step, 0) call from old code (env override not reflected).
# It is recommended that new code use get_n_max(step).
N_MAX_BY_STEP = _N_MAX_DEFAULT


# T-506 P1 — Parallel spawn limit / SPEC §3.4 new
_MAX_PARALLEL_DEFAULT = 4

# T-506 P4 — Failure Handling Policy / SPEC §3.4 New
_FAIL_POLICY_DEFAULT = "fail_fast"
_FAIL_POLICY_VALID = ("fail_fast", "fail_tolerant")


def get_max_parallel() -> int:
    """T-506 P1 — Same topo level simultaneous spawn limit return.

    Priority: os.environ.V2_MAX_PARALLEL > .settings.V2_MAX_PARALLEL > 4.
    When entering a negative number / 0 / non-number, default 4 fallback (graceful).
    """
    raw = os.environ.get("V2_MAX_PARALLEL")
    if raw is None:
        raw = _load_settings().get("V2_MAX_PARALLEL")
    if raw is None:
        return _MAX_PARALLEL_DEFAULT
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return _MAX_PARALLEL_DEFAULT
    if v <= 0:
        return _MAX_PARALLEL_DEFAULT
    return v


def get_fail_policy() -> str:
    """T-506 P4 — Returns parallel spawn failure handling policy.

    Priority: os.environ.V2_FAIL_POLICY > .settings.V2_FAIL_POLICY > 'fail_fast'.
    Valid values: 'fail_fast' | 'fail_tolerant'. For other inputs, default 'fail_fast'.
    """
    raw = os.environ.get("V2_FAIL_POLICY")
    if raw is None:
        raw = _load_settings().get("V2_FAIL_POLICY")
    if raw is None:
        return _FAIL_POLICY_DEFAULT
    value = str(raw).strip().lower()
    if value in _FAIL_POLICY_VALID:
        return value
    return _FAIL_POLICY_DEFAULT


# SPEC.md §8.1 — timeout (seconds) per step
STEP_TIMEOUT_BY_STEP: dict[str, int] = {
    "PLAN": 300,        # 5min
    "WORK": 1800,       # 30min
    "VALIDATE": 180,    # 3min
    "REPORT": 600,      # 10min
}


@dataclass
class WorkflowContext:
    """1 cycle state — driver in-process state.

    SPEC.md §4 output model + §7.2 driver.py pseudocode based.
    """

    work_request_no: str                          # "WR-489"
    registry_key: str                       # "20260514-230000"
    work_dir: Path                          # .agent-factory/runs/<registry_key>/
    command: str = "implement"              # implement | research | review | test
    mode: str = "multi"                     # single | multi (plan.md frontmatter makes the final decision)
    current_step: str = "NONE"
    feature_branch: str | None = None       # Worktree Guard (T-411 remnants, preserved)
    worktree_path: Path | None = None       # SPEC §9.1.1 (Stage 3-D) + §0.1 (Stage 3-E auto_commit)
    title: str = ""                         # WorkRequest title (for auto_commit message template)
    session_ids: dict[str, str] = field(default_factory=dict)  # Step|Phase → session_id
    wf_session_id: str | None = None        # Stage 3-B — board side workflow_registry mapping ID

    def status_json_path(self) -> Path:
        return self.work_dir / "status.json"

    def context_json_path(self) -> Path:
        return self.work_dir / ".context.json"

    def metrics_jsonl_path(self) -> Path:
        return self.work_dir / "metrics.jsonl"

    def workflow_log_path(self) -> Path:
        return self.work_dir / "workflow.log"

    def plan_dir(self) -> Path:
        """T-504 — `plan/` directory (PLAN output area)."""
        return self.work_dir / "plan"

    def plan_md_path(self) -> Path:
        """T-504 cutover — `plan/plan.md` (LLM↔LLM natural language body, discarding old root plan.md)."""
        return self.plan_dir() / "plan.md"

    def plan_json_path(self) -> Path:
        """New T-504 — `plan/plan.json` (driver deterministic parsing target, SSOT)."""
        return self.plan_dir() / "plan.json"

    def work_dir_phase_md(self, phase_id: str) -> Path:
        """flat path — backward compat (T-503 migration hold period)."""
        return self.work_dir / "work" / f"{phase_id}.md"

    def work_phase_dir(self, phase_id: str) -> Path:
        """T-503 directory nesting — work/<phase>/."""
        return self.work_dir / "work" / phase_id

    def work_phase_w_md(self, phase_id: str, worker_idx: int = 1) -> Path:
        """T-503 directory nesting — work/<phase>/W<n>.md (workers ≥ 1)."""
        return self.work_phase_dir(phase_id) / f"W{worker_idx}.md"

    def work_phase_md_resolved(self, phase_id: str) -> Path:
        """T-503 — Tries both flat and nested paths, returning the one that exists.

        Priority: nested (work/<phase>/W1.md) > flat (work/<phase>.md). If both do not exist, return the nested default path (can be used as write-target).
        """
        nested = self.work_phase_w_md(phase_id, 1)
        if nested.exists():
            return nested
        flat = self.work_dir_phase_md(phase_id)
        if flat.exists():
            return flat
        return nested

    def validate_dir(self) -> Path:
        """T-503 — validate/ directory."""
        return self.work_dir / "validate"

    def validate_report_md_path(self) -> Path:
        """validate-report.md — flat (backward compat, T-503 migration hold)."""
        return self.work_dir / "validate-report.md"

    def validate_report_md_nested_path(self) -> Path:
        """T-503 — validate/report.md (directory nesting)."""
        return self.validate_dir() / "report.md"

    def validate_rules_json_path(self) -> Path:
        """validate-rules.json — flat (backward compat, T-503 migration hold)."""
        return self.work_dir / "validate-rules.json"

    def validate_rules_json_nested_path(self) -> Path:
        """T-503 — validate/rules.json (directory nesting)."""
        return self.validate_dir() / "rules.json"

    def validate_code_json_path(self) -> Path:
        """New T-503 — validate/code.json (driver `_verify_code.py` output, implement only)."""
        return self.validate_dir() / "code.json"

    def validate_verdict_json_path(self) -> Path:
        """M9 — VERIFY step structured verdict (`validate/verdict.json`)."""
        return self.validate_dir() / "verdict.json"

    def report_manifest_json_path(self) -> Path:
        """M9 — REPORT stage manifest (`report.json`)."""
        return self.work_dir / "report.json"

    def final_verdict_json_path(self) -> Path:
        """M9 — COMPLETE gate final verdict (`final-verdict.json`)."""
        return self.work_dir / "final-verdict.json"

    def report_md_path(self) -> Path:
        """T-504 cutover — `report.html` (human readable, obsolete old report.md).

        The function name is backward compat alias (REPORT step + R-EXIST-1 caller preservation).
        """
        return self.work_dir / "report.html"

    def report_html_path(self) -> Path:
        """T-504 — `report.html` explicit path (human readable, HTML template + placeholder)."""
        return self.work_dir / "report.html"

    def user_prompt_path(self) -> Path:
        return self.work_dir / "user_prompt.txt"

    def summary_txt_path(self) -> Path:
        return self.work_dir / "summary.txt"

    def usage_json_path(self) -> Path:
        return self.work_dir / "usage.json"

    def failure_md_path(self) -> Path:
        return self.work_dir / "failure.md"

    def metadata_json_path(self) -> Path:
        """T-503 — metadata.json (absorbs old .context.json + status.json + summary.txt + failure)."""
        return self.work_dir / "metadata.json"


def new_registry_key(now: datetime | None = None) -> str:
    """SPEC.md §4 — registryKey number. v1 compatible format (YYYYMMDD-HHMMSS)."""
    moment = now or datetime.now()
    return moment.strftime("%Y%m%d-%H%M%S")


def make_work_dir(registry_key: str) -> Path:
    work_dir = RUNS_DIR / registry_key
    (work_dir / "work").mkdir(parents=True, exist_ok=True)
    return work_dir


def read_status(ctx: WorkflowContext) -> dict[str, Any]:
    path = ctx.status_json_path()
    if not path.exists():
        return {"workflow_step": "NONE", "transitions": []}
    status = json.loads(path.read_text(encoding="utf-8"))
    if "workflow_step" not in status and "workflow_stage" in status:
        status["workflow_step"] = canonicalize_production_line_step(str(status["workflow_stage"]))
    return status


def write_status(ctx: WorkflowContext, status: dict[str, Any]) -> None:
    ctx.status_json_path().write_text(
        json.dumps(status, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def update_step(ctx: WorkflowContext, prev: str, nxt: str, *, note: str = "") -> None:
    """workflow_step transition — Record transition in status.json.

    SPEC.md §3.3 — Driver decides to transition to rule base.
    """
    prev = canonicalize_production_line_step(prev)
    nxt = canonicalize_production_line_step(nxt)
    prev_stage = stage_from_production_line_step(prev)
    next_stage = stage_from_production_line_step(nxt)
    if prev != "NONE":
        assert_valid_stage_transition(prev_stage, next_stage)
    elif nxt not in {"INIT", "PLAN", "FAILED"}:
        raise ValueError("illegal workflow step transition NONE -> " + nxt)
    status = read_status(ctx)
    status["workflow_step"] = nxt
    status["workflow_stage"] = next_stage.value
    status.setdefault("transitions", []).append(
        {
            "from": prev,
            "to": nxt,
            "from_stage": prev_stage.value,
            "to_stage": next_stage.value,
            "ts": datetime.now().isoformat(timespec="seconds"),
            "note": note,
        }
    )
    write_status(ctx, status)
    ctx.current_step = nxt


def read_context(ctx: WorkflowContext) -> dict[str, Any]:
    path = ctx.context_json_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_context(ctx: WorkflowContext) -> None:
    """Serialize ctx state to `.context.json` — feature_branch / mode / command etc."""
    payload = {
        "schema_version": 1,
        "work_request_no": ctx.work_request_no,
        "registry_key": ctx.registry_key,
        "command": ctx.command,
        "mode": ctx.mode,
        "feature_branch": ctx.feature_branch,
        "worktree_path": str(ctx.worktree_path) if ctx.worktree_path else None,
        "title": ctx.title,
        "session_ids": dict(ctx.session_ids),
        "wf_session_id": ctx.wf_session_id,
        "engine_version": "production_line",
    }
    ctx.context_json_path().write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def conveyor_show(work_request_no: str) -> str:
    """`.agent-factory/bin/flow-conveyor show WR-NNN` — Return stdout."""
    result = subprocess.run(
        [str(CONVEYOR_BIN), "show", work_request_no],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        check=False,
    )
    return result.stdout


def conveyor_move(work_request_no: str, target: str) -> int:
    """`flow-conveyor move WR-NNN <target>` — Draft/Accepted/Executing/Verifying/Complete.

    INIT moves Accepted to Executing; DONE moves Executing to Verifying.
    """
    result = subprocess.run(
        [str(CONVEYOR_BIN), "move", work_request_no, target],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        check=False,
    )
    return result.returncode


def append_log(ctx: WorkflowContext, line: str) -> None:
    """Add line to workflow.log. Diagnostic trace."""
    log_path = ctx.workflow_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"[{ts}] {line}\n")


def write_metadata(
    ctx: WorkflowContext,
    *,
    finalized_at: str | None = None,
    failure_reason: str | None = None,
) -> Path:
    """T-503 — `metadata.json` integrated writer.

    Old output 4 files (`.context.json` + `status.json` + `summary.txt` + `failure.md`)
    stuffed into a single JSON. Call a function that only sees new cycles. Consistent output from one driver writer.

    Schema:
        {
          "schema_version": 1,
          "work_request_no": "WR-NNN",
          "registry_key": "...",
          "command": "implement",
          "mode": "multi",
          "feature_branch": "feat/...",
          "worktree_path": "...",
          "title": "...",
          "wf_session_id": "...",
          "engine_version": "production_line",
          "session_ids": {"wf-T-PLAN": "...", ...},
          "workflow_step": "DONE",
          "transitions": [{"from":"INIT","to":"PLAN","ts":"..."}, ...],
          "finalized_at": "2026-05-18T...",   # Fill only in DONE step (replaces old summary.txt)
          "failure": {"reason": "...", "ts": "..."} | null,  # FAILED step only (replaces old failure.md)
        }
    """
    status = read_status(ctx)
    payload = {
        "schema_version": 1,
        "work_request_no": ctx.work_request_no,
        "registry_key": ctx.registry_key,
        "command": ctx.command,
        "mode": ctx.mode,
        "feature_branch": ctx.feature_branch,
        "worktree_path": str(ctx.worktree_path) if ctx.worktree_path else None,
        "title": ctx.title,
        "wf_session_id": ctx.wf_session_id,
        "engine_version": "production_line",
        "session_ids": dict(ctx.session_ids),
        "workflow_step": status.get("workflow_step", ctx.current_step),
        "transitions": status.get("transitions", []),
        "finalized_at": finalized_at,
        "failure": (
            {"reason": failure_reason, "ts": datetime.now().isoformat(timespec="seconds")}
            if failure_reason
            else None
        ),
    }
    path = ctx.metadata_json_path()
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def read_metadata(ctx: WorkflowContext) -> dict[str, Any]:
    """T-503 — `metadata.json` reader. If not present, `{}` is returned."""
    path = ctx.metadata_json_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def auto_commit(ctx: WorkflowContext) -> int:
    """SPEC §0.1 (Stage 3-E) — worker output determinism commit.

    The driver is called immediately after the WORK Step ends. 0 LLM mandates.

    movement:
      1. ctx.worktree_path is None (worktree-less or init regression) → skip, return 0
      2. `git -C <wt> add -A` — worker output + work/*.md all stage
      3. `git -C <wt> diff --cached --quiet` — If there are 0 changes, returncode 0 → skip, return 0
      4. Deterministic message template `git -C <wt> commit -m <msg>` → returncode is returned

    Message template: "feat(<work_request>): <title> [production-line auto-commit]"
    """
    if ctx.worktree_path is None:
        append_log(ctx, "[AUTO-COMMIT] worktree-less — skip")
        return 0
    wt = str(ctx.worktree_path)
    if not Path(wt).is_dir():
        append_log(ctx, f"[AUTO-COMMIT] worktree path does not exist ({wt}) — skip")
        return 0
    # 1. add -A
    add = subprocess.run(
        ["git", "-C", wt, "add", "-A"],
        capture_output=True,
        text=True,
        check=False,
    )
    if add.returncode != 0:
        append_log(ctx, f"[AUTO-COMMIT] git add failed rc={add.returncode}: {add.stderr.strip()[:200]}")
        return add.returncode
    # 2. Detect staged changes
    diff = subprocess.run(
        ["git", "-C", wt, "diff", "--cached", "--quiet"],
        capture_output=True,
        text=True,
        check=False,
    )
    if diff.returncode == 0:
        append_log(ctx, "[AUTO-COMMIT] 0 staged changes — skip")
        return 0
    # 3. commit message determinism template
    title = ctx.title or "(no title)"
    msg = f"feat({ctx.work_request_no}): {title} [production-line auto-commit]"
    commit = subprocess.run(
        ["git", "-C", wt, "commit", "-m", msg],
        capture_output=True,
        text=True,
        check=False,
    )
    if commit.returncode != 0:
        append_log(
            ctx,
            f"[AUTO-COMMIT] git commit failed rc={commit.returncode}:"
            f"{commit.stderr.strip()[:200]}",
        )
        return commit.returncode
    append_log(ctx, f"[AUTO-COMMIT] commit OK — {msg}")
    return 0
