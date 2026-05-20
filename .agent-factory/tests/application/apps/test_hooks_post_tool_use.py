"""Tests for PostToolUse hook app entrypoint."""

from __future__ import annotations

import json

from engine.apps.hooks import post_tool_use


def test_post_tool_use_run_ignores_invalid_json(monkeypatch) -> None:
    monkeypatch.setattr(post_tool_use, "_record_tool_call_metrics", lambda *_args: None)

    assert post_tool_use.run(b"{not-json") == 0


def test_post_tool_use_run_handles_bash_flow_end(monkeypatch) -> None:
    calls: list[dict] = []
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "flow-claude end"},
    }

    monkeypatch.setattr(post_tool_use, "_record_tool_call_metrics", lambda *_args: None)
    monkeypatch.setattr(post_tool_use, "_handle_bash_flow_end", lambda tool_input: calls.append(tool_input))

    assert post_tool_use.run(json.dumps(payload).encode()) == 0
    assert calls == [{"command": "flow-claude end"}]


def test_post_tool_use_run_dispatches_skill_catalog_sync(monkeypatch) -> None:
    calls: list[tuple[str, str, bytes, dict[str, bool] | None]] = []
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/.claude/skills/demo/SKILL.md"},
    }
    stdin_data = json.dumps(payload).encode()

    def fake_scripts_dir(*parts: str) -> str:
        return "/agent/engine/" + "/".join(parts)

    def fake_dispatch_async(hook_flag_name, script_path, data, flags=None):
        calls.append((hook_flag_name, script_path, data, flags))

    monkeypatch.setattr(post_tool_use, "_record_tool_call_metrics", lambda *_args: None)
    monkeypatch.setattr(post_tool_use, "load_env_flags", lambda: {"HOOK_CATALOG_SYNC": True})
    monkeypatch.setattr(post_tool_use, "scripts_dir", fake_scripts_dir)
    monkeypatch.setattr(post_tool_use, "dispatch_async", fake_dispatch_async)

    assert post_tool_use.run(stdin_data) == 0
    assert calls == [
        (
            "HOOK_CATALOG_SYNC",
            "/agent/engine/sync/catalog_sync.py",
            stdin_data,
            {"HOOK_CATALOG_SYNC": True},
        )
    ]


def test_post_tool_use_run_skips_non_skill_paths(monkeypatch) -> None:
    calls: list[tuple] = []
    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": "/repo/README.md"},
    }

    monkeypatch.setattr(post_tool_use, "_record_tool_call_metrics", lambda *_args: None)
    monkeypatch.setattr(post_tool_use, "load_env_flags", lambda: {"HOOK_CATALOG_SYNC": True})
    monkeypatch.setattr(post_tool_use, "dispatch_async", lambda *args, **kwargs: calls.append(args))

    assert post_tool_use.run(json.dumps(payload).encode()) == 0
    assert calls == []


def test_post_tool_use_records_task_subagent_metrics(monkeypatch) -> None:
    events: list[tuple[str, dict]] = []
    payload = {
        "tool_name": "Task",
        "tool_use_id": "task-1",
        "parent_tool_use_id": "parent-1",
        "duration_ms": 42,
        "tool_input": {"subagent_type": "worker", "task_index": 2},
        "tool_result": "done",
    }

    monkeypatch.setattr(post_tool_use, "_append_metrics_event", lambda event_type, data: events.append((event_type, data)))

    assert post_tool_use.run(json.dumps(payload).encode()) == 0
    assert [event_type for event_type, _data in events] == [
        "tool.call",
        "subagent.spawn",
        "subagent.end",
    ]
    assert events[1][1]["agent_kind"] == "worker"
    assert events[2][1]["tool_use_id"] == "task-1"
