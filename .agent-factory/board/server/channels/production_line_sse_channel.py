"""ProductionLineSSEChannel — per-session NDJSON broadcast + jsonl persist.

v1 TerminalSSEChannel and separated production-line only SSE channels.
One channel instance per ProductionLineSession is assigned.

call endpoint(`/step`, `/stdout`, `/phase`, `/finish`)
The broadcast itself is simple forward — meaning classification (text delta / tool use, etc.)
The front-end side branch is commissioned.
"""

from __future__ import annotations

import json
import threading
import time

from board.server.support.common import logger


class ProductionLineSSEChannel:
    """SSE channel for production-line — per-session client fan-out.

    Attributes:
        session id: possession session ID (wf-WR-NNN-<uuid>)
        clients: SSE client wfile list connected
        lock: Client List Access Lock
        client locks: per-client Lock by wfile
        next seq: SSE id sequence
        persist path: NDJSON file path (None tooth persist inert)
        persist lock
    """

    def __init__(self, session_id: str, persist_path: str | None = None) -> None:
        """Add to cart

        Args:
            session id: possession session ID
            persist path: NDJSON file path (None side persist inactive)
        """
        self.session_id: str = session_id
        self._clients: list = []
        self._lock: threading.Lock = threading.Lock()
        self._client_locks: dict = {}
        self._next_seq: int = 0
        self._persist_path: str | None = persist_path
        self._persist_lock: threading.Lock = threading.Lock()

    @property
    def persist_path(self) -> str | None:
        """NDJSON persist file absolute path (perist inactive None).

        WR-513 P1 — `GET /api/v2/sessions/<id>/history` endpoint
        read returns past events (REST Single Source Policy Completion).
        """
        return self._persist_path

    def add(self, wfile: object) -> None:
        """Registered SSE client to live stream.

        replay is separate endpoint (GET /api/v2/sessions/<id>/history) with NDJSON
        read in the file. This method only registers a new client and then live
        Get in touch
        """
        with self._lock:
            self._clients.append(wfile)
            self._client_locks[id(wfile)] = threading.Lock()

    def remove(self, wfile: object) -> None:
        """Remove the client."""
        with self._lock:
            try:
                self._clients.remove(wfile)
            except ValueError:
                pass
            self._client_locks.pop(id(wfile), None)

    def get_lock(self, wfile: object) -> threading.Lock | None:
        """return wfile per-client lock."""
        with self._lock:
            return self._client_locks.get(id(wfile))

    def client_count(self) -> int:
        """returns the number of clients currently connected (for testing)."""
        with self._lock:
            return len(self._clients)

    def broadcast(self, event_name: str, payload: dict) -> None:
        """Send SSE Event + NDJSON file persist.

        Args:
            event name: SSE event name (e.g. workflow step, workflow stdout)
            payload: event payload dict (JSON serialization possible)
        """
        json_payload = json.dumps(payload, ensure_ascii=False)
        self._emit_event(event_name, json_payload)

        if self._persist_path is not None:
            try:
                line = json.dumps(
                    {
                        'ts': time.time(),
                        'event': event_name,
                        'payload': payload,
                    },
                    ensure_ascii=False,
                ) + '\n'
                with self._persist_lock:
                    with open(self._persist_path, 'a', encoding='utf-8') as f:
                        f.write(line)
            except (OSError, TypeError) as exc:
                logger.error(
                    "production line sse channel[%s]: persist write failed (%s): %s",
                    self.session_id, self._persist_path, exc,
                )

    def emit_step(
        self, step: str, phase: str = '', prev_step: str = '',
        extras: dict | None = None,
    ) -> None:
        """workflow step event saturation — step ahead.

        Args:
            Step: New Step (NONE/INIT/PLAN/WORK/VALIDATE/REPORT/DONE/FAILED)
            phase: WORK internal sub-phase (P1, P2, ...). Without empty string
            prev step: Direct Step (frontend FSM verification)
            Extras: WR-495 P3 — forward-compatible meta such as verdict/commit/retry.
                Fixed key (session id/step/phase/prev step) is protected.
        """
        payload = {
            'session_id': self.session_id,
            'step': step,
            'phase': phase,
            'prev_step': prev_step,
        }
        if extras:
            for k, v in extras.items():
                if k not in payload:
                    payload[k] = v
        self.broadcast('workflow_step', payload)

    def emit_stdout(self, text: str, raw: dict | None = None) -> None:
        """workflow stdout event saturation — claude -p stdout NDJSON chunk.

        Args:
            text: text chunk (frontend fast path)
            raw: original NDJSON dict (frontend quarter renderer required)
        """
        payload = {
            'session_id': self.session_id,
            'text': text,
        }
        if raw is not None:
            payload['raw'] = raw
        self.broadcast('workflow_stdout', payload)

    def emit_phase(
        self, phase: str, action: str = 'start',
        extras: dict | None = None,
    ) -> None:
        """workflow phase event saturation — WORK internal phase transformation.

        Args:
            phase: P1, P2, ...
            action: start | end
            Extras: WR-495 P3 — forward-compatible meta such as verdict/commit/retry.
        """
        payload = {
            'session_id': self.session_id,
            'phase': phase,
            'action': action,
        }
        if extras:
            for k, v in extras.items():
                if k not in payload:
                    payload[k] = v
        self.broadcast('workflow_phase', payload)

    def emit_finish(
        self, outcome: str, summary: str = '',
        extras: dict | None = None,
    ) -> None:
        """workflow finish event saturation — cycle closing.

        Args:
            outcome: ok | fail
            summary: ending oil / one line summary
            Extras: WR-495 P3 — forward-compatible meta such as verdict/commit/retry.
        """
        payload = {
            'session_id': self.session_id,
            'outcome': outcome,
            'summary': summary,
        }
        if extras:
            for k, v in extras.items():
                if k not in payload:
                    payload[k] = v
        self.broadcast('workflow_finish', payload)

    def _emit_event(self, event_name: str, json_payload: str) -> None:
        """Send SSE event to all client after seq id authorization."""
        dead_clients: list = []
        with self._lock:
            seq_id = self._next_seq
            self._next_seq += 1
            message = f"id: {seq_id}\nevent: {event_name}\ndata: {json_payload}\n\n"
            encoded = message.encode('utf-8')
            clients_snapshot = list(self._clients)

        for wfile in clients_snapshot:
            wfile_id = id(wfile)
            client_lock = self._client_locks.get(wfile_id)
            if client_lock is None:
                continue
            try:
                with client_lock:
                    wfile.write(encoded)
                    wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                dead_clients.append(wfile)

        if dead_clients:
            with self._lock:
                for wfile in dead_clients:
                    try:
                        self._clients.remove(wfile)
                    except ValueError:
                        pass
                    self._client_locks.pop(id(wfile), None)
