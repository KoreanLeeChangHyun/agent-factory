"""PreToolUse hook app entrypoint."""

from __future__ import annotations

import json
import os
import sys

from engine.adapters.hooks.dispatcher import (
    dispatch,
    dispatch_async,
    load_env_flags,
    scripts_dir,
)

_ENGINE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
GUARDED_TOOLS = (*WRITE_TOOLS, "Bash")


def _get_metrics_work_dir() -> str | None:
    """Extract the metrics work directory from workflow environment variables."""
    for key in ("WORKFLOW_WORK_DIR", "_WF_WORK_DIR"):
        val = os.environ.get(key, "").strip()
        if val and os.path.isdir(val):
            return val
    return None


def _record_tool_deny_metrics(
    tool_name: str,
    tool_use_id: str,
    reason: str,
    tool_input: object,
) -> None:
    """Record a tool.deny metrics event without affecting hook behavior."""
    try:
        work_dir = _get_metrics_work_dir()
        if not work_dir:
            return

        input_summary = ""
        try:
            if tool_input is not None:
                raw = (
                    tool_input
                    if isinstance(tool_input, str)
                    else json.dumps(tool_input, ensure_ascii=False)
                )
                input_summary = raw[:500]
        except Exception:  # noqa: BLE001
            pass

        from flow.metrics import append_event

        append_event(
            work_dir,
            "tool.deny",
            {
                "tool_name": tool_name,
                "tool_use_id": tool_use_id,
                "reason": reason,
                "input_summary": input_summary,
            },
        )
    except Exception:  # noqa: BLE001
        pass


def _dispatch_guard(
    flag_name: str,
    script_parts: tuple[str, ...],
    stdin_data: bytes,
    flags: dict,
):
    return dispatch(
        flag_name,
        scripts_dir(*script_parts),
        stdin_data,
        flags=flags,
        capture_output=True,
    )


def _record_deny_from_result(tool_name: str, payload: dict, stdout: bytes) -> None:
    try:
        deny_reason = ""
        try:
            deny_data = json.loads(stdout)
            hook_out = deny_data.get("hookSpecificOutput", {})
            deny_reason = hook_out.get("permissionDecisionReason", "")
        except Exception:  # noqa: BLE001
            pass
        if not deny_reason:
            deny_reason = "guard denied"
        tool_use_id_str = payload.get("tool_use_id", "") or ""
        tool_input_val = payload.get("tool_input")
        _record_tool_deny_metrics(tool_name, tool_use_id_str, deny_reason, tool_input_val)
    except Exception:  # noqa: BLE001
        pass


def run(stdin_data: bytes) -> tuple[int, bytes]:
    """Dispatch PreToolUse hook behavior and return ``(exit_code, stdout)``."""
    try:
        payload = json.loads(stdin_data)
    except (json.JSONDecodeError, ValueError):
        return 0, b""

    tool_name = payload.get("tool_name", "")
    flags = load_env_flags()
    sync_results = []

    if tool_name in WRITE_TOOLS:
        result = _dispatch_guard(
            "HOOK_RULES_AUTO_APPROVE",
            ("guards", "rules_auto_approve.py"),
            stdin_data,
            flags,
        )
        if result is not None and result.stdout and b"allow" in result.stdout:
            return 0, result.stdout

    if tool_name in GUARDED_TOOLS:
        sync_results.append(
            _dispatch_guard(
                "HOOK_HOOKS_SELF_PROTECT",
                ("guards", "hooks_self_guard.py"),
                stdin_data,
                flags,
            )
        )

    if tool_name == "AskUserQuestion":
        dispatch_async(
            "HOOK_SLACK_ASK",
            scripts_dir("slack", "slack_ask.py"),
            stdin_data,
            flags=flags,
        )

    if tool_name == "Bash":
        for flag_name, script_name in (
            ("HOOK_DANGEROUS_COMMAND", "dangerous_command_guard.py"),
            ("HOOK_DIRECT_PATH_GUARD", "direct_path_guard.py"),
            ("HOOK_MAIN_BRANCH_GUARD", "main_branch_guard.py"),
            ("HOOK_KANBAN_SUBCOMMAND_GUARD", "kanban_subcommand_guard.py"),
            ("HOOK_DONE_RELATION_GUARD", "done_relation_guard.py"),
            ("HOOK_WORKTREE_REMOVE_GUARD", "worktree_remove_guard.py"),
        ):
            sync_results.append(
                _dispatch_guard(flag_name, ("guards", script_name), stdin_data, flags)
            )

    if tool_name in GUARDED_TOOLS:
        for flag_name, script_name in (
            ("HOOK_MAIN_SESSION_GUARD", "main_session_guard.py"),
            ("HOOK_READONLY_SESSION_GUARD", "readonly_session_guard.py"),
            ("HOOK_WORKTREE_PATH_GUARD", "worktree_path_guard.py"),
        ):
            sync_results.append(
                _dispatch_guard(flag_name, ("guards", script_name), stdin_data, flags)
            )

    if tool_name == "Task":
        sync_results.append(
            _dispatch_guard(
                "HOOK_AGENT_INVESTIGATION_GUARD",
                ("guards", "agent_investigation_guard.py"),
                stdin_data,
                flags,
            )
        )

    workflow_pretooluse_result = None

    for result in sync_results:
        if result is not None and result.stdout and b"deny" in result.stdout:
            _record_deny_from_result(tool_name, payload, result.stdout)
            return 0, result.stdout

    if (
        workflow_pretooluse_result is not None
        and workflow_pretooluse_result.stdout
        and b"allow" in workflow_pretooluse_result.stdout
    ):
        return 0, workflow_pretooluse_result.stdout

    allow_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "모든 가드를 통과하였습니다.",
        }
    }
    return 0, json.dumps(allow_payload).encode() + b"\n"


def main() -> int:
    """Read PreToolUse stdin, write hook output, and return the exit code."""
    exit_code, output = run(sys.stdin.buffer.read())
    if output:
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
