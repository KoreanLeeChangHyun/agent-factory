# Workflow Orchestration (Session Summary)

All `cc:*` commands execute phases according to their mode:

```
Tier 1 (full):    INIT -> PLAN -> WORK -> REPORT   (default)
Tier 2 (no-plan): INIT -> WORK -> REPORT            (-np flag)
Tier 3 (prompt):  INIT -> Main Agent Direct Work     (cc:prompt)
```

## Commands

implement, refactor, review, build, analyze, architect, framework, research -- all follow Tier 1 by default, Tier 2 with `-np` flag.
prompt -- always Tier 3 (no workflow phases).

## Mode Determination

| Condition | Mode | Phase Order |
|-----------|------|-------------|
| `cc:prompt` | Tier 3 (prompt) | INIT -> Direct Work -> COMPLETED |
| `cc:<cmd> -np` | Tier 2 (no-plan) | INIT -> WORK -> REPORT -> COMPLETED |
| `cc:<cmd>` (default) | Tier 1 (full) | INIT -> PLAN -> WORK -> REPORT -> COMPLETED |

## Orchestrator Structure

```
Main Agent (Orchestrator)
  +-- 0. INIT: init agent -> request, workDir, workId, date, title, workName, rationale
  +-- 1. PLAN: planner agent -> plan path (then AskUserQuestion approval) [full only]
  +-- 2. WORK: worker agent(s) -> work log path [full + no-plan]
  +-- 3. REPORT: reporter agent -> report path [full + no-plan]
  +-- Direct Work: main agent performs work directly [prompt only]
```

Sub-agents MUST NOT call other sub-agents; main agent chains directly.

## Banner Calls

```bash
Workflow INIT none <command>           # Before INIT (all modes)
Workflow <registryKey> PLAN            # Before PLAN (full only)
Workflow <registryKey> PLAN done       # After PLAN (full only)
Workflow <registryKey> WORK            # Before WORK (full + no-plan)
Workflow <registryKey> WORK-PHASE <N> "<taskIds>" <parallel|sequential>  # Each Phase start (full only, not in no-plan)
Workflow <registryKey> WORK done       # After WORK (full + no-plan)
Workflow <registryKey> REPORT          # Before REPORT (full + no-plan)
Workflow <registryKey> REPORT done     # After REPORT (full + no-plan)
Workflow <registryKey> DONE done       # Final (all modes)
```

## Sub-agent Dispatch

```
# INIT (all modes)
Task(subagent_type="init", prompt="command: <command>, mode: <mode>")

# PLAN (full mode only)
Task(subagent_type="planner", prompt="command: <command>, workId: <workId>, request: <request>, workDir: <workDir>")

# WORK - Phase 0 (full mode only, sequential)
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: phase0, planPath: <planPath>, workDir: <workDir>, mode: phase0")

# WORK - Phase 1~N (full mode)
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: W01, planPath: <planPath>, workDir: <workDir>, skills: <skillName>")

# WORK - no-plan mode (single worker, no Phase 0)
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: W01, workDir: <workDir>, mode: no-plan")

# REPORT (full + no-plan)
Task(subagent_type="reporter", prompt="command: <command>, workId: <workId>, workDir: <workDir>, workPath: <workDir>/work/")
```

## State Update

```bash
wf-state both <registryKey> <agent> <fromPhase> <toPhase>   # Recommended
wf-state context <registryKey> <agent>                       # .context.json only
wf-state status <registryKey> <fromPhase> <toPhase>          # status.json only
wf-state register <registryKey>                              # Global registry
wf-state unregister <registryKey>                            # Global registry
wf-state link-session <registryKey> <sessionId>              # Session tracking
```

**Mode-aware State Update:**

| Mode | WORK transition | Command |
|------|----------------|---------|
| full | PLAN -> WORK | `wf-state both <registryKey> worker PLAN WORK` |
| no-plan | INIT -> WORK | `wf-state both <registryKey> worker INIT WORK` |
| prompt | INIT -> COMPLETED | `wf-state status <registryKey> INIT COMPLETED` |

## Return Formats

| Agent | Lines | Key Fields |
|-------|-------|------------|
| init | 7 | request, workDir, workId, date, title, workName, rationale |
| planner | 3 | status, plan path, task count |
| worker | 3 | status, work log path, changed file count |
| reporter | 3 | status, report path, CLAUDE.md status |

## FSM Transition

| Mode | Normal Flow | Branches |
|------|-------------|----------|
| full (default) | INIT -> PLAN -> WORK -> REPORT -> COMPLETED | PLAN->CANCELLED, WORK/REPORT->FAILED, TTL->STALE |
| no-plan | INIT -> WORK -> REPORT -> COMPLETED | WORK/REPORT->FAILED, TTL->STALE |
| prompt | INIT -> COMPLETED | TTL->STALE |

Illegal transitions blocked by system guard. Emergency: `WORKFLOW_SKIP_GUARD=1`.
`mode` field absent in legacy status.json defaults to `full` (backward compatible).

## Key Rules

1. On `cc:*` command, call init immediately (MUST NOT check user input first)
2. After INIT, check mode to determine branch: prompt -> direct work, no-plan -> skip PLAN, full -> PLAN
3. PLAN approval via AskUserQuestion (Approve / Revise / Cancel) -- full mode only, PLAN banner MUST complete before AskUserQuestion
4. WORK: only worker/reporter calls; MUST NOT re-call planner/init or reverse phase
5. no-plan WORK: single worker call (taskId: W01, no planPath, no Phase 0)
6. prompt mode: main agent direct work after INIT, then INIT->COMPLETED + unregister + DONE banner
7. Worker return: extract first 3 lines only (discard from line 4)
8. MUST NOT output internal analysis/reasoning to terminal -- only banners, links, errors
9. After DONE banner: immediate termination, no further text

## Supporting Files

Full details in `.claude/skills/workflow-orchestration/`:
- `SKILL.md` -- navigation hub with complete rules
- `step0-init.md` -- INIT phase details
- `step1-plan.md` -- PLAN phase + approval flow details
- `step2-work.md` -- WORK phase + Phase 0/1~N details
- `step3-report.md` -- REPORT phase details
- `common-reference.md` -- return formats, state management, FSM, error handling
