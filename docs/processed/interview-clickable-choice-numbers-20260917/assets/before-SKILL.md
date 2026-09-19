---
name: design-clickable-questions
description: Apply the accepted behavior and scope for Agent-designated clickable choice questions.
metadata:
  document-type: "Specification"
  category: "design"
  domain: null
  name: "clickable-questions"
  specification-id: "design-clickable-questions"
  version: "1.0.0"
  semantic-revision: 1
  sync-base-revision: 1
  modified-at: "2026-09-17T12:45:31Z"
  projection: "skill"
  language: "en"
  counterpart: "../../../docs/specification/design-clickable-questions/index.html"
  provenance:
    initial-request: "/home/deus/.agent-factory/projects/project-c0fa88296a30438da4dff2dded77cedc/agents/main-0e9bb0c1-78b6-41f8-a602-a0efd9aee8bc/runs/run-20260917T123127298757Z-23c5a2c5/request.md"
    activation-answer: "/home/deus/.agent-factory/projects/project-c0fa88296a30438da4dff2dded77cedc/agents/main-0e9bb0c1-78b6-41f8-a602-a0efd9aee8bc/runs/run-20260917T123621477743Z-bd84a033/request.md"
    scope-answer: "/home/deus/.agent-factory/projects/project-c0fa88296a30438da4dff2dded77cedc/agents/main-0e9bb0c1-78b6-41f8-a602-a0efd9aee8bc/runs/run-20260917T123722937127Z-dc0b95ac/request.md"
    identity-and-completion-answer: "/home/deus/.agent-factory/projects/project-c0fa88296a30438da4dff2dded77cedc/agents/main-0e9bb0c1-78b6-41f8-a602-a0efd9aee8bc/runs/run-20260917T124242593296Z-81a6be72/request.md"
    q3-context: "/home/deus/.agent-factory/projects/project-c0fa88296a30438da4dff2dded77cedc/agents/work-choice-interview-20260917/runs/run-20260917T124321060258Z-5b0e2d62/request.md"
    interview-record: "../../../docs/processed/interview-clickable-choices-20260917/SKILL.md"
---

# Clickable choice questions

This is the English Skill projection of the accepted `design-clickable-questions` Specification, version 1.0.0.

<!-- clause-id: clickable-questions.activation -->
## 1. Immediate answer submission

Activating a clickable choice must immediately send the selected answer, without a separate send confirmation step.

<!-- clause-id: clickable-questions.designation -->
## 2. Explicit Agent designation

Clickable choices must apply only to questions explicitly designated by the Agent. Arbitrary comparison tables must not be automatically converted into clickable choices.

## Provenance and acceptance

The Human accepted immediate submission by answering `2` to question 1 and explicit Agent designation by answering `3` to question 2. The Human then answered `1` to question 3, whose first option explicitly included finalizing a separate `design-clickable-questions` Specification and completing the interview. This resolved the design category, identity, destination, and completion signal, activating the already requested completion-based promotion. Neither product decision was corrected.

The metadata links the original requests and answers. The meaning of the actual question 3 options, including completion, is supplied by Main's `q3-context` delegation; the literal Human response is in `identity-and-completion-answer`. The [Processed interview record](../../interview-clickable-choices-20260917/SKILL.md) retains the full history, including the question-count revision from two to three due to an initially omitted document decision.

The explicit user requirement for dual projections takes precedence over the installed single-source convention. This projection and its [Korean HTML counterpart](../../../docs/specification/design-clickable-questions/index.html) share the specification ID, version, semantic revision, sync base revision, modification timestamp, and stable clause IDs.

## Implementation boundaries

Technical wire format, UI styling, and persistence remain unresolved implementation details, not additional accepted requirements. This document does not claim implementation completion. No Human decision about document identity or interview completion remains unresolved.
