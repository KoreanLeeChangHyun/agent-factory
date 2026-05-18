"""test_emitter.py — T-495 P1 의미별 board endpoint helper 검증.

대상:
  - session_create → POST /api/v2/sessions
  - step_start → POST /api/v2/sessions/<id>/step
  - stdout_chunk → POST /api/v2/sessions/<id>/stdout
  - phase_start/phase_end → POST /api/v2/sessions/<id>/phase
  - workflow_finish → POST /api/v2/sessions/<id>/finish
  - V2_BOARD_POST gate 시 silent skip
  - wf_session_id 미설정 시 silent skip
  - metrics.jsonl 누적 (NDJSON)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from engine.v2._common import WorkflowContext
from engine.v2 import _emitter as emitter


@pytest.fixture
def ctx(tmp_path: Path) -> WorkflowContext:
    work = tmp_path / "20260517-203000"
    (work / "work").mkdir(parents=True, exist_ok=True)
    return WorkflowContext(
        ticket_no="T-495",
        registry_key="20260517-203000",
        work_dir=work,
        command="implement",
        title="dummy ticket",
        wf_session_id="wf-T-495-20260517-203000",
    )


@pytest.fixture(autouse=True)
def enable_board_post(monkeypatch):
    """V2_BOARD_POST=true + .board.url stub."""
    monkeypatch.setenv("V2_BOARD_POST", "true")
    with patch.object(emitter, "_read_board_base", return_value="http://127.0.0.1:9927"):
        yield


def _capture_posts(monkeypatch):
    """_post_to_board 호출 인자 캡처. fire-and-forget thread 우회 — 동기 캡처."""
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_post(endpoint_path: str, body: dict[str, Any]) -> None:
        calls.append((endpoint_path, body))

    monkeypatch.setattr(emitter, "_post_to_board", fake_post)
    return calls


def test_session_create_endpoint_and_body(ctx, monkeypatch):
    calls = _capture_posts(monkeypatch)
    emitter.session_create(ctx)
    assert len(calls) == 1
    path, body = calls[0]
    assert path == "/api/v2/sessions"
    assert body["session_id"] == "wf-T-495-20260517-203000"
    assert body["ticket_id"] == "T-495"
    assert body["command"] == "implement"
    assert body["work_dir"] == str(ctx.work_dir)
    assert body["worktree_path"] == ""


def test_session_create_skips_when_no_session_id(tmp_path, monkeypatch):
    calls = _capture_posts(monkeypatch)
    ctx_no_id = WorkflowContext(
        ticket_no="T-495",
        registry_key="k",
        work_dir=tmp_path,
        command="implement",
        wf_session_id=None,
    )
    emitter.session_create(ctx_no_id)
    assert calls == []


def test_step_start_posts_step_endpoint(ctx, monkeypatch):
    calls = _capture_posts(monkeypatch)
    emitter.step_start(ctx, "PLAN", prev_step="INIT")
    assert len(calls) == 1
    path, body = calls[0]
    assert path == f"/api/v2/sessions/{ctx.wf_session_id}/step"
    assert body == {"step": "PLAN", "prev_step": "INIT"}


def test_step_end_does_not_post(ctx, monkeypatch):
    """step_end 는 board POST 안 함 — 다음 step.start 가 backend 갱신."""
    calls = _capture_posts(monkeypatch)
    emitter.step_end(ctx, "PLAN", outcome="ok", retry_count=0)
    assert calls == []


def test_stdout_chunk_posts_stdout_endpoint(ctx, monkeypatch):
    calls = _capture_posts(monkeypatch)
    emitter.stdout_chunk(ctx, "hello", raw={"type": "assistant"})
    assert len(calls) == 1
    path, body = calls[0]
    assert path == f"/api/v2/sessions/{ctx.wf_session_id}/stdout"
    assert body["text"] == "hello"
    assert body["raw"] == {"type": "assistant"}


def test_stdout_chunk_omits_raw_when_none(ctx, monkeypatch):
    calls = _capture_posts(monkeypatch)
    emitter.stdout_chunk(ctx, "plain")
    path, body = calls[0]
    assert path == f"/api/v2/sessions/{ctx.wf_session_id}/stdout"
    assert body == {"text": "plain"}


def test_stdout_chunk_skips_when_no_ctx(monkeypatch):
    calls = _capture_posts(monkeypatch)
    emitter.stdout_chunk(None, "x")
    assert calls == []


def test_phase_start_action_start(ctx, monkeypatch):
    calls = _capture_posts(monkeypatch)
    emitter.phase_start(ctx, "P1")
    assert len(calls) == 1
    path, body = calls[0]
    assert path == f"/api/v2/sessions/{ctx.wf_session_id}/phase"
    assert body == {"phase": "P1", "action": "start"}


def test_phase_end_action_end(ctx, monkeypatch):
    calls = _capture_posts(monkeypatch)
    emitter.phase_end(ctx, "P2", outcome="ok")
    assert len(calls) == 1
    path, body = calls[0]
    assert path == f"/api/v2/sessions/{ctx.wf_session_id}/phase"
    assert body == {"phase": "P2", "action": "end"}


def test_workflow_finish_ok(ctx, monkeypatch):
    calls = _capture_posts(monkeypatch)
    emitter.workflow_finish(ctx, outcome="ok", verdict="PASS", summary="done")
    assert len(calls) == 1
    path, body = calls[0]
    assert path == f"/api/v2/sessions/{ctx.wf_session_id}/finish"
    assert body == {"outcome": "ok", "summary": "done"}


def test_workflow_finish_fail_normalizes_unknown_outcome(ctx, monkeypatch):
    calls = _capture_posts(monkeypatch)
    emitter.workflow_finish(ctx, outcome="weird", summary="x")
    path, body = calls[0]
    assert body["outcome"] == "fail"  # ok|fail 외는 fail 안전 매핑


def test_metrics_jsonl_appended_on_emit(ctx):
    """emit() 호출이 metrics.jsonl 에 NDJSON line 추가."""
    emitter.emit(ctx, "step.start", step="PLAN", ticket=ctx.ticket_no)
    emitter.emit(ctx, "step.end", step="PLAN", ticket=ctx.ticket_no, outcome="ok")
    lines = ctx.metrics_jsonl_path().read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "step.start"
    assert json.loads(lines[1])["event"] == "step.end"
    assert json.loads(lines[1])["outcome"] == "ok"


def test_board_post_gate_disabled(ctx, monkeypatch):
    """V2_BOARD_POST 미설정 시 _post_to_board 가 internal gate 로 skip."""
    monkeypatch.delenv("V2_BOARD_POST", raising=False)
    # _post_to_board 의 실제 분기 검사 (mock 안 함)
    calls: list[tuple[str, dict]] = []
    real_post = emitter._post_to_board

    def spy(path, body):
        calls.append((path, body))
        real_post(path, body)

    monkeypatch.setattr(emitter, "_post_to_board", spy)

    with patch("urllib.request.urlopen") as mocked_urlopen:
        emitter.session_create(ctx)
        # session_create 는 helper 가 직접 _post_to_board 호출 — spy 가 한 번 잡힘
        assert len(calls) == 1
        # 그러나 V2_BOARD_POST 비활성 + _post_to_board 내부 gate 로 urlopen 미호출
        mocked_urlopen.assert_not_called()


def test_session_start_alias_calls_session_create(ctx, monkeypatch):
    """backward-compat alias 검증 — session_start = session_create."""
    calls = _capture_posts(monkeypatch)
    emitter.session_start(ctx)
    assert len(calls) == 1
    assert calls[0][0] == "/api/v2/sessions"


# ---------------------------------------------------------------------------
# T-506 P7 — phase_start/end 다중 session 박제 + thread-safe append
# ---------------------------------------------------------------------------


def test_phase_start_session_id_payload(ctx, monkeypatch):
    """T-506 P7 — phase_start 가 session_id + worker_index payload 박제."""
    _capture_posts(monkeypatch)
    emitter.phase_start(ctx, "P1", session_id="abc-uuid", worker_index=2)
    lines = ctx.metrics_jsonl_path().read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[-1])
    assert record["event"] == "phase.start"
    assert record["phase"] == "P1"
    assert record["session_id"] == "abc-uuid"
    assert record["worker_index"] == 2


def test_phase_end_session_id_payload(ctx, monkeypatch):
    """T-506 P7 — phase_end 도 session_id + worker_index payload 박제."""
    _capture_posts(monkeypatch)
    emitter.phase_end(ctx, "P1", outcome="ok", session_id="xyz-uuid", worker_index=3)
    lines = ctx.metrics_jsonl_path().read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[-1])
    assert record["event"] == "phase.end"
    assert record["session_id"] == "xyz-uuid"
    assert record["worker_index"] == 3


def test_phase_start_omits_empty_session_id(ctx, monkeypatch):
    """기존 호출자 시그니처 호환 — session_id="" / worker_index=0 default → payload 미포함."""
    _capture_posts(monkeypatch)
    emitter.phase_start(ctx, "P1", spawn_mode="in_place")
    lines = ctx.metrics_jsonl_path().read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[-1])
    assert "session_id" not in record
    assert "worker_index" not in record
    assert record["spawn_mode"] == "in_place"


def test_emit_multi_thread_no_line_drop(ctx):
    """T-506 P7 — 10 thread × 30 emit = 300 line 모두 metrics.jsonl 박제."""
    import threading

    N_THREADS = 10
    PER_THREAD = 30

    def worker(tid: int) -> None:
        for i in range(PER_THREAD):
            emitter.emit(
                ctx,
                "test.event",
                tid=tid,
                seq=i,
                ticket=ctx.ticket_no,
            )

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = ctx.metrics_jsonl_path().read_text(encoding="utf-8").splitlines()
    assert len(lines) == N_THREADS * PER_THREAD, (
        f"line drop: expected {N_THREADS * PER_THREAD}, got {len(lines)}"
    )
    # 각 line 이 valid JSON + event=test.event
    parsed = [json.loads(line) for line in lines]
    assert all(r["event"] == "test.event" for r in parsed)
    # 각 (tid, seq) 쌍이 정확히 1번씩 등장
    pairs = {(r["tid"], r["seq"]) for r in parsed}
    assert len(pairs) == N_THREADS * PER_THREAD


def test_phase_start_session_ids_list(ctx, monkeypatch):
    """T-506 P7 — workers > 1 phase 의 session_ids list payload 박제."""
    _capture_posts(monkeypatch)
    emitter.phase_end(
        ctx,
        "P1",
        outcome="ok",
        session_ids=["a-uuid", "b-uuid", "c-uuid"],
    )
    lines = ctx.metrics_jsonl_path().read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[-1])
    assert record["session_ids"] == ["a-uuid", "b-uuid", "c-uuid"]
