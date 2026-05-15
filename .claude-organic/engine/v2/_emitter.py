"""v2 emitter — NDJSON event stream.

SPEC.md §12.3 — driver 가 stdout NDJSON emit → Board 서버 SSE.
동시에 metrics.jsonl 에 append (회귀 분석 자료).

Stage 3-B — board HTTP push (env `V2_BOARD_POST=true` gate).
"""

from __future__ import annotations

import json
import os
import sys
import threading
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from ._common import PROJECT_ROOT, WorkflowContext


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


_BOARD_URL_PATH = PROJECT_ROOT / ".claude-organic" / ".board.url"


def _board_post_enabled() -> bool:
    """Stage 3-B — env flag gate. 미설정/false 시 driver 흐름 영향 0."""
    raw = os.environ.get("V2_BOARD_POST", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _read_board_base() -> str | None:
    """`.board.url` 첫 줄에서 scheme://host:port 추출. 미존재 시 None."""
    if not _BOARD_URL_PATH.is_file():
        return None
    try:
        for line in _BOARD_URL_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            parsed = urllib.parse.urlsplit(line)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
    except OSError:
        return None
    return None


def _post_to_board(session_id: str, event: str, payload: dict[str, Any]) -> None:
    """fire-and-forget POST `/api/v2/wf-event`.

    실패 silent skip — driver 흐름 영향 0 (네트워크 오류 / board 미기동 / endpoint 404).
    timeout 1s 로 driver subprocess 지연 차단.
    """
    if not _board_post_enabled():
        return
    base = _read_board_base()
    if base is None:
        return

    body = json.dumps(
        {"session_id": session_id, "event": event, "payload": payload},
        ensure_ascii=False,
    ).encode("utf-8")

    def _send() -> None:
        try:
            req = urllib.request.Request(
                f"{base}/api/v2/wf-event",
                data=body,
                method="POST",
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            urllib.request.urlopen(req, timeout=1.0).read()
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()


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
        if ctx.wf_session_id:
            _post_to_board(ctx.wf_session_id, event, record)


def session_start(ctx: WorkflowContext) -> None:
    """Stage 3-B — board lazy session create trigger.

    INIT Step 진입 시 driver 가 발급한 `wf_session_id` 로 board side
    workflow_registry 등록을 1회 발사. 등록 외 비용 0.
    """
    if not ctx.wf_session_id:
        return
    payload = {
        "event": "session.start",
        "ts": _now_iso(),
        "ticket": ctx.ticket_no,
        "command": ctx.command,
        "work_dir": str(ctx.work_dir),
        "title": ctx.title,
    }
    _post_to_board(ctx.wf_session_id, "session.start", payload)


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
