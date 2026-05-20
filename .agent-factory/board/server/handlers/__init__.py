"""Compatibility exports for legacy Board handler imports.

The active implementations live under ``engine.apps.board_api``. This package is
kept as a lazy compatibility surface for older ``board.server.handlers`` imports.
"""

from __future__ import annotations

__all__ = [
    'GenericHandlerMixin',
    'FilesHandlerMixin',
    'SyncHandlerMixin',
    'SettingsHandlerMixin',
    'TerminalHandlerMixin',
    'KanbanHandlerMixin',
    'V2WorkflowHandlerMixin',
    'MetricsHandlerMixin',
    'MemoryGcHandlerMixin',
    'WorktreeCommitHandlerMixin',
]

_EXPORT_MODULES = {
    'GenericHandlerMixin': '.generic',
    'FilesHandlerMixin': '.files',
    'SyncHandlerMixin': '.sync',
    'SettingsHandlerMixin': '.settings',
    'TerminalHandlerMixin': '.terminal',
    'KanbanHandlerMixin': '.kanban',
    'V2WorkflowHandlerMixin': '.v2_workflow',
    'MetricsHandlerMixin': '.metrics',
    'MemoryGcHandlerMixin': '.memory_gc',
    'WorktreeCommitHandlerMixin': '.worktree_commit',
}


def __getattr__(name: str) -> object:
    if name not in _EXPORT_MODULES:
        raise AttributeError(name)

    from importlib import import_module

    module = import_module(_EXPORT_MODULES[name], __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
