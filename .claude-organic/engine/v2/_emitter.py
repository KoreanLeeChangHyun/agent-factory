"""v2 emitter — NDJSON metrics + 의미별 board endpoint helper.

SPEC.md §12.3 — driver 가 stdout NDJSON emit → board 서버 SSE.
동시에 metrics.jsonl 에 append (회귀 분석 자료).

T-495 Phase 2 (driver) — v1 단일 `/api/v2/wf-event` 호출은 폐기되고
backend Phase 1 의 7 endpoint 로 분해된다:
  POST /api/v2/sessions                       — session_create
  POST /api/v2/sessions/<id>/step             — step_start (전이 통보)
  POST /api/v2/sessions/<id>/stdout           — stdout_chunk (NDJSON forward)
  POST /api/v2/sessions/<id>/phase            — phase_start / phase_end
  POST /api/v2/sessions/<id>/finish           — finish (DONE/FAILED)

board push 는 env `V2_BOARD_POST=true` gate. fire-and-forget thread, 1s
timeout, 실패 silent skip — driver 흐름 영향 0.
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
    """env flag gate. 미설정/false 시 driver 흐름 영향 0."""
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


def _post_to_board(endpoint_path: str, body: dict[str, Any]) -> None:
    """fire-and-forget POST to `<board>/api/v2/...`.

    Args:
        endpoint_path: "/api/v2/sessions" / "/api/v2/sessions/<id>/step" 등 절대 path
        body: JSON 직렬화 가능한 dict

    실패 silent skip — 네트워크 오류 / board 미기동 / endpoint 404 등.
    timeout 1s 로 driver subprocess 지연 차단.
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
    """NDJSON line — stdout + metrics.jsonl append (ctx 있을 때만).

    board POST 는 본 함수가 하지 않음 (의미별 helper 가 endpoint 호출).
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


# ---------------------------------------------------------------------------
# 의미별 board endpoint helper — T-495 P1
# ---------------------------------------------------------------------------


def session_create(ctx: WorkflowContext) -> None:
    """POST /api/v2/sessions — 세션 명시 등록 (lazy create 폐기).

    INIT Step 진입 직후 driver 가 1회 호출. board 가 발급한 session_id 와
    정합 — 본 driver 는 `ctx.wf_session_id` 를 직접 발급해 board 에 통보한다.
    실패 silent skip (board 미기동 / 환경 미설정 시 등).
    """
    if not ctx.wf_session_id:
        return
    body = {
        "session_id": ctx.wf_session_id,
        "ticket_id": ctx.ticket_no,
        "command": ctx.command,
        "work_dir": str(ctx.work_dir),
        "worktree_path": str(ctx.worktree_path) if ctx.worktree_path else "",
    }
    _post_to_board("/api/v2/sessions", body)


def step_start(ctx: WorkflowContext, step: str, **extra: Any) -> None:
    """Step 전이 시작 — metrics.jsonl + board POST /step.

    board endpoint 는 step 전이 1건만 보내면 backend 가 current_step 갱신.
    step_end 는 metrics.jsonl 만 기록 (전이 endpoint 중복 호출 회피).
    """
    emit(ctx, "step.start", step=step, ticket=ctx.ticket_no, **extra)
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
    """Step 종료 — metrics.jsonl only. board side 는 다음 step.start 가 갱신."""
    emit(
        ctx,
        "step.end",
        step=step,
        ticket=ctx.ticket_no,
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

    spawn 의 on_line 콜백이 이 함수를 호출한다. fire-and-forget,
    실패 silent — driver 흐름 영향 0 (위험 ② broadcast chunk 부하 차단).
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


def phase_start(ctx: WorkflowContext, phase_id: str, **extra: Any) -> None:
    """WORK 내부 phase 시작 — metrics.jsonl + board POST /phase action=start."""
    emit(ctx, "phase.start", step="WORK", phase=phase_id, ticket=ctx.ticket_no, **extra)
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
    **extra: Any,
) -> None:
    """WORK 내부 phase 종료 — metrics.jsonl + board POST /phase action=end."""
    emit(
        ctx,
        "phase.end",
        step="WORK",
        phase=phase_id,
        ticket=ctx.ticket_no,
        outcome=outcome,
        **extra,
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
    """사이클 종결 — metrics.jsonl + board POST /finish.

    Args:
        outcome: "ok" | "fail"
        verdict: 12룰 verdict (PASS/WARN/FAIL/SKIP) — metrics 만 기록
        summary: 한 줄 요약 — board 가 frontend 에 노출
    """
    payload: dict[str, Any] = {"outcome": outcome, "ticket": ctx.ticket_no}
    if verdict is not None:
        payload["verdict"] = verdict
    emit(ctx, "workflow.finish", **payload, **extra)
    if ctx.wf_session_id:
        # backend 가 받는 outcome 은 "ok"|"fail" 둘 중 하나. 그 외는 "fail" 로 안전 매핑.
        outcome_norm = outcome if outcome in ("ok", "fail") else "fail"
        _post_to_board(
            f"/api/v2/sessions/{ctx.wf_session_id}/finish",
            {"outcome": outcome_norm, "summary": summary},
        )


def regression(ctx: WorkflowContext, pattern: str, **extra: Any) -> None:
    """SPEC.md §10 회귀 5종 차단 — pattern 발견 시 emit (metrics only)."""
    emit(ctx, "regression.pattern", pattern=pattern, ticket=ctx.ticket_no, **extra)


def tool_deny(ctx: WorkflowContext, tool: str, **extra: Any) -> None:
    """R-METRIC-3 — tool.deny 0건 룰 검증용 (metrics only)."""
    emit(ctx, "tool.deny", tool=tool, ticket=ctx.ticket_no, **extra)


# ---------------------------------------------------------------------------
# Backward-compat alias — 옛 호출자 보존 (init.py 등이 갈아끼우면 제거 가능)
# ---------------------------------------------------------------------------


def session_start(ctx: WorkflowContext) -> None:
    """Deprecated — `session_create` 로 갈아끼움. backward-compat alias."""
    session_create(ctx)
