"""Internal helpers for _handle_kanban_done sub-branches."""

from __future__ import annotations

import os
import re
import sys
import subprocess

from ._kanban_done_re import (
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
        project_root, '.claude-organic', 'tickets', 'open', f'{ticket}.xml',
    )
    if not os.path.isfile(open_xml):
        handler._send_error(
            400,
            f'{ticket} is not in Open column (force done requires Open status)',
        )
        return

    # 워크트리 dirty 가드
    wt_path: str | None = None
    try:
        engine_dir = os.path.join(project_root, '.claude-organic', 'engine')
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
                        f'{ticket} 워크트리에 미커밋 변경이 있습니다. '
                        'force_dirty=true 로 재시도하거나 취소하세요.'
                    ),
                    'ticket': ticket,
                })
                return
    except ImportError:
        wt_path = None  # 워크트리 비활성 환경 — 가드 생략

    # flow-kanban move <ticket> done --force 호출
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

    # 워크트리 정리 (force=True: lock 해제 후 강제 삭제)
    worktree_removed = False
    if wt_path:
        try:
            engine_dir = os.path.join(project_root, '.claude-organic', 'engine')
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
    # Review 상태 사전 확인 — review/ 디렉터리에 티켓 XML 존재 여부로 판별
    review_xml = os.path.join(
        project_root, '.claude-organic', 'tickets', 'review', f'{ticket}.xml',
    )
    if not os.path.isfile(review_xml):
        handler._send_error(
            400,
            f'{ticket} is not in Review column (current state check failed)',
        )
        return

    # flow-kanban done 호출 — merge 시간 고려해 timeout 120초
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

        # rc=0 이지만 merge_commit 이 비어있는 경우 분기:
        # (1) 충돌 시그널 있음 → merge_conflict
        # (2) "T-NNN: <prev> → Done" 시그널 있음 → merge_skipped (research 등)
        # (3) 둘 다 없음 → 백엔드 응답 형식 오류
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
                    'message': 'merge_commit 누락 — 백엔드 응답 형식 오류',
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

    # 실패 — stdout 줄 단위 분석으로 error_kind 분류
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
    """ticket 을 derived-from 으로 참조하는 파생 티켓 중 Done 이외 상태인 것을 반환한다."""
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
