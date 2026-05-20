"""Compatibility module alias for board server runtime state."""

from __future__ import annotations

import sys
from importlib import import_module

_module = import_module("board.server.runtime.state")
sys.modules[__name__] = _module
