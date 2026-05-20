"""Tests for SessionStart hook app entrypoint."""

from __future__ import annotations

import subprocess

from engine.apps.hooks import session_start


def test_session_start_run_dispatches_expected_scripts(monkeypatch) -> None:
    calls: list[tuple[str, str, bytes, bool]] = []

    def fake_load_env_flags() -> dict[str, bool]:
        return {"HOOK_BIN_PATH_INJECT": True, "HOOK_SESSION_SYSTEM_PROMPT": True}

    def fake_scripts_dir(*parts: str) -> str:
        return "/agent/engine/" + "/".join(parts)

    def fake_dispatch(hook_flag_name, script_path, stdin_data, flags=None, capture_output=False):
        calls.append((hook_flag_name, script_path, stdin_data, capture_output))
        return subprocess.CompletedProcess([script_path], 0)

    monkeypatch.setattr(session_start, "load_env_flags", fake_load_env_flags)
    monkeypatch.setattr(session_start, "scripts_dir", fake_scripts_dir)
    monkeypatch.setattr(session_start, "dispatch", fake_dispatch)
    monkeypatch.setattr(session_start, "trigger_memory_gc_session", lambda: None)

    assert session_start.run(b'{"hook_event_name":"SessionStart"}') == 0
    assert calls == [
        (
            "HOOK_BIN_PATH_INJECT",
            "/agent/engine/apps/hooks/ensure_bin_path.sh",
            b'{"hook_event_name":"SessionStart"}',
            True,
        ),
        (
            "HOOK_SESSION_SYSTEM_PROMPT",
            "/agent/engine/apps/hooks/inject_prompt.py",
            b'{"hook_event_name":"SessionStart"}',
            False,
        ),
    ]
