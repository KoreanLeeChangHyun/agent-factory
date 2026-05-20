"""Compatibility alias for ``engine.apps.production_line._common``."""

from __future__ import annotations

import sys
from importlib import import_module

sys.modules[__name__] = import_module("engine.apps.production_line._common")
