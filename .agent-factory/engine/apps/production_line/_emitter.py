"""Production-line emitter — NDJSON metrics + semantic board endpoint helper.

SPEC.md §12.3 — driver emits NDJSON to stdout → board server SSE.
At the same time, append to metrics.jsonl (regression analysis data).

T-495 Phase 2 (driver) — v1 single `/api/v2/wf-event` call is deprecated
Backend Phase 1 is decomposed into 7 endpoints:
  POST /api/v2/sessions                       — session_create
  POST /api/v2/sessions/<id>/step — step_start (transition notification)
  POST /api/v2/sessions/<id>/stdout           — stdout_chunk (NDJSON forward)
  POST /api/v2/sessions/<id>/phase            — phase_start / phase_end
  POST /api/v2/sessions/<id>/finish           — finish (DONE/FAILED)

board push is env `V2_BOARD_POST=true` gate. fire-and-forget thread, 1s
timeout, failure silent skip — driver flow impact 0.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from ._common import PROJECT_ROOT, WorkflowContext


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


_BOARD_URL_PATH = PROJECT_ROOT / ".agent-factory" / ".board.url"

# T-506 P7 — metrics.jsonl Guarantees line atomicity when emitting multiple threads.
# OS append (O_APPEND) of a short line is usually atomic, but an explicit lock guarantees line drop 0.
_METRICS_APPEND_LOCK = threading.Lock()


def _board_post_enabled() -> bool:
    """env flag gate. If not set/false, driver flow impact is 0."""
    raw = os.environ.get("V2_BOARD_POST", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _read_board_base() -> str | None:
    """Extract scheme://host:port from the first line of `.board.url`. None if not present."""
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


