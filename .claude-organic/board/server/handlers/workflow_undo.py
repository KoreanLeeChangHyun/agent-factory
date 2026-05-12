"""Workflow undo-done handler."""

from __future__ import annotations

import os
import subprocess

from ._helpers import (
    _TICKET_RE,
    _UNDO_ERROR_RE,
    _UNDO_STRATEGY_RESET,
    _UNDO_STRATEGY_REVERT,
    _UNDO_WORKTREE_RE,
)


class WorkflowUndoHandlerMixin:
    """Workflow undo-done handler.

    Done 처리된 워크플로우를 Review 단계로 자동 롤백하는 POST 핸들러.
    내부적으로 flow-undo-done 을 호출한다.
    """

    def _handle_workflow_undo_done(self) -> None:
        """POST /api/workflow/undo-done — body {"ticket": "T-NNN", "force": bool}.

        Done 처리된 워크플로우를 Review 단계로 자동 롤백한다.

        내부적으로 `flow-undo-done T-NNN [--force]` 를 호출하여
        develop reset/revert + feature 브랜치 + worktree 재생성 + 칸반 force 전이
        를 위임한다. stdout 을 파싱해 전략(reset/revert), 재생성된 worktree 정보,
        에러 메시지를 추출하여 프론트로 반환한다.

        성공 응답 (200):
            {ok: true, kind: 'reset_ok'|'revert_ok',
             ticket, strategy, merge_commit?, branch?, worktree_path?,
             stdout, message}

        실패 응답 (409):
            {ok: false, kind: 'error', error: <message>, ticket, stdout, stderr}

        타임아웃(504) / 실행파일 없음(500) 패턴은 _handle_kanban_done 답습.
        """
        data = self._read_json_body() or {}
        ticket = (data.get('ticket') or '').strip()
        force = bool(data.get('force', False))

        # 입력 검증 — ^T-\d+$ 형식만 허용
        if not ticket or not _TICKET_RE.match(ticket):
            self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
            return

        # Done 상태 사전 확인 — done/<T-NNN>.xml 존재 여부로 판별
        # 반환이므로 list[dict] 가정한 옛 로직은 항상 fail)
        project_root = os.getcwd()
        done_xml = os.path.join(
            project_root, '.claude-organic', 'tickets', 'done', f'{ticket}.xml',
        )
        if not os.path.isfile(done_xml):
            self._send_error(
                400,
                f'{ticket} is not in Done column (undo-done targets Done tickets only)',
            )
            return

        # flow-undo-done 호출 — 워크트리 재생성 등을 고려해 timeout 180초
        flow_undo_done = os.path.join(
            project_root, '.claude-organic', 'bin', 'flow-undo-done',
        )
        cmd_args = [flow_undo_done, ticket]
        if force:
            cmd_args.append('--force')
        try:
            result = subprocess.run(
                cmd_args,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired:
            self._send_error(504, 'flow-undo-done timed out (180s)')
            return
        except FileNotFoundError:
            self._send_error(500, f'flow-undo-done not found: {flow_undo_done}')
            return

        stdout = result.stdout or ''
        stderr = result.stderr or ''

        # stdout + stderr 모두 라인 단위 파싱 — undo_done.py 는 _log 를 stdout 으로,
        # _err / _warn 을 stderr 로 출력한다. 전략/워크트리 메시지는 stdout, 에러는 stderr.
        all_lines = stdout.splitlines() + stderr.splitlines()

        strategy = ''
        worktree_path = ''
        branch = ''
        error_message = ''

        for line in all_lines:
            if not strategy and _UNDO_STRATEGY_RESET.search(line):
                strategy = 'reset'
            elif not strategy and _UNDO_STRATEGY_REVERT.search(line):
                strategy = 'revert'
            wt_match = _UNDO_WORKTREE_RE.search(line)
            if wt_match:
                worktree_path = wt_match.group(1).strip()
                branch = wt_match.group(2).strip()
            err_match = _UNDO_ERROR_RE.search(line)
            if err_match and not error_message:
                error_message = err_match.group(1).strip()

        if result.returncode == 0:
            kind = 'reset_ok' if strategy == 'reset' else 'revert_ok' if strategy == 'revert' else 'unknown_ok'
            self._send_json({
                'ok': True,
                'kind': kind,
                'ticket': ticket,
                'strategy': strategy,
                'branch': branch,
                'worktree_path': worktree_path,
                'message': f'{ticket} 롤백 완료 (전략: {strategy or "?"})',
                'stdout': stdout.strip(),
            })
            return

        # 실패 — error_message 우선, 없으면 stderr 끝에서 비어있지 않은 라인 사용
        if not error_message:
            for line in reversed(stderr.splitlines()):
                stripped = line.strip()
                if stripped:
                    error_message = stripped
                    break
        if not error_message:
            error_message = f'flow-undo-done exited with code {result.returncode}'

        self._send_json_with_status(409, {
            'ok': False,
            'kind': 'error',
            'ticket': ticket,
            'error': error_message,
            'message': error_message,
            'stdout': stdout.strip(),
            'stderr': stderr.strip(),
        })
