from __future__ import annotations

from engine.application.llm import FakeAdapter, LLMEvent, LLMRequest, LLMResult


def test_fake_adapter_records_requests_and_emits_events() -> None:
    seen: list[LLMEvent] = []
    adapter = FakeAdapter(
        results=[
            LLMResult(
                ok=True,
                output_text="done",
                events=[LLMEvent(type="assistant", text="hello")],
            )
        ]
    )

    result = adapter.complete(LLMRequest(prompt="work"), on_event=seen.append)

    assert result.ok
    assert result.output_text == "done"
    assert adapter.requests == [LLMRequest(prompt="work")]
    assert seen == [LLMEvent(type="assistant", text="hello")]

