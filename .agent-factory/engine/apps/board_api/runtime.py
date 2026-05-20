"""Board API runtime helpers used by the board server entrypoint."""

from __future__ import annotations

import hashlib
import os
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def is_port_in_use(port: int) -> bool:
    """Return True when localhost already accepts TCP connections on port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def resolve_port(
    project_root: str,
    *,
    range_start: int,
    range_end: int,
    port_in_use: Callable[[int], bool] = is_port_in_use,
) -> int:
    """Resolve a stable available board server port for a project root."""
    range_size = range_end - range_start + 1
    hash_bytes = hashlib.md5(project_root.encode()).digest()
    hash_int = int.from_bytes(hash_bytes[:4], byteorder="big")
    start_offset = hash_int % range_size

    for i in range(range_size):
        port = range_start + (start_offset + i) % range_size
        if not port_in_use(port):
            return port

    raise RuntimeError(f"Ports All ports in the range {range_start}~{range_end} are in use.")


def board_url_file_path(project_root: str) -> Path:
    return Path(project_root) / ".agent-factory" / ".board.url"


def write_board_url_file(project_root: str, port: int) -> str:
    """Persist the board URL file and return the base URL."""
    url_file = board_url_file_path(project_root)
    url_file.parent.mkdir(parents=True, exist_ok=True)
    base = f"http://127.0.0.1:{port}"
    url_file.write_text(f"{base}/index.html\n{base}/terminal.html", encoding="utf-8")
    return base


def read_board_url_port(project_root: str) -> int | None:
    """Return the port recorded in `.board.url`, or None when unavailable."""
    try:
        recorded_url = board_url_file_path(project_root).read_text(
            encoding="utf-8",
        ).strip().split("\n")[0]
    except OSError:
        return None
    try:
        return urlparse(recorded_url).port
    except ValueError:
        return None


def refresh_existing_board_url(project_root: str, port: int) -> None:
    """Rewrite `.board.url` for an already-running board server."""
    write_board_url_file(project_root, port)


def remove_board_url_file(project_root: str) -> None:
    try:
        board_url_file_path(project_root).unlink()
    except OSError:
        pass


def reap_zombie_children(*, waitpid: Callable[[int, int], tuple[int, int]] = os.waitpid) -> int:
    """Reap already-finished child processes without blocking."""
    count = 0
    try:
        while True:
            pid, _status = waitpid(-1, os.WNOHANG)
            if pid == 0:
                break
            count += 1
    except ChildProcessError:
        pass
    return count


def log_reaped_zombies(count: int, logger: Any) -> None:
    if count > 0:
        logger.info("[zombie-gc] reaped %d child processes", count)


__all__ = [
    "board_url_file_path",
    "is_port_in_use",
    "log_reaped_zombies",
    "read_board_url_port",
    "reap_zombie_children",
    "refresh_existing_board_url",
    "remove_board_url_file",
    "resolve_port",
    "write_board_url_file",
]
