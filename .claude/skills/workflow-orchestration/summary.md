# Workflow Orchestration (Session Summary)

All `cc:*` commands MUST execute: **INIT -> PLAN -> WORK -> REPORT** (no skipping).

## Commands

implement, refactor, review, build, analyze, architect, framework, research -- all follow the same 4-phase workflow.

## Orchestrator Structure

```
Main Agent (Orchestrator)
  +-- 0. INIT: init agent -> request, workDir, workId, date, title, workName, rationale
  +-- 1. PLAN: planner agent -> plan path (then AskUserQuestion approval)
  +-- 2. WORK: worker agent(s) -> work log path (Phase 0 first, then Phase 1~N)
  +-- 3. REPORT: reporter agent -> report path
```

Sub-agents MUST NOT call other sub-agents; main agent chains directly.

## Banner Calls

```bash
Workflow INIT none <command>           # Before INIT
Workflow <registryKey> PLAN            # Before PLAN
Workflow <registryKey> PLAN done       # After PLAN
Workflow <registryKey> WORK            # Before WORK
Workflow <registryKey> WORK done       # After WORK
Workflow <registryKey> REPORT          # Before REPORT
Workflow <registryKey> REPORT done     # After REPORT
Workflow <registryKey> DONE done       # Final (after status.json + unregister)
```

## Sub-agent Dispatch

```
Task(subagent_type="init", prompt="command: <command>")
Task(subagent_type="planner", prompt="command: <command>, workId: <workId>, request: <request>, workDir: <workDir>")
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: phase0, planPath: <planPath>, workDir: <workDir>, mode: phase0")
Task(subagent_type="worker", prompt="command: <command>, workId: <workId>, taskId: W01, planPath: <planPath>, workDir: <workDir>, skills: <skillName>")
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

## Return Formats

| Agent | Lines | Key Fields |
|-------|-------|------------|
| init | 7 | request, workDir, workId, date, title, workName, rationale |
| planner | 3 | status, plan path, task count |
| worker | 3 | status, work log path, changed file count |
| reporter | 3 | status, report path, CLAUDE.md status |

## Key Rules

1. On `cc:*` command, call init immediately (MUST NOT check user input first)
2. PLAN approval via AskUserQuestion (Approve / Revise / Cancel) -- PLAN banner MUST complete before AskUserQuestion
3. WORK: only worker/reporter calls; MUST NOT re-call planner/init or reverse phase
4. Worker return: extract first 3 lines only (discard from line 4)
5. MUST NOT output internal analysis/reasoning to terminal -- only banners, links, errors
6. After DONE banner: immediate termination, no further text

## Supporting Files

Full details in `.claude/skills/workflow-orchestration/`:
- `SKILL.md` -- navigation hub with complete rules
- `step0-init.md` -- INIT phase details
- `step1-plan.md` -- PLAN phase + approval flow details
- `step2-work.md` -- WORK phase + Phase 0/1~N details
- `step3-report.md` -- REPORT phase details
- `common-reference.md` -- return formats, state management, FSM, error handling
