from __future__ import annotations

from pathlib import Path

import pytest

from engine.adapters.llm.codex import CodexAdapter
from engine.adapters.llm.factory import LLMProviderConfig, make_llm_adapter
from engine.core.ports.llm import FakeAdapter


def test_provider_env_codex_selects_codex(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_FACTORY_LLM_PROVIDER", "codex")
    monkeypatch.setenv("CODEX_BIN", "codex-test")

    config = LLMProviderConfig.from_env()
    adapter = make_llm_adapter(config)

    assert isinstance(adapter, CodexAdapter)
    assert adapter.codex_bin == "codex-test"


def test_provider_default_remains_fake_for_unit_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENT_FACTORY_LLM_PROVIDER", raising=False)

    adapter = make_llm_adapter(LLMProviderConfig.from_env())

    assert isinstance(adapter, FakeAdapter)


def test_provider_config_can_read_settings_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENT_FACTORY_LLM_PROVIDER", raising=False)
    settings = tmp_path / ".settings"
    settings.write_text(
        "AGENT_FACTORY_LLM_PROVIDER=codex\nCODEX_MODEL=gpt-test\n",
        encoding="utf-8",
    )

    config = LLMProviderConfig.from_env(settings)

    assert config.provider == "codex"
    assert config.codex_model == "gpt-test"
