"""Sync adapter placement coverage."""

from __future__ import annotations


def test_sync_adapter_modules_import_from_adapter_boundary() -> None:
    from engine.adapters.sync import catalog_sync, history_sync, usage_sync

    assert callable(catalog_sync.main)
    assert callable(history_sync.main)
    assert callable(usage_sync.main)


def test_flow_catalog_wrapper_points_to_sync_adapter() -> None:
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    wrapper = repo_root / ".agent-factory" / "bin" / "flow-catalog"

    assert "engine/adapters/sync/catalog_sync.py" in wrapper.read_text(encoding="utf-8")
