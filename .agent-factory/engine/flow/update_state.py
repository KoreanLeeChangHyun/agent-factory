#!/usr/bin/env -S python3 -u
"""Workflow status batch update script (router).

Business logic is delegated to four sub-modules, and this file handles CLI argument parsing and
It is only responsible for handler dispatch.

Module division:
    state_machine.py: state transitions, context updates, session links
    core.metrics.usage: Usage tracking, settlement, .usage.md management
    task_tracker.py: Task state management
    adapters.filesystem.settings: Environment variable management

Usage:
  flow-update context <registryKey> <agent>
  flow-update status <registryKey> <toStep>
  flow-update both <registryKey> <agent> <toStep>
  flow-update link-session <registryKey> <sessionId>
  flow-update usage-pending <registryKey> <id>...
  flow-update usage <registryKey> <agent_name> <input_tokens> <output_tokens> [cache_creation] [cache_read] [task_id]
  flow-update usage-finalize <registryKey>
  flow-update usage-regenerate
  flow-update env <registryKey> <set|unset> <key> [value]
  flow-update task-status <registryKey> <status> <id>...
  flow-update task-start <registryKey> <id>...
  flow-update metrics-event <event_type> [--key=value ...]

Exit code:
  Always 0 (non-blocking principle)
"""
from __future__ import annotations

import argparse
import os
import sys

_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import STEP_COLORS, load_json_file, resolve_abs_work_dir, resolve_project_root  # noqa: E402
from flow.cli_utils import build_common_epilog, deprecation_warning, registry_key_type  # noqa: E402
from flow.flow_logger import append_log as _append_log  # noqa: E402
from flow.state_machine import _print_state_banner, update_context, update_status, link_session  # noqa: E402
from core.metrics.usage import usage_pending, usage_record, usage_finalize, usage_regenerate  # noqa: E402
from flow.task_tracker import update_task_status  # noqa: E402
from adapters.filesystem.settings import env_manage  # noqa: E402

# backward compatible alias
PHASE_COLORS: dict[str, str] = STEP_COLORS

SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT: str = resolve_project_root()

# Handler common return types: (banner_from, banner_to, banner_ok)
_HandlerResult = tuple[str | None, str | None, bool]
_NO_BANNER: _HandlerResult = (None, None, False)

# Set of modes for automatic correction of printing order
_VALID_MODES: frozenset[str] = frozenset({
    "context", "status", "both", "link-session",
    "usage-pending", "usage", "usage-finalize", "usage-regenerate",
    "env", "task-status", "task-start", "metrics-event",
})


def resolve_paths(work_dir_arg: str) -> tuple[str, str, str]:
    """Interprets the workDir argument as an absolute path and returns related paths.

    Args:
        work_dir_arg: Work directory argument (registryKey or absolute path)

    Returns:
        (abs_work_dir, local_context, status_file) 3-tuple.
    """
    abs_work_dir: str = resolve_abs_work_dir(work_dir_arg, PROJECT_ROOT)
    local_context: str = os.path.join(abs_work_dir, ".context.json")
    status_file: str = os.path.join(abs_work_dir, "status.json")
    return abs_work_dir, local_context, status_file


