# Agent Factory Documentation

`.agent-factory` is the runtime root for WorkRequest authoring, workflow
execution, verification, reporting, board services, and provider adapters.

## Operator Docs

- [CLI reference](cli-reference.md): active `flow-*` wrappers.
- [Common constraints](common-constraints.md): shared workflow constraints.
- [Naming policy](naming-policy.md): active Agent Factory naming and allowed
  provider-specific exceptions.
- [M10 release and migration notes](release-migration-notes.md): cleanup status
  and migration guidance.

## Architecture Docs

- [Refactor documentation index](refactor/README.md): current read order,
  active design docs, and archived migration records.
- [Agent Factory roadmap](refactor/agent-factory-roadmap.md): product pillars
  and milestone status.
- [Target DDD/TDD architecture](refactor/production-line-ddd-tdd-target.md):
  domain, application, adapter, and contract boundaries.
- [LLM adapter architecture](refactor/llm-adapter-architecture.md): provider
  replacement strategy.
- [Action render event](refactor/action-render-event.md): provider-neutral
  Desk rendering contract for agent actions, tool calls, and workflow updates.
- [Codex terminal transition plan](refactor/codex-terminal-transition-plan.md):
  experimental provider-neutral Console terminal migration.
- [Domain directory restructure](refactor/domain-directory-restructure.md):
  planned source layout.
- [Layout convergence plan](refactor/layout-convergence-plan.md): current
  M12+ source move sequence and freeze list.
- [Runtime root rename](refactor/runtime-root-rename.md): historical migration
  from `.claude-organic` to `.agent-factory`.

## Historical Refactor Records

The files under `docs/refactor/` include both active design docs and archived
migration records. Use the refactor documentation index first to avoid treating
historical migration notes as current implementation guidance.
