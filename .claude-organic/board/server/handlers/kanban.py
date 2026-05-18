"""Kanban DnD POST handlers (move/submit/done/delete) — preserves cb7427f regression fixes."""

from __future__ import annotations

import fnmatch
import os
import re
import sys
import subprocess
import threading
from datetime import datetime, timezone

from ._helpers import _TICKET_RE, _KANBAN_ALL_DIRS
from ._kanban_done_helpers import (
    handle_kanban_done_force,
    handle_kanban_done_review,
    check_derived_blocked,
)
from .._common import logger
from ..state import sse_manager
from ..v2_launcher import (
    _LAUNCH_READER_LOCK,
    _LAUNCH_READER_THREADS,
    spawn_v2_driver,
)


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------


def _classify_failure_reason(returncode: int, stderr: str) -> str:
    """flow-launcher 비정상 종료 사유를 stderr·returncode 패턴으로 분류한다.

    T-450 보고서 §5 reason enum:
      - to_do_status:        launcher 측 사전 검증 거부 (티켓이 To Do 상태)
      - http_post_timeout:   H4 urllib timeout=10s
      - http_post_error:     H4 urllib 일반 에러 (URLError 등)
      - workflow_start_error: WorkflowHandler 측 spawn 실패
      - unknown:             그 외 (returncode=0 인데 LAUNCH:/INLINE: 둘 다 아닌 경우 포함)
    """
    if returncode == 0:
        return 'unknown'
    err = stderr or ''
    if 'To Do' in err:
        return 'to_do_status'
    if 'urllib timed out' in err or 'timed out' in err:
        return 'http_post_timeout'
    if 'urllib' in err:
        return 'http_post_error'
    if 'workflow start' in err:
        return 'workflow_start_error'
    return 'unknown'


def _emit_launch_event(event: str, ticket: str, **kwargs: object) -> None:
    """LAUNCH_* 이벤트를 SSE broadcast + workflow.log 동시 기록한다.

    SSE event_type='launch' 단일 채널 재사용 (보고서 §5 — 신규 채널 신설 X).
    payload 의 'event' 필드로 PENDING/STARTED/FAILED 분기 식별.

    Args:
        event:  'LAUNCH_PENDING' | 'LAUNCH_STARTED' | 'LAUNCH_FAILED'
        ticket: T-NNN
        **kwargs: 추가 payload 필드 (command, mode, reason, error_message,
                  latency_ms, submitted_at, session_id, returncode, elapsed_ms 등)
    """
    ts = datetime.now(timezone.utc).isoformat()
    payload: dict[str, object] = {'event': event, 'ts': ts, 'ticket': ticket}
    payload.update(kwargs)

    try:
        sse_manager.broadcast('launch', data=payload)
    except Exception as exc:  # broadcast 실패가 reader thread 자체를 죽이지 않도록 격리
        logger.error('launch SSE broadcast failed: event=%s ticket=%s exc=%r',
                     event, ticket, exc)

    # 별도 파일 신설 X — logger.info 가 board 서버 stderr/log 로 흐른다.
    try:
        extra_kv = ' '.join(
            f'{k}={v!r}' for k, v in kwargs.items()
            if k not in ('error_message',)  # error_message 는 길이 클 수 있어 별도 라인
        )
        logger.info('LAUNCH_EVENT %s ticket=%s %s', event, ticket, extra_kv)
        if 'error_message' in kwargs and kwargs['error_message']:
            logger.info('LAUNCH_EVENT %s ticket=%s error_message=%s',
                        event, ticket, str(kwargs['error_message'])[:500])
    except Exception:  # 로깅 실패도 무시
        pass


