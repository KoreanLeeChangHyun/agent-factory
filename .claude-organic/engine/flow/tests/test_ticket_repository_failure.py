"""test_ticket_repository_failure.py - <failure> XML 요소 파싱/갱신 단위 테스트 (T-456).

검증 항목:
  1. test_parse_4element_ticket_returns_failure_none
     -- 기존 4요소 티켓 파싱 시 result["failure"] is None 검증 (회귀 가드)
  2. test_parse_5element_ticket_returns_failure_dict
     -- <failure> 포함 티켓 파싱 시 4개 자식 요소 모두 dict 매핑 검증
  3. test_parse_failure_with_empty_children
     -- <failure> 존재하나 자식 일부 누락 시 빈 문자열 fallback 검증
  4. test_update_failure_inserts_new_element
     -- failure 미존재 티켓에 update_failure 호출 시 신규 <failure> 요소 + 4 자식 추가 검증
  5. test_update_failure_preserves_other_elements
     -- failure 갱신 후 metadata/relations/prompt/result 회귀 0 검증
"""
from __future__ import annotations

import sys
from pathlib import Path

# sys.path: .claude-organic/engine 포함 -> flow 패키지 import 가능
_ENGINE_DIR = str(Path(__file__).resolve().parent.parent.parent)
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

import flow.ticket_repository as ticket_repo  # noqa: E402


# --- XML 픽스처 헬퍼 ----------------------------------------------------------


def _write_xml(path: Path, content: str) -> None:
    """XML 문자열을 파일에 저장한다."""
    path.write_text(content, encoding="utf-8")


def _xml_4element(ticket_number: str = "T-001") -> str:
    """기존 4요소 티켓 XML (failure 없음) 픽스처를 반환한다."""
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
    <workdir>.claude-organic/runs/20260510-000000/</workdir>
    <plan>.claude-organic/runs/20260510-000000/plan.md</plan>
    <report>.claude-organic/runs/20260510-000000/report.md</report>
    <merge_commit>abc1234</merge_commit>
  </result>
</ticket>
"""


def _xml_5element(ticket_number: str = "T-002") -> str:
    """5요소 티켓 XML (<failure> 포함) 픽스처를 반환한다."""
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
    """<failure> 존재하나 일부 자식 요소 누락 픽스처 (reason/phase 만 있음)."""
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
    """failure 미존재 + result 있는 티켓 (update_failure 삽입 테스트용)."""
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
    <workdir>.claude-organic/runs/20260510-111111/</workdir>
    <plan>.claude-organic/runs/20260510-111111/plan.md</plan>
    <report>.claude-organic/runs/20260510-111111/report.md</report>
    <merge_commit></merge_commit>
  </result>
</ticket>
"""


# --- 테스트 케이스 ------------------------------------------------------------


def test_parse_4element_ticket_returns_failure_none(tmp_path):
    """기존 4요소 티켓 파싱 시 result["failure"] is None (회귀 가드).

    <failure> 요소가 없는 기존 티켓을 parse_ticket_xml 로 파싱할 때
    "failure" 키가 존재하고 값이 None 임을 검증한다.
    """
    ticket_file = tmp_path / "T-001.xml"
    _write_xml(ticket_file, _xml_4element("T-001"))

    result = ticket_repo.parse_ticket_xml(str(ticket_file))

    assert "failure" in result, (
        "parse_ticket_xml 반환 dict 에 'failure' 키가 없습니다 -- dict key regression"
    )
    assert result["failure"] is None, (
        f"4요소 티켓에서 failure 는 None 이어야 하나 {result['failure']!r} 반환"
    )
    # 기존 요소 무결성 확인
    assert result["number"] == "T-001"
    assert result["status"] == "Done"
    assert isinstance(result["result"], dict)
    assert result["result"]["registrykey"] == "20260510-000000"


def test_parse_5element_ticket_returns_failure_dict(tmp_path):
    """<failure> 포함 티켓 파싱 시 4개 자식 요소 모두 dict 매핑 검증.

    reason/phase/retry_count/context 각 필드가 올바른 문자열 값으로
    매핑되는지 확인한다.
    """
    ticket_file = tmp_path / "T-002.xml"
    _write_xml(ticket_file, _xml_5element("T-002"))

    result = ticket_repo.parse_ticket_xml(str(ticket_file))

    assert "failure" in result, "parse_ticket_xml 반환 dict 에 'failure' 키가 없습니다"
    assert isinstance(result["failure"], dict), (
        f"<failure> 포함 티켓에서 failure 는 dict 이어야 하나 {type(result['failure'])} 반환"
    )
    failure = result["failure"]

    assert failure["reason"] == "verifier_failure", (
        f"failure.reason: 'verifier_failure' 기대, {failure['reason']!r} 반환"
    )
    assert failure["phase"] == "VALIDATE", (
        f"failure.phase: 'VALIDATE' 기대, {failure['phase']!r} 반환"
    )
    assert failure["retry_count"] == "3", (
        f"failure.retry_count: '3' 기대, {failure['retry_count']!r} 반환"
    )
    assert "R-203" in failure["context"], (
        f"failure.context 에 'R-203' 이 포함되어야 하나 {failure['context']!r} 반환"
    )


