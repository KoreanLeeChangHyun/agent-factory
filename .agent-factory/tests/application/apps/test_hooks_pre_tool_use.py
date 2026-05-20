"""Tests for PreToolUse hook app entrypoint."""

from __future__ import annotations

import json
import subprocess

from engine.apps.hooks import pre_tool_use


def test_pre_tool_use_run_returns_default_allow_for_unhandled_tool(monkeypatch) -> None:
    monkeypatch.setattr(pre_tool_use, "load_env_flags", lambda: {})

    exit_code, output = pre_tool_use.run(b'{"tool_name":"Read"}')
    payload = json.loads(output)

    assert exit_code == 0
    assert payload["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_pre_tool_use_run_short_circuits_rules_auto_approve(monkeypatch) -> None:
    allow = b'{"hookSpecificOutput":{"permissionDecision":"allow"}}'
    calls: list[str] = []

    def fake_dispatch(flag_name, _script_path, _stdin_data, flags=None, capture_output=False):
        calls.append(flag_name)
        return subprocess.CompletedProcess([flag_name], 0, stdout=allow)

    monkeypatch.setattr(pre_tool_use, "load_env_flags", lambda: {"HOOK_RULES_AUTO_APPROVE": True})
    monkeypatch.setattr(pre_tool_use, "scripts_dir", lambda *parts: "/agent/engine/" + "/".join(parts))
    monkeypatch.setattr(pre_tool_use, "dispatch", fake_dispatch)

    exit_code, output = pre_tool_use.run(b'{"tool_name":"Write","tool_input":{"file_path":".claude/rules/x.md"}}')

    assert exit_code == 0
    assert output == allow
    assert calls == ["HOOK_RULES_AUTO_APPROVE"]


def test_pre_tool_use_run_returns_first_deny_and_records_metrics(monkeypatch) -> None:
    deny = (
        b'{"hookSpecificOutput":{"permissionDecision":"deny",'
        b'"permissionDecisionReason":"blocked"}}'
    )
    metrics: list[tuple[str, str, str, object]] = []

    def fake_dispatch(flag_name, _script_path, _stdin_data, flags=None, capture_output=False):
        stdout = deny if flag_name == "HOOK_DANGEROUS_COMMAND" else b""
        return subprocess.CompletedProcess([flag_name], 0, stdout=stdout)

    monkeypatch.setattr(pre_tool_use, "load_env_flags", lambda: {"HOOK_DANGEROUS_COMMAND": True})
    monkeypatch.setattr(pre_tool_use, "scripts_dir", lambda *parts: "/agent/engine/" + "/".join(parts))
    monkeypatch.setattr(pre_tool_use, "dispatch", fake_dispatch)
    monkeypatch.setattr(
        pre_tool_use,
        "_record_tool_deny_metrics",
        lambda tool_name, tool_use_id, reason, tool_input: metrics.append(
            (tool_name, tool_use_id, reason, tool_input)
        ),
    )

    exit_code, output = pre_tool_use.run(
        b'{"tool_name":"Bash","tool_use_id":"u1","tool_input":{"command":"rm -rf /"}}'
    )

    assert exit_code == 0
    assert output == deny
    assert metrics == [("Bash", "u1", "blocked", {"command": "rm -rf /"})]


def test_pre_tool_use_run_dispatches_slack_ask_async(monkeypatch) -> None:
    calls: list[tuple[str, str, bytes, dict[str, bool] | None]] = []
    stdin_data = b'{"tool_name":"AskUserQuestion"}'

    def fake_dispatch_async(flag_name, script_path, data, flags=None):
        calls.append((flag_name, script_path, data, flags))

    monkeypatch.setattr(pre_tool_use, "load_env_flags", lambda: {"HOOK_SLACK_ASK": True})
    monkeypatch.setattr(pre_tool_use, "scripts_dir", lambda *parts: "/agent/engine/" + "/".join(parts))
    monkeypatch.setattr(pre_tool_use, "dispatch_async", fake_dispatch_async)

    exit_code, output = pre_tool_use.run(stdin_data)

    assert exit_code == 0
    assert json.loads(output)["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert calls == [
        (
            "HOOK_SLACK_ASK",
            "/agent/engine/adapters/slack/slack_ask.py",
            stdin_data,
            {"HOOK_SLACK_ASK": True},
        )
    ]