def _launch_reader_loop(
    proc: subprocess.Popen,
    ticket: str,
    command: str,
    submitted_at: datetime,
) -> None:
    """flow-launcher Popen 의 stdout/stderr 를 회수하고 LAUNCH_STARTED/FAILED 를 emit 한다.

    proc.communicate() 로 종료까지 무한 대기. timeout 책임은 launcher 측
    H4 urllib timeout=10s + T-904 cleanup 단일 진실 공급원에 위임 (보고서 §6).

    finally 블록에서 thread 핸들 set 자체 제거 (GC 누수 차단).
    """
    self_thread = threading.current_thread()
    try:
        try:
            stdout, stderr = proc.communicate(timeout=None)
        except Exception as exc:  # Popen 자체 실패 (드물지만 방어)
            elapsed_ms = int((datetime.now(timezone.utc) - submitted_at).total_seconds() * 1000)
            _emit_launch_event(
                'LAUNCH_FAILED', ticket,
                reason='reader_loop_exception',
                returncode=None,
                error_message=repr(exc),
                elapsed_ms=elapsed_ms,
                command=command,
            )
            return

        elapsed_ms = int((datetime.now(timezone.utc) - submitted_at).total_seconds() * 1000)
        rc = proc.returncode
        first_line = ((stdout or '').split('\n', 1)[0]).strip() if stdout else ''

        if rc == 0 and first_line.startswith('LAUNCH:'):
            tail = first_line[len('LAUNCH:'):].strip()
            session_id = tail.split()[0] if tail else ''
            _emit_launch_event(
                'LAUNCH_STARTED', ticket,
                session_id=session_id,
                mode='launched',
                spawn_duration_ms=elapsed_ms,
                command=command,
            )
        elif rc == 0 and first_line.startswith('INLINE:'):
            tail = first_line[len('INLINE:'):].strip()
            _emit_launch_event(
                'LAUNCH_STARTED', ticket,
                session_id='',
                mode='inline',
                spawn_duration_ms=elapsed_ms,
                command=command,
                message=tail,
            )
        elif rc == 0:
            # returncode=0 인데 stdout 패턴이 LAUNCH:/INLINE: 둘 다 아님 — unknown 분류
            _emit_launch_event(
                'LAUNCH_FAILED', ticket,
                reason='unknown',
                returncode=0,
                error_message=(first_line or 'no stdout')[:500],
                elapsed_ms=elapsed_ms,
                command=command,
            )
        else:
            reason = _classify_failure_reason(rc, stderr or '')
            _emit_launch_event(
                'LAUNCH_FAILED', ticket,
                reason=reason,
                returncode=rc,
                error_message=((stderr or stdout or '').strip())[:500],
                elapsed_ms=elapsed_ms,
                command=command,
            )
    except Exception as exc:  # reader 루프 자체 예외 (방어)
        try:
            elapsed_ms = int((datetime.now(timezone.utc) - submitted_at).total_seconds() * 1000)
            _emit_launch_event(
                'LAUNCH_FAILED', ticket,
                reason='reader_loop_exception',
                error_message=repr(exc),
                elapsed_ms=elapsed_ms,
                command=command,
            )
        except Exception:
            pass
    finally:
        # GC 누수 차단 — 자신을 핸들 set 에서 제거
        with _LAUNCH_READER_LOCK:
            _LAUNCH_READER_THREADS.discard(self_thread)

# board/server/** + .claude-organic/board/server/** + .claude-organic/engine/** 셋 모두 backend 도메인
_BACKEND_GLOB_PATTERNS = (
    'board/server/*',
    'board/server/**',
    '.claude-organic/board/server/*',
    '.claude-organic/board/server/**',
    '.claude-organic/engine/*',
    '.claude-organic/engine/**',
)

