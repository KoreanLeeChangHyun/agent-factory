---
name: agent-factory-hooks-guards
description: Use when changing Agent Factory Claude hook entrypoints, guard scripts, permission decisions, hook dispatchers, or hook-related tests. Keep hook JSON schemas stable and guard messages/imports reliable.
---

# Agent Factory Hooks And Guards

Use this skill for `.agent-factory/hooks`, `.agent-factory/engine/apps/hooks`, `.agent-factory/engine/adapters/hooks`, and `.agent-factory/engine/guards`.

## Boundary Rules

- Top-level `.agent-factory/hooks/*.py` files are compatibility entrypoints.
- Shared hook dispatch behavior belongs in `engine/adapters/hooks`.
- Hook app logic belongs in `engine/apps/hooks`.
- Guard scripts belong in `engine/guards`.
- User-facing deny messages should live near guard code, not in generic prompt/template directories.

## Workflow

1. Preserve executable entrypoint behavior and stdin/stdout contracts.
2. Keep `hookSpecificOutput` schema stable for allow/deny responses.
3. Avoid adding `updatedInput` unless the canonical contract explicitly requires it.
4. Use concise deny reasons that tell the user what to do next.
5. Run focused hook tests after schema or guard behavior changes.

## Common Checks

- `python3 -m pytest .agent-factory/tests/adapters/hooks`
- `python3 -m pytest .agent-factory/tests/application/apps/test_hooks_*.py`
- `python3 -m py_compile .agent-factory/hooks/*.py .agent-factory/engine/guards/*.py`

