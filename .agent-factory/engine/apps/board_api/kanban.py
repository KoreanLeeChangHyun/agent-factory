"""Kanban DnD POST handlers (move/submit/done/delete) — preserves cb7427f regression fixes.

T-513 P2 — `_handle_kanban_undo_done` / `_handle_kanban_workflow_entries` /
Absorb `_handle_kanban_workflow_detail` (old V1 undo / generic branch / list+entries+detail
domain transfer). V1 endpoint body + alias routing is collectively discarded in P5 — this mixin
KANBAN domain single point of entry.
"""

from __future__ import annotations

import fnmatch
import os
import re
import sys
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from engine.adapters.kanban import XmlWorkRequestStore
from engine.apps.board_api.handler_common import _TICKET_RE, _KANBAN_ALL_DIRS
from engine.apps.board_api.kanban_done_helpers import (
    handle_kanban_done_force,
    handle_kanban_done_review,
    check_derived_blocked,
)
from engine.apps.board_api.kanban_done_re import (
    _UNDO_ERROR_RE,
    _UNDO_STRATEGY_RESET,
    _UNDO_STRATEGY_REVERT,
    _UNDO_WORKTREE_RE,
)
from board.server.support.common import (
    _list_workflow_entries,
    _workflow_detail,
    api_endpoint,
    logger,
)
from board.server.runtime.state import sse_manager
from board.server.processes.production_line_launcher import (
    _LAUNCH_READER_LOCK,
    _LAUNCH_READER_THREADS,
    spawn_production_line,
)
from engine.core.work_requests import (
    OuroborosEntry,
    OuroborosPhase,
    OuroborosState,
    WorkRequestRef,
)


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------


