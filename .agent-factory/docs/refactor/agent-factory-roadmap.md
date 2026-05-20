# Agent Factory Roadmap

## North Star

`.agent-factory` exists to close the semantic gap between human intent and AI
execution.

It does this by:

1. turning vague intent into a high-quality `WorkRequest`
2. refining the request with an Ouroboros loop
3. executing the accepted request through Harness Engineering
4. using interchangeable `LLMAdapter` providers
5. verifying, reporting, and completing the work

## Product Pillars

### WorkRequest Engineering

Goal: make the 작업 요청서 good enough that both humans and AI understand the
same job.

Core loop:

```text
DRAFT -> CLARIFY -> CRITIQUE -> REWRITE -> ACCEPT
```

Outputs:

- intent
- context
- constraints
- acceptance criteria
- non-goals
- risk notes
- refinement history

### Harness Engineering

Goal: execute an accepted WorkRequest through a reliable production line.

Absolute workflow:

```text
PREPARE -> PLAN -> EXECUTE -> VERIFY -> REPORT -> COMPLETE
```

Responsibilities:

- orchestration
- retries and fail policy
- parallel execution
- isolation with worktrees and writable roots
- artifact management
- events, metrics, logs, run manifests

### LLM Adapter Layer

Goal: make the model/runtime replaceable.

Target:

```text
LLMAdapter
  -> CodexAdapter
  -> ClaudeAdapter
  -> GeminiAdapter
  -> FakeAdapter
```

Priority:

1. `FakeAdapter` for TDD
2. `CodexAdapter` as the main brain
3. `ClaudeAdapter` as migration compatibility
4. `GeminiAdapter` as follow-up

### Verification And Reporting

Goal: make outputs reviewable, repeatable, and safe to close.

Responsibilities:

- deterministic artifact checks
- code validation
- rule gates
- verdict generation
- final report
- complete/rollback/retry decisions

### UI/UX

Goal: make the factory usable by a human operator.

Key screens:

- WorkRequest authoring and Ouroboros refinement
- Run timeline: `PREPARE -> PLAN -> EXECUTE -> VERIFY -> REPORT -> COMPLETE`
- Adapter status: Codex/Claude/Gemini/Fake
- Verification verdicts and retry actions
- Report review and completion
- Run history, metrics, provider comparison

## Milestones

### M0: Baseline And Safety Rails

Status: done

Purpose:

Create a stable baseline so refactors do not fight stale V1 tests or unclear
architecture.

Deliverables:

- canonical pytest config
- V1 removal inventory
- DDD/TDD target architecture
- domain directory move map
- runtime root rename plan
- LLMAdapter plan
- `.repo` reference catalog

Acceptance criteria:

- `python3 -m pytest` passes from the current runtime root
- stale V1 tests are not part of default test collection
- roadmap documents agree on terminology

Current verification:

```text
python3 -m pytest  # 355 passed, 2 skipped
```

### M1: Test Consolidation

Status: done

Purpose:

Move from scattered test directories to one canonical test root.

Target layout:

```text
tests/
  domain/
  application/
  adapters/
  contracts/
  e2e/
```

Tasks:

- create canonical `tests/` root
- move green `engine/v2/tests` into domain/application/adapter buckets
- move `board/server/tests` into `tests/contracts/board_api`
- delete or rewrite V1-only tests
- remove stale `tests/__init__.py` package roots
- update `pytest.ini` to collect only `tests/`

Acceptance criteria:

- no pytest import collision
- `python3 -m pytest` passes
- old scattered test roots are gone or explicitly excluded with deletion notes

Current verification:

```text
python3 -m pytest  # 355 passed, 2 skipped
```

### M2: Runtime Root Rename

Status: done

Purpose:

Rename `.claude-organic/` to `.agent-factory/`.

Tasks:

- `git mv .claude-organic .agent-factory`
- update `.gitignore`
- update `init-claude-workflow.sh`
- update `.claude/settings.json`
- update wrapper paths and `PYTHONPATH`
- update build templates
- update Python constants and root discovery
- keep migration script support for old user data

