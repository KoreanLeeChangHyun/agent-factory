"""Conveyor DnD POST handlers (move/submit/complete/delete) — preserves cb7427f regression fixes.

T-513 P2 — `_handle_conveyor_undo_complete` / `_handle_conveyor_workflow_entries` /
Absorb `_handle_conveyor_workflow_detail` (old V1 undo / generic branch / list+entries+detail
domain transfer). V1 endpoint body + alias routing is collectively discarded in P5 — this mixin
CONVEYOR domain single point of entry.
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

from engine.adapters.conveyor import XmlWorkRequestStore
from engine.apps.board_api.handler_common import _WORK_REQUEST_RE, _CONVEYOR_ALL_DIRS
from engine.apps.board_api.conveyor_complete_helpers import (
    handle_conveyor_complete_force,
    handle_conveyor_complete_review,
    check_derived_blocked,
)
from engine.apps.board_api.conveyor_complete_re import (
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
      - to_do_status: Launcher side pre-verification denied (work_request is in Draft status)
      - http_post_timeout:   H4 urllib timeout=10s
      - http_post_error: H4 urllib general error (URLError, etc.)
      - workflow_start_error: WorkflowHandler spawn failure
      - unknown: Others (including cases where returncode=0 and LAUNCH:/INLINE: are neither)
    """
    if returncode == 0:
        return 'unknown'
    err = stderr or ''
    if 'Draft' in err:
        return 'to_do_status'
    if 'urllib timed out' in err or 'timed out' in err:
        return 'http_post_timeout'
    if 'urllib' in err:
        return 'http_post_error'
    if 'workflow start' in err:
        return 'workflow_start_error'
    return 'unknown'


def _emit_launch_event(event: str, work_request: str, **kwargs: object) -> None:
    """internal helper — not exposed as endpoint.

    LAUNCH_* events are recorded simultaneously in SSE broadcast + workflow.log.

    SSE event_type='launch' Reuse of single channel (Report §5 — Creation of new channel
    Identify PENDING/STARTED/FAILED branches with the 'event' field in payload.

    Args:
        event:  'LAUNCH_PENDING' | 'LAUNCH_STARTED' | 'LAUNCH_FAILED'
        work_request: WR-NNN
        **kwargs: Additional payload fields (command, mode, reason, error_message,
                  latency_ms, submitted_at, session_id, returncode, elapsed_ms, etc.)
    """
    ts = datetime.now(timezone.utc).isoformat()
    payload: dict[str, object] = {'event': event, 'ts': ts, 'work_request': work_request}
    payload.update(kwargs)

    try:
        sse_manager.broadcast('launch', data=payload)
    except Exception as exc:  # Isolate broadcast failures so they don't kill the reader thread itself
        logger.error('launch SSE broadcast failed: event=%s work_request=%s exc=%r',
                     event, work_request, exc)

    # Create a separate file X — logger.info flows to the board server stderr/log.
    try:
        extra_kv = ' '.join(
            f'{k}={v!r}' for k, v in kwargs.items()
            if k not in ('error_message',)  # error_message can be long so it is a separate line
        )
        logger.info('LAUNCH_EVENT %s work_request=%s %s', event, work_request, extra_kv)
        if 'error_message' in kwargs and kwargs['error_message']:
            logger.info('LAUNCH_EVENT %s work_request=%s error_message=%s',
                        event, work_request, str(kwargs['error_message'])[:500])
    except Exception:  # Ignore logging failures
        pass


