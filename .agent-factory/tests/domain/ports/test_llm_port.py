"""LLM core port contract coverage."""

from __future__ import annotations

from engine.core.ports.llm import FakeAdapter, LLMEvent, LLMRequest, LLMResult


def test_fake_adapter_records_requests_and_replays_events() -> None:
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

    assert result.output_text == "done"
    assert adapter.requests == [LLMRequest(prompt="work")]
    assert seen == [LLMEvent(type="assistant", text="hello")]


def test_application_llm_compat_wrapper_is_removed() -> None:
    import importlib.util

    assert importlib.util.find_spec("engine.application.llm") is None
