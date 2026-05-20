"""SessionStart hook app entrypoint."""

from __future__ import annotations

import os
import subprocess
import sys

from engine.adapters.hooks.dispatcher import (
    _find_project_root,
    collect_exit_codes,
    dispatch,
    load_env_flags,
    scripts_dir,
)


def run(stdin_data: bytes) -> int:
    """Dispatch SessionStart hook behavior and return an exit code."""
    flags = load_env_flags()
    sync_results = []

    r = dispatch(
        "HOOK_BIN_PATH_INJECT",
        scripts_dir("hook-handlers", "ensure_bin_path.sh"),
        stdin_data,
        flags=flags,
        capture_output=True,
    )
    sync_results.append(r)

    r = dispatch(
        "HOOK_SESSION_SYSTEM_PROMPT",
        scripts_dir("flow", "inject_prompt.py"),
        stdin_data,
        flags=flags,
    )
    sync_results.append(r)

    trigger_memory_gc_session()

    return collect_exit_codes(sync_results)


def trigger_memory_gc_session() -> None:
    """Trigger memory GC for session start when the wrapper exists."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or _find_project_root()
    gc_bin = os.path.join(project_dir, ".agent-factory", "bin", "flow-memory-gc")
    if not os.path.isfile(gc_bin):
        return
    try:
        subprocess.Popen(
            [gc_bin, "auto", "--trigger", "session"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        pass


def main() -> int:
    """Read SessionStart stdin and run the hook app."""
    return run(sys.stdin.buffer.read())


if __name__ == "__main__":
    sys.exit(main())
