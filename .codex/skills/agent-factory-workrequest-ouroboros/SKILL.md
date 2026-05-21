---
name: agent-factory-workrequest-ouroboros
description: Use when creating, refining, or accepting Agent Factory WorkRequests. Apply the Ouroboros authoring loop to turn vague intent into executable goal, target, constraints, criteria, and context before workflow execution.
---

# Agent Factory WorkRequest Ouroboros

Use this skill whenever a user asks to create, edit, refine, split, or accept a
WorkRequest.

## Purpose

The WorkRequest is the contract before execution. The Ouroboros loop improves
that contract before a production-line workflow starts.

Target loop:

```text
DRAFT -> CLARIFY -> CRITIQUE -> REWRITE -> ACCEPT
```

The loop belongs to WorkRequest authoring, not to WorkflowRun execution.
When the WorkRequest XML exists, preserve the authoring trail in
`<ouroboros_history>` entries with `phase`, `created_at`, and text.

## WorkRequest Fields

Map the user's request into:

- `title`: short visible request title.
- `command`: `implement`, `research`, or `review`.
- `goal`: what outcome is wanted.
- `target`: files, modules, behavior, or artifact under work.
- `constraints`: boundaries, non-goals, compatibility requirements, and safety limits.
- `criteria`: observable completion conditions.
- `context`: relevant background, prior decisions, risks, and dependencies.

## Authoring Workflow

1. **Draft**: capture the user's request without inventing implementation details.
2. **Clarify**: identify missing target, constraints, criteria, or command type.
3. **Critique**: find ambiguity, unverifiable criteria, hidden coupling, risky scope, and missing rollback/compatibility needs.
4. **Rewrite**: produce a tighter WorkRequest using the five prompt fields.
5. **Accept**: only accept when `goal`, `target`, `constraints`, and `criteria` are specific enough to guide execution.

Ask the user only when a missing field cannot be inferred safely. Otherwise,
make conservative assumptions and write them into `context` or `constraints`.

## CLI Mapping

Create a draft:

```bash
flow-conveyor create "TITLE" --command implement --status draft
```

Write or refine the prompt:

```bash
flow-conveyor update-prompt WR-NNN \
  --command implement \
  --goal "..." \
  --target "..." \
  --constraints "..." \
  --criteria "..." \
  --context "..."
```

Accept by moving the WorkRequest to Accepted:

```bash
flow-conveyor move WR-NNN accepted
```

Persistence shape:

```xml
<ouroboros_history>
  <entry phase="CLARIFY" created_at="...">Checked missing fields</entry>
  <entry phase="CRITIQUE" created_at="...">Checked ambiguity and criteria</entry>
  <entry phase="REWRITE" created_at="...">Rewrote prompt fields</entry>
</ouroboros_history>
```

## Acceptance Checklist

- The request can be executed without re-reading the whole conversation.
- Criteria are observable: tests pass, file exists, endpoint returns shape, UI action works, docs updated, etc.
- Constraints include what not to touch when scope could expand.
- Risks or assumptions are visible in context.
- Implementation details are not over-prescribed unless required for safety or compatibility.