_FEAT_BRANCH_RE = re.compile(r'^feat/(T-\d+)-')


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

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------

    def _resolve_feat_branch(self, ticket: str, project_root: str) -> str | None:
        """티켓 번호로 정확한 feat/T-NNN-* 브랜치명을 조회한다.

        ``git worktree list --porcelain`` 출력을 파싱하여 ``refs/heads/feat/T-NNN-*``
        형태에서 ``feat/T-NNN-*`` 부분만 추출. 워크트리 등록되지 않은 경우 None.
        """
        try:
            r = subprocess.run(
                ['git', 'worktree', 'list', '--porcelain'],
                cwd=project_root, capture_output=True, text=True, timeout=10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
        if r.returncode != 0:
            return None

        for line in r.stdout.splitlines():
            line = line.strip()
            if not line.startswith('branch '):
                continue
            ref = line[len('branch '):].strip()
            if ref.startswith('refs/heads/'):
                ref = ref[len('refs/heads/'):]
            m = _FEAT_BRANCH_RE.match(ref)
            if m and m.group(1) == ticket:
                return ref
        return None

    def _get_current_branch(self, project_root: str) -> str | None:
        """메인 working tree 의 현재 HEAD 브랜치명 반환. 실패 시 None."""
        try:
            r = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=project_root, capture_output=True, text=True, timeout=10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
        if r.returncode != 0:
            return None
        return r.stdout.strip() or None

    def _detect_backend_changes(self, branch: str, project_root: str) -> bool:
        """`git diff --name-only develop..<branch>` 결과에서 backend glob 매칭 여부 반환.

        매칭되면 True (needs_restart=true), 미매칭이면 False.
        diff 호출 자체가 실패하면 보수적으로 False (UI 측에서 강제 재시작 모달 띄우지 않음).
        """
        try:
            r = subprocess.run(
                ['git', 'diff', '--name-only', f'develop..{branch}'],
                cwd=project_root, capture_output=True, text=True, timeout=10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
        if r.returncode != 0:
            return False
        for path in r.stdout.splitlines():
            path = path.strip()
            if not path:
                continue
            for pat in _BACKEND_GLOB_PATTERNS:
                if fnmatch.fnmatch(path, pat):
                    return True
        return False

    def _git_switch(self, branch: str, project_root: str, ignore_other_worktrees: bool = False) -> tuple[bool, str]:
        """메인 working tree 에서 ``git switch <branch>`` 실행. (ok, stderr_or_msg)."""
        cmd = ['git', 'switch']
        if ignore_other_worktrees:
            cmd.append('--ignore-other-worktrees')
        cmd.append(branch)
        try:
            r = subprocess.run(
                cmd,
                cwd=project_root, capture_output=True, text=True, timeout=10,
            )
        except subprocess.TimeoutExpired:
            return False, 'git switch timed out'
        except FileNotFoundError:
            return False, 'git not found'
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or 'git switch failed').strip()
        return True, (r.stdout or '').strip()

    def _handle_kanban_branch_toggle(self) -> None:
        """POST /api/kanban/branch/toggle — Review 카드 feature 브랜치 활성/해제.

        요청: ``{"ticket_number": "T-NNN", "action": "on"|"off"}``

        on:
          - 메인 working tree dirty 검증 (git status --porcelain) → dirty 면 거부
          - feat/T-NNN-* 브랜치 매칭 (git worktree list --porcelain)
          - 메인 working tree 에서 ``git switch <feat 브랜치>``
          - backend 변경 자동 감지 (git diff develop..feat/T-NNN-* 결과 glob 매칭)

        off:
          - 메인 working tree dirty 검증 동일
          - ``git switch develop``

        제약:
          - 자동 stash / 자동 commit / 자동 reset 절대 금지 (사용자 수동 수습 안내만)
          - feedback_no_speculative_guards 캐논 준수
        """
        data = self._read_json_body() or {}
        ticket = (data.get('ticket_number') or '').strip()
        action = (data.get('action') or '').strip().lower()

        if not ticket or not _TICKET_RE.match(ticket):
            self._send_error(400, 'Missing or invalid "ticket_number" (T-NNN required)')
            return
        if action not in ('on', 'off'):
            self._send_error(400, 'Invalid "action" (must be "on" or "off")')
            return

        project_root = os.getcwd()

        # dirty 검증 — 메인 working tree 기준
        dirty = self._get_dirty_files(project_root)
        if dirty:
            self._send_json({
                'ok': False,
                'reason': 'dirty',
                'files': dirty,
                'modal_message': (
                    f'메인 working tree 에 미커밋 변경이 있습니다 ({len(dirty)}개 파일). '
                    f'브랜치 토글은 자동 stash/commit/reset 을 수행하지 않습니다. '
                    f'수동으로 commit / stash / reset 후 다시 시도하세요.'
                ),
                'ticket': ticket,
                'action': action,
            })
            return

        if action == 'off':
            ok, msg = self._git_switch('develop', project_root)
            if not ok:
                self._send_json({
                    'ok': False,
                    'reason': 'git_switch_failed',
                    'message': msg,
                    'ticket': ticket,
                    'action': action,
                })
                return
            self._send_json({
                'ok': True,
                'branch': 'develop',
                'needs_restart': False,
                'active_ticket': None,
            })
            return

        # action == 'on'
        feat_branch = self._resolve_feat_branch(ticket, project_root)
        if not feat_branch:
            self._send_json({
                'ok': False,
                'reason': 'feature_branch_not_found',
                'message': (
                    f'{ticket} 의 feature 브랜치 (feat/{ticket}-*) 를 찾을 수 없습니다. '
                    f'워크트리가 등록되어 있는지 확인하세요 (git worktree list).'
                ),
                'ticket': ticket,
                'action': action,
            })
            return

        ok, msg = self._git_switch(feat_branch, project_root, ignore_other_worktrees=True)
        if not ok:
            self._send_json({
                'ok': False,
                'reason': 'git_switch_failed',
                'message': msg,
                'ticket': ticket,
                'action': action,
                'branch': feat_branch,
            })
            return

        needs_restart = self._detect_backend_changes(feat_branch, project_root)
        self._send_json({
            'ok': True,
            'branch': feat_branch,
            'needs_restart': needs_restart,
            'active_ticket': ticket,
        })

    def _handle_kanban_branch_active(self) -> None:
        """GET /api/kanban/branch/active — 현재 메인 working tree HEAD 브랜치 + active_ticket 반환.

        응답: ``{"branch": "feat/T-NNN-...", "active_ticket": "T-NNN"}`` 또는
              ``{"branch": "develop", "active_ticket": null}``

        frontend 가 페이지 로드 시 active 카드 시각 복원에 사용.
        """
        project_root = os.getcwd()
        branch = self._get_current_branch(project_root)
        if not branch:
            self._send_json({'branch': None, 'active_ticket': None})
            return

        m = _FEAT_BRANCH_RE.match(branch)
        active_ticket = m.group(1) if m else None
        self._send_json({
            'branch': branch,
            'active_ticket': active_ticket,
        })

    def _check_derived_blocked(self, ticket: str, kanban_base: str) -> list[str]:
        """derived-from 파생 티켓 중 Done 이외 상태인 것 반환 (위임)."""
        return check_derived_blocked(ticket, kanban_base, _KANBAN_ALL_DIRS)

    def _handle_kanban_move(self) -> None:
        """POST /api/kanban/move — {"ticket","to"}: To Do ↔ Open + Open → Review + Review → Open 전이 허용."""
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
        """POST /api/kanban/submit — {"ticket","command"}: v2 driver 비동기 spawn.

        T-500: spawn 책임은 ``server.v2_launcher.spawn_v2_driver()`` 로 분리.
        본 handler 는 입력 validation → 위임 → JSON 응답만 담당.

        Stage 3-B (T-489) + T-495 P2 의미론은 v2_launcher 안에 보존되어 있다:
          - flow-wf submit (v2 driver) Popen.
          - V2_BOARD_POST=true + V2_REGISTRY_KEY env 자동 주입.
          - LAUNCH_PENDING + LAUNCH_STARTED 모두 Popen 직후 즉시 발사.
          - reader thread = driver rc != 0 일 때만 LAUNCH_FAILED 발사.
          - 응답 키 ``{ok, status:'starting', ticket, command, submitted_at, session_id}``
            완전 보존 (회귀 0건).
        """
        data = self._read_json_body() or {}
        ticket = (data.get('ticket') or '').strip()
        command = (data.get('command') or '').strip()

        if not ticket or not re.match(r'^T-\d+$', ticket):
            self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
            return
        if command not in ('implement', 'research', 'review'):
            self._send_error(400, 'Invalid "command" (must be implement/research/review)')
            return

        result = spawn_v2_driver(ticket, command)
        if not result.get('ok'):
            kind = result.get('error_kind') or 'spawn_failed'
            msg = result.get('message') or 'v2 driver spawn failed'
            self._send_error(500, f'{kind}: {msg}')
            return
        self._send_json(result)

    def _handle_kanban_done(self) -> None:
        """POST /api/kanban/done — {"ticket","force","force_dirty"}.

        force=false: Review → Done.
        force=true:  Open → Done.
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
        """POST /api/kanban/delete — {"ticket"}: derived-from 가드 + delete + worktree 정리."""
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

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------

    def _resolve_audit_workdir(self, ticket: str, project_root: str) -> 'str | None':
        """티켓 번호로 최신 work_dir 경로를 결정한다.

        1순위: tickets/<status>/<T-NNN>.xml 의 <result>/<workdir> 필드 참조
        2순위: runs/ 디렉터리들을 mtime 역순으로 순회하여 status.json ticket_number 매칭

        Returns None if not found.
        """
        import xml.etree.ElementTree as ET
        import glob as _glob

        tickets_root = os.path.join(project_root, ".claude-organic", "tickets")
        kanban_dirs = ("todo", "open", "progress", "review", "done")

        # 1순위: XML <result>/<workdir>
        for kdir in kanban_dirs:
            xml_path = os.path.join(tickets_root, kdir, f"{ticket}.xml")
            if not os.path.isfile(xml_path):
                continue
            try:
                tree = ET.parse(xml_path)
                root_el = tree.getroot()
                wd_el = root_el.find(".//result/workdir")
                if wd_el is not None and wd_el.text and wd_el.text.strip():
                    wd = wd_el.text.strip()
                    if not os.path.isabs(wd):
                        wd = os.path.join(project_root, wd)
                    return wd
            except Exception:
                pass

        # 2순위: runs/ 디렉터리 순회 (mtime 역순)
        runs_root = os.path.join(project_root, ".claude-organic", "runs")
        if not os.path.isdir(runs_root):
            return None
        try:
            run_dirs = [
                d for d in _glob.glob(os.path.join(runs_root, "*"))
                if os.path.isdir(d) and not os.path.basename(d).startswith("_")
            ]
            run_dirs.sort(key=lambda d: os.path.getmtime(d), reverse=True)
        except Exception:
            return None

        import json as _json
        for rdir in run_dirs:
            # status.json ticket_number 필드
            status_path = os.path.join(rdir, "status.json")
            if os.path.isfile(status_path):
                try:
                    with open(status_path, encoding="utf-8") as f:
                        sdata = _json.load(f)
                    if sdata.get("ticket_number") == ticket:
                        return rdir
                except Exception:
                    pass

        return None

    @staticmethod
    def _compute_combined_verdict(tier1, tier2) -> str:
        """1차+2차 worst-of 통합 verdict 산출.

        Rules (priority order):
          1. either overall == FAIL  -> FAIL
          2. either overall == WARN  -> WARN
          3. both   overall == PASS  -> PASS
          4. one None + one PASS     -> PASS
          5. one None + non-PASS     -> NONE
          6. both None               -> NONE

        advisory only — 어떤 칸반 전이/차단도 없음.
        """
        def _overall(d) -> "str | None":
            if d is None:
                return None
            return (d.get("overall") or "").upper() or None

        o1 = _overall(tier1)
        o2 = _overall(tier2)

        if o1 == "FAIL" or o2 == "FAIL":
            return "FAIL"
        if o1 == "WARN" or o2 == "WARN":
            return "WARN"
        if o1 == "PASS" and o2 == "PASS":
            return "PASS"
        if (o1 == "PASS" and o2 is None) or (o1 is None and o2 == "PASS"):
            return "PASS"
        return "NONE"

    def _handle_kanban_audit_verdict(self) -> None:
        """GET /api/kanban/audit/verdict?ticket=T-NNN — Auditor T3 advisory verdict 조회.

        W04 runner.py 가 work_dir 루트에 영속한 audit-verdict.json 을 읽어
        {ticket, tier1, tier2, combined} 를 반환한다.

        파일 미존재 시 {"tier1": null, "tier2": null, "combined": "NONE"} 반환 (404 X).
        advisory only — 자동 차단/강제 전이/칸반 회귀 없음 (feedback_no_speculative_guards 캐논).
        """
        from urllib.parse import urlparse, parse_qs
        import json as _json

        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        ticket = (qs.get("ticket", [None])[0] or "").strip()

        if not ticket or not _TICKET_RE.match(ticket):
            self._send_error(400, 'Missing or invalid "ticket" query param (T-NNN required)')
            return

        _NONE_RESPONSE = {"tier1": None, "tier2": None, "combined": "NONE"}

        project_root = os.getcwd()
        work_dir = self._resolve_audit_workdir(ticket, project_root)
        if not work_dir:
            self._send_json(_NONE_RESPONSE)
            return

        verdict_path = os.path.join(work_dir, "audit-verdict.json")
        if not os.path.isfile(verdict_path):
            self._send_json(_NONE_RESPONSE)
            return

        try:
            with open(verdict_path, encoding="utf-8") as f:
                data = _json.load(f)
        except Exception:
            self._send_json(_NONE_RESPONSE)
            return

        tier1 = data.get("tier1")  # None or dict
        tier2 = data.get("tier2")  # None or dict

        # Recompute combined (worst-of) — do not trust stored value blindly
        combined = self._compute_combined_verdict(tier1, tier2)

        self._send_json({
            "ticket": ticket,
            "tier1": tier1,
            "tier2": tier2,
            "combined": combined,
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

    def _handle_kanban_review_verdict(self) -> None:
        """GET /api/kanban/review-verdict?ticket=T-NNN -- Review 카드 룰베이스 advisory verdict.

        T-463: finalization.py W04 hook 이 생성한 review-verdict.json 을 읽어
        verdict (PASS / WARN / FAIL / SKIP / UNKNOWN) 를 반환한다.

        advisory only -- kanban move / status 전이 / 자동 회귀 없음.
        (feedback_no_speculative_guards 캐논 / T-411 commit 0c970fa 폐기 사례)
        """
        import json as _json
        import xml.etree.ElementTree as ET
        from urllib.parse import urlparse, parse_qs
        from pathlib import Path

        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        ticket = (qs.get('ticket', [None])[0] or '').strip()

        if not ticket:
            self._send_error(400, 'ticket parameter required')
            return
        if not _TICKET_RE.match(ticket):
            self._send_error(400, 'invalid ticket format')
            return

        project_root = os.getcwd()
        tickets_base = os.path.join(project_root, '.claude-organic', 'tickets')

        # 1. review/<ticket>.xml 또는 done/<ticket>.xml 탐색
        ticket_xml_path: str | None = None
        review_xml = os.path.join(tickets_base, 'review', f'{ticket}.xml')
        done_xml = os.path.join(tickets_base, 'done', f'{ticket}.xml')

        if os.path.isfile(review_xml):
            ticket_xml_path = review_xml
        elif os.path.isfile(done_xml):
            ticket_xml_path = done_xml
        else:
            # todo / open / progress 컬럼 -- Review/Done 이외 -> SKIP
            self._send_json({
                'ticket': ticket,
                'verdict': 'SKIP',
                'reason': 'not_review',
                'details': {'message': f'{ticket} 은 Review/Done 컬럼에 없습니다'},
                'violations': [],
            })
            return

        # 2. XML 파싱 -> registrykey 추출
        registry_key: str | None = None
        try:
            tree = ET.parse(ticket_xml_path)
            root = tree.getroot()
            rk_el = root.find('.//result/registrykey')
            if rk_el is not None and rk_el.text:
                registry_key = rk_el.text.strip() or None
        except Exception:
            registry_key = None

        if not registry_key:
            self._send_json({
                'ticket': ticket,
                'verdict': 'UNKNOWN',
                'reason': 'no_registry_key',
                'details': {'message': 'registrykey 정보 없음 (워크플로우 인프라 도입 이전 티켓일 수 있음)'},
                'violations': [],
            })
            return

        # 3. review-verdict.json 읽기
        # runs/<registry_key> 또는 runs/.history/<registry_key> 탐색
        runs_base = os.path.join(project_root, '.claude-organic', 'runs')
        verdict_path: Path | None = None
        for candidate in (
            Path(runs_base) / registry_key / 'review-verdict.json',
            Path(runs_base) / '.history' / registry_key / 'review-verdict.json',
        ):
            if candidate.is_file():
                verdict_path = candidate
                break

        if verdict_path is None:
            self._send_json({
                'ticket': ticket,
                'verdict': 'UNKNOWN',
                'reason': 'no_verdict_meta',
                'details': {
                    'message': f'review-verdict.json 없음 (registry_key={registry_key})',
                    'registry_key': registry_key,
                },
                'violations': [],
            })
            return

        try:
            verdict_dict = _json.loads(verdict_path.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            self._send_json({
                'ticket': ticket,
                'verdict': 'UNKNOWN',
                'reason': 'invalid_verdict_json',
                'details': {
                    'message': 'review-verdict.json 파싱 실패',
                    'registry_key': registry_key,
                },
                'violations': [],
            })
            return

        # 4. ticket 필드 주입 후 반환
        verdict_dict['ticket'] = ticket
        self._send_json(verdict_dict)
