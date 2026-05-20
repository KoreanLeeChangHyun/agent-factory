"""SSE client manager for kanban/workflow/dashboard events."""

from __future__ import annotations

import json
import threading
import time

from engine.adapters.board.watchers import FileWatcher, GitBranchWatcher


# ---------------------------------------------------------------------------
# SSE Client Manager
# ---------------------------------------------------------------------------


class SSEClientManager:
    """SSE Client Connection Manager.

    thread-safe,
    Broadcast events to all clients.

    Attributes:
        clients: list of wfile objects associated
        lock: Client List Approach Lock
        client locks: per-client Lock Dix
    """

    def __init__(self) -> None:
        """Add to cart"""
        self._clients: list = []
        self._lock: threading.Lock = threading.Lock()
        self._client_locks: dict = {}

    def add(self, wfile: object) -> None:
        """Add client.

        Args:
            wfile: HTTP handler wfile (socket output stream)
        """
        with self._lock:
            self._clients.append(wfile)
            self._client_locks[id(wfile)] = threading.Lock()

    def remove(self, wfile: object) -> None:
        """Remove the client.

        Args:
            wfile: wfile of client to remove
        """
        with self._lock:
            try:
                self._clients.remove(wfile)
            except ValueError:
                pass
            self._client_locks.pop(id(wfile), None)

    def get_lock(self, wfile: object) -> threading.Lock | None:
        """returns per-client lock to wfile.

        Args:
            wfile: client wfile to acquire lock

        Returns:
            Lock of the wfile. None if the client does not exist.
        """
        with self._lock:
            return self._client_locks.get(id(wfile))

    def broadcast(
        self,
        event_type: str,
        files: list | None = None,
        data: dict | None = None,
    ) -> None:
        """Send SSE events to all clients.

        The client fails to send (connect break) will be removed from the list.
        prevent concurrent write with heartbeat loop with per-client lock.

        Args:
            event type: SSE event type (kanban, workflow, dashboard, git branch, etc.)
            files: List of changed files. kanban event contains JSON in data field.
            data: random payload dict. Default file size
                  All files and data are sent to data for timestamp strings.
        """
        if data is not None:
            body = json.dumps(data)
        elif files is not None:
            body = json.dumps({"files": files})
        else:
            body = str(int(time.time()))
        message = f"event: {event_type}\ndata: {body}\n\n"
        encoded = message.encode('utf-8')

        dead_clients: list = []
        with self._lock:
            clients_snapshot = list(self._clients)

        for wfile in clients_snapshot:
            client_lock = self._client_locks.get(id(wfile))
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


# ---------------------------------------------------------------------------
# Terminal SSE Channel
# ---------------------------------------------------------------------------

# NDJSON message type -> SSE event name map
_NDJSON_EVENT_MAP: dict[str, str] = {
    'text_delta': 'stdout',
    'input_json_delta': 'stdout',
    'result': 'result',
    'system': 'system',
    'control_request': 'permission',
    'error': 'error',
    'user_input': 'user_input',
    'attachment': 'skill_listing',
    'rate_limit_event': 'rate_limit',
}