def _append_fsm_metrics(abs_work_dir: str, from_step: str, to_step: str) -> None:
    """After successful FSM transition, append step.end{prev} + step.start{next} to metrics.jsonl.

    In case of failure, WARN is output and ignored (non-blocking).

    Args:
        abs_work_dir: Absolute path to the workflow work directory.
        from_step: Previous step name (e.g. "PLAN").
        to_step: Next step name (e.g. "WORK").
    """
    try:
        import time as _time

        try:
            from engine.core import metrics as _metrics_mod
        except ModuleNotFoundError:
            from core import metrics as _metrics_mod  # type: ignore[no-redef]

        # Calculate duration: Refer to the temporary file recorded at step.start
        _tmp_file = os.path.join(abs_work_dir, f".metrics_step_start_{from_step}.tmp")
        _duration_ms: object = None
        if os.path.isfile(_tmp_file):
            try:
                _start_ms = int(open(_tmp_file).read().strip())
                _end_ms = int(_time.time() * 1000)
                _duration_ms = _end_ms - _start_ms
                os.remove(_tmp_file)
            except Exception:
                _duration_ms = None

        # step.end{prev} — The 'step' key in metric event has the same meaning as 'workflow_phase' in status.json (metric event schema BC)
        _metrics_mod.append_event(  # type: ignore[attr-defined]
            abs_work_dir,
            "step.end",
            {
                "step": from_step,
                "duration_ms": _duration_ms,
                "outcome": "ok",
                "source": "fsm",
            },
        )
        # step.start{next} + create temporary file
        _next_tmp = os.path.join(abs_work_dir, f".metrics_step_start_{to_step}.tmp")
        try:
            with open(_next_tmp, "w") as _fp:
                _fp.write(str(int(_time.time() * 1000)))
        except Exception:
            pass
        # step.start{next} — The 'step' key in metric event has the same meaning as 'workflow_phase' in status.json (metric event schema BC)
        _metrics_mod.append_event(  # type: ignore[attr-defined]
            abs_work_dir,
            "step.start",
            {"step": to_step, "source": "fsm"},
        )
    except Exception as _exc:
        import sys as _sys
        print(f"[WARN] _append_fsm_metrics failed: {_exc}", file=_sys.stderr)


def _read_current_step(status_file: str) -> str:
    """Reads the current step from status.json and returns it.

    T-459: workflow_phase single key. step/phase is legacy status.json (pre
    Maintain consistency with the read pattern of state_machine.py:update_status().
    """
    _data = load_json_file(status_file) if os.path.isfile(status_file) else None
    if isinstance(_data, dict):
        return (
            _data.get("workflow_phase")  # single key
            or _data.get("step")          # legacy status.json (pre
            or _data.get("phase", "NONE") # legacy status.json (pre
        )
    return "NONE"


def _check_banner_ok(result: str) -> bool:
    """Whether to display the banner is determined from the state transition result."""
    return not any(x in result for x in ("blocked", "skipped", "failed"))


# ─── Subcommand handler ───────────────────────────────────────────────────────────

def _handle_context(args: argparse.Namespace) -> _HandlerResult:
    """context mode: Update the .context.json agent field."""
    abs_work_dir, local_context, _status_file = resolve_paths(args.registry_key)
    update_context(local_context, args.agent)
    return _NO_BANNER


def _handle_status(args: argparse.Namespace) -> _HandlerResult:
    """status mode: status.json Transitions FSM status."""
    abs_work_dir, _local_context, status_file = resolve_paths(args.registry_key)
    from_step: str = _read_current_step(status_file)
    result: str = update_status(abs_work_dir, status_file, from_step, args.to_step)
    banner_ok = _check_banner_ok(result)
    # When FSM transition is successful, step.end{prev} + step.start{next} metrics append (source: "fsm")
    if banner_ok and from_step != args.to_step:
        _append_fsm_metrics(abs_work_dir, from_step, args.to_step)
    return from_step, args.to_step, banner_ok


def _handle_both(args: argparse.Namespace) -> _HandlerResult:
    """Both mode: Context update + status transition are performed together."""
    abs_work_dir, local_context, status_file = resolve_paths(args.registry_key)
    from_step: str = _read_current_step(status_file)
    update_context(local_context, args.agent)
    result: str = update_status(abs_work_dir, status_file, from_step, args.to_step)
    banner_ok: bool = _check_banner_ok(result)
    if banner_ok:
        _append_log(abs_work_dir, "INFO", f"STATE_BOTH: agent={args.agent} step={from_step}->{args.to_step}")
        # When FSM transition is successful, step.end{prev} + step.start{next} metrics append (source: "fsm")
        if from_step != args.to_step:
            _append_fsm_metrics(abs_work_dir, from_step, args.to_step)
    return from_step, args.to_step, banner_ok


