"""Worktree uncommitted indicator + commit action handlers.

T-419 진단형 핸들러 폐지(99c9ce0) 후 워크플로우 회귀 시 사용자 수동
수습 경로로 단순화 부활. 카드 우상단 인디케이터 일괄 조회 + 자동 commit
액션만 제공.
"""

from __future__ import annotations

import os
import sys

from .._common import api_endpoint, logger


def _import_worktree_status():
    """internal helper — not exposed as endpoint.

    engine/flow/worktree_status 모듈을 lazy import 한다.
    """
    engine_dir = os.path.normpath(
        os.path.join(os.getcwd(), '.claude-organic', 'engine'),
    )
    if engine_dir not in sys.path:
        sys.path.insert(0, engine_dir)
    from flow import worktree_status  # noqa: WPS433
    return worktree_status


class WorktreeCommitHandlerMixin:
    """Worktree uncommitted indicator + commit action handlers."""

    @api_endpoint("WTC", "uncommitted_all")
    def _handle_worktree_uncommitted_all(self) -> None:
        """GET /api/worktree/uncommitted/all — 전체 워크트리 미커밋 카운트 list.

        method: GET
        url: /api/worktree/uncommitted/all
        domain: WTC
        handler: WorktreeCommitHandlerMixin._handle_worktree_uncommitted_all
        request: query none
        response_ok: [{ticket, branch, dirty_count, ...}]
        response_error: {ok: false, error: str}
        status_codes: 200, 500
        auth: none (local-only)
        side_effects: spawn `git -C <worktree> status --porcelain` subprocesses
        sse_events: none
        """
        try:
            mod = _import_worktree_status()
            data = mod.get_all_uncommitted()
        except Exception as exc:  # noqa: BLE001
            logger.exception('worktree_uncommitted.all failed: %s', exc)
            self._send_error(500, f'get_all_uncommitted failed: {exc}')
            return
        self._send_json(data)

    @api_endpoint("WTC", "commit")
    def _handle_worktree_commit(self) -> None:
        """POST /api/kanban/worktree-commit — 워크트리 자동 commit.

        Body: {ticket: "T-NNN", message?: "..."}.
        message 미지정 시 `wip(T-NNN): pending worktree changes` 자동 채움.

        method: POST
        url: /api/kanban/worktree-commit
        domain: WTC
        handler: WorktreeCommitHandlerMixin._handle_worktree_commit
        request: body {ticket: str, message?: str}
        response_ok: {ok: true, commit_hash: str, message: str}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 409, 500
        auth: none (local-only) — user-triggered
        side_effects: git add + git commit in worktree
        sse_events: kanban_update (via FileWatcher if status changes)
        """
        data = self._read_json_body()
        if data is None:
            return
        ticket = data.get('ticket')
        if not ticket or not isinstance(ticket, str):
            self._send_error(400, 'Missing or invalid "ticket" field')
            return
        message = data.get('message')
        if message is not None and not isinstance(message, str):
            self._send_error(400, '"message" must be a string')
            return
        try:
            mod = _import_worktree_status()
            result = mod.commit_worktree(ticket, message)
        except Exception as exc:  # noqa: BLE001
            logger.exception('worktree_commit failed: %s', exc)
            self._send_error(500, f'commit_worktree failed: {exc}')
            return
        if result.get('ok'):
            self._send_json(result)
        else:
            self._send_json_with_status(409, result)
