"""Workflow run readers for the Board backend."""

from __future__ import annotations

import json
import os
import re
import subprocess

WF_BASE: str = os.path.join('.agent-factory', 'runs')
WF_HISTORY: str = os.path.join('.agent-factory', 'runs', '.history')
WF_ENTRY_RE = re.compile(r'^\d{8}-\d{6}$')
WF_DETAIL_FILES: list[dict] = [
    {'key': 'query',   'file': 'user_prompt.txt'},
    {'key': 'plan',    'file': 'plan.md'},
    {'key': 'report',  'file': 'report.html'},
    {'key': 'summary', 'file': 'summary.txt'},
    {'key': 'usage',   'file': 'usage.json'},
    {'key': 'log',     'file': 'workflow.log'},
]


def _list_workflow_entries(project_root: str) -> list[str]:
    """return the workflow + .history entry to the latest order."""
    entries: list[str] = []
    for rel in (WF_BASE, WF_HISTORY):
        abs_dir = os.path.join(project_root, rel)
        if not os.path.isdir(abs_dir):
            continue
        prefix = rel + '/'
        try:
            for e in os.scandir(abs_dir):
                if e.is_dir() and WF_ENTRY_RE.match(e.name):
                    entries.append(prefix + e.name + '/')
        except OSError:
            pass
    entries.sort(key=lambda p: p.rstrip('/').rsplit('/', 1)[-1], reverse=True)
    return entries


def _get_git_branch(project_root: str) -> str:
    """returns the current git brand name.

    git command returns empty strings when failed or timeout.
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True, text=True, timeout=3,
            cwd=project_root,
        )
        return result.stdout.strip() if result.returncode == 0 else ''
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ''


def _workflow_detail(project_root: str, entry_rel: str) -> list[dict]:
    """Workflow Entries returns one details.

    T-449 fold structure priority: ``<key>/status.json` direct.
    old nested structure fallback: ``<key>/<task>/<cmd>/status.json` (containing legacy  etc).
    """
    entry_name = entry_rel.rstrip('/').rsplit('/', 1)[-1]
    entry_abs = os.path.join(project_root, entry_rel.strip('/'))
    if not os.path.isdir(entry_abs):
        return []
    items: list[dict] = []

    def _build_file_map(dir_abs: str, base_path: str) -> dict:
        file_map: dict = {}
        for wf in WF_DETAIL_FILES:
            fp = os.path.join(dir_abs, wf['file'])
            exists = os.path.isfile(fp)
            file_map[wf['key']] = {
                'exists': exists,
                'url': base_path + wf['file'] if exists else '',
            }
        work_dir = os.path.join(dir_abs, 'work')
        has_work = os.path.isdir(work_dir)
        file_map['work'] = {
            'exists': has_work,
            'url': base_path + 'work/' if has_work else '',
            'isDir': True,
        }
        return file_map

    direct_status = os.path.join(entry_abs, 'status.json')
    if os.path.isfile(direct_status):
        try:
            with open(direct_status, encoding='utf-8') as f:
                status = json.load(f)
        except (OSError, json.JSONDecodeError):
            status = None
        if isinstance(status, dict):
            command = ''
            work_name = entry_name
            ticket_number = ''
            title = ''
            ctx_path = os.path.join(entry_abs, '.context.json')
            try:
                with open(ctx_path, encoding='utf-8') as f:
                    ctx = json.load(f)
                if isinstance(ctx, dict):
                    command = ctx.get('command', '') or ''
                    work_name = ctx.get('workName', '') or entry_name
                    ticket_number = (ctx.get('ticketNumber', '') or '').strip()
                    title = ctx.get('title', '') or ''
            except (OSError, json.JSONDecodeError):
                pass
            items.append({
                'entry': entry_name,
                'task': work_name,
                'command': command,
                'basePath': entry_rel,
                # production-line uses status.json to `workflow step` key (SPEC §2 vocabulary correction).
                # Supports the old v1 cycle 'step' keyway fallback. 'NONE' without both.
                'step': status.get('workflow_step', status.get('step', 'NONE')),
                'created_at': status.get('created_at', ''),
                'updated_at': status.get('updated_at', ''),
                'transitions': status.get('transitions', []),
                'fileMap': _build_file_map(entry_abs, entry_rel),
                'ticketNumber': ticket_number,
                'title': title,
            })

    # 2nd fallback: <key>/<task>/<cmd>/status.json ( legacy  preserve)
    try:
        task_dirs = sorted(
            e.name for e in os.scandir(entry_abs)
            if e.is_dir() and e.name != 'work'
        )
    except OSError:
        return items
    for task in task_dirs:
        task_abs = os.path.join(entry_abs, task)
        try:
            cmd_dirs = sorted(
                e.name for e in os.scandir(task_abs) if e.is_dir()
            )
        except OSError:
            continue
        for cmd in cmd_dirs:
            cmd_abs = os.path.join(task_abs, cmd)
            status_path = os.path.join(cmd_abs, 'status.json')
            if not os.path.isfile(status_path):
                continue
            try:
                with open(status_path, encoding='utf-8') as f:
                    status = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            base_path = entry_rel + task + '/' + cmd + '/'
            ticket_number = ''
            title = ''
            ctx_path = os.path.join(cmd_abs, '.context.json')
            try:
                with open(ctx_path, encoding='utf-8') as f:
                    ctx = json.load(f)
                if isinstance(ctx, dict):
                    ticket_number = (ctx.get('ticketNumber', '') or '').strip()
                    title = ctx.get('title', '') or ''
            except (OSError, json.JSONDecodeError):
                pass
            items.append({
                'entry': entry_name,
                'task': task,
                'command': cmd,
                'basePath': base_path,
                # production-line uses status.json to `workflow step` key (SPEC §2 vocabulary correction).
                # Supports the old v1 cycle 'step' keyway fallback. 'NONE' without both.
                'step': status.get('workflow_step', status.get('step', 'NONE')),
                'created_at': status.get('created_at', ''),
                'updated_at': status.get('updated_at', ''),
                'transitions': status.get('transitions', []),
                'fileMap': _build_file_map(cmd_abs, base_path),
                'ticketNumber': ticket_number,
                'title': title,
            })
    return items
