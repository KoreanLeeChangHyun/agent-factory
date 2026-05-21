"""Internal helpers for _handle_conveyor_complete sub-branches."""

from __future__ import annotations

import os
import re
import sys
import subprocess

from engine.apps.board_api.conveyor_complete_re import (
    _classify_complete_failure,
    _COMPLETE_MERGE_OK_RE,
)


def handle_conveyor_complete_force(handler, work_request: str, force_dirty: bool,
                              project_root: str, flow_conveyor: str) -> None:
    """force=True branch: Accepted → Complete direct transition.

    1. Verify the existence of accepted/<work_request>.xml
    2. Dirty work tree guard (blocks 409 if force_dirty=false)
    3. call flow-conveyor move <work_request> complete --force
    4. Clean up the work tree/branch with worktree_manager.remove_worktree
    """
    accepted_xml = os.path.join(
        project_root, '.agent-factory', 'work-requests', 'accepted', f'{work_request}.xml',
    )
    if not os.path.isfile(accepted_xml):
        handler._send_error(
            400,
            f'{work_request} is not in Accepted column (force complete requires Accepted status)',
        )
        return

    # Worktree dirty guard
    wt_path: str | None = None
    try:
        engine_dir = os.path.join(project_root, '.agent-factory', 'engine')
        if engine_dir not in sys.path:
            sys.path.insert(0, engine_dir)
        from flow import worktree_manager  # noqa: WPS433
        wt_path = worktree_manager.get_worktree_path(work_request, repo_path=project_root)
        if wt_path and worktree_manager.has_uncommitted_changes(wt_path):
            if not force_dirty:
                dirty_files = handler._get_dirty_files(wt_path)
                handler._send_json_with_status(409, {
                    'ok': False,
                    'error_kind': 'dirty_worktree',
                    'conflicts': [],
                    'dirty_files': dirty_files,
                    'message': (
                        f'There are uncommitted changes in the {work_request} worktree.'
                        'Retry with force_dirty=true or cancel.'
                    ),
                    'work_request': work_request,
                })
                return
    except ImportError:
        wt_path = None  # Worktree Inactive Environment — Guard Omitted

    # flow-conveyor move <work_request> complete --force call
    try:
        result = subprocess.run(
            [flow_conveyor, 'move', work_request, 'complete', '--force'],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        handler._send_error(504, 'flow-conveyor move timed out (30s)')
        return
    except FileNotFoundError:
        handler._send_error(500, f'flow-conveyor not found: {flow_conveyor}')
        return

    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or '').strip()
        handler._send_json_with_status(409, {
            'ok': False,
            'error_kind': 'other',
            'conflicts': [],
            'dirty_files': [],
            'message': stderr or 'flow-conveyor move complete --force failed',
            'work_request': work_request,
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
                work_request, delete_branch=True, repo_path=project_root,
            )
        except ImportError:
            pass

    handler._send_json({
        'ok': True,
        'work_request': work_request,
        'force': True,
        'worktree_removed': worktree_removed,
        'stdout': (result.stdout or '').strip(),
    })


def handle_conveyor_complete_review(handler, work_request: str,
                               project_root: str, flow_conveyor: str) -> None:
    """force=False Branch: Verifying → Complete transition.

    1. Verifying/<work_request>.xml existence verification (os.path.isfile — dict→list regression fix)
    2. Call flow-conveyor complete <work_request>
    3. stdout parsing — merge_commit / merge_skipped / error_kind classification
    """
    # Pre-check verifying status — Determined by the presence of work_request XML in the verifying/ directory
    verifying_xml = os.path.join(
        project_root, '.agent-factory', 'work-requests', 'verifying', f'{work_request}.xml',
    )
    if not os.path.isfile(verifying_xml):
        handler._send_error(
            400,
            f'{work_request} is not in Verifying column (current state check failed)',
        )
        return

    # call flow-conveyor complete — timeout 120 seconds considering merge time
    try:
        result = subprocess.run(
            [flow_conveyor, 'complete', work_request],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        handler._send_error(504, 'flow-conveyor complete timed out (120s)')
        return
    except FileNotFoundError:
        handler._send_error(500, f'flow-conveyor not found: {flow_conveyor}')
        return

    stdout = result.stdout or ''

    if result.returncode == 0:
        merge_commit = ''
        merged_branch = ''
        for line in stdout.splitlines():
            m = _COMPLETE_MERGE_OK_RE.search(line)
            if m:
                merged_branch = m.group(1).strip()
                merge_commit = m.group(2).strip()
                break

        # Branch if rc=0 but merge_commit is empty:
        # (1) Conflict signal exists → merge_conflict
        # (2) “WR-NNN: <prev> → Complete” signal present → merge_skipped (research, etc.)
        # (3) Neither → backend response format error
        if not merge_commit:
            complete_transition_re = re.compile(
                rf'^{re.escape(work_request)}:\s+\S+\s+→\s+Complete\b'
            )
            merge_skipped = any(
                complete_transition_re.match(line) for line in stdout.splitlines()
            )
            if merge_skipped:
                handler._send_json({
                    'ok': True,
                    'work_request': work_request,
                    'merge_commit': '',
                    'merged_branch': '',
                    'merge_skipped': True,
                    'stdout': stdout.strip(),
                })
                return

            failure = _classify_complete_failure(stdout, result.stderr or '')
            if failure['error_kind'] == 'merge_conflict':
                handler._send_json_with_status(409, {
                    'ok': False,
                    'error_kind': 'merge_conflict',
                    'conflicts': failure['conflicts'],
                    'dirty_files': failure['dirty_files'],
                    'message': failure['message'],
                    'work_request': work_request,
                })
            else:
                handler._send_json_with_status(409, {
                    'ok': False,
                    'error_kind': 'other',
                    'conflicts': [],
                    'dirty_files': [],
                    'message': 'merge_commit missing — backend response format error',
                    'work_request': work_request,
                })
            return

        handler._send_json({
            'ok': True,
            'work_request': work_request,
            'merge_commit': merge_commit,
            'merged_branch': merged_branch,
            'stdout': stdout.strip(),
        })
        return

    # Failure — Sorting error_kind with stdout line-by-line analysis
    failure = _classify_complete_failure(stdout, result.stderr or '')
    handler._send_json_with_status(409, {
        'ok': False,
        'error_kind': failure['error_kind'],
        'conflicts': failure['conflicts'],
        'dirty_files': failure['dirty_files'],
        'message': failure['message'],
        'work_request': work_request,
    })


def check_derived_blocked(work_request: str, conveyor_base: str,
                           conveyor_all_dirs: tuple) -> list[str]:
    """Among the derived work-requests that refer to work_request as derived-from, returns those with a status other than Complete."""
    import xml.etree.ElementTree as ET

    not_complete: list[str] = []
    for d in conveyor_all_dirs:
        dir_path = os.path.join(conveyor_base, d)
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
                                and rel.get('work_request') == work_request):
                            num_el = tree.find('.//metadata/number')
                            status_el = tree.find('.//metadata/status')
                            num = (num_el.text or '').strip() if num_el is not None else ''
                            status = (status_el.text or '').strip() if status_el is not None else ''
                            if status != 'Complete' and num:
                                not_complete.append(f'{num}({status or "?"})')
                except Exception:
                    continue
        except OSError:
            continue
    return not_complete
