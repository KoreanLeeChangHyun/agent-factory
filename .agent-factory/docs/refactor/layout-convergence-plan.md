# Layout Convergence Plan

## Purpose

M12 resets the directory refactor plan after M0-M11.

The original target layout in `domain-directory-restructure.md` is still the
direction, but the codebase has already evolved into a partial DDD layout. This
plan records the current structure, the target structure, and the safe order for
future moves.

No broad source move should happen before this plan is updated and the
canonical tests are green.

## Current Shape

Current high-level runtime layout:

```text
.agent-factory/
  bin/
  board/
    server/
      handlers/
    static/
      css/
      js/
  engine/
    core/
      work_requests/
      workflows/
    application/
      orchestration/
    adapters/
      hooks/
      kanban/
      llm/
    v2/
      core/
      prompts/
      steps/
      templates/
    flow/
    guards/
    memory_gc/
    sync/
    slack/
  hooks/
  tests/
    domain/
    application/
    adapters/
    architecture/
    contracts/
```

Current important facts:

- `tests/` is the canonical test root.
- `engine/core`, `engine/application`, and `engine/adapters` already exist.
- `engine/v2` remains the active workflow driver/runtime implementation.
- `engine/flow` still owns many active CLI, kanban, worktree, metrics, and
  skill utilities.
- `board/server` still owns HTTP handlers and board session/event glue.
- `board/static` is still the active web UI.
- top-level `hooks/` is still the active Claude Code hook entry surface.

## Target Shape

The target remains DDD-inspired:

```text
engine/
  core/
    workflows/
    work_requests/
    planning/
    execution/
    validation/
    reporting/
    worktrees/
    events/
    ports/
  application/
    orchestration/
    planning/
    execution/
    validation/
    reporting/
  adapters/
    llm/
    kanban/
    filesystem/
    git/
    board/
    hooks/
  apps/
    cli/
    board_api/
    hooks/
board/
  web/
tests/
  domain/
  application/
  adapters/
  contracts/
  e2e/
```

Decision: keep plural package names already introduced by M3/M4, such as
`workflows` and `work_requests`, unless a move has a strong reason to rename
them. Avoid churn that only changes spelling.

## Gap Analysis

| Area | Current | Target | Status |
|---|---|---|---|
| Workflow domain | `engine/core/workflows` | `engine/core/workflows` | mostly aligned |
| WorkRequest domain | `engine/core/work_requests` | `engine/core/work_requests` | mostly aligned |
| Orchestration app | `engine/application/orchestration` | same | aligned |
| LLM adapters | `engine/adapters/llm` | same | aligned |
| Kanban store adapter | `engine/adapters/kanban` | same | aligned |
| V2 driver | `engine/v2` | `engine/apps/cli` + application/core services | not aligned |
| Planning | `engine/v2/core`, `engine/v2/steps/plan.py` | `core/planning`, `application/planning` | not aligned |
| Validation | `engine/v2/_verify*.py`, `_validate.py`, `steps/validate.py` | `core/validation`, `application/validation` | not aligned |
| Reporting | `engine/v2/steps/report.py`, `engine/application/reporting`, `engine/core/reporting` | `core/reporting`, `application/reporting` | partially aligned |
| Worktree/Git | `engine/flow/worktree_manager.py`, `merge_pipeline.py`, `undo_done.py`, `engine/adapters/git`, `engine/core/worktrees`, `engine/git` | `core/worktrees`, `adapters/git` | partially aligned |
| Kanban CLI/service | `engine/flow/kanban*.py`, `engine/application/kanban` | `application`/`apps/cli` + adapters | partially aligned |
| Board API | `board/server/handlers`, `engine/application/kanban` | `engine/apps/board_api` or thin board handlers | partially aligned |
| Board web | `board/static` | `board/web` | not aligned |
| Hooks | top-level `hooks/`, `engine/adapters/hooks`, `engine/guards` | `engine/apps/hooks`, `adapters/hooks` | partially aligned |
| Memory | `engine/memory_gc`, board memory handlers/UI | keep domain-specific package | acceptable |
| Legacy tests | excluded roots under `engine/*/tests`, `board/tests` | delete/rewrite under `tests/` | not aligned |

## Move Policy

Use these rules for every move:

1. Move only one behavioral boundary at a time.
2. Add or identify tests at the destination boundary before moving.
3. Keep public wrappers stable: `flow-wf`, `flow-kanban`, board endpoints, and
   hook entry files must continue to work.
