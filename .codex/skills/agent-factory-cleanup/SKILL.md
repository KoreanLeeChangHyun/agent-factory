---
name: agent-factory-cleanup
description: Use when cleaning, moving, deleting, or reorganizing files in this repository. Applies Agent Factory source/runtime separation, reference checks, compatibility wrappers, and focused validation before removing directories or changing paths.
---

# Agent Factory Cleanup

Use this skill for repository cleanup, directory moves, path consolidation, and dead asset removal.

## Principles

- Separate source assets from runtime state.
- Keep runtime outputs out of source decisions: `.agent-factory/runs`, `.agent-factory/logs`, `.agent-factory/worktrees`, `.agent-factory/staging`, caches, and local sqlite/log files are state.
- Do not delete a path until `rg` confirms runtime, tests, docs, and UI references are understood.
- Move code to a more truthful boundary before deleting compatibility paths.
- Preserve user changes already present in the worktree.

## Workflow

1. List files and size with `find`/`du`.
2. Search references with `rg`, excluding generated/runtime directories where needed.
3. Classify each path as source, template, config, runtime state, cache, docs, or compatibility shim.
4. For source moves, update imports and docs; keep wrappers when callers still rely on old imports.
5. For runtime/cache cleanup, update `.gitignore` instead of committing local state.
6. Verify with focused import checks, `py_compile`, or tests for the touched boundary.

## Red Flags

- A directory name is generic but contains executable imports.
- UI/API paths refer to a directory as editable user data.
- A deleted file is imported by hooks or guards.
- A runtime cleanup would erase user history without an explicit retention decision.

