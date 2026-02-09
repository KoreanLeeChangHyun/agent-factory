#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Claude Code Statusline - Context Usage Progress Bar

stdin으로 JSON 데이터를 받아 컨텍스트 사용률 프로그레스 바를 stdout으로 출력합니다.
외부 의존성 없이 Python 3.12+ 표준 라이브러리만 사용합니다.

CCWO의 설계 패턴을 참고하되, 우리 시스템(.workflow/ 기반)에 맞게 재작성했습니다.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


# -- Phase color mapping (ANSI codes) --
PHASE_COLORS: dict[str, str] = {
    "INIT":     "\033[31m",        # Red
    "PLAN":     "\033[34m",        # Blue
    "WORK":     "\033[32m",        # Green
    "REPORT":   "\033[35m",        # Magenta
}
RESET = "\033[0m"


def format_tokens(tokens: int) -> str:
    """Format token count with k/M suffixes."""
    if tokens >= 1_000_000:
        val = f"{tokens / 1_000_000:.1f}M"
        return val.replace(".0M", "M")
    if tokens >= 1_000:
        return f"{tokens // 1_000}k"
    return str(tokens)


def create_progress_bar(usage_pct: float, used: int, limit: int) -> str:
    """Create a colored progress bar for context usage.

    Args:
        usage_pct: Usage percentage (0-100+).
        used: Used token count.
        limit: Maximum token count.

    Returns:
        ANSI-colored progress bar string.
    """
    pct = max(0, min(100, int(usage_pct)))

    filled = pct * 20 // 100
    empty = 20 - filled

    bar = "\u2588" * filled + "\u2591" * empty

    fmt_used = format_tokens(used)
    fmt_limit = format_tokens(limit)

    # Color thresholds: <40% green, 40-60% yellow, 60-70% orange, >=70% red
    if pct >= 70:
        color = "\033[31m"   # Red
    elif pct >= 60:
        color = "\033[33m"   # Orange/Yellow
    elif pct >= 40:
        color = "\033[93m"   # Bright Yellow
    else:
        color = "\033[32m"   # Green

    return f"{color}[{bar}] {usage_pct:.1f}% ({fmt_used}/{fmt_limit}){RESET}"


def get_context_usage(data: dict) -> tuple[float, int, int]:
    """Calculate context usage from stdin JSON data.

    Uses the context_window field provided by Claude Code's statusline system.

    Args:
        data: Parsed JSON from stdin.

    Returns:
        Tuple of (usage_percentage, used_tokens, max_tokens).
    """
    ctx = data.get("context_window", {})
    ctx_size = ctx.get("context_window_size", 0)
    usage = ctx.get("current_usage")

    if not usage or not ctx_size:
        return 0.0, 0, ctx_size or 200_000

    tokens = (
        usage.get("input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
    )

    pct = tokens * 100 / ctx_size if ctx_size else 0.0
    return pct, tokens, ctx_size


def get_git_branch(cwd: str) -> str:
    """Get current git branch name.

    Args:
        cwd: Current working directory for git command.

    Returns:
        Branch name or empty string.
    """
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            if len(branch) > 60:
                branch = branch[:60] + "..."
            return branch
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return ""


def get_active_workflow(cwd: str) -> dict | None:
    """Read active workflow info filtered by the current session.

    Reads CLAUDE_SESSION_ID from the environment, then scans
    registry.json for workflow entries whose status.json contains
    the current session ID in either the ``session_id`` field
    (orchestrator) or the ``linked_sessions`` array (workers/reporters).

    If CLAUDE_SESSION_ID is not set or no matching workflow is found,
    returns None so that no workflow info is displayed.

    Args:
        cwd: Current working directory (project root).

    Returns:
        Dict with keys (title, phase, command, agent) or None if no
        matching workflow found for the current session.
    """
    current_session = os.environ.get("CLAUDE_SESSION_ID", "")
    if not current_session:
        return None

    registry_path = os.path.join(cwd, ".workflow", "registry.json")
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None

    if not isinstance(registry, dict):
        return None

    for _key, entry in registry.items():
        work_dir = entry.get("workDir", "")
        if not work_dir:
            continue

        # Read status.json to check session ownership
        status_path = os.path.join(cwd, work_dir, "status.json")
        try:
            with open(status_path, "r", encoding="utf-8") as f:
                status = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue

        # Match: current session is the orchestrator or a linked worker/reporter
        orchestrator_sid = status.get("session_id", "")
        linked = status.get("linked_sessions", [])
        if current_session != orchestrator_sid and current_session not in linked:
            continue

        title = entry.get("title", "")
        phase = entry.get("phase", "")
        command = entry.get("command", "")
        agent = ""

        ctx_path = os.path.join(cwd, work_dir, ".context.json")
        try:
            with open(ctx_path, "r", encoding="utf-8") as f:
                ctx = json.load(f)
            agent = ctx.get("agent", "")
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

        if title or phase:
            return {
                "title": title,
                "phase": phase,
                "command": command,
                "agent": agent,
            }

    return None


def main() -> None:
    """Main entry point.

    Reads JSON from stdin, computes context usage, and prints
    a single-line or two-line statusline to stdout.
    """
    data: dict = {}
    if not sys.stdin.isatty():
        try:
            data = json.loads(sys.stdin.read())
        except (json.JSONDecodeError, ValueError):
            pass

    # -- Model --
    model = data.get("model", {}).get("display_name", "?")

    # -- Lines added/removed --
    cost = data.get("cost", {})
    added = cost.get("total_lines_added", 0)
    removed = cost.get("total_lines_removed", 0)

    # -- Context usage --
    usage_pct, used_tokens, max_tokens = get_context_usage(data)
    progress_bar = create_progress_bar(usage_pct, used_tokens, max_tokens)

    # -- Git branch --
    cwd = data.get("workspace", {}).get("current_dir", "")
    branch = get_git_branch(cwd) if cwd else ""
    branch_display = f" \033[33m{branch}\033[0m" if branch else ""

    # -- Active workflow --
    wf = get_active_workflow(cwd) if cwd else None
    workflow_display = ""
    if wf:
        phase = wf.get("phase", "")
        title = wf.get("title", "")
        # Truncate title to 30 chars
        if len(title) > 30:
            title = title[:30] + "..."
        # Phase color
        phase_color = PHASE_COLORS.get(phase, "\033[90m")
        if phase:
            agent = wf.get("agent", "")
            if agent:
                workflow_display = f" {phase_color}[{phase}:{agent}]{RESET} {title}"
            else:
                workflow_display = f" {phase_color}[{phase}]{RESET} {title}"
        elif title:
            workflow_display = f" \033[90m{title}{RESET}"

    # -- Output --
    # Format: model [PHASE:agent] title branch ctx:bar +added/-removed
    line = (
        f"\033[36m{model}\033[0m"
        f"{workflow_display}"
        f"{branch_display}"
        f" {progress_bar}"
        f" \033[32m+{added}\033[0m/\033[31m-{removed}\033[0m"
    )
    print(line)


if __name__ == "__main__":
    main()
