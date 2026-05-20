"""Contract tests for board web static path routing."""

from __future__ import annotations

from pathlib import Path

from board.server.http_router import BoardHTTPRequestHandler


def _make_handler(tmp_path: Path):
    handler = BoardHTTPRequestHandler.__new__(BoardHTTPRequestHandler)
    handler.directory = str(tmp_path / ".agent-factory" / "board" / "web")
    handler._project_root = str(tmp_path)
    return handler


def test_translate_path_uses_board_web_root(tmp_path) -> None:
    handler = _make_handler(tmp_path)

    resolved = handler.translate_path("/index.html")

    assert resolved == str(tmp_path / ".agent-factory" / "board" / "web" / "index.html")


def test_translate_path_keeps_legacy_board_static_url_compatible(tmp_path) -> None:
    handler = _make_handler(tmp_path)

    resolved = handler.translate_path("/.agent-factory/board/static/js/core/app.js")

    assert resolved == str(
        tmp_path / ".agent-factory" / "board" / "web" / "js" / "core" / "app.js"
    )
