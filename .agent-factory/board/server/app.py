"""Compatibility module alias for the board server runtime app."""

from __future__ import annotations

import sys
from importlib import import_module

_module = import_module("board.server.runtime.app")
sys.modules[__name__] = _module
