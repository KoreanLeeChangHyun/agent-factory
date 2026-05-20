"""Compatibility module alias for production-line launcher helpers."""

from __future__ import annotations

import sys
from importlib import import_module

_module = import_module("board.server.processes.production_line_launcher")
sys.modules[__name__] = _module
