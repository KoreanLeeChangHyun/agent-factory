# Domain Directory Restructure

## Purpose

The current code is organized mostly by historical location:

- `engine/apps/production_line`
- `engine/flow`
- `board/server`
- `board/web`
- `hooks`

That layout hides the real domains. The target layout should make the harness
easy for LLMs and humans to navigate by business responsibility.

This document is the file-move map. Do not perform broad moves until the
canonical tests are green and stale V1 tests are removed.

## Absolute Workflow Model

The core workflow has six mandatory stages:

```text
PREPARE -> PLAN -> EXECUTE -> VERIFY -> REPORT -> COMPLETE
```

Korean labels:

```text
작업 준비 -> 작업 계획 -> 작업 수행 -> 작업 검증 -> 작업 보고 -> 작업 완료
```

This order is not an orchestration choice. It is the domain model.

`DONE` in the current Production-line code maps to the target `COMPLETE` stage. Runtime
lifecycle events such as `INIT`, `FAILED`, cancellation, retry, parallel
execution, and provider selection belong to orchestration/application code, not
to the workflow stage model.

## Work Request Model

`Ticket` is the current storage/UI term. The target domain term is
`WorkRequest`:

```text
WorkRequest = 작업 요청서
WorkflowRun = 작업 요청서를 처리하는 1회 실행
```

Work request authoring uses an Ouroboros loop before orchestration starts:

```text
DRAFT -> CLARIFY -> CRITIQUE -> REWRITE -> ACCEPT
```

This loop improves the request until it has enough intent, context, constraints,
and acceptance criteria to enter the absolute workflow.

## Domain Inventory

| Domain | Current Files | Responsibility |
|---|---|---|
| Work Request | `engine/flow/ticket_repository.py`, `engine/flow/kanban*.py`, `board/server/handlers/kanban.py`, `board/board_data.py` | 작업 요청서, Ouroboros refinement, kanban/request state |
| Workflow Model | `engine/apps/production_line/_common.py`, `engine/apps/production_line/driver.py`, `engine/apps/production_line/steps/*` | Absolute stage model, run metadata, stage transition invariants |
| Orchestration | `engine/apps/production_line/driver.py`, `engine/apps/production_line/steps/*`, `engine/apps/production_line/_retry.py`, `engine/apps/production_line/_parallel.py` | Runtime coordination, retry, adapter invocation, lifecycle events |
| Planning | `engine/apps/production_line/core/plan_loader.py`, `engine/apps/production_line/steps/plan.py`, `engine/apps/production_line/prompts/plan.txt` | Plan schema, phase graph, PLAN generation |
| Work Execution | `engine/apps/production_line/steps/work.py`, `engine/apps/production_line/_parallel.py`, `engine/apps/production_line/_retry.py` | Phase scheduling, worker execution, retries |
| LLM Runtime | `engine/apps/production_line/_spawn.py` | Claude subprocess execution, session IDs, stream parsing |
| Validation | `engine/apps/production_line/_verify.py`, `engine/apps/production_line/_verify_code.py`, `engine/apps/production_line/_validate.py`, `engine/apps/production_line/steps/validate.py` | Artifact checks, code checks, verdict rules |
| Reporting | `engine/apps/production_line/steps/report.py`, `engine/apps/production_line/templates/report.html` | REPORT artifact generation |
| Kanban | `engine/flow/kanban*.py`, `board/server/handlers/kanban.py`, `board/board_data.py` | Request board state and board-facing operations |
| Worktree/Git | `engine/flow/worktree_manager.py`, `engine/flow/merge_pipeline.py`, `engine/flow/undo_done.py`, `engine/git/git_config.py`, `board/server/handlers/worktree_commit.py` | Feature branches, commits, merge/undo workflows |
| Events/Sessions | `engine/apps/production_line/_emitter.py`, `board/server/production_line_workflow_session.py`, `board/server/production_line_sse_channel.py`, `board/server/sse_client_manager.py`, `board/server/poll_tracker.py` | Workflow sessions, event streams, SSE fan-out |
| Board API | `board/server/http_router.py`, `board/server/handlers/*` | HTTP routing and JSON contracts |
| Terminal | `board/server/claude_process.py`, `board/server/terminal_channel.py`, `board/server/handlers/terminal.py`, `board/web/js/terminal/*` | Interactive terminal process and UI |
| Hooks | `hooks/*.py`, `engine/hook-handlers/*`, `engine/guards/*` | Claude Code hook payloads, guards, prompt injection |
| Memory | `engine/memory_gc/*`, `board/server/handlers/memory_gc.py`, `board/web/js/memory/*` | Memory pruning, reflection, UI |
| Settings/Sync | `engine/flow/env_manager.py`, `engine/sync/*`, `board/server/handlers/settings.py`, `board/server/handlers/sync.py` | Runtime settings, dashboard sync |
| Skills/Project Detection | `engine/flow/project_skill_detector.py`, `engine/flow/skill_*.py`, `engine/flow/inject_prompt.py` | Skill activation and prompt context |
| Metrics/History | `engine/flow/metrics*.py`, `engine/flow/usage_tracker.py`, `board/server/handlers/metrics.py`, `board/web/js/views/_deprecated/metrics.js` | Metrics JSONL, usage/history surfaces |

