#!/usr/bin/env -S python3 -u
"""Board HTTP server launcher.

Starts python3 -m http.server on port 8080 if not already running.
Designed to be called from SessionStart hook.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import os


def is_port_in_use(port: int) -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def main() -> int:
    port = 9977
    if is_port_in_use(port):
        return 0

    project_root = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', '..', '..')
    )

    subprocess.Popen(
        [sys.executable, '-m', 'http.server', str(port)],
        cwd=project_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
