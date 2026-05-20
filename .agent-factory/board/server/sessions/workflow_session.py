"""WorkflowSession + WorkflowSessionRegistry — workflow session lifecycle."""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field

from board.server._common import logger
from board.server.processes.claude_process import ClaudeProcess
from board.server.channels.terminal_channel import TerminalSSEChannel


@dataclass
class WorkflowSession:
    """Data class indicating one of the workflow sessions.

    Each workflow ticket runs an independent ClaudeProcess and TerminalSSEChannel
    is identified as session id.

    Attributes:
        session id: Session Original ID (Type: wf-T-NNN-timestamp)
        ticket id: Kanban ticket ID (e.g. T-238)
        command: execution command (implement, review, research, etc.)
        work dir: task directory absolute path
        process: Claude CLI process manager instance
        channel: terminal SSE broadcast channel instance
        created at: Session creation time (ISO format)
        current step: current workflow stage (e.g. PLAN, WORK, REPORT)
        last artifact: Recently generated output path (e.g. work/W01-design.md)
    """

    session_id: str
    ticket_id: str
    command: str
    work_dir: str
    process: ClaudeProcess = field(repr=False)
    channel: TerminalSSEChannel = field(repr=False)
    created_at: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%S'))
    current_step: str = ''
    last_artifact: str = ''


