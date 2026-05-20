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
      handlers/  # compatibility exports only
    web/
      css/
      js/
  engine/
    core/
      ports/
      work_requests/
      workflows/
    application/
      orchestration/
    adapters/
      hooks/
      kanban/
      llm/
    apps/
      board_api/
      cli/
      hooks/
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
- `board/server` owns the HTTP router plus board session/event glue; handler
  implementations live under `engine/apps/board_api`.
- `board/web` is the active web UI; old `/.agent-factory/board/static/*` URLs
  are translated for compatibility.
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
| V2 driver | `engine/apps/cli`, `engine/v2` | `engine/apps/cli` + application/core services | partially aligned |
| Planning | `engine/v2/core`, `engine/v2/steps/plan.py` | `core/planning`, `application/planning` | not aligned |
| Validation | `engine/v2/_verify*.py`, `_validate.py`, `steps/validate.py` | `core/validation`, `application/validation` | not aligned |
| Reporting | `engine/v2/steps/report.py`, `engine/application/reporting`, `engine/core/reporting` | `core/reporting`, `application/reporting` | partially aligned |
| Worktree/Git | `engine/flow/worktree_manager.py`, `merge_pipeline.py`, `undo_done.py`, `engine/adapters/git`, `engine/core/worktrees` | `core/worktrees`, `adapters/git` | partially aligned |
| Kanban CLI/service | `engine/flow/kanban*.py`, `engine/application/kanban` | `application`/`apps/cli` + adapters | partially aligned |
| Board API | `engine/apps/board_api` with `board/server/handlers` compatibility exports | `engine/apps/board_api` or thin board handlers | aligned |
| Board web | `board/web` | `board/web` | aligned |
| Hooks | top-level `hooks/`, `engine/apps/hooks`, `engine/adapters/hooks`, `engine/guards` | `engine/apps/hooks`, `adapters/hooks` | mostly aligned |
| Memory | `engine/memory_gc`, board memory handlers/UI | keep domain-specific package | acceptable |
| Legacy tests | canonical `tests/` root | `tests/` | aligned |

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
- `.agent-factory/board/web/*`: web UI asset paths are coupled to the board.
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

### M21: Hook And V2 Legacy Test Migration

Status: complete

Goal:

Move green hook, guard, and V2 verdict tests out of legacy excluded roots into
the canonical `tests/` tree.

Completed slice:

- moved `engine/guards/tests` guard coverage to `tests/adapters/hooks`
- moved `engine/tests/hooks` PreToolUse coverage to `tests/adapters/hooks`
- moved `engine/tests/test_v2_m9_verdict.py` to `tests/application/v2`
- removed empty legacy test package markers under `engine/guards/tests` and
  `engine/tests`
- removed `engine/guards/tests` and `engine/tests` from pytest quarantine

Acceptance:

- migrated hook/guard tests pass from the canonical tree
- migrated V2 verdict tests pass from the canonical tree
- full pytest includes the migrated tests and passes

### M22: Board Green Test Migration

Status: complete

Goal:

Move green board contract tests out of the legacy `board/tests` package into
the canonical board API contract tree.

Completed slice:

- moved V2 launcher tests to `tests/contracts/board_api`
- moved kanban audit verdict tests to `tests/contracts/board_api`
- moved V2 workflow phase 1 tests to `tests/contracts/board_api`
- moved M8 WorkRequest facade handler tests to `tests/contracts/board_api`
- left stale `board/tests/test_handlers_t424.py` quarantined because it still
  expects the removed `workflow_undo` handler

Acceptance:

- migrated board tests pass from canonical paths
- full pytest includes the migrated board tests and passes
- `board/tests` remains quarantined until the stale T-424 test is rewritten or
  deleted

### M23: Board Handler Test Rewrite

Status: complete

Goal:

Remove the remaining `board/tests` quarantine by rewriting stale T-424 handler
coverage against current kanban-domain endpoints.

Completed slice:

- rewrote the old T-424 handler regression test under
  `tests/contracts/board_api`