4. Leave compatibility imports when needed, but mark them as temporary.
5. Run `python3 -m pytest` from `.agent-factory/` after each slice.
6. Do not rename `.claude/` or remove Claude-specific adapters in layout work.

## Freeze List

Do not move these in early layout milestones:

- `.agent-factory/bin/*`: wrappers are the operator contract.
- `.agent-factory/hooks/*`: Claude Code settings point here directly.
- `.agent-factory/board/static/*`: web UI asset paths are coupled to the board.
- `.agent-factory/board/server/http_router.py`: route stability matters.
- `.agent-factory/engine/v2/driver.py`: keep as the active `flow-wf` entry until
  the services underneath it have moved.
- `.agent-factory/runs`, `.agent-factory/tickets`,
  `.agent-factory/staging`: runtime data, not source layout.

## First Safe Move Candidates

### Candidate A: Validation Core

Current:

- `engine/v2/_verify.py`
- `engine/v2/_verify_code.py`
- `engine/v2/_validate.py`
- `engine/v2/_verdict.py`

Target:

- `engine/core/validation/artifact_rules.py`
- `engine/core/validation/code_checks.py`
- `engine/core/validation/verdict.py`

Why first:

- Validation has focused domain tests.
- It is less coupled to board UI than kanban or sessions.
- `report.html` canonicalization is already tested.

Risk:

- V2 step modules import these helpers directly.

Mitigation:

- Move pure logic first.
- Leave `engine/v2/_*.py` compatibility modules that re-export moved functions.

### Candidate B: Planning Loader

Current:

- `engine/v2/core/plan_loader.py`

Target:

- `engine/core/planning/loader.py`

Why:

- Mostly pure parsing/loading behavior.
- Existing domain tests cover plan parsing/topology.

Risk:

- V2 path assumptions.

Mitigation:

- Keep V2 import wrapper initially.

### Candidate C: Worktree/Git Adapter

Current:

- `engine/flow/worktree_manager.py`
- `engine/flow/merge_pipeline.py`
- `engine/flow/undo_done.py`
- `engine/git/git_config.py`

Target:

- `engine/adapters/git/`
- `engine/core/worktrees/`

Why:

- Git subprocess behavior belongs outside core domain.

Risk:

- Board done/undo flows and CLI wrappers depend on current paths.

Mitigation:

- Move after validation/planning.
- Keep CLI wrappers unchanged.

## Deferred Moves

| Area | Reason |
|---|---|
| Board API handlers | endpoint contract and UI coupling are high |
| Board static -> board/web | mostly cosmetic until route/assets are stabilized |
| Hooks -> engine/apps/hooks | Claude Code settings point to top-level files |
| `engine/flow/kanban*.py` | kanban CLI, XML storage, board state, and DnD flows are intertwined |
| Full `engine/v2/driver.py` move | must wait until validation/planning/reporting services are extracted |

## Proposed Milestones

### M12: Layout Audit And Freeze

Status: complete

Deliverables:

- current/target layout comparison
- gap analysis
- freeze list
- first safe move candidates
- deferred move list

Acceptance:

- no source moves
- canonical tests pass
- roadmap links this plan

### M13: Validation Core Extraction

Status: complete

Goal:

Move pure validation/verdict logic into `engine/core/validation` while keeping
V2 compatibility imports.

Completed slice:

- created `engine/core/validation/artifact_rules.py`
- moved deterministic artifact checks from `engine/v2/_verify.py`
- kept `engine/v2/_verify.py` as a V2 compatibility export module
- created `engine/core/planning/loader.py`
- moved the pure planning loader from `engine/v2/core/plan_loader.py` because
  core validation needs plan schema validation without a core-to-V2 import
- kept `engine/v2/core/plan_loader.py` as a V2 compatibility export module
- deferred `_verify_code.py`, `_validate.py`, and `_verdict.py` because they
  still depend on subprocess, runtime context, and verdict artifact writing

Acceptance:

- `tests/domain/validation/test_artifact_rules.py` passes
- `tests/domain/planning/test_loader.py` passes
- `tests/domain/v2/test_validate.py` passes
- `tests/domain/v2/test_verify.py` passes
- `tests/application/v2/test_steps_validate.py` passes
- `tests/architecture/test_boundaries.py` passes
- full pytest passes

### M14: Planning Loader Extraction

Status: complete

Goal:

Move plan loading/parsing into `engine/core/planning`.

Completed slice:

- migrated canonical plan parser tests from `tests/domain/v2` to
  `tests/domain/planning`
- migrated topology-level tests from `tests/domain/v2` to
  `tests/domain/planning`