Acceptance criteria:

- canonical tests pass from `.agent-factory`
- board server starts and writes `.agent-factory/.board.url`
- `flow-wf` wrapper smoke passes
- `flow-kanban` read-only smoke passes
- no application code searches both `.claude-organic` and `.agent-factory`

Current verification:

```text
python3 -m pytest                         # 355 passed, 2 skipped
bash .agent-factory/build.sh              # all verification items passed
.agent-factory/bin/flow-wf --help         # exit 0
.agent-factory/bin/flow-kanban list       # exit 0
curl -I $(head -1 .agent-factory/.board.url)  # HTTP 200
```

### M3: WorkRequest Domain

Status: done

Purpose:

Promote `Ticket` to the target domain concept `WorkRequest`.

Tasks:

- add `WorkRequest`, `WorkRequestRef`, `AcceptanceCriteria`, `RiskNote`
- add Ouroboros refinement model
- map current XML ticket storage to `WorkRequestStore`
- keep external `T-123` IDs during migration
- update board/API terminology where safe

Acceptance criteria:

- pure domain tests for WorkRequest authoring pass
- WorkRequest can round-trip through existing ticket storage
- accepted WorkRequest can start a WorkflowRun
- old `TicketRef` terminology is absent from new core code

Current verification:

```text
python3 -m pytest  # 355 passed, 2 skipped
```

### M4: Workflow Model

Status: done

Purpose:

Extract the absolute workflow model from V2 runtime code.

Target stages:

```text
PREPARE -> PLAN -> EXECUTE -> VERIFY -> REPORT -> COMPLETE
```

Tasks:

- add `WorkflowStage` enum
- add transition rules
- map V2 names:
  - `INIT` -> lifecycle / prepare runtime
  - `WORK` -> `EXECUTE`
  - `VALIDATE` -> `VERIFY`
  - `DONE` -> `COMPLETE`
- add `WorkflowRun` domain model
- keep existing V2 behavior through compatibility mapping

Acceptance criteria:

- domain tests prove the six-stage order is enforced
- orchestration cannot reorder stages
- V2 status files can still be read during migration

Current verification:

```text
python3 -m pytest tests/domain/workflows tests/application/v2/test_common.py
```

### M5: Orchestration And Harness Engineering

Status: done

Purpose:

Separate workflow model from runtime orchestration.

Tasks:

- extract `orchestration/service.py`
- extract retry policy
- extract scheduler/parallel execution
- extract lifecycle events
- add run manifest
- separate artifact store from workflow rules

Acceptance criteria:

- application tests use fake ports
- orchestration executes six stages in order
- retry and fail policy are tested without real LLM calls
- artifacts are indexed in a run manifest

Current verification:

```text
python3 -m pytest tests/application/orchestration tests/domain/workflows tests/domain/work_requests
```

### M6: LLMAdapter Foundation

Status: done

Purpose:

Introduce provider-independent execution.

Tasks:

- add `LLMAdapter` protocol
- add `LLMRequest`, `LLMResult`, `LLMEvent`
- add `FakeAdapter`
- wrap current Claude spawn logic as `ClaudeAdapter`
- inject adapter into PLAN/EXECUTE/REPORT application services

Acceptance criteria:

- application tests run with `FakeAdapter`
- no application service imports provider-specific adapter implementations
- existing Claude behavior still works through `ClaudeAdapter`

Current verification:

```text
python3 -m pytest tests/application/llm tests/application/orchestration tests/adapters/llm
```

### M7: Codex Main Brain

Status: done

Purpose:

Make Codex the primary provider.

Tasks:

- implement `CodexAdapter`
- add provider selection config
- add Codex smoke tests
- map Codex output/events to `LLMResult`
- document Codex runtime constraints

Acceptance criteria:

