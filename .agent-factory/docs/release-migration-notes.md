# M10 Release And Migration Notes

## Summary

M10 closes the Agent Factory refactor by removing stale active guidance and
locking architecture boundaries with tests.

Current operator entrypoints:

- `flow-wf submit T-NNN` for workflow execution
- `flow-kanban` for WorkRequest board storage
- `flow-validate` and `flow-validate-p` for deterministic checks
- `flow-review-verdict` for advisory review checks
- `flow-claude-edit` only for `.claude/` integration file edits

Canonical report artifacts are HTML:

- workflow detail views expose `report.html`
- ticket drag-and-drop attachments fetch `report.html`
- legacy `report.md` references are historical only

## Removed Or Retired

- The broken `flow-claude` banner wrapper was removed.
- Removed V1 lifecycle wrappers are not active CLI surface:
  `flow-init`, `flow-step`, `flow-phase`, `flow-finish`, `flow-reload`, and
  `flow-recommend`.
- Historical V1 notes remain only as archived refactor context, not active
  implementation guidance.

## Migration Guidance

Replace old lifecycle calls with the V2 driver:

```bash
flow-wf submit T-123
```

Use `--step` only for controlled debugging:

```bash
flow-wf submit T-123 --step VERIFY
```

Use canonical stage vocabulary in new docs and code:

```text
PREPARE -> PLAN -> EXECUTE -> VERIFY -> REPORT -> COMPLETE
```

Compatibility status files may still contain:

```text
INIT -> PLAN -> WORK -> VALIDATE -> REPORT -> DONE
```

Do not add direct provider calls, subprocess calls, board handlers, or V2
runtime imports to `engine/core` or `engine/application`. Provider-specific
code belongs under adapters.

## Verification

M10 adds architecture boundary checks under `tests/architecture/`. Canonical
verification is:

```bash
cd .agent-factory
python3 -m pytest
```