- updated V2 WORK step to import from `engine.core.planning.loader`
- left `engine/v2/core/plan_loader.py` as a compatibility export module
- added focused V2 compatibility coverage for the old import path

Acceptance:

- plan parsing/topology tests pass
- V2 PLAN step tests pass
- V2 WORK step tests pass
- architecture boundary tests pass
- full pytest passes

### M15: Reporting Service Extraction

Status: complete

Goal:

Move report artifact generation and template ownership toward
`engine/core/reporting` and `engine/application/reporting`.

Completed slice:

- moved `report.html` template ownership to `engine/core/reporting/templates`
- added `engine/core/reporting/templates.py`
- added `engine/application/reporting/prompt.py`
- updated V2 REPORT step to delegate deterministic prompt construction
- kept V2 runtime orchestration, retry, verification, and manifest writing in
  place
- kept `engine.v2._common.load_template("report.html")` compatibility

Acceptance:

- report HTML tests pass
- REPORT step tests pass
- board workflow report artifact tests pass
- architecture boundary tests pass
- full pytest passes

### M16: Worktree/Git Boundary

Status: complete

Goal:

Separate git subprocess gateways from worktree domain decisions.

Completed slice:

- added `engine/adapters/git/cli.py` for git subprocess execution
- added `engine/core/worktrees/paths.py` for pure ticket/path/lock rules
- routed `flow.worktree_manager._git` through the git adapter
- updated worktree path construction to use core worktree rules
- kept `flow.worktree_manager._git` as the legacy patch point for existing
  tests and callers
- kept `flow-merge` and `flow-kanban` wrapper behavior stable

Acceptance:

- canonical worktree/git boundary tests pass
- board API smoke contracts pass
- `flow-merge --help` passes
- `flow-kanban list` passes
- full pytest passes

### M17: Kanban And Board API Boundary

Status: complete

Goal:

Make board handlers thin and move kanban service decisions behind application
or adapter boundaries.

Completed slice:

- added `engine/application/kanban/done_result.py`
- moved `flow-kanban done` failure classification out of board handlers
- moved `flow-undo-done` stdout regex ownership out of board handlers
- kept `board/server/handlers/_kanban_done_re.py` as a compatibility export
  module
- kept HTTP handlers and subprocess calls in place for this slice

Acceptance:

- `flow-kanban` smoke passes
- board API contracts pass
- full pytest passes

### M18: Workflow Session Persist Cleanup

Status: complete

Goal:

Remove root-level workflow session caches from the active runtime path.

Completed slice:

- changed default V2 workflow event persistence to
  `runs/<registry>/workflow-events.jsonl`
- stopped board startup from creating `.agent-factory/.workflow-sessions-v2`
- stopped board startup from creating `.agent-factory/.workflow-sessions`
- kept explicit `persist_dir` support for tests and legacy registry
  construction
- kept V2 history endpoint behavior backed by `session.channel.persist_path`
- added `.agent-factory/.workflow-sessions-v2/` to `.gitignore`

Acceptance:

- V2 history endpoint tests pass
- V2 workflow session registry tests pass
- full pytest passes

### M19: Hooks Boundary

Status: complete

Goal:

Clarify top-level hooks as app entrypoints and guards as hook adapters.

Completed slice:

- added `engine/adapters/hooks/dispatcher.py` for shared Claude Code hook
  dispatcher behavior
- kept `.agent-factory/hooks/dispatcher.py` as a compatibility wrapper for
  existing hook entrypoint imports
- kept top-level hook entry files stable for Claude Code settings
- added adapter tests for hook flag parsing, path resolution, dispatch
  aggregation, and wrapper exports

Acceptance:

- hook regression tests pass
- Claude Code settings continue to point to stable entry files

### M20: Naming And Rebranding

Status: complete

Goal:

Clean active user-facing names after layout has stabilized.

Completed slice:

- added `docs/naming-policy.md` as the active naming rule
- linked the naming policy from the documentation index
- renamed remaining `organic` test bootstrap variables to Agent Factory terms
- changed the standalone board title from `Claude Code Terminal` to
  `Agent Factory Terminal`
- changed board CSS header comments from Claude-branded dashboard labels to
  Agent Factory dashboard labels
- left Claude names where they describe provider adapters, `.claude/`, Claude
  Code hooks, or historical migration records

Acceptance:

- active docs use Agent Factory naming
- provider-specific Claude names remain only in adapters or `.claude/`
  integration surfaces

## Verification Baseline

Current baseline:

```text
python3 -m pytest  # 384 passed, 2 skipped
```
