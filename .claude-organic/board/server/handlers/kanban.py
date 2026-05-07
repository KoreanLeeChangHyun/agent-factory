"""Kanban DnD POST handlers (move/submit/done/delete) — preserves cb7427f regression fixes."""

from __future__ import annotations

import os
import re
import sys
import subprocess

from ._helpers import _TICKET_RE, _KANBAN_ALL_DIRS
from ._kanban_done_helpers import (
    handle_kanban_done_force,
    handle_kanban_done_review,
    check_derived_blocked,
)


class KanbanHandlerMixin:
    """Kanban DnD POST handlers (move/submit/done/delete) — preserves cb7427f regression fixes."""

    def _get_dirty_files(self, wt_path: str) -> list[str]:
        """워크트리 미커밋 파일 목록 반환 (git status --porcelain 파싱)."""
        try:
            r = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=wt_path, capture_output=True, text=True, timeout=10,
            )
            if r.returncode != 0 or not r.stdout.strip():
                return []
            return [line[3:].split(' -> ')[-1].strip() for line in r.stdout.splitlines()]
        except Exception:
            return []

    def _check_derived_blocked(self, ticket: str, kanban_base: str) -> list[str]:
        """derived-from 파생 티켓 중 Done 이외 상태인 것 반환 (위임)."""
        return check_derived_blocked(ticket, kanban_base, _KANBAN_ALL_DIRS)

    def _handle_kanban_move(self) -> None:
        """POST /api/kanban/move — {"ticket","to"}: To Do ↔ Open 전이만 허용."""
        data = self._read_json_body() or {}
        ticket = (data.get('ticket') or '').strip()
        to = (data.get('to') or '').strip().lower()

        if not ticket or not ticket.startswith('T-'):
            self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
            return
        if to not in ('todo', 'open'):
            self._send_error(400, 'DnD allows only To Do ↔ Open transitions ("to" must be "todo" or "open")')
            return

        project_root = os.getcwd()
        flow_kanban = os.path.join(project_root, '.claude-organic', 'bin', 'flow-kanban')
        try:
            result = subprocess.run(
                [flow_kanban, 'move', ticket, to],
                cwd=project_root, capture_output=True, text=True, timeout=10,
            )
        except subprocess.TimeoutExpired:
            self._send_error(504, 'flow-kanban move timed out')
            return
        except FileNotFoundError:
            self._send_error(500, f'flow-kanban not found: {flow_kanban}')
            return

        if result.returncode != 0:
            self._send_error(400, f'flow-kanban move failed: {(result.stderr or result.stdout or "").strip()}')
            return
        self._send_json({'ok': True, 'ticket': ticket, 'to': to, 'stdout': result.stdout.strip()})

    def _handle_kanban_submit(self) -> None:
        """POST /api/kanban/submit — {"ticket","command"}: flow-launcher 위임, LAUNCH:/INLINE: 파싱."""
        data = self._read_json_body() or {}
        ticket = (data.get('ticket') or '').strip()
        command = (data.get('command') or '').strip()

        if not ticket or not re.match(r'^T-\d+$', ticket):
            self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
            return
        if command not in ('implement', 'research', 'review'):
            self._send_error(400, 'Invalid "command" (must be implement/research/review)')
            return

        project_root = os.getcwd()
        flow_launcher = os.path.join(project_root, '.claude-organic', 'bin', 'flow-launcher')
        try:
            result = subprocess.run(
                [flow_launcher, 'launch', ticket, command],
                cwd=project_root, capture_output=True, text=True, timeout=15,
            )
        except subprocess.TimeoutExpired:
            self._send_error(504, 'flow-launcher launch timed out')
            return
        except FileNotFoundError:
            self._send_error(500, f'flow-launcher not found: {flow_launcher}')
            return

        if result.returncode != 0:
            self._send_error(400, f'flow-launcher launch failed: {(result.stderr or result.stdout or "").strip()}')
            return

        stdout = result.stdout.strip()
        first_line = stdout.split('\n', 1)[0].strip() if stdout else ''
        if first_line.startswith('LAUNCH:'):
            tail = first_line[len('LAUNCH:'):].strip()
            payload = {'ok': True, 'mode': 'launched', 'ticket': ticket,
                       'session_id': tail.split()[0] if tail else '', 'message': first_line}
        elif first_line.startswith('INLINE:'):
            payload = {'ok': True, 'mode': 'inline', 'ticket': ticket, 'message': first_line}
        else:
            payload = {'ok': True, 'mode': 'unknown', 'ticket': ticket,
                       'message': first_line or 'no stdout'}
        self._send_json(payload)

    def _handle_kanban_done(self) -> None:
        """POST /api/kanban/done — {"ticket","force","force_dirty"}.

        force=false: Review → Done (T-906 dict→list fix, merge_skipped 분기).
        force=true:  Open → Done (T-418, dirty 워크트리 가드).
        세부 로직은 _kanban_done_helpers.py 위임.
        """
        data = self._read_json_body() or {}
        ticket = (data.get('ticket') or '').strip()
        force = bool(data.get('force', False))
        force_dirty = bool(data.get('force_dirty', False))

        if not ticket or not _TICKET_RE.match(ticket):
            self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
            return

        project_root = os.getcwd()
        flow_kanban = os.path.join(project_root, '.claude-organic', 'bin', 'flow-kanban')

        if force:
            handle_kanban_done_force(self, ticket, force_dirty, project_root, flow_kanban)
        else:
            handle_kanban_done_review(self, ticket, project_root, flow_kanban)

    def _handle_kanban_delete(self) -> None:
        """POST /api/kanban/delete — {"ticket"}: derived-from 가드 + delete + worktree 정리 (T-418)."""
        data = self._read_json_body() or {}
        ticket = (data.get('ticket') or '').strip()

        if not ticket or not _TICKET_RE.match(ticket):
            self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
            return

        project_root = os.getcwd()
        kanban_base = os.path.join(project_root, '.claude-organic', 'tickets')

        not_done = self._check_derived_blocked(ticket, kanban_base)
        if not_done:
            self._send_json_with_status(409, {
                'ok': False, 'error_kind': 'derived_blocked',
                'blocked_by': not_done,
                'message': (
                    f'{ticket} 삭제 차단: 파생 티켓 {", ".join(not_done)}이 '
                    '아직 완료되지 않았습니다. 파생 티켓 완료 후 삭제하세요.'
                ),
                'ticket': ticket,
            })
            return

        flow_kanban = os.path.join(project_root, '.claude-organic', 'bin', 'flow-kanban')
        try:
            result = subprocess.run(
                [flow_kanban, 'delete', ticket],
                cwd=project_root, capture_output=True, text=True, timeout=30,
            )
        except subprocess.TimeoutExpired:
            self._send_error(504, 'flow-kanban delete timed out (30s)')
            return
        except FileNotFoundError:
            self._send_error(500, f'flow-kanban not found: {flow_kanban}')
            return

        if result.returncode != 0:
            self._send_json_with_status(409, {
                'ok': False, 'error_kind': 'other', 'blocked_by': [],
                'message': (result.stderr or result.stdout or '').strip() or 'flow-kanban delete failed',
                'ticket': ticket,
            })
            return

        worktree_removed = False
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

        self._send_json({
            'ok': True, 'ticket': ticket,
            'stdout': (result.stdout or '').strip(),
            'worktree_removed': worktree_removed,
        })