def _classify_failure_reason(returncode: int, stderr: str) -> str:
    """internal helper — not exposed as endpoint.

    Reasons for abnormal termination of flow-launcher are classified into stderr·returncode patterns.

    T-450 Report §5 reason enum:
      - to_do_status: Launcher side pre-verification denied (ticket is in To Do status)
      - http_post_timeout:   H4 urllib timeout=10s
      - http_post_error: H4 urllib general error (URLError, etc.)
      - workflow_start_error: WorkflowHandler spawn failure
      - unknown: Others (including cases where returncode=0 and LAUNCH:/INLINE: are neither)
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
    """internal helper — not exposed as endpoint.

    LAUNCH_* events are recorded simultaneously in SSE broadcast + workflow.log.

    SSE event_type='launch' Reuse of single channel (Report §5 — Creation of new channel
    Identify PENDING/STARTED/FAILED branches with the 'event' field in payload.

    Args:
        event:  'LAUNCH_PENDING' | 'LAUNCH_STARTED' | 'LAUNCH_FAILED'
        ticket: T-NNN
        **kwargs: Additional payload fields (command, mode, reason, error_message,
                  latency_ms, submitted_at, session_id, returncode, elapsed_ms, etc.)
    """
    ts = datetime.now(timezone.utc).isoformat()
    payload: dict[str, object] = {'event': event, 'ts': ts, 'ticket': ticket}
    payload.update(kwargs)

    try:
        sse_manager.broadcast('launch', data=payload)
    except Exception as exc:  # Isolate broadcast failures so they don't kill the reader thread itself
        logger.error('launch SSE broadcast failed: event=%s ticket=%s exc=%r',
                     event, ticket, exc)

    # Create a separate file X — logger.info flows to the board server stderr/log.
    try:
        extra_kv = ' '.join(
            f'{k}={v!r}' for k, v in kwargs.items()
            if k not in ('error_message',)  # error_message can be long so it is a separate line
        )
        logger.info('LAUNCH_EVENT %s ticket=%s %s', event, ticket, extra_kv)
        if 'error_message' in kwargs and kwargs['error_message']:
            logger.info('LAUNCH_EVENT %s ticket=%s error_message=%s',
                        event, ticket, str(kwargs['error_message'])[:500])
    except Exception:  # Ignore logging failures
        pass


def _record_workrequest_ouroboros(
    project_root: str,
    ticket: str,
    action: str,
    text: str,
) -> bool:
    """internal helper — persist authoring-loop history after facade success."""

    try:
        store = XmlWorkRequestStore(Path(project_root) / ".agent-factory" / "tickets")
        request = store.get(WorkRequestRef.parse(ticket))
        entries = _ouroboros_entries_for_action(request.ouroboros_history, action, text)
        if not entries:
            return True
        request.ouroboros_history.extend(entries)
        store.save(request)
        return True
    except (FileNotFoundError, TypeError, ValueError) as exc:
        logger.debug("Could not record WorkRequest Ouroboros history for %s: %s", ticket, exc)
        return False


def _ouroboros_entries_for_action(
    history: list[object],
    action: str,
    text: str,
) -> list[OuroborosEntry]:
    """internal helper — build Ouroboros history entries for one action."""
    current = _last_ouroboros_phase(history)
    if action == "create":
        if history or current is not OuroborosPhase.DRAFT:
            return []
        return [OuroborosEntry(phase=OuroborosPhase.DRAFT, text=text)]

    entries: list[OuroborosEntry] = []
    if action == "refine" and current is OuroborosPhase.ACCEPT:
        entries.append(
            OuroborosEntry(
                phase=OuroborosPhase.DRAFT,
                text="Reopened accepted WorkRequest for another refinement loop.",
            )
        )
        current = OuroborosPhase.DRAFT

    state = OuroborosState(current=current)
    if action == "refine":
        _advance_to_rewrite(state, text)
    elif action == "accept":
        if state.current is OuroborosPhase.ACCEPT:
            return []
        _advance_to_accept(state, text)
    else:
        return []
    entries.extend(state.history)
    return entries


def _last_ouroboros_phase(history: list[object]) -> OuroborosPhase:
    """internal helper — return the last persisted Ouroboros phase."""
    for entry in reversed(history):
        phase = getattr(entry, "phase", None)
        if isinstance(phase, OuroborosPhase):
            return phase
        if isinstance(phase, str) and phase:
            return OuroborosPhase(phase)
    return OuroborosPhase.DRAFT


def _advance_to_rewrite(state: OuroborosState, text: str) -> None:
    """internal helper — advance an authoring state to REWRITE."""
    if state.current is OuroborosPhase.REWRITE:
        state.advance(OuroborosPhase.CLARIFY, "Started another refinement pass.")
    if state.current is OuroborosPhase.DRAFT:
        state.advance(OuroborosPhase.CLARIFY, "Captured WorkRequest fields for refinement.")
    if state.current is OuroborosPhase.CLARIFY:
        state.advance(OuroborosPhase.CRITIQUE, "Checked ambiguity, criteria, constraints, and target.")
    if state.current is OuroborosPhase.CRITIQUE:
        state.advance(OuroborosPhase.REWRITE, text)


def _advance_to_accept(state: OuroborosState, text: str) -> None:
    """internal helper — advance an authoring state to ACCEPT."""
    if state.current is OuroborosPhase.DRAFT:
        state.advance(OuroborosPhase.CLARIFY, "Captured minimum fields before acceptance.")
    if state.current is OuroborosPhase.CLARIFY:
        state.advance(OuroborosPhase.CRITIQUE, "Checked WorkRequest quality before acceptance.")
    if state.current in (OuroborosPhase.CRITIQUE, OuroborosPhase.REWRITE):
        state.advance(OuroborosPhase.ACCEPT, text)


def _launch_reader_loop(
    proc: subprocess.Popen,
    ticket: str,
    command: str,
    submitted_at: datetime,
) -> None:
    """internal helper — not exposed as endpoint.

    Recover stdout/stderr of flow-launcher Popen and emit LAUNCH_STARTED/FAILED.

    Infinite wait until completion with proc.communicate(). The timeout responsibility is on the launcher side.
    H4 urllib timeout=10s + T-904 cleanup delegated to single source of truth (Report §6).

    Remove thread handle set itself from finally block (block GC leak).
    """
    self_thread = threading.current_thread()
    try:
        try:
            stdout, stderr = proc.communicate(timeout=None)
        except Exception as exc:  # Popen itself fails (rare but defensive)
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
            # returncode=0 but stdout pattern is LAUNCH:/INLINE: neither — unknown classification
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
    except Exception as exc:  # reader loop self exception (defense)
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
        # Block GC leaks — remove yourself from handle set
        with _LAUNCH_READER_LOCK:
            _LAUNCH_READER_THREADS.discard(self_thread)

# board/server/** + .agent-factory/board/server/** + .agent-factory/engine/** All three backend domains
_BACKEND_GLOB_PATTERNS = (
    'board/server/*',
    'board/server/**',
    '.agent-factory/board/server/*',
    '.agent-factory/board/server/**',
    '.agent-factory/engine/*',
    '.agent-factory/engine/**',
)

_FEAT_BRANCH_RE = re.compile(r'^feat/(T-\d+)-')


class KanbanHandlerMixin:
    """Kanban DnD POST handlers (move/submit/done/delete) — preserves cb7427f regression fixes."""

    def _get_dirty_files(self, wt_path: str) -> list[str]:
        """internal helper — not exposed as endpoint.

        Returns a list of worktree uncommitted files (git status --porcelain parsing).
        """
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
        """internal helper — not exposed as endpoint.

        Search for the exact feat/T-NNN-* branch name using the ticket number.

        Parse the output of ``git worktree list --porcelain`` into ``refs/heads/feat/T-NNN-*``
        Extract only the ``feat/T-NNN-*`` part from the form. None if the work tree is not registered.
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
        """internal helper — not exposed as endpoint.

        Returns the current HEAD branch name of the main working tree. None on failure.
        """
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
        """internal helper — not exposed as endpoint.

        Returns whether the backend glob matches in the result of `git diff --name-only develop..<branch>`.

        True if matched (needs_restart=true), False if not matched.
        Conservatively set to False if the diff call itself fails (do not pop up a force restart modal on the UI side).
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
        """internal helper — not exposed as endpoint.

        Execute ``git switch <branch>`` in the main working tree. (ok, stderr_or_msg).
        """
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

    @api_endpoint("K", "branch_toggle")
    def _handle_kanban_branch_toggle(self) -> None:
        """POST /api/kanban/branch/toggle — Enable/disable Review card feature branch.

        Request: ``{"ticket_number": "T-NNN", "action": "on"|"off"}``

        on:
          - Verify main working tree dirty (git status --porcelain) → Reject if dirty
          - feat/T-NNN-* branch matching (git worktree list --porcelain)
          - ``git switch <feat branch>`` in the main working tree
          - Automatic detection of backend changes (git diff develop..feat/T-NNN-* result glob matching)

        off:
          - Same as main working tree dirty verification
          - ``git switch develop``

        Constraints:
          - Automatic stash / automatic commit / automatic reset is absolutely prohibited (user manual correction guidance only)
          - feedback_no_speculative_guards Canon compliance

        method: POST
        url: /api/kanban/branch/toggle
        domain: K
        handler: KanbanHandlerMixin._handle_kanban_branch_toggle
        request: body {ticket_number: str, action: on|off}
        response_ok: {ok: true, branch: str, needs_restart: bool}
        response_error: {ok: false, error: str, dirty_files?: list}
        status_codes: 200, 400, 409
        auth: none (local-only) — user-triggered
        side_effects: `git switch` in main working tree
        sse_events: git_branch (via GitBranchWatcher)
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

        # Dirty verification — based on main working tree
        dirty = self._get_dirty_files(project_root)
        if dirty:
            self._send_json({
                'ok': False,
                'reason': 'dirty',
                'files': dirty,
                'modal_message': (
                    f'There are uncommitted changes in the main working tree ({len(dirty)} files).'
                    f'Branch toggle does not perform automatic stash/commit/reset.'
                    f'Please manually commit / stash / reset and try again.'
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
                    f'The feature branch (feat/{ticket}-*) of {ticket} could not be found.'
                    f'Check if the worktree is registered (git worktree list).'
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

    @api_endpoint("K", "branch_active")
    def _handle_kanban_branch_active(self) -> None:
        """GET /api/kanban/branch/active — Returns the current main working tree HEAD branch + active_ticket.

        Response: ``{"branch": "feat/T-NNN-...", "active_ticket": "T-NNN"}`` or
              ``{"branch": "develop", "active_ticket": null}``

        Used by the frontend to restore the active card visual when the page is loaded.

        method: GET
        url: /api/kanban/branch/active
        domain: K
        handler: KanbanHandlerMixin._handle_kanban_branch_active
        request: query none
        response_ok: {branch: str|null, active_ticket: T-NNN|null}
        response_error: n/a (always 200)
        status_codes: 200
        auth: none (local-only)
        side_effects: spawn `git branch --show-current`
        sse_events: none
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
        """internal helper — not exposed as endpoint.

        derived-from Returns derived tickets with a status other than Done (delegation).
        """
        return check_derived_blocked(ticket, kanban_base, _KANBAN_ALL_DIRS)

    @api_endpoint("K", "move")
    def _handle_kanban_move(self) -> None:
        """POST /api/kanban/move — {"ticket","to"}: Allow transition To Do ↔ Open + Open → Review + Review → Open.

        method: POST
        url: /api/kanban/move
        domain: K
        handler: KanbanHandlerMixin._handle_kanban_move
        request: body {ticket: T-NNN, to: todo|open|review}
        response_ok: {ok: true, ticket, to, stdout: str}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 500, 504
        auth: none (local-only)
        side_effects: flow-kanban move subprocess
        sse_events: kanban_update (via FileWatcher)
        """
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
        flow_kanban = os.path.join(project_root, '.agent-factory', 'bin', 'flow-kanban')
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

    @api_endpoint("K", "submit")
    def _handle_kanban_submit(self) -> None:
        """POST /api/kanban/submit — {"ticket","command"}: production-line asynchronous spawn.

        T-500: Spawn responsibility is separated into ``server.production_line_launcher.spawn_production_line()``.
        This handler is only responsible for input validation → delegation → JSON response.

        Stage 3-B (T-489) + T-495 P2 semantics are preserved in production_line_launcher:
          - flow-wf submit (production-line) Popen.
          - V2_BOARD_POST=true + V2_REGISTRY_KEY env auto-injection.
          - LAUNCH_PENDING + LAUNCH_STARTED Both fire immediately after Popen.
          - LAUNCH_FAILED fires only when reader thread = driver rc != 0.
          - Response key ``{ok, status:'starting', ticket, command, submitted_at, session_id}``
            Full retention (0 regressions).

        method: POST
        url: /api/kanban/submit
        domain: K
        handler: KanbanHandlerMixin._handle_kanban_submit
        request: body {ticket: T-NNN, command: implement|research|review}
        response_ok: {ok: true, status: starting, ticket, command, submitted_at, session_id}
        response_error: {ok: false, error: str, error_kind?: str}
        status_codes: 200, 400, 500
        auth: none (local-only)
        side_effects: spawn production-line subprocess, kanban Open → In Progress
        sse_events: launch (LAUNCH_PENDING, LAUNCH_STARTED), kanban_update
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

        result = spawn_production_line(ticket, command)
        if not result.get('ok'):
            kind = result.get('error_kind') or 'spawn_failed'
            msg = result.get('message') or 'production-line spawn failed'
            self._send_error(500, f'{kind}: {msg}')
            return
        self._send_json(result)

    @api_endpoint("K", "done")
    def _handle_kanban_done(self) -> None:
        """POST /api/kanban/done — {"ticket","force","force_dirty"}.

        force=false: Review → Done.
        force=true:  Open → Done.
        Detailed logic is delegated to _kanban_done_helpers.py.

        method: POST
        url: /api/kanban/done
        domain: K
        handler: KanbanHandlerMixin._handle_kanban_done
        request: body {ticket: T-NNN, force?: bool, force_dirty?: bool}
        response_ok: {ok: true, ticket, merge_commit?, message}
        response_error: {ok: false, error: str, blocked_derived?: list}
        status_codes: 200, 400, 409, 500, 504
        auth: none (local-only) — user-triggered
        side_effects: flow-merge subprocess (commit + worktree cleanup + kanban move)
        sse_events: kanban_update (via FileWatcher)
        """
        data = self._read_json_body() or {}
        ticket = (data.get('ticket') or '').strip()
        force = bool(data.get('force', False))
        force_dirty = bool(data.get('force_dirty', False))

        if not ticket or not _TICKET_RE.match(ticket):
            self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
            return

        project_root = os.getcwd()
        flow_kanban = os.path.join(project_root, '.agent-factory', 'bin', 'flow-kanban')

        if force:
            handle_kanban_done_force(self, ticket, force_dirty, project_root, flow_kanban)
        else:
            handle_kanban_done_review(self, ticket, project_root, flow_kanban)

    @api_endpoint("K", "delete")
    def _handle_kanban_delete(self) -> None:
        """POST /api/kanban/delete — {"ticket"}: derived-from guard + delete + worktree cleanup.

        method: POST
        url: /api/kanban/delete
        domain: K
        handler: KanbanHandlerMixin._handle_kanban_delete
        request: body {ticket: T-NNN}
        response_ok: {ok: true, ticket, stdout, worktree_removed: bool}
        response_error: {ok: false, error_kind: derived_blocked|other, blocked_by, message}
        status_codes: 200, 400, 409, 500, 504
        auth: none (local-only) — user-triggered
        side_effects: flow-kanban delete + worktree_manager.remove_worktree
        sse_events: kanban_update (via FileWatcher)
        """
        data = self._read_json_body() or {}
        ticket = (data.get('ticket') or '').strip()

        if not ticket or not _TICKET_RE.match(ticket):
            self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
            return

        project_root = os.getcwd()
        kanban_base = os.path.join(project_root, '.agent-factory', 'tickets')

        not_done = self._check_derived_blocked(ticket, kanban_base)
        if not_done:
            self._send_json_with_status(409, {
                'ok': False, 'error_kind': 'derived_blocked',
                'blocked_by': not_done,
                'message': (
                    f'Block {ticket} deletion: derived ticket {", ".join(not_done)}'
                    'It\'s not done yet. Delete the derived ticket after completing it.'
                ),
                'ticket': ticket,
            })
            return

        flow_kanban = os.path.join(project_root, '.agent-factory', 'bin', 'flow-kanban')
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
            engine_dir = os.path.join(project_root, '.agent-factory', 'engine')
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
        """internal helper — not exposed as endpoint.

        Determine the latest work_dir path using the ticket number.

        1st priority: See <result>/<workdir> field in tickets/<status>/<T-NNN>.xml
        2nd priority: Runs/ directories in reverse mtime order to match status.json ticket_number

        Returns None if not found.
        """
        import xml.etree.ElementTree as ET
        import glob as _glob

        tickets_root = os.path.join(project_root, ".agent-factory", "tickets")
        kanban_dirs = ("todo", "open", "progress", "review", "done")

        # #1: XML <result>/<workdir>
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

        # 2nd priority: runs/ directory traversal (reverse mtime order)
        runs_root = os.path.join(project_root, ".agent-factory", "runs")
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
            # status.json ticket_number field
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
        """internal helper — not exposed as endpoint.

        1st + 2nd worst-of integrated verdict calculation.

        Rules (priority order):
          1. either overall == FAIL  -> FAIL
          2. either overall == WARN  -> WARN
          3. both   overall == PASS  -> PASS
          4. one None + one PASS     -> PASS
          5. one None + non-PASS     -> NONE
          6. both None               -> NONE

        advisory only — No Kanban transitions/blocks.
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

    @api_endpoint("K", "audit_verdict")
    def _handle_kanban_audit_verdict(self) -> None:
        """GET /api/kanban/audit/verdict?ticket=T-NNN — Auditor T3 advisory verdict inquiry.

        W04 runner.py reads audit-verdict.json persistent in the work_dir root.
        Returns {ticket, tier1, tier2, combined}.

        If the file does not exist, {"tier1": null, "tier2": null, "combined": "NONE"} is returned (404
        advisory only — No autoblock/forced transition/kanban regression (feedback_no_speculative_guards canon).

        method: GET
        url: /api/kanban/audit/verdict
        domain: K
        handler: KanbanHandlerMixin._handle_kanban_audit_verdict
        request: query {ticket: T-NNN}
        response_ok: {ticket, tier1: dict|null, tier2: dict|null, combined: PASS|WARN|FAIL|NONE}
        response_error: {ok: false, error: str}
        status_codes: 200, 400
        auth: none (local-only)
        side_effects: read audit-verdict.json from work_dir
        sse_events: none
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

    @api_endpoint("K", "done_verdict")
    def _handle_kanban_done_verdict(self) -> None:
        """GET /api/kanban/done-verdict?ticket=T-NNN — Done card merge consistency advisory verdict.

        T-441: After Review→Done DnD develop HEAD == merge commit consistency check.
        verdict OK: develop HEAD == merge commit && merge commit parents include feature branch tip.
        verdict FAIL: The above conditions are not met (develop HEAD is not a merge commit, etc.).

        advisory only — No autoregression/forced transitions (feedback_no_speculative_guards canon).

        method: GET
        url: /api/kanban/done-verdict
        domain: K
        handler: KanbanHandlerMixin._handle_kanban_done_verdict
        request: query {ticket: T-NNN}
        response_ok: {ticket, verdict: OK|FAIL|NONE, details: dict}
        response_error: {ok: false, error: str}
        status_codes: 200, 400
        auth: none (local-only)
        side_effects: spawn git rev-parse / git log --merges
        sse_events: none
        """
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        ticket = (qs.get('ticket', [None])[0] or '').strip()

        if not ticket or not _TICKET_RE.match(ticket):
            self._send_error(400, 'Missing or invalid "ticket" query param (T-NNN required)')
            return

        project_root = os.getcwd()

        # Check if a ticket exists in the Done directory (meaningless for tickets other than the Done column)
        done_xml = os.path.join(
            project_root, '.agent-factory', 'tickets', 'done', f'{ticket}.xml',
        )
        if not os.path.isfile(done_xml):
            self._send_json({
                'ticket': ticket,
                'verdict': 'SKIP',
                'reason': 'not_done',
                'details': {'message': f'{ticket} is not in the Done column — verdict omitted'},
            })
            return

        # merge_commit Read: tickets/done/<T-NNN>.xml result/merge_commit field
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
            # Missing merge_commit meta — Done ticket before Phase 1 infrastructure introduction
            self._send_json({
                'ticket': ticket,
                'verdict': 'UNKNOWN',
                'reason': 'no_merge_commit_meta',
                'details': {'message': 'merge_commit No information (Done ticket before infrastructure introduction)'},
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

        # check develop HEAD SHA
        head_result = _git('rev-parse', 'develop')
        if head_result.returncode != 0:
            self._send_json({
                'ticket': ticket,
                'verdict': 'UNKNOWN',
                'reason': 'git_error',
                'details': {'message': 'develop HEAD lookup failed:' + (head_result.stderr or '').strip()},
            })
            return
        develop_head = head_result.stdout.strip()

        # merge_commit SHA normalization (full SHA)
        mc_result = _git('rev-parse', merge_commit)
        if mc_result.returncode != 0:
            self._send_json({
                'ticket': ticket,
                'verdict': 'UNKNOWN',
                'reason': 'git_error',
                'details': {'message': f'merge_commit {merge_commit!r} rev-parse failed'},
            })
            return
        merge_commit_sha = mc_result.stdout.strip()

        # Condition 1: develop HEAD == merge commit
        if develop_head != merge_commit_sha:
            self._send_json({
                'ticket': ticket,
                'verdict': 'FAIL',
                'reason': 'develop_head_mismatch',
                'details': {
                    'message': (
                        f'develop HEAD is not a merge commit —'
                        f'HEAD={develop_head[:8]}, merge_commit={merge_commit_sha[:8]}'
                    ),
                    'develop_head': develop_head,
                    'merge_commit': merge_commit_sha,
                },
            })
            return

        # Condition 2: Whether feature branch tip is included in merge commit parents
        parents_result = _git('log', merge_commit_sha, '-1', '--format=%P')
        if parents_result.returncode != 0:
            self._send_json({
                'ticket': ticket,
                'verdict': 'UNKNOWN',
                'reason': 'git_error',
                'details': {'message': 'merge commit parents lookup failed'},
            })
            return
        parent_shas = parents_result.stdout.strip().split()

        # feature branch pattern (feat/T-NNN-*)
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
            # If the branch has already been deleted — If there are more than 2 parents, it is considered a non-ff merge. OK
            feature_tip_in_parents = len(parent_shas) >= 2

        if not feature_tip_in_parents and feature_branch_exists:
            self._send_json({
                'ticket': ticket,
                'verdict': 'FAIL',
                'reason': 'feature_tip_not_in_parents',
                'details': {
                    'message': (
                        f'The feature branch tip is not included in the parent of the merge commit —'
                        f'branch={feature_branch_name}'
                    ),
                    'merge_commit': merge_commit_sha,
                    'parents': parent_shas,
                },
            })
            return

        # All conditions met
        self._send_json({
            'ticket': ticket,
            'verdict': 'OK',
            'reason': 'all_checks_passed',
            'details': {
                'message': 'develop HEAD == merge commit, check feature branch tip inclusion',
                'develop_head': develop_head,
                'merge_commit': merge_commit_sha,
                'parents': parent_shas,
            },
        })

    @api_endpoint("K", "review_verdict")
    def _handle_kanban_review_verdict(self) -> None:
        """GET /api/kanban/review-verdict?ticket=T-NNN -- Review card rule base advisory verdict.

        T-463: finalization.py Read review-verdict.json generated by W04 hook
        Returns verdict (PASS / WARN / FAIL / SKIP / UNKNOWN).

        advisory only -- no kanban move / status transition / auto regression.
        (feedback_no_speculative_guards canon / T-411 commit 0c970fa deprecation case)

        method: GET
        url: /api/kanban/review-verdict
        domain: K
        handler: KanbanHandlerMixin._handle_kanban_review_verdict
        request: query {ticket: T-NNN}
        response_ok: {ticket, verdict: PASS|WARN|FAIL|SKIP|UNKNOWN, violations: list}
        response_error: {ok: false, error: str}
        status_codes: 200, 400
        auth: none (local-only)
        side_effects: read review-verdict.json from work_dir
        sse_events: none
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
        tickets_base = os.path.join(project_root, '.agent-factory', 'tickets')

        # 1. Navigate to review/<ticket>.xml or done/<ticket>.xml
        ticket_xml_path: str | None = None
        review_xml = os.path.join(tickets_base, 'review', f'{ticket}.xml')
        done_xml = os.path.join(tickets_base, 'done', f'{ticket}.xml')

        if os.path.isfile(review_xml):
            ticket_xml_path = review_xml
        elif os.path.isfile(done_xml):
            ticket_xml_path = done_xml
        else:
            # todo / open / progress column -- Other than Review/Done -> SKIP
            self._send_json({
                'ticket': ticket,
                'verdict': 'SKIP',
                'reason': 'not_review',
                'details': {'message': f'{ticket} is not in the Review/Done column'},
                'violations': [],
            })
            return

        # 2. XML parsing -> registrykey extraction
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
                'details': {'message': 'No registrykey information (may be a ticket prior to the introduction of workflow infrastructure)'},
                'violations': [],
            })
            return

        # 3. Read review-verdict.json
        # Navigate to runs/<registry_key> or runs/.history/<registry_key>
        runs_base = os.path.join(project_root, '.agent-factory', 'runs')
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
                    'message': f'No review-verdict.json (registry_key={registry_key})',
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
                    'message': 'review-verdict.json parsing failed',
                    'registry_key': registry_key,
                },
                'violations': [],
            })
            return

        # 4. Return after injection of ticket field
        verdict_dict['ticket'] = ticket
        self._send_json(verdict_dict)

    # ------------------------------------------------------------------
    # T-513 P2 — domain transfer absorption endpoint (undo-done + workflow-entries + workflow-detail)
    # ------------------------------------------------------------------

    @api_endpoint("KANBAN", "undo_done")
    def _handle_kanban_undo_done(self) -> None:
        """POST /api/kanban/undo-done — Rolls back the Done workflow to Review.

        T-513 P2 — Transfer of old V1 undo handler to kanban domain. flow-undo-done
        Invocation + Kanban force transition is essentially a kanban task, so KANBAN domain matching.

        method: POST
        url: /api/kanban/undo-done
        domain: KANBAN
        handler: KanbanHandlerMixin._handle_kanban_undo_done
        request: body {ticket: T-NNN, force?: bool}
        response_ok: {ok: true, kind, ticket, strategy, branch, worktree_path, stdout, message}
        response_error: {ok: false, kind: error, ticket, error, stdout, stderr}
        status_codes: 200, 400, 409, 500, 504
        auth: none (local-only) — user-triggered
        side_effects: develop reset/revert + worktree recreate + kanban force move
        sse_events: kanban_update (via FileWatcher)
        """
        data = self._read_json_body() or {}
        ticket = (data.get('ticket') or '').strip()
        force = bool(data.get('force', False))

        if not ticket or not _TICKET_RE.match(ticket):
            self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
            return

        project_root = os.getcwd()
        done_xml = os.path.join(
            project_root, '.agent-factory', 'tickets', 'done', f'{ticket}.xml',
        )
        if not os.path.isfile(done_xml):
            self._send_error(
                400,
                f'{ticket} is not in Done column (undo-done targets Done tickets only)',
            )
            return

        flow_undo_done = os.path.join(
            project_root, '.agent-factory', 'bin', 'flow-undo-done',
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
            kind = (
                'reset_ok' if strategy == 'reset'
                else 'revert_ok' if strategy == 'revert'
                else 'unknown_ok'
            )
            self._send_json({
                'ok': True,
                'kind': kind,
                'ticket': ticket,
                'strategy': strategy,
                'branch': branch,
                'worktree_path': worktree_path,
                'message': f'{ticket} rollback completed (strategy: {strategy or "?"})',
                'stdout': stdout.strip(),
            })
            return

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

    @api_endpoint("KANBAN", "workflow_entries")
    def _handle_kanban_workflow_entries(self) -> None:
        """GET /api/kanban/workflow-entries — List of workflow entries (runs/<key>/).

        T-513 P2 — old workflow entries inline branch in handlers/generic.py
        Moved to kanban domain. Workflow entries are Kanban card side information.
        Because it is consumed, KANBAN domain matching.

        method: GET
        url: /api/kanban/workflow-entries
        domain: KANBAN
        handler: KanbanHandlerMixin._handle_kanban_workflow_entries
        request: query none
        response_ok: [{registry_key, ticket_id, command, status, ts, ...}]
        response_error: n/a (always 200)
        status_codes: 200
        auth: none (local-only)
        side_effects: read .agent-factory/runs/ filesystem
        sse_events: none
        """
        project_root = os.getcwd()
        self._send_json(_list_workflow_entries(project_root))

    @api_endpoint("KANBAN", "workflow_detail")
    def _handle_kanban_workflow_detail(self) -> None:
        """GET /api/kanban/workflow-detail?entry=<key> — Workflow entry details.

        T-513 P2 — old workflow detail inline branch in handlers/generic.py
        Moved to kanban domain. If the entry query is empty, an empty array is returned.

        method: GET
        url: /api/kanban/workflow-detail
        domain: KANBAN
        handler: KanbanHandlerMixin._handle_kanban_workflow_detail
        request: query {entry: str (registry_key)}
        response_ok: [...]
        response_error: n/a (always 200, empty array for empty entry)
        status_codes: 200
        auth: none (local-only)
        side_effects: read .agent-factory/runs/<entry>/ filesystem
        sse_events: none
        """
        entry = self._parse_query_param('entry')
        if not entry:
            self._send_json([])
            return
        project_root = os.getcwd()
        self._send_json(_workflow_detail(project_root, entry))
    @api_endpoint("K", "workrequest")
    def _handle_kanban_workrequest(self) -> None:
        """POST /api/kanban/workrequest — WorkRequest create/refine/accept facade.

        The storage model still uses ticket XML and ``flow-kanban``. This endpoint
        gives the Board UI an M8 product-language API without changing existing
        workflow contracts.

        method: POST
        url: /api/kanban/workrequest
        domain: KANBAN
        handler: KanbanHandlerMixin._handle_kanban_workrequest
        request: JSON {action, title?, command?, status?, ticket?, fields?}
        response_ok: WorkRequest facade payload or command output
        response_error: JSON error for invalid input, missing command, or timeout
        status_codes: 200, 400, 500, 504
        auth: none (local-only)
        side_effects: may create or update .agent-factory/tickets XML via flow-kanban
        sse_events: none
        """
        data = self._read_json_body() or {}
        action = (data.get('action') or '').strip().lower()
        project_root = os.getcwd()
        flow_kanban = os.path.join(project_root, '.agent-factory', 'bin', 'flow-kanban')

        def _run(args: list[str], timeout: int = 15) -> subprocess.CompletedProcess[str] | None:
            try:
                return subprocess.run(
                    [flow_kanban] + args,
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                self._send_error(504, 'flow-kanban timed out')
                return None
            except FileNotFoundError:
                self._send_error(500, f'flow-kanban not found: {flow_kanban}')
                return None

        def _send_run_error(result: subprocess.CompletedProcess[str]) -> None:
            self._send_error(400, (result.stderr or result.stdout or 'flow-kanban failed').strip())

        if action == 'create':
            title = (data.get('title') or '').strip()
            command = (data.get('command') or 'implement').strip()
            status = (data.get('status') or 'todo').strip().lower()
            if not title:
                self._send_error(400, 'Missing "title"')
                return
            if command not in ('implement', 'research', 'review'):
                self._send_error(400, 'Invalid "command"')
                return
            if status not in ('todo', 'open'):
                self._send_error(400, 'Invalid "status"')
                return

            result = _run(['create', title, '--command', command, '--status', status])
            if result is None:
                return
            if result.returncode != 0:
                _send_run_error(result)
                return
            match = re.search(r'\b(T-\d+)\b', result.stdout or '')
            ticket = match.group(1) if match else ''

            prompt_args = []
            for field in ('goal', 'target', 'constraints', 'criteria', 'context'):
                value = (data.get(field) or '').strip()
                if value:
                    prompt_args.extend([f'--{field}', value])
            if ticket and prompt_args:
                update = _run(['update-prompt', ticket, '--command', command, '--skip-validation'] + prompt_args)
                if update is None:
                    return
                if update.returncode != 0:
                    _send_run_error(update)
                    return

            recorded = False
            if ticket:
                recorded = _record_workrequest_ouroboros(
                    project_root,
                    ticket,
                    action,
                    f"Created WorkRequest draft: {title}",
                )
            self._send_json({
                'ok': True,
                'action': action,
                'ticket': ticket,
                'stdout': result.stdout.strip(),
                'ouroborosRecorded': recorded,
            })
            return

        if action == 'refine':
            ticket = (data.get('ticket') or '').strip()
            command = (data.get('command') or '').strip()
            if not ticket or not _TICKET_RE.match(ticket):
                self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
                return
            args = ['update-prompt', ticket, '--skip-validation']
            if command:
                if command not in ('implement', 'research', 'review'):
                    self._send_error(400, 'Invalid "command"')
                    return
                args.extend(['--command', command])
            for field in ('goal', 'target', 'constraints', 'criteria', 'context'):
                value = (data.get(field) or '').strip()
                if value:
                    args.extend([f'--{field}', value])
            if len(args) == 3:
                self._send_error(400, 'No refinement fields supplied')
                return
            result = _run(args)
            if result is None:
                return
            if result.returncode != 0:
                _send_run_error(result)
                return
            recorded = _record_workrequest_ouroboros(
                project_root,
                ticket,
                action,
                "Rewrote WorkRequest prompt fields through Board refinement.",
            )
            self._send_json({
                'ok': True,
                'action': action,
                'ticket': ticket,
                'stdout': result.stdout.strip(),
                'ouroborosRecorded': recorded,
            })
            return

        if action == 'accept':
            ticket = (data.get('ticket') or '').strip()
            if not ticket or not _TICKET_RE.match(ticket):
                self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
                return
            result = _run(['move', ticket, 'open'])
            if result is None:
                return
            if result.returncode != 0:
                _send_run_error(result)
                return
            recorded = _record_workrequest_ouroboros(
                project_root,
                ticket,
                action,
                "Accepted WorkRequest for workflow execution.",
            )
            self._send_json({
                'ok': True,
                'action': action,
                'ticket': ticket,
                'stdout': result.stdout.strip(),
                'ouroborosRecorded': recorded,
            })
            return

        self._send_error(400, 'Invalid "action" (create/refine/accept)')
