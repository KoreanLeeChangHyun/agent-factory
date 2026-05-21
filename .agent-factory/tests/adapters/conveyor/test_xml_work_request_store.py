from __future__ import annotations

from pathlib import Path

from engine.adapters.conveyor import XmlWorkRequestStore
from engine.core.work_requests import (
    AcceptanceCriteria,
    OuroborosEntry,
    OuroborosPhase,
    RiskNote,
    WorkRequest,
    WorkRequestRef,
    WorkRequestStatus,
)


def test_xml_store_loads_existing_work_request(tmp_path: Path) -> None:
    request_dir = tmp_path / "accepted"
    request_dir.mkdir()
    (request_dir / "WR-123.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<work_request>
  <metadata>
    <number>WR-123</number>
    <title>Importer</title>
    <status>Accepted</status>
    <command>implement</command>
  </metadata>
  <prompt>
    <goal>Map current XML storage</goal>
    <context>Keep current work request files</context>
    <constraints>- no broad move</constraints>
    <criteria>- round-trip passes
- can start workflow</criteria>
  </prompt>
  <ouroboros_history>
    <entry phase="CLARIFY" created_at="2026-05-21T00:00:00+00:00">Checked missing fields</entry>
  </ouroboros_history>
</work_request>
""",
        encoding="utf-8",
    )

    request = XmlWorkRequestStore(tmp_path).get(WorkRequestRef.parse("123"))

    assert request.ref == WorkRequestRef.parse("WR-123")
    assert request.title == "Importer"
    assert request.intent == "Map current XML storage"
    assert request.constraints == ["no broad move"]
    assert [c.text for c in request.acceptance_criteria] == [
        "round-trip passes",
        "can start workflow",
    ]
    assert [entry.phase for entry in request.ouroboros_history] == [OuroborosPhase.CLARIFY]
    assert request.start_workflow_run().work_request_arg == "WR-123"


def test_xml_store_round_trips_work_request_layout(tmp_path: Path) -> None:
    request = WorkRequest(
        ref=WorkRequestRef.parse("WR-124"),
        title="Round trip",
        intent="Persist WorkRequest through XML storage",
        context="Existing files remain the migration bridge",
        constraints=["canonical tests only"],
        acceptance_criteria=[AcceptanceCriteria("load after save returns same fields")],
        non_goals=["rename WorkRequest files"],
        risk_notes=[RiskNote("board terminology is migrated gradually", severity="low")],
        ouroboros_history=[
            OuroborosEntry(
                phase=OuroborosPhase.REWRITE,
                text="Rewrote WorkRequest into executable fields",
                created_at="2026-05-21T00:00:00+00:00",
            )
        ],
        status=WorkRequestStatus.ACCEPTED,
        command="research",
    )
    store = XmlWorkRequestStore(tmp_path)

    store.save(request)
    loaded = store.get(WorkRequestRef.parse("WR-124"))

    assert (tmp_path / "accepted" / "WR-124.xml").is_file()
    assert loaded.ref == request.ref
    assert loaded.command == "research"
    assert loaded.context == request.context
    assert loaded.non_goals == request.non_goals
    assert [r.text for r in loaded.risk_notes] == ["board terminology is migrated gradually"]
    assert [entry.phase for entry in loaded.ouroboros_history] == [OuroborosPhase.REWRITE]


def test_xml_store_moves_file_when_status_changes(tmp_path: Path) -> None:
    store = XmlWorkRequestStore(tmp_path)
    request = WorkRequest(
        ref=WorkRequestRef.parse("WR-125"),
        title="Move",
        intent="Move status directory",
        acceptance_criteria=[AcceptanceCriteria("file appears under executing")],
    )
    store.save(request)

    request.status = WorkRequestStatus.EXECUTING
    store.save(request)

    assert not (tmp_path / "accepted" / "WR-125.xml").exists()
    assert (tmp_path / "executing" / "WR-125.xml").is_file()