def test_parse_failure_with_empty_children(tmp_path):
    """<failure> 존재하나 자식 일부 누락 시 빈 문자열 fallback 검증.

    reason/phase 만 있고 retry_count/context 가 없을 때
    누락 필드는 빈 문자열("")로 반환해야 한다.
    """
    ticket_file = tmp_path / "T-003.xml"
    _write_xml(ticket_file, _xml_failure_partial_children("T-003"))

    result = ticket_repo.parse_ticket_xml(str(ticket_file))

    assert isinstance(result["failure"], dict), (
        "자식 일부 누락 시에도 failure 는 dict 이어야 한다 (요소 존재하므로)"
    )
    failure = result["failure"]

    assert failure["reason"] == "sentinel", (
        f"failure.reason: 'sentinel' 기대, {failure['reason']!r} 반환"
    )
    assert failure["phase"] == "WORK", (
        f"failure.phase: 'WORK' 기대, {failure['phase']!r} 반환"
    )
    assert failure["retry_count"] == "", (
        f"누락된 retry_count 는 빈 문자열 기대, {failure['retry_count']!r} 반환"
    )
    assert failure["context"] == "", (
        f"누락된 context 는 빈 문자열 기대, {failure['context']!r} 반환"
    )


def test_update_failure_inserts_new_element(tmp_path):
    """failure 미존재 티켓에 update_failure 호출 시 신규 <failure> 요소 + 4 자식 추가 검증.

    1. failure 없는 티켓 파일 생성
    2. update_failure 호출 (reason/phase/retry_count/context 전달)
    3. 파일 다시 파싱하여 failure dict 검증
    """
    ticket_file = tmp_path / "T-004.xml"
    _write_xml(ticket_file, _xml_no_failure_with_result("T-004"))

    # 파싱: 초기 상태 failure=None 확인
    initial = ticket_repo.parse_ticket_xml(str(ticket_file))
    assert initial["failure"] is None, "초기 상태에서 failure 는 None 이어야 한다"

    # update_failure 호출
    ticket_repo.update_failure(str(ticket_file), {
        "reason": "retry_max",
        "phase": "WORK",
        "retry_count": "5",
        "context": "Max retry (5) reached in WORK phase. Sentinel detected.",
    })

    # 재파싱 -> failure dict 검증
    updated = ticket_repo.parse_ticket_xml(str(ticket_file))

    assert isinstance(updated["failure"], dict), (
        f"update_failure 호출 후 failure 는 dict 이어야 하나 {type(updated['failure'])} 반환"
    )
    failure = updated["failure"]

    assert failure["reason"] == "retry_max", (
        f"failure.reason: 'retry_max' 기대, {failure['reason']!r} 반환"
    )
    assert failure["phase"] == "WORK", (
        f"failure.phase: 'WORK' 기대, {failure['phase']!r} 반환"
    )
    assert failure["retry_count"] == "5", (
        f"failure.retry_count: '5' 기대, {failure['retry_count']!r} 반환"
    )
    assert "retry" in failure["context"].lower(), (
        f"failure.context 에 'retry' 포함 기대, {failure['context']!r} 반환"
    )

    # XML 파일에 <failure> 태그 직접 확인
    xml_content = ticket_file.read_text(encoding="utf-8")
    assert "<failure>" in xml_content or "<failure " in xml_content, (
        "XML 파일에 <failure> 태그가 없습니다"
    )
    assert "<reason>retry_max</reason>" in xml_content, (
        "XML 파일에 <reason>retry_max</reason> 없음"
    )
    assert "<retry_count>5</retry_count>" in xml_content, (
        "XML 파일에 <retry_count>5</retry_count> 없음"
    )


def test_update_failure_preserves_other_elements(tmp_path):
    """failure 갱신 후 metadata/relations/prompt/result 회귀 0 검증.

    update_failure 호출 후 기존 요소의 필드값이 변경되지 않아야 한다.
    """
    ticket_file = tmp_path / "T-004b.xml"
    _write_xml(ticket_file, _xml_no_failure_with_result("T-004b"))

    # 초기 파싱으로 기준값 확보
    before = ticket_repo.parse_ticket_xml(str(ticket_file))

    # update_failure 호출
    ticket_repo.update_failure(str(ticket_file), {
        "reason": "validator_failure",
        "phase": "VALIDATE",
        "retry_count": "2",
        "context": "Plan validation failed at VALIDATE phase.",
    })

    # 재파싱
    after = ticket_repo.parse_ticket_xml(str(ticket_file))

    # metadata 필드 보존 확인 (updated 타임스탬프는 write_ticket_xml 이 자동 갱신 -- 허용)
    assert after["number"] == before["number"], (
        f"number 회귀: {before['number']} -> {after['number']}"
    )
    assert after["status"] == before["status"], (
        f"status 회귀: {before['status']} -> {after['status']}"
    )
    assert after["title"] == before["title"], (
        f"title 회귀: {before['title']} -> {after['title']}"
    )
    assert after["command"] == before["command"], (
        f"command 회귀: {before['command']} -> {after['command']}"
    )

    # relations 보존 확인
    assert after["relations"] == before["relations"], (
        f"relations 회귀: {before['relations']} -> {after['relations']}"
    )

    # prompt 필드 보존 확인
    assert after["prompt"]["goal"] == before["prompt"]["goal"], (
        f"prompt.goal 회귀: {before['prompt']['goal']!r} -> {after['prompt']['goal']!r}"
    )
    assert after["prompt"]["target"] == before["prompt"]["target"], (
        f"prompt.target 회귀: {before['prompt']['target']!r} -> {after['prompt']['target']!r}"
    )

    # result 필드 보존 확인
    assert isinstance(after["result"], dict), "result 는 dict 이어야 한다"
    assert after["result"]["registrykey"] == before["result"]["registrykey"], (
        f"result.registrykey 회귀: {before['result']['registrykey']!r} -> {after['result']['registrykey']!r}"
    )
    assert after["result"]["workdir"] == before["result"]["workdir"], (
        "result.workdir 회귀"
    )

    # failure 신규 삽입 확인
    assert isinstance(after["failure"], dict), "update_failure 후 failure 는 dict 이어야 한다"
    assert after["failure"]["reason"] == "validator_failure"
    assert after["failure"]["phase"] == "VALIDATE"
