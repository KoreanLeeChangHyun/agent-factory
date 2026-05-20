# flow-* CLI Reference

This page lists active `.agent-factory/bin` wrappers. Removed V1 lifecycle
wrappers such as `flow-init`, `flow-step`, `flow-phase`, `flow-finish`,
`flow-reload`, and `flow-recommend` are not part of the current operator
contract.

## Quick Reference

| wrapper | usage | purpose |
|---|---|---|
| `flow-wf` | `flow-wf submit T-NNN [--step STEP]` | Start the V2 workflow driver for one WorkRequest. |
| `flow-launcher` | `flow-launcher T-NNN [--step STEP]` | Compatibility entry wired to the same V2 driver. Prefer `flow-wf`. |
| `flow-kanban` | `flow-kanban <subcommand> ...` | Manage WorkRequest XML files and board columns. |
| `flow-validate` | `flow-validate [plan_path]` or `flow-validate --mode ticket` | Validate plans or WorkRequest XML contracts. |
| `flow-validate-p` | `flow-validate-p <xml_path>` | Validate one WorkRequest prompt XML file. |
| `flow-review-verdict` | `flow-review-verdict <registry_key>` | Run advisory review verdict checks for a workflow run. |
| `flow-migrate-runs` | `flow-migrate-runs dry-run|apply [--backup] [--verify]` | Flatten legacy run history directories. |
| `flow-merge` | `flow-merge ...` | Run merge/review pipeline helpers. |
| `flow-metrics` | `flow-metrics ...` | Inspect workflow metrics. |
| `flow-history` | `flow-history ...` | Inspect workflow history. |
| `flow-gc` | `flow-gc [project_root]` | Garbage collect workflow runtime data. |
| `flow-memory-gc` | `flow-memory-gc ...` | Maintain memory GC artifacts. |
| `flow-catalog` | `flow-catalog ...` | Sync or inspect catalog data. |
| `flow-skill` | `flow-skill ...` | Manage skill activation state. |
| `flow-skillmap` | `flow-skillmap <registry_key>` | Map skills for a run. |
| `flow-detect` | `flow-detect ...` | Detect workflow/project state. |
| `flow-gitconfig` | `flow-gitconfig ...` | Manage git configuration helpers. |
| `flow-undo-done` | `flow-undo-done ...` | Move a completed WorkRequest back from Done. |
| `flow-claude-edit` | `flow-claude-edit open|save|diff|new <path>` | Controlled edit path for `.claude/` integration files. |

## Workflow Driver

`flow-wf` is the canonical workflow entrypoint.

```bash
flow-wf submit T-123
flow-wf submit T-123 --step PLAN
```

The driver executes the current six-stage model:

```text
PREPARE -> PLAN -> EXECUTE -> VERIFY -> REPORT -> COMPLETE
```

Status files may still expose V2 step names for compatibility:

```text
INIT -> PLAN -> WORK -> VALIDATE -> REPORT -> DONE
```

Use the canonical stage names in new documentation and domain/application code.

## WorkRequest Board

`flow-kanban` is the active CLI for WorkRequest XML storage.

```bash
flow-kanban create
flow-kanban list
flow-kanban show T-123
flow-kanban move T-123 progress
flow-kanban done T-123
```

Run `flow-kanban <subcommand> --help` for subcommand-specific arguments.

## Validation

Plan validation:

```bash
flow-validate .agent-factory/runs/20260520-120000/plan/plan.md
flow-validate 20260520-120000
```

WorkRequest validation:

```bash
flow-validate --mode ticket
flow-validate --mode ticket --ticket T-123
flow-validate-p .agent-factory/tickets/progress/T-123.xml
```

## Review Verdict

```bash
flow-review-verdict 20260520-120000
flow-review-verdict 20260520-120000 --workdir .agent-factory/runs/20260520-120000
```

The command is advisory. Blocking completion decisions are owned by the VERIFY
and REPORT artifacts produced by the V2 driver.

## Run Migration

```bash
flow-migrate-runs dry-run
flow-migrate-runs apply --backup --verify
```

Use this only for legacy `.agent-factory/runs/.history` directory shape cleanup.

## Provider-Specific Helpers

`flow-claude-edit` remains because `.claude/` is the Claude Code integration
surface. It is not part of the core factory runtime and must not be imported by
domain or application modules.

```bash
flow-claude-edit open rules/workflow/general.md
flow-claude-edit diff rules/workflow/general.md
flow-claude-edit save rules/workflow/general.md
flow-claude-edit new rules/workflow/new-rule.md
```
