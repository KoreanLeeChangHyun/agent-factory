# `.repo` Reference Assets

The `.repo/` directory contains external reference implementations and templates
that should inform `.agent-factory`, but should not be copied blindly.

Use these repos as design references while preserving our domain language:

```text
WorkRequest -> Ouroboros Refinement -> WorkflowRun
PREPARE -> PLAN -> EXECUTE -> VERIFY -> REPORT -> COMPLETE
LLMAdapter -> Claude / Codex / Gemini / Fake
```

## High-Value References

### `.repo/ouroboros`

Best fit:

- WorkRequest authoring
- Ouroboros refinement loop
- specification-first execution
- multi-runtime support
- evaluation pipeline

Useful ideas:

- "Stop prompting. Start specifying."
- input clarity is the main bottleneck
- interview -> seed/spec -> execute -> evaluate -> evolve
- ambiguity scoring / convergence
- runtime guides for Claude, Codex, Gemini, OpenCode, Kiro, Copilot
- tests split into `unit`, `integration`, `e2e`

Apply to `.agent-factory`:

- WorkRequest authoring should expose hidden assumptions before workflow starts.
- Accepted WorkRequests should become immutable enough for reproducible runs.
- Evaluation output can feed later WorkRequest refinement, but should not reorder
  the absolute workflow stages.

Do not copy directly:

- command names such as `ooo`
- project branding
- full Agent OS scope

### `.repo/OpenHarness`

Best fit:

- harness engineering vocabulary
- provider/runtime integration ideas
- tools, skills, memory, permissions, agent coordination
- long-running session infrastructure

Useful ideas:

- harness as tools + knowledge + observation + action + permissions
- dry-run readiness checks
- provider compatibility
- channel/gateway model
- memory and session persistence

Apply to `.agent-factory`:

- Harness Engineering is the third responsibility: executing an accepted
  WorkRequest safely and observably.
- Keep tools, permissions, memory, and sessions as infrastructure around the
  model, not inside the core workflow domain.

Do not copy directly:

- UI/marketing structure
- broad chatbot/channel product scope unless it supports WorkRequest execution

### `.repo/ai-harness-template`

Best fit:

- gates
- methodology plugin system
- DDD/TDD/BDD/security/observability methods
- structural enforcement

Useful ideas:

- harness core fixed, methodology plugins optional
- gates as blocking constraints, not suggestions
- method bundles such as `ouroboros`, `ddd-lite`, `tdd-strict`,
  `observability-first`, `threat-model-lite`
- isolated security gate

Apply to `.agent-factory`:

- Use method plugins as optional WorkRequest refinement or verification policies.
- Keep the absolute workflow order fixed.
- Add gates around request quality, architecture boundaries, tests, security,
  and observability.

Do not copy directly:

- `.harness/` root naming; our locked runtime root is `.agent-factory/`
- Claude-specific command assumptions

## Secondary References

### `.repo/everything-claude-code`

Use for:

- cataloging Claude-specific integration points
- migration checklist when isolating Claude into `ClaudeAdapter`
- skills/plugins ecosystem patterns

Avoid:

- reinforcing Claude as the core runtime

### `.repo/oh-my-claudecode`

Use for:

- Claude Code command/skill UX references
- setup/uninstall patterns

Avoid:

- Claude-centric architecture decisions

### `.repo/andrej-karpathy-skills`, `.repo/skills`, `.repo/superpowers`

Use for:

- skill authoring style
- prompt/task decomposition examples
- lightweight reusable capability packaging

Apply later after WorkRequest and LLMAdapter boundaries are stable.

### `.repo/Claude-Usage-Tracker`

Use for:

- usage/cost/status surface ideas

Mostly unrelated to the refactor core.

### `.repo/gstack`, `.repo/gsd-2`

Not yet classified. Review only if they contain provider orchestration,
developer workflow, or UI patterns relevant to `.agent-factory`.

## Adoption Rules

- Extract concepts, not code, unless a file is clearly standalone and licensed
  compatibly.
- Keep `.agent-factory` language:
  - `WorkRequest`, not ticket/spec/seed as the primary domain term.
  - `LLMAdapter`, not provider-specific runner.
  - `PREPARE -> PLAN -> EXECUTE -> VERIFY -> REPORT -> COMPLETE`.
- Add a focused test before importing any behavior inspired by `.repo`.
- Do not introduce a new methodology unless it improves WorkRequest quality,
  Harness Engineering, or Verification/Reporting.

