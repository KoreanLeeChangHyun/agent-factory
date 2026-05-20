"""Internal helpers for _handle_kanban_done sub-branches."""

from __future__ import annotations

import os
import re
import sys
import subprocess

from engine.apps.board_api.kanban_done_re import (
    _classify_done_failure,
    _DONE_MERGE_OK_RE,
)


def handle_kanban_done_force(handler, ticket: str, force_dirty: bool,
                              project_root: str, flow_kanban: str) -> None:
    """force=True 분기: Open → Done 직접 전이.

    1. open/<ticket>.xml 존재 검증
    2. dirty 워크트리 가드 (force_dirty=false 면 409 차단)
    3. flow-kanban move <ticket> done --force 호출
    4. worktree_manager.remove_worktree 로 워크트리/브랜치 정리
    """
    open_xml = os.path.join(
        project_root, '.agent-factory', 'tickets', 'open', f'{ticket}.xml',
    )
    if not os.path.isfile(open_xml):
        handler._send_error(
            400,
            f'{ticket} is not in Open column (force done requires Open status)',
        )
        return

    # Worktree dirty guard
    wt_path: str | None = None
    try:
        engine_dir = os.path.join(project_root, '.agent-factory', 'engine')
        if engine_dir not in sys.path:
            sys.path.insert(0, engine_dir)
        from flow import worktree_manager  # noqa: WPS433
        wt_path = worktree_manager.get_worktree_path(ticket, repo_path=project_root)
        if wt_path and worktree_manager.has_uncommitted_changes(wt_path):
            if not force_dirty:
                dirty_files = handler._get_dirty_files(wt_path)
                handler._send_json_with_status(409, {
                    'ok': False,
                    'error_kind': 'dirty_worktree',
                    'conflicts': [],
                    'dirty_files': dirty_files,
                    'message': (
                        f'There are uncommitted changes in the {ticket} worktree.'
                        'Retry with force_dirty=true or cancel.'
                    ),
                    'ticket': ticket,
                })
                return
    except ImportError:
        wt_path = None  # Worktree Inactive Environment — Guard Omitted

    # flow-kanban move <ticket> done --force call
    try:
        result = subprocess.run(
            [flow_kanban, 'move', ticket, 'done', '--force'],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        handler._send_error(504, 'flow-kanban move timed out (30s)')
        return
    except FileNotFoundError:
        handler._send_error(500, f'flow-kanban not found: {flow_kanban}')
        return

    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or '').strip()
        handler._send_json_with_status(409, {
            'ok': False,
            'error_kind': 'other',
            'conflicts': [],
            'dirty_files': [],
            'message': stderr or 'flow-kanban move done --force failed',
            'ticket': ticket,
        })
        return

    # Clean up the work tree (force=True: Force deletion after releasing the lock)
    worktree_removed = False
    if wt_path:
        try:
            engine_dir = os.path.join(project_root, '.agent-factory', 'engine')
            if engine_dir not in sys.path:
                sys.path.insert(0, engine_dir)
            from flow import worktree_manager as _wm  # noqa: WPS433
            worktree_removed = _wm.remove_worktree(
                ticket, delete_branch=True, repo_path=project_root,
            )
        except ImportError:
            pass

    handler._send_json({
        'ok': True,
        'ticket': ticket,
        'force': True,
        'worktree_removed': worktree_removed,
        'stdout': (result.stdout or '').strip(),
    })


