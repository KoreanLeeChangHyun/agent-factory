#!/usr/bin/env -S python3 -u
"""SubagentStop event dispatcher.

Dispatches subagent-stop hooks based on HOOK_* flags in .claude.env.
Replaces individual wrapper scripts in .claude/hooks/subagent-stop/.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dispatcher import (
    load_env_flags,
    dispatch_async,
    scripts_dir,
)


def main() -> None:
    """Dispatch subagent-stop hooks for each registered async hook.

    Reads raw stdin data and dispatches async fire-and-forget hooks.
    All hooks in this dispatcher are async; exits with 0 unconditionally.
    """
    stdin_data = sys.stdin.buffer.read()
    flags = load_env_flags()

    # usage-tracker (async)
    dispatch_async(
        'HOOK_USAGE_TRACKER',
        scripts_dir('sync', 'usage_sync.py'),  # subcmd: track (default)
        stdin_data,
        flags=flags,
    )

    # usage-jsonl-sync: 워크플로우 종료 시 전체 JSONL 일괄 파싱 (async)
    # finalization.py(flow-finish)에서 직접 호출하므로 subagent-stop에서는 비활성
    # (done 에이전트 제거로 subagent-stop 트리거 경로 사용하지 않음)

    # All hooks are async/fire-and-forget, no exit code aggregation needed
    sys.exit(0)


if __name__ == '__main__':
    main()