## Target Layout

```text
.agent-factory/
  engine/
    core/
      workflow/
        domain.py
        stages.py
        run_store.py
      orchestration/
        service.py
        retry.py
        scheduler.py
        lifecycle.py
      planning/
        domain.py
        loader.py
        service.py
      execution/
        result.py
      validation/
        artifact_rules.py
        code_checks.py
        verdict.py
      reporting/
        service.py
        templates/
      work_requests/
        domain.py
        ouroboros.py
        repository.py
      kanban/
        domain.py
        kanban_service.py
      worktrees/
        service.py
        merge.py
        git.py
      events/
        event.py
        emitter.py
        session.py
      ports/
        llm_adapter.py
        work_request_store.py
        artifact_store.py
        event_bus.py
        worktree_gateway.py
    adapters/
      llm/
        claude.py
        codex.py
        gemini.py
        fake.py
      claude/
        hooks.py
        terminal.py
      filesystem/
        artifacts.py
        run_store.py
        settings.py
      git/
        worktree_gateway.py
      board/
        event_bus.py
      kanban/
        xml_work_request_store.py
    apps/
      workflow_driver.py
      cli/
        flow_wf.py
        flow_kanban.py
        flow_merge.py
        flow_validate.py
      board_api/
        router.py
        handlers/
      hooks/
        pre_tool_use.py
        post_tool_use.py
        session_start.py
        subagent_stop.py
        user_prompt_submit.py
    memory/
      ...
    integrations/
      slack/
    tests/  # removed after top-level tests/ migration
  board/
    web/
      core/
      terminal/
      workflow/
      kanban/
      memory/
      settings/
      vendor/
  tests/
    domain/
    application/
    adapters/
    contracts/
    e2e/
```

## Move Map

### Workflow Core

| Current | Target |
|---|---|
| `engine/apps/production_line/_common.py::WorkflowContext` | `engine/core/workflow/domain.py` |
| Production-line step names `INIT/PLAN/WORK/VALIDATE/REPORT/DONE` | target model `PREPARE/PLAN/EXECUTE/VERIFY/REPORT/COMPLETE` plus lifecycle events |
| `engine/apps/production_line/_common.py::read_status/write_status/update_step` | `engine/core/workflow/run_store.py` initially, then filesystem adapter |
| `engine/apps/production_line/driver.py` | `engine/core/orchestration/service.py` plus `engine/apps/workflow_cli.py` |
| `engine/apps/production_line/steps/init.py` | `engine/core/orchestration/lifecycle.py` and `PREPARE` service |
| `engine/apps/production_line/steps/done.py` | `engine/core/orchestration/lifecycle.py` |

### Planning

