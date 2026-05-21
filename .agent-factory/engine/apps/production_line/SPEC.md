# production-line workflow engine specification (SPEC)

> **Single Source of Truth (SSOT)**. This document obfuscates all responsibilities, interfaces, and canons of production-line.
> If there is a conflict between this document and other documents (skills/SKILL.md, rules/workflow/workflow.md, agents/*.md), this document takes precedence and updates the other documents.
> Created: 2026-05-14 (T-489, Phase 1). Specification version: production-line 1.0.0

---

## 0. One line summary

> production-line = **driver script 1 process (rule base, LLM call
> All state changes, decisions, and control flows are handled by the driver. claude -p only writes output files.

### 0.1 Shared responsibility canon (user specified 2026-05-15, T-503 expanded 2026-05-18)

> **driver = 14+ rule evaluation + code determinism verification (pytest/lint) + git commit + conveyor transition + FSM** (all determinism)
> **LLM = Writing the body of the output .md** (**natural language part only** of plan/work/validate natural language evaluation/report)

All prompt areas that delegate 14+ rule evaluation, code determinism verification (pytest -q / ruff / mypy), verdict calculation, git commit, conveyor transition, and FSM transition to LLM are **rule violations**. Recover to the driver determinism domain.

### 0.1.1 Verification 2-axis separation (T-503)

> Production-line verification is clearly separated into **2 axes**. Blocks v1·production-line initial regression where natural language evaluation and determinism verification are mixed within the same vocabulary called 'VALIDATE'.

| axis | subject | output | Format | Text |
|----|------|--------|------|------|
| **Natural Language Paper Assessment (LLM)** | claude -p (VALIDATE Step) | `validate/report.md` | Markdown | phase decomposition adequacy / deliverable completeness / deps flow / comprehensive evaluation |
| **Determinism rule evaluation (driver)** | driver `_validate.py` | `validate/rules.json` | JSON | 14+ rule PASS/WARN/FAIL/SKIP stuffed + violation count + hard_fail |
| **Deterministic code verification (driver, implement only)** | driver `_verify_code.py` | `validate/code.json` | JSON | pytest -q + ​​ruff check + mypy's status/counts/head_diagnostics |

LLM is responsible for code verification, rule evaluation, and verdict calculation. Driver is responsible for natural language evaluation.

### 0.1.2 TDD enforcement (implement only)

> Implement command only — Acceptance_criteria obligation in PLAN stage + Mandatory Red→Green→Refactor cycle prompt in WORK phase. Post-verification using the R-CODE-1/2 rule on the driver side.

- **PLAN**: Specifies the `acceptance_criteria` key (list[str]) in each phase of `plan.md` frontmatter (a form that can deterministically verify whether the criteria are met — pytest assertion / file existence / command exit code, etc.).
- **WORK**: For each item of acceptance_criteria, process in the following order: (1) Write a test that fails (Red) → (2) Implement it to pass (Green) → (3) Clean it up (Refactor).
- **Verification**: Driver `_verify_code.py` calls pytest -q in the worktree → `validate/code.json` output → R-CODE-1 (pytest passed hard-fail) / R-CODE-2 (lint clean advisory) evaluation of `_validate.py`.

TDD is not applied to research / review commands (accompanied by code changes). `_verify_code.py` itself SKIP.

---

## 1. Why production-line?

### Inherent flaws in 1.1 v1

In v1, the main session Claude (LLM) served as the orchestrator. This accumulated three regressions:

1. **Non-determinism of decisions**: LLM makes different decisions every cycle, such as “whether to enter the next step / retry prompt / phase decomposition / worker allocation”. The same output from the same input is not guaranteed.
2. **Fragility of hook absorption mechanism**: Attempting to convert Task subagent calls into deterministic wrappers with PreToolUse Hook. Multiple limitations including ZodError schema regression, SDK cap (SKILL.md 10KB), Anthropic hardcoded guard, etc.
3. **Main session context pollution**: Workflow progress eats up the token budget of the main session. Users cannot perform tasks outside of the workflow.

### 1.2 Production-line solution direction

- **Orchestration = Rule base code**: Decision area of ​​LLM → Absorbed into driver function. Input → same output guaranteed.
- **claude -p subprocess isolation**: The LLM work of each step is separated into a separate subprocess. Main session context 0 impact.
- **file-based pipeline**: Communication between steps only involves files. Memory state, session state, hook message dependency
- **Inject whole (Summary LLM avoids lossy compression.

### 1.3 User Insight Sequence (2026-05-14)

> Abolition of orchestrator → claude -p model → step-by-step isolation → file-based pipeline → propagation of entire output (Summary X) → Retry is claude -p --resume rule base

---

## 2. Vocabulary correction (Step vs Phase reversal)

The v1 vocabulary was homonymous, which caused confusion for both LLM/People. production-line is corrected.

| tier | v1 (confusing) | **production-line correction** | Remarks |
|------|----------|------------|------|
| Workflow Step 6 | phase (`workflow_phase`) | **Step** (`workflow_step`) | INIT / PLAN / WORK / VALIDATE / REPORT / DONE |
| WORK internal sub-step | step (`work_step`) | **Phase** (`work_phase`) | Phase 1, Phase 2, ... |

### 2.1 English identifier unification (LLM processing accuracy)

- `workflow_step`: 6 Step FSM (NONE / INIT / PLAN / WORK / VALIDATE / REPORT / DONE / FAILED)
- `work_phase`: WORK internal phase identifier (P1, P2, ...)
- The old `workflow_phase` key disappears from production-line base and is completely replaced with `workflow_step`.

### 2.2 No migration code required

production-line starts fresh from the b69645a base, so there is no need to co-exist with the old `workflow_phase` key. The new code starts from `workflow_step`.

---

## 3. 6 Step FSM Specification

### 3.1 Step flow

```
NONE → INIT → PLAN → WORK → VALIDATE → REPORT → DONE
                                                   ↓
                                                FAILED (when N retries are exceeded)
```

### 3.2 Responsibilities for each step (T-503 output 6 area canon)

| Step | subject | LLM Call | output | Core Responsibilities |
|------|------|---------|--------|----------|
| INIT | driver (in-process) | X | `metadata.json` (initial) / `workflow.log` (start append) | Parse WorkRequest prompt, create work_dir, conveyor Accepted→Executing |
| PLAN | driver → claude -p | 1 spawn | `plan/plan.json` (driver=JSON SSOT) + `plan/plan.md` (LLM↔LLM=md natural language body) | Work decomposition, Phase·worker·deps·acceptance_criteria specification (T-504 separate) |
| WORK | driver → claude -p | 1 spawn (inside Phase loop) | `work/<phase_id>/W<n>.md` × N (directory nesting) | Create output for each phase, follow dependency graph, TDD Red→Green→Refactor (implement) |
| VALIDATE | driver → claude -p + driver | 1 spawn (LLM) + driver in-process | `validate/report.md` (LLM) + `validate/rules.json` (driver) + `validate/code.json` (driver, implement only) | **Quality evaluation natural language only (LLM)** — phase decomposition adequacy / deliverable completeness. **14+Rule evaluation/code determinism verification (driver)** — pytest/ruff/mypy + R-CODE-1/2 (§0.1.1 canon) |
| REPORT | driver → claude -p | 1 spawn | `report.html` (person=HTML, template + placeholder 4 types) | plan + work + validate overall, T-504 cutover |
| DONE | driver (in-process) | X | `metadata.json` (finalize absorption — summary/usage/finalized_at) | conveyor Executing→Verifying, regression metric emit |
| FAILED | driver (in-process) | X | `metadata.json` (failure field absorbed) | fail-fast when retries exceed N or when hard-fail rule is violated |

#### 3.2.0 Determination of output format Canon SSOT (T-504, user specified 2026-05-18)

> **Who reads it → Determine the format**. This rule is the single basis for determining the format of all deliverables.

| Consumer | Format | Reason |
|--------|------|------|
| **driver (machine)** | **driver=JSON** | json.loads + dataclass validation determinism. Avoiding YAML homebrew parsers. |
| **LLM ↔ LLM** | **LLM↔LLM=md** | LLM friendly. WORK / VALIDATE / REPORT LLM Injects the entire output of the previous stage. |
| **Person (User)** | **Person=HTML** | TOC / code highlights / mermaid inline / terracotta tones. Read directly from Board terminal + browser. |

Formats other than these rules (CSV / YAML / old `summary.txt` / old `failure.md` / old `validate/code.md`) are prohibited from being introduced. The format determination for each area in §3.2.1 is automatically derived from this SSOT.

#### 3.2.1 Deliverable 6 Area Cannon (T-504 Update)

| # | output | Written by | Format |
|---|--------|----------|------|
| 1 | `metadata.json` | driver | JSON (absorbs old `.context.json` + `status.json` + `summary.txt` + `failure.md`) |
| 2 | `workflow.log` | driver | Text cumulative log |
| 3 | **`plan/plan.json` + `plan/plan.md`** | PLAN LLM | JSON (driver deterministic parsing SSOT) + Markdown (LLM natural language body) — T-504 separation |
| 4 | `work/<phase>/W<n>.md` | WORK LLM | Markdown (directory nesting — consistent across all phases) |
| 5 | **`report.html`** | REPORT LLM | **HTML (template `templates/report.html` + 4 types of placeholders)** — T-504 cutover |
| 6 | `validate/` directory | driver + VALIDATE LLM | `rules.json` (driver 14+ rules) + `report.md` (LLM natural language report verification) + `code.json` (driver pytest/lint, implement only) |

#### 3.2.2 Decommissioning Deliverables (T-503 + T-504 Migration)

| file | Reason | Absorber |
|------|------|--------|
| `user_prompt.txt` | The WorkRequest prompt is SSOT | (WorkRequest body) |
| `summary.txt` | report.html is a natural language report SSOT | `report.html` |
| `.context.json` + `status.json` | Output integration and registration | `metadata.json` |
| `failure.md` | A single JSON field is sufficient | `metadata.json.failure` |
| `validate-report.md` (flat) | `validate/` directory nesting | `validate/report.md` |
| `validate-rules.json` (flat) | `validate/` directory nesting | `validate/rules.json` |
| **`plan.md` (root, YAML frontmatter)** | T-504 — separate driver=JSON | `plan/plan.json` (SSOT) + `plan/plan.md` (natural language body) |
| **`report.md` (Markdown)** | T-504 — People=HTML Canon | `report.html` (template + placeholder) |

> **Migration sequence (T-503)**: Apply new path only to new cycle. Retroactive conversion is a star track. The driver path helper holds both paths (flat + nested) resolvable and discards the flat when the cycle is stable.

### 3.3 Step transition gate

At the end of each step, the driver verifies the rule base → enters the next step or retry or FAILED.

```
Step N End
  ↓
Output consistency verification (rule base — file exist, size > 0, frontmatter schema, regex)
  ↓
PASS → Enter Step N+1
FAIL (retry < N_max) → claude -p --resume + rule base retry prompt → re-execute Step N
FAIL (Retry = N_max) → Step FAILED → Cycle terminated
```

### 3.4 Retry limit per step (default)

| Step | N_max | Remarks |
|------|-------|------|
| INIT | 0 | driver in-process, no retry meaning |
| PLAN | 2 | Output 2 file (plan/plan.json + plan/plan.md), simple correction possible even after T-504 separation |
| WORK | 3 | Retry per phase (independent for each phase) |
| VALIDATE | 1 | advisory rating, low retry value |
| REPORT | 2 | Comprehensive writing (preserve the entire input, only rewrite) |
| DONE | 0 | driver in-process |

Can be overridden for each step with `.agent-factory/.settings` or env `V2_RETRY_<STEP>`.

### 3.4.1 Parallel spawn policy (T-506 new)

Simultaneous spawn limit + failure handling between and within phases in WORK Step subprocess mode.

| Item | default | env override | meaning |
|------|--------|--------------|------|
| `max_parallel` | 4 | `V2_MAX_PARALLEL` | Same topo level simultaneous spawn limit. The inner workers pool is separate (phase.workers as is). |
| `fail_policy` | `fail_fast` | `V2_FAIL_POLICY` | `fail_fast` (default) / `fail_tolerant`. At fail_fast, one phase fails → future cancel at same level does not start + blocks next level. |

Priority: env > `.settings` > default. When entering a negative number / 0 / non-number, default 4 fallback (graceful). `fail_policy` unknown value → `fail_fast` fallback.

driver implementation: `engine/apps/production_line/_common.py: get_max_parallel()` + `get_fail_policy()`. `engine/apps/production_line/_parallel.py: parallel_spawn()` is the infrastructure.

Decided not to adopt asyncio: claude -p subprocess is I/O bound + existing `_spawn.spawn_claude` is based on synchronous `subprocess.Popen`. ThreadPoolExecutor is sufficient without affecting the GIL (GIL is released during subprocess). Before asyncio, it was a star track.

---

## 4. Output model (file-based pipeline)

### 4.1 Directory structure

```
.agent-factory/runs/<registryKey>/
├── metadata.json # cycle meta (driver write, T-503 — absorb old .context/status/summary/failure)
├── metrics.jsonl          # event stream (driver append, NDJSON)
├── user_prompt.txt # INIT step WorkRequest prompt quote
├── plan/ # PLAN calculation (T-504 — directory nesting)
│ ├── plan.json # driver=JSON SSOT (driver determinism parsing target)
│ └── plan.md # LLM↔LLM=md (natural language text, WORK/VALIDATE/REPORT inject)
├── work/ # WORK output
│ ├── P1/W1.md # nested (T-503 recommended)
│   ├── P2/W1.md
│   └── ...
├── validate/ # VALIDATE calculation (T-503 — nesting)
│ ├── report.md # LLM Quality Evaluation Natural Language
│ ├── rules.json # driver 14+ rule evaluation result
│ └── code.json # driver pytest/ruff/mypy (implement only)
├── report.html # REPORT output (T-504 — person = HTML, template + placeholder)
└── workflow.log           # driver stdout/stderr append
```

### 4.2 Prompt injection matrix of the next step

| Step | File injected in its entirety into the text of the prompt |
|------|----------------------------------|
| INIT | (None — driver in-process) |
| PLAN | `metadata.json` (initial) + WorkRequest prompt (XML 5 fields) |
| WORK | `metadata.json` + `plan/plan.md` (full natural language text) + dependent work/`<deps>`.md (optional) |
| VALIDATE | `metadata.json` + `plan/plan.md` (whole) + `work/**/*.md` (whole) |
| REPORT | `metadata.json` + `plan/plan.md` + `work/**/*.md` + `validate/report.md` + `templates/report.html` (all in its entirety) |
| DONE | (None — driver in-process) |

### 4.3 Whole injection vs summary (avoiding LLM lossy compression)

Regression pattern in v1: PLAN output is delivered to worker as a “summary” → worker omits details of plan → incorrect implementation. production-line is **completely inject**. The context window burden is independent of the main session due to claude -p subprocess isolation.

What if I get close to the context window limit (200K tokens)? → N division of work/ directory by phase division + selective injection according to dependency graph (only REPORT applies to whole inject).

---

## 5. plan/ Directory structuring specification (T-504 cutover)

### 5.1 Separate output 2 files (driver=JSON / LLM↔LLM=md)

According to T-504 Canon SSOT (§3.2.0) the PLAN output is separated into 2 files:

- **`plan/plan.json`** — driver deterministic parsing target (SSOT). schema_version / work_request / command / mode / phases.
- **`plan/plan.md`** — WORK / VALIDATE / REPORT Natural language body for LLM handover (background / decision / diagram, etc.).

Old root `plan.md` (YAML frontmatter + body) completely discarded — backward compat 0 cases.

### 5.1.1 plan/plan.json schema (JSON, driver SSOT)

```json
{
  "schema_version": 2,
  "work_request": "WR-NNN",
  "command": "implement",
  "mode": "multi",
  "phases": [
    {
      "id": "P1",
      "title": "New core/_common",
      "deps": [],
      "deliverable": "work/P1/W1.md",
      "spawn_mode": "in_place",
      "workers": 1,
      "acceptance_criteria": [
        "Engine/apps/production_line/_common.py can be created + imported",
        "Work_dir/registry_key/command field exists in WorkflowContext dataclass",
        "pytest tests/application/production_line/test_common.py passed"
      ]
    },
    {
      "id": "P2",
      "title": "New core/_emitter",
      "deps": ["P1"],
      "deliverable": "work/P2/W1.md",
      "spawn_mode": "in_place",
      "workers": 1,
      "acceptance_criteria": [
        "New engine/apps/production_line/_emitter.py + emit(ctx, event, **kwargs) signature",
        "pytest tests/adapters/production_line/test_emitter.py passed"
      ]
    }
  ]
}
```

### 5.1.2 plan/plan.md text (Markdown, LLM↔LLM natural language)

driver does not parse. WORK / VALIDATE / REPORT LLM received full inject.
Recommended structure:
1. `## Canon SSOT` — Single rule/decision/table of this plan
2. `## Decision` — backward compat / cutover / schema branch decision
3. `## Output Mapping` — §3.2.1 6 area table citation
4. `## phase decomposition topology` — mermaid or ASCII
5. `## Details of each phase` — New file / Disposal / Migration
6. `## Danger Area + Avoidance`
7. `## Follow-up Track`

### 5.2 driver `parse_plan_json` verification (core/plan_loader.py)

- `phases` is required, if list is empty, `PlanLoaderError` → PLAN retry trigger
- The ID of `deps` must exist in the phases list (unknown → error)
- `deps` is prohibited from referencing itself (self → error)
- Phase id unique (duplicate → error)
- Determine execution order with topological sort (circular dep → error)
- `spawn_mode` default `in_place`
- **`acceptance_criteria` required (command=implement only, T-503)**: list[str], 1+ items. PLAN retry trigger when list is empty. Research/review is not applicable.
- `workers` default `1`. 2+ is worker N simultaneous spawn during phase (T-506). `parse_plan_json` checks for `workers >= 1`.
- `deliverable` recommended format: `work/<id>/W1.md` (T-503 directory nesting). `work/<id>.md` flat is also backward compat.
- Allow `deps` empty list. Sibling phases with the same `deps` are grouped at the same level with the driver `topo_levels` and can spawn simultaneously in subprocess mode (T-506).

### 5.3 spawn_mode Meaning

| value | meaning | effect |
|----|------|------|
| `in_place` (default) | Phase sequential processing within claude -p 1 subprocess of WORK Step | Reduce spawn overhead, preserve plan.md + full deps memory |
| `subprocess` (exception) | Separately only the relevant phase claude -p subprocess spawn | Tasks that require isolation (DB write, network call, large context, etc.) |

Plan.md determines whether WORK is in_place (LLM is specified when writing the phase). The driver decides X, just spawns as per the plan.md specification.

### 5.3.1 Meaning of workers (T-506 new)

| value | meaning | Output Path |
|----|------|-----------|
| `1` (default) | Single worker — existing route (regression 0) | `work/<id>/W1.md` (or flat `work/<id>.md`) |
| `N` (≥ 2) | N workers spawn simultaneously within phase (subprocess mode only) | Mandatory to write all `work/<id>/W1.md` ~ `work/<id>/W<N>.md` |

A phase with `workers > 1` is recommended for use with `spawn_mode=subprocess`. in_place mode processes phases sequentially within a single subprocess — workers > 1 meaningless (LLM produces N output within 1 subprocess).

driver implementation: `_spawn_one_phase` branch `phase.workers > 1` — `parallel_spawn(worker_indices, ...)` nested pool. Independent of external level pool (`max_parallel` guard).

Risk area: outer level pool (max=4) × inner workers pool (workers=N) → maximum simultaneous 4×N. Since it is not a CPU bound but a subprocess I/O bound, N×4 is safe from 8 to 12. Beyond that, the user is responsible for determining the specified plan.

---

## 6. Retry Policy

### 6.1 trigger

When the driver’s rule base verification function fails after each step is completed.

Example verification function (PLAN):
- `verify_plan_md()`: file exist + size > 0 + frontmatter YAML parse + `phases` not empty + deps DAG verification

### 6.2 Retry prompt template (rule base)

The driver collects verification-failed items into a list → Template fill:

```text
Verification of previous output failed. Missing/error items:
{missing_items}

Rewrite by filling in only the above items. Modification of other areas is prohibited.
Artifact Path: {artifact_path}
```

LLM does not create a retry prompt. The driver's `_render_retry_prompt(missing_items, artifact_path)` function fills deterministically.

### 6.3 claude -p --resume

- Preserve the session_id of the previous claude -p subprocess (driver state)
- When retrying, continue the same session with `claude -p --resume <session_id> <retry_prompt>`
- Preserve previous context (plan.md / attempt to create) while adding only missing items

### When exceeding 6.4 N_max

Write `Step FAILED` marker to status.json → Create `failure.md` (driver template) → End cycle → Conveyor WorkRequest remains Executing (waiting for user decision, automatic regression X).

### 6.5 Parallel spawn policy (T-506 new)

WORK Step inter-phase + intra-phase parallel spawn policy in subprocess mode. This policy does not apply to PLAN/VALIDATE/REPORT (single spawn).

#### 6.5.1 topo level simultaneous spawn (between phases)

`engine/apps/production_line/core/plan_loader.py: topo_levels(phases) -> list[list[Phase]]` groups deps graphs by level. driver `engine/apps/production_line/stations/work.py: _run_subprocess_mode` has:

1. Calculate `levels = topo_levels(phases)`
2. Call `parallel_spawn(level_phases, fn=spawn_one_phase, max_workers=get_max_parallel(), fail_fast=...)` for each level
3. Enter the next level after completing all phases

#### 6.5.2 Parallel worker in phase (workers > 1)

`_spawn_one_phase` is nested when `phase.workers > 1` `parallel_spawn(worker_indices, ...)` — N session_ids spawn simultaneously → Write all `work/<id>/W1.md` to `work/<id>/W<N>.md`. The inner pool's max_workers remains `phase.workers` (independent of the outer pool's `max_parallel` guard).

