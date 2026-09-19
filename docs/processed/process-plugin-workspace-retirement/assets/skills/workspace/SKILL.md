---
name: workspace
description: Provide the Human-facing Agent Factory control tower with exactly six top-level Activities for schedule, Agents, Documents, external integrations, logs, and tests. Use for Workspace shell and navigation work; do not infer undecided Activity details or own the projected state.
metadata:
  specification-id: workspace
  human-entry: .agent-factory/document/specification/workspace/index.html
  ai-root: skills/workspace/
---

# Agent Factory Workspace

## Entry contract

Use this Skill for the Human-facing project control tower. Its three principal
regions are `작업 표시줄`, `기본 사이드바`, and `작업 영역` (`Activity Bar`,
`Primary Sidebar`, and `Workspace area`). The Activity Bar has exactly these six
top-level Activities, in order: 일정, 에이전트, 문서, 외부연동, 로그, 테스트.
Do not add another top-level Activity or alias.

Workspace is a projection and control surface. It does not own or execute Agent,
Document, Gather, Tool, provider, credential, or catalog state. Show only
owner-backed facts and controls, keep unresolved areas visibly unresolved, and
never infer live state or fabricate sample data from configuration or local
artifacts.

## Choose the work

Read the applicable reference completely before acting:

- `references/activities.md` owns the six-Activity information architecture,
  External Integration categories, Document sidebar, discovery states, and
  unresolved Activity scope.
- `references/interface.md` owns the browser shell, accessibility and visual
  behavior, Document tables and explorers, recursive Specification tabs and
  splits, MCP runtime publication and server behavior, and storage and authority
  boundaries.

Read both when a change crosses information architecture and interface behavior.
Do not restate their detailed contracts here.

## Runtime and storage

This plugin owns the Workspace Skill and its Human Specification. The selected
Agent Factory MCP application owns and serves the Workspace implementation:

```text
<agent-factory-mcp>/app/                         FastAPI, MCP, and domain runtime
<agent-factory-mcp>/static/workspace/            canonical browser assets
<agent-factory-mcp>/tests/                       runtime contract tests
```

In the sibling development checkout, `<agent-factory-mcp>` is `../mcp`; that
relative path is not a universal installation requirement. Do not recreate the
runtime under this plugin or materialize browser assets into a target project.

Consumer projects do not contain `.agent-factory/workspace/`, copied Workspace
assets, launchers, port files, or Workspace-owned projections. PostgreSQL and
object storage are authoritative for tenant Workspace data. A client may keep
non-authoritative installation and connection state below
`~/.agent-factory/`, separate from project repositories. Legacy project-local
Documents must be inventoried, backed up, and imported through the MCP
application before their old source tree is retired; migration never implies
permission to delete that source.

## Completion gate

A Workspace change is complete only when:

- the six ordered Activities and the decided/unresolved boundary still match
  `references/activities.md`;
- affected browser, navigation, accessibility, security, and publication rules
  match `references/interface.md`;
- the selected MCP runtime's focused tests pass for affected runtime behavior;
- no projected domain state has been invented, mutated, or taken over; and
- this Skill and its Human Specification remain synchronized.
