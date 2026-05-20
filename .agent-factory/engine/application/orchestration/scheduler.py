"""Stage scheduling primitives for orchestration."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Iterable, Protocol, TypeVar

from engine.core.workflows import WorkflowRun, WorkflowStage


T = TypeVar("T")


class StageHandlerLike(Protocol):
    def execute(self, run: WorkflowRun, stage: WorkflowStage) -> T:
        """Execute one workflow stage."""


@dataclass(frozen=True)
class SequentialStageScheduler:
    """Default scheduler for one stage at a time.

    The bounded `map_parallel` helper is the application-level parallelism seam
    used by later orchestration extraction without coupling workflow rules to
    threads or provider adapters.
    """

    max_parallel: int = 1

    def execute(
        self,
        handler: StageHandlerLike[T],
        run: WorkflowRun,
        stage: WorkflowStage,
    ) -> T:
        return handler.execute(run, stage)

    def map_parallel(self, items: Iterable[T]) -> list[T]:
        values = list(items)
        if self.max_parallel <= 1 or len(values) <= 1:
            return values
        with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
            return list(executor.map(lambda item: item, values))

