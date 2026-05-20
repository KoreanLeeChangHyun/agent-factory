from __future__ import annotations

import pytest

from engine.core.work_requests import WorkRequestRef
from engine.core.workflows import (
    WorkflowRun,
    WorkflowRunRef,
    WorkflowStage,
    canonicalize_v2_step,
    stage_from_v2_step,
    stage_to_v2_step,
)


def _run() -> WorkflowRun:
    return WorkflowRun(
        ref=WorkflowRunRef("WF-T-123-20260520-000000"),
        work_request_ref=WorkRequestRef.parse("T-123"),
    )


def test_workflow_run_enforces_six_stage_order() -> None:
    run = _run()

    for stage in (
        WorkflowStage.PLAN,
        WorkflowStage.EXECUTE,
        WorkflowStage.VERIFY,
        WorkflowStage.REPORT,
        WorkflowStage.COMPLETE,
    ):
        run.advance_to(stage)

    assert run.terminal
    assert run.stage is WorkflowStage.COMPLETE
    assert [t.to_stage for t in run.transitions] == [
        WorkflowStage.PLAN,
        WorkflowStage.EXECUTE,
        WorkflowStage.VERIFY,
        WorkflowStage.REPORT,
        WorkflowStage.COMPLETE,
    ]


def test_workflow_run_rejects_reordered_stages() -> None:
    run = _run()

    with pytest.raises(ValueError, match="illegal workflow transition"):
        run.advance_to(WorkflowStage.EXECUTE)

    run.advance_to(WorkflowStage.PLAN)
    with pytest.raises(ValueError, match="illegal workflow transition"):
        run.advance_to(WorkflowStage.REPORT)


def test_production_line_step_mapping_keeps_status_file_compatibility() -> None:
    assert stage_from_v2_step("INIT") is WorkflowStage.PREPARE
    assert stage_from_v2_step("WORK") is WorkflowStage.EXECUTE
    assert stage_from_v2_step("VALIDATE") is WorkflowStage.VERIFY
    assert stage_from_v2_step("DONE") is WorkflowStage.COMPLETE
    assert stage_to_v2_step(WorkflowStage.EXECUTE) == "WORK"
    assert canonicalize_v2_step("VERIFY") == "VALIDATE"


def test_workflow_run_reads_legacy_v2_status() -> None:
    run = WorkflowRun.from_v2_status(
        run_ref=WorkflowRunRef("WF-T-123-20260520-000000"),
        work_request_ref=WorkRequestRef.parse("T-123"),
        status={
            "workflow_step": "VALIDATE",
            "transitions": [
                {"from": "INIT", "to": "PLAN", "ts": "2026-05-20T00:00:00"},
                {"from": "PLAN", "to": "WORK", "ts": "2026-05-20T00:00:01"},
                {"from": "WORK", "to": "VALIDATE", "ts": "2026-05-20T00:00:02"},
            ],
        },
    )

    assert run.stage is WorkflowStage.VERIFY
    assert [t.to_stage for t in run.transitions] == [
        WorkflowStage.PLAN,
        WorkflowStage.EXECUTE,
        WorkflowStage.VERIFY,
    ]