#### 6.5.3 fail_fast policy

When `get_fail_policy() == "fail_fast"` (default):
- Phase fail without level → future cancel at same level without starting (`ThreadPoolExecutor.shutdown(cancel_futures=True)`)
- After counting all outcomes at the same level, `any_fail` is True → Entry to the next level is blocked.

When `fail_tolerant` — run to the end of all phases in a level + also enter the next level (failure does not block level transition).

#### 6.5.4 emit matching

`_emitter.phase_start(ctx, phase_id, *, session_id="", worker_index=0, **extra)` / `phase_end(...)` is multi-session stuffed. Compatible with existing caller signature (default value → payload not included). `session_id` / `worker_index` fields added to NDJSON record in metrics.jsonl.

The `emit` function in `engine/apps/production_line/_emitter.py` is serialized to `threading.Lock` — Guaranteed line drop 0 when emitting simultaneously from multiple threads.

board POST endpoint (`/api/v2/sessions/<id>/phase`) body preserves T-495 P1 Canon compatibility — additional fields are stuffed only on the metrics.jsonl side.

#### 6.5.5 Running subprocess kill not applied (star track)

When `fail_fast`, `cancel_futures=True` **cancels only futures that have not started**. Claude -p subprocess that is already running continues to the end (does not force kill). This cycle means “block next level”. Force termination of a running subprocess is a star track (T-506 successor).

