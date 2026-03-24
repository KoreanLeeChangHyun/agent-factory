"""Dispatcher common utilities for Claude Code hooks.

Provides shared functions for loading .claude.env flags and dispatching
hook scripts based on HOOK_* environment variable toggles.

현재 등록된 디스패처:
  pre-tool-use.py    - PreToolUse 이벤트
  post-tool-use.py   - PostToolUse 이벤트
  subagent-stop.py   - SubagentStop 이벤트
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Callable


def _find_project_root() -> str:
    """Find project root by locating .claude directory.

    Returns:
        Absolute path to the project root directory.
    """
    d = os.path.dirname(os.path.abspath(__file__))
    # .claude/hooks/dispatcher.py -> project root is ../..
    return os.path.normpath(os.path.join(d, '..', '..'))


def _env_path() -> str:
    """Return path to .claude.env file.

    Returns:
        Absolute path to the .claude.env file.
    """
    return os.path.join(_find_project_root(), '.claude.env')


def load_env_flags(prefix: str = 'HOOK_') -> dict[str, bool]:
    """Parse .claude.env and return HOOK_* flags as a dict.

    Args:
        prefix: Variable name prefix to filter (default: 'HOOK_').

    Returns:
        dict mapping flag names (with prefix) to bool values.
        e.g. {'HOOK_DANGEROUS_COMMAND': False, 'HOOK_SLACK_ASK': True}
    """
    flags: dict[str, bool] = {}
    env_file = _env_path()
    if not os.path.exists(env_file):
        return flags

    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip()
            if not key.startswith(prefix):
                continue
            # Support both true/false strings and legacy 0/1, plus yes/no, on/off
            if value.lower() in ('true', '1', 'yes', 'on'):
                flags[key] = True
            elif value.lower() in ('false', '0', 'no', 'off'):
                flags[key] = False
            else:
                flags[key] = bool(value)
    return flags


def is_enabled(flags: dict[str, bool], hook_flag_name: str) -> bool:
    """Check if a hook is enabled in the flags dict.

    Args:
        flags: Dict from load_env_flags().
        hook_flag_name: Full flag name, e.g. 'HOOK_DANGEROUS_COMMAND'.

    Returns:
        True if enabled (default True if flag is not defined).
    """
    return flags.get(hook_flag_name, True)


def dispatch(
    hook_flag_name: str,
    script_path: str,
    stdin_data: bytes,
    flags: dict[str, bool] | None = None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess | None:
    """Dispatch to an external script if the hook is enabled.

    Args:
        hook_flag_name: HOOK_* flag name controlling this hook.
        script_path: Absolute path to the target Python script.
        stdin_data: bytes to pass as stdin to the subprocess.
        flags: Pre-loaded flags dict (loads from env if None).
        capture_output: If True, capture subprocess stdout/stderr into
            result.stdout / result.stderr instead of inheriting from parent.
            Defaults to False (existing behavior: output passes through).

    Returns:
        subprocess.CompletedProcess result, or None if disabled/missing.
        When capture_output=True, result.stdout contains captured bytes.
    """
    if flags is None:
        flags = load_env_flags()

    if not is_enabled(flags, hook_flag_name):
        return None

    if not os.path.exists(script_path):
        return None

    result = subprocess.run(
        [sys.executable, script_path],
        input=stdin_data,
        capture_output=capture_output,
    )
    return result


def dispatch_async(
    hook_flag_name: str,
    script_path: str,
    stdin_data: bytes,
    flags: dict[str, bool] | None = None,
) -> subprocess.Popen | None:
    """Dispatch to an external script asynchronously (fire-and-forget).

    Args:
        hook_flag_name: HOOK_* flag name controlling this hook.
        script_path: Absolute path to the target Python script.
        stdin_data: bytes to pass as stdin to the subprocess.
        flags: Pre-loaded flags dict (loads from env if None).

    Returns:
        subprocess.Popen object, or None if disabled/missing.
    """
    if flags is None:
        flags = load_env_flags()

    if not is_enabled(flags, hook_flag_name):
        return None

    if not os.path.exists(script_path):
        return None

    proc = subprocess.Popen(
        [sys.executable, script_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        proc.stdin.write(stdin_data)
        proc.stdin.close()
    except BrokenPipeError:
        sys.stderr.write(f"[WARN] dispatch_async: BrokenPipeError for {script_path}\n")
    return proc


def run_inline(
    hook_flag_name: str,
    main_func: Callable[[bytes | str], int],
    stdin_data: bytes | str,
    flags: dict[str, bool] | None = None,
) -> int:
    """Run an inline hook function if enabled.

    Args:
        hook_flag_name: HOOK_* flag name controlling this hook.
        main_func: Callable(stdin_data) -> exit_code (int).
        stdin_data: Data to pass to the function (str or bytes).
        flags: Pre-loaded flags dict (loads from env if None).

    Returns:
        int exit code from main_func, or 0 if disabled.
    """
    if flags is None:
        flags = load_env_flags()

    if not is_enabled(flags, hook_flag_name):
        return 0

    return main_func(stdin_data)


def scripts_dir(*parts: str) -> str:
    """Return absolute path under .claude/scripts/.

    Args:
        *parts: Path components after .claude/scripts/.

    Returns:
        Absolute path string.
    """
    root = _find_project_root()
    return os.path.join(root, '.claude', 'scripts', *parts)


def collect_exit_codes(
    results: list[subprocess.CompletedProcess | subprocess.Popen | int | None],
) -> int:
    """Aggregate exit codes from multiple dispatch results.

    Args:
        results: List of (subprocess.CompletedProcess | subprocess.Popen | None | int).

    Returns:
        0 if all succeeded, otherwise the first non-zero exit code.
    """
    for r in results:
        if r is None:
            continue
        if isinstance(r, int):
            code = r
        elif isinstance(r, subprocess.Popen):
            r.wait()
            code = r.returncode
        else:
            code = r.returncode
        if code != 0:
            return code
    return 0


def collect_outputs(
    results: list[subprocess.CompletedProcess | None],
) -> bytes:
    """Concatenate stdout bytes from multiple CompletedProcess results.

    Intended for use after dispatch() calls with capture_output=True.
    Results that are None or whose .stdout is None are silently skipped.

    Args:
        results: List of subprocess.CompletedProcess (or None) returned by
            dispatch() with capture_output=True.

    Returns:
        Concatenated bytes of all non-None .stdout values.  Returns b'' if
        no result has captured output.
    """
    chunks: list[bytes] = []
    for r in results:
        if r is None:
            continue
        stdout = getattr(r, 'stdout', None)
        if stdout:
            chunks.append(stdout)
    return b''.join(chunks)
