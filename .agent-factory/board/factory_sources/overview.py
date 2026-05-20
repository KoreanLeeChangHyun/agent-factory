"""Kanban and dashboard readers for the Board backend."""

from __future__ import annotations

import os

KANBAN_DIRS_LIST: list[str] = ['todo', 'open', 'progress', 'review', 'done']
DASH_BASE: str = os.path.join('.agent-factory', 'board', 'data')
DASH_FILES: list[str] = ['usage', 'logs', 'skills']


def _read_kanban_tickets(
    project_root: str, files: list[str] | None = None,
) -> dict[str, str | None]:
    """kanban 디렉터리에서 XML 티켓을 읽어 {파일명: 내용} dict를 반환한다."""
    kanban = os.path.join(project_root, '.agent-factory', 'tickets')
    result: dict[str, str | None] = {}
    for d in KANBAN_DIRS_LIST:
        dp = os.path.join(kanban, d)
        if not os.path.isdir(dp):
            continue
        try:
            for e in os.scandir(dp):
                if not e.is_file() or not e.name.endswith('.xml'):
                    continue
                if files and e.name not in files:
                    continue
                if e.name in result:
                    continue
                try:
                    with open(e.path, encoding='utf-8') as f:
                        result[e.name] = f.read()
                except OSError:
                    result[e.name] = None
        except OSError:
            pass
    if files:
        for fn in files:
            if fn not in result:
                result[fn] = None
    return result


def _read_dashboard(project_root: str) -> dict[str, str]:
    """dashboard .md 파일 3개를 읽어 반환한다."""
    base = os.path.join(project_root, DASH_BASE)
    result: dict[str, str] = {}
    for name in DASH_FILES:
        path = os.path.join(base, f'.{name}.md')
        try:
            with open(path, encoding='utf-8') as f:
                result[name] = f.read()
        except OSError:
            result[name] = ''
    return result
