"""Claude statusline hook app placement coverage."""

from __future__ import annotations


def test_statusline_imports_from_hook_app_boundary() -> None:
    from engine.apps.hooks import statusline

    assert statusline.format_tokens(1_500) == "1k"
    assert statusline.RESET == statusline.C_RESET
