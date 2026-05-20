---
name: agent-factory-adapter
description: Use when adding or changing provider, CLI, filesystem, Git, Slack, Claude, Codex, hook, or LLM integrations in Agent Factory. Keep external systems behind adapters and preserve provider-neutral core/application code.
---

# Agent Factory Adapter

Use this skill for integration work at the edge of Agent Factory.

## Boundary Rules

- Core contracts live under `.agent-factory/engine/core`.
- Use-case orchestration lives under `.agent-factory/engine/application` or app stations.
- External systems live under `.agent-factory/engine/adapters`.
- User-facing entrypoints live under `.agent-factory/engine/apps`, `.agent-factory/bin`, `.agent-factory/hooks`, or board handlers.
- Provider-specific names such as Claude, Codex, Slack, GitHub, and filesystem details belong in adapters or integration surfaces, not generic core logic.

## Workflow

1. Find the existing port or create the smallest provider-neutral contract.
2. Implement concrete behavior in the matching adapter package.
3. Wire selection in a factory or app boundary, not inside core logic.
4. Add tests at the adapter boundary and at the caller boundary if behavior changes.
5. Document runtime settings in `.agent-factory/.settings` templates only when the setting must survive bootstrap.

## Codex Notes

- Codex LLM integration is under `engine/adapters/llm/codex.py`.
- Project-local Codex assets live under `.codex/`; never copy `$HOME/.codex` runtime state into the repo.
- Prefer additive Codex support over replacing Claude-specific surfaces that still power hooks or project assets.