def _handle_link_session(args: argparse.Namespace) -> _HandlerResult:
    """link-session mode: Register the session ID in status.json."""
    _abs_work_dir, _local_context, status_file = resolve_paths(args.registry_key)
    link_session(status_file, args.session_id)
    return _NO_BANNER


def _handle_usage_pending(args: argparse.Namespace) -> _HandlerResult:
    """usage-pending mode: Register agent-task mapping in _pending_workers."""
    abs_work_dir, _local_context, _status_file = resolve_paths(args.registry_key)
    seen: set[str] = set()
    for tid in args.ids:
        if tid not in seen:
            seen.add(tid)
            usage_pending(abs_work_dir, tid, tid)
    return _NO_BANNER


def _handle_usage(args: argparse.Namespace) -> _HandlerResult:
    """usage mode: Records token data for each agent."""
    abs_work_dir, _local_context, _status_file = resolve_paths(args.registry_key)
    cache_creation: str = args.cache_creation or "0"
    cache_read: str = args.cache_read or "0"
    task_id_arg: str = args.task_id or ""
    usage_record(abs_work_dir, args.agent_name, args.input_tokens, args.output_tokens, cache_creation, cache_read, task_id_arg)
    return _NO_BANNER


def _handle_usage_finalize(args: argparse.Namespace) -> _HandlerResult:
    """usage-finalize mode: Calculate totals and update .usage.md."""
    abs_work_dir, _local_context, _status_file = resolve_paths(args.registry_key)
    usage_finalize(abs_work_dir)
    return _NO_BANNER


def _handle_usage_regenerate(args: argparse.Namespace) -> _HandlerResult:
    """usage-regenerate mode: Regenerates the entire .usage.md."""
    usage_regenerate()
    return _NO_BANNER


def _handle_env(args: argparse.Namespace) -> _HandlerResult:
    """env mode: Set/unset .agent-factory/.settings environment variables."""
    resolve_paths(args.registry_key)  # registryKey for validation
    value: str = args.value or ""
    env_manage(args.action, args.key, value)
    return _NO_BANNER


def _handle_task_start(args: argparse.Namespace) -> _HandlerResult:
    """task-start mode: Set the task to running and register usage-pending."""
    abs_work_dir, _local_context, status_file = resolve_paths(args.registry_key)
    seen: set[str] = set()
    for tid in args.ids:
        if tid not in seen:
            seen.add(tid)
            update_task_status(status_file, tid, "running")
            usage_pending(abs_work_dir, tid, tid)
    return _NO_BANNER


def _handle_task_status(args: argparse.Namespace) -> _HandlerResult:
    """task-status mode: Records task status in plural/legacy format."""
    _TS_VALID_STATUSES: set[str] = {"pending", "running", "completed", "failed", "in_progress"}
    _abs_work_dir, _local_context, status_file = resolve_paths(args.registry_key)

    # status_or_id: status if new format, taskId if legacy format
    status_or_id: str = args.status_or_id
    rest: list[str] = args.ids or []

    if status_or_id in _TS_VALID_STATUSES:
        # New format: task-status <registryKey> <status> <id1> [id2] ...
        for tid in rest:
            update_task_status(status_file, tid, status_or_id)
    else:
        # Legacy format: task-status <registryKey> <taskId> <status>
        legacy_status: str = rest[0] if rest else ""
        update_task_status(status_file, status_or_id, legacy_status)
    return _NO_BANNER


