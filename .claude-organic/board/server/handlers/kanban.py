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
        """POST /api/kanban/move — {"ticket","to"}: To Do ↔ Open + Open → Review 전이 허용."""
        data = self._read_json_body() or {}
        ticket = (data.get('ticket') or '').strip()
        to = (data.get('to') or '').strip().lower()

        if not ticket or not ticket.startswith('T-'):
            self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
            return
        if to not in ('todo', 'open', 'review'):
            self._send_error(400, 'DnD allows only "todo" / "open" / "review" transitions')
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

    def _handle_kanban_done_verdict(self) -> None:
        """GET /api/kanban/done-verdict?ticket=T-NNN — Done 카드 머지 정합성 advisory verdict.

        T-441: Review→Done DnD 후 develop HEAD == merge commit 정합성 검사.
        verdict OK:   develop HEAD == merge commit && merge commit parents 에 feature branch tip 포함.
        verdict FAIL: 위 조건 미충족 (develop HEAD 가 머지 commit 아님 등).

        advisory only — 자동 회귀/강제 전이 없음 (feedback_no_speculative_guards 캐논).
        """
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        ticket = (qs.get('ticket', [None])[0] or '').strip()

        if not ticket or not _TICKET_RE.match(ticket):
            self._send_error(400, 'Missing or invalid "ticket" query param (T-NNN required)')
            return

        project_root = os.getcwd()

        # Done 디렉터리에 티켓이 존재하는지 확인 (Done 컬럼 아닌 티켓에는 의미 없음)
        done_xml = os.path.join(
            project_root, '.claude-organic', 'tickets', 'done', f'{ticket}.xml',
        )
        if not os.path.isfile(done_xml):
            self._send_json({
                'ticket': ticket,
                'verdict': 'SKIP',
                'reason': 'not_done',
                'details': {'message': f'{ticket} 은 Done 컬럼에 없습니다 — verdict 생략'},
            })
            return

        # merge_commit 읽기: tickets/done/<T-NNN>.xml result/merge_commit 필드
        merge_commit: str | None = None
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(done_xml)
            root = tree.getroot()
            result_el = root.find('.//result/merge_commit')
            if result_el is not None and result_el.text:
                merge_commit = result_el.text.strip() or None
        except Exception:
            merge_commit = None

        if not merge_commit:
            # merge_commit 메타 누락 — Phase 1 인프라 도입 이전 Done 티켓
            self._send_json({
                'ticket': ticket,
                'verdict': 'UNKNOWN',
                'reason': 'no_merge_commit_meta',
                'details': {'message': 'merge_commit 정보 없음 (인프라 도입 이전 Done 티켓)'},
            })
            return

        def _git(*args: str) -> 'subprocess.CompletedProcess[str]':
            return subprocess.run(
                ['git', *args],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=10,
            )

        # develop HEAD SHA 확인
        head_result = _git('rev-parse', 'develop')
        if head_result.returncode != 0:
            self._send_json({
                'ticket': ticket,
                'verdict': 'UNKNOWN',
                'reason': 'git_error',
                'details': {'message': 'develop HEAD 조회 실패: ' + (head_result.stderr or '').strip()},
            })
            return
        develop_head = head_result.stdout.strip()

        # merge_commit SHA 정규화 (full SHA)
        mc_result = _git('rev-parse', merge_commit)
        if mc_result.returncode != 0:
            self._send_json({
                'ticket': ticket,
                'verdict': 'UNKNOWN',
                'reason': 'git_error',
                'details': {'message': f'merge_commit {merge_commit!r} rev-parse 실패'},
            })
            return
        merge_commit_sha = mc_result.stdout.strip()

        # 조건 1: develop HEAD == merge commit
        if develop_head != merge_commit_sha:
            self._send_json({
                'ticket': ticket,
                'verdict': 'FAIL',
                'reason': 'develop_head_mismatch',
                'details': {
                    'message': (
                        f'develop HEAD 가 머지 commit 아님 — '
                        f'HEAD={develop_head[:8]}, merge_commit={merge_commit_sha[:8]}'
                    ),
                    'develop_head': develop_head,
                    'merge_commit': merge_commit_sha,
                },
            })
            return

        # 조건 2: merge commit parents에 feature branch tip 포함 여부
        parents_result = _git('log', merge_commit_sha, '-1', '--format=%P')
        if parents_result.returncode != 0:
            self._send_json({
                'ticket': ticket,
                'verdict': 'UNKNOWN',
                'reason': 'git_error',
                'details': {'message': 'merge commit parents 조회 실패'},
            })
            return
        parent_shas = parents_result.stdout.strip().split()

        # feature 브랜치 패턴 (feat/T-NNN-*)
        feat_branch_result = _git('branch', '--list', f'feat/{ticket}-*')
        feature_branch_exists = feat_branch_result.returncode == 0 and bool(feat_branch_result.stdout.strip())

        feature_tip_in_parents = False
        feature_branch_name: str | None = None
        if feature_branch_exists:
            branch_name = feat_branch_result.stdout.strip().lstrip('* ').split('\n')[0].strip()
            feature_branch_name = branch_name
            feat_tip_result = _git('rev-parse', branch_name)
            if feat_tip_result.returncode == 0:
                feat_tip = feat_tip_result.stdout.strip()
                feature_tip_in_parents = feat_tip in parent_shas
        else:
            # 브랜치가 이미 삭제된 경우 — parents가 2개 이상이면 non-ff 머지로 간주 OK
            feature_tip_in_parents = len(parent_shas) >= 2

        if not feature_tip_in_parents and feature_branch_exists:
            self._send_json({
                'ticket': ticket,
                'verdict': 'FAIL',
                'reason': 'feature_tip_not_in_parents',
                'details': {
                    'message': (
                        f'merge commit 의 parent 에 feature 브랜치 tip 이 포함되지 않음 — '
                        f'branch={feature_branch_name}'
                    ),
                    'merge_commit': merge_commit_sha,
                    'parents': parent_shas,
                },
            })
            return

        # 모든 조건 충족
        self._send_json({
            'ticket': ticket,
            'verdict': 'OK',
            'reason': 'all_checks_passed',
            'details': {
                'message': 'develop HEAD == merge commit, feature branch tip 포함 확인',
                'develop_head': develop_head,
                'merge_commit': merge_commit_sha,
                'parents': parent_shas,
            },
        })
