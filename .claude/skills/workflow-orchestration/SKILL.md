---
name: workflow-orchestration
description: "Workflow orchestration skill with Supporting Files. SKILL.md is a navigation hub (~300 lines). SessionStart hook injects summary.md (~3KB). Detailed guides: step0-init.md, step1-plan.md, step2-work.md, step3-report.md, common-reference.md."
disable-model-invocation: true
---

## Workflow Compliance

All cc:* commands execute phases according to their mode:

```
Tier 1 (full):    INIT -> PLAN -> WORK -> REPORT
Tier 2 (no-plan): INIT -> WORK -> REPORT
Tier 3 (prompt):  INIT -> Direct Work by Main Agent
```

**Mode Rules:**

| Mode | Phase Order | Skip Allowed |
|------|-------------|-------------|
| full (default) | INIT -> PLAN -> WORK -> REPORT | None |
| no-plan (-np) | INIT -> WORK -> REPORT | PLAN skipped |
| prompt | INIT -> Main Agent Direct | PLAN, WORK, REPORT skipped |

1. Phase order within each mode MUST NOT be violated
2. PLAN approval REQUIRED before WORK proceeds (full mode only)
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
| prompt | Lightweight direct work (Tier 3, no workflow) |

Commands follow their mode's phase order. Default is full (INIT -> PLAN -> WORK -> REPORT). `prompt` always runs in Tier 3 mode.

## Input Parameters

- `command`: execution command (implement, refactor, review, etc.)

> cc:* commands do NOT use `$ARGUMENTS` for prompt content. User requests are handled by init agent via `.prompt/prompt.txt`. Mode flags (`-np`) in `$ARGUMENTS` are allowed for mode selection only.

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
| Prompt mode Final | `Workflow <registryKey> DONE done` (after direct work, no PLAN/WORK/REPORT banners) |

PLAN completion banner MUST complete before AskUserQuestion (sequential, 2 separate turns).

DONE banner: Called after REPORT completion + status.json finalization + registry unregister. Auto-sends Slack notification.

### Output Rules

**Allowed:** Phase banners, phase report links, file paths, approval requests, error messages, status returns.

**MUST NOT output:** analysis process, reasoning, code review details, comparisons, internal thoughts, work plans, progress reports, free-text messages, sub-agent return interpretation, any text after DONE banner.

**Sub-agents:** Standard return format only. MUST NOT quote/explain skill content in terminal.

### Post-Return Silence Rules

| Step Completed | Allowed Actions | Prohibited |
|---------------|----------------|------------|
| INIT done (full) | Extract/retain params, PLAN banner, status update, planner call | Return summary, progress text |
| INIT done (no-plan) | Extract/retain params, skip PLAN, WORK banner, status update (INIT->WORK), single worker call | PLAN banner, planner call, AskUserQuestion |
| INIT done (prompt) | Direct work by main agent | Sub-agent calls, PLAN/WORK/REPORT banners |
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
Task(subagent_type="init", prompt="command: <command>, mode: <mode>")
```

> `mode` is determined before calling init: `prompt` for cc:prompt, `no-plan` if `-np` flag detected in `$ARGUMENTS`, `full` (default) otherwise.

Returns: `request`, `workDir`, `workId`, `date`, `title`, `workName`, `rationale` -- all MUST be retained for subsequent phases.

### Mode Branching (After INIT)

After INIT returns, check the command to determine mode:

| Command | Mode | Next Step |
|---------|------|-----------|
| `prompt` | Tier 3 | Main agent direct work (skip PLAN/WORK/REPORT) |
| Others with `-np` | Tier 2 | Skip to WORK (skip PLAN) |
| Others (default) | Tier 1 | Proceed to PLAN |

**Prompt Mode (Tier 3):**
If command is `prompt`, the orchestrator performs direct work after INIT:
1. Read `<workDir>/user_prompt.txt` for the user request
2. Perform work directly (using Read, Write, Edit, Grep, Glob, Bash, etc.)
3. On completion:
   ```bash
   # Update history.md (append 1 row)
   # Transition status: INIT -> COMPLETED
   wf-state status <registryKey> INIT COMPLETED
   # Unregister from global registry
   wf-state unregister <registryKey>
   # DONE banner
   Workflow <registryKey> DONE done
   ```
4. Terminate immediately after DONE banner

**No-Plan Mode (Tier 2):**
If `$ARGUMENTS` contains `-np` flag, the orchestrator skips PLAN and proceeds directly to WORK after INIT:
1. INIT returns normally (init agent called with `mode: no-plan`)
2. Skip PLAN entirely (no planner call, no AskUserQuestion, no PLAN banners)
3. WORK banner, then single Worker call with `mode: no-plan` (no planPath, no Phase 0):
   ```bash
   Workflow <registryKey> WORK
   wf-state both <registryKey> worker INIT WORK
   ```
   ```
   Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: W01, workDir: <workDir>, mode: no-plan")
   ```
4. After Worker returns, proceed to REPORT as normal
5. Phase order: INIT -> WORK -> REPORT -> COMPLETED

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

**Status update (mode-aware):**
- full mode: `wf-state both <registryKey> worker PLAN WORK`
- no-plan mode: `wf-state both <registryKey> worker INIT WORK`

**Rules:** Only worker/reporter calls allowed. MUST NOT re-call planner/init. MUST NOT reverse phase. MUST NOT augment context autonomously. Execute ONLY plan tasks (full mode) or user_prompt.txt request (no-plan mode).

**No-Plan Mode (single worker, no Phase 0):**
```
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: W01, workDir: <workDir>, mode: no-plan")
```
- Phase 0 (skill-map) skipped
- planPath not provided; worker reads `<workDir>/user_prompt.txt` directly
- Single worker call (taskId: W01 fixed)

**Full Mode - Phase 0 (REQUIRED, sequential):**
```
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: phase0, planPath: <planPath>, workDir: <workDir>, mode: phase0")
```

**Full Mode - Phase 1~N:** Execute per plan. Independent tasks parallel, dependent tasks sequential.
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

Mode-aware: full=`INIT->PLAN->WORK->REPORT->COMPLETED`, no-plan=`INIT->WORK->REPORT->COMPLETED`, prompt=`INIT->COMPLETED`. Branches: PLAN->CANCELLED, WORK/REPORT->FAILED, TTL->STALE. Illegal transitions blocked by system guard. Emergency: `WORKFLOW_SKIP_GUARD=1`.

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
3. Phase order per mode strictly enforced (full: INIT->PLAN->WORK->REPORT, no-plan: INIT->WORK->REPORT, prompt: INIT->COMPLETED)
4. Full clarification in PLAN; WORK cannot ask questions
5. After planner returns, orchestrator performs AskUserQuestion directly
6. Independent tasks parallel; dependent tasks sequential
7. All phases MUST save documents
8. REPORT MUST update CLAUDE.md
9. Slack failure does not block workflow
10. Git commits via `/git:commit` separately