---

## 7. Driver.py responsibility division (v1 orchestrator → production-line driver mapping)

### 7.1 Mapping Table

| v1 Responsibilities (Main Session LLM) | production-line driver rule base implementation |
|---|---|
| `/wf -s N` trigger → INIT entry | argparse + `.context.json` template fill |
| Read WorkRequest prompt field | xml parser + dict access |
| command branch (implement/research/review/test) | str match → prompt template by command |
| mode branch (single/multi) | auto_router 8 signal → threshold rule (LLM call
| Enter PLAN stage + call planner subagent | `subprocess.run(["claude","-p",...])` |
| plan.md review | file exist + size + frontmatter schema |
| **plan.md decomposition (Phase·worker·deps)** | **frontmatter YAML parser → Phase list extraction** |
| **Determination of Dependency Graph** | frontmatter `deps` → topological sort |
| WORK Step worker N calls | `for phase in sorted_phases: spawn claude -p` |
| worker result inspection | `verify_artifact("work/{phase.id}.md")` |
| **worker output git commit** (New Stage 3-E) | **driver `auto_commit(ctx)`** — Deterministic `git -C <worktree> add -A` + `git commit -m "<template>"` immediately after WORK ends. 0 changes skip. Prohibition on LLM delegation (§0.1) |
| **Generate retry prompt** | **template fill: "missing = {missing}, rewrite"** |
| Retry decision | `retry_count < N and verify_fail` → resume |
| VALIDATE LLM Quality Evaluation | claude -p — `validate/report.md` natural language output (phase decomposition adequacy / deliverable completeness / deps flow). **14+Responsibility for rule evaluation, code verification, and verdict calculation X (§0.1)** |
| **14+rule evaluation + verdict calculation** | **driver `evaluate_rules` + `save_verdict_report` (validate/rules.json)** — Called inside DONE step finalize (REPORT completion + step.end DONE registration point after record, T-490 regression correction §9.2). **LLM delegation 0 cases (§0.1)** |
| **Code determinism verification (pytest/ruff/mypy)** | **driver `_verify_code.py` (T-503)** — produces `validate/code.json`. implement limited (research/review SKIP). Tool not installed/no settings → graceful SKIP. |
| **R-CODE-1 + R-CODE-2 Evaluation** | **driver `_validate.py` (T-503)** — Rulebase evaluation of `tool: pytest` / `tool: ruff` results of `validate/code.json`. R-CODE-1 = pytest passed hard-fail / R-CODE-2 = lint clean advisory. |
| REPORT reporter subagent | `subprocess.run(["claude","-p",...])` |
| report.md comprehensive | verify + size match (whole inject verification) |
| finalize (summary + usage) | `summary.txt` template + `usage.json` aggregate |
| conveyor transition (Executing → Verifying) | conveyor CLI subprocess |
| Regression Processing | conditional + `metrics.jsonl` emit |
| User Progress Reporting | driver stdout + SSE event emit |
| PreToolUse hook absorption | **hook self-disposal** — driver deterministic progress |
| Task subagent call | **Discard the entire SDK Task** → claude -p subprocess |
| `.claude/agents/*.md` definition | **Totally discarded** — Replaced with claude -p prompt template |

### 7.2 driver.py pseudocode

```python
def main(work_request_no: str) -> int:
    # 1. INIT (driver in-process, LLM calls X)
    ctx = init_step(work_request_no)
    conveyor_move(work_request_no, "executing")
    update_status(ctx, "INIT", "PLAN")

    # 2. PLAN
    plan_md = spawn_with_retry(
        step="PLAN",
        prompt=render_plan_prompt(ctx),
        artifact="plan.md",
        verify=verify_plan_md,
        n_max=2,
    )
    plan = parse_plan_frontmatter(plan_md)
    update_status(ctx, "PLAN", "WORK")

    # 3. WORK (Phase loop, in_place or subprocess)
    if any(p.spawn_mode == "subprocess" for p in plan.phases):
        # Isolation mode — Separate spawn for each phase
        for phase in topo_sort(plan.phases):
            work_md = spawn_with_retry(
                step="WORK",
                phase=phase,
                prompt=render_work_prompt(ctx, plan, phase, load_deps(phase)),
                artifact=f"work/{phase.id}.md",
                verify=verify_work_md,
                n_max=3,
            )
    else:
        # default — claude -p 1 Sequential processing within subprocess
        work_outputs = spawn_with_retry(
            step="WORK",
            prompt=render_work_prompt(ctx, plan, all_phases=plan.phases),
            artifact_set=[f"work/{p.id}.md" for p in plan.phases],
            verify=verify_work_set,
            n_max=3,
        )
    auto_commit(ctx) # Stage 3-E §0.1 — Deterministic commit of worker output (skip 0 changes)
    update_status(ctx, "WORK", "VALIDATE")

    # 4. VALIDATE — LLM evaluates quality only in natural language (§0.1, 12 rule evaluations 0)
    validate_md = spawn_with_retry(
        step="VALIDATE",
        prompt=render_validate_prompt(ctx, plan, load_all_work()),
        artifact="validate-report.md",
        verify=verify_validate_md,
        n_max=1,
    )
    update_status(ctx, "VALIDATE", "REPORT")

    # 5. REPORT — LLM receives the entire plan+work+validate(Quality) inject and synthesizes natural language
    report_md = spawn_with_retry(
        step="REPORT",
        prompt=render_report_prompt(ctx, plan, load_all_work(), validate_md),
        artifact="report.md",
        verify=verify_report_md,
        n_max=2,
    )
    update_status(ctx, "REPORT", "DONE")

    # 6. DONE (driver in-process) — 12 rule evaluation + verdict calculation (§0.1)
    verdict = evaluate_12_rules(ctx)
    save_verdict_report(ctx, verdict)  # validate-rules.json — SSOT
    finalize(ctx)
    conveyor_move(work_request_no, "verifying")
    return 0
```

---

## 8. claude -p subprocess interface

### 8.1 spawn call pattern

```python
result = subprocess.run(
    [
        "claude", "-p",
        "--session-id", session_id, # Unique for each step (reused when retrying)
        "--append-system-prompt", system_prompt, # production-line Only the core of SKILL.md (less than 10KB cap)
        prompt_body, # plan.md / work/* / inject the entire validate-report.md
    ],
    cwd=ctx.work_dir,
    timeout=ctx.step_timeout, # By Step (PLAN 5min, WORK 30min, VALIDATE 3min, REPORT 10min)
    capture_output=True,
)
```

### 8.2 session_id management

- The driver generates session_id for each Step + Phase: `wf-T489-PLAN`, `wf-T489-WORK-P1`, `wf-T489-WORK-P2`, ...
- When retrying, continue the same session with `--resume <session_id>`
- Session storage location: Claude CLI default (`~/.claude/projects/...`) — Driver manages path

### 8.3 Delivery of system prompt

The problem of v1's SKILL.md (15KB) being truncated to SDK cap (10KB) → production-line is **the system prompt for each step is separate** + 10KB or less.

- `engine/apps/production_line/prompts/plan.txt` (PLAN system prompt, target 5KB)
- `engine/apps/production_line/prompts/work.txt`
- `engine/apps/production_line/prompts/validate.txt`
- `engine/apps/production_line/prompts/report.txt`

The driver is sent to `--append-system-prompt`. SDK cap avoidance is certain.

### 8.4 Where to write output

`cwd` = `ctx.work_dir` (= `.agent-factory/runs/<key>/`) in claude -p subprocess. The prompt specifies "Path to output = `plan.md`" or "`work/P1.md`". claude -p writes directly with the Write/Edit tool.

---

## 9. VALIDATE 14+Rule Canon (rule-based, T-503 expansion)

T-463 12 rules (already stuffed in v1) + T-503 new R-CODE-1/2. However, some rule names have been corrected to the `workflow_step` vocabulary.

| Category | ID | rules | hard-fail? | command branch |
|---------|----|----|----------|-------------|
| R-EXIST | R-EXIST-1 | report.md exists | YES | All |
| R-EXIST | R-EXIST-2 | plan.md exists (research SKIP) | NO | research SKIP |
| R-EXIST | R-EXIST-3 | status.json exists + `workflow_step` key | NO | All |
| R-EXIST | R-EXIST-4 | metrics.jsonl exists ≥ 1 line | NO | All |
| R-METRIC | R-METRIC-2 | last step.end{step=DONE}.outcome == "ok" | YES | All |
| R-METRIC | R-METRIC-3 | tool.deny 0 cases | NO | All |
| R-GUARD | R-GUARD-1 | worktree mode active | NO | research/review SKIP |
| R-GUARD | R-GUARD-2 | feature branch exists | NO | If feature_branch does not exist, SKIP |
| R-GUARD | R-GUARD-3 | regression.pattern 0 cases | NO | All |
| R-PATH | R-PATH-1 | report.md → plan.md link matching (research, etc.) | NO | research SKIP |
| R-FSM | R-FSM-1 | status.json `workflow_step` ∈ {DONE, FAILED} | NO | All |
| R-WT | R-WT-1 | commits ahead ≥ 1 (command=implement) or SKIP | YES (implementation only) | research/review SKIP |
| **R-CODE** | **R-CODE-1** | **pytest passed (tool=pytest in `validate/code.json`, status ∈ {ok, skip})** | **YES (implementation only)** | **research/review SKIP** |
| **R-CODE** | **R-CODE-2** | **lint clean (tool=ruff in `validate/code.json`, status ∈ {ok, skip} or counts==0)** | **NO (advisory FAIL)** | **research/review SKIP** |

### 9.1 verdict (advisory only, T-503 critical recalculation)

- PASS: 14+ 0 rule violations
- WARN: 1~2 rule violation (0 hard-fail cases)
- FAIL: 3+ rule violation or one or more hard-fail cases
- SKIP: `workflow_step` ∉ {DONE, FAILED}

> **Critical recalculation (T-503)**: WARN 1~2 / FAIL 3+ criticality is the same even after expansion from 12 rules → 14+ rules. hard-fail rules = `R-EXIST-1` + `R-METRIC-2` + `R-WT-1` + `R-CODE-1` 4 types.

Even if the verdict is FAIL, you can still proceed with Verifying→Complete DnD (advisory only). Auto guard/auto regression: 0 cases.

### 9.1.1 worktree policy (branching by command, T-489 Stage 3-D)

User-specified policy (2026-05-15): **Worktree isolation is required for tickets whose workflow involves code changes, worktree-less is allowed for research/review tickets**.

| command | worktree branch | feature_branch | R-WT-1 Evaluation |
|---------|--------------|---------------|------------|
| `implement` | `git worktree add` + create feature_branch (driver init_step) | `feat/WR-NNN-<title>` | **hard-fail** (commits ahead ≥ 1 obligation) |
| `research` | Create work tree X (develop directly) | `null` | SKIP (`research` mark) |
| `review` | Create work tree X (develop directly) | `null` | SKIP (`review` mark) |

Call `worktree_manager.create_worktree(work_request_no, title, command=...)` inside driver `init_step` and return None if `command != "implement"` → ctx.feature_branch=null + work_dir is main `.agent-factory/runs/<key>/`. If `command == "implement"`, ctx.feature_branch + work_dir is not in `<worktree_path>/.agent-factory/runs/<key>/`.

### 9.2 When to evaluate (DONE stage)

The call to the driver rule base `evaluate_rules` (T-503 — old `evaluate_12_rules`) is performed **inside the DONE Step** (inside the `done_step` function, after recording `step_end DONE outcome=ok` + after `update_step(_, "DONE")` + before `conveyor_move review`).

reason:
- R-EXIST-1 (`report.md` exists) — Match only after completion of the REPORT step
- R-METRIC-2 (`step.end DONE outcome=ok`) — Match only after recording DONE step.end
- R-FSM-1 (`workflow_step ∈ {DONE, FAILED}`) — Match only after `update_step("DONE")`
- R-CODE-1/2 — After calculating `validate/code.json` (driver calls `_verify_code.py` in VALIDATE Step → R-CODE rule evaluation in DONE step)

The `validate_step` function of VALIDATE Step is (1) `claude -p (advisory)` 1 spawn to create `validate/report.md` free prose + (2) driver calls `_verify_code.run(ctx)` → `validate/code.json` output (implement only). Driver 14+ rule evaluation is not performed at this stage — delayed to the DONE stage.

### 9.3 Output Separation Cannon (T-503 — 3 Type Separation)

> User specified (2026-05-18): The deliverable format is **separated into 3 areas**, with each area having a single responsibility.

| Format | area | responsibility |
|------|------|------|
| **JSON** | `metadata.json` / `validate/rules.json` / `validate/code.json` / `usage.json` | Driver determinism evaluation, metadata, and code verification results. Machine readability priority. |
| **Markdown (natural language)** | `plan.md` / `work/<phase>/W<n>.md` / `validate/report.md` / `report.md` | LLM Natural Language Production. Human read + LLM Next Step inject read. |
| **HTML render (viewer responsibility)** | T-502 board UI viewer | Combining JSON and Markdown to render user-readable cards/tabs. Bone track out of range — star track. |

Formats other than the above 3 areas (e.g. CSV / YAML / old `summary.txt` / old `failure.md` / old `validate/code.md`) are prohibited from being introduced. Human readability is clearly separated into the responsibility of the board UI viewer.

Mapping by deliverable:
- `validate/report.md` = advisory natural language evaluation of claude -p (LLM) (VALIDATE step, T-503 directory nesting)
- `validate/rules.json` = Evaluate rule base determinism of driver (DONE step, T-503 directory nesting)
- `validate/code.json` = Deterministic code verification of driver `_verify_code.py` (driver call within VALIDATE step, T-503 newly established)

---

## 10. Five types of regression blocking verification

T-489 prototype verification criteria. Confirm automatic blocking during 1 cycle finalize.

| regression pattern | blocking mechanism |
|----------|-------------|
| `worker_false_success` | Verify driver's `verify_artifact` rule base (file size > 0, regex match) |
| `hook_deny` | Hook self-disposal (production-line depends on hook
| `empty_bash_card` | claude -p writes directly to the output file, Board UI's bash card dependency
| `stage_header_leak` | driver controls stdout, Step header format driver template fill |
| `worktree_commit_missing` | R-WT-1 hard-fail promotion (commits ahead ≥ 1 obligation) |

---

## 11. Disappearing infrastructure (v1 → entire production-line discarded)

If remnants of v1 are still alive after revert (b69645a base), further discard:

### 11.1 Subject to complete deletion

- `.claude/agents/*.md` 9 files (subagent definition)
- `engine/workflow_hooks/` (discarded again if alive after revert)
- `engine/banners/` (Step header output script — absorbed into driver template)
- Task subagent branch of `engine/hooks/dispatcher.py`
- All SDK Task calls
- `system-prompt-wf.xml` (already discarded, not revived)
- `flow-init` / `flow-update` / `flow-phase` / `flow-step` / `flow-finish` / `flow-launcher` 6 wrapper (integrated into driver)

### 11.2 New wrapper

- `flow-wf` single entrypoint (`.agent-factory/bin/flow-wf`)
- Call: `flow-wf submit WR-NNN` → `python3 -m engine.apps.production_line WR-NNN`
- Existing `/wf` slash commands are preserved (user interface), internally calling `flow-wf submit`

### 11.3 What to preserve

- `engine/core/` — Some v1 core modules can be reused within the driver (path helper in `_common.py`, etc.). However, the production-line driver only uses specification-violating code.
- `engine/guards/` — finalize guards (R-WT-1, etc.) are called by the driver.
- `engine/flow/` — conveyor CLI / conveyor data model preservation
- `engine/git/` — Preserve git helpers
- `engine/sync/` — Preserve history sync
- `engine/memory_gc/` — Memory GC retention
- VALIDATE 12 rule evaluation code (T-463 main body) preservation

---

## 12. Interface

### 12.1 CLI

```bash
# User entry
flow-wf submit WR-NNN # Execute Step 0~6 (driver spawn)
flow-wf submit WR-NNN --step PLAN # Execute only specific Steps (debug)
flow-wf status WR-NNN # Check progress status (status.json read)
flow-wf abort WR-NNN # abort cycle (claude -p subprocess kill + status FAILED)
```

### 12.2 Slash command

`/wf -s N` → `.agent-factory/bin/flow-wf submit T-N` call. The main session is triggered only, and progress is made by driver.

### 12.3 SSE event (Board UI)

Driver emits NDJSON to stdout → Board server sends client to SSE:

```json
{"event":"step.start","step":"PLAN","work_request":"WR-489","ts":"2026-05-14T..."}
{"event":"step.end","step":"PLAN","outcome":"ok","retry_count":0,"ts":"..."}
{"event":"phase.start","step":"WORK","phase":"P1","ts":"..."}
{"event":"phase.end","step":"WORK","phase":"P1","outcome":"ok","ts":"..."}
{"event":"workflow.finish","outcome":"ok","verdict":"PASS","ts":"..."}
```

Both workflow-bar / conveyor verdict badges in Board UI are updated to this stream.

### 12.4 conveyor transition

- When entering INIT: `conveyor move WR-NNN executing` (driver)
- When DONE ends: `conveyor move WR-NNN verifying` (driver)
- Upon termination of FAILED: conveyor automatic regression

---

## 13. Directory structure (new)

```
.agent-factory/engine/apps/production_line/
├── SPEC.md # This document (SSOT)
├── driver.py # Entry point + 6 Step orchestration
├── _common.py                 # path helper, conveyor CLI wrapper, status I/O
├── _emitter.py                # SSE event NDJSON emit
├── _verify.py # Collection of rule base output verification functions
├── _retry.py # Retry prompt template + claude -p --resume
├── _spawn.py                  # claude -p subprocess.run wrapper
├── steps/
│   ├── init.py
│   ├── plan.py
│   ├── work.py
│   ├── validate.py
│   ├── report.py
│   └── done.py
├── prompts/ # claude -p system prompt (less than 10KB for each step)
│   ├── plan.txt
│   ├── work.txt
│   ├── validate.txt
│   └── report.txt
├── templates/ # Output template that the driver fills
│   ├── retry_prompt.txt
│   ├── summary.txt
│   └── failure.md
└── tests/
    ├── test_driver.py
    ├── test_spawn.py
    ├── test_verify.py
    └── test_retry.py
```

---

## 14. Milestones (Phase 0~3)

### Phase 0 — Secure revert base (complete)

- WR-489 Draft → Accepted
- develop reset --hard b69645a (39 commit revert, user specified exception)
- Delete T-488 (T-486 subject to verification disappears)
- working tree clean, push hold

### Phase 1 — Production-line specification stuffed (in progress)

- Newly created `engine/apps/production_line/SPEC.md` (this document)
- Updated `.claude/rules/workflow/workflow.md` (Orchestrator section → driver, Step/Phase vocabulary correction)
- New memory `project_workflow_v2_orchestrator_to_driver_canon.md` created

### Phase 2 — driver prototype implementation

- `driver.py` + `_common.py` + `_emitter.py` + `_verify.py` + `_retry.py` + `_spawn.py`
- `steps/init.py` + `steps/plan.py` + `steps/work.py` + `steps/validate.py` + `steps/report.py` + `steps/done.py`
- `prompts/*.txt` (each Step system prompt)
- `templates/*` (driver fill output)
- `tests/test_*.py` (unit tests)
- `.agent-factory/bin/flow-wf` wrapper

### Phase 3 — 1 cycle finalize verification

- Create 1 new WorkRequest for verification (T-490 candidate, simple implement)
- Execute `flow-wf submit WR-490` → driver proceeds through all 6 steps
- Verification of consistency of 5 types of output: plan.md / work/*.md / validate-report.md / report.md / .context.json
- Verification of 5 types of regression blocking (R-WT-1 + worker_false_success, etc.)
- Measure token usage (compared to v1 SDK Task model 1 cycle)
- Create token usage/determinism/context isolation report compared to v1

### Follow-up milestones

- Phase 4 — Verification of multi-phase isolation mode (`spawn_mode: subprocess`)
- Phase 5 — Block multi-cycle simultaneous submission race (block registryKey conflict regression)
- Phase 6 — Board UI workflow-bar production-line application (SSE event mapping)
- Phase 7 — single mode (multiple discard vs preservation decisions)

---

## 15. Consistency rules for this document

### 15.1 SSOT priority

In case of conflict between this document and another document, this document takes precedence. Update other documents.

### 15.2 Change Procedure

- Production-line specification change = update of this document + user agreement
- No voluntary renewal without agreement (general.md “no guessing” rule applied)
- When making changes, record the date, item, and basis in the `## Change History` section.

### 15.3 v1 Legacy Reference

When referencing v1 regression examples within this document, quote the commit hash or memory file name. No speculative quotations allowed.

### 15.4 Stage 3-E Verification Procedure

The operation of Stage 3-E (§0.1 Separation of Responsibility Canon Taxidermy) is verified by finalizing a simple output WorkRequest 1 cycle, such as this T-494. On the driver side, 12 rule evaluation, verdict calculation, git commit (auto_commit), conveyor transition, and FSM transition are all performed deterministically, and at the same time, claude -p subprocess (PLAN/WORK/REPORT) is passed if only the natural language part of the output .md body is written and does not violate the driver's responsibility. The core of this procedure is to check whether regressions such as the conflict between the LLM verdict and the driver verdict found in T-493 smoke (violation of the rule that validate.txt evaluated 12 rules to LLM + omission of git commit in work.txt) have disappeared. For detailed division of responsibility, refer to §0.1 / §3.2 (Responsibility by Step) / §7.1 (driver.py mapping).

---

## Change history

| date | Item | Evidence |
|------|------|------|
| 2026-05-14 | Production-line 1.0.0 Draft (T-489 Phase 1) | User insight sequence (abolish orchestrator → claude -p model → file-based pipeline → complete injection → retry rule base) |
| 2026-05-15 | §7.1 + §9.2 — driver rule base 12 Rule re-verification period corrected to VALIDATE → DONE stage | T-490 Phase 3 verification regression discovered (3 false FAILs due to report.md / step.end DONE not being created when evaluate is called at the time of VALIDATE = R-EXIST-1 / R-METRIC-2 / R-PATH-1) |
| 2026-05-15 | §9.1.1 — Introducing worktree branching policy for each command (Stage 3-D) | T-489 Stage 3-D — implement obligation / research·review worktree-less / R-WT-1 SKIP coordination (commit e73dfc1 + 79bf36d) |
| 2026-05-15 | §0.1 New responsibility sharing canon (Stage 3-E) — driver=12 rules+commit+conveyor+FSM determinism / LLM=natural language calculation only. §3.2 / §7.1 / §7.2 matching | LLM verdict (WARN) ≡ driver verdict (FAIL) conflict discovered in T-493 smoke. Validate.txt violates the rule that LLM evaluates 12 rules and calculates verdict + missing git commit in work.txt. User specified canon taxidermy (commit ? + ?) |
| 2026-05-18 | T-503 — §0.1 / §0.1.1 / §0.1.2 / §3.2 / §3.2.1 / §3.2.2 / §5.1 / §5.2 / §7.1 / §9 / §9.2 / §9.3 Update — 12 rules → 14+ rules (R-CODE-1/2), output 6 areas + discard 5 files, verification 2-axis separation (natural language report LLM / determinism code driver), TDD enforcement (acceptance_criteria + Red→Green→Refactor) | User-specified Canon extension (output consistency + verification 2-axis separation + forced TDD prompt). This cycle itself processes the old driver — R-CODE applies the next cycle. |
| 2026-05-19 | T-504 — §3.2.0 (format decision canon SSOT) / §3.2.1 / §3.2.2 / §3.2 Step responsibility / §3.4 PLAN N_max / §4.1 directory / §4.2 prompt injection matrix / §5 plan/ directory structuring (5.1 / 5.1.1 JSON schema / 5.1.2 plan.md body / 5.2 driver parse_plan_json) — Output Format Canon SSOT Taxidermy (driver=JSON / LLM↔LLM=md / person=HTML). Discard old root `plan.md` (YAML) + old `report.md` (Markdown) cutover. New `plan/plan.json` + `plan/plan.md` + `report.html` (template + placeholder). | User specified (2026-05-18) “Who reads → format decision” single rule. T-489 cutover policy consistent — backward compat shim 0 cases. P1~P6 of this cycle migrates the entire driver `parse_plan_json` + `core/plan_loader.py` + `templates/report.html` + verification function (`verify_plan_artifacts` / `verify_report_html`) + prompts (plan.txt / report.txt). |
| 2026-05-19 | T-506 — §3.4.1 New parallel spawn policy (`max_parallel` default 4 + `V2_MAX_PARALLEL` / `fail_policy` default `fail_fast` + `V2_FAIL_POLICY` env override). §5.2 Specifies `workers >= 1` + `deps=[]` siblings matching. §5.3.1 New `workers` semantic table (1=single / N=N worker simultaneous spawn, `work/<id>/W<n>.md` output matrix). §6.5 New parallel spawn policy (6.5.1 topo level simultaneous spawn / 6.5.2 worker parallel within phase / 6.5.3 fail_fast / 6.5.4 emit matching / 6.5.5 running subprocess kill not applied). | T-506 User-specified decision — Planner LLM determines deps + workers between phases in plan.json. driver has deterministically same level simultaneous spawn + workers > 1 nested pool. New infrastructure: `engine/apps/production_line/_parallel.py` (parallel_spawn) + `engine/apps/production_line/core/plan_loader.py: topo_levels` + `engine/apps/production_line/_common.py: get_max_parallel/get_fail_policy` + `engine/apps/production_line/_verify.py: verify_work_md_multi`. Decided not to adopt asyncio (subprocess I/O bound + preserving existing `_spawn` synchronous infrastructure). |
