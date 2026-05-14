"""v2 emitter — NDJSON event stream.

SPEC.md §12.3 — driver 가 stdout NDJSON emit → Board 서버 SSE.
동시에 metrics.jsonl 에 append (회귀 분석 자료).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Any

from ._common import WorkflowContext


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def emit(ctx: WorkflowContext | None, event: str, **payload: Any) -> None:
    """Single NDJSON line — stdout + metrics.jsonl append (ctx 있을 때만).

    payload 에 ticket / step / phase / outcome / retry_count 등 자유 키.
    """
    record = {"event": event, "ts": _now_iso(), **payload}
    line = json.dumps(record, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()
    if ctx is not None:
        path = ctx.metrics_jsonl_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def step_start(ctx: WorkflowContext, step: str, **extra: Any) -> None:
    emit(ctx, "step.start", step=step, ticket=ctx.ticket_no, **extra)


def step_end(
    ctx: WorkflowContext,
    step: str,
    *,
    outcome: str,
    retry_count: int = 0,
    **extra: Any,
) -> None:
    emit(
        ctx,
        "step.end",
        step=step,
        ticket=ctx.ticket_no,
        outcome=outcome,
        retry_count=retry_count,
        **extra,
    )


def phase_start(ctx: WorkflowContext, phase_id: str, **extra: Any) -> None:
    emit(ctx, "phase.start", step="WORK", phase=phase_id, ticket=ctx.ticket_no, **extra)


def phase_end(
    ctx: WorkflowContext,
    phase_id: str,
    *,
    outcome: str,
    **extra: Any,
) -> None:
    emit(
        ctx,
        "phase.end",
        step="WORK",
        phase=phase_id,
        ticket=ctx.ticket_no,
        outcome=outcome,
        **extra,
    )


def workflow_finish(
    ctx: WorkflowContext,
    *,
    outcome: str,
    verdict: str | None = None,
    **extra: Any,
) -> None:
    payload: dict[str, Any] = {"outcome": outcome, "ticket": ctx.ticket_no}
    if verdict is not None:
        payload["verdict"] = verdict
    emit(ctx, "workflow.finish", **payload, **extra)


def regression(ctx: WorkflowContext, pattern: str, **extra: Any) -> None:
    """SPEC.md §10 회귀 5종 차단 — pattern 발견 시 emit."""
    emit(ctx, "regression.pattern", pattern=pattern, ticket=ctx.ticket_no, **extra)


def tool_deny(ctx: WorkflowContext, tool: str, **extra: Any) -> None:
    """R-METRIC-3 — tool.deny 0건 룰 검증용 (v1 hook 잔재, v2 는 기본 0건)."""
    emit(ctx, "tool.deny", tool=tool, ticket=ctx.ticket_no, **extra)
