"""test work_request repository failure.py

Payment Terms:
  1. test_parse_4element_work_request_returns_failure_none
     -- Result ["failure"] is None Verified (return guard) when the existing 4 yoso work_request parsing
  2. test_parse_5element_work_request_returns_failure_dict
     -- <failure> Validation of dict mapping all four child elements in work_request parsing
  3. test_parse_failure_with_empty_children
     -- <failure> exists and validates empty string fallback when some missing
  4. test_update_failure_inserts_new_element
     -- failure New <failure> element + 4 self-exclusive verification when calling update failure on the Mizone work_request
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

import flow.work_request_repository as work_request_repo  # noqa: E402


# --- XML Picker Helper ----------------------------------------------------------


def _write_xml(path: Path, content: str) -> None:
    """Save the XML string to the file."""
    path.write_text(content, encoding="utf-8")


def _xml_4element(work_request_number: str = "WR-001") -> str:
    """Returns the existing 4-nursing work_request XML (failure) picker."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<work_request>
  <!-- metadata -->
  <metadata>
    <number>{work_request_number}</number>
    <title>Test WorkRequest</title>
    <created>2026-05-10 00:00:00</created>
    <updated>2026-05-10 00:00:00</updated>
    <status>Complete</status>
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
</work_request>
"""


def _xml_5element(work_request_number: str = "WR-002") -> str:
    """5Returns the Pictures section including the yoso work_request XML (<failure>)."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<work_request>
  <!-- metadata -->
  <metadata>
    <number>{work_request_number}</number>
    <title>Failed WorkRequest</title>
    <created>2026-05-10 00:00:00</created>
    <updated>2026-05-10 00:00:00</updated>
    <status>Verifying</status>
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
</work_request>
"""


def _xml_failure_partial_children(work_request_number: str = "WR-003") -> str:
    """<failure> exists, but some voluntary elements are missing Pics (reson/phase only)."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<work_request>
  <!-- metadata -->
  <metadata>
    <number>{work_request_number}</number>
    <title>Partial Failure WorkRequest</title>
    <created>2026-05-10 00:00:00</created>
    <updated>2026-05-10 00:00:00</updated>
    <status>Verifying</status>
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
</work_request>
"""


def _xml_no_failure_with_result(work_request_number: str = "WR-004") -> str:
    """failure Mizone + result work_request (for update failure insertion test)."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<work_request>
  <!-- metadata -->
  <metadata>
    <number>{work_request_number}</number>
    <title>No Failure Yet</title>
    <created>2026-05-10 00:00:00</created>
    <updated>2026-05-10 00:00:00</updated>
    <status>Executing</status>
    <command>implement</command>
  </metadata>

  <!-- relations -->
  <relations>
    <relation type="depends-on" work_request="WR-001" />
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
</work_request>
"""


# --- Test case ------------------------------------------------------------


def test_parse_4element_work_request_returns_failure_none(tmp_path):
    """Existing 4Yoso work_request parsing result["failure"] is None (return guard).

    <failure> When parse existing work_requests without elements work_request xml
    "failure" key exists and validate the value is None.
    """
    work_request_file = tmp_path / "WR-001.xml"
    _write_xml(work_request_file, _xml_4element("WR-001"))

    result = work_request_repo.parse_work_request_xml(str(work_request_file))

    assert "failure" in result, (
        "parse work_request xml return dict to 'failure' -- dict key regression"
    )
    assert result["failure"] is None, (
        f"4Field work_requests to failure must be None   FIELD 0  Return"
    )
    # Configuration
    assert result["number"] == "WR-001"
    assert result["status"] == "Complete"
    assert isinstance(result["result"], dict)
    assert result["result"]["registrykey"] == "20260510-000000"


def test_parse_5element_work_request_returns_failure_dict(tmp_path):
    """<failure> Validation of dict mapping all four digits when work_request parsing.

    reason/phase/retry count/context Each field is the right string value
    Check if the map is mapped.
    """
    work_request_file = tmp_path / "WR-002.xml"
    _write_xml(work_request_file, _xml_5element("WR-002"))

    result = work_request_repo.parse_work_request_xml(str(work_request_file))

    assert "failure" in result, "parse work_request xml return dict has no 'failure' key"
    assert isinstance(result["failure"], dict), (
        f"<failure> In the work_request included failure must be dictated one   FIELD 0   return"
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
    work_request_file = tmp_path / "WR-003.xml"
    _write_xml(work_request_file, _xml_failure_partial_children("WR-003"))

    result = work_request_repo.parse_work_request_xml(str(work_request_file))

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
    """failure New <failure> element + 4 self-adhesive verification when calling update failure on the Mizone work_request.

    1. Create a work_request file without failure
    2. update failure call (reason/phase/retry count/context delivery)
    3. FAQs にほんご (Japanese)
    """
    work_request_file = tmp_path / "WR-004.xml"
    _write_xml(work_request_file, _xml_no_failure_with_result("WR-004"))

    # parsing: initial status failure=None check
    initial = work_request_repo.parse_work_request_xml(str(work_request_file))
    assert initial["failure"] is None, "failure in the initial state should be None"

    # update failure call
    work_request_repo.update_failure(str(work_request_file), {
        "reason": "retry_max",
        "phase": "WORK",
        "retry_count": "5",
        "context": "Max retry (5) reached in WORK phase. Sentinel detected.",
    })

    # repasing -> failure dict verification
    updated = work_request_repo.parse_work_request_xml(str(work_request_file))

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
    xml_content = work_request_file.read_text(encoding="utf-8")
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
    work_request_file = tmp_path / "WR-004b.xml"
    _write_xml(work_request_file, _xml_no_failure_with_result("WR-004b"))

    # Secure the standard value with initial parsing
    before = work_request_repo.parse_work_request_xml(str(work_request_file))

    # update failure call
    work_request_repo.update_failure(str(work_request_file), {
        "reason": "validator_failure",
        "phase": "VALIDATE",
        "retry_count": "2",
        "context": "Plan validation failed at VALIDATE phase.",
    })

    # pantyhose
    after = work_request_repo.parse_work_request_xml(str(work_request_file))

    # metadata field preservation confirmation (updated timestamp write work_request xml This automatic update -- accepted)
    assert after["number"] == before["number"], (
        "number field must be preserved"
    )
    assert after["status"] == before["status"], (
        "status field must be preserved"
    )
    assert after["title"] == before["title"], (
        "title field must be preserved"
    )
    assert after["command"] == before["command"], (
        "command field must be preserved"
    )

    # Testimonials
    assert after["relations"] == before["relations"], (
        "relations must be preserved"
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
