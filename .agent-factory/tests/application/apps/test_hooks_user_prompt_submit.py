"""Tests for UserPromptSubmit hook app entrypoint."""

from __future__ import annotations

import json
import subprocess

from engine.apps.hooks import user_prompt_submit


def test_user_prompt_submit_run_skips_workflow_session(monkeypatch) -> None:
    monkeypatch.setenv("_WF_SESSION_TYPE", "workflow")

    exit_code, output = user_prompt_submit.run(
        json.dumps({"hook_event_name": "UserPromptSubmit", "cwd": "/repo"}).encode()
    )

    assert exit_code == 0
    assert output == b""


def test_user_prompt_submit_run_dispatches_context_for_main_session(monkeypatch) -> None:
    calls: list[tuple[str, str, bytes, bool]] = []
    stdin_raw = json.dumps({"hook_event_name": "UserPromptSubmit", "cwd": "/repo"}).encode()

    def fake_scripts_dir(*parts: str) -> str:
        return "/agent/engine/" + "/".join(parts)

    def fake_dispatch(hook_flag_name, script_path, data, flags=None, capture_output=False):
        calls.append((hook_flag_name, script_path, data, capture_output))
        return subprocess.CompletedProcess([script_path], 0, stdout=b"context")

    monkeypatch.delenv("_WF_SESSION_TYPE", raising=False)
    monkeypatch.setattr(user_prompt_submit, "_dispatcher_loaded", True)
    monkeypatch.setattr(user_prompt_submit, "load_env_flags", lambda: {"HOOK_USER_PROMPT_KANBAN": True})
    monkeypatch.setattr(user_prompt_submit, "scripts_dir", fake_scripts_dir)
    monkeypatch.setattr(user_prompt_submit, "dispatch", fake_dispatch)
    monkeypatch.setattr(user_prompt_submit, "collect_outputs", lambda results: results[0].stdout)
    monkeypatch.setattr(user_prompt_submit, "collect_exit_codes", lambda _results: 0)

    exit_code, output = user_prompt_submit.run(stdin_raw)

    assert exit_code == 0
    assert output == b"context"
    assert calls == [
        (
            "HOOK_USER_PROMPT_KANBAN",
            "/agent/engine/apps/hooks/inject_kanban_context.py",
            stdin_raw,
            True,
        )
    ]


def test_user_prompt_submit_run_degrades_when_dispatcher_unavailable(monkeypatch) -> None:
    monkeypatch.delenv("_WF_SESSION_TYPE", raising=False)
    monkeypatch.setattr(user_prompt_submit, "_dispatcher_loaded", False)

    exit_code, output = user_prompt_submit.run(
        json.dumps({"hook_event_name": "UserPromptSubmit", "cwd": "/repo"}).encode()
    )

    assert exit_code == 0
    assert output == b""