- replaced removed `workflow_undo` expectations with
  `KanbanHandlerMixin._handle_kanban_undo_done` coverage
- kept done/undo regex, done failure classification, review XML precondition,
  undo stderr parsing, undo success parsing, and force-done dirty guard
  coverage
- removed `board/tests/__init__.py`
- removed `board/tests` from pytest quarantine

Acceptance:

- rewritten T-424 board handler tests pass from canonical paths
- full pytest includes board handler coverage and passes
- no tracked files remain under `board/tests`

### M24: Flow Green Test Migration

Status: complete

Goal:

Move green `engine/flow/tests` coverage into the canonical test tree while
leaving stale V1-era tests quarantined for rewrite/delete decisions.

Completed slice:

- added `tests/application/flow`
- moved green flow tests for kanban done parsing, merge anchor safety,
  premerge state guard, review verdict, subagent-stop sentinel, ticket
  numbering, ticket repository failures, undo/redo cycle, user-prompt-submit,
  and worker commit detection
- updated relocated tests to resolve `.agent-factory/engine` and hook paths from
  the canonical tree
- left stale or partially stale flow tests quarantined for M26:
  `test_failure_handler.py`, `test_fsm_8state.py`,
  `test_http_launcher_timeout.py`, `test_kanban_force_done_handler.py`,
  `test_merge_conflict_detection.py`, `test_phase_verifier.py`,
  `test_sessions_status.py`, `test_stop.py`, `test_undo_done.py`, and
  `test_worker_return_parser.py`

Acceptance:

- migrated flow tests pass from canonical paths
- full pytest includes migrated flow tests and passes
- remaining flow quarantine is explicitly narrowed to stale/partial failures

### M25: Auditor Green Test Migration

Status: complete

Goal:

Move green auditor tests out of `engine/flow/auditor/tests` into the canonical
application flow test tree.

Completed slice:

- added `tests/application/flow/auditor`
- moved auditor dataclass, rubric, and runner dry-run tests
- updated relocated tests to resolve `.agent-factory/engine` from the canonical
  tree
- left stale `test_finalization_audit_hook.py` quarantined because it imports
  removed `flow.finalization`

Acceptance:

- migrated auditor tests pass from canonical paths
- full pytest includes migrated auditor tests and passes
- remaining auditor quarantine is narrowed to the stale finalization hook test

### M26: Stale Flow Test Prune And Migration

Status: complete

Goal:

Finish active `engine/flow/tests` cleanup by deleting V1-only tests and moving
the remaining current flow coverage into `tests/application/flow`.

Completed slice:

- deleted V1-only tests for removed failure handler, 8-state FSM,
  HTTP launcher, old force-done generic handler, phase verifier wrapper,
  sessions status, stop command, and finalization audit hook
- moved current merge conflict, undo-done, and worker return parser tests to
  `tests/application/flow`
- updated relocated tests to resolve `.agent-factory/engine` from canonical
  paths
- removed obsolete `ticket_state` imports and the stale T-446 advisory wording
  expectation
- removed empty legacy flow test package markers

Acceptance:

- migrated current flow tests pass from canonical paths
- full pytest includes migrated current flow tests and passes
- no tracked files remain under legacy flow test roots

### M27: Test Quarantine Removal

Status: complete

Goal:

Remove the final pytest quarantine entry now that all tracked legacy test roots
are empty or gone.

Completed slice:

- removed `board/server/tests` from `pytest.ini` quarantine
- removed stale untracked legacy test cache directories from the workspace
- confirmed no tracked files remain under legacy test roots

Acceptance:

- canonical pytest still passes
- `pytest.ini` no longer carries stale legacy test quarantine entries

### M28: CLI App Entrypoint

Status: complete

Goal:

Introduce the target `engine/apps/cli` boundary for the workflow CLI without
moving the active V2 driver internals.

Completed slice:

- added `engine/apps/cli/flow_wf.py` as the app-layer workflow CLI entrypoint
- kept `engine.v2.driver` as the active driver implementation
- rewired `flow-wf submit` and `flow-launcher` to call
  `engine.apps.cli.flow_wf`
