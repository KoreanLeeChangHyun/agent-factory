from __future__ import annotations

from pathlib import Path

from engine.adapters.llm import claude
from engine.adapters.llm.claude import ClaudeAdapter
from engine.core.ports.llm import LLMEvent, LLMRequest
from engine.core.workflows import WorkflowStage
from engine.apps.production_line._spawn import SpawnResult


def test_claude_adapter_maps_request_to_existing_spawn(monkeypatch, tmp_path: Path) -> None:
    captured: dict = {}

    def fake_spawn_claude(**kwargs):
        captured.update(kwargs)
        if kwargs["on_line"] is not None:
            kwargs["on_line"](
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "text", "text": "hello"}]},
                }
            )
        return SpawnResult(
            returncode=0,
            stdout="hello",
            stderr="",
            terminal_reason="completed",
        )

    monkeypatch.setattr(claude, "spawn_claude", fake_spawn_claude)
    seen: list[LLMEvent] = []

    result = ClaudeAdapter().complete(
        LLMRequest(
            prompt="prompt",
            system_prompt="system",
            session_id="uuid-x",
            cwd=tmp_path,
            stage=WorkflowStage.EXECUTE,
        ),
        on_event=seen.append,
    )

    assert result.ok
    assert result.output_text == "hello"
    assert result.terminal_reason == "completed"
    assert captured["prompt_body"] == "prompt"
    assert captured["system_prompt"] == "system"
    assert captured["session_id"] == "uuid-x"
    assert captured["cwd"] == tmp_path
    assert captured["step"] == "WORK"
    assert seen == [
        LLMEvent(
            type="assistant",
            text="hello",
            raw={
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "hello"}]},
            },
        )
    ]
