"""SessionStart system prompt injection hook app placement coverage."""

from __future__ import annotations


def test_inject_prompt_imports_from_hook_app_boundary() -> None:
    from engine.apps.hooks import inject_prompt

    assert inject_prompt._strip_frontmatter("---\nname: x\n---\nbody") == "body"
    assert inject_prompt._strip_frontmatter("body") == "body"
