"""Compatibility exports for Board factory data helpers.

The canonical implementation lives in ``board.factory_data``.
"""

from __future__ import annotations

from board import factory_data as _factory_data

for _name in dir(_factory_data):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_factory_data, _name)

__all__ = [_name for _name in globals() if not _name.startswith('__')]
