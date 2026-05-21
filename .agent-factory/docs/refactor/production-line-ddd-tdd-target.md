# Production-line DDD/TDD Refactor Target

## Goal

V1 workflow code is not a compatibility target. The product core is Production-line.

The refactor goal is to make the harness understandable to an LLM and safe to
change with TDD:

- Production-line workflow behavior is the canonical contract.
- Domain concepts are named explicitly.
- Claude-specific execution is isolated behind adapters.
- Tests describe behavior at the same boundary where code is changed.

## Absolute Workflow Order

The workflow order is absolute and provider-independent:

```text
PREPARE -> PLAN -> EXECUTE -> VERIFY -> REPORT -> COMPLETE
```

Korean labels:

```text
Preparing work -> Planning work -> Performing work -> Verifying work -> Reporting work -> Completing work
```

`INIT` is a runtime lifecycle event, not a core workflow stage.
`DONE` maps to the target `COMPLETE` stage.
`WORK` is renamed to `EXECUTE` in the target model.
`VALIDATE` is renamed to `VERIFY` in the target model to avoid mixing policy
validation, artifact verification, and final reporting concerns.

Core workflow code must preserve this order. Orchestration may choose retries,
parallelism, provider adapters, and event delivery, but it must not reorder the
five stages.

## Current Canonical Test Suite

Run from `.agent-factory/`:

```bash
python3 -m pytest
```

The default pytest scope is intentionally limited to the canonical root:

- `tests/`

Stale V1 tests are excluded from default collection in `pytest.ini`. They
should be deleted or rewritten against Production-line before any source directory move.

## Test Layout Policy

Green Production-line and board API tests now live under one canonical root. Older scattered
roots remain excluded until they are deleted or rewritten.

Canonical roots:

- `tests/domain/production-line`
- `tests/application/production_line`
- `tests/adapters/production_line`
- `tests/contracts/board_api`

Excluded legacy roots:

- `board/tests`
- `engine/flow/tests`
- `engine/flow/auditor/tests`
- `engine/guards/tests`
- `engine/tests/hooks`

Target layout remains:

```text
tests/
  domain/
  application/
  adapters/
  contracts/
  e2e/
```

Mapping:

| Current area | Target area |
|---|---|
| Production-line pure rules and plan loading | `tests/domain/production-line` |
| Production-line workflow/application behavior | `tests/application/production_line` |
| Production-line subprocess, git, template, and tool adapters | `tests/adapters/production_line` |
| board API contracts | `tests/contracts/board_api` |
| hook tests | `tests/adapters/hooks` |
| git/worktree tests | `tests/adapters/git` |
| stale V1 tests | delete or rewrite before moving |

Rules:

- There should be one top-level test package root.
- Avoid `tests/__init__.py` unless package imports are strictly needed.
- Test filenames should describe behavior, not old module names.
- Shared fixtures live in `tests/conftest.py` or narrow subdirectory
  `conftest.py` files.
- Do not keep test files next to V1 modules after V1 removal.

## Target Architecture

The target shape is DDD-inspired, not ceremony-heavy. The code should be easy
for agents to navigate by responsibility.

Detailed file-level move mapping lives in
`docs/refactor/domain-directory-restructure.md`.

The runtime root rename away from `.claude-organic/` is tracked separately in
`docs/refactor/runtime-root-rename.md`.

Provider independence is tracked in
`docs/refactor/llm-adapter-architecture.md`.

Reference material from `repo/` is cataloged in
`docs/refactor/repo-reference-assets.md`.

The executable milestone roadmap lives in
`docs/refactor/agent-factory-roadmap.md`.

```text
engine/
  core/
    domain/
      workflow.py
      plan.py
      artifact.py
      ticket.py
      validation.py
    application/
      run_workflow.py
      plan_step.py
      work_step.py
      validate_step.py
      report_step.py
      done_step.py
    ports/
      llm_adapter.py
      work_request_store.py
      artifact_store.py
      event_bus.py
      worktree.py
    adapters/
      llm/
        claude.py
        codex.py
        gemini.py
        fake.py
      filesystem_artifacts.py
      kanban_work_request_store.py
      board_event_bus.py
      git_worktree.py
    tests/
      domain/
      application/
      adapters/
```

`engine/production-line/` remains the working implementation during migration. Move code only
when tests exist at the new boundary.

## Domain Model

Use these terms consistently:

| Concept | Meaning |
|---|---|
| `WorkRequest` | Work Request. The source request that starts one or more workflow runs. |
| `WorkRequestRef` | Stable reference such as `T-123`; replaces `TicketRef` in the target model. |
| `WorkflowRun` | One execution cycle for one work request. |
| `WorkflowStage` | `PREPARE`, `PLAN`, `EXECUTE`, `VERIFY`, `REPORT`, `COMPLETE`. |
| `WorkflowLifecycle` | runtime events such as `STARTED`, `FAILED`, `CANCELLED`. |
| `Plan` | Structured execution plan loaded from `plan/plan.json`. |
| `Phase` | A unit of `EXECUTE`, optionally with dependencies and workers. |
| `Artifact` | File produced under a run directory. |
| `ExecutionSession` | Runtime session surfaced to the board. |
| `ValidationVerdict` | Deterministic result of rule and code validation. |