- `AGENT_FACTORY_LLM_PROVIDER=codex` selects Codex
- Codex can run at least PLAN or REPORT in a controlled smoke
- FakeAdapter remains the default in unit/application tests
- Claude is no longer hard-coded in orchestration

Current verification:

```text
python3 -m pytest tests/adapters/llm tests/application/llm tests/application/orchestration
```

### M8: Board UI/UX Redesign

Status: complete

Purpose:

Make the UI match the new product model.

Target areas:

- WorkRequests
- Runs
- Verification
- Reports
- Settings

Tasks:

- [x] rename top-level UI language: Ticket -> WorkRequest, Work -> Execute, Validate -> Verify, Done -> Complete
- [x] build WorkRequest authoring/refinement/acceptance surface backed by existing `flow-kanban`
- [x] build six-stage run timeline in run detail view
- [x] show adapter/provider status in Settings, with provider-specific terms isolated to adapter details
- [x] show verification verdicts with clearer retry/close actions
- [x] connect report review more explicitly to completion

Acceptance criteria:

- operator can create/refine/accept a WorkRequest
- operator can watch a run through all six stages
- operator can inspect failures and choose retry/close actions
- UI does not expose Claude-specific terms unless viewing ClaudeAdapter details

### M9: Verification And Reporting Upgrade

Status: complete

Purpose:

Make completion defensible.

Tasks:

- [x] split deterministic artifact verification from semantic evaluation
- [x] add rule-gate registry
- [x] add code check result model
- [x] add final verdict model
- [x] produce consistent report artifacts
- [x] connect verification failures to WorkRequest refinement where appropriate

Acceptance criteria:

- VERIFY stage produces structured verdict data
- REPORT stage consumes verdict data
- COMPLETE stage cannot pass if blocking gates fail
- report links request, plan, artifacts, checks, and final decision

### M10: Cleanup And Hardening

Status: complete

Purpose:

Remove migration leftovers and make the factory maintainable.

Tasks:

- [x] delete V1 compatibility shims
- [x] delete stale docs and wrappers
- [x] remove old Claude-centric naming from core
- [x] add architecture boundary checks
- [x] add docs index for `.agent-factory`
- [x] add release/migration notes

Acceptance criteria:

- no V1 test/doc path remains as active guidance
- no core module imports board handlers, subprocess, or provider-specific code
- docs describe `.agent-factory`, not `claude-workflow`
- canonical tests and smoke tests pass

Current verification:

```text
python3 -m pytest                         # 355 passed, 2 skipped
.agent-factory/bin/flow-wf --help         # exit 0
.agent-factory/bin/flow-kanban list       # exit 0
```

### M11: Runtime Contract Hardening

Status: complete

Purpose:

Close the remaining active-runtime contract drift after M10.

Tasks:

- [x] update direct-path guard detection to the current `.agent-factory/engine`
      layout
- [x] remove removed V1 wrapper suggestions from direct-path guard alias mapping
- [x] make link validation scan canonical `report.html` artifacts
- [x] teach link validation to ignore HTML fragment-only anchors
- [x] add focused contracts for the M11 runtime cleanup behavior

Acceptance criteria:

- direct `python3 .agent-factory/engine/...` calls are denied with a live
  `flow-*` wrapper suggestion when one exists
- removed wrappers such as `flow-init`, `flow-finish`, `flow-reload`, and
  `flow-recommend` are not recommended by active guards
- report artifact link validation targets `report.html`, not `report.md`
- canonical tests pass

Current verification:

```text
python3 -m pytest tests/contracts/board_api/test_m11_runtime_cleanup.py  # 5 passed
python3 -m pytest                                                        # 355 passed, 2 skipped
```

### M12: Layout Audit And Freeze

Status: complete

Purpose:

Reset the directory refactor plan against the actual M0-M11 codebase before
moving more files.

Tasks:

- [x] document current source layout
- [x] compare current layout with the target DDD layout
- [x] define early freeze list for wrappers, hooks, board assets, and runtime data
- [x] identify first safe move candidates
- [x] defer high-coupling moves until lower-risk boundaries are extracted

