# V1 Removal Inventory

## Policy

V1 is removed, not preserved. Compatibility shims are allowed only when V2
currently imports a utility and the shim has a deletion target.

## Known Stale Test Groups

These tests currently describe removed V1 modules or old wrappers:

| Path | Issue | Action |
|---|---|---|
| `engine/flow/tests/test_failure_handler.py` | imports removed `flow.failure_handler` | delete or rewrite for V2 failure handling |
| `engine/flow/tests/test_fsm_8state.py` | imports removed `flow.initialization` | rewrite against `engine.v2._common.update_step` |
| `engine/flow/tests/test_http_launcher_timeout.py` | imports removed `flow.http_launcher` | delete; V2 launcher tests live under `tests/contracts/board_api` and `tests/adapters/v2` |
| `engine/flow/tests/test_sessions_status.py` | imports removed `flow.sessions` | rewrite against V2 session registry |
| `engine/flow/tests/test_stop.py` | imports removed `flow.stop` | rewrite against V2 session finish/delete behavior |
| `engine/flow/tests/test_phase_verifier.py` | expects missing `bin/flow-phase-verify` | delete wrapper expectation or migrate to V2 validation tests |
| `board/tests/test_handlers_t424.py` | references removed `workflow_undo` handler | rewrite against `/api/kanban/undo-done` |
| `board/tests/test_v2_*` | package import collision under old `board/tests` | rewrite into canonical `tests/contracts/board_api` if still relevant, or remove duplicate package layout |
| `engine/guards/tests/*` | package import collision under old test root | move into canonical test tree if still relevant |
| `engine/tests/hooks/*` | package import collision under old test root | move into canonical hook adapter tests |

## Known V1 Documentation

These files still mention V1 or old entrypoints:

| Path | Action |
|---|---|
| `.claude-organic/docs/cli-reference.md` | replace with V2 `flow-wf` and current `flow-*` wrappers |
| `.claude/commands/wf.md` | remove residual V1 notes after V2 command behavior is documented |
| `.claude-organic/build-assets/templates/claude-env.tmpl` | remove old `flow-init/flow-step/flow-finish` lifecycle comments |
| `.claude-organic/board/static/js/workflow/workflow-bar.js` | remove V1 wording once UI contract is V2-only |
| `.claude-organic/board/static/js/workflow/session.js` | remove V1 history/session comments after route cleanup |

## Shared Code That May Stay Temporarily

`engine/flow` is not automatically deleted as a directory because V2 still uses
some mature utilities:

- `worktree_manager.py`
- `kanban.py` and `kanban_cli.py`
- `merge_pipeline.py`
- `review_verdict.py`
- `phase_verifier.py` until V2 validation fully replaces it
- `worker_return_parser.py` only if current V2 paths still emit or parse it

Each retained module needs one of these outcomes:

- move into `engine/core/adapters`
- move into `engine/core/application`
- delete after V2 equivalent exists

## First Safe Cleanup Batch

The first removal batch should avoid runtime behavior changes:

1. Delete or move stale V1 tests excluded by `pytest.ini`.
2. Consolidate surviving tests under one canonical `tests/` root.
3. Update CLI docs to mark `flow-wf submit T-NNN` as the canonical entry.
4. Remove references to missing wrappers such as `flow-phase-verify`.
5. Keep current V2 runtime files untouched.
6. Re-run canonical pytest.

## Test Directory Consolidation

The scattered test layout is itself a refactor target. It currently causes
pytest package-name collisions because several directories expose a `tests`
package from different import roots.

Target:

```text
.claude-organic/tests/
  domain/
  application/
  adapters/
  contracts/
  e2e/
```

Move policy:

- Move green V2 tests first.
- Move board server tests into `tests/contracts/board_api`.
- Rewrite hook and guard tests into adapter tests only if the behavior still
  exists in the V2 architecture.
- Delete V1-only tests instead of preserving them under a legacy folder.
- Remove old `tests/__init__.py` files during consolidation to prevent import
  shadowing.
