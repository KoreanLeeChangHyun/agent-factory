"""ProductionLineSession + ProductionLineSessionRegistry — production-line subprocess

v1 WorkflowSession and separate separate data models. 0 ClaudeProcess dependence.
SSE fan-out is part of ProductionLineSSEChannel (TerminalSSEChannel and separated).

Registered the board side as session id issued by driver subprocess
(POST /api/v2/sessions). lazy create infrastructure is closed — all entry is express POST.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from board.server.support.common import logger

if TYPE_CHECKING:
    from board.server.channels.production_line_sse_channel import ProductionLineSSEChannel


# fake/test session id pattern — production registry registration + persist blocking.
# T-495 cycle in P2/P3 worker call curl directly to production endpoint
# News added after workflow-sessions-v2/` is contaminated revolving (2026-05-17).
_FAKE_SESSION_PATTERNS: tuple[str, ...] = (
    '-test', '-smoke', '-fake', '-mock',
    'test-', 'smoke-', 'fake-', 'mock-',
)


def is_fake_session_id(session_id: str) -> bool:
    """session id is fake/test pattern if true.

    production driver issuance session id with pattern in the format `wf-T-NNN-<uuid>
    Not a collision. + persist skip.
    """
    lower = session_id.lower()
    return any(pat in lower for pat in _FAKE_SESSION_PATTERNS)


@dataclass
class ProductionLineSession:
    """production-line subprocess is issued workflow session meta.

    V1 WorkflowSession And Other Point:
    - Remove ClaudeProcess field (driver subprocess runs external process)
    - status / current step / current phase / cycle start ts / step ts
      (frontend counter + tab visibility)
    - artifacts dict self-retention (generated output path + size)
    - channel is ProductionLineSSEChannel instance (TerminalSSEChannel and separated)

    Attributes:
        session id: driver issue session ID (wf-T-NNN-<uuid>)
        Ticket ID (T-NNN)
        command: implement / research / review
        work dir: run/<registryKey>/ absolute path
        worktree path: execution-only worktree absolute path (no empty string)
        status: idle | running | completed | failed
        current_step: NONE | INIT | PLAN | WORK | VALIDATE | REPORT | DONE | FAILED
        current phase: WORK internal sub-phase (P1, P2, ... Without empty string)
        cycle start ts: cycle start epoch (frontend cycle accumulator counter)
        step ts: Current step entry epoch (frontend step elapsed)
        artifacts: output path → meta dict (size, mtime)
        channel: ProductionLineSSEChannel instance
        created at: ISO Vision
    """

    session_id: str
    ticket_id: str
    command: str
    work_dir: str
    channel: 'ProductionLineSSEChannel' = field(repr=False)
    worktree_path: str = ''
    status: str = 'idle'
    current_step: str = 'NONE'
    current_phase: str = ''
    cycle_start_ts: float = field(default_factory=time.time)
    step_ts: float = field(default_factory=time.time)
    artifacts: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%S'))


class ProductionLineSessionRegistry:
    """production-line session registry.

    thread-safe to generate session, check/delete.
    v1 WorkflowSessionRegistry with separate (workflow registry / production line registry release).

    The default persist position is `workflow-events.jsonl` of each run.
    `persist dir` is used only for testing and backward restoration routes.
    """

    def __init__(self, persist_dir: str | None = None) -> None:
        """Add to cart

        Args:
            persist dir: directory to save session jsonl. None Integrity persist.
        """
        self._sessions: dict[str, ProductionLineSession] = {}
        self._lock: threading.Lock = threading.Lock()
        self._persist_dir: str | None = persist_dir
        if self._persist_dir is not None:
            try:
                os.makedirs(self._persist_dir, exist_ok=True)
            except OSError:
                self._persist_dir = None

    def _session_file(self, session_id: str, work_dir: str = '') -> str | None:
        """Returns the session NDJSON file path."""
        if self._persist_dir is not None:
            return os.path.join(self._persist_dir, f'{session_id}.jsonl')
        if not work_dir:
            return None
        return os.path.join(work_dir, 'workflow-events.jsonl')

    def create(
        self,
        session_id: str,
        ticket_id: str,
        command: str,
        work_dir: str,
        worktree_path: str = '',
    ) -> ProductionLineSession:
        """Registered the session with session id issued by driver.

        The same session id returns an existing session (idempotent) when reissuing.
        Unlike lazy create v1 create external POST /api/v2/sessions entry point.

        Args:
            session id: driver issue session ID (wf-T-NNN-<uuid>)
            ticket_id: T-NNN
            command: implement / research / review
            work dir: run/<registryKey>/ absolute path
            worktree path: execution-only worktree absolute path (bin strings when research/review)

        Returns:
            Registered ProductionLineSession instance
        """
        if is_fake_session_id(session_id):
            logger.warning(
                "production_line_session: fake/test session_id pattern detected (%s) — "
                "+ persist skip (T-495 production endpoint contamination block)",
                session_id,
            )
            raise ValueError(
                f"Session ID matches fake/test pattern: {session_id}. "
                f"Production endpoint to fake session registration ban — using the unit test (tempfile)."
            )

        with self._lock:
            existing = self._sessions.get(session_id)
            if existing is not None:
                return existing

        persist_path = self._session_file(session_id, work_dir)
        # return import
        from board.server.channels.production_line_sse_channel import ProductionLineSSEChannel
        channel = ProductionLineSSEChannel(session_id=session_id, persist_path=persist_path)

        session = ProductionLineSession(
            session_id=session_id,
            ticket_id=ticket_id,
            command=command,
            work_dir=work_dir,
            worktree_path=worktree_path,
            channel=channel,
        )

        if persist_path is not None:
            try:
                os.makedirs(os.path.dirname(persist_path), exist_ok=True)
                meta = {
                    '_meta': {
                        'session_id': session_id,
                        'ticket_id': ticket_id,
                        'command': command,
                        'work_dir': work_dir,
                        'worktree_path': worktree_path,
                        'created_at': session.created_at,
                        'engine_version': 'production_line',
                    }
                }
                with open(persist_path, 'w', encoding='utf-8') as f:
                    f.write(json.dumps(meta, ensure_ascii=False) + '\n')
            except OSError as exc:
                logger.error(
                    "production line session[%s]: meta persist fail (%s): %s",
                    session_id, persist_path, exc,
                )

        with self._lock:
            self._sessions[session_id] = session

        return session

    def get(self, session_id: str) -> ProductionLineSession | None:
        """session id"""
        with self._lock:
            return self._sessions.get(session_id)

    def get_by_ticket(self, ticket_id: str) -> ProductionLineSession | None:
        """Check the session with the ticket ID (first matching at multiple times)."""
        with self._lock:
            for session in self._sessions.values():
                if session.ticket_id == ticket_id:
                    return session
            return None

    def remove(self, session_id: str) -> bool:
        """Remove session from the registry (disk retention)."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def purge(self, session_id: str) -> bool:
        """Completely remove session from the registry + disk."""
        session = self.get(session_id)
        persist_path = session.channel.persist_path if session is not None else None
        removed = self.remove(session_id)
        if removed:
            if self._persist_dir is not None:
                persist_path = self._session_file(session_id)
            if persist_path and os.path.exists(persist_path):
                try:
                    os.remove(persist_path)
                except OSError as exc:
                    logger.error(
                        "production line session[%s]: Delete file failed (%s): %s",
                        session_id, persist_path, exc,
                    )
        return removed

    def list_all(self) -> list[dict]:
        """Returns the full session list to dict list.

        Returns:
            Session meta dict list. key: session id, ticket id, command, work dir,
            worktree_path, status, current_step, current_phase, cycle_start_ts,
            step_ts, created_at
        """
        with self._lock:
            return [
                {
                    'session_id': s.session_id,
                    'ticket_id': s.ticket_id,
                    'command': s.command,
                    'work_dir': s.work_dir,
                    'worktree_path': s.worktree_path,
                    'status': s.status,
                    'current_step': s.current_step,
                    'current_phase': s.current_phase,
                    'cycle_start_ts': s.cycle_start_ts,
                    'step_ts': s.step_ts,
                    'created_at': s.created_at,
                }
                for s in self._sessions.values()
            ]

    def update_step(
        self,
        session_id: str,
        step: str,
        phase: str = '',
    ) -> ProductionLineSession | None:
        """current step + current phase + step ts thread-safe update.

        status Automatic map:
        - DONE → completed
        - FAILED → failed
        News Other → running (idle entry)
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.current_step = step
            session.current_phase = phase
            session.step_ts = time.time()
            if step == 'DONE':
                session.status = 'completed'
            elif step == 'FAILED':
                session.status = 'failed'
            elif session.status == 'idle':
                session.status = 'running'
            return session

    def set_status(self, session_id: str, status: str) -> ProductionLineSession | None:
        """set status (e.g. external closing signal)."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.status = status
            return session

    def add_artifact(
        self,
        session_id: str,
        path: str,
        size: int = 0,
    ) -> ProductionLineSession | None:
        """Registered output meta (path → {size, mtime})."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.artifacts[path] = {
                'size': size,
                'mtime': time.time(),
            }
            return session

    def load_from_disk(self) -> int:
        """Restores registries by loading session meta in persist directory.

        pattern like v1 load from disk — first line  meta only read session object playback.
        Event data should not be restored to memory (read client directly in NDJSON file when redirected).
        restore status='completed' or 'failed' (the session in progress in the server reboot is not meaningful).

        Returns:
            Load more
        """
        if self._persist_dir is None or not os.path.isdir(self._persist_dir):
            return 0

        from board.server.channels.production_line_sse_channel import ProductionLineSSEChannel
        loaded = 0
        for fname in sorted(os.listdir(self._persist_dir)):
            if not fname.endswith('.jsonl'):
                continue
            fpath = os.path.join(self._persist_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    first_line = f.readline()
            except OSError:
                continue
            if not first_line:
                continue
            try:
                first = json.loads(first_line)
                meta = first.get('_meta')
                if not meta or not meta.get('session_id'):
                    continue
            except (json.JSONDecodeError, ValueError):
                continue

            session_id = meta['session_id']
            channel = ProductionLineSSEChannel(session_id=session_id, persist_path=fpath)
            session = ProductionLineSession(
                session_id=session_id,
                ticket_id=meta.get('ticket_id', ''),
                command=meta.get('command', ''),
                work_dir=meta.get('work_dir', ''),
                worktree_path=meta.get('worktree_path', ''),
                channel=channel,
                status='completed',
                created_at=meta.get('created_at', time.strftime('%Y-%m-%dT%H:%M:%S')),
            )

            with self._lock:
                self._sessions[session_id] = session
            loaded += 1

        return loaded
