"""Provider selection for LLM adapters."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from engine.core.ports.llm import FakeAdapter, LLMAdapter

from .claude import ClaudeAdapter
from .codex import CodexAdapter


def _read_settings(path: Path | None) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


@dataclass(frozen=True)
class LLMProviderConfig:
    provider: str = "fake"
    codex_bin: str = "codex"
    codex_model: str | None = None
    codex_profile: str | None = None
    codex_sandbox: str = "workspace-write"
    codex_approval_policy: str = "never"
    claude_permission_mode: str = "bypassPermissions"

    @classmethod
    def from_env(cls, settings_path: Path | None = None) -> "LLMProviderConfig":
        settings = _read_settings(settings_path)

        def get(key: str, default: str | None = None) -> str | None:
            return os.environ.get(key) or settings.get(key) or default

        return cls(
            provider=str(get("AGENT_FACTORY_LLM_PROVIDER", "fake")).strip().lower(),
            codex_bin=str(get("CODEX_BIN", "codex")),
            codex_model=get("CODEX_MODEL"),
            codex_profile=get("CODEX_PROFILE"),
            codex_sandbox=str(get("CODEX_SANDBOX", "workspace-write")),
            codex_approval_policy=str(get("CODEX_APPROVAL_POLICY", "never")),
            claude_permission_mode=str(get("CLAUDE_PERMISSION_MODE", "bypassPermissions")),
        )


def make_llm_adapter(config: LLMProviderConfig | None = None) -> LLMAdapter:
    cfg = config or LLMProviderConfig.from_env()
    if cfg.provider == "fake":
        return FakeAdapter()
    if cfg.provider == "codex":
        return CodexAdapter(
            codex_bin=cfg.codex_bin,
            model=cfg.codex_model,
            profile=cfg.codex_profile,
            sandbox=cfg.codex_sandbox,
            approval_policy=cfg.codex_approval_policy,
        )
    if cfg.provider == "claude":
        return ClaudeAdapter(permission_mode=cfg.claude_permission_mode)
    raise ValueError(f"unknown LLM provider: {cfg.provider!r}")
