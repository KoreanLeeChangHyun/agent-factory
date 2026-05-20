"""Retry policy for workflow orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.core.workflows import WorkflowStage


@dataclass(frozen=True)
class RetryPolicy:
    """Deterministic retry limits keyed by workflow stage.

    Values are retry counts after the first attempt. A value of 2 means the
    stage can run at most three times.
    """

    max_retries_by_stage: dict[WorkflowStage, int] = field(default_factory=dict)
    default_max_retries: int = 0

    def max_retries_for(self, stage: WorkflowStage) -> int:
        value = self.max_retries_by_stage.get(stage, self.default_max_retries)
        return max(0, int(value))

    def can_retry(self, stage: WorkflowStage, failed_attempts: int) -> bool:
        return failed_attempts <= self.max_retries_for(stage)