| Current | Target |
|---|---|
| `engine/apps/production_line/core/plan_loader.py` | `engine/core/planning/loader.py` and `domain.py` |
| `engine/apps/production_line/steps/plan.py` | `engine/core/planning/service.py` |
| `engine/apps/production_line/prompts/plan.txt` | `engine/core/planning/prompts/plan.txt` or prompt adapter |

### Execution

| Current | Target |
|---|---|
| `engine/apps/production_line/steps/work.py` | `engine/core/orchestration/scheduler.py` plus `engine/core/execution/result.py` |
| `engine/apps/production_line/_parallel.py` | `engine/core/orchestration/scheduler.py` |
| `engine/apps/production_line/_retry.py` | `engine/core/orchestration/retry.py` |
| `engine/apps/production_line/_spawn.py` | `engine/adapters/llm/claude.py` behind `ports/llm_adapter.py` |

### Validation

| Current | Target |
|---|---|
| `engine/apps/production_line/_verify.py` | `engine/core/validation/artifact_rules.py` |
| `engine/apps/production_line/_verify_code.py` | split: `engine/core/validation/code_checks.py` + tool adapter |
| `engine/apps/production_line/_validate.py` | `engine/core/validation/verdict.py` |
| `engine/apps/production_line/steps/validate.py` | `engine/core/validation/service.py` |

### Reporting

| Current | Target |
|---|---|
| `engine/apps/production_line/steps/report.py` | `engine/core/reporting/service.py` |
| `engine/apps/production_line/templates/report.html` | `engine/core/reporting/templates/report.html` |

### Work Requests And Kanban

| Current | Target |
|---|---|
| `engine/flow/ticket_repository.py` | `engine/core/work_requests/repository.py` or `adapters/kanban/xml_work_request_store.py` |
| `engine/flow/kanban.py` | `engine/apps/cli/flow_kanban.py` |
| `engine/flow/kanban_cli.py` | `engine/core/kanban/kanban_service.py` plus CLI wrapper |
| `board/server/handlers/kanban.py` | `engine/apps/board_api/handlers/kanban.py` |
| `board/board_data.py` ticket readers | `engine/adapters/kanban/xml_work_request_store.py` |

### Worktree And Git

| Current | Target |
|---|---|
| `engine/flow/worktree_manager.py` | `engine/adapters/git/worktree_gateway.py` |
| `engine/flow/merge_pipeline.py` | `engine/core/worktrees/merge.py` plus git adapter |
| `engine/flow/undo_done.py` | `engine/core/worktrees/undo.py` |
| `engine/git/git_config.py` | `engine/adapters/git/config.py` |
| `board/server/handlers/worktree_commit.py` | `engine/apps/board_api/handlers/worktree_commit.py` |

### Events And Sessions

| Current | Target |
|---|---|
| `engine/apps/production_line/_emitter.py` | `engine/core/events/emitter.py` with board adapter |
| `board/server/production_line_workflow_session.py` | `engine/core/events/session.py` plus filesystem adapter |
| `board/server/production_line_sse_channel.py` | `engine/adapters/board/sse.py` |
| `board/server/sse_client_manager.py` | `engine/adapters/board/sse.py` |
| `board/server/poll_tracker.py` | `engine/adapters/board/polling.py` |

### Board API

| Current | Target |
|---|---|
| `board/server/http_router.py` | `engine/apps/board_api/router.py` |
| `board/server/handlers/*.py` | `engine/apps/board_api/handlers/*.py` |
| `board/server/app.py` | `engine/apps/board_api/server.py` |
| `board/server/_common.py` | split into `board_api/http.py`, `events`, `settings` |

### Terminal

| Current | Target |
|---|---|
| `board/server/claude_process.py` | `engine/adapters/claude/terminal.py` |
| `board/server/terminal_channel.py` | `engine/apps/board_api/terminal_channel.py` initially, then adapter |
| `board/server/handlers/terminal.py` | `engine/apps/board_api/handlers/terminal.py` |
| `board/web/js/terminal/*` | `board/web/terminal/*` |

### Hooks And Guards

