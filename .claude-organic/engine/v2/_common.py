"""v2 common utilities — WorkflowContext, status I/O, kanban CLI wrapper, paths.

SPEC.md §13 (디렉터리) + §4 (산출물) + §3.4 (재시도 한도) + §8 (claude -p) 흡수.
LLM 호출 없음. 룰베이스 결정만.
"""

from __future__ import annotations

import json
import os
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


# SPEC.md §3.4 — Step 별 재시도 한도 (기본값)
# .claude-organic/.settings 의 V2_RETRY_<STEP> 환경 변수로 override 가능.
_N_MAX_DEFAULT: dict[str, int] = {
    "INIT": 0,
    "PLAN": 2,
    "WORK": 3,
    "VALIDATE": 1,
    "REPORT": 2,
    "DONE": 0,
}


def _load_settings() -> dict[str, str]:
    """`.claude-organic/.settings` (KEY=value, # 주석) 을 dict 로 읽는다.

    파일 미존재·파싱 실패는 silent skip — driver 가 기본값으로 동작 보장.
    """
    settings_path = PROJECT_ROOT / ".claude-organic" / ".settings"
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
    """Step 별 재시도 한도 반환. `V2_RETRY_<STEP>` env override 우선.

    우선순위: os.environ > .settings > _N_MAX_DEFAULT > 0.
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


# 하위 호환 — 옛 코드의 N_MAX_BY_STEP.get(step, 0) 호출 보존 (env override 미반영).
# 신규 코드는 get_n_max(step) 사용 권장.
N_MAX_BY_STEP = _N_MAX_DEFAULT


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
    worktree_path: Path | None = None       # SPEC §9.1.1 (Stage 3-D) + §0.1 (Stage 3-E auto_commit)
    title: str = ""                         # 티켓 제목 (auto_commit 메시지 template 용)
    session_ids: dict[str, str] = field(default_factory=dict)  # Step|Phase → session_id
    wf_session_id: str | None = None        # Stage 3-B — board side workflow_registry 매핑 ID

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
        """flat 경로 — backward compat (T-503 마이그레이션 hold 기간)."""
        return self.work_dir / "work" / f"{phase_id}.md"

    def work_phase_dir(self, phase_id: str) -> Path:
        """T-503 디렉터리 nesting — work/<phase>/."""
        return self.work_dir / "work" / phase_id

    def work_phase_w_md(self, phase_id: str, worker_idx: int = 1) -> Path:
        """T-503 디렉터리 nesting — work/<phase>/W<n>.md (workers ≥ 1)."""
        return self.work_phase_dir(phase_id) / f"W{worker_idx}.md"

    def work_phase_md_resolved(self, phase_id: str) -> Path:
        """T-503 — flat 과 nested 경로 양쪽을 시도, 존재하는 쪽 반환.

        우선순위: nested (work/<phase>/W1.md) > flat (work/<phase>.md). 양쪽 모두 미존재 시 nested 기본 경로 반환 (write-target 으로 사용 가능).
        """
        nested = self.work_phase_w_md(phase_id, 1)
        if nested.exists():
            return nested
        flat = self.work_dir_phase_md(phase_id)
        if flat.exists():
            return flat
        return nested

    def validate_dir(self) -> Path:
        """T-503 — validate/ 디렉터리."""
        return self.work_dir / "validate"

    def validate_report_md_path(self) -> Path:
        """validate-report.md — flat (backward compat, T-503 마이그레이션 hold)."""
        return self.work_dir / "validate-report.md"

    def validate_report_md_nested_path(self) -> Path:
        """T-503 — validate/report.md (디렉터리 nesting)."""
        return self.validate_dir() / "report.md"

    def validate_rules_json_path(self) -> Path:
        """validate-rules.json — flat (backward compat, T-503 마이그레이션 hold)."""
        return self.work_dir / "validate-rules.json"

    def validate_rules_json_nested_path(self) -> Path:
        """T-503 — validate/rules.json (디렉터리 nesting)."""
        return self.validate_dir() / "rules.json"

    def validate_code_json_path(self) -> Path:
        """T-503 신설 — validate/code.json (driver `_verify_code.py` 산출, implement 한정)."""
        return self.validate_dir() / "code.json"

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

    def metadata_json_path(self) -> Path:
        """T-503 — metadata.json (옛 .context.json + status.json + summary.txt + failure 흡수)."""
        return self.work_dir / "metadata.json"


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
        "worktree_path": str(ctx.worktree_path) if ctx.worktree_path else None,
        "title": ctx.title,
        "session_ids": dict(ctx.session_ids),
        "wf_session_id": ctx.wf_session_id,
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


def write_metadata(
    ctx: WorkflowContext,
    *,
    finalized_at: str | None = None,
    failure_reason: str | None = None,
) -> Path:
    """T-503 — `metadata.json` 통합 writer.

    옛 산출물 4 파일 (`.context.json` + `status.json` + `summary.txt` + `failure.md`)
    을 단일 JSON 으로 통합 박제. 신규 cycle 만 본 함수 호출. driver writer 1 곳에서 일관 산출.

    스키마:
        {
          "schema_version": 1,
          "ticket_no": "T-NNN",
          "registry_key": "...",
          "command": "implement",
          "mode": "multi",
          "feature_branch": "feat/...",
          "worktree_path": "...",
          "title": "...",
          "wf_session_id": "...",
          "engine_version": "v2",
          "session_ids": {"wf-T-PLAN": "...", ...},
          "workflow_step": "DONE",
          "transitions": [{"from":"INIT","to":"PLAN","ts":"..."}, ...],
          "finalized_at": "2026-05-18T...",   # DONE 단계에서만 채움 (옛 summary.txt 대체)
          "failure": {"reason": "...", "ts": "..."} | null,  # FAILED 단계만 (옛 failure.md 대체)
        }
    """
    status = read_status(ctx)
    payload = {
        "schema_version": 1,
        "ticket_no": ctx.ticket_no,
        "registry_key": ctx.registry_key,
        "command": ctx.command,
        "mode": ctx.mode,
        "feature_branch": ctx.feature_branch,
        "worktree_path": str(ctx.worktree_path) if ctx.worktree_path else None,
        "title": ctx.title,
        "wf_session_id": ctx.wf_session_id,
        "engine_version": "v2",
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
    """T-503 — `metadata.json` reader. 미존재 시 `{}` 반환."""
    path = ctx.metadata_json_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def auto_commit(ctx: WorkflowContext) -> int:
    """SPEC §0.1 (Stage 3-E) — worker 산출물 결정론 commit.

    WORK Step 종료 직후 driver 가 호출. LLM 위임 0건.

    동작:
      1. ctx.worktree_path 가 None (worktree-less 또는 init 회귀) → skip, return 0
      2. `git -C <wt> add -A` — worker 산출물 + work/*.md 모두 stage
      3. `git -C <wt> diff --cached --quiet` — 변경 0건이면 returncode 0 → skip, return 0
      4. 결정론 메시지 template 으로 `git -C <wt> commit -m <msg>` → returncode 반환

    메시지 template: "feat(<ticket>): <title> [v2 driver auto-commit]"
    """
    if ctx.worktree_path is None:
        append_log(ctx, "[AUTO-COMMIT] worktree-less — skip")
        return 0
    wt = str(ctx.worktree_path)
    if not Path(wt).is_dir():
        append_log(ctx, f"[AUTO-COMMIT] worktree path 미존재 ({wt}) — skip")
        return 0
    # 1. add -A
    add = subprocess.run(
        ["git", "-C", wt, "add", "-A"],
        capture_output=True,
        text=True,
        check=False,
    )
    if add.returncode != 0:
        append_log(ctx, f"[AUTO-COMMIT] git add 실패 rc={add.returncode}: {add.stderr.strip()[:200]}")
        return add.returncode
    # 2. staged 변경 detect
    diff = subprocess.run(
        ["git", "-C", wt, "diff", "--cached", "--quiet"],
        capture_output=True,
        text=True,
        check=False,
    )
    if diff.returncode == 0:
        append_log(ctx, "[AUTO-COMMIT] staged 변경 0건 — skip")
        return 0
    # 3. commit 메시지 결정론 template
    title = ctx.title or "(no title)"
    msg = f"feat({ctx.ticket_no}): {title} [v2 driver auto-commit]"
    commit = subprocess.run(
        ["git", "-C", wt, "commit", "-m", msg],
        capture_output=True,
        text=True,
        check=False,
    )
    if commit.returncode != 0:
        append_log(
            ctx,
            f"[AUTO-COMMIT] git commit 실패 rc={commit.returncode}: "
            f"{commit.stderr.strip()[:200]}",
        )
        return commit.returncode
    append_log(ctx, f"[AUTO-COMMIT] commit OK — {msg}")
    return 0
