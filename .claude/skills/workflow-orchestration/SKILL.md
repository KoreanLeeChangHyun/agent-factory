---
name: workflow-orchestration
description: "Workflow orchestration skill with Supporting Files. SKILL.md is a navigation hub (~300 lines). SessionStart hook injects summary.md (~3KB). Detailed guides: step0-init.md, step1-plan.md, step2-work.md, step3-report.md, common-reference.md."
disable-model-invocation: true
---

## Workflow Compliance

All cc:* commands MUST execute these phases in strict order:

```
INIT -> PLAN -> WORK -> REPORT
```

1. All phases REQUIRED, MUST NOT skip any phase
2. PLAN approval REQUIRED before WORK proceeds
3. Violation: halt workflow and report error

---

# Orchestrator

Main agent controls workflow sequencing and agent dispatch only.

## Workflow Structure

```
Main Agent (Orchestrator)
    |
    +-- 0. INIT: init agent -> returns: request, workDir, workId, date, title, workName, rationale
    +-- 1. PLAN: planner agent (workflow-plan skill) -> returns: plan path
    +-- 2. WORK: worker agent (workflow-work skill) -> returns: work log path
    +-- 3. REPORT: reporter agent (workflow-report skill) -> returns: report path
```

Core Principles:
- All phases execute via sub-agents
- Sub-agents MUST NOT call other sub-agents; main agent chains directly
- Git commits run separately via `/git:commit` after workflow completion

## Supported Commands

| Command | Description |
|---------|------------|
| implement | Feature implementation |
| refactor | Code refactoring |
| review | Code review |
| build | Build script generation |
| analyze | Requirements analysis |
| architect | Architecture design and diagrams |
| framework | Framework project initialization |
| research | Research/investigation |

All commands follow the same INIT -> PLAN -> WORK -> REPORT workflow.

## Input Parameters

- `command`: execution command (implement, refactor, review, etc.)

> cc:* commands do NOT use `$ARGUMENTS`. User requests are handled by init agent via `.prompt/prompt.txt`.

---

## Terminal Output Protocol

> Core principle: Users want phase-level results only. MUST NOT output internal analysis/reasoning.

### Phase Banner Calls

```bash
# Phase start banner
Workflow <registryKey> <phase>

# Phase completion banner (status included, path auto-inferred)
Workflow <registryKey> <phase> <status>
```

- **`<registryKey>`**: `YYYYMMDD-HHMMSS` format workflow identifier (full workDir path backward compatible)
- **`[path]`**: (optional) Auto-inferred if omitted. Explicit path overrides.

**Call Timing:**

| Timing | Command |
|--------|---------|
| Before INIT | `Workflow INIT none <command>` |
| Before/After PLAN | `Workflow <registryKey> PLAN` / `Workflow <registryKey> PLAN done` |
| Before/After WORK | `Workflow <registryKey> WORK` / `Workflow <registryKey> WORK done` |
| Before/After REPORT | `Workflow <registryKey> REPORT` / `Workflow <registryKey> REPORT done` |
| Final | `Workflow <registryKey> DONE done` |

PLAN completion banner MUST complete before AskUserQuestion (sequential, 2 separate turns).

DONE banner: Called after REPORT completion + status.json finalization + registry unregister. Auto-sends Slack notification.

### Output Rules

**Allowed:** Phase banners, phase report links, file paths, approval requests, error messages, status returns.

**MUST NOT output:** analysis process, reasoning, code review details, comparisons, internal thoughts, work plans, progress reports, free-text messages, sub-agent return interpretation, any text after DONE banner.

**Sub-agents:** Standard return format only. MUST NOT quote/explain skill content in terminal.

### Post-Return Silence Rules

| Step Completed | Allowed Actions | Prohibited |
|---------------|----------------|------------|
| INIT done | Extract/retain params, PLAN banner, status update, planner call | Return summary, progress text |
| PLAN (1a) done | PLAN completion banner **(await Bash)**, then AskUserQuestion **(sequential, MUST NOT parallel)** | Plan summary, parallel banner+ask |
| PLAN (1b) done | Branch on approval, WORK banner, status update | Approval explanation |
| WORK in progress | Next worker call (parallel/sequential per dependency) | Planner re-call, status rollback, autonomous augmentation |
| WORK done | WORK completion banner, extract first 3 lines, REPORT banner, reporter call | Work summary, file listing |
| REPORT done | REPORT completion banner, DONE banner, **immediate termination** | Report summary, any post-DONE text |

---

## Step 0: INIT

**Details:** See [step0-init.md](step0-init.md)

```bash
Workflow INIT none <command>
```

```
Task(subagent_type="init", prompt="command: <command>")
```

