"""Canonical pytest bootstrap for the consolidated test tree."""

from __future__ import annotations

import sys
from pathlib import Path

AGENT_FACTORY_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AGENT_FACTORY_ROOT.parent
BOARD_ROOT = AGENT_FACTORY_ROOT / "board"

for path in (AGENT_FACTORY_ROOT, PROJECT_ROOT, BOARD_ROOT):
    path_s = str(path)
    if path_s in sys.path:
        sys.path.remove(path_s)
    sys.path.insert(0, path_s)