- added focused delegation coverage for the new CLI app entrypoint

Acceptance:

- CLI app entrypoint delegates to the current V2 driver
- `flow-wf --help` still works
- full pytest passes

### M29: SessionStart Hook App Entrypoint

Status: complete

Goal:

Start the `engine/apps/hooks` boundary while preserving stable top-level Claude
Code hook files.

Completed slice:

- added `engine/apps/hooks/session_start.py`
- moved SessionStart dispatch behavior behind the hook app entrypoint
- kept `.agent-factory/hooks/session-start.py` as a compatibility wrapper
- added focused SessionStart app tests

Acceptance:

- SessionStart app test passes
- top-level `session-start.py` smoke passes
- full pytest passes

### M30: PostToolUse Hook App Entrypoint

Status: complete

Goal:

Continue the `engine/apps/hooks` boundary by moving PostToolUse behavior out of
the stable top-level hook script.

Completed slice:

- added `engine/apps/hooks/post_tool_use.py`
- moved PostToolUse dispatch, catalog sync triggering, Bash cleanup, and
  metrics recording behind the hook app entrypoint
- kept `.agent-factory/hooks/post-tool-use.py` as a compatibility wrapper
- added focused PostToolUse app tests

Acceptance:

- PostToolUse app tests pass
- top-level `post-tool-use.py` smoke passes
- full pytest passes

### M31: UserPromptSubmit Hook App Entrypoint

Status: complete

Goal:

Continue top-level hook thinning by moving UserPromptSubmit behavior into the
`engine/apps/hooks` boundary.

Completed slice:

- added `engine/apps/hooks/user_prompt_submit.py`
- moved main-session guard, dispatcher invocation, debug logging, and stdout
  passthrough behind the hook app entrypoint
- kept `.agent-factory/hooks/user-prompt-submit.py` as a compatibility wrapper
- preserved `_is_main_session` re-export for existing tests and compatibility
- added focused UserPromptSubmit app tests

Acceptance:

- UserPromptSubmit app and existing flow hook tests pass
- top-level `user-prompt-submit.py` workflow-session smoke passes
- full pytest passes

### M32: SubagentStop Hook App Entrypoint

Status: complete

Goal:

Move SubagentStop implementation into `engine/apps/hooks` while preserving
sentinel fail-record behavior and stable top-level hook paths.

Completed slice:

- added `engine/apps/hooks/subagent_stop.py`
- moved usage tracker dispatch, active workflow logging, and fail-record
  sentinel scanning behind the hook app entrypoint
- kept `.agent-factory/hooks/subagent-stop.py` as a compatibility wrapper
- preserved existing sentinel helper re-exports for compatibility tests
- added focused SubagentStop app tests

Acceptance:

- SubagentStop app and sentinel tests pass
- top-level `subagent-stop.py` smoke passes
- full pytest passes

### M33: PreToolUse Hook App Entrypoint

Status: complete

Goal:

Complete the current top-level hook thinning pass by moving PreToolUse guard
dispatch into `engine/apps/hooks`.

Completed slice:

- added `engine/apps/hooks/pre_tool_use.py`
- moved PreToolUse allow/deny routing, async Slack dispatch, guard ordering, and
  deny metrics recording behind the hook app entrypoint
- kept `.agent-factory/hooks/pre-tool-use.py` as a compatibility wrapper
- preserved `_record_tool_deny_metrics` re-export for compatibility
- added focused PreToolUse app tests

Acceptance:

- PreToolUse app and adapter hook tests pass
- top-level `pre-tool-use.py` smoke passes
- full pytest passes

### M34: Board API Observability App Boundary

Status: complete

Goal:

Introduce the missing `engine/apps/board_api` boundary with a low-risk shared
Board API helper extraction.

Completed slice:

- added `engine/apps/board_api`
- moved Board API `server_debug_log` and `api_endpoint` helper implementation
  into `engine/apps/board_api/observability.py`
