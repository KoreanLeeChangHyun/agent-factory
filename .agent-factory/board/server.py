#!/usr/bin/env -S python3 -u
"""Board HTTP server — shim delegating to the server/ package.

The original monolithic server.py (3020 lines) was split in T-379 Phase 0-6
into a server/ package with Mixin-composed HTTP handler. This file preserves
the two invocation forms:

    python3 .agent-factory/board/server.py                 # start (main)
    python3 .agent-factory/board/server.py --serve <root>  # foreground

Alternative (package form):

    python3 -m board.server
"""

from __future__ import annotations

import os
import sys

# Add the .agent-factory/ directory to the import path (for accessing board.* and engine.*)
_BOARD_DIR = os.path.dirname(os.path.abspath(__file__))
_AGENT_FACTORY_DIR = os.path.dirname(_BOARD_DIR)
if _AGENT_FACTORY_DIR not in sys.path:
    sys.path.insert(0, _AGENT_FACTORY_DIR)

from board.server.__main__ import main  # noqa: E402
from board.server.app import _run_server  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--serve":
        _run_server(sys.argv[2])
    else:
        sys.exit(main())
