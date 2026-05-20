"""Compatibility module alias for board server shared support."""

from __future__ import annotations

import sys
from importlib import import_module

_module = import_module("board.server.support.common")
sys.modules[__name__] = _module