- kept `board/server/_common.py` as the compatibility export surface for
  existing board handlers and contract tests
- updated timestamp emission to timezone-aware UTC
- added focused Board API app tests

Acceptance:

- Board API observability app tests pass
- existing `api_endpoint` contract tests pass through `_common.py`
- full pytest passes

### M35: Board Web Directory Move

Status: complete

Goal:

Align the board frontend asset tree with the target `board/web` layout.

Completed slice:

- moved board frontend assets from `board/static` to `board/web`
- updated `BoardHTTPRequestHandler` to serve `board/web`
- preserved old `/.agent-factory/board/static/*` URL compatibility in
  `translate_path`
- updated frontend path contract tests and refactor docs
- added board web static path contract tests

Acceptance:

- board web path contract tests pass
- board API smoke tests pass
- full pytest passes

### M36: Skill Mapper Test Canonicalization

Status: complete

Goal:

Remove the remaining tracked source-tree test file from `engine/flow`.

Completed slice:

- moved `engine/flow/test_skill_mapper.py` to
  `tests/application/flow/test_skill_mapper.py`
- updated the relocated test to import `flow.skill_mapper` through the engine
  package path
- confirmed no tracked `*test*` files remain under `engine/flow`

Acceptance:

- relocated skill mapper tests pass
- full pytest passes

### M37: Memory GC Board API App Handler

Status: complete

Goal:

Continue moving board API handler implementations into `engine/apps/board_api`
with a small, low-risk endpoint group.

Completed slice:

- moved Memory GC Board API handler implementation to
  `engine/apps/board_api/memory_gc.py`
- kept `board/server/handlers/memory_gc.py` as a compatibility export
- updated board API static analysis to scan app-boundary handlers as well as
  legacy board handler modules
- added focused Memory GC board API app tests

Acceptance:

- Memory GC board API app tests pass
- board API handler/router contract tests pass
- full pytest passes

### M38: Sync Board API App Handler

Status: complete

Goal:

Continue moving Board API handler implementations from `board/server/handlers`
into `engine/apps/board_api`.

Completed slice:

- moved Sync handler implementation to `engine/apps/board_api/sync.py`
- kept `board/server/handlers/sync.py` as a compatibility export
- updated restart entrypoint resolution to use the project root instead of the
  moved module path
- added focused Sync board API app tests

Acceptance:

- Sync board API app tests pass
- board API handler/router contract tests pass
- full pytest passes

### M39: Settings Board API App Handler

Status: complete

Goal:

Continue the Board API handler migration by moving the settings workflow-sync
handler into `engine/apps/board_api`.

Completed slice:

- moved Settings handler implementation to `engine/apps/board_api/settings.py`
- kept `board/server/handlers/settings.py` as a compatibility export
- added focused Settings board API app tests

Acceptance:

- Settings board API app tests pass
- board API handler/router contract tests pass
- full pytest passes

### M40: Ops Board API App Handler

Status: complete

Goal:

Move the operator diagnostics/recovery endpoints into `engine/apps/board_api`.

Completed slice:

- moved Ops handler implementation to `engine/apps/board_api/ops_endpoints.py`
- kept `board/server/handlers/ops_endpoints.py` as a compatibility export
- updated Ops endpoint contract tests to inspect the app-boundary handler
- added focused Ops board API app tests

Acceptance:

- Ops board API app tests pass
- Ops endpoint contract tests pass
- board API handler/router contract tests pass
- full pytest passes

### M41: Worktree Commit Board API App Handler

Status: complete

Goal:

Move the worktree commit endpoint group into `engine/apps/board_api`.

Completed slice:

- moved Worktree Commit handler implementation to
  `engine/apps/board_api/worktree_commit.py`
- kept `board/server/handlers/worktree_commit.py` as a compatibility export
- added focused Worktree Commit board API app tests

Acceptance:

- Worktree Commit board API app tests pass
- board API handler/router contract tests pass
- full pytest passes

### M42: Metrics Board API App Handler

Status: complete

Goal:

