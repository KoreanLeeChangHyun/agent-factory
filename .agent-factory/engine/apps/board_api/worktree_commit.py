"""Worktree uncommitted indicator + commit action handlers.

User manual when workflow regresses after T-419 diagnostic handler abolition (99c9ce0)
Bringing back simplicity with apprenticeship paths. Batch inquiry of indicators at the top right of the card + automatic commit
Action only provided.
"""

from __future__ import annotations

import os
import sys

from board.server.support.common import api_endpoint, logger


def _import_worktree_status():
    """internal helper — not exposed as endpoint.

    Lazy import the engine/flow/worktree_status module.
    """
    engine_dir = os.path.normpath(
        os.path.join(os.getcwd(), '.agent-factory', 'engine'),
    )
    if engine_dir not in sys.path:
        sys.path.insert(0, engine_dir)
    from flow import worktree_status  # noqa: WPS433
    return worktree_status


class WorktreeCommitHandlerMixin:
    """Worktree uncommitted indicator + commit action handlers."""

    @api_endpoint("WTC", "uncommitted_all")
    def _handle_worktree_uncommitted_all(self) -> None:
        """GET /api/worktree/uncommitted/all — List of entire worktree uncommitted counts.

        method: GET
        url: /api/worktree/uncommitted/all
        domain: WTC
        handler: WorktreeCommitHandlerMixin._handle_worktree_uncommitted_all
        request: query none
        response_ok: [{work_request, branch, dirty_count, ...}]
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
        """POST /api/conveyor/worktree-commit — Worktree automatic commit.

        Body: {work_request: "WR-NNN", message?: "..."}.
        If message is not specified, `wip(WR-NNN): pending worktree changes` is automatically filled.

        method: POST
        url: /api/conveyor/worktree-commit
        domain: WTC
        handler: WorktreeCommitHandlerMixin._handle_worktree_commit
        request: body {work_request: str, message?: str}
        response_ok: {ok: true, commit_hash: str, message: str}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 409, 500
        auth: none (local-only) — user-triggered
        side_effects: git add + git commit in worktree
        sse_events: conveyor_update (via FileWatcher if status changes)
        """
        data = self._read_json_body()
        if data is None:
            return
        work_request = data.get('work_request')
        if not work_request or not isinstance(work_request, str):
            self._send_error(400, 'Missing or invalid "work_request" field')
            return
        message = data.get('message')
        if message is not None and not isinstance(message, str):
            self._send_error(400, '"message" must be a string')
            return
        try:
            mod = _import_worktree_status()
            result = mod.commit_worktree(work_request, message)
        except Exception as exc:  # noqa: BLE001
            logger.exception('worktree_commit failed: %s', exc)
            self._send_error(500, f'commit_worktree failed: {exc}')
            return
        if result.get('ok'):
            self._send_json(result)
        else:
            self._send_json_with_status(409, result)
