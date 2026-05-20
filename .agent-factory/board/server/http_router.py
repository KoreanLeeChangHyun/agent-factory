"""Compatibility module alias for the board HTTP router."""

from __future__ import annotations

import sys
from importlib import import_module

_module = import_module("board.server.routing.http_router")
sys.modules[__name__] = _module