Returns: `request`, `workDir`, `workId`, `date`, `title`, `workName`, `rationale` -- all MUST be retained for subsequent phases.

---

## Sub-agent Dispatch

### Step 1: PLAN

**Details:** See [step1-plan.md](step1-plan.md)

**Status update:** `wf-state both <registryKey> planner INIT PLAN`

```
Task(subagent_type="planner", prompt="command: <command>, workId: <workId>, request: <request>, workDir: <workDir>")
```

After planner returns, orchestrator performs **AskUserQuestion** approval (3 fixed options: Approve / Revise / Cancel). See step1-plan.md for full approval flow, .context.json handling, Slack notification, CANCELLED processing, and Binding Contract rule.

### Step 2: WORK

**Details:** See [step2-work.md](step2-work.md)

**Status update:** `wf-state both <registryKey> worker PLAN WORK`

**Rules:** Only worker/reporter calls allowed. MUST NOT re-call planner/init. MUST NOT reverse phase. MUST NOT augment context autonomously. Execute ONLY plan tasks.

**Phase 0 (REQUIRED, sequential):**
```
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: phase0, planPath: <planPath>, workDir: <workDir>, mode: phase0")
```

**Phase 1~N:** Execute per plan. Independent tasks parallel, dependent tasks sequential.
```
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: W01, planPath: <planPath>, workDir: <workDir>, skills: <skillName>")
```

**Worker return:** Extract first 3 lines only (discard from line 4). Details in .workflow/ files.

### Step 3: REPORT

**Details:** See [step3-report.md](step3-report.md)

**Status update:** `wf-state both <registryKey> reporter WORK REPORT`

```
Task(subagent_type="reporter", prompt="command: <command>, workId: <workId>, workDir: <workDir>, workPath: <workDir>/work/")
```

After REPORT: completion banner -> (reporter handles status.json + unregister) -> DONE banner -> terminate.

```bash
Workflow <registryKey> DONE done
```

---

## Common Reference

**Full details:** See [common-reference.md](common-reference.md)

### Sub-agent Return Formats

> Return values exceeding line limits cause context bloat and system failure.

| Agent | Lines | Format |
|-------|-------|--------|
| init | 7 | `request`, `workDir`, `workId`, `date`, `title`, `workName`, `rationale` |
| planner | 3 | `status`, `plan path`, `task count` |
| worker | 3 | `status`, `work log path`, `changed file count` |
| reporter | 3 | `status`, `report path`, `CLAUDE.md status` |

### Invocation Rules

| Target | Method | Example |
|--------|--------|---------|
| Agent (4) | Task | `Task(subagent_type="init", prompt="...")` |
| Skill (5) | Skill | `Skill(skill="workflow-report")` |

Agents: init, planner, worker, reporter. Skills: workflow-orchestration, workflow-init, workflow-plan, workflow-work, workflow-report.

### State Update

```bash
wf-state <mode> <registryKey> [args...]
```

| Mode | Arguments | Description |
|------|-----------|-------------|
| context | `<registryKey> <agent>` | Update .context.json agent field |
| status | `<registryKey> <fromPhase> <toPhase>` | Update status.json phase |
| both | `<registryKey> <agent> <fromPhase> <toPhase>` | Update both (recommended) |
| register | `<registryKey>` | Register in global registry |
| unregister | `<registryKey>` | Unregister from global registry |
| link-session | `<registryKey> <sessionId>` | Add session to linked_sessions |

registryKey: `YYYYMMDD-HHMMSS` format. Non-blocking: failures emit warning only.

### FSM Transition

`INIT -> PLAN -> WORK -> REPORT -> COMPLETED`. Branches: PLAN->CANCELLED, WORK/REPORT->FAILED, TTL->STALE. Illegal transitions blocked by system guard. Emergency: `WORKFLOW_SKIP_GUARD=1`.

### Error Handling

| Situation | Action |
|-----------|--------|
| INIT error | Retry up to 3 times |
| Phase error | Retry up to 3 times, then error report |
| Independent task failure | Other tasks continue |
| Dependent blocker failure | Halt chain, others continue |
| Failure rate >50% | Halt workflow, AskUserQuestion |

---

## Notes

1. MUST run INIT first to obtain request, workDir
2. On cc:* command, MUST NOT check user input -- always call init immediately
3. Phase order: INIT -> PLAN -> WORK -> REPORT strictly enforced
4. Full clarification in PLAN; WORK cannot ask questions
5. After planner returns, orchestrator performs AskUserQuestion directly
6. Independent tasks parallel; dependent tasks sequential
7. All phases MUST save documents
8. REPORT MUST update CLAUDE.md
9. Slack failure does not block workflow
10. Git commits via `/git:commit` separately
