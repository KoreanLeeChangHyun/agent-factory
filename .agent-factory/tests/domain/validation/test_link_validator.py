"""Link validator core placement coverage."""

from __future__ import annotations

from engine.core.validation import link_validator


def test_link_validator_imports_from_core_validation_boundary() -> None:
    assert link_validator.extract_links("[x](docs/a.md)") == ["docs/a.md"]
    assert link_validator._is_skip_link("#summary")