Avoid aliases such as `phase` for the whole workflow, `step` for kanban state,
or `session` when the object is actually a run.

## Work Request Ouroboros

Work request authoring uses an Ouroboros loop: the request drafts, critiques,
and improves itself before it becomes executable.

```text
DRAFT -> CLARIFY -> CRITIQUE -> REWRITE -> ACCEPT
          ^                         |
          |_________________________|
```

Korean labels:

```text
Draft -> Clarify -> Self-review -> Rewrite -> Approval
```

Purpose:

- make vague work requests executable
- surface missing acceptance criteria
- separate user intent from implementation guesses
- generate a better `PLAN` input before orchestration starts

The Ouroboros loop belongs to `WorkRequest`, not to `WorkflowRun`.
Once accepted, a `WorkRequest` may start a workflow run with the absolute stage
order:

```text
PREPARE -> PLAN -> EXECUTE -> VERIFY -> REPORT -> COMPLETE
```

Target request fields:

| Field | Meaning |
|---|---|
| `id` | `T-123` style stable identifier |
| `title` | short user-visible request title |
| `intent` | what the user wants |
| `context` | relevant background and constraints |
| `acceptance_criteria` | observable completion conditions |
| `non_goals` | explicit exclusions |
| `risk_notes` | known risks or ambiguity |
| `ouroboros_history` | critique/rewrite iterations |
| `status` | kanban/request state |

## Dependency Direction

Allowed direction:

```text
domain <- application <- adapters
                  ^
                  |
                driver
```

Rules:

- `domain` imports only Python stdlib and domain modules.
- `application` depends on ports, not concrete adapters.
- `adapters` may call subprocesses, filesystem, HTTP, git, or Claude.
- Board handlers call application services or adapters. They should not own
  workflow rules.
- Tests should prefer domain/application units before endpoint or subprocess
  tests.

## Claude Dependency Removal Plan

Claude remains an adapter during the first refactor. Do not spread direct
Claude assumptions into core code.

Claude-specific items to isolate:

- `claude -p` subprocess invocation.
- Claude Code hook payloads.
- `.claude/` and `.agent-factory/` runtime paths.
- Claude session IDs and terminal process management.
- Prompt templates that assume Claude wording or tool behavior.

Target port:

```python
class LLMAdapter(Protocol):
    def run(self, request: LLMRequest) -> LLMResult: ...
```

Initial adapters:

- `ClaudeAdapter`: current behavior.
- `CodexAdapter`: Codex provider implementation.
- `GeminiAdapter`: Gemini provider implementation.
- `FakeAdapter`: deterministic TDD runner.

## TDD Rules

Before moving or rewriting a module:

1. Add or identify a failing/covering test at the intended boundary.
2. Move behavior with no behavior change.
3. Run the canonical suite.
4. Delete or rewrite stale tests that describe V1 behavior.

Test levels:

| Level | What it covers | Example |
|---|---|---|
| Domain | Pure decisions and invariants | workflow transition validation |
| Application | Step orchestration with fake ports | `run_workflow` calls plan/work/validate |
| Adapter | Shell, filesystem, HTTP, git glue | Claude runner timeout handling |
| Contract | Board API and event shapes | `/api/v2/sessions/<id>/step` |

## Migration Phases

### Phase 0: Baseline

- Keep `engine/production-line` behavior green.
- Keep `board/server` tests green.
- Exclude stale V1 tests from default pytest.
- Document V1 removal inventory.

### Phase 0.5: Runtime Root Rename

- Rename `.claude-organic/` to a provider-neutral runtime root.
- Locked target: `.agent-factory/`.
- Keep `.claude/` only as the Claude Code integration surface.
- Do not combine this with domain file moves.

### Phase 1: V1 Removal

- Delete V1-only tests and missing wrapper expectations.
- Remove docs that present `flow-init`, `flow-step`, `flow-finish` as current.
- Replace V1 route references with Production-line route references.
- Keep shared utilities only if Production-line imports them.

### Phase 2: Boundary Extraction

- Extract domain dataclasses and enums from `engine/production-line/_common.py`.
- Extract ports for LLM, ticket, artifact, event, worktree.
- Convert step functions to application services.
- Keep wrappers and board endpoints stable.

### Phase 3: Claude Adapter Isolation

- Move direct Claude subprocess calls behind `LLMAdapter` and `ClaudeAdapter`.
- Move hook payload parsing behind a hook adapter.
- Add fake runner tests for plan/work/report behavior.

### Phase 4: Harness Upgrade

- Add multiple runner backends.
- Improve validation gates and replayability.
- Add run manifests and deterministic artifact indexing.
- Make board sessions inspectable and restartable independent of Claude.

## Definition Of Done

The refactor baseline is acceptable when:

- `python3 -m pytest` passes from `.agent-factory/`.
- V1 tests are gone or explicitly rewritten for Production-line behavior.
- No user-facing doc describes V1 as the active workflow.
- Core workflow logic can be understood without reading board handlers.
- Claude-specific code is located in adapters or hooks, not domain/application.