Acceptance criteria:

- no source files are moved in M12
- future milestones have a risk-ordered move sequence
- docs point to the M12 convergence plan
- canonical tests remain green

Current verification:

```text
python3 -m pytest  # 355 passed, 2 skipped
```

### M13: Validation Core Extraction

Status: complete

Purpose:

Start the post-M12 layout convergence by moving pure deterministic validation
rules out of the active V2 runtime package. The pure planning loader was moved
with this slice because core validation validates `plan.json` schema and the
architecture boundary forbids core modules from importing V2 runtime modules.

Tasks:

- [x] create `engine/core/validation`
- [x] move artifact validation rules into
      `engine/core/validation/artifact_rules.py`
- [x] keep `engine/v2/_verify.py` as a compatibility export surface
- [x] move pure plan loading into `engine/core/planning/loader.py`
- [x] keep `engine/v2/core/plan_loader.py` as a compatibility export surface
- [x] add direct domain coverage for the new core validation module
- [x] add direct domain coverage for the new core planning loader
- [x] leave coupled code checks, verdict writing, and validate-step orchestration
      in V2 for later slices

Acceptance criteria:

- core validation artifact rules can be imported without using the V2 `_verify`
  module
- existing V2 `_verify` imports continue to work
- existing V2 `core.plan_loader` imports continue to work
- PLAN, WORK, VALIDATE, REPORT artifact checks keep existing behavior
- core architecture tests still forbid core-to-V2 imports
- canonical tests pass

Current verification:

```text
python3 -m pytest tests/domain/validation tests/domain/planning tests/domain/v2/test_parse_plan_json.py tests/domain/v2/test_topo_levels.py tests/domain/v2/test_verify.py tests/adapters/v2/test_report_html_verify.py tests/application/v2/test_steps_work.py tests/application/v2/test_steps_validate.py tests/architecture/test_boundaries.py  # 72 passed
python3 -m pytest  # 361 passed, 2 skipped
```

### M14: Planning Loader Extraction

Status: complete

Purpose:

Finish the planning-loader portion that M13 pulled forward for architecture
reasons, and make `engine/core/planning` the canonical home for plan parsing
and topology rules.

Tasks:

- [x] migrate plan parser tests from `tests/domain/v2` to
      `tests/domain/planning`
- [x] migrate topology-level tests from `tests/domain/v2` to
      `tests/domain/planning`
- [x] update the V2 WORK step to import planning rules from
      `engine.core.planning.loader`
- [x] keep `engine/v2/core/plan_loader.py` as a compatibility export surface
- [x] add focused V2 compatibility tests for the old plan loader path

Acceptance criteria:

- core planning tests cover parse and topology behavior
- active runtime code prefers `engine.core.planning.loader`
- legacy `engine.v2.core.plan_loader` imports still resolve to the core objects
- architecture boundary tests pass
- canonical tests pass

Current verification:

```text
python3 -m pytest tests/domain/planning tests/domain/v2/test_plan_loader_compat.py tests/domain/v2/test_verify.py tests/application/v2/test_steps_work.py tests/architecture/test_boundaries.py  # 57 passed
python3 -m pytest  # 363 passed, 2 skipped
```

### M15: Reporting Service Extraction

Status: complete

Purpose:

Move report template ownership and deterministic REPORT prompt construction out
of the V2 runtime step while keeping the active REPORT driver stable.

Tasks:

- [x] move `report.html` template ownership to `engine/core/reporting`
- [x] keep `engine.v2._common.load_template("report.html")` compatibility
- [x] add `engine/application/reporting` prompt construction
- [x] update the V2 REPORT step to use the reporting application service
- [x] keep V2 responsible for runtime file reads, session setup, retry, spawn,
      verification, and manifest writing
- [x] add focused tests for core template loading and REPORT prompt construction

Acceptance criteria:

