"""Workflow domain model and V2 compatibility helpers."""

from .domain import (
    WorkflowRun,
    WorkflowRunRef,
    WorkflowStage,
    WorkflowStageTransition,
    V2_STEP_TO_STAGE,
    assert_valid_stage_transition,
    canonicalize_v2_step,
    can_transition,
    stage_from_v2_step,
    stage_to_v2_step,
)

__all__ = [
    "V2_STEP_TO_STAGE",
    "WorkflowRun",
    "WorkflowRunRef",
    "WorkflowStage",
    "WorkflowStageTransition",
    "assert_valid_stage_transition",
    "canonicalize_v2_step",
    "can_transition",
    "stage_from_v2_step",
    "stage_to_v2_step",
]