class WorkflowSessionRegistry:
    """Multi-Workflow Session Registry.

    thread-safe creates a workflow session.
    Each session holds an independent ClaudeProcess + TerminalSSEChannel pair.

    Attributes:
        sessions: session id -> WorkflowSession map
        lock: Lock for thread-safe access
    """

    def __init__(self, persist_dir: str | None = None) -> None:
        """Add to cart

        Args:
            persist dir: Directory to save session. If None persist inactive.
        """
        self._sessions: dict[str, WorkflowSession] = {}
        self._lock: threading.Lock = threading.Lock()
        self._persist_dir: str | None = persist_dir
        if self._persist_dir is not None:
            try:
                os.makedirs(self._persist_dir, exist_ok=True)
            except OSError:
                self._persist_dir = None

    def _session_file(self, session_id: str) -> str | None:
        """Returns the session event file path."""
        if self._persist_dir is None:
            return None
        return os.path.join(self._persist_dir, f'{session_id}.jsonl')

    def create(
        self,
        ticket_id: str,
        command: str,
        work_dir: str,
    ) -> WorkflowSession:
        """Create a new workflow session.

        allocates independent terminalSSEChannel and ClaudeProcess instances,
        Create session id to register in the registry.

        Args:
            ticket id: Kanban ticket ID (e.g. T-238)
            command: execution command (implement, review, research, etc.)
            work dir: task directory absolute path

        Returns:
            Created WorkflowSession instance
        """
        timestamp = time.strftime('%Y%m%d-%H%M%S')
        session_id = f'wf-{ticket_id}-{timestamp}'

        persist_path = self._session_file(session_id)
        channel = TerminalSSEChannel(persist_path=persist_path)
        process = ClaudeProcess(channel)

        session = WorkflowSession(
            session_id=session_id,
            ticket_id=ticket_id,
            command=command,
            work_dir=work_dir,
            process=process,
            channel=channel,
        )

        # session.current step auto update when stdout-based step detection
        def _on_step(step_name: str, _payload: dict) -> None:
            session.current_step = step_name
        channel.on_step = _on_step

        # Metadata to the file first line
        if persist_path is not None:
            try:
                meta = {
                    '_meta': {
                        'session_id': session_id,
                        'ticket_id': ticket_id,
                        'command': command,
                        'work_dir': work_dir,
                        'created_at': session.created_at,
                    }
                }
                with open(persist_path, 'w', encoding='utf-8') as f:
                    f.write(json.dumps(meta, ensure_ascii=False) + '\n')
            except OSError as exc:
                logger.error("workflow session[%s]: metadata persist write failed (%s): %s", session_id, persist_path, exc)

        with self._lock:
            self._sessions[session_id] = session

        return session

    def load_from_disk(self) -> int:
        """Restores registries by loading session metadata in persist directory.

        The first line of each *.jsonl file  meta only reads the WorkflowSession object.
        Event data is not restored in memory — Clients are redirected
        read directly from jsonl file via REST /workflow/history.
        process is created with new ClaudeProcess (status='stopped').

        Returns:
            Load more
        """
        if self._persist_dir is None or not os.path.isdir(self._persist_dir):
            return 0

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

            channel = TerminalSSEChannel(persist_path=fpath)
            process = ClaudeProcess(channel)
            session = WorkflowSession(
                session_id=meta['session_id'],
                ticket_id=meta.get('ticket_id', ''),
                command=meta.get('command', ''),
                work_dir=meta.get('work_dir', ''),
                process=process,
                channel=channel,
                created_at=meta.get('created_at', time.strftime('%Y-%m-%dT%H:%M:%S')),
            )

            with self._lock:
                self._sessions[session.session_id] = session
            loaded += 1

        return loaded

    def purge(self, session_id: str) -> bool:
        """Remove session completely from the registry and disk."""
        removed = self.remove(session_id)
        if removed and self._persist_dir is not None:
            fpath = self._session_file(session_id)
            if fpath and os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except OSError as exc:
                    logger.error("workflow session[%s]: Delete session files failed (%s): %s", session_id, fpath, exc)
        return removed

    def load_archived(self, session_id: str) -> 'WorkflowSession | None':
        """Restore the metadata of the session completed in the disk archive to on-demand.

        .jsonl .jsonl .jsonl .
        process is set to status='stopped' and new inputs are denied. This method is
        Without inserting a session to registry, the caller uses it as a one-time basis and sets the reference.

        Event data does not restore to memory — client REST /workflow/history
        read directly from jsonl file via endpoint.
        """
        if self._persist_dir is None:
            return None
        fpath = self._session_file(session_id)
        if fpath is None or not os.path.exists(fpath):
            return None
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                first_line = f.readline()
        except OSError:
            return None
        if not first_line:
            return None
        try:
            first = json.loads(first_line)
            meta = first.get('_meta') or {}
        except (json.JSONDecodeError, ValueError):
            return None
        if not meta.get('session_id'):
            return None

        channel = TerminalSSEChannel(persist_path=None)
        process = ClaudeProcess(channel)
        session = WorkflowSession(
            session_id=meta['session_id'],
            ticket_id=meta.get('ticket_id', ''),
            command=meta.get('command', ''),
            work_dir=meta.get('work_dir', ''),
            process=process,
            channel=channel,
            created_at=meta.get('created_at', time.strftime('%Y-%m-%dT%H:%M:%S')),
        )
        return session

    def get(self, session_id: str) -> WorkflowSession | None:
        """session id

        Args:
            session id: Session ID to view

        Returns:
            WorkflowSession instance. None.
        """
        with self._lock:
            return self._sessions.get(session_id)

    def remove(self, session_id: str) -> bool:
        """Remove session from the registry.

        The end of the process should be handled separately.

        Args:
            session id: Session ID to remove

        Returns:
            True, if the session does not exist, False.
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def list_all(self) -> list[dict]:
        """Returns the full session list to dict list.

        Returns:
            Session metadata dict list. Angle dict key:
            session_id, ticket_id, command, work_dir, status, created_at
        """
        with self._lock:
            return [
                {
                    'session_id': s.session_id,
                    'ticket_id': s.ticket_id,
                    'command': s.command,
                    'work_dir': s.work_dir,
                    'status': s.process.status,
                    'created_at': s.created_at,
                }
                for s in self._sessions.values()
            ]

    def get_by_ticket(self, ticket_id: str) -> WorkflowSession | None:
        """Check the session with the ticket ID.

        If there are multiple sessions in the same ticket, return the first matching.

        Args:
            Ticket ID: T-238)

        Returns:
            WorkflowSession instance. None.
        """
        with self._lock:
            for session in self._sessions.values():
                if session.ticket_id == ticket_id:
                    return session
            return None


# Module Level Workflow Session Registry Singleton
