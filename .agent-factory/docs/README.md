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

- [Agent Factory roadmap](refactor/agent-factory-roadmap.md): product pillars
  and milestone status.
- [Target DDD/TDD architecture](refactor/v2-ddd-tdd-target.md): domain,
  application, adapter, and contract boundaries.
- [LLM adapter architecture](refactor/llm-adapter-architecture.md): provider
  replacement strategy.
- [Domain directory restructure](refactor/domain-directory-restructure.md):
  planned source layout.
- [Layout convergence plan](refactor/layout-convergence-plan.md): current
  M12+ source move sequence and freeze list.
- [Runtime root rename](refactor/runtime-root-rename.md): historical migration
  from `.claude-organic` to `.agent-factory`.

## Historical Refactor Records

The files under `docs/refactor/` are migration records unless their heading says
otherwise. They are useful for context, but new work should follow the roadmap,
target architecture, and CLI reference above.
