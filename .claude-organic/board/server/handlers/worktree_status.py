"""Worktree status handlers (T-419)."""

from __future__ import annotations

from .._common import logger
from ._helpers import _import_worktree_status


class WorktreeStatusHandlerMixin:
    """Worktree status handlers (T-419)."""

    def _handle_worktree_status(self, ticket: str) -> None:
        """GET /api/worktree/status?ticket=T-NNN — 단일 티켓 워크트리 상태 응답.

        결과가 None(티켓에 해당하는 워크트리 미존재)이어도 200 + {exists: false} 응답.
        클라이언트가 exists 필드로 존재 여부를 판단한다.
        """
        if ticket is None:
            ticket = ''
        try:
            mod = _import_worktree_status()
            data = mod.get_worktree_status(ticket)
        except Exception as exc:  # noqa: BLE001
            logger.exception('worktree_status.single failed: %s', exc)
            self._send_error(500, f'get_worktree_status failed: {exc}')
            return
        if data is None:
            data = {'ticket': ticket, 'exists': False}
        self._send_json(data)

    def _handle_worktree_status_all(self) -> None:
        """GET /api/worktree/status/all — 전체 워크트리 상태 list 응답."""
        try:
            mod = _import_worktree_status()
            data = mod.get_all_worktree_statuses()
        except Exception as exc:  # noqa: BLE001
            logger.exception('worktree_status.all failed: %s', exc)
            self._send_error(500, f'get_all_worktree_statuses failed: {exc}')
            return
        self._send_json(data)
