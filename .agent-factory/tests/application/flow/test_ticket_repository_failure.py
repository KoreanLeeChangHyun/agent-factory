"""test ticket repository failure.py

Payment Terms:
  1. test_parse_4element_ticket_returns_failure_none
     -- Result ["failure"] is None Verified (return guard) when the existing 4 yoso ticket parsing
  2. test_parse_5element_ticket_returns_failure_dict
     -- <failure> Validation of dict mapping all four child elements in ticket parsing
  3. test_parse_failure_with_empty_children
     -- <failure> exists and validates empty string fallback when some missing
  4. test_update_failure_inserts_new_element
     -- failure New <failure> element + 4 self-exclusive verification when calling update failure on the Mizone ticket
  5. test_update_failure_preserves_other_elements
     -- failure metadata/relations/prompt/result revolving after update 0 verification
"""
from __future__ import annotations

import sys
from pathlib import Path

# sys.path: .agent-factory/engine included -> flow package importable
_ENGINE_DIR = str(Path(__file__).resolve().parents[3] / "engine")
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

import flow.ticket_repository as ticket_repo  # noqa: E402


# --- XML Picker Helper ----------------------------------------------------------


def _write_xml(path: Path, content: str) -> None:
    """Save the XML string to the file."""
    path.write_text(content, encoding="utf-8")


def _xml_4element(ticket_number: str = "T-001") -> str:
    """Returns the existing 4-nursing ticket XML (failure) picker."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ticket>
  <!-- metadata -->
  <metadata>
    <number>{ticket_number}</number>
    <title>Test Ticket</title>
    <created>2026-05-10 00:00:00</created>
    <updated>2026-05-10 00:00:00</updated>
    <status>Done</status>
    <command>implement</command>
  </metadata>

  <!-- prompt -->
  <prompt>
    <goal>Test goal</goal>
    <target>Test target</target>
    <constraints>Test constraints</constraints>
    <criteria>Test criteria</criteria>
    <context>Test context</context>
  </prompt>

  <!-- result -->
  <result>
    <registrykey>20260510-000000</registrykey>
    <workdir>.agent-factory/runs/20260510-000000/</workdir>
    <plan>.agent-factory/runs/20260510-000000/plan.md</plan>
    <report>.agent-factory/runs/20260510-000000/report.md</report>
    <merge_commit>abc1234</merge_commit>
  </result>
</ticket>
"""


def _xml_5element(ticket_number: str = "T-002") -> str:
    """5Returns the Pictures section including the yoso ticket XML (<failure>)."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ticket>
  <!-- metadata -->
  <metadata>
    <number>{ticket_number}</number>
    <title>Failed Ticket</title>
    <created>2026-05-10 00:00:00</created>
    <updated>2026-05-10 00:00:00</updated>
    <status>Review</status>
    <command>implement</command>
  </metadata>

  <!-- prompt -->
  <prompt>
    <goal>Test goal</goal>
    <target>Test target</target>
    <constraints>Test constraints</constraints>
    <criteria>Test criteria</criteria>
    <context>Test context</context>
  </prompt>

  <!-- result -->
  <result />

  <!-- failure -->
  <failure>
    <reason>verifier_failure</reason>
    <phase>VALIDATE</phase>
    <retry_count>3</retry_count>
    <context>work/W02-*.md missing. phase_verifier rule R-203 not satisfied.</context>
  </failure>
</ticket>
"""


def _xml_failure_partial_children(ticket_number: str = "T-003") -> str:
    """<failure> exists, but some voluntary elements are missing Pics (reson/phase only)."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ticket>
  <!-- metadata -->
  <metadata>
    <number>{ticket_number}</number>
    <title>Partial Failure Ticket</title>
    <created>2026-05-10 00:00:00</created>
    <updated>2026-05-10 00:00:00</updated>
    <status>Review</status>
    <command>implement</command>
  </metadata>

  <!-- prompt -->
  <prompt>
    <goal>Test goal</goal>
    <target>Test target</target>
    <constraints></constraints>
    <criteria></criteria>
    <context></context>
  </prompt>

  <!-- result -->
  <result />

  <!-- failure -->
  <failure>
    <reason>sentinel</reason>
    <phase>WORK</phase>
  </failure>
</ticket>
"""