- report HTML template tests pass from the core reporting location
- REPORT prompt construction is covered without V2 runtime imports
- board workflow report artifact contracts continue to pass
- architecture boundary tests pass
- canonical tests pass

Current verification:

```text
python3 -m pytest tests/application/reporting tests/adapters/v2/test_report_html_verify.py tests/domain/validation/test_artifact_rules.py tests/application/v2/test_steps_done.py tests/contracts/board_api/test_workflow_report_artifacts.py tests/architecture/test_boundaries.py  # 24 passed
python3 -m pytest  # 366 passed, 2 skipped
```

### M16: Worktree/Git Boundary

Status: complete

Purpose:

Start separating git subprocess gateways from worktree domain decisions without
moving the active `flow-*` CLI contracts.

Tasks:

- [x] add `engine/adapters/git` as the git subprocess gateway
- [x] route `flow.worktree_manager._git` through the git adapter while keeping
      the old patchable helper for compatibility
- [x] add `engine/core/worktrees` for pure ticket, branch, path, and lock-path
      rules
- [x] update `worktree_manager` to use core worktree rules for ticket
      normalization and worktree path construction
- [x] keep `flow-merge` and `flow-kanban` wrappers stable
- [x] add focused adapter/domain tests for the new boundary

Acceptance criteria:

- git subprocess invocation is isolated behind `engine.adapters.git`
- worktree path decisions are covered in `engine.core.worktrees`
- existing worktree manager callers and patch-based tests can still use
  `flow.worktree_manager._git`
- `flow-merge --help` and `flow-kanban list` still run
- canonical tests pass

Current verification:

```text
python3 -m pytest tests/domain/worktrees tests/adapters/git tests/adapters/v2/test_init_work_dir.py tests/application/v2/test_steps_init.py tests/contracts/board_api/test_api_smoke.py tests/contracts/board_api/test_workflow_report_artifacts.py tests/architecture/test_boundaries.py  # 25 passed, 2 skipped
.agent-factory/bin/flow-merge --help  # exit 0
.agent-factory/bin/flow-kanban list   # exit 0
python3 -m pytest  # 370 passed, 2 skipped
```

### M17: Kanban And Board API Boundary

Status: complete

Purpose:

Start thinning board kanban handlers by moving command-output decision logic into
the application layer while leaving HTTP handlers and subprocess execution
stable.

Tasks:

- [x] add `engine/application/kanban`
- [x] move `flow-kanban done` failure classification into
      `engine/application/kanban/done_result.py`
- [x] move `flow-undo-done` stdout regex ownership into the same application
      service
- [x] keep `board/server/handlers/_kanban_done_re.py` as a compatibility export
      module for existing board helper imports
- [x] add focused application tests for done/undo output parsing
- [x] keep `flow-kanban` and board API contracts stable

Acceptance criteria:

- kanban done/undo parsing is covered outside board handlers
- board handler imports remain compatible
- board API contract tests pass
- `flow-kanban list` passes
- canonical tests pass

Current verification:

```text
python3 -m pytest tests/application/kanban tests/contracts/board_api tests/architecture/test_boundaries.py  # 78 passed, 2 skipped
python3 -m pytest engine/flow/tests/test_kanban_done_handler.py  # 5 passed
.agent-factory/bin/flow-kanban list  # exit 0
python3 -m pytest  # 375 passed, 2 skipped
```

### M18: Workflow Session Persist Cleanup

Status: complete

Purpose:

Stop using root-level workflow session caches and make V2 history follow the
run-local artifact model.

Tasks:

- [x] move default V2 workflow event persistence to
      `runs/<registry>/workflow-events.jsonl`
- [x] stop board startup from creating `.agent-factory/.workflow-sessions-v2`
- [x] stop board startup from creating `.agent-factory/.workflow-sessions`
- [x] keep explicit `persist_dir` support for tests and legacy registry
      construction
- [x] keep V2 history endpoint behavior backed by `session.channel.persist_path`
- [x] ignore `.agent-factory/.workflow-sessions-v2/` if old local data exists
- [x] add contract coverage for run-local V2 history persistence

