"""Tests for board API app observability helpers."""

from __future__ import annotations

import json
from typing import Any

from engine.apps.board_api import observability


def test_api_endpoint_emits_entry_and_exit(monkeypatch, tmp_path) -> None:
    bg = tmp_path / ".agent-factory" / "runs" / "bg"
    bg.mkdir(parents=True)
    (bg / "debug.enabled").write_text("")
    monkeypatch.chdir(tmp_path)

    @observability.api_endpoint("K", "move")
    def handler(_self: Any) -> str:
        return "ok"

    assert handler(object()) == "ok"

    lines = [
        json.loads(line)
        for line in (bg / "debug.log").read_text(encoding="utf-8").splitlines()
    ]
    tags = [line["tag"] for line in lines]
    assert "server.api.K.move.entry" in tags
    assert "server.api.K.move.exit" in tags


def test_api_endpoint_preserves_wrapped_metadata() -> None:
    @observability.api_endpoint("M", "save")
    def original(_self: Any) -> str:
        """Original docstring."""
        return "ok"

    assert original.__name__ == "original"
    assert original.__doc__ == "Original docstring."