def _xml_no_failure_with_result(ticket_number: str = "T-004") -> str:
    """failure Mizone + result ticket (for update failure insertion test)."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ticket>
  <!-- metadata -->
  <metadata>
    <number>{ticket_number}</number>
    <title>No Failure Yet</title>
    <created>2026-05-10 00:00:00</created>
    <updated>2026-05-10 00:00:00</updated>
    <status>In Progress</status>
    <command>implement</command>
  </metadata>

  <!-- relations -->
  <relations>
    <relation type="depends-on" ticket="T-001" />
  </relations>

  <!-- prompt -->
  <prompt>
    <goal>Test goal for failure insert</goal>
    <target>Test target</target>
    <constraints>Test constraints</constraints>
    <criteria>Test criteria</criteria>
    <context>Test context</context>
  </prompt>

  <!-- result -->
  <result>
    <registrykey>20260510-111111</registrykey>
    <workdir>.agent-factory/runs/20260510-111111/</workdir>
    <plan>.agent-factory/runs/20260510-111111/plan.md</plan>
    <report>.agent-factory/runs/20260510-111111/report.md</report>
    <merge_commit></merge_commit>
  </result>
</ticket>
"""


# --- Test case ------------------------------------------------------------


def test_parse_4element_ticket_returns_failure_none(tmp_path):
    """Existing 4Yoso ticket parsing result["failure"] is None (return guard).

    <failure> When parse existing tickets without elements ticket xml
    "failure" key exists and validate the value is None.
    """
    ticket_file = tmp_path / "T-001.xml"
    _write_xml(ticket_file, _xml_4element("T-001"))

    result = ticket_repo.parse_ticket_xml(str(ticket_file))

    assert "failure" in result, (
        "parse ticket xml return dict to 'failure' -- dict key regression"
    )
    assert result["failure"] is None, (
        f"4Field tickets to failure must be None   FIELD 0  Return"
    )
    # Configuration
    assert result["number"] == "T-001"
    assert result["status"] == "Done"
    assert isinstance(result["result"], dict)
    assert result["result"]["registrykey"] == "20260510-000000"


def test_parse_5element_ticket_returns_failure_dict(tmp_path):
    """<failure> Validation of dict mapping all four digits when ticket parsing.

    reason/phase/retry count/context Each field is the right string value
    Check if the map is mapped.
    """
    ticket_file = tmp_path / "T-002.xml"
    _write_xml(ticket_file, _xml_5element("T-002"))

    result = ticket_repo.parse_ticket_xml(str(ticket_file))

    assert "failure" in result, "parse ticket xml return dict has no 'failure' key"
    assert isinstance(result["failure"], dict), (
        f"<failure> In the ticket included failure must be dictated one   FIELD 0   return"
    )
    failure = result["failure"]

    assert failure["reason"] == "verifier_failure", (
        f"failure.reason: 'verifier failure' expectations,   FIELD 0   return"
    )
    assert failure["phase"] == "VALIDATE", (
        f"failure.phase: 'VALIDATE' expectations,   FIELD 0  return"
    )
    assert failure["retry_count"] == "3", (
        f"failure.retry count: '3' expectations,   FIELD 0  return"
    )
    assert "R-203" in failure["context"], (
        f"failure.context must include 'R-203'   FIELD 0  return"
    )


def test_parse_failure_with_empty_children(tmp_path):
    """<failure> exists, but blank string fallback validation for some missing.

    reason/phase only and retry count/context
    The missing field should be returned to the empty string("").
    """
    ticket_file = tmp_path / "T-003.xml"
    _write_xml(ticket_file, _xml_failure_partial_children("T-003"))

    result = ticket_repo.parse_ticket_xml(str(ticket_file))

    assert isinstance(result["failure"], dict), (
        "failures should be dictated even if some missing (as there is no need)"
    )
    failure = result["failure"]

    assert failure["reason"] == "sentinel", (
        f"failure.reason: 'sentinel' expectations,   FIELD 0  return"
    )
    assert failure["phase"] == "WORK", (
        f"failure.phase: 'WORK' expectations,   FIELD 0  return"
    )
    assert failure["retry_count"] == "", (
        f"missing retry count expects empty strings,   FIELD 0  return"
    )
    assert failure["context"] == "", (
        f"missing context expects empty strings,   FIELD 0   return"
    )