def _post_to_board(endpoint_path: str, body: dict[str, Any]) -> None:
    """fire-and-forget POST to `<board>/api/v2/...`.

    Args:
        endpoint_path: Absolute path such as "/api/v2/sessions" / "/api/v2/sessions/<id>/step"
        body: JSON serializable dict

    Failure silent skip — network error / board not starting / endpoint 404, etc.
    Block driver subprocess delay with timeout 1s.
    """
    if not _board_post_enabled():
        return
    base = _read_board_base()
    if base is None:
        return

    try:
        body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError):
        return

    url = f"{base}{endpoint_path}"

    def _send() -> None:
        try:
            req = urllib.request.Request(
                url,
                data=body_bytes,
                method="POST",
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            urllib.request.urlopen(req, timeout=1.0).read()
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()


def emit(ctx: WorkflowContext | None, event: str, **payload: Any) -> None:
    """NDJSON line — stdout + metrics.jsonl append (only when ctx exists).

    This function does not do board POST (the helper calls the endpoint depending on the meaning).

    T-506 P7 — Guaranteed line drop 0 when multiple threads emit simultaneously.
    Serialize the file open + write section with `_METRICS_APPEND_LOCK`.
    """
    record = {"event": event, "ts": _now_iso(), **payload}
    line = json.dumps(record, ensure_ascii=False)
    with _METRICS_APPEND_LOCK:
        try:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
        except BrokenPipeError:
            # T-518 — graceful skip when driver subprocess stdout pipe is disconnected.
            # Other OSErrors are propagated (preventing loss of diagnostic information).
            return
        if ctx is not None:
            path = ctx.metrics_jsonl_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")


# ---------------------------------------------------------------------------
# board endpoint helper by meaning — T-495 P1
# ---------------------------------------------------------------------------


def session_create(ctx: WorkflowContext) -> None:
    """POST /api/v2/sessions — explicitly register a session (lazy create discarded).

    Immediately after entering the INIT Step, the driver is called once. session_id issued by the board and
    Matching — This driver directly issues `ctx.wf_session_id` and notifies the board.
    Failure silent skip (when the board is not started / the environment is not set, etc.).
    """
    if not ctx.wf_session_id:
        return
    body = {
        "session_id": ctx.wf_session_id,
        "ticket_id": ctx.work_request_no,
        "command": ctx.command,
        "work_dir": str(ctx.work_dir),
        "worktree_path": str(ctx.worktree_path) if ctx.worktree_path else "",
    }
    _post_to_board("/api/v2/sessions", body)


def step_start(ctx: WorkflowContext, step: str, **extra: Any) -> None:
    """Step Start transition — metrics.jsonl + board POST /step.

    If the board endpoint sends only one step transition, the backend updates current_step.
    step_end only records metrics.jsonl (avoiding duplicate calls to transitive endpoints).
    """
    emit(ctx, "step.start", step=step, work_request=ctx.work_request_no, **extra)
    if ctx.wf_session_id:
        prev = extra.get("prev_step", "") or ""
        _post_to_board(
            f"/api/v2/sessions/{ctx.wf_session_id}/step",
            {"step": step, "prev_step": prev},
        )


def step_end(
    ctx: WorkflowContext,
    step: str,
    *,
    outcome: str,
    retry_count: int = 0,
    **extra: Any,
) -> None:
    """Step End — metrics.jsonl only. The board side is updated by the next step.start."""
    emit(
        ctx,
        "step.end",
        step=step,
        work_request=ctx.work_request_no,
        outcome=outcome,
        retry_count=retry_count,
        **extra,
    )


def stdout_chunk(
    ctx: WorkflowContext | None,
    text: str,
    raw: dict[str, Any] | None = None,
) -> None:
    """POST /api/v2/sessions/<id>/stdout — claude -p NDJSON line forward.

    spawn 's on_line callback calls this function. fire-and-forget,
    Failure silent — driver flow impact 0 (risk ② broadcast chunk load shedding).
    """
    if ctx is None or not ctx.wf_session_id:
        return
    body: dict[str, Any] = {"text": text}
    if raw is not None:
        body["raw"] = raw
    _post_to_board(
        f"/api/v2/sessions/{ctx.wf_session_id}/stdout",
        body,
    )


def phase_start(
    ctx: WorkflowContext,
    phase_id: str,
    *,
    session_id: str = "",
    worker_index: int = 0,
    **extra: Any,
) -> None:
    """WORK internal phase start — metrics.jsonl + board POST /phase action=start.

    T-506 P7 — `session_id` / `worker_index` payload stuffed (UI/UX at same level
    for progress visualization + phase × worker matrix display).
    backend Phase 1 endpoint `/api/v2/sessions/<id>/phase` body is kept compatible —
    Additional fields are only stuffed in the metrics.jsonl side.
    """
    payload: dict[str, Any] = dict(extra)
    if session_id:
        payload["session_id"] = session_id
    if worker_index:
        payload["worker_index"] = worker_index
    emit(
        ctx,
        "phase.start",
        step="WORK",
        phase=phase_id,
        work_request=ctx.work_request_no,
        **payload,
    )
    if ctx.wf_session_id:
        _post_to_board(
            f"/api/v2/sessions/{ctx.wf_session_id}/phase",
            {"phase": phase_id, "action": "start"},
        )


def phase_end(
    ctx: WorkflowContext,
    phase_id: str,
    *,
    outcome: str,
    session_id: str = "",
    worker_index: int = 0,
    **extra: Any,
) -> None:
    """WORK internal phase end — metrics.jsonl + board POST /phase action=end.

    T-506 P7 — Stuffed `session_id` / `worker_index` payload. Backend body compatible preservation.
    """
    payload: dict[str, Any] = dict(extra)
    if session_id:
        payload["session_id"] = session_id
    if worker_index:
        payload["worker_index"] = worker_index
    emit(
        ctx,
        "phase.end",
        step="WORK",
        phase=phase_id,
        work_request=ctx.work_request_no,
        outcome=outcome,
        **payload,
    )
    if ctx.wf_session_id:
        _post_to_board(
            f"/api/v2/sessions/{ctx.wf_session_id}/phase",
            {"phase": phase_id, "action": "end"},
        )


def workflow_finish(
    ctx: WorkflowContext,
    *,
    outcome: str,
    verdict: str | None = None,
    summary: str = "",
    **extra: Any,
) -> None:
    """Cycle closure — metrics.jsonl + board POST /finish.

    Args:
        outcome: "ok" | "fail"
        verdict: 12 rule verdict (PASS/WARN/FAIL/SKIP) — records only metrics
        summary: One-line summary — board exposed to frontend
    """
    payload: dict[str, Any] = {"outcome": outcome, "ticket": ctx.work_request_no}
    if verdict is not None:
        payload["verdict"] = verdict
    emit(ctx, "workflow.finish", **payload, **extra)
    if ctx.wf_session_id:
        # The outcome that the backend receives is one of the following: "ok"|"fail". Otherwise, safety mapping to “fail”.
        outcome_norm = outcome if outcome in ("ok", "fail") else "fail"
        body: dict[str, Any] = {"outcome": outcome_norm, "summary": summary}
        body.update(extra)
        _post_to_board(
            f"/api/v2/sessions/{ctx.wf_session_id}/finish",
            body,
        )


def regression(ctx: WorkflowContext, pattern: str, **extra: Any) -> None:
    """SPEC.md §10 Block 5 types of regression — emit when pattern is found (metrics only)."""
    emit(ctx, "regression.pattern", pattern=pattern, work_request=ctx.work_request_no, **extra)


def tool_deny(ctx: WorkflowContext, tool: str, **extra: Any) -> None:
    """R-METRIC-3 — tool.deny 0 cases For rule verification (metrics only)."""
    emit(ctx, "tool.deny", tool=tool, work_request=ctx.work_request_no, **extra)


# ---------------------------------------------------------------------------
# Backward-compat alias — Preserve old caller (can be removed if init.py, etc. are replaced)
# ---------------------------------------------------------------------------


def session_start(ctx: WorkflowContext) -> None:
    """Deprecated — Replaced with `session_create`. backward-compat alias."""
    session_create(ctx)
