"""Tests for SubagentStop hook app entrypoint."""

from __future__ import annotations

from engine.apps.hooks import subagent_stop


def test_subagent_stop_run_dispatches_usage_tracker(monkeypatch) -> None:
    calls: list[tuple[str, str, bytes, dict[str, bool] | None]] = []
    stdin_data = b'{"hook_event_name":"SubagentStop"}'

    def fake_scripts_dir(*parts: str) -> str:
        return "/agent/engine/" + "/".join(parts)

    def fake_dispatch_async(hook_flag_name, script_path, data, flags=None):
        calls.append((hook_flag_name, script_path, data, flags))

    monkeypatch.setattr(subagent_stop, "load_env_flags", lambda: {"HOOK_USAGE_TRACKER": True})
    monkeypatch.setattr(subagent_stop, "scripts_dir", fake_scripts_dir)
    monkeypatch.setattr(subagent_stop, "dispatch_async", fake_dispatch_async)
    monkeypatch.setattr(subagent_stop, "_log_first_active_workflow_stop_event", lambda: None)
    monkeypatch.setattr(subagent_stop, "_scan_and_trigger_fail_record", lambda _flags: None)

    assert subagent_stop.run(stdin_data) == 0
    assert calls == [
        (
            "HOOK_USAGE_TRACKER",
            "/agent/engine/adapters/sync/usage_sync.py",
            stdin_data,
            {"HOOK_USAGE_TRACKER": True},
        )
    ]


def test_subagent_stop_run_swallows_fail_record_errors(monkeypatch, capsys) -> None:
    monkeypatch.setattr(subagent_stop, "load_env_flags", lambda: {"HOOK_FAIL_RECORD": True})
    monkeypatch.setattr(subagent_stop, "dispatch_async", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(subagent_stop, "_log_first_active_workflow_stop_event", lambda: None)

    def fail_record(_flags):
        raise RuntimeError("boom")

    monkeypatch.setattr(subagent_stop, "_scan_and_trigger_fail_record", fail_record)

    assert subagent_stop.run(b"{}") == 0
    assert "_scan_and_trigger_fail_record top-level failure" in capsys.readouterr().err