Acceptance criteria:

- new V2 sessions do not require `.agent-factory/.workflow-sessions-v2`
- board startup does not recreate root `.workflow-sessions*` directories
- V2 history endpoint tests still pass
- V2 workflow session registry tests still pass
- canonical tests pass

Current verification:

```text
python3 -m pytest tests/contracts/board_api/test_v2_history_endpoint.py tests/contracts/board_api/test_v2_endpoints.py tests/contracts/board_api/test_api_smoke.py  # 21 passed, 2 skipped
python3 -m pytest board/tests/test_v2_workflow_phase1.py  # 28 passed
python3 -m pytest  # 378 passed, 2 skipped
```

### M19: Hooks Boundary

Status: complete

Purpose:

Clarify `.agent-factory/hooks` as stable Claude Code entrypoint scripts while
moving shared hook dispatcher behavior into the adapter layer.

Tasks:

- [x] add `engine/adapters/hooks/dispatcher.py`
- [x] keep `.agent-factory/hooks/dispatcher.py` as a compatibility export
      module for current hook entrypoint imports
- [x] preserve top-level hook script paths for Claude Code settings
- [x] cover hook flag parsing, script path resolution, dispatch result
      aggregation, and wrapper exports with adapter tests

Acceptance criteria:

- hook dispatcher adapter tests pass
- architecture boundary tests pass
- top-level pre-tool-use hook smoke passes
- canonical tests pass

Current verification:

```text
python3 -m pytest tests/adapters/hooks/test_dispatcher.py  # 6 passed
printf '{"hook_event_name":"PreToolUse","tool_name":"Read","tool_input":{}}' | python3 .agent-factory/hooks/pre-tool-use.py  # exit 0
python3 -m pytest tests/architecture/test_boundaries.py  # 2 passed
python3 -m pytest  # 384 passed, 2 skipped
```

### M20: Naming And Rebranding

Status: complete

Purpose:

Make Agent Factory the active product/runtime name while keeping provider names
only at explicit provider or integration boundaries.

Tasks:

- [x] add active naming policy documentation
- [x] link the naming policy from the documentation index
- [x] rename residual `organic` test bootstrap symbols to Agent Factory terms
- [x] change the standalone board title to `Agent Factory Terminal`
- [x] change board stylesheet headers from Claude-branded dashboard labels to
      Agent Factory labels
- [x] keep Claude names in provider adapters, `.claude/` integration surfaces,
      Claude Code hook descriptions, and historical migration records

Acceptance criteria:

- active documentation points to Agent Factory naming rules
- no active test bootstrap uses `organic` naming for `.agent-factory`
- board standalone terminal title uses Agent Factory naming
- canonical tests pass

Current verification:

```text
python3 -m pytest tests/contracts/board_api/test_api_endpoint_helper.py  # 5 passed
python3 -m pytest board/tests/test_v2_launcher.py board/tests/test_kanban_audit_verdict.py board/tests/test_v2_workflow_phase1.py  # 60 passed
python3 -m pytest  # 384 passed, 2 skipped
```

## Execution Order

Recommended sequence:

```text
M0 -> M1 -> M2 -> M3 -> M4 -> M5 -> M6 -> M7 -> M8 -> M9 -> M10 -> M11 -> M12 -> M13 -> M14 -> M15 -> M16 -> M17 -> M18 -> M19 -> M20
```

Hard dependencies:

- M1 before M2/M3 source moves
- M2 before broad path-sensitive refactors
- M3 before UI terminology redesign
- M4 before orchestration extraction
- M6 before Codex as main brain
- M8 after core vocabulary is stable

## First Implementation Slice

Start with M1:

1. create canonical `tests/`
2. move only green tests
3. delete or quarantine V1-only tests
4. update `pytest.ini`
5. run canonical tests

Do not rename `.claude-organic` or move source files until M1 is done.
