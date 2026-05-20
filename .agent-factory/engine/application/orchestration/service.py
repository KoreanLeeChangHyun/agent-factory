"""Application orchestration service for WorkflowRun execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from engine.core.workflows import WorkflowRun, WorkflowRunRef, WorkflowStage

from .retry import RetryPolicy
from .scheduler import SequentialStageScheduler


WORKFLOW_STAGE_ORDER: tuple[WorkflowStage, ...] = (
    WorkflowStage.PREPARE,
    WorkflowStage.PLAN,
    WorkflowStage.EXECUTE,
    WorkflowStage.VERIFY,
    WorkflowStage.REPORT,
    WorkflowStage.COMPLETE,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class StageResult:
    """Result returned by a stage handler."""

    ok: bool
    message: str = ""

    @classmethod
    def pass_(cls, message: str = "") -> "StageResult":
        return cls(ok=True, message=message)

    @classmethod
    def fail(cls, message: str = "") -> "StageResult":
        return cls(ok=False, message=message)


@dataclass(frozen=True)
class ArtifactRecord:
    """Artifact indexed for a workflow run manifest."""

    path: str
    kind: str
    stage: WorkflowStage
    sha256: str | None = None


@dataclass(frozen=True)
class StageExecution:
    """One stage attempt recorded in the run manifest."""

    stage: WorkflowStage
    attempt: int
    outcome: str
    message: str = ""
    created_at: str = field(default_factory=_now)


@dataclass
class RunManifest:
    """Reviewable index of orchestration attempts and artifacts."""

    run_ref: WorkflowRunRef
    stage_executions: list[StageExecution] = field(default_factory=list)
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    status: str = "running"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def record_execution(self, execution: StageExecution) -> None:
        self.stage_executions.append(execution)
        self.updated_at = _now()

    def add_artifacts(self, artifacts: list[ArtifactRecord]) -> None:
        self.artifacts.extend(artifacts)
        self.updated_at = _now()


@dataclass(frozen=True)
class LifecycleEvent:
    """Lifecycle event emitted by orchestration."""

    name: str
    run_ref: WorkflowRunRef
    stage: WorkflowStage | None = None
    attempt: int | None = None
    message: str = ""
    created_at: str = field(default_factory=_now)


class StageHandler(Protocol):
    def execute(self, run: WorkflowRun, stage: WorkflowStage) -> StageResult:
        """Execute one workflow stage using application ports."""


class StageScheduler(Protocol):
    def execute(
        self,
        handler: StageHandler,
        run: WorkflowRun,
        stage: WorkflowStage,
    ) -> StageResult:
        """Schedule one stage execution."""


class ArtifactStore(Protocol):
    def index(self, run_ref: WorkflowRunRef, stage: WorkflowStage) -> list[ArtifactRecord]:
        """Return artifacts produced by a completed stage."""


class ManifestStore(Protocol):
    def save(self, manifest: RunManifest) -> None:
        """Persist a run manifest."""


class LifecycleEventSink(Protocol):
    def publish(self, event: LifecycleEvent) -> None:
        """Publish a lifecycle event."""


class OrchestrationFailed(RuntimeError):
    """Raised when a stage exhausts its retry policy."""


@dataclass
class OrchestrationService:
    """Run the canonical workflow lifecycle through injected ports."""

    handler: StageHandler
    artifact_store: ArtifactStore
    manifest_store: ManifestStore
    event_sink: LifecycleEventSink
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    scheduler: StageScheduler = field(default_factory=SequentialStageScheduler)

    def execute(self, run: WorkflowRun) -> RunManifest:
        if run.stage is not WorkflowStage.PREPARE:
            raise ValueError("orchestration must start from PREPARE")

        manifest = RunManifest(run_ref=run.ref)
        self.event_sink.publish(LifecycleEvent("run.started", run.ref, run.stage))
        self.manifest_store.save(manifest)

        for index, stage in enumerate(WORKFLOW_STAGE_ORDER):
            self._execute_stage(run, manifest, stage)
            if stage is not WorkflowStage.COMPLETE:
                run.advance_to(WORKFLOW_STAGE_ORDER[index + 1])

        manifest.status = "complete"
        manifest.updated_at = _now()
        self.event_sink.publish(LifecycleEvent("run.completed", run.ref, run.stage))
        self.manifest_store.save(manifest)
        return manifest

    def _execute_stage(
        self,
        run: WorkflowRun,
        manifest: RunManifest,
        stage: WorkflowStage,
    ) -> None:
        if run.stage is not stage:
            raise ValueError(f"expected stage {stage.value}, got {run.stage.value}")

        attempt = 1
        while True:
            self.event_sink.publish(LifecycleEvent("stage.started", run.ref, stage, attempt))
            result = self.scheduler.execute(self.handler, run, stage)
            outcome = "ok" if result.ok else "fail"
            manifest.record_execution(
                StageExecution(
                    stage=stage,
                    attempt=attempt,
                    outcome=outcome,
                    message=result.message,
                )
            )

            if result.ok:
                artifacts = self.artifact_store.index(run.ref, stage)
                manifest.add_artifacts(artifacts)
                self.event_sink.publish(
                    LifecycleEvent("stage.completed", run.ref, stage, attempt, result.message)
                )
                self.manifest_store.save(manifest)
                return

            self.event_sink.publish(
                LifecycleEvent("stage.failed", run.ref, stage, attempt, result.message)
            )
            if not self.retry_policy.can_retry(stage, attempt):
                run.advance_to(WorkflowStage.FAILED, note=result.message)
                manifest.status = "failed"
                manifest.updated_at = _now()
                self.event_sink.publish(
                    LifecycleEvent("run.failed", run.ref, run.stage, attempt, result.message)
                )
                self.manifest_store.save(manifest)
                raise OrchestrationFailed(
                    f"{stage.value} failed after {attempt} attempt(s): {result.message}"
                )
            attempt += 1