| Current | Target |
|---|---|
| `hooks/*.py` | `engine/apps/hooks/*.py` |
| `hooks/dispatcher.py` | `engine/apps/hooks/dispatcher.py` |
| `engine/guards/*.py` | `engine/adapters/claude/guards/*.py` initially |
| `engine/hook-handlers/inject_kanban_context.py` | `engine/apps/hooks/inject_kanban_context.py` |

### Memory, Skills, Settings, Metrics

| Current | Target |
|---|---|
| `engine/memory_gc/*` | `engine/core/memory/*` if domain logic, adapters for filesystem |
| `engine/flow/project_skill_detector.py` | `engine/core/skills/project_detector.py` |
| `engine/flow/skill_mapper.py` | `engine/core/skills/mapper.py` |
| `engine/flow/skill_state_manager.py` | `engine/core/skills/state.py` plus filesystem adapter |
| `engine/flow/env_manager.py` | `engine/adapters/filesystem/settings.py` |
| `engine/sync/*` | `engine/core/history/*` plus adapters |
| `engine/flow/metrics*.py` | `engine/core/metrics/*` |
| `engine/flow/usage_tracker.py` | `engine/core/metrics/usage.py` |

## Board Web Layout

The board frontend should also be organized by user-facing domain:

```text
board/web/
  core/
    common.js
    sse.js
    renderer-helpers.js
  workflow/
    production-line-workflow.js
    workflow-bar.js
    workflow-sessions.js
    step-overlay.js
  terminal/
    terminal.js
    terminal-input.js
    session-switcher.js
    tool-renderers.js
  kanban/
    kanban.js
  memory/
    memory-core.js
    memory-gc.js
    memory-quick-prompts.js
    memory-rules-prompt.js
  settings/
    settings.js
  viewer/
    viewer.js
  vendor/
```

Keep the current static URLs stable until the server route and HTML references
are migrated together.

## Refactor Order

### Phase A: Tests First

1. Move green tests into `.agent-factory/tests` after the runtime root rename.
2. Delete V1-only tests.
3. Keep `python3 -m pytest` green.

### Phase B: Pure Domain Extraction

1. Extract enums/dataclasses: workflow step, run ID, ticket ref, phase, plan,
   artifact, verdict.
2. Add domain tests before moving behavior.
3. Do not move subprocess, HTTP, git, or filesystem calls yet.

### Phase C: Application Services

1. Extract `run_workflow`.
2. Convert step functions to services that depend on ports.
3. Use fake ports in tests.

### Phase D: Adapter Split

1. Move Claude subprocess into `adapters/claude/runner.py`.
2. Move XML ticket and run file IO into filesystem/kanban adapters.
3. Move git worktree calls into git adapters.
4. Move board SSE/session persistence into board adapters.

### Phase E: App Entrypoints

1. Rebuild CLI wrappers against `engine/apps/cli`.
2. Rebuild board server imports against `engine/apps/board_api`.
3. Move hooks into `engine/apps/hooks`.
4. Keep wrapper names stable for users.

### Phase F: Board Web

1. Move frontend modules by domain.
2. Update `index.html`/`terminal.html` references in one commit.
3. Remove deprecated metrics and V1 workflow UI files.

## Rules For File Moves

- One domain per commit or ticket.
- Add import-compatibility shims only inside the same phase and delete them
  before the phase closes.
- Never move stale V1 tests; delete or rewrite them first.
- After each phase, run `python3 -m pytest` from `.agent-factory`.
- Prefer smaller modules with explicit names over generic `utils.py`.
- Domain modules must not import board handlers, subprocess, HTTP, or Claude.

## First Concrete Batch

M1 completed the first real restructuring batch:

1. Created the canonical top-level tests directory under the runtime root.
2. Moved green Production-line tests into:
   - `tests/domain/production_line`
   - `tests/application/production_line`
   - `tests/adapters/production_line`
3. Moved board server tests to `tests/contracts/board_api`.
4. Removed old `tests/__init__.py` files from the moved roots.
5. Updated `pytest.ini` to use only `tests`.
6. Verified canonical tests with `python3 -m pytest`.

Only after this batch should source files start moving.