def test_update_failure_inserts_new_element(tmp_path):
    """failure New <failure> element + 4 self-adhesive verification when calling update failure on the Mizone ticket.

    1. Create a ticket file without failure
    2. update failure call (reason/phase/retry count/context delivery)
    3. FAQs にほんご (Japanese)
    """
    ticket_file = tmp_path / "T-004.xml"
    _write_xml(ticket_file, _xml_no_failure_with_result("T-004"))

    # parsing: initial status failure=None check
    initial = ticket_repo.parse_ticket_xml(str(ticket_file))
    assert initial["failure"] is None, "failure in the initial state should be None"

    # update failure call
    ticket_repo.update_failure(str(ticket_file), {
        "reason": "retry_max",
        "phase": "WORK",
        "retry_count": "5",
        "context": "Max retry (5) reached in WORK phase. Sentinel detected.",
    })

    # repasing -> failure dict verification
    updated = ticket_repo.parse_ticket_xml(str(ticket_file))

    assert isinstance(updated["failure"], dict), (
        f"update failure After calling failure must be dictated   FIELD 0   Return"
    )
    failure = updated["failure"]

    assert failure["reason"] == "retry_max", (
        f"failure.reason: 'retry max' expectations,   FIELD 0   return"
    )
    assert failure["phase"] == "WORK", (
        f"failure.phase: 'WORK' expectations,   FIELD 0  return"
    )
    assert failure["retry_count"] == "5", (
        f"failure.retry count: '5' expectations,   FIELD 0  return"
    )
    assert "retry" in failure["context"].lower(), (
        f"expectations containing 'retry' in failure.context,   FIELD 0  return"
    )

    # <failure> tag direct check in XML file
    xml_content = ticket_file.read_text(encoding="utf-8")
    assert "<failure>" in xml_content or "<failure " in xml_content, (
        "No <failure> tags in XML files"
    )
    assert "<reason>retry_max</reason>" in xml_content, (
        "<reason>retry max</reason>"
    )
    assert "<retry_count>5</retry_count>" in xml_content, (
        "<retry count>5</retry count>"
    )


def test_update_failure_preserves_other_elements(tmp_path):
    """metadata/relations/prompt/result revolving after failure update 0 verification.

    After calling update failure, the field value of the existing element should not be changed.
    """
    ticket_file = tmp_path / "T-004b.xml"
    _write_xml(ticket_file, _xml_no_failure_with_result("T-004b"))

    # Secure the standard value with initial parsing
    before = ticket_repo.parse_ticket_xml(str(ticket_file))

    # update failure call
    ticket_repo.update_failure(str(ticket_file), {
        "reason": "validator_failure",
        "phase": "VALIDATE",
        "retry_count": "2",
        "context": "Plan validation failed at VALIDATE phase.",
    })

    # pantyhose
    after = ticket_repo.parse_ticket_xml(str(ticket_file))

    # metadata field preservation confirmation (updated timestamp write ticket xml This automatic update -- accepted)
    assert after["number"] == before["number"], (
        f"number Regression:   FIELD 0    FIELD 1  "
    )
    assert after["status"] == before["status"], (
        f"<% if (imgObj.width >= imgObj.height) { %>"
    )
    assert after["title"] == before["title"], (
        f"<% if (imgObj.width >= imgObj.height) { %>"
    )
    assert after["command"] == before["command"], (
        f"command:   FIELD 0   ->   FIELD 1  "
    )

    # Testimonials
    assert after["relations"] == before["relations"], (
        f" FIELD 0  "
    )

    # Check the prompt field preservation
    assert after["prompt"]["goal"] == before["prompt"]["goal"], (
        f"prompt.goal Regression:   FIELD 0    FIELD 1 "
    )
    assert after["prompt"]["target"] == before["prompt"]["target"], (
        f"prompt.target Regression:   FIELD 0    FIELD 1 "
    )

    # Result Field Conservation Check
    assert isinstance(after["result"], dict), "result must be dictated"
    assert after["result"]["registrykey"] == before["result"]["registrykey"], (
        f"result.registrykey Regression:   FIELD 0 "
    )
    assert after["result"]["workdir"] == before["result"]["workdir"], (
        "result.workdir regression"
    )

    # failure New insertion check
    assert isinstance(after["failure"], dict), "update failure failure should be dictated"
    assert after["failure"]["reason"] == "validator_failure"
    assert after["failure"]["phase"] == "VALIDATE"
