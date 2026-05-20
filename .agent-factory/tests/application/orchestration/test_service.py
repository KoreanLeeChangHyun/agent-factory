from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from engine.application.orchestration import (
    ArtifactRecord,
    LifecycleEvent,
    OrchestrationFailed,
    OrchestrationService,
    RetryPolicy,
    RunManifest,
    StageResult,
)
from engine.core.work_requests import WorkRequestRef
from engine.core.workflows import WorkflowRun, WorkflowRunRef, WorkflowStage


def _run() -> WorkflowRun:
    return WorkflowRun(
        ref=WorkflowRunRef("WF-T-123-20260520-000000"),
        work_request_ref=WorkRequestRef.parse("T-123"),
    )


@dataclass
class FakeHandler:
    failures: dict[WorkflowStage, int] = field(default_factory=dict)
    calls: list[WorkflowStage] = field(default_factory=list)

    def execute(self, run: WorkflowRun, stage: WorkflowStage) -> StageResult:
        self.calls.append(stage)
        remaining = self.failures.get(stage, 0)
        if remaining > 0:
            self.failures[stage] = remaining - 1
            return StageResult.fail(f"{stage.value} failed")
        return StageResult.pass_(f"{stage.value} ok")


@dataclass
class FakeArtifactStore:
    def index(self, run_ref: WorkflowRunRef, stage: WorkflowStage) -> list[ArtifactRecord]:
        return [
            ArtifactRecord(
                path=f"{run_ref.value}/{stage.value.lower()}.txt",
                kind="text",
                stage=stage,
            )
        ]


@dataclass
class FakeManifestStore:
    saved: list[RunManifest] = field(default_factory=list)

    def save(self, manifest: RunManifest) -> None:
        self.saved.append(manifest)


@dataclass
class FakeEventSink:
    events: list[LifecycleEvent] = field(default_factory=list)

    def publish(self, event: LifecycleEvent) -> None:
        self.events.append(event)


def _service(handler: FakeHandler) -> tuple[OrchestrationService, FakeManifestStore, FakeEventSink]:
    manifests = FakeManifestStore()
    events = FakeEventSink()
    return (
        OrchestrationService(
            handler=handler,
            artifact_store=FakeArtifactStore(),
            manifest_store=manifests,
            event_sink=events,
        ),
        manifests,
        events,
    )


def test_orchestration_executes_six_stages_in_order_with_fake_ports() -> None:
    handler = FakeHandler()
    service, manifests, events = _service(handler)

    manifest = service.execute(_run())

    assert handler.calls == [
        WorkflowStage.PREPARE,
        WorkflowStage.PLAN,
        WorkflowStage.EXECUTE,
        WorkflowStage.VERIFY,
        WorkflowStage.REPORT,
        WorkflowStage.COMPLETE,
    ]
    assert manifest.status == "complete"
    assert [item.stage for item in manifest.artifacts] == handler.calls
    assert [item.name for item in events.events if item.name == "stage.completed"] == [
        "stage.completed",
        "stage.completed",
        "stage.completed",
        "stage.completed",
        "stage.completed",
        "stage.completed",
    ]
    assert manifests.saved[-1].status == "complete"


def test_retry_policy_retries_failed_stage_without_real_llm_calls() -> None:
    handler = FakeHandler(failures={WorkflowStage.EXECUTE: 2})
    manifests = FakeManifestStore()
    events = FakeEventSink()
    service = OrchestrationService(
        handler=handler,
        artifact_store=FakeArtifactStore(),
        manifest_store=manifests,
        event_sink=events,
        retry_policy=RetryPolicy(max_retries_by_stage={WorkflowStage.EXECUTE: 2}),
    )

    manifest = service.execute(_run())

    execute_attempts = [
        item for item in manifest.stage_executions if item.stage is WorkflowStage.EXECUTE
    ]
    assert [item.outcome for item in execute_attempts] == ["fail", "fail", "ok"]
    assert manifest.status == "complete"


def test_orchestration_fails_when_retry_policy_is_exhausted() -> None:
    handler = FakeHandler(failures={WorkflowStage.VERIFY: 2})
    service, manifests, events = _service(handler)

    with pytest.raises(OrchestrationFailed, match="VERIFY failed after 1 attempt"):
        service.execute(_run())

    assert manifests.saved[-1].status == "failed"
    assert events.events[-1].name == "run.failed"
    assert events.events[-1].stage is WorkflowStage.FAILED


def test_manifest_indexes_artifacts_by_stage() -> None:
    service, _, _ = _service(FakeHandler())

    manifest = service.execute(_run())

    assert len(manifest.artifacts) == 6
    assert manifest.artifacts[0].path.endswith("/prepare.txt")
    assert manifest.artifacts[-1].stage is WorkflowStage.COMPLETE
