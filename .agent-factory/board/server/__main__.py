"""server/__main__.py — entry point for ``python3 -m board.server``."""

from __future__ import annotations

import os
import subprocess
import sys

from .runtime.app import _run_server
from engine.apps.board_api.runtime import (
    is_port_in_use,
    read_board_url_port,
    refresh_existing_board_url,
    remove_board_url_file,
)


# A stable path (shim) to call when this script is redirected to the background.
_SHIM_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'server.py')
)


def main() -> int:
    """Start the server to the background.

    . board.url file exists or prevents duplicate execution in the corresponding port active status.

    Returns:
        Skip to content If the server is already running 0, 0 for success.
    """
    project_root = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', '..', '..')
    )

    recorded_port = read_board_url_port(project_root)
    if recorded_port and is_port_in_use(recorded_port):
        # Server is already running — Renew URL files only
        refresh_existing_board_url(project_root, recorded_port)
        return 0
    if recorded_port is not None:
        # stale file: Since the port is inactive, restart after deleting the file
        remove_board_url_file(project_root)

    # Run the background in your own --serve mode (using the shim path)
    subprocess.Popen(
        [sys.executable, _SHIM_PATH, '--serve', project_root],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == '--serve':
        _run_server(sys.argv[2])
    else:
        sys.exit(main())