Move Metrics endpoint handlers into `engine/apps/board_api` and keep contract
tests aware of the app-boundary handler location.

Completed slice:

- moved Metrics handler implementation to `engine/apps/board_api/metrics.py`
- kept `board/server/handlers/metrics.py` as a compatibility export
- updated Metrics launch latency fallback to use the board server working
  directory after the module move
- updated API docstring/decorator coverage tests to scan `engine/apps/board_api`
- added focused Metrics board API app tests

Acceptance:

- Metrics board API app tests pass
- board API docstring/decorator and handler/router contract tests pass
- full pytest passes

### M43: Files Board API App Handler

Status: complete

Goal:

Move memory/rules/prompt file write/delete endpoints into
`engine/apps/board_api`.

Completed slice:

- moved Files handler implementation to `engine/apps/board_api/files.py`
- kept `board/server/handlers/files.py` as a compatibility export
- added focused Files board API app tests

Acceptance:

- Files board API app tests pass
- board API docstring/decorator and handler/router contract tests pass
- full pytest passes

### M44: Generic Board API App Handler

Status: complete

Goal:

Move generic API dispatch, poll, and SSE handlers into `engine/apps/board_api`.

Completed slice:

- moved Generic handler implementation to `engine/apps/board_api/generic.py`
- kept `board/server/handlers/generic.py` as a compatibility export
- updated direct static contract coverage to inspect the app-boundary generic
  handler
- added focused Generic board API app tests

Acceptance:

- Generic board API app tests pass
- board API docstring/decorator and handler/router contract tests pass
- full pytest passes

### M45: Board API Handler Common App Helper

Status: complete

Goal:

Move shared Board API handler helper constants and lazy imports into
`engine/apps/board_api`.

Completed slice:

- moved `_handler_common.py` implementation to
  `engine/apps/board_api/handler_common.py`
- kept `board/server/handlers/_handler_common.py` as a compatibility export
- updated Metrics and Kanban handler imports to use the app-boundary helper
- added focused handler common app tests

Acceptance:

- handler common app tests pass
- board API handler/router contract tests pass
- full pytest passes

### M46: V2 Workflow Board API App Handler

Status: complete

Goal:

Move V2 workflow REST/SSE endpoint handlers into `engine/apps/board_api`.

Completed slice:

- moved V2 Workflow handler implementation to
  `engine/apps/board_api/v2_workflow.py`
- kept `board/server/handlers/v2_workflow.py` as a compatibility export
- updated V2 workflow static contract tests to inspect the app-boundary handler
- added focused V2 Workflow board API app tests

Acceptance:

- V2 Workflow board API app tests pass
- V2 workflow endpoint contract tests pass
- board API handler/router contract tests pass
- full pytest passes

### M47: Kanban Done Board API App Helpers

Status: complete

Goal:

Move Kanban done helper implementation and done/undo parsing compatibility
exports into `engine/apps/board_api`.

Completed slice:

- moved Kanban done helper implementation to
  `engine/apps/board_api/kanban_done_helpers.py`
- moved Kanban done/undo parsing compatibility exports to
  `engine/apps/board_api/kanban_done_re.py`
- kept `board/server/handlers/_kanban_done_helpers.py` and
  `board/server/handlers/_kanban_done_re.py` as compatibility exports
- updated Kanban handler imports to use the app-boundary helpers
- updated focused tests to patch and inspect the app-boundary modules

Acceptance:

- Kanban done helper app tests pass
- Kanban done handler regression tests pass
- board API handler/router contract tests pass
- full pytest passes

### M48: Terminal Board API App Handler

Status: complete

Goal:

Move Terminal REST/SSE endpoint handlers into `engine/apps/board_api`.

Completed slice:

- moved Terminal handler implementation to
  `engine/apps/board_api/terminal.py`
- kept `board/server/handlers/terminal.py` as a compatibility export
- updated Terminal handler imports to use absolute board server dependencies
- added focused Terminal board API app tests

Acceptance:

- Terminal board API app tests pass
- board API docstring/decorator and handler/router contract tests pass
- full pytest passes

