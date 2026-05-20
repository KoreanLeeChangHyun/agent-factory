from __future__ import annotations

import pytest

from engine.core.work_requests import (
    AcceptanceCriteria,
    OuroborosPhase,
    OuroborosState,
    WorkRequest,
    WorkRequestRef,
)


def test_work_request_ref_normalizes_external_ticket_ids() -> None:
    assert str(WorkRequestRef.parse("7")) == "T-007"
    assert str(WorkRequestRef.parse("t-12")) == "T-012"


def test_work_request_requires_intent_and_acceptance_before_workflow_run() -> None:
    request = WorkRequest(
        ref=WorkRequestRef.parse("T-123"),
        title="Add importer",
        intent="Import existing ticket XML as work requests",
    )

    with pytest.raises(ValueError, match="acceptance"):
        request.start_workflow_run()

    request.acceptance_criteria.append(AcceptanceCriteria("XML round-trip passes"))
    run = request.start_workflow_run()

    assert run.work_request_ref == WorkRequestRef.parse("T-123")
    assert run.ticket_arg == "T-123"
    assert run.initial_stage == "PREPARE"


def test_ouroboros_refinement_allows_rewrite_loop_and_acceptance() -> None:
    state = OuroborosState()

    state.advance(OuroborosPhase.CLARIFY, "Need storage compatibility")
    state.advance(OuroborosPhase.CRITIQUE, "Acceptance criteria are vague")
    state.advance(OuroborosPhase.REWRITE, "Add XML round-trip acceptance")
    state.advance(OuroborosPhase.CLARIFY, "Keep T-123 IDs")
    state.advance(OuroborosPhase.CRITIQUE, "Ready")
    state.advance(OuroborosPhase.ACCEPT, "Accepted")

    assert state.accepted
    assert [entry.phase for entry in state.history] == [
        OuroborosPhase.CLARIFY,
        OuroborosPhase.CRITIQUE,
        OuroborosPhase.REWRITE,
        OuroborosPhase.CLARIFY,
        OuroborosPhase.CRITIQUE,
        OuroborosPhase.ACCEPT,
    ]


def test_ouroboros_rejects_illegal_transition() -> None:
    state = OuroborosState()
    with pytest.raises(ValueError, match="illegal Ouroboros transition"):
        state.advance(OuroborosPhase.ACCEPT, "too early")

