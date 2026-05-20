"""PostToolUse hook app entrypoint."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

from engine.adapters.hooks.dispatcher import (
    dispatch_async,
    load_env_flags,
    scripts_dir,
)

_ENGINE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from flow.session_identifier import WINDOW_PREFIX_P  # noqa: E402


def _get_metrics_work_dir() -> str | None:
    """Extract the metrics work directory from workflow environment variables."""
    for key in ("WORKFLOW_WORK_DIR", "_WF_WORK_DIR"):
        val = os.environ.get(key, "").strip()
        if val and os.path.isdir(val):
            return val
    return None


def _append_metrics_event(event_type: str, payload: dict) -> None:
    """Append a metrics event without allowing metrics failures to affect hooks."""
    try:
        work_dir = _get_metrics_work_dir()
        if not work_dir:
            return
        from flow.metrics import append_event

        append_event(work_dir, event_type, payload)
    except Exception:  # noqa: BLE001
        pass


def _handle_bash_flow_end(tool_input: dict) -> None:
    """Handle delayed workflow session cleanup when ``flow-claude end`` is used."""
    command: str = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not re.search(r"(?:^|[;&|]\s*)flow-claude\s+end\b", command):
        return

    session_id: str | None = os.environ.get("_WF_SESSION_ID")
    server_port: str | None = os.environ.get("_WF_SERVER_PORT")

    if session_id and server_port:
        port = server_port
        sid = session_id
        python_cmd = (
            "import time,urllib.request,json; "
            "time.sleep(5); "
            "urllib.request.urlopen("
            "urllib.request.Request("
            f"'http://127.0.0.1:{port}/terminal/workflow/kill', "
            f"data=json.dumps({{'session_id':'{sid}'}}).encode(), "
            "headers={'Content-Type':'application/json'}, "
            "method='POST'))"
        )
        subprocess.Popen(
            ["python3", "-c", python_cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return

    tmux_pane: str | None = os.environ.get("TMUX_PANE")
    if not tmux_pane:
        return

    try:
        result = subprocess.run(
            ["tmux", "display-message", "-t", tmux_pane, "-p", "#W"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        window_name: str = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return

    if not window_name.startswith(f"{WINDOW_PREFIX_P}T-"):
        return

    pane_target: str = shlex.quote(tmux_pane)
    bash_cmd: str = f"sleep 5 && tmux kill-window -t {pane_target}"

    subprocess.Popen(
        ["bash", "-c", bash_cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def run(stdin_data: bytes) -> int:
    """Dispatch PostToolUse hook behavior and return an exit code."""
    try:
        payload = json.loads(stdin_data)
        if not isinstance(payload, dict):
            return 0
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    _record_tool_call_metrics(tool_name, payload)

    if tool_name == "Bash":
        _handle_bash_flow_end(tool_input)
        return 0

    if tool_name == "Task":
        return 0

    file_path = tool_input.get("file_path", "") if isinstance(tool_input, dict) else ""
    if not file_path:
        return 0

    flags = load_env_flags()

    if tool_name in ("Write", "Edit"):
        if ".claude/skills/" in file_path and file_path.endswith("/SKILL.md"):
            dispatch_async(
                "HOOK_CATALOG_SYNC",
                scripts_dir("adapters", "sync", "catalog_sync.py"),
                stdin_data,
                flags=flags,
            )

    return 0


def _record_tool_call_metrics(tool_name: str, payload: dict) -> None:
    """Record tool.call metrics for PostToolUse payloads when timing exists."""
    try:
        tool_use_id: str = payload.get("tool_use_id", "") or ""
        parent_tool_use_id: str | None = payload.get("parent_tool_use_id") or None
        duration_ms: int | None = payload.get("duration_ms")

        if duration_ms is None:
            return

        tool_input = payload.get("tool_input")
        tool_result = payload.get("tool_result")
        bytes_in: int | None = None
        bytes_out: int | None = None
        try:
            if tool_input is not None:
                bytes_in = len(json.dumps(tool_input, ensure_ascii=False))
        except Exception:  # noqa: BLE001
            pass
        try:
            if tool_result is not None:
                bytes_out = len(json.dumps(tool_result, ensure_ascii=False))
        except Exception:  # noqa: BLE001
            pass

        tool_call_payload: dict = {
            "tool_name": tool_name,
            "tool_use_id": tool_use_id,
            "duration_ms": int(duration_ms),
            "allowed": True,
        }
        if parent_tool_use_id:
            tool_call_payload["parent_tool_use_id"] = parent_tool_use_id
        if bytes_in is not None:
            tool_call_payload["bytes_in"] = bytes_in
        if bytes_out is not None:
            tool_call_payload["bytes_out"] = bytes_out

        _append_metrics_event("tool.call", tool_call_payload)

        if tool_name == "Task":
            _record_subagent_metrics(tool_use_id, parent_tool_use_id, duration_ms, payload)

    except Exception:  # noqa: BLE001
        pass


def _record_subagent_metrics(
    tool_use_id: str,
    parent_tool_use_id: str | None,
    duration_ms: int,
    payload: dict,
) -> None:
    """Record subagent.spawn and subagent.end metrics for Task tool payloads."""
    try:
        tool_input = payload.get("tool_input") or {}
        tool_result = payload.get("tool_result")

        agent_kind: str = "unknown"
        if isinstance(tool_input, dict):
            subagent_type = tool_input.get("subagent_type", "")
            if subagent_type and isinstance(subagent_type, str):
                agent_kind = subagent_type.strip()
            else:
                desc = tool_input.get("description", "")
                if desc and isinstance(desc, str):
                    first_word = desc.strip().split()[0] if desc.strip() else "unknown"
                    agent_kind = first_word[:64]

        spawn_payload: dict = {
            "agent_kind": agent_kind,
            "parent_tool_use_id": parent_tool_use_id or "",
        }
        if isinstance(tool_input, dict) and "task_index" in tool_input:
            spawn_payload["task_index"] = tool_input["task_index"]
        _append_metrics_event("subagent.spawn", spawn_payload)

        stdout_tail = ""
        try:
            if tool_result is not None:
                result_str = (
                    tool_result
                    if isinstance(tool_result, str)
                    else json.dumps(tool_result, ensure_ascii=False)
                )
                stdout_tail = result_str[-500:]
        except Exception:  # noqa: BLE001
            pass

        outcome = "ok"
        try:
            if tool_result is not None:
                result_str = (
                    tool_result
                    if isinstance(tool_result, str)
                    else json.dumps(tool_result, ensure_ascii=False)
                )
                if "error" in result_str.lower()[:200]:
                    outcome = "fail"
        except Exception:  # noqa: BLE001
            pass

        end_payload: dict = {
            "agent_kind": agent_kind,
            "tool_use_id": tool_use_id,
            "duration_ms": int(duration_ms),
            "outcome": outcome,
            "stdout_tail": stdout_tail,
        }
        _append_metrics_event("subagent.end", end_payload)

    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    """Read PostToolUse stdin and run the hook app."""
    return run(sys.stdin.buffer.read())


if __name__ == "__main__":
    sys.exit(main())
