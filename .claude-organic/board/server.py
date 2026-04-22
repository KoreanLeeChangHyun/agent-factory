#!/usr/bin/env -S python3 -u
"""Board HTTP server — shim delegating to the server/ package.

The original monolithic server.py (3020 lines) was split in T-379 Phase 0-6
into a server/ package with Mixin-composed HTTP handler. This file preserves
the two invocation forms:

    python3 .claude-organic/board/server.py                 # start (main)
    python3 .claude-organic/board/server.py --serve <root>  # foreground

Alternative (package form):

    python3 -m board.server
"""

from __future__ import annotations

import os
import sys

# board/ 디렉터리를 import 경로에 추가 (board_data.py 및 server/ 접근용)
_BOARD_DIR = os.path.dirname(os.path.abspath(__file__))
if _BOARD_DIR not in sys.path:
    sys.path.insert(0, _BOARD_DIR)

from server.__main__ import main  # noqa: E402
from server.app import _run_server  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--serve":
        _run_server(sys.argv[2])
    else:
        sys.exit(main())
