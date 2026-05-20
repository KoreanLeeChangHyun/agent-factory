"""SubagentStop hook app entrypoint."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from engine.adapters.hooks.dispatcher import (
    _find_project_root,
    dispatch_async,
    load_env_flags,
    scripts_dir,
)

_ENGINE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)


def _append_log(abs_work_dir: str, level: str, message: str) -> None:
    """Append an event to the workflow log."""
    try:
        kst = timezone(timedelta(hours=9))
        ts = datetime.now(kst).strftime("%Y-%m-%dT%H:%M:%S")
        log_path = os.path.join(abs_work_dir, "workflow.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {message}\n")
    except Exception:  # noqa: BLE001
        pass


def _resolve_fail_record_bin() -> str | None:
    """Return the executable ``flow-fail-record`` path, if available."""
    project_root = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    if not project_root:
        try:
            project_root = _find_project_root()
        except Exception:  # noqa: BLE001
            project_root = ""

    if not project_root:
        return None

    candidate = os.path.join(project_root, ".agent-factory", "bin", "flow-fail-record")
    if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        return candidate
    return None


def _scan_active_workflows() -> tuple[str, dict]:
    """Load active workflow registry entries from the engine common module."""
    from common import resolve_project_root, scan_active_workflows  # noqa: PLC0415

    project_root = resolve_project_root()
    return project_root, scan_active_workflows(project_root=project_root)


def _scan_and_trigger_fail_record(flags: dict) -> None:
    """Trigger non-blocking fail-record processing for failed active workflows."""
    if not flags.get("HOOK_FAIL_RECORD", False):
        return

    bin_path = _resolve_fail_record_bin()
    if bin_path is None:
        return

    try:
        project_root, workflows = _scan_active_workflows()
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"[WARN] subagent-stop fail-record scan failed: {exc}\n")
        return

    if not workflows:
        return

    for registry_key, entry in workflows.items():
        try:
            if not isinstance(entry, dict) or "workDir" not in entry:
                continue
            rel = entry["workDir"]
            abs_wd = rel if os.path.isabs(rel) else os.path.join(project_root, rel)
            if not os.path.isdir(abs_wd):
                continue

            sentinel = os.path.join(abs_wd, ".workflow-failed")
            recorded = os.path.join(abs_wd, ".workflow-failed.recorded")
            if not os.path.isfile(sentinel):
                continue
            if os.path.exists(recorded):
                continue

            try:
                subprocess.Popen(
                    [bin_path, "record", registry_key],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                _append_log(
                    abs_wd,
                    "INFO",
                    f"flow-fail-record dispatched (key={registry_key})",
                )
            except OSError as exc:
                _append_log(abs_wd, "WARN", f"flow-fail-record Popen failed: {exc}")
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(
                f"[WARN] subagent-stop fail-record entry skipped "
                f"(key={registry_key}): {exc}\n"
            )
            continue


def _log_first_active_workflow_stop_event() -> None:
    """Append a best-effort subagent stop event to the first active workflow."""
    try:
        project_root, workflows = _scan_active_workflows()
        if not workflows:
            return
        for entry in workflows.values():
            if isinstance(entry, dict) and "workDir" in entry:
                rel = entry["workDir"]
                abs_work_dir = rel if os.path.isabs(rel) else os.path.join(project_root, rel)
                if os.path.isdir(abs_work_dir):
                    _append_log(abs_work_dir, "INFO", "Subagent stop event dispatched")
                    break
    except Exception:  # noqa: BLE001
        pass


def run(stdin_data: bytes) -> int:
    """Dispatch SubagentStop hook behavior and return an exit code."""
    flags = load_env_flags()

    dispatch_async(
        "HOOK_USAGE_TRACKER",
        scripts_dir("adapters", "sync", "usage_sync.py"),
        stdin_data,
        flags=flags,
    )

    _log_first_active_workflow_stop_event()

    try:
        _scan_and_trigger_fail_record(flags)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"[WARN] _scan_and_trigger_fail_record top-level failure: {exc}\n")

    return 0


def main() -> int:
    """Read SubagentStop stdin and run the hook app."""
    return run(sys.stdin.buffer.read())


if __name__ == "__main__":
    sys.exit(main())
