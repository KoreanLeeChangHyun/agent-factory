"""Sync adapter placement coverage."""

from __future__ import annotations


def test_sync_adapter_modules_import_from_adapter_boundary() -> None:
    from engine.adapters.sync import catalog_sync, history_sync, usage_sync

    assert callable(catalog_sync.main)
    assert callable(history_sync.main)
    assert callable(usage_sync.main)
