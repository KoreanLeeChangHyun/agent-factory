# Runtime Root Rename

## Decision

`.claude-organic/` was a transitional name and should be renamed. It keeps the
runtime mentally tied to Claude, which conflicts with the agent factory direction.

Locked target:

```text
.agent-factory/
```

Rationale:

- explicit agent-oriented product name
- provider-neutral
- describes the product category, not the first adapter
- leaves `.claude/` available only for Claude Code integration files

## Scope

This is a large mechanical change. The initial scan found more than 800 textual
references to `.claude-organic` across runtime code, docs, hooks, generated
settings, shell wrappers, and frontend code.

Do not combine this rename with domain source moves.

## Target Meaning

After rename:

| Path | Meaning |
|---|---|
| `.agent-factory/` | provider-neutral agent factory runtime |
| `.claude/` | Claude Code integration surface only |
| `.agent-factory/engine/adapters/claude/` | Claude-specific runtime adapter |
| `.agent-factory/apps/hooks/` | hook entrypoints used by `.claude/settings.json` |

## Compatibility Policy

Preferred:

- no long-term `.claude-organic` compatibility
- one migration script or bootstrap branch may copy preserved user data
- runtime source should refer to one canonical root only

Temporary compatibility is allowed only inside the bootstrap/migration script:

```text
if .claude-organic exists and .agent-factory does not:
  migrate preserved dirs/files to .agent-factory
```

Do not leave application code searching both roots indefinitely.

## Preserved User Data

The rename must preserve:

- `tickets/`
- `runs/`
- `roadmap/`
- `memo/`
- `.settings`
- `.env`
- `.version`
- `.board.url`
- `build.url`
- `.last-session-id`
- `worktrees/` if present
- `board/data/`
- `logs/`
- `staging/`

## File Groups To Change

### Bootstrap And Build

- `init-claude-workflow.sh`
- runtime `build.sh`
- `build-assets/defaults.conf`
- `build-assets/templates/settings.json.tmpl`
- `build-assets/templates/claude-aliases.tmpl`
- `build-assets/templates/claude-env.tmpl`

### Runtime Wrappers

- `bin/flow-*`
- any wrapper `PYTHONPATH` entries
- any wrapper direct script paths

### Claude Code Integration

- `.claude/settings.json`
- `.claude/commands/*.md`
- `.claude/skills/**`

These files may still live under `.claude/`, but they should point to
`.agent-factory/` entrypoints.

### Python Runtime

- project-root discovery
- run paths
- ticket paths
- board URL path
- settings path
- watch directories
- hook dispatch paths

### Board Frontend

- static asset references that expose `.claude-organic`
- workflow artifact URLs
- user-facing copy and comments

### Git Ignore

Replace runtime entries:

```text
.claude-organic/...
```

with:

```text
.agent-factory/...
```

Keep a temporary ignore for `.claude-organic/` during the migration branch if
the old directory may still exist locally.

## Rename Phase Plan

### Phase R0: Decision Lock

- Target name is locked: `.agent-factory`.
- Document preserved user data.
- Count references.
- Keep tests green.

### Phase R1: Mechanical Root Rename

- `git mv .claude-organic .agent-factory`
- update `.gitignore`
- update `init-claude-workflow.sh`
- update `.claude/settings.json`
- update wrappers and templates
- update Python path constants and docs
- run canonical tests

### Phase R2: Runtime Smoke

- run `bash .agent-factory/build.sh` in a disposable checkout or with preserved data
- start board server
- verify `.agent-factory/.board.url`
- run `flow-wf --help` or equivalent wrapper smoke
- run `flow-kanban` read-only command

### Phase R3: Terminology Cleanup

- remove "claude-organic" comments from docs
- update board UI copy
- keep "Claude" only in adapter, hook integration, or external product docs

## Ordering With Domain Refactor

Do this before large domain source moves, but after the test-root consolidation.

Recommended order:

1. consolidate tests
2. remove V1 tests
3. rename `.claude-organic` to `.agent-factory`
4. extract domain/application/adapters
5. isolate Claude adapter

The root rename is mostly mechanical. Domain extraction is semantic. Keeping
them separate makes regressions easier to locate.