def _record_workrequest_ouroboros(
    project_root: str,
    work_request: str,
    action: str,
    text: str,
) -> bool:
    """internal helper — persist authoring-loop history after facade success."""

    try:
        store = XmlWorkRequestStore(Path(project_root) / ".agent-factory" / "work-requests")
        request = store.get(WorkRequestRef.parse(work_request))
        entries = _ouroboros_entries_for_action(request.ouroboros_history, action, text)
        if not entries:
            return True
        request.ouroboros_history.extend(entries)
        store.save(request)
        return True
    except (FileNotFoundError, TypeError, ValueError) as exc:
        logger.debug("Could not record WorkRequest Ouroboros history for %s: %s", work_request, exc)
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
    work_request: str,
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
                'LAUNCH_FAILED', work_request,
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
                'LAUNCH_STARTED', work_request,
                session_id=session_id,
                mode='launched',
                spawn_duration_ms=elapsed_ms,
                command=command,
            )
        elif rc == 0 and first_line.startswith('INLINE:'):
            tail = first_line[len('INLINE:'):].strip()
            _emit_launch_event(
                'LAUNCH_STARTED', work_request,
                session_id='',
                mode='inline',
                spawn_duration_ms=elapsed_ms,
                command=command,
                message=tail,
            )
        elif rc == 0:
            # returncode=0 but stdout pattern is LAUNCH:/INLINE: neither — unknown classification
            _emit_launch_event(
                'LAUNCH_FAILED', work_request,
                reason='unknown',
                returncode=0,
                error_message=(first_line or 'no stdout')[:500],
                elapsed_ms=elapsed_ms,
                command=command,
            )
        else:
            reason = _classify_failure_reason(rc, stderr or '')
            _emit_launch_event(
                'LAUNCH_FAILED', work_request,
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
                'LAUNCH_FAILED', work_request,
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

_FEAT_BRANCH_RE = re.compile(r'^feat/(WR-\d+)-')


class ConveyorHandlerMixin:
    """Conveyor DnD POST handlers (move/submit/complete/delete) — preserves cb7427f regression fixes."""

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

    def _resolve_feat_branch(self, work_request: str, project_root: str) -> str | None:
        """internal helper — not exposed as endpoint.

        Search for the exact feat/WR-NNN-* branch name using the work_request number.

        Parse the output of ``git worktree list --porcelain`` into ``refs/heads/feat/WR-NNN-*``
        Extract only the ``feat/WR-NNN-*`` part from the form. None if the work tree is not registered.
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
            if m and m.group(1) == work_request:
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
    def _handle_conveyor_branch_toggle(self) -> None:
        """POST /api/conveyor/branch/toggle — Enable/disable Verifying card feature branch.

        Request: ``{"work_request_number": "WR-NNN", "action": "on"|"off"}``

        on:
          - Verify main working tree dirty (git status --porcelain) → Reject if dirty
          - feat/WR-NNN-* branch matching (git worktree list --porcelain)
          - ``git switch <feat branch>`` in the main working tree
          - Automatic detection of backend changes (git diff develop..feat/WR-NNN-* result glob matching)

        off:
          - Same as main working tree dirty verification
          - ``git switch develop``

        Constraints:
          - Automatic stash / automatic commit / automatic reset is absolutely prohibited (user manual correction guidance only)
          - feedback_no_speculative_guards Canon compliance

        method: POST
        url: /api/conveyor/branch/toggle
        domain: K
        handler: ConveyorHandlerMixin._handle_conveyor_branch_toggle
        request: body {work_request_number: str, action: on|off}
        response_ok: {ok: true, branch: str, needs_restart: bool}
        response_error: {ok: false, error: str, dirty_files?: list}
        status_codes: 200, 400, 409
        auth: none (local-only) — user-triggered
        side_effects: `git switch` in main working tree
        sse_events: git_branch (via GitBranchWatcher)
        """
        data = self._read_json_body() or {}
        work_request = (data.get('work_request_number') or '').strip()
        action = (data.get('action') or '').strip().lower()

        if not work_request or not _WORK_REQUEST_RE.match(work_request):
            self._send_error(400, 'Missing or invalid "work_request_number" (WR-NNN required)')
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
                'work_request': work_request,
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
                    'work_request': work_request,
                    'action': action,
                })
                return
            self._send_json({
                'ok': True,
                'branch': 'develop',
                'needs_restart': False,
                'active_work_request': None,
            })
            return

        # action == 'on'
        feat_branch = self._resolve_feat_branch(work_request, project_root)
        if not feat_branch:
            self._send_json({
                'ok': False,
                'reason': 'feature_branch_not_found',
                'message': (
                    f'The feature branch (feat/{work_request}-*) of {work_request} could not be found.'
                    f'Check if the worktree is registered (git worktree list).'
                ),
                'work_request': work_request,
                'action': action,
            })
            return

        ok, msg = self._git_switch(feat_branch, project_root, ignore_other_worktrees=True)
        if not ok:
            self._send_json({
                'ok': False,
                'reason': 'git_switch_failed',
                'message': msg,
                'work_request': work_request,
                'action': action,
                'branch': feat_branch,
            })
            return

        needs_restart = self._detect_backend_changes(feat_branch, project_root)
        self._send_json({
            'ok': True,
            'branch': feat_branch,
            'needs_restart': needs_restart,
            'active_work_request': work_request,
        })

    @api_endpoint("K", "branch_active")
    def _handle_conveyor_branch_active(self) -> None:
        """GET /api/conveyor/branch/active — Returns the current main working tree HEAD branch + active_work_request.

        Response: ``{"branch": "feat/WR-NNN-...", "active_work_request": "WR-NNN"}`` or
              ``{"branch": "develop", "active_work_request": null}``

        Used by the frontend to restore the active card visual when the page is loaded.

        method: GET
        url: /api/conveyor/branch/active
        domain: K
        handler: ConveyorHandlerMixin._handle_conveyor_branch_active
        request: query none
        response_ok: {branch: str|null, active_work_request: WR-NNN|null}
        response_error: n/a (always 200)
        status_codes: 200
        auth: none (local-only)
        side_effects: spawn `git branch --show-current`
        sse_events: none
        """
        project_root = os.getcwd()
        branch = self._get_current_branch(project_root)
        if not branch:
            self._send_json({'branch': None, 'active_work_request': None})
            return

        m = _FEAT_BRANCH_RE.match(branch)
        active_work_request = m.group(1) if m else None
        self._send_json({
            'branch': branch,
            'active_work_request': active_work_request,
        })

    def _check_derived_blocked(self, work_request: str, conveyor_base: str) -> list[str]:
        """internal helper — not exposed as endpoint.

        derived-from Returns derived work_requests with a status other than Complete (delegation).
        """
        return check_derived_blocked(work_request, conveyor_base, _CONVEYOR_ALL_DIRS)

    @api_endpoint("K", "move")
    def _handle_conveyor_move(self) -> None:
        """POST /api/conveyor/move — {"work_request","to"}: Allow transition Draft ↔ Accepted + Accepted → Verifying + Verifying → Accepted.

        method: POST
        url: /api/conveyor/move
        domain: K
        handler: ConveyorHandlerMixin._handle_conveyor_move
        request: body {work_request: WR-NNN, to: draft|accepted|verifying}
        response_ok: {ok: true, work_request, to, stdout: str}
        response_error: {ok: false, error: str}
        status_codes: 200, 400, 500, 504
        auth: none (local-only)
        side_effects: flow-conveyor move subprocess
        sse_events: conveyor_update (via FileWatcher)
        """
        data = self._read_json_body() or {}
        work_request = (data.get('work_request') or '').strip()
        to = (data.get('to') or '').strip().lower()

        if not work_request or not _WORK_REQUEST_RE.match(work_request):
            self._send_error(400, 'Missing or invalid "work_request" (WR-NNN required)')
            return
        if to not in ('draft', 'accepted', 'verifying'):
            self._send_error(400, 'DnD allows only "draft" / "accepted" / "verifying" transitions')
            return

        project_root = os.getcwd()
        flow_conveyor = os.path.join(project_root, '.agent-factory', 'bin', 'flow-conveyor')
        try:
            result = subprocess.run(
                [flow_conveyor, 'move', work_request, to],
                cwd=project_root, capture_output=True, text=True, timeout=10,
            )
        except subprocess.TimeoutExpired:
            self._send_error(504, 'flow-conveyor move timed out')
            return
        except FileNotFoundError:
            self._send_error(500, f'flow-conveyor not found: {flow_conveyor}')
            return

        if result.returncode != 0:
            self._send_error(400, f'flow-conveyor move failed: {(result.stderr or result.stdout or "").strip()}')
            return
        self._send_json({'ok': True, 'work_request': work_request, 'to': to, 'stdout': result.stdout.strip()})

    @api_endpoint("K", "submit")
    def _handle_conveyor_submit(self) -> None:
        """POST /api/conveyor/submit — {"work_request","command"}: production-line asynchronous spawn.

        T-500: Spawn responsibility is separated into ``server.production_line_launcher.spawn_production_line()``.
        This handler is only responsible for input validation → delegation → JSON response.

        Stage 3-B (T-489) + T-495 P2 semantics are preserved in production_line_launcher:
          - flow-wf submit (production-line) Popen.
          - V2_BOARD_POST=true + V2_REGISTRY_KEY env auto-injection.
          - LAUNCH_PENDING + LAUNCH_STARTED Both fire immediately after Popen.
          - LAUNCH_FAILED fires only when reader thread = driver rc != 0.
          - Response key ``{ok, status:'starting', work_request, command, submitted_at, session_id}``
            Full retention (0 regressions).

        method: POST
        url: /api/conveyor/submit
        domain: K
        handler: ConveyorHandlerMixin._handle_conveyor_submit
        request: body {work_request: WR-NNN, command: implement|research|review}
        response_ok: {ok: true, status: starting, work_request, command, submitted_at, session_id}
        response_error: {ok: false, error: str, error_kind?: str}
        status_codes: 200, 400, 500
        auth: none (local-only)
        side_effects: spawn production-line subprocess, conveyor Accepted → Executing
        sse_events: launch (LAUNCH_PENDING, LAUNCH_STARTED), conveyor_update
        """
        data = self._read_json_body() or {}
        work_request = (data.get('work_request') or '').strip()
        command = (data.get('command') or '').strip()

        if not work_request or not re.match(r'^WR-\d+$', work_request):
            self._send_error(400, 'Missing or invalid "work_request" (WR-NNN required)')
            return
        if command not in ('implement', 'research', 'review'):
            self._send_error(400, 'Invalid "command" (must be implement/research/verifying)')
            return

        result = spawn_production_line(work_request, command)
        if not result.get('ok'):
            kind = result.get('error_kind') or 'spawn_failed'
            msg = result.get('message') or 'production-line spawn failed'
            self._send_error(500, f'{kind}: {msg}')
            return
        self._send_json(result)

    @api_endpoint("K", "complete")
    def _handle_conveyor_complete(self) -> None:
        """POST /api/conveyor/complete — {"work_request","force","force_dirty"}.

        force=false: Verifying → Complete.
        force=true:  Accepted → Complete.
        Detailed logic is delegated to _conveyor_complete_helpers.py.

        method: POST
        url: /api/conveyor/complete
        domain: K
        handler: ConveyorHandlerMixin._handle_conveyor_complete
        request: body {work_request: WR-NNN, force?: bool, force_dirty?: bool}
        response_ok: {ok: true, work_request, merge_commit?, message}
        response_error: {ok: false, error: str, blocked_derived?: list}
        status_codes: 200, 400, 409, 500, 504
        auth: none (local-only) — user-triggered
        side_effects: flow-merge subprocess (commit + worktree cleanup + conveyor move)
        sse_events: conveyor_update (via FileWatcher)
        """
        data = self._read_json_body() or {}
        work_request = (data.get('work_request') or '').strip()
        force = bool(data.get('force', False))
        force_dirty = bool(data.get('force_dirty', False))

        if not work_request or not _WORK_REQUEST_RE.match(work_request):
            self._send_error(400, 'Missing or invalid "work_request" (WR-NNN required)')
            return

        project_root = os.getcwd()
        flow_conveyor = os.path.join(project_root, '.agent-factory', 'bin', 'flow-conveyor')

        if force:
            handle_conveyor_complete_force(self, work_request, force_dirty, project_root, flow_conveyor)
        else:
            handle_conveyor_complete_review(self, work_request, project_root, flow_conveyor)

    @api_endpoint("K", "delete")
    def _handle_conveyor_delete(self) -> None:
        """POST /api/conveyor/delete — {"work_request"}: derived-from guard + delete + worktree cleanup.

        method: POST
        url: /api/conveyor/delete
        domain: K
        handler: ConveyorHandlerMixin._handle_conveyor_delete
        request: body {work_request: WR-NNN}
        response_ok: {ok: true, work_request, stdout, worktree_removed: bool}
        response_error: {ok: false, error_kind: derived_blocked|other, blocked_by, message}
        status_codes: 200, 400, 409, 500, 504
        auth: none (local-only) — user-triggered
        side_effects: flow-conveyor delete + worktree_manager.remove_worktree
        sse_events: conveyor_update (via FileWatcher)
        """
        data = self._read_json_body() or {}
        work_request = (data.get('work_request') or '').strip()

        if not work_request or not _WORK_REQUEST_RE.match(work_request):
            self._send_error(400, 'Missing or invalid "work_request" (WR-NNN required)')
            return

        project_root = os.getcwd()
        conveyor_base = os.path.join(project_root, '.agent-factory', 'work-requests')

        not_complete = self._check_derived_blocked(work_request, conveyor_base)
        if not_complete:
            self._send_json_with_status(409, {
                'ok': False, 'error_kind': 'derived_blocked',
                'blocked_by': not_complete,
                'message': (
                    f'Block {work_request} deletion: derived work_request {", ".join(not_complete)}'
                    'It\'s not complete yet. Delete the derived work_request after completing it.'
                ),
                'work_request': work_request,
            })
            return

        flow_conveyor = os.path.join(project_root, '.agent-factory', 'bin', 'flow-conveyor')
        try:
            result = subprocess.run(
                [flow_conveyor, 'delete', work_request],
                cwd=project_root, capture_output=True, text=True, timeout=30,
            )
        except subprocess.TimeoutExpired:
            self._send_error(504, 'flow-conveyor delete timed out (30s)')
            return
        except FileNotFoundError:
            self._send_error(500, f'flow-conveyor not found: {flow_conveyor}')
            return

        if result.returncode != 0:
            self._send_json_with_status(409, {
                'ok': False, 'error_kind': 'other', 'blocked_by': [],
                'message': (result.stderr or result.stdout or '').strip() or 'flow-conveyor delete failed',
                'work_request': work_request,
            })
            return

        worktree_removed = False
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

        self._send_json({
            'ok': True, 'work_request': work_request,
            'stdout': (result.stdout or '').strip(),
            'worktree_removed': worktree_removed,
        })

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------

    def _resolve_audit_workdir(self, work_request: str, project_root: str) -> 'str | None':
        """internal helper — not exposed as endpoint.

        Determine the latest work_dir path using the work_request number.

        1st priority: See <result>/<workdir> field in work_requests/<status>/<WR-NNN>.xml
        2nd priority: Runs/ directories in reverse mtime order to match status.json work_request_number

        Returns None if not found.
        """
        import xml.etree.ElementTree as ET
        import glob as _glob

        work_requests_root = os.path.join(project_root, ".agent-factory", "work-requests")
        conveyor_dirs = ("draft", "accepted", "executing", "verifying", "complete")

        # #1: XML <result>/<workdir>
        for kdir in conveyor_dirs:
            xml_path = os.path.join(work_requests_root, kdir, f"{work_request}.xml")
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
            # status.json work_request_number field
            status_path = os.path.join(rdir, "status.json")
            if os.path.isfile(status_path):
                try:
                    with open(status_path, encoding="utf-8") as f:
                        sdata = _json.load(f)
                    if sdata.get("work_request_number") == work_request:
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

        advisory only — No Conveyor transitions/blocks.
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
    def _handle_conveyor_audit_verdict(self) -> None:
        """GET /api/conveyor/audit/verdict?work_request=WR-NNN — Auditor T3 advisory verdict inquiry.

        W04 runner.py reads audit-verdict.json persistent in the work_dir root.
        Returns {work_request, tier1, tier2, combined}.

        If the file does not exist, {"tier1": null, "tier2": null, "combined": "NONE"} is returned (404
        advisory only — No autoblock/forced transition/conveyor regression (feedback_no_speculative_guards canon).

        method: GET
        url: /api/conveyor/audit/verdict
        domain: K
        handler: ConveyorHandlerMixin._handle_conveyor_audit_verdict
        request: query {work_request: WR-NNN}
        response_ok: {work_request, tier1: dict|null, tier2: dict|null, combined: PASS|WARN|FAIL|NONE}
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
        work_request = (qs.get("work_request", [None])[0] or "").strip()

        if not work_request or not _WORK_REQUEST_RE.match(work_request):
            self._send_error(400, 'Missing or invalid "work_request" query param (WR-NNN required)')
            return

        _NONE_RESPONSE = {"tier1": None, "tier2": None, "combined": "NONE"}

        project_root = os.getcwd()
        work_dir = self._resolve_audit_workdir(work_request, project_root)
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
            "work_request": work_request,
            "tier1": tier1,
            "tier2": tier2,
            "combined": combined,
        })

    @api_endpoint("K", "complete_verdict")
    def _handle_conveyor_complete_verdict(self) -> None:
        """GET /api/conveyor/complete-verdict?work_request=WR-NNN — Complete card merge consistency advisory verdict.

        T-441: After Verifying→Complete DnD develop HEAD == merge commit consistency check.
        verdict OK: develop HEAD == merge commit && merge commit parents include feature branch tip.
        verdict FAIL: The above conditions are not met (develop HEAD is not a merge commit, etc.).

        advisory only — No autoregression/forced transitions (feedback_no_speculative_guards canon).

        method: GET
        url: /api/conveyor/complete-verdict
        domain: K
        handler: ConveyorHandlerMixin._handle_conveyor_complete_verdict
        request: query {work_request: WR-NNN}
        response_ok: {work_request, verdict: OK|FAIL|NONE, details: dict}
        response_error: {ok: false, error: str}
        status_codes: 200, 400
        auth: none (local-only)
        side_effects: spawn git rev-parse / git log --merges
        sse_events: none
        """
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        work_request = (qs.get('work_request', [None])[0] or '').strip()

        if not work_request or not _WORK_REQUEST_RE.match(work_request):
            self._send_error(400, 'Missing or invalid "work_request" query param (WR-NNN required)')
            return

        project_root = os.getcwd()

        # Check if a work_request exists in the Complete directory (meaningless for work_requests other than the Complete column)
        complete_xml = os.path.join(
            project_root, '.agent-factory', 'work-requests', 'complete', f'{work_request}.xml',
        )
        if not os.path.isfile(complete_xml):
            self._send_json({
                'work_request': work_request,
                'verdict': 'SKIP',
                'reason': 'not_complete',
                'details': {'message': f'{work_request} is not in the Complete column — verdict omitted'},
            })
            return

        # merge_commit Read: work_requests/complete/<WR-NNN>.xml result/merge_commit field
        merge_commit: str | None = None
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(complete_xml)
            root = tree.getroot()
            result_el = root.find('.//result/merge_commit')
            if result_el is not None and result_el.text:
                merge_commit = result_el.text.strip() or None
        except Exception:
            merge_commit = None

        if not merge_commit:
            # Missing merge_commit meta — Complete work_request before Phase 1 infrastructure introduction
            self._send_json({
                'work_request': work_request,
                'verdict': 'UNKNOWN',
                'reason': 'no_merge_commit_meta',
                'details': {'message': 'merge_commit No information (Complete work_request before infrastructure introduction)'},
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
                'work_request': work_request,
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
                'work_request': work_request,
                'verdict': 'UNKNOWN',
                'reason': 'git_error',
                'details': {'message': f'merge_commit {merge_commit!r} rev-parse failed'},
            })
            return
        merge_commit_sha = mc_result.stdout.strip()

        # Condition 1: develop HEAD == merge commit
        if develop_head != merge_commit_sha:
            self._send_json({
                'work_request': work_request,
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
                'work_request': work_request,
                'verdict': 'UNKNOWN',
                'reason': 'git_error',
                'details': {'message': 'merge commit parents lookup failed'},
            })
            return
        parent_shas = parents_result.stdout.strip().split()

        # feature branch pattern (feat/WR-NNN-*)
        feat_branch_result = _git('branch', '--list', f'feat/{work_request}-*')
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
                'work_request': work_request,
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
            'work_request': work_request,
            'verdict': 'OK',
            'reason': 'all_checks_passed',
            'details': {
                'message': 'develop HEAD == merge commit, check feature branch tip inclusion',
                'develop_head': develop_head,
                'merge_commit': merge_commit_sha,
                'parents': parent_shas,
            },
        })

    @api_endpoint("K", "verifying_verdict")
    def _handle_conveyor_verifying_verdict(self) -> None:
        """GET /api/conveyor/verifying-verdict?work_request=WR-NNN -- Verifying card rule base advisory verdict.

        T-463: finalization.py Read verifying-verdict.json generated by W04 hook
        Returns verdict (PASS / WARN / FAIL / SKIP / UNKNOWN).

        advisory only -- no conveyor move / status transition / auto regression.
        (feedback_no_speculative_guards canon / T-411 commit 0c970fa deprecation case)

        method: GET
        url: /api/conveyor/verifying-verdict
        domain: K
        handler: ConveyorHandlerMixin._handle_conveyor_verifying_verdict
        request: query {work_request: WR-NNN}
        response_ok: {work_request, verdict: PASS|WARN|FAIL|SKIP|UNKNOWN, violations: list}
        response_error: {ok: false, error: str}
        status_codes: 200, 400
        auth: none (local-only)
        side_effects: read verifying-verdict.json from work_dir
        sse_events: none
        """
        import json as _json
        import xml.etree.ElementTree as ET
        from urllib.parse import urlparse, parse_qs
        from pathlib import Path

        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        work_request = (qs.get('work_request', [None])[0] or '').strip()

        if not work_request:
            self._send_error(400, 'work_request parameter required')
            return
        if not _WORK_REQUEST_RE.match(work_request):
            self._send_error(400, 'invalid work_request format')
            return

        project_root = os.getcwd()
        work_requests_base = os.path.join(project_root, '.agent-factory', 'work-requests')

        # 1. Navigate to verifying/<work_request>.xml or complete/<work_request>.xml
        work_request_xml_path: str | None = None
        verifying_xml = os.path.join(work_requests_base, 'verifying', f'{work_request}.xml')
        complete_xml = os.path.join(work_requests_base, 'complete', f'{work_request}.xml')

        if os.path.isfile(verifying_xml):
            work_request_xml_path = verifying_xml
        elif os.path.isfile(complete_xml):
            work_request_xml_path = complete_xml
        else:
            # draft / accepted / executing column -- Other than Verifying/Complete -> SKIP
            self._send_json({
                'work_request': work_request,
                'verdict': 'SKIP',
                'reason': 'not_review',
                'details': {'message': f'{work_request} is not in the Verifying/Complete column'},
                'violations': [],
            })
            return

        # 2. XML parsing -> registrykey extraction
        registry_key: str | None = None
        try:
            tree = ET.parse(work_request_xml_path)
            root = tree.getroot()
            rk_el = root.find('.//result/registrykey')
            if rk_el is not None and rk_el.text:
                registry_key = rk_el.text.strip() or None
        except Exception:
            registry_key = None

        if not registry_key:
            self._send_json({
                'work_request': work_request,
                'verdict': 'UNKNOWN',
                'reason': 'no_registry_key',
                'details': {'message': 'No registrykey information (may be a work_request prior to the introduction of workflow infrastructure)'},
                'violations': [],
            })
            return

        # 3. Read verifying-verdict.json
        # Navigate to runs/<registry_key> or runs/.history/<registry_key>
        runs_base = os.path.join(project_root, '.agent-factory', 'runs')
        verdict_path: Path | None = None
        for candidate in (
            Path(runs_base) / registry_key / 'verifying-verdict.json',
            Path(runs_base) / '.history' / registry_key / 'verifying-verdict.json',
        ):
            if candidate.is_file():
                verdict_path = candidate
                break

        if verdict_path is None:
            self._send_json({
                'work_request': work_request,
                'verdict': 'UNKNOWN',
                'reason': 'no_verdict_meta',
                'details': {
                    'message': f'No verifying-verdict.json (registry_key={registry_key})',
                    'registry_key': registry_key,
                },
                'violations': [],
            })
            return

        try:
            verdict_dict = _json.loads(verdict_path.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            self._send_json({
                'work_request': work_request,
                'verdict': 'UNKNOWN',
                'reason': 'invalid_verdict_json',
                'details': {
                    'message': 'verifying-verdict.json parsing failed',
                    'registry_key': registry_key,
                },
                'violations': [],
            })
            return

        # 4. Return after injection of work_request field
        verdict_dict['work_request'] = work_request
        self._send_json(verdict_dict)

    # ------------------------------------------------------------------
    # T-513 P2 — domain transfer absorption endpoint (undo-complete + workflow-entries + workflow-detail)
    # ------------------------------------------------------------------

    @api_endpoint("CONVEYOR", "undo_complete")
    def _handle_conveyor_undo_complete(self) -> None:
        """POST /api/conveyor/undo-complete — Rolls back the Complete workflow to Verifying.

        T-513 P2 — Transfer of old V1 undo handler to conveyor domain. flow-undo-complete
        Invocation + Conveyor force transition is essentially a conveyor task, so CONVEYOR domain matching.

        method: POST
        url: /api/conveyor/undo-complete
        domain: CONVEYOR
        handler: ConveyorHandlerMixin._handle_conveyor_undo_complete
        request: body {work_request: WR-NNN, force?: bool}
        response_ok: {ok: true, kind, work_request, strategy, branch, worktree_path, stdout, message}
        response_error: {ok: false, kind: error, work_request, error, stdout, stderr}
        status_codes: 200, 400, 409, 500, 504
        auth: none (local-only) — user-triggered
        side_effects: develop reset/revert + worktree recreate + conveyor force move
        sse_events: conveyor_update (via FileWatcher)
        """
        data = self._read_json_body() or {}
        work_request = (data.get('work_request') or '').strip()
        force = bool(data.get('force', False))

        if not work_request or not _WORK_REQUEST_RE.match(work_request):
            self._send_error(400, 'Missing or invalid "work_request" (WR-NNN required)')
            return

        project_root = os.getcwd()
        complete_xml = os.path.join(
            project_root, '.agent-factory', 'work-requests', 'complete', f'{work_request}.xml',
        )
        if not os.path.isfile(complete_xml):
            self._send_error(
                400,
                f'{work_request} is not in Complete column (undo-complete targets Complete work_requests only)',
            )
            return

        flow_undo_complete = os.path.join(
            project_root, '.agent-factory', 'bin', 'flow-undo-complete',
        )
        cmd_args = [flow_undo_complete, work_request]
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
            self._send_error(504, 'flow-undo-complete timed out (180s)')
            return
        except FileNotFoundError:
            self._send_error(500, f'flow-undo-complete not found: {flow_undo_complete}')
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
                'work_request': work_request,
                'strategy': strategy,
                'branch': branch,
                'worktree_path': worktree_path,
                'message': f'{work_request} rollback completed (strategy: {strategy or "?"})',
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
            error_message = f'flow-undo-complete exited with code {result.returncode}'

        self._send_json_with_status(409, {
            'ok': False,
            'kind': 'error',
            'work_request': work_request,
            'error': error_message,
            'message': error_message,
            'stdout': stdout.strip(),
            'stderr': stderr.strip(),
        })

    @api_endpoint("CONVEYOR", "workflow_entries")
    def _handle_conveyor_workflow_entries(self) -> None:
        """GET /api/conveyor/workflow-entries — List of workflow entries (runs/<key>/).

        T-513 P2 — old workflow entries inline branch in handlers/generic.py
        Moved to conveyor domain. Workflow entries are Conveyor card side information.
        Because it is consumed, CONVEYOR domain matching.

        method: GET
        url: /api/conveyor/workflow-entries
        domain: CONVEYOR
        handler: ConveyorHandlerMixin._handle_conveyor_workflow_entries
        request: query none
        response_ok: [{registry_key, work_request, command, status, ts, ...}]
        response_error: n/a (always 200)
        status_codes: 200
        auth: none (local-only)
        side_effects: read .agent-factory/runs/ filesystem
        sse_events: none
        """
        project_root = os.getcwd()
        self._send_json(_list_workflow_entries(project_root))

    @api_endpoint("CONVEYOR", "workflow_detail")
    def _handle_conveyor_workflow_detail(self) -> None:
        """GET /api/conveyor/workflow-detail?entry=<key> — Workflow entry details.

        T-513 P2 — old workflow detail inline branch in handlers/generic.py
        Moved to conveyor domain. If the entry query is empty, an empty array is returned.

        method: GET
        url: /api/conveyor/workflow-detail
        domain: CONVEYOR
        handler: ConveyorHandlerMixin._handle_conveyor_workflow_detail
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
    def _handle_conveyor_workrequest(self) -> None:
        """POST /api/conveyor/workrequest — WorkRequest create/refine/accept facade.

        The storage model still uses work_request XML and ``flow-conveyor``. This endpoint
        gives the Board UI an M8 product-language API without changing existing
        workflow contracts.

        method: POST
        url: /api/conveyor/workrequest
        domain: CONVEYOR
        handler: ConveyorHandlerMixin._handle_conveyor_workrequest
        request: JSON {action, title?, command?, status?, work_request?, fields?}
        response_ok: WorkRequest facade payload or command output
        response_error: JSON error for invalid input, missing command, or timeout
        status_codes: 200, 400, 500, 504
        auth: none (local-only)
        side_effects: may create or update .agent-factory/work-requests XML via flow-conveyor
        sse_events: none
        """
        data = self._read_json_body() or {}
        action = (data.get('action') or '').strip().lower()
        project_root = os.getcwd()
        flow_conveyor = os.path.join(project_root, '.agent-factory', 'bin', 'flow-conveyor')

        def _run(args: list[str], timeout: int = 15) -> subprocess.CompletedProcess[str] | None:
            try:
                return subprocess.run(
                    [flow_conveyor] + args,
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                self._send_error(504, 'flow-conveyor timed out')
                return None
            except FileNotFoundError:
                self._send_error(500, f'flow-conveyor not found: {flow_conveyor}')
                return None

        def _send_run_error(result: subprocess.CompletedProcess[str]) -> None:
            self._send_error(400, (result.stderr or result.stdout or 'flow-conveyor failed').strip())

        if action == 'create':
            title = (data.get('title') or '').strip()
            command = (data.get('command') or 'implement').strip()
            status = (data.get('status') or 'draft').strip().lower()
            if not title:
                self._send_error(400, 'Missing "title"')
                return
            if command not in ('implement', 'research', 'review'):
                self._send_error(400, 'Invalid "command"')
                return
            if status not in ('draft', 'accepted'):
                self._send_error(400, 'Invalid "status"')
                return

            result = _run(['create', title, '--command', command, '--status', status])
            if result is None:
                return
            if result.returncode != 0:
                _send_run_error(result)
                return
            match = re.search(r'\b(WR-\d+)\b', result.stdout or '')
            work_request = match.group(1) if match else ''

            prompt_args = []
            for field in ('goal', 'target', 'constraints', 'criteria', 'context'):
                value = (data.get(field) or '').strip()
                if value:
                    prompt_args.extend([f'--{field}', value])
            if work_request and prompt_args:
                update = _run(['update-prompt', work_request, '--command', command, '--skip-validation'] + prompt_args)
                if update is None:
                    return
                if update.returncode != 0:
                    _send_run_error(update)
                    return

            recorded = False
            if work_request:
                recorded = _record_workrequest_ouroboros(
                    project_root,
                    work_request,
                    action,
                    f"Created WorkRequest draft: {title}",
                )
            self._send_json({
                'ok': True,
                'action': action,
                'work_request': work_request,
                'stdout': result.stdout.strip(),
                'ouroborosRecorded': recorded,
            })
            return

        if action == 'refine':
            work_request = (data.get('work_request') or '').strip()
            command = (data.get('command') or '').strip()
            if not work_request or not re.match(r'^WR-\d+$', work_request):
                self._send_error(400, 'Missing or invalid "work_request" (WR-NNN required)')
                return
            args = ['update-prompt', work_request, '--skip-validation']
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
                work_request,
                action,
                "Rewrote WorkRequest prompt fields through Board refinement.",
            )
            self._send_json({
                'ok': True,
                'action': action,
                'work_request': work_request,
                'stdout': result.stdout.strip(),
                'ouroborosRecorded': recorded,
            })
            return

        if action == 'accept':
            work_request = (data.get('work_request') or '').strip()
            if not work_request or not re.match(r'^WR-\d+$', work_request):
                self._send_error(400, 'Missing or invalid "work_request" (WR-NNN required)')
                return
            result = _run(['move', work_request, 'accepted'])
            if result is None:
                return
            if result.returncode != 0:
                _send_run_error(result)
                return
            recorded = _record_workrequest_ouroboros(
                project_root,
                work_request,
                action,
                "Accepted WorkRequest for workflow execution.",
            )
            self._send_json({
                'ok': True,
                'action': action,
                'work_request': work_request,
                'stdout': result.stdout.strip(),
                'ouroborosRecorded': recorded,
            })
            return

        self._send_error(400, 'Invalid "action" (create/refine/accept)')