def _handle_metrics_event(args: argparse.Namespace) -> _HandlerResult:
    """metrics-event mode: Append a single event to metrics.jsonl.

    banners (flow_step_banner.sh / flow_phase_banner.sh) uses this subcommand.
    Call it to record step.start / step.end / phase.start / phase.end events.

    Argument format:
        flow-update metrics-event <event_type> --key1=value1 --key2=value2 ...

    Payload is delivered in the form of --key=value, and numeric strings are automatically converted to float/int.
    registry_key and work_dir are automatically extracted from environment variables or .context.json.

    Non-blocking: If metrics recording fails, a WARN is output and the process continues.
    """
    event_type: str = args.event_type

    # --registry-key / --registry_key is extracted from kwargs first
    # (named option can be mixed in kwargs by using REMAINDER)
    raw_kwargs: list[str] = list(args.kwargs or [])
    registry_key_from_kwargs: str = ""
    filtered_kwargs: list[str] = []
    for _kv in raw_kwargs:
        _k_part = _kv.lstrip("-").partition("=")[0].replace("-", "_")
        if _k_part in ("registry_key",):
            _v_part = _kv.partition("=")[2]
            if _v_part:
                registry_key_from_kwargs = _v_part
        else:
            filtered_kwargs.append(_kv)

    # --key=value Convert list to payload dict
    payload: dict[str, object] = {}
    for kv in filtered_kwargs:
        if "=" in kv:
            k, _, v = kv.partition("=")
            k = k.lstrip("-")
            # Automatic conversion of numbers: int first → try float
            try:
                payload[k] = int(v)
            except ValueError:
                try:
                    payload[k] = float(v)
                except ValueError:
                    # "true"/"false" → bool conversion
                    if v.lower() == "true":
                        payload[k] = True
                    elif v.lower() == "false":
                        payload[k] = False
                    elif v.lower() == "null":
                        payload[k] = None
                    else:
                        payload[k] = v

    # Work_dir determination: specified arguments → values ​​extracted from kwargs → environment variables
    registry_key: str = (getattr(args, "registry_key", "") or "").strip()
    if not registry_key:
        registry_key = registry_key_from_kwargs
    if not registry_key:
        registry_key = os.environ.get("_WF_REGISTRY_KEY", "")

    try:
        if registry_key:
            abs_work_dir, _, _ = resolve_paths(registry_key)
        else:
            abs_work_dir = os.environ.get("_WF_WORK_DIR", "")

        if not abs_work_dir:
            print("[WARN] metrics-event: work_dir cannot be determined (registry_key not delivered)", file=sys.stderr)
            return _NO_BANNER

        try:
            from engine.core import metrics as _metrics_mod
        except ModuleNotFoundError:
            from core import metrics as _metrics_mod  # type: ignore[no-redef]

        _metrics_mod.append_event(abs_work_dir, event_type, payload)  # type: ignore[attr-defined]
    except Exception as exc:
        print(f"[WARN] metrics-event append failed: {exc}", file=sys.stderr)

    return _NO_BANNER


