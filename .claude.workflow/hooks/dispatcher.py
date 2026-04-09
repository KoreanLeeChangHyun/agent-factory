"""Dispatcher common utilities for Claude Code hooks.

Provides shared functions for loading .claude.workflow/.settings
flags and dispatching hook scripts based on HOOK_* environment variable toggles.

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
    """Find project root by locating .claude.workflow directory.

    워크트리에서 실행 시 메인 리포 루트를 반환한다.
    .claude.workflow/.settings는 메인 리포에만 존재하므로,
    git-common-dir로 메인 리포를 탐색한다.

    Returns:
        Absolute path to the project root directory.
    """
    d = os.path.dirname(os.path.abspath(__file__))
    # .claude.workflow/hooks/dispatcher.py -> project root is ../..
    root = os.path.normpath(os.path.join(d, '..', '..'))

    # 메인 리포이면 그대로 반환 (.settings 존재 확인)
    cw_dir = os.path.join(root, '.claude.workflow')
    if os.path.exists(os.path.join(cw_dir, '.settings')):
        return root

    # 워크트리일 수 있음 — git-common-dir로 메인 리포 탐색
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'],
            capture_output=True, text=True, timeout=5, cwd=root,
        )
        if result.returncode == 0:
            git_common = result.stdout.strip()
            # git-common-dir은 메인 리포의 .git 디렉터리를 가리킴
            main_root = os.path.dirname(git_common)
            main_cw_dir = os.path.join(main_root, '.claude.workflow')
            if os.path.exists(os.path.join(main_cw_dir, '.settings')):
                return main_root
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return root


def _env_path() -> str:
    """Return path to the settings file (.settings).

    Returns:
        Absolute path to .claude.workflow/.settings.
    """
    return os.path.join(_find_project_root(), '.claude.workflow', '.settings')


def load_env_flags(prefix: str = 'HOOK_') -> dict[str, bool]:
    """Parse .claude.workflow/.settings and return HOOK_* flags as a dict.

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


def _find_workflow_log(log_dir: str | None = None) -> str | None:
    """활성 워크플로우의 workflow.log 경로를 탐색하여 반환한다.

    Args:
        log_dir: 명시적 로그 디렉터리 경로. None이면 scan_active_workflows로 자동 탐색.

    Returns:
        workflow.log 파일의 절대 경로. 찾지 못하면 None.
    """
    try:
        if log_dir is not None:
            candidate = os.path.join(log_dir, "workflow.log") if not log_dir.endswith("workflow.log") else log_dir
            if os.path.isfile(candidate) or os.path.isdir(os.path.dirname(candidate)):
                return candidate

        scripts_path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
        from common import scan_active_workflows, resolve_project_root  # noqa: PLC0415
        project_root = resolve_project_root()
        workflows = scan_active_workflows(project_root=project_root)
        if workflows:
            for _key, entry in workflows.items():
                if isinstance(entry, dict) and "workDir" in entry:
                    rel = entry["workDir"]
                    abs_wd = os.path.join(project_root, rel) if not os.path.isabs(rel) else rel
                    if os.path.isdir(abs_wd):
                        return os.path.join(abs_wd, "workflow.log")
    except Exception:
        pass
    return None


def dispatch_async(
    hook_flag_name: str,
    script_path: str,
    stdin_data: bytes,
    flags: dict[str, bool] | None = None,
    log_dir: str | None = None,
) -> subprocess.Popen | None:
    """Dispatch to an external script asynchronously (fire-and-forget).

    Args:
        hook_flag_name: HOOK_* flag name controlling this hook.
        script_path: Absolute path to the target Python script.
        stdin_data: bytes to pass as stdin to the subprocess.
        flags: Pre-loaded flags dict (loads from env if None).
        log_dir: Optional directory path for workflow.log redirection.
            If None, the active workflow log is located automatically via
            scan_active_workflows. Falls back to DEVNULL if no log is found.

    Returns:
        subprocess.Popen object, or None if disabled/missing.
    """
    if flags is None:
        flags = load_env_flags()

    if not is_enabled(flags, hook_flag_name):
        return None

    if not os.path.exists(script_path):
        return None

    log_path = _find_workflow_log(log_dir)
    if log_path is not None:
        try:
            stderr_target = open(log_path, "a", encoding="utf-8")  # noqa: WPS515
        except OSError:
            stderr_target = subprocess.DEVNULL
    else:
        stderr_target = subprocess.DEVNULL

    try:
        proc = subprocess.Popen(
            [sys.executable, script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=stderr_target,
        )
    finally:
        if stderr_target is not subprocess.DEVNULL:
            stderr_target.close()

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
    """Return absolute path under .claude.workflow/scripts/.

    Args:
        *parts: Path components after .claude.workflow/scripts/.

    Returns:
        Absolute path string.
    """
    root = _find_project_root()
    return os.path.join(root, '.claude.workflow', 'scripts', *parts)


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
