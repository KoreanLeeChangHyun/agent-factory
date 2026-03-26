#!/usr/bin/env -S python3 -u
"""SubagentStop event dispatcher.

Dispatches subagent-stop hooks based on HOOK_* flags in .claude.workflow/.settings(.env fallback).
Replaces individual wrapper scripts in .claude.workflow/hooks/subagent-stop/.
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


def _append_log(abs_work_dir: str, level: str, message: str) -> None:
    """워크플로우 로그에 이벤트를 기록한다."""
    try:
        from datetime import datetime, timezone, timedelta
        kst = timezone(timedelta(hours=9))
        ts = datetime.now(kst).strftime("%Y-%m-%dT%H:%M:%S")
        log_path = os.path.join(abs_work_dir, "workflow.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {message}\n")
    except Exception:
        pass


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

    # dispatch_async 호출 직후 활성 워크플로우에 로그 기록 (비차단)
    try:
        _scripts_path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
        if _scripts_path not in sys.path:
            sys.path.insert(0, _scripts_path)
        from common import scan_active_workflows, resolve_project_root
        _project_root = resolve_project_root()
        _workflows = scan_active_workflows(project_root=_project_root)
        if _workflows:
            for _key, _entry in _workflows.items():
                if isinstance(_entry, dict) and "workDir" in _entry:
                    _rel = _entry["workDir"]
                    _abs = os.path.join(_project_root, _rel) if not _rel.startswith("/") else _rel
                    if os.path.isdir(_abs):
                        _append_log(_abs, "INFO", "Subagent stop event dispatched")
                        break
    except Exception:
        pass

    # usage-jsonl-sync: 워크플로우 종료 시 전체 JSONL 일괄 파싱 (async)
    # finalization.py(flow-finish)에서 직접 호출하므로 subagent-stop에서는 비활성
    # (done 에이전트 제거로 subagent-stop 트리거 경로 사용하지 않음)

    # All hooks are async/fire-and-forget, no exit code aggregation needed
    sys.exit(0)


if __name__ == '__main__':
    main()
