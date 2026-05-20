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
    apps/
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
| V2 driver | `engine/apps/cli`, `engine/v2` | `engine/apps/cli` + application/core services | partially aligned |
| Planning | `engine/v2/core`, `engine/v2/steps/plan.py` | `core/planning`, `application/planning` | not aligned |
| Validation | `engine/v2/_verify*.py`, `_validate.py`, `steps/validate.py` | `core/validation`, `application/validation` | not aligned |
| Reporting | `engine/v2/steps/report.py`, `engine/application/reporting`, `engine/core/reporting` | `core/reporting`, `application/reporting` | partially aligned |
| Worktree/Git | `engine/flow/worktree_manager.py`, `merge_pipeline.py`, `undo_done.py`, `engine/adapters/git`, `engine/core/worktrees`, `engine/git` | `core/worktrees`, `adapters/git` | partially aligned |
| Kanban CLI/service | `engine/flow/kanban*.py`, `engine/application/kanban` | `application`/`apps/cli` + adapters | partially aligned |
| Board API | `board/server/handlers`, `engine/application/kanban` | `engine/apps/board_api` or thin board handlers | partially aligned |
| Board web | `board/static` | `board/web` | not aligned |
| Hooks | top-level `hooks/`, `engine/apps/hooks`, `engine/adapters/hooks`, `engine/guards` | `engine/apps/hooks`, `adapters/hooks` | partially aligned |
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

## Verification Baseline

Current baseline:

```text
python3 -m pytest  # 731 passed, 2 skipped, 6 subtests passed
```