### M49: Kanban Board API App Handler

Status: complete

Goal:

Move Kanban REST endpoint handlers into `engine/apps/board_api`.

Completed slice:

- moved Kanban handler implementation to `engine/apps/board_api/kanban.py`
- kept `board/server/handlers/kanban.py` as a compatibility export
- preserved the `_emit_launch_event` lazy import path used by `v2_launcher`
- updated Kanban handler imports to use absolute board server dependencies
- added focused Kanban board API app tests

Acceptance:

- Kanban board API app tests pass
- Kanban workrequest/audit/done regression tests pass
- board API docstring/decorator and handler/router contract tests pass
- full pytest passes

### M50: Board API Runtime Import Alignment

Status: complete

Goal:

Make the active board runtime depend directly on `engine/apps/board_api` instead
of compatibility handler modules.

Completed slice:

- updated `board/server/http_router.py` to compose app-boundary Board API mixins
  directly
- updated `board/server/v2_launcher.py` to lazy import Kanban launch events from
  `engine.apps.board_api.kanban`
- kept `board/server/handlers` as compatibility exports for older import paths
- added focused router import boundary tests
- updated the layout gap analysis to mark Board API as aligned

Acceptance:

- router import boundary tests pass
- board API handler/router and V2 launch contract tests pass
- full pytest passes

### M51: Git Config Adapter Placement

Status: complete

Goal:

Move the Git config CLI implementation into the Git adapter boundary.

Completed slice:

- moved `engine/git/git_config.py` implementation to
  `engine/adapters/git/config.py`
- kept `engine/git/git_config.py` as a compatibility wrapper
- updated `bin/flow-gitconfig` to execute the adapter implementation directly
- adjusted adapter-local path resolution for `.agent-factory/.settings`
- added focused Git config adapter tests

Acceptance:

- Git config adapter tests pass
- `flow-gitconfig --help` works from the repo root
- full pytest passes

### M52: Remove Legacy Engine Git Wrapper

Status: complete

Goal:

Remove the last tracked `engine/git` source after `flow-gitconfig` moved to the
Git adapter boundary.

Completed slice:

- removed the temporary `engine/git/git_config.py` compatibility wrapper
- updated Git config adapter tests to use the canonical adapter module only
- added an architecture check that prevents the legacy source path from
  returning
- updated Worktree/Git gap analysis to remove `engine/git`

Acceptance:

- Git config adapter tests pass
- layout convergence architecture test passes
- full pytest passes

### M53: Move Hook Helper Scripts Into Hook Apps

Status: complete

Goal:

Remove the legacy `engine/hook-handlers` source directory by moving its helper
scripts into `engine/apps/hooks`.

Completed slice:

- moved `ensure_bin_path.sh` to `engine/apps/hooks/ensure_bin_path.sh`
- moved `inject_kanban_context.py` to
  `engine/apps/hooks/inject_kanban_context.py`
- updated SessionStart and UserPromptSubmit dispatch paths
- adjusted helper path calculations for the new app location
- updated hook tests to load and assert the app-boundary helper paths
- extended layout convergence tests to prevent the legacy source paths from
  returning

Acceptance:

- hook app tests pass
- UserPromptSubmit context tests pass
- layout convergence architecture test passes
- full pytest passes

### M54: Remove Legacy Engine Data Symlink

Status: complete

Goal:

Remove the unused legacy `engine/data/colors.sh` tracked symlink.

Completed slice:

- removed the broken `engine/data/colors.sh` symlink
- added a layout convergence architecture check preventing it from returning

Acceptance:

- layout convergence architecture test passes
- full pytest passes

### M55: Move LLM Contract To Core Port

Status: complete

Goal:

Place the provider-independent LLM contract under the target `core/ports`
boundary.

Completed slice:

- moved `engine/application/llm.py` implementation to
  `engine/core/ports/llm.py`
- added `engine/core/ports/__init__.py`
- kept `engine/application/llm.py` as a compatibility export
- updated LLM adapters and orchestration handler imports to use the core port
- added focused core port tests