# ─── Building argparse ─────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    """argparse Builds and returns a parser and subcommand."""
    parser = argparse.ArgumentParser(
        prog="flow-update",
        description="Batch update of workflow status (router)",
        epilog=build_common_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(
        dest="subcommand",
        title="Subcommand",
        description="available modes",
        metavar="<subcommand>",
    )

    # --- context ---
    p_context = subparsers.add_parser(
        "context",
        help="Update .context.json agent field",
        description="context mode: Update the agent field in .context.json.",
    )
    p_context.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS format registry key")
    p_context.add_argument("agent", help="agent name")
    p_context.set_defaults(handler=_handle_context)

    # --- status ---
    p_status = subparsers.add_parser(
        "status",
        help="status.json FSM state transition",
        description="status mode: status.json Transitions FSM status.",
    )
    p_status.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS format registry key")
    p_status.add_argument("to_step", metavar="toStep", help="Target state to transition to")
    p_status.set_defaults(handler=_handle_status)

    # --- both ---
    p_both = subparsers.add_parser(
        "both",
        help="Context update + status transition performed simultaneously",
        description="Both mode: Context update and status transition are performed together.",
    )
    p_both.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS format registry key")
    p_both.add_argument("agent", help="agent name")
    p_both.add_argument("to_step", metavar="toStep", help="Target state to transition to")
    p_both.set_defaults(handler=_handle_both)

    # --- link-session ---
    p_link = subparsers.add_parser(
        "link-session",
        help="Register session ID in status.json",
        description="link-session mode: Register the session ID in status.json.",
    )
    p_link.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS format registry key")
    p_link.add_argument("session_id", metavar="sessionId", help="session id")
    p_link.set_defaults(handler=_handle_link_session)

    # --- usage-pending ---
    p_usage_pending = subparsers.add_parser(
        "usage-pending",
        help="Register usage tracking target (pending worker)",
        description="usage-pending mode: Register agent-task mapping in _pending_workers.",
    )
    p_usage_pending.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS format registry key")
    p_usage_pending.add_argument("ids", nargs="+", metavar="id", help="Task ID (multiple possible)")
    p_usage_pending.set_defaults(handler=_handle_usage_pending)

    # --- usage ---
    p_usage = subparsers.add_parser(
        "usage",
        help="Token data recording per agent",
        description="usage mode: Records token usage data for each agent.",
    )
    p_usage.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS format registry key")
    p_usage.add_argument("agent_name", metavar="agent_name", help="agent name")
    p_usage.add_argument("input_tokens", metavar="input_tokens", help="Number of input tokens")
    p_usage.add_argument("output_tokens", metavar="output_tokens", help="Number of output tokens")
    p_usage.add_argument("cache_creation", nargs="?", default="0", metavar="cache_creation", help="Number of cache creation tokens (default: 0)")
    p_usage.add_argument("cache_read", nargs="?", default="0", metavar="cache_read", help="Number of cache read tokens (default: 0)")
    p_usage.add_argument("task_id", nargs="?", default="", metavar="task_id", help="Task ID (optional)")
    p_usage.set_defaults(handler=_handle_usage)

    # --- usage-finalize ---
    p_usage_finalize = subparsers.add_parser(
        "usage-finalize",
        help="Calculate totals and update .usage.md",
        description="usage-finalize mode: Calculate totals and update .usage.md.",
    )
    p_usage_finalize.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS format registry key")
    p_usage_finalize.set_defaults(handler=_handle_usage_finalize)

    # --- usage-regenerate ---
    p_usage_regenerate = subparsers.add_parser(
        "usage-regenerate",
        help="Regenerate entire .usage.md",
        description="usage-regenerate mode: Regenerates the entire .usage.md.",
    )
    p_usage_regenerate.set_defaults(handler=_handle_usage_regenerate)

    # --- env ---
    p_env = subparsers.add_parser(
        "env",
        help=".settings Environment variable management",
        description="env mode: Set/unset .agent-factory/.settings environment variables.",
    )
    p_env.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS format registry key")
    p_env.add_argument("action", choices=["set", "unset"], help="Action to perform")
    p_env.add_argument("key", metavar="KEY", help="environment variable key")
    p_env.add_argument("value", nargs="?", default="", metavar="VALUE", help="Value to set (used when setting)")
    p_env.set_defaults(handler=_handle_env)

    # --- task-status ---
    p_task_status = subparsers.add_parser(
        "task-status",
        help="Batch change task status",
        description=(
            "task-status mode: Change the task status. \n \n"
            "New format: task-status <registryKey> <status> <id1> [id2] ... \n"
            "Legacy: task-status <registryKey> <taskId> <status>"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_task_status.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS format registry key")
    p_task_status.add_argument("status_or_id", metavar="status_or_id", help="Status (pending|running|completed|failed|in_progress) or legacy task ID")
    p_task_status.add_argument("ids", nargs="*", metavar="id", help="List of task IDs (new format) or status (legacy)")
    p_task_status.set_defaults(handler=_handle_task_status)

    # --- task-start ---
    p_task_start = subparsers.add_parser(
        "task-start",
        help="Set task to running + register usage-pending",
        description="task-start mode: Set the task to running and register usage-pending.",
    )
    p_task_start.add_argument("registry_key", type=registry_key_type, metavar="registryKey", help="YYYYMMDD-HHMMSS format registry key")
    p_task_start.add_argument("ids", nargs="+", metavar="id", help="Task ID (multiple possible)")
    p_task_start.set_defaults(handler=_handle_task_start)

    # --- metrics-event ---
    p_metrics = subparsers.add_parser(
        "metrics-event",
        help="Append single event to metrics.jsonl",
        description=(
            "metrics-event mode: Append an event line to metrics.jsonl. \n \n"
            "Usage: flow-update metrics-event <event_type> [--key=value ...] \n \n"
            "Example: \n"
            "  flow-update metrics-event step.start --step=INIT --source=banner\n"
            "  flow-update metrics-event phase.start --phase_index=1 --total=2\n\n"
            "registry_key is an optional argument, and if not passed, the _WF_REGISTRY_KEY environment variable is used."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_metrics.add_argument(
        "event_type",
        metavar="event_type",
        help="One of 11 catalogs (step.start, step.end, phase.start, phase.end, ...)",
    )
    p_metrics.add_argument(
        "kwargs",
        nargs=argparse.REMAINDER,
        metavar="--key=value",
        help="payload key-value pairs (in --key=value format, plural)",
    )
    p_metrics.add_argument(
        "--registry-key",
        dest="registry_key",
        default="",
        metavar="registryKey",
        help="YYYYMMDD-HHMMSS format registry key (if not delivered, use _WF_REGISTRY_KEY environment variable)",
    )
    p_metrics.set_defaults(handler=_handle_metrics_event)

    return parser


# ─── Backward Compatibility: Automatic correction of printing order ──────────────────────────────────────────────

def _maybe_swap_args(argv: list[str]) -> list[str]:
    """Automatically corrects if the argument order is reversed in a legacy call.

    Existing calling pattern:
        update_state.py <workDir> <mode> [args...] (wrong order)
    Correct pattern:
        update_state.py <mode> <registryKey> [args...]

    If argv[1] is not a valid mode and argv[2] is a valid mode
    Exchanges the two arguments and prints a deprecation warning.

    Args:
        argv: A copy of sys.argv (in-place modification safe).

    Returns:
        Corrected argv list.
    """
    if len(argv) < 3:
        return argv
    arg1, arg2 = argv[1], argv[2]
    if arg1 not in _VALID_MODES and arg2 in _VALID_MODES:
        deprecation_warning(
            f"update_state.py {arg1} {arg2} ... (workDir mode order)",
            f"flow-update {arg2} {arg1} ... (mode registryKey order)",
        )
        result = argv[:]
        result[1], result[2] = arg2, arg1
        return result
    return argv


# ─── main ───────────────────────────────────────────────────────────────────

def main() -> None:
    """Parse the command line arguments and dispatch the appropriate handler."""
    # Backward compatibility: automatic correction of argument order (deprecated)
    corrected_argv: list[str] = _maybe_swap_args(sys.argv[:])

    parser = _build_parser()

    # Safeguard in case argparse is not recognized
    # (Non-blocking principle: exit 0)
    try:
        args = parser.parse_args(corrected_argv[1:])
    except SystemExit as exc:
        # argparse raises SystemExit when --help or error occurs
        # --help is exit(0), error is exit(2)
        # In accordance with the non-blocking principle, even in case of error, it is unified as exit(0)
        if exc.code == 0:
            sys.exit(0)
        sys.exit(0)

    if not hasattr(args, "handler"):
        parser.print_help(sys.stderr)
        sys.exit(0)

    _banner_from, _banner_to, _banner_ok = args.handler(args)

    if _banner_ok and _banner_from and _banner_to:
        abs_work_dir = resolve_abs_work_dir(args.registry_key, PROJECT_ROOT)
        _print_state_banner(_banner_from, _banner_to, abs_work_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()
