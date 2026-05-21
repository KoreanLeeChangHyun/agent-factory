"""test_emitter.py — Verification of board endpoint helper by WR-495 P1 meaning.

Target:
  - session_create → POST /api/v2/sessions
  - step_start → POST /api/v2/sessions/<id>/step
  - stdout_chunk → POST /api/v2/sessions/<id>/stdout
  - phase_start/phase_end → POST /api/v2/sessions/<id>/phase
  - workflow_finish → POST /api/v2/sessions/<id>/finish
  - Silent skip at V2_BOARD_POST gate
  - Silent skip when wf_session_id is not set
  - metrics.jsonl cumulative (NDJSON)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from engine.apps.production_line._common import WorkflowContext
from engine.apps.production_line import _emitter as emitter


@pytest.fixture
def ctx(tmp_path: Path) -> WorkflowContext:
    work = tmp_path / "20260517-203000"
    (work / "work").mkdir(parents=True, exist_ok=True)
    return WorkflowContext(
        work_request_no="WR-495",
        registry_key="20260517-203000",
        work_dir=work,
        command="implement",
        title="dummy work request",
        wf_session_id="wf-WR-495-20260517-203000",
    )


@pytest.fixture(autouse=True)
def enable_board_post(monkeypatch):
    """V2_BOARD_POST=true + .board.url stub."""
    monkeypatch.setenv("V2_BOARD_POST", "true")
    with patch.object(emitter, "_read_board_base", return_value="http://127.0.0.1:9927"):
        yield


def _capture_posts(monkeypatch):
    """Capturing _post_to_board call arguments. fire-and-forget thread bypass — synchronous capture."""
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
    assert body["session_id"] == "wf-WR-495-20260517-203000"
    assert body["work_request"] == "WR-495"
    assert body["command"] == "implement"
    assert body["work_dir"] == str(ctx.work_dir)
    assert body["worktree_path"] == ""


def test_session_create_skips_when_no_session_id(tmp_path, monkeypatch):
    calls = _capture_posts(monkeypatch)
    ctx_no_id = WorkflowContext(
        work_request_no="WR-495",
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
    """step_end does not POST the board — the next step.start updates the backend."""
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
    assert body["outcome"] == "fail"  # Other than ok|fail, fail-safe mapping


def test_metrics_jsonl_appended_on_emit(ctx):
    """The emit() call adds an NDJSON line to metrics.jsonl."""
    emitter.emit(ctx, "step.start", step="PLAN", work_request=ctx.work_request_no)
    emitter.emit(ctx, "step.end", step="PLAN", work_request=ctx.work_request_no, outcome="ok")
    lines = ctx.metrics_jsonl_path().read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "step.start"
    assert json.loads(lines[1])["event"] == "step.end"
    assert json.loads(lines[1])["outcome"] == "ok"


def test_board_post_gate_disabled(ctx, monkeypatch):
    """If V2_BOARD_POST is not set, _post_to_board skips to internal gate."""
    monkeypatch.delenv("V2_BOARD_POST", raising=False)
    # Check actual branch of _post_to_board (not mock)
    calls: list[tuple[str, dict]] = []
    real_post = emitter._post_to_board

    def spy(path, body):
        calls.append((path, body))
        real_post(path, body)

    monkeypatch.setattr(emitter, "_post_to_board", spy)

    with patch("urllib.request.urlopen") as mocked_urlopen:
        emitter.session_create(ctx)
        # session_create calls _post_to_board directly from helper — spy caught once
        assert len(calls) == 1
        # However, V2_BOARD_POST is inactive + urlopen is not called with the _post_to_board internal gate.
        mocked_urlopen.assert_not_called()


def test_session_start_alias_calls_session_create(ctx, monkeypatch):
    """backward-compat alias validation — session_start = session_create."""
    calls = _capture_posts(monkeypatch)
    emitter.session_start(ctx)
    assert len(calls) == 1
    assert calls[0][0] == "/api/v2/sessions"


# ---------------------------------------------------------------------------
# T-506 P7 — phase_start/end multi-session stuffing + thread-safe append
# ---------------------------------------------------------------------------


def test_phase_start_session_id_payload(ctx, monkeypatch):
    """T-506 P7 — phase_start stuffed with session_id + worker_index payload."""
    _capture_posts(monkeypatch)
    emitter.phase_start(ctx, "P1", session_id="abc-uuid", worker_index=2)
    lines = ctx.metrics_jsonl_path().read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[-1])
    assert record["event"] == "phase.start"
    assert record["phase"] == "P1"
    assert record["session_id"] == "abc-uuid"
    assert record["worker_index"] == 2


def test_phase_end_session_id_payload(ctx, monkeypatch):
    """T-506 P7 — phase_end also stuffed with session_id + worker_index payload."""
    _capture_posts(monkeypatch)
    emitter.phase_end(ctx, "P1", outcome="ok", session_id="xyz-uuid", worker_index=3)
    lines = ctx.metrics_jsonl_path().read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[-1])
    assert record["event"] == "phase.end"
    assert record["session_id"] == "xyz-uuid"
    assert record["worker_index"] == 3


def test_phase_start_omits_empty_session_id(ctx, monkeypatch):
    """Compatible with existing caller signatures — session_id="" / worker_index=0 default → payload not included."""
    _capture_posts(monkeypatch)
    emitter.phase_start(ctx, "P1", spawn_mode="in_place")
    lines = ctx.metrics_jsonl_path().read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[-1])
    assert "session_id" not in record
    assert "worker_index" not in record
    assert record["spawn_mode"] == "in_place"


def test_emit_multi_thread_no_line_drop(ctx):
    """T-506 P7 — 10 thread × 30 emit = 300 lines all stuffed in metrics.jsonl."""
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
                work_request=ctx.work_request_no,
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
    # Each line is valid JSON + event=test.event
    parsed = [json.loads(line) for line in lines]
    assert all(r["event"] == "test.event" for r in parsed)
    # Each (tid, seq) pair occurs exactly once
    pairs = {(r["tid"], r["seq"]) for r in parsed}
    assert len(pairs) == N_THREADS * PER_THREAD


# ---------------------------------------------------------------------------
# T-518 — emit() BrokenPipeError graceful skip
# ---------------------------------------------------------------------------


class _BrokenStdout:
    """Replaces sys.stdout — raises BrokenPipeError when writing."""

    def write(self, data: str) -> int:  # noqa: ARG002
        raise BrokenPipeError("EPIPE")

    def flush(self) -> None:
        pass


class _OSErrorStdout:
    """Replaces sys.stdout — raises a general OSError when writing (BrokenPipe, etc.)."""

    def write(self, data: str) -> int:  # noqa: ARG002
        raise OSError(28, "ENOSPC")

    def flush(self) -> None:
        pass


def test_emit_broken_pipe_returns_silently(ctx, monkeypatch):
    """T-518 — Even if sys.stdout.write raises BrokenPipeError, exception is not propagated.

    Root cause (T-514 P6 §1): Driver subprocess stdout pipe is disconnected. emit()
    BrokenPipeError not caught was the single origin of driver death.
    """
    monkeypatch.setattr(sys, "stdout", _BrokenStdout())
    # graceful return — exception propagation 0
    emitter.emit(ctx, "test.event", payload="x")


def test_emit_normal_writes_to_stdout(ctx, capsys):
    """T-518 — Preserve stdout output of normal path (no regression of BrokenPipe catch)."""
    emitter.emit(ctx, "test.event", payload="x")
    captured = capsys.readouterr()
    assert '"event": "test.event"' in captured.out
    assert '"payload": "x"' in captured.out
    # metrics.jsonl Park Je-do summit
    lines = ctx.metrics_jsonl_path().read_text(encoding="utf-8").splitlines()
    assert any(json.loads(line)["event"] == "test.event" for line in lines)


def test_emit_other_oserror_propagates(ctx, monkeypatch):
    """T-518 — BrokenPipeError only swallow; Other OSErrors are propagated (preventing loss of diagnostic information)."""
    monkeypatch.setattr(sys, "stdout", _OSErrorStdout())
    with pytest.raises(OSError):
        emitter.emit(ctx, "test.event", payload="x")


def test_phase_start_session_ids_list(ctx, monkeypatch):
    """T-506 P7 — workers > 1 phase of session_ids list payload stuffed."""
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
