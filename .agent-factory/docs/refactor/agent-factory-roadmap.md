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

Status: in progress

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
321 passed, 2 skipped
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
321 passed, 2 skipped
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
python3 -m pytest                         # 321 passed, 2 skipped
bash .agent-factory/build.sh              # all verification items passed
.agent-factory/bin/flow-wf submit --help  # exit 0
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
python3 -m pytest  # 328 passed, 2 skipped
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

Status: planned

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

### M7: Codex Main Brain

Status: planned

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

### M8: Board UI/UX Redesign

Status: planned

Purpose:

Make the UI match the new product model.

Target areas:

- WorkRequests
- Runs
- Verification
- Reports
- Settings

Tasks:

- rename UI language: Ticket -> WorkRequest, Work -> Execute, Validate -> Verify, Done -> Complete
- build WorkRequest authoring/refinement view
- build six-stage run timeline
- show adapter/provider status
- show verification verdicts with clear actions
- connect report review to completion

Acceptance criteria:

- operator can create/refine/accept a WorkRequest
- operator can watch a run through all six stages
- operator can inspect failures and choose retry/close actions
- UI does not expose Claude-specific terms unless viewing ClaudeAdapter details

### M9: Verification And Reporting Upgrade

Status: planned

Purpose:

Make completion defensible.

Tasks:

- split deterministic artifact verification from semantic evaluation
- add rule-gate registry
- add code check result model
- add final verdict model
- produce consistent report artifacts
- connect verification failures to WorkRequest refinement where appropriate

Acceptance criteria:

- VERIFY stage produces structured verdict data
- REPORT stage consumes verdict data
- COMPLETE stage cannot pass if blocking gates fail
- report links request, plan, artifacts, checks, and final decision

### M10: Cleanup And Hardening

Status: planned

Purpose:

Remove migration leftovers and make the factory maintainable.

Tasks:

- delete V1 compatibility shims
- delete stale docs and wrappers
- remove old Claude-centric naming from core
- add architecture boundary checks
- add docs index for `.agent-factory`
- add release/migration notes

Acceptance criteria:

- no V1 test/doc path remains as active guidance
- no core module imports board handlers, subprocess, or provider-specific code
- docs describe `.agent-factory`, not `claude-workflow`
- canonical tests and smoke tests pass

## Execution Order

Recommended sequence:

```text
M0 -> M1 -> M2 -> M3 -> M4 -> M5 -> M6 -> M7 -> M8 -> M9 -> M10
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
