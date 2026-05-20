"""LLM-backed stage handler for orchestration services."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.core.ports.llm import LLMAdapter, LLMEvent, LLMRequest
from engine.core.workflows import WorkflowRun, WorkflowStage

from .service import LifecycleEvent, LifecycleEventSink, StageResult


@dataclass(frozen=True)
class StagePrompt:
    """Prompt pair used for one LLM-backed workflow stage."""

    prompt: str
    system_prompt: str = ""


@dataclass
class LLMStageHandler:
    """Stage handler that delegates LLM-backed stages to an injected adapter."""

    adapter: LLMAdapter
    prompts: dict[WorkflowStage, StagePrompt]
    event_sink: LifecycleEventSink | None = None
    llm_stages: set[WorkflowStage] = field(
        default_factory=lambda: {
            WorkflowStage.PLAN,
            WorkflowStage.EXECUTE,
            WorkflowStage.REPORT,
        }
    )

    def execute(self, run: WorkflowRun, stage: WorkflowStage) -> StageResult:
        if stage not in self.llm_stages:
            return StageResult.pass_(f"{stage.value} driver stage")

        prompt = self.prompts.get(stage)
        if prompt is None:
            return StageResult.fail(f"missing LLM prompt for {stage.value}")

        def _publish(event: LLMEvent) -> None:
            if self.event_sink is None:
                return
            self.event_sink.publish(
                LifecycleEvent(
                    "llm.event",
                    run.ref,
                    stage,
                    message=event.text or event.type,
                )
            )

        result = self.adapter.complete(
            LLMRequest(
                prompt=prompt.prompt,
                system_prompt=prompt.system_prompt,
                session_id=str(run.ref),
                stage=stage,
            ),
            on_event=_publish,
        )
        if result.ok:
            return StageResult.pass_(result.output_text)
        return StageResult.fail(result.error or f"{stage.value} adapter failed")
