"""v2 common utilities — WorkflowContext, status I/O, kanban CLI wrapper, paths.

SPEC.md §13 (디렉터리) + §4 (산출물) + §3.4 (재시도 한도) + §8 (claude -p) 흡수.
LLM 호출 없음. 룰베이스 결정만.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNS_DIR = PROJECT_ROOT / ".claude-organic" / "runs"
KANBAN_BIN = PROJECT_ROOT / ".claude-organic" / "bin" / "flow-kanban"
ENGINE_V2_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = ENGINE_V2_DIR / "prompts"
TEMPLATES_DIR = ENGINE_V2_DIR / "templates"


WORKFLOW_STEPS = ("NONE", "INIT", "PLAN", "WORK", "VALIDATE", "REPORT", "DONE", "FAILED")
TERMINAL_STEPS = ("DONE", "FAILED")


def load_prompt(name: str) -> str:
    """SPEC.md §8.3 — Step 별 system prompt 외부화 (10KB 이하 정합)."""
    path = PROMPTS_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8")


def load_template(name: str) -> str:
    """driver fill template (retry_prompt / summary / failure)."""
    path = TEMPLATES_DIR / name
    return path.read_text(encoding="utf-8")


# SPEC.md §3.4 — Step 별 재시도 한도
N_MAX_BY_STEP: dict[str, int] = {
    "INIT": 0,
    "PLAN": 2,
    "WORK": 3,
    "VALIDATE": 1,
    "REPORT": 2,
    "DONE": 0,
}


# SPEC.md §8.1 — Step 별 timeout (초)
STEP_TIMEOUT_BY_STEP: dict[str, int] = {
    "PLAN": 300,        # 5min
    "WORK": 1800,       # 30min
    "VALIDATE": 180,    # 3min
    "REPORT": 600,      # 10min
}


@dataclass
class WorkflowContext:
    """1 사이클 상태 — driver in-process state.

    SPEC.md §4 산출물 모델 + §7.2 driver.py 의사 코드 기반.
    """

    ticket_no: str                          # "T-489"
    registry_key: str                       # "20260514-230000"
    work_dir: Path                          # .claude-organic/runs/<registry_key>/
    command: str = "implement"              # implement | research | review | test
    mode: str = "multi"                     # single | multi (plan.md frontmatter 가 최종 결정)
    current_step: str = "NONE"
    feature_branch: str | None = None       # 워크트리 가드 (T-411 잔존, 보존)
    session_ids: dict[str, str] = field(default_factory=dict)  # Step|Phase → session_id

    def status_json_path(self) -> Path:
        return self.work_dir / "status.json"

    def context_json_path(self) -> Path:
        return self.work_dir / ".context.json"

    def metrics_jsonl_path(self) -> Path:
        return self.work_dir / "metrics.jsonl"

    def workflow_log_path(self) -> Path:
        return self.work_dir / "workflow.log"

    def plan_md_path(self) -> Path:
        return self.work_dir / "plan.md"

    def work_dir_phase_md(self, phase_id: str) -> Path:
        return self.work_dir / "work" / f"{phase_id}.md"

    def validate_report_md_path(self) -> Path:
        return self.work_dir / "validate-report.md"

    def validate_rules_json_path(self) -> Path:
        return self.work_dir / "validate-rules.json"

    def report_md_path(self) -> Path:
        return self.work_dir / "report.md"

    def user_prompt_path(self) -> Path:
        return self.work_dir / "user_prompt.txt"

    def summary_txt_path(self) -> Path:
        return self.work_dir / "summary.txt"

    def usage_json_path(self) -> Path:
        return self.work_dir / "usage.json"

    def failure_md_path(self) -> Path:
        return self.work_dir / "failure.md"


def new_registry_key(now: datetime | None = None) -> str:
    """SPEC.md §4 — registryKey 채번. v1 호환 형식 (YYYYMMDD-HHMMSS)."""
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
    return json.loads(path.read_text(encoding="utf-8"))


def write_status(ctx: WorkflowContext, status: dict[str, Any]) -> None:
    ctx.status_json_path().write_text(
        json.dumps(status, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def update_step(ctx: WorkflowContext, prev: str, nxt: str, *, note: str = "") -> None:
    """workflow_step 전이 — status.json 에 transition 기록.

    SPEC.md §3.3 — driver 가 룰베이스로 전이 결정.
    """
    if nxt not in WORKFLOW_STEPS:
        raise ValueError(f"unknown step: {nxt}")
    status = read_status(ctx)
    status["workflow_step"] = nxt
    status.setdefault("transitions", []).append(
        {
            "from": prev,
            "to": nxt,
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
    """`.context.json` 에 ctx 상태 직렬화 — feature_branch / mode / command 등."""
    payload = {
        "schema_version": 1,
        "ticket_no": ctx.ticket_no,
        "registry_key": ctx.registry_key,
        "command": ctx.command,
        "mode": ctx.mode,
        "feature_branch": ctx.feature_branch,
        "session_ids": dict(ctx.session_ids),
        "engine_version": "v2",
    }
    ctx.context_json_path().write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def kanban_show(ticket_no: str) -> str:
    """`.claude-organic/bin/flow-kanban show T-NNN` — stdout 반환."""
    result = subprocess.run(
        [str(KANBAN_BIN), "show", ticket_no],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        check=False,
    )
    return result.stdout


def kanban_move(ticket_no: str, target: str) -> int:
    """`flow-kanban move T-NNN <target>` — Open/In Progress/Review/Done/Todo.

    SPEC.md §12.4 — INIT 진입 시 in_progress, DONE 종결 시 review, FAILED 시 자동 회귀 X.
    """
    result = subprocess.run(
        [str(KANBAN_BIN), "move", ticket_no, target],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        check=False,
    )
    return result.returncode


def append_log(ctx: WorkflowContext, line: str) -> None:
    """workflow.log 에 line append. 진단 trace."""
    log_path = ctx.workflow_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"[{ts}] {line}\n")
