"""Pure workflow domain model.

Production-line runtime keeps its historical step names in status files while the core
domain uses the provider-independent lifecycle:

    PREPARE -> PLAN -> EXECUTE -> VERIFY -> REPORT -> COMPLETE
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from engine.core.work_requests import WorkRequestRef


_WORKFLOW_RUN_REF_RE = re.compile(r"^WF-[A-Z0-9][A-Z0-9._:-]*$")


class WorkflowStage(str, Enum):
    """Canonical lifecycle stages for one workflow run."""

    PREPARE = "PREPARE"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    VERIFY = "VERIFY"
    REPORT = "REPORT"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


_NEXT_STAGE: dict[WorkflowStage, tuple[WorkflowStage, ...]] = {
    WorkflowStage.PREPARE: (WorkflowStage.PLAN, WorkflowStage.FAILED),
    WorkflowStage.PLAN: (WorkflowStage.EXECUTE, WorkflowStage.FAILED),
    WorkflowStage.EXECUTE: (WorkflowStage.VERIFY, WorkflowStage.FAILED),
    WorkflowStage.VERIFY: (WorkflowStage.REPORT, WorkflowStage.FAILED),
    WorkflowStage.REPORT: (WorkflowStage.COMPLETE, WorkflowStage.FAILED),
    WorkflowStage.COMPLETE: (),
    WorkflowStage.FAILED: (),
}

PRODUCTION_LINE_STEP_TO_STAGE: dict[str, WorkflowStage] = {
    "NONE": WorkflowStage.PREPARE,
    "INIT": WorkflowStage.PREPARE,
    "PLAN": WorkflowStage.PLAN,
    "WORK": WorkflowStage.EXECUTE,
    "VALIDATE": WorkflowStage.VERIFY,
    "REPORT": WorkflowStage.REPORT,
    "DONE": WorkflowStage.COMPLETE,
    "FAILED": WorkflowStage.FAILED,
}

STAGE_TO_PRODUCTION_LINE_STEP: dict[WorkflowStage, str] = {
    WorkflowStage.PREPARE: "INIT",
    WorkflowStage.PLAN: "PLAN",
    WorkflowStage.EXECUTE: "WORK",
    WorkflowStage.VERIFY: "VALIDATE",
    WorkflowStage.REPORT: "REPORT",
    WorkflowStage.COMPLETE: "DONE",
    WorkflowStage.FAILED: "FAILED",
}


def _coerce_stage(stage: WorkflowStage | str) -> WorkflowStage:
    if isinstance(stage, WorkflowStage):
        return stage
    value = stage.strip().upper()
    if value in WorkflowStage.__members__:
        return WorkflowStage[value]
    if value in PRODUCTION_LINE_STEP_TO_STAGE:
        return PRODUCTION_LINE_STEP_TO_STAGE[value]
    raise ValueError(f"unknown workflow stage: {stage!r}")


def can_transition(from_stage: WorkflowStage | str, to_stage: WorkflowStage | str) -> bool:
    """Return whether the canonical workflow transition is legal."""

    current = _coerce_stage(from_stage)
    nxt = _coerce_stage(to_stage)
    return nxt in _NEXT_STAGE[current]


def assert_valid_stage_transition(
    from_stage: WorkflowStage | str,
    to_stage: WorkflowStage | str,
) -> None:
    """Raise `ValueError` unless a canonical transition is legal."""

    current = _coerce_stage(from_stage)
    nxt = _coerce_stage(to_stage)
    if can_transition(current, nxt):
        return
    allowed = ", ".join(s.value for s in _NEXT_STAGE[current]) or "(terminal)"
    raise ValueError(
        f"illegal workflow transition {current.value} -> {nxt.value}; "
        f"allowed: {allowed}"
    )


def stage_from_production_line_step(step: str) -> WorkflowStage:
    """Map a current production-line status step to the canonical workflow stage."""

    value = step.strip().upper()
    try:
        return PRODUCTION_LINE_STEP_TO_STAGE[value]
    except KeyError as exc:
        raise ValueError(f"unknown production-line workflow step: {step!r}") from exc


def stage_to_production_line_step(stage: WorkflowStage | str) -> str:
    """Map a canonical stage back to the current production-line status vocabulary."""

    canonical = _coerce_stage(stage)
    try:
        return STAGE_TO_PRODUCTION_LINE_STEP[canonical]
    except KeyError as exc:
        raise ValueError(f"unknown workflow stage: {stage!r}") from exc


def canonicalize_production_line_step(step: str) -> str:
    """Return the normalized production-line step name, accepting canonical stage names too."""

    value = step.strip().upper()
    if value in PRODUCTION_LINE_STEP_TO_STAGE:
        return value
    return stage_to_production_line_step(value)


@dataclass(frozen=True)
class WorkflowRunRef:
    """Stable internal reference for one workflow run, for example `WF-T-123-20260520`."""

    value: str

    def __post_init__(self) -> None:
        value = self.value.strip().upper()
        if not _WORKFLOW_RUN_REF_RE.match(value):
            raise ValueError(f"invalid WorkflowRunRef: {self.value!r}")
        object.__setattr__(self, "value", value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class WorkflowStageTransition:
    """A legal transition recorded by the domain model."""

    from_stage: WorkflowStage
    to_stage: WorkflowStage
    note: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


@dataclass
class WorkflowRun:
    """Domain representation of one executable workflow lifecycle."""

    ref: WorkflowRunRef
    work_request_ref: WorkRequestRef
    stage: WorkflowStage = WorkflowStage.PREPARE
    transitions: list[WorkflowStageTransition] = field(default_factory=list)

    @property
    def terminal(self) -> bool:
        return self.stage in {WorkflowStage.COMPLETE, WorkflowStage.FAILED}

    def can_advance_to(self, stage: WorkflowStage | str) -> bool:
        return can_transition(self.stage, stage)

    def advance_to(self, stage: WorkflowStage | str, *, note: str = "") -> None:
        nxt = _coerce_stage(stage)
        assert_valid_stage_transition(self.stage, nxt)
        self.transitions.append(
            WorkflowStageTransition(
                from_stage=self.stage,
                to_stage=nxt,
                note=note.strip(),
            )
        )
        self.stage = nxt

    @classmethod
    def from_production_line_status(
        cls,
        *,
        run_ref: WorkflowRunRef,
        work_request_ref: WorkRequestRef,
        status: dict[str, Any],
    ) -> "WorkflowRun":
        """Build a domain run from the current production-line `status.json` shape."""

        raw_stage = status.get("workflow_stage") or status.get("workflow_step") or "NONE"
        run = cls(
            ref=run_ref,
            work_request_ref=work_request_ref,
            stage=_coerce_stage(str(raw_stage)),
        )
        for item in status.get("transitions", []):
            if not isinstance(item, dict):
                continue
            raw_from = item.get("from_stage") or item.get("from") or "NONE"
            raw_to = item.get("to_stage") or item.get("to") or "NONE"
            run.transitions.append(
                WorkflowStageTransition(
                    from_stage=_coerce_stage(str(raw_from)),
                    to_stage=_coerce_stage(str(raw_to)),
                    note=str(item.get("note") or "").strip(),
                    created_at=str(item.get("ts") or item.get("created_at") or ""),
                )
            )
        return run
