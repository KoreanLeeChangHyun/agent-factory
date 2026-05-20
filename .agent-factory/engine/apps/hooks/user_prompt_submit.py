"""UserPromptSubmit hook app entrypoint."""

from __future__ import annotations

import json
import os
import sys


def _debug_log(msg: str) -> None:
    """Append debug logs only when HOOK_USER_PROMPT_DEBUG is enabled."""
    if os.environ.get("HOOK_USER_PROMPT_DEBUG", "").lower() not in ("true", "1", "yes", "on"):
        return
    try:
        project_root = os.environ.get("CLAUDE_PROJECT_DIR")
        if not project_root:
            agent_factory_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..")
            )
            project_root = os.path.dirname(agent_factory_dir)
        log_path = os.path.join(project_root, ".agent-factory", "runs", ".user_prompt_hook.log")
        runs_dir = os.path.dirname(log_path)
        if os.path.isdir(runs_dir):
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
    except Exception:  # noqa: BLE001
        pass


_dispatcher_loaded = False
try:
    from engine.adapters.hooks.dispatcher import (
        collect_exit_codes,
        collect_outputs,
        dispatch,
        load_env_flags,
        scripts_dir,
    )

    _dispatcher_loaded = True
except Exception as _e:  # noqa: BLE001
    _debug_log(f"[user-prompt-submit] dispatcher import failed: {_e}")


def _is_main_session(stdin_data: dict) -> bool:
    """Return True when the prompt belongs to the main session."""
    wf_session_type = os.environ.get("_WF_SESSION_TYPE", "").strip().lower()
    if wf_session_type == "workflow":
        _debug_log("[user-prompt-submit] guard: _WF_SESSION_TYPE=workflow -> not main")
        return False
    if wf_session_type == "main":
        _debug_log("[user-prompt-submit] guard: _WF_SESSION_TYPE=main -> main")
        return True

    cwd = stdin_data.get("cwd", "") or ""
    cwd_norm = cwd.replace("\\", "/")
    if "/.agent-factory/worktrees/" in cwd_norm:
        _debug_log(f"[user-prompt-submit] guard: cwd contains worktrees/ -> not main: {cwd!r}")
        return False

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if project_dir and cwd:
        worktree_abs = os.path.join(project_dir, ".agent-factory", "worktrees")
        cwd_abs = os.path.abspath(cwd)
        try:
            if os.path.commonpath([cwd_abs, worktree_abs]) == worktree_abs:
                _debug_log(
                    "[user-prompt-submit] guard: cwd under CLAUDE_PROJECT_DIR/worktrees "
                    f"-> not main: {cwd!r}"
                )
                return False
        except (ValueError, OSError):
            pass

    transcript_path = stdin_data.get("transcript_path", "") or ""
    if transcript_path:
        check_dir = os.path.dirname(transcript_path)
        for _ in range(5):
            if not check_dir or check_dir == os.path.dirname(check_dir):
                break
            context_json = os.path.join(check_dir, "implement", ".context.json")
            if os.path.isfile(context_json):
                _debug_log(f"[user-prompt-submit] guard: .context.json found -> not main: {context_json!r}")
                return False
            direct_context = os.path.join(check_dir, ".context.json")
            if os.path.isfile(direct_context):
                _debug_log(
                    f"[user-prompt-submit] guard: .context.json found (direct) -> not main: {direct_context!r}"
                )
                return False
            check_dir = os.path.dirname(check_dir)

    if "/.agent-factory/runs/" in cwd_norm:
        _debug_log(f"[user-prompt-submit] guard: cwd contains /runs/ -> not main: {cwd!r}")
        return False

    _debug_log(f"[user-prompt-submit] guard: no worktree/workflow signals -> assuming main: {cwd!r}")
    return True


def run(stdin_raw: bytes) -> tuple[int, bytes]:
    """Dispatch UserPromptSubmit behavior and return ``(exit_code, stdout)``."""
    try:
        try:
            stdin_data: dict = json.loads(stdin_raw) if stdin_raw else {}
        except (json.JSONDecodeError, ValueError):
            stdin_data = {}

        _debug_log(
            "[user-prompt-submit] "
            f"hook_event_name={stdin_data.get('hook_event_name')!r} cwd={stdin_data.get('cwd')!r}"
        )

        if not _is_main_session(stdin_data):
            _debug_log("[user-prompt-submit] not main session -> exit 0 (empty stdout)")
            return 0, b""

        if not _dispatcher_loaded:
            _debug_log("[user-prompt-submit] dispatcher not loaded -> exit 0")
            return 0, b""

        flags = load_env_flags()
        target_script = scripts_dir("hook-handlers", "inject_kanban_context.py")
        _debug_log(f"[user-prompt-submit] dispatching to {target_script!r}")

        result = dispatch(
            "HOOK_USER_PROMPT_KANBAN",
            target_script,
            stdin_raw,
            flags=flags,
            capture_output=True,
        )

        output = collect_outputs([result])
        return collect_exit_codes([result]), output

    except Exception as e:  # noqa: BLE001
        _debug_log(f"[user-prompt-submit] unhandled exception: {type(e).__name__}: {e}")
        return 0, b""


def main() -> int:
    """Read UserPromptSubmit stdin, write hook output, and return the exit code."""
    try:
        stdin_raw = sys.stdin.buffer.read()
    except Exception:  # noqa: BLE001
        stdin_raw = b""

    exit_code, output = run(stdin_raw)
    if output:
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
