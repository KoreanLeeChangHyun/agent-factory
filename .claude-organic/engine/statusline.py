#!/usr/bin/env -S python3 -u
# /// script
# requires-python = ">=3.8"
# dependencies = []
# ///
"""
Claude Code Statusline - Context Usage Progress Bar

stdin으로 JSON 데이터를 받아 컨텍스트 사용률 프로그레스 바를 stdout으로 출력합니다.
외부 의존성 없이 Python 3.8+ 표준 라이브러리만 사용합니다.

CCWO의 설계 패턴을 참고하되, 우리 시스템(.workflow/ 기반)에 맞게 재작성했습니다.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# -- sys.path 보장: data.constants import를 위해 scripts/ 디렉터리 추가 --
_engine_dir = os.path.dirname(os.path.abspath(__file__))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from constants import STEP_COLORS, PHASE_COLORS, C_RESET  # noqa: E402

# -- RESET alias (기존 코드 하위 호환) --
RESET = C_RESET


def format_tokens(tokens: int) -> str:
    """Format token count with k/M suffixes.

    Args:
        tokens: Raw token count.

    Returns:
        Human-readable string with k or M suffix (e.g. '12k', '1.5M').
    """
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

    Uses current_usage tokens for the actual count and used_percentage
    for the percentage, matching the CLI's native display.

    Args:
        data: Parsed JSON from stdin.

    Returns:
        Tuple of (usage_percentage, used_tokens, max_tokens).
    """
    ctx = data.get("context_window", {})
    ctx_size = ctx.get("context_window_size", 0)

    if not ctx_size:
        return 0.0, 0, 200_000

    # Token count: always from current_usage (actual values, not reverse-calculated)
    usage = ctx.get("current_usage")
    tokens = 0
    if usage:
        tokens = (
            usage.get("input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
        )

    # Percentage: prefer CLI's pre-calculated value, fallback to manual calc
    pre_pct = ctx.get("used_percentage")
    if pre_pct is not None:
        pct = float(pre_pct)
    elif tokens and ctx_size:
        pct = tokens * 100 / ctx_size
    else:
        pct = 0.0

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
    .workflow/ directories for workflow entries whose status.json
    contains the current session ID in either the ``session_id`` field
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

    # 디렉터리 스캔으로 활성 워크플로우 조회
    try:
        _engine_dir_local = os.path.dirname(os.path.abspath(__file__))
        if _engine_dir_local not in sys.path:
            sys.path.insert(0, _engine_dir_local)
        from common import scan_active_workflows
        workflows = scan_active_workflows(project_root=cwd)
    except Exception:
        return None

    if not workflows:
        return None

    for _key, entry in workflows.items():
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
        phase = entry.get("step") or entry.get("phase", "")
        command = entry.get("command", "")
        agent = ""

        ctx_path = os.path.join(cwd, work_dir, ".context.json")
        try:
            with open(ctx_path, "r", encoding="utf-8") as f:
                ctx = json.load(f)
            agent = ctx.get("agent", "")
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

        # Read tasks progress from status.json
        tasks = status.get("tasks", {})

        if title or phase:
            return {
                "title": title,
                "step": phase,
                "command": command,
                "agent": agent,
                "tasks": tasks,
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
    model = re.sub(r"\s*\(.*?\)", "", model)

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
        phase = wf.get("step", "")
        title = wf.get("title", "")
        # Truncate title to 30 chars
        if len(title) > 30:
            title = title[:30] + "..."
        # Step color
        phase_color = STEP_COLORS.get(phase, "\033[90m")
        if phase:
            agent = wf.get("agent", "")
            tasks = wf.get("tasks", {})
            # Show progress in WORK phase when tasks info is available
            progress = ""
            if phase == "WORK" and tasks:
                worker_tasks = {
                    k: v for k, v in tasks.items()
                    if re.match(r'^W\d+', k)
                }
                if worker_tasks:
                    completed = sum(
                        1 for t in worker_tasks.values()
                        if isinstance(t, dict) and t.get("status") == "completed"
                    )
                    total = len(worker_tasks)
                    progress = f"{completed}/{total}"

            if progress and agent:
                workflow_display = f" {phase_color}[{phase}:{progress}:{agent}]{RESET} {title}"
            elif progress:
                workflow_display = f" {phase_color}[{phase}:{progress}]{RESET} {title}"
            elif agent:
                workflow_display = f" {phase_color}[{phase}:{agent}]{RESET} {title}"
            else:
                workflow_display = f" {phase_color}[{phase}]{RESET} {title}"
        elif title:
            workflow_display = f" \033[90m{title}{RESET}"

    # -- Board port --
    board_port = ""
    if cwd:
        url_file = Path(cwd) / ".claude-organic" / ".board.url"
        try:
            from urllib.parse import urlparse
            board_url = url_file.read_text(encoding="utf-8").strip().split('\n')[0]
            parsed_port = urlparse(board_url).port
            if parsed_port:
                board_port = str(parsed_port)
        except (FileNotFoundError, OSError, ValueError):
            pass

    port_display = f" port:{board_port}" if board_port else ""

    # -- Output --
    # Format: model [PHASE:agent] title branch ctx:bar port:NNNN
    line = (
        f"\033[36m{model}\033[0m"
        f"{workflow_display}"
        f"{branch_display}"
        f" {progress_bar}"
        f"{port_display}"
    )
    print(line)


if __name__ == "__main__":
    main()
