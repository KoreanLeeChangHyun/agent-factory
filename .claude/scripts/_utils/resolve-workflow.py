#!/usr/bin/env python3
"""
Resolve active workflow from registry.json

Reads the global workflow registry and identifies the most relevant active workflow.
Outputs context information (title, workId, workName, command, agent, phase) to stdout,
one field per line.

Usage:
    python3 resolve-workflow.py <registry_file> <project_root>

Exit codes:
    0 - Success (context printed to stdout)
    1 - No workflow identified (registry missing, empty, or no valid entry)
"""

import os
import sys

# common 모듈에서 load_json_file을 import
# 이 파일이 직접 실행될 때를 위해 sys.path 조정
# _utils/ 디렉터리는 scripts/ 하위이므로, scripts/를 sys.path에 추가
_utils_dir = os.path.dirname(os.path.abspath(__file__))
_scripts_dir = os.path.dirname(_utils_dir)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from _utils.common import load_json_file


def get_updated_at(project_root, entry):
    """Read updated_at from a workflow's status.json."""
    work_dir = entry.get("workDir", "")
    abs_wd = (
        os.path.join(project_root, work_dir)
        if not os.path.isabs(work_dir)
        else work_dir
    )
    status_file = os.path.join(abs_wd, "status.json")
    status = load_json_file(status_file)
    if status:
        return status.get("updated_at", "")
    return ""


def select_by_most_recent(candidates, project_root):
    """Select the candidate with the most recent updated_at."""
    with_time = []
    for key, entry in candidates:
        updated_at = get_updated_at(project_root, entry)
        with_time.append((key, entry, updated_at))
    if not with_time:
        return None, None
    with_time.sort(key=lambda x: x[2], reverse=True)
    return with_time[0][0], with_time[0][1]


def resolve_workflow(registry_file, project_root):
    """Identify the active workflow from the registry."""
    registry = load_json_file(registry_file)

    if not isinstance(registry, dict) or not registry:
        return None

    # Convert dict to list of (key, entry) tuples
    entries = [(k, v) for k, v in registry.items() if isinstance(v, dict)]
    if not entries:
        return None

    selected_entry = None

    if len(entries) == 1:
        # Single active workflow -> select immediately
        _, selected_entry = entries[0]
    else:
        # Multiple -> filter by phase='PLAN'
        plan_entries = [
            (k, v) for k, v in entries if v.get("phase", "") == "PLAN"
        ]

        if len(plan_entries) == 1:
            _, selected_entry = plan_entries[0]
        elif len(plan_entries) > 1:
            _, selected_entry = select_by_most_recent(plan_entries, project_root)
        else:
            # No PLAN entries -> most recent among all
            _, selected_entry = select_by_most_recent(entries, project_root)

    if not selected_entry:
        return None

    # Read local .context.json
    work_dir = selected_entry.get("workDir", "")
    abs_work_dir = (
        os.path.join(project_root, work_dir)
        if not os.path.isabs(work_dir)
        else work_dir
    )
    local_context_file = os.path.join(abs_work_dir, ".context.json")

    ctx = load_json_file(local_context_file)
    if not ctx:
        return None

    title = ctx.get("title", "")
    work_id = ctx.get("workId", "")
    work_name = ctx.get("workName", "") or ctx.get("title", "")
    command = ctx.get("command", "")
    agent = ctx.get("agent", "")

    if not (title and work_id and command):
        return None

    # Read phase from status.json
    phase = ""
    status_file = os.path.join(abs_work_dir, "status.json")
    status = load_json_file(status_file)
    if status:
        phase = status.get("phase", "")

    return f"{title}\n{work_id}\n{work_name}\n{command}\n{agent}\n{phase}"


def main():
    if len(sys.argv) < 3:
        print("Usage: resolve-workflow.py <registry_file> <project_root>", file=sys.stderr)
        sys.exit(1)

    registry_file = sys.argv[1]
    project_root = sys.argv[2]

    result = resolve_workflow(registry_file, project_root)
    if result is None:
        sys.exit(1)

    print(result)


if __name__ == "__main__":
    main()
