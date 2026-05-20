"""Kanban and dashboard readers for the Board backend."""

from __future__ import annotations

import os
import json

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


def _parse_markdown_table(text: str) -> dict[str, object]:
    headers: list[str] = []
    rows: list[list[str]] = []
    in_table = False
    header_seen = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith('|'):
            if in_table:
                break
            continue
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        if not in_table:
            in_table = True
            headers = cells
            continue
        if not header_seen:
            header_seen = True
            continue
        rows.append(cells)
    return {
        'headers': headers,
        'rows': rows,
        'source': 'legacy-md',
    }


def _read_dashboard_json(path: str) -> dict[str, object]:
    with open(path, encoding='utf-8') as f:
        payload = json.load(f)
    if isinstance(payload, list):
        return {'headers': [], 'rows': payload, 'source': 'json'}
    if not isinstance(payload, dict):
        return {'headers': [], 'rows': [], 'source': 'json'}
    rows = payload.get('rows', [])
    headers = payload.get('headers', [])
    return {
        **payload,
        'headers': headers if isinstance(headers, list) else [],
        'rows': rows if isinstance(rows, list) else [],
        'source': payload.get('source') or 'json',
    }


def _empty_dashboard_table() -> dict[str, object]:
    return {'headers': [], 'rows': [], 'source': 'empty'}


def _read_dashboard(project_root: str) -> dict[str, dict[str, object]]:
    """dashboard JSON files are canonical; legacy Markdown tables are fallback."""
    base = os.path.join(project_root, DASH_BASE)
    result: dict[str, dict[str, object]] = {}
    for name in DASH_FILES:
        json_path = os.path.join(base, f'{name}.json')
        legacy_path = os.path.join(base, f'.{name}.md')
        try:
            result[name] = _read_dashboard_json(json_path)
            continue
        except (OSError, json.JSONDecodeError):
            pass
        try:
            with open(legacy_path, encoding='utf-8') as f:
                result[name] = _parse_markdown_table(f.read())
        except OSError:
            result[name] = _empty_dashboard_table()
    return result
