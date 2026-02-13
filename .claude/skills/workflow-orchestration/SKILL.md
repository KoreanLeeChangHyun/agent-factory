---
name: workflow-orchestration
description: "워크플로우 전체 오케스트레이션 내부 스킬. INIT -> PLAN -> WORK -> REPORT 4단계 워크플로우를 관리한다. Use for workflow orchestration: cc:* 커맨드 실행 시 자동 로드되어 단계별 흐름 제어, 서브에이전트 호출, 상태 관리를 수행한다. SKILL.md는 네비게이션 허브(~300줄)이며, 상세 가이드는 step0-init.md ~ step3-report.md, common-reference.md에 분리."
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
    +-- 0. INIT: init agent -> returns: request, workDir, workId, registryKey, date, title, workName, rationale
    +-- 1. PLAN: planner agent (workflow-plan skill) -> returns: plan path
    +-- 2. WORK: worker agent (workflow-work skill) -> returns: work log path
    +-- 3. REPORT: reporter agent (workflow-report skill) -> returns: report path
    +-- 4. END: end agent (workflow-end skill) -> history.md, status.json, usage, unregister + orchestrator DONE banner
```

Core Principles:
- All phases execute via sub-agents
- Sub-agents MUST NOT call other sub-agents; main agent chains directly
- Git commits run separately via `/git:commit` after workflow completion

## Supported Commands

| Command | Description |
|---------|------------|
| implement | Feature implementation, refactoring, architecture diagrams |
| review | Code review |
| research | Research/investigation and internal asset analysis |
| strategy | Multi-workflow strategy and roadmap generation |
| prompt | Lightweight direct work (Tier 3, no workflow) |

Commands follow their mode's phase order. Default is full (INIT -> PLAN -> WORK -> REPORT). `prompt` always runs in Tier 3 mode.

## Input Parameters

- `command`: execution command (implement, review, research, strategy, prompt)

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
| WORK Phase N start | `Workflow <registryKey> WORK-PHASE <N> "<taskIds>" <parallel\|sequential>` |
| Before/After REPORT | `Workflow <registryKey> REPORT` / `Workflow <registryKey> REPORT done` |
| Before/After DONE | `Workflow <registryKey> DONE` / `Workflow <registryKey> DONE done` |
| Prompt mode Final | `Workflow <registryKey> DONE done` (after direct work, no PLAN/WORK/REPORT banners) |

PLAN completion banner MUST complete before AskUserQuestion (sequential, 2 separate turns).

DONE start banner: Called by orchestrator before dispatching end agent. DONE completion banner: Called by orchestrator after end agent returns. Auto-sends Slack notification.

**CRITICAL: After DONE banner, the orchestrator MUST terminate immediately. Output ZERO text after DONE banner. Any post-DONE output (e.g., "Workflow already completed", "All tasks finished", status explanations) is a protocol violation.**

### Output Rules

**Allowed:** Phase banners, phase report links, file paths, approval requests, error messages, status returns.

**MUST NOT output:** analysis process, reasoning, code review details, comparisons, internal thoughts, work plans, progress reports, free-text messages, sub-agent return interpretation, any text after DONE banner, workflow completion status messages (e.g., "Workflow already completed", "All tasks finished", "DONE banner was issued"), post-completion explanations or summaries.

**Sub-agents:** Standard return format only. MUST NOT quote/explain skill content in terminal.

### Post-Return Silence Rules

| Step Completed | Allowed Actions | Prohibited |
|---------------|----------------|------------|
| INIT done (full) | Extract/retain params, PLAN banner, status update, planner call | Return summary, progress text |
| INIT done (no-plan) | Extract/retain params, skip PLAN, WORK banner, status update (INIT->WORK), single worker call | PLAN banner, planner call, AskUserQuestion |
| INIT done (prompt) | Direct work by main agent | Sub-agent calls, PLAN/WORK/REPORT banners |
| PLAN (1a) done | PLAN completion banner **(await Bash)**, then AskUserQuestion **(sequential, MUST NOT parallel)** | Plan summary, parallel banner+ask |
| PLAN (1b) done | Branch on approval, WORK banner, status update | Approval explanation |
| WORK Phase start | WORK-PHASE banner, then worker call(s) for that phase | Skipping Phase banner |
| WORK in progress | Next worker call (parallel/sequential per dependency) | Planner re-call, status rollback, autonomous augmentation |
| WORK done | WORK completion banner, extract first 3 lines, REPORT banner, reporter call | Work summary, file listing |
| REPORT done | REPORT completion banner, DONE start banner, end agent call, extract first 2 lines, DONE completion banner, immediate termination | Report summary, any post-DONE text, "Workflow already completed", "All tasks finished", "DONE banner was issued", any workflow status message |

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

Returns: `request`, `workDir`, `workId`, `registryKey`, `date`, `title`, `workName`, `rationale` -- all MUST be retained for subsequent phases.

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
3. On completion (MUST execute steps 3a-3d sequentially, skipping none):
   ```bash
   # 3a. Update .prompt/history.md (append 1 row)
   # 3b. Transition status: INIT -> COMPLETED
   wf-state status <registryKey> INIT COMPLETED
   # 3c. Unregister from global registry (MUST NOT skip: 누락 시 INIT phase 잔류 엔트리 발생)
   wf-state unregister <registryKey>
   # 3d. DONE banner
   Workflow <registryKey> DONE done
   ```
   > **REQUIRED:** `wf-state status` (3b)와 `wf-state unregister` (3c)는 반드시 순차 실행. unregister 누락 시 INIT phase로 레지스트리에 잔류하여 `wf-registry clean`에서도 정리되지 않는 고아 엔트리가 됩니다.
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

After planner returns, orchestrator performs **AskUserQuestion** approval (3 fixed options: 승인 / 수정 / 중지). See step1-plan.md for full approval flow, .context.json handling, Slack notification, CANCELLED processing, and Binding Contract rule.

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
```bash
Workflow <registryKey> WORK-PHASE 0 "phase0" sequential
```
```
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: phase0, planPath: <planPath>, workDir: <workDir>, mode: phase0")
```

**Full Mode - Phase 1~N:** Execute per plan. Independent tasks parallel, dependent tasks sequential. Call WORK-PHASE banner before each phase's worker(s).
```bash
Workflow <registryKey> WORK-PHASE <N> "<taskIds>" <parallel|sequential>
```
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

After REPORT: completion banner -> DONE start banner -> end agent call (history.md, status.json, usage, unregister) -> DONE completion banner -> terminate.

```bash
# Orchestrator calls DONE start banner before end agent
Workflow <registryKey> DONE
# Orchestrator dispatches end agent
Task(subagent_type="end", ...)
# Orchestrator calls DONE completion banner after end agent returns
Workflow <registryKey> DONE done
```

---

## Common Reference

> Sub-agent return formats, invocation rules, state update methods, FSM transitions, error handling: See [common-reference.md](common-reference.md)

---

## Notes

1. MUST run INIT first; on cc:* command, call init immediately without checking user input
2. Phase order per mode strictly enforced; WORK cannot ask questions (clarification in PLAN only)
3. Git commits via `/git:commit` separately; Slack failure does not block workflow