def handle_kanban_done_review(handler, ticket: str,
                               project_root: str, flow_kanban: str) -> None:
    """force=False 분기: Review → Done 전이.

    1. review/<ticket>.xml 존재 검증 (os.path.isfile — dict→list 회귀 fix)
    2. flow-kanban done <ticket> 호출
    3. stdout 파싱 — merge_commit / merge_skipped / error_kind 분류
    """
    # Pre-check review status — Determined by the presence of ticket XML in the review/ directory
    review_xml = os.path.join(
        project_root, '.agent-factory', 'tickets', 'review', f'{ticket}.xml',
    )
    if not os.path.isfile(review_xml):
        handler._send_error(
            400,
            f'{ticket} is not in Review column (current state check failed)',
        )
        return

    # call flow-kanban done — timeout 120 seconds considering merge time
    try:
        result = subprocess.run(
            [flow_kanban, 'done', ticket],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        handler._send_error(504, 'flow-kanban done timed out (120s)')
        return
    except FileNotFoundError:
        handler._send_error(500, f'flow-kanban not found: {flow_kanban}')
        return

    stdout = result.stdout or ''

    if result.returncode == 0:
        merge_commit = ''
        merged_branch = ''
        for line in stdout.splitlines():
            m = _DONE_MERGE_OK_RE.search(line)
            if m:
                merged_branch = m.group(1).strip()
                merge_commit = m.group(2).strip()
                break

        # Branch if rc=0 but merge_commit is empty:
        # (1) Conflict signal exists → merge_conflict
        # (2) “T-NNN: <prev> → Done” signal present → merge_skipped (research, etc.)
        # (3) Neither → backend response format error
        if not merge_commit:
            done_transition_re = re.compile(
                rf'^{re.escape(ticket)}:\s+\S+\s+→\s+Done\b'
            )
            merge_skipped = any(
                done_transition_re.match(line) for line in stdout.splitlines()
            )
            if merge_skipped:
                handler._send_json({
                    'ok': True,
                    'ticket': ticket,
                    'merge_commit': '',
                    'merged_branch': '',
                    'merge_skipped': True,
                    'stdout': stdout.strip(),
                })
                return

            failure = _classify_done_failure(stdout, result.stderr or '')
            if failure['error_kind'] == 'merge_conflict':
                handler._send_json_with_status(409, {
                    'ok': False,
                    'error_kind': 'merge_conflict',
                    'conflicts': failure['conflicts'],
                    'dirty_files': failure['dirty_files'],
                    'message': failure['message'],
                    'ticket': ticket,
                })
            else:
                handler._send_json_with_status(409, {
                    'ok': False,
                    'error_kind': 'other',
                    'conflicts': [],
                    'dirty_files': [],
                    'message': 'merge_commit missing — backend response format error',
                    'ticket': ticket,
                })
            return

        handler._send_json({
            'ok': True,
            'ticket': ticket,
            'merge_commit': merge_commit,
            'merged_branch': merged_branch,
            'stdout': stdout.strip(),
        })
        return

    # Failure — Sorting error_kind with stdout line-by-line analysis
    failure = _classify_done_failure(stdout, result.stderr or '')
    handler._send_json_with_status(409, {
        'ok': False,
        'error_kind': failure['error_kind'],
        'conflicts': failure['conflicts'],
        'dirty_files': failure['dirty_files'],
        'message': failure['message'],
        'ticket': ticket,
    })


def check_derived_blocked(ticket: str, kanban_base: str,
                           kanban_all_dirs: tuple) -> list[str]:
    """Among the derived tickets that refer to ticket as derived-from, returns those with a status other than Done."""
    import xml.etree.ElementTree as ET

    not_done: list[str] = []
    for d in kanban_all_dirs:
        dir_path = os.path.join(kanban_base, d)
        if not os.path.isdir(dir_path):
            continue
        try:
            for entry in os.scandir(dir_path):
                if not entry.is_file() or not entry.name.endswith('.xml'):
                    continue
                try:
                    tree = ET.parse(entry.path)
                    for rel in tree.findall('.//relations/relation'):
                        if (rel.get('type') == 'derived-from'
                                and rel.get('ticket') == ticket):
                            num_el = tree.find('.//metadata/number')
                            status_el = tree.find('.//metadata/status')
                            num = (num_el.text or '').strip() if num_el is not None else ''
                            status = (status_el.text or '').strip() if status_el is not None else ''
                            if status != 'Done' and num:
                                not_done.append(f'{num}({status or "?"})')
                except Exception:
                    continue
        except OSError:
            continue
    return not_done
