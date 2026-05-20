from __future__ import annotations

import subprocess
from pathlib import Path

from engine.adapters.llm import codex
from engine.adapters.llm.codex import CodexAdapter
from engine.core.ports.llm import LLMEvent, LLMRequest
from engine.core.workflows import WorkflowStage


def test_codex_adapter_maps_json_events_to_llm_result(monkeypatch, tmp_path: Path) -> None:
    captured: dict = {}

    def fake_subprocess_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured.update(kwargs)
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=(
                '{"type":"message","text":"plan ready"}\n'
                '{"type":"result","message":"done"}\n'
            ),
            stderr="",
        )

    monkeypatch.setattr(codex.subprocess, "run", fake_subprocess_run)
    seen: list[LLMEvent] = []

    result = CodexAdapter(codex_bin="codex-test").complete(
        LLMRequest(
            prompt="make a plan",
            system_prompt="system",
            cwd=tmp_path,
            stage=WorkflowStage.PLAN,
            session_id="wf-1",
        ),
        on_event=seen.append,
    )

    assert result.ok
    assert result.output_text == "plan readydone"
    assert result.metadata["provider"] == "codex"
    assert captured["cmd"][:2] == ["codex-test", "exec"]
    assert "--json" in captured["cmd"]
    assert captured["input"] == "system\n\nmake a plan"
    assert captured["cwd"] == str(tmp_path)
    assert seen == [
        LLMEvent(type="message", text="plan ready", raw={"type": "message", "text": "plan ready"}),
        LLMEvent(type="result", text="done", raw={"type": "result", "message": "done"}),
    ]


def test_codex_adapter_controlled_plan_smoke(monkeypatch, tmp_path: Path) -> None:
    def fake_subprocess_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout='{"type":"message","text":"PLAN smoke ok"}\n',
            stderr="",
        )

    monkeypatch.setattr(codex.subprocess, "run", fake_subprocess_run)

    result = CodexAdapter(codex_bin="codex-test").complete(
        LLMRequest(prompt="write plan smoke", cwd=tmp_path, stage=WorkflowStage.PLAN)
    )

    assert result.ok
    assert "PLAN smoke ok" in result.output_text
