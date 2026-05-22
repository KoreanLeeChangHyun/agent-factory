# Refactor Documentation Index

This directory contains active Agent Factory design documents and historical
migration records. New work should start from the active documents below.

## Read Order

1. [Agent Factory roadmap](agent-factory-roadmap.md)
2. [Target DDD/TDD architecture](production-line-ddd-tdd-target.md)
3. [LLM adapter architecture](llm-adapter-architecture.md)
4. [Action render event](action-render-event.md)
5. [Layout convergence plan](layout-convergence-plan.md)

## Active Design Docs

- [Agent Factory roadmap](agent-factory-roadmap.md): product pillars and
  milestone status.
- [Target DDD/TDD architecture](production-line-ddd-tdd-target.md): target
  domain, application, adapter, and contract boundaries.
- [LLM adapter architecture](llm-adapter-architecture.md): Claude, Codex,
  Gemini, and fake provider adapter boundary.
- [Action render event](action-render-event.md): provider-neutral Desk event
  contract for rendering actions, tool calls, and workflow updates.
- [Layout convergence plan](layout-convergence-plan.md): current source move
  order and freeze list.
- [Domain directory restructure](domain-directory-restructure.md): long-term
  source layout target.
- [Codex terminal transition plan](codex-terminal-transition-plan.md):
  experimental Console terminal provider migration.
- [Repo reference assets](repo-reference-assets.md): external reference
  repositories and assets.

## Archived Migration Records

- [Inventory](inventory.md): `.claude.workflow` to `.agent-factory` migration
  inventory.
- [Runtime root rename](runtime-root-rename.md): historical runtime root rename
  decision.
- [V1 removal inventory](v1-removal-inventory.md): archived V1 removal record.

## Current Focus

- Provider execution belongs behind the `LLMAdapter` boundary.
- Desk rendering uses `ActionRenderEvent`; it is not the same contract as raw
  Console terminal streaming.
- Provider-specific names stay at adapter and integration boundaries.

When a current design conflicts with an archived migration record, update the
active design doc first and treat the archived record as context only.