Acceptance:

- core LLM port tests pass
- LLM adapter and orchestration tests pass
- full pytest passes

### M56: Move Claude Edit CLI Into Apps

Status: complete

Goal:

Move the `flow-claude-edit` implementation out of the engine root and into the
CLI app boundary.

Completed slice:

- moved `engine/claude_edit.py` to `engine/apps/cli/claude_edit.py`
- updated `bin/flow-claude-edit` to execute the app CLI implementation
- adjusted project path resolution for the new CLI location
- updated direct path guard coverage to block direct execution of the new
  implementation path
- added focused CLI placement tests
- extended layout convergence tests to prevent the legacy root source from
  returning

Acceptance:

- CLI placement tests pass
- direct path guard tests pass
- `flow-claude-edit` executes from the repo root
- full pytest passes

### M57: Move Statusline Into Hook Apps

Status: complete

Goal:

Move the Claude statusline implementation out of the engine root and into the
hook app boundary.

Completed slice:

- moved `engine/statusline.py` to `engine/apps/hooks/statusline.py`
- updated `.claude/settings.json` to execute the new statusline path
- adjusted direct script execution to add `.agent-factory` to `sys.path`
- updated direct path guard coverage for the new implementation path
- added focused statusline hook app tests
- extended layout convergence tests to prevent the legacy root source from
  returning

Acceptance:

- statusline hook app tests pass
- statusline command executes from the repo root
- direct path guard tests pass
- full pytest passes

### M58: Move Slack Integration Into Adapter Boundary

Status: complete

Goal:

Move Slack integration scripts out of the engine root and into
`engine/adapters/slack`.

Completed slice:

- moved `engine/slack/slack_ask.py` to `engine/adapters/slack/slack_ask.py`
- moved `engine/slack/slack_notify.py` to
  `engine/adapters/slack/slack_notify.py`
- moved `engine/slack/slack_common.py` to
  `engine/adapters/slack/slack_common.py`
- added `engine/adapters/slack/__init__.py`
- updated PreToolUse Slack dispatch to use the adapter path
- updated Slack scripts to import through `engine.adapters.slack`
- added focused Slack adapter placement tests
- extended layout convergence tests to prevent legacy Slack paths from
  returning

Acceptance:

- Slack adapter placement tests pass
- PreToolUse dispatch tests pass
- full pytest passes

### M59: Move Sync Scripts Into Adapter Boundary

Status: complete

Goal:

Move sync helper scripts out of the engine root and into
`engine/adapters/sync`.

Completed slice:

- moved `engine/sync/catalog_sync.py` to
  `engine/adapters/sync/catalog_sync.py`
- moved `engine/sync/history_sync.py` to
  `engine/adapters/sync/history_sync.py`
- moved `engine/sync/usage_sync.py` to `engine/adapters/sync/usage_sync.py`
- added `engine/adapters/sync/__init__.py`
- updated PostToolUse and SubagentStop dispatch paths
- updated sync scripts to import through `engine.*` from the adapter location
- updated chained history-sync guard compatibility for the new path
- added focused sync adapter placement tests
- extended layout convergence tests to prevent legacy sync paths from returning

Acceptance:

- sync adapter placement tests pass
- hook app dispatch tests pass
- sync scripts execute from the repo root
- full pytest passes

### M60: Remove Application LLM Compatibility Wrapper

Status: complete

Goal:

Remove the temporary `engine/application/llm.py` compatibility wrapper after the
LLM contract moved to `engine/core/ports`.

Completed slice:

- removed `engine/application/llm.py`
- updated LLM adapter and orchestration tests to import from
  `engine.core.ports.llm`
- updated core port tests to assert the legacy wrapper is absent
- extended layout convergence tests to prevent the wrapper from returning

Acceptance:

- LLM port, adapter, and orchestration tests pass
- layout convergence architecture test passes
- full pytest passes

## Verification Baseline

Current baseline:

```text
python3 -m pytest  # 814 passed, 2 skipped, 6 subtests passed
```
