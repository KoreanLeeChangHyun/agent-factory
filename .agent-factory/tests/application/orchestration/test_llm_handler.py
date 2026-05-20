from __future__ import annotations

from dataclasses import dataclass, field

from engine.core.ports.llm import FakeAdapter, LLMEvent, LLMResult
from engine.application.orchestration import LLMStageHandler, StagePrompt
from engine.application.orchestration.service import LifecycleEvent
from engine.core.work_requests import WorkRequestRef
from engine.core.workflows import WorkflowRun, WorkflowRunRef, WorkflowStage


@dataclass
class FakeEventSink:
    events: list[LifecycleEvent] = field(default_factory=list)

    def publish(self, event: LifecycleEvent) -> None:
        self.events.append(event)


def _run() -> WorkflowRun:
    return WorkflowRun(
        ref=WorkflowRunRef("WF-T-123-20260520-000000"),
        work_request_ref=WorkRequestRef.parse("T-123"),
    )


def test_llm_stage_handler_uses_injected_fake_adapter_for_llm_stages() -> None:
    adapter = FakeAdapter(
        results=[
            LLMResult(
                ok=True,
                output_text="planned",
                events=[LLMEvent(type="assistant", text="planning")],
            )
        ]
    )
    events = FakeEventSink()
    handler = LLMStageHandler(
        adapter=adapter,
        prompts={WorkflowStage.PLAN: StagePrompt("make a plan", "system")},
        event_sink=events,
    )

    result = handler.execute(_run(), WorkflowStage.PLAN)

    assert result.ok
    assert result.message == "planned"
    assert adapter.requests[0].prompt == "make a plan"
    assert adapter.requests[0].system_prompt == "system"
    assert adapter.requests[0].stage is WorkflowStage.PLAN
    assert events.events[0].name == "llm.event"
    assert events.events[0].message == "planning"


def test_llm_stage_handler_keeps_driver_stages_out_of_adapter() -> None:
    adapter = FakeAdapter()
    handler = LLMStageHandler(adapter=adapter, prompts={})

    result = handler.execute(_run(), WorkflowStage.PREPARE)

    assert result.ok
    assert adapter.requests == []
