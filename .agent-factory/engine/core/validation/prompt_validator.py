#!/usr/bin/env -S python3 -u
"""prompt_validator.py - 티켓 파일 XML 계약 스펙 검증 스크립트.

티켓 파일을 입력받아 다음을 검증한다:
(1) 필수 태그 4개(<goal>, <target>, <constraints>, <criteria>) 존재 확인
(2) 빈 섹션 감지 (내용 없음 또는 TODO: 패턴만 존재, 최소 10자 미만)
(3) 품질 점수 산출: (존재 필수 태그 수 / 4) * 0.6 + (유효 내용 태그 수 / 4) * 0.4
(4) 선택 태그(<context>, <approach>, <scope>, <reference>) 존재 여부 기재

사용법:
  python3 prompt_validator.py <prompt_file_path>
  python3 prompt_validator.py --help

출력:
  JSON stdout: quality_score, has_tags, missing_tags, empty_tags,
               optional_tags, feedback

종료 코드:
  0  검증 완료
  1  파일 읽기 실패
  2  인자 오류
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

# Determine project route
_engine_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from constants import QUALITY_THRESHOLD

REQUIRED_TAGS = ["goal", "target", "constraints", "criteria"]
OPTIONAL_TAGS = ["context", "approach", "scope", "reference"]
_KST = timezone(timedelta(hours=9))

# TODO pattern: Starts with "TODO:" or is entirely TODO text
_TODO_PATTERN = re.compile(r"^\s*TODO\s*:", re.IGNORECASE)


def build_common_epilog() -> str:
    """Return the common CLI footer without importing flow runtime helpers."""
    return "Agent Factory CLI"


def append_log(abs_work_dir: str, level: str, message: str) -> None:
    """Append workflow log entries without coupling core validation to flow."""
    try:
        ts = datetime.now(_KST).strftime("%Y-%m-%dT%H:%M:%S")
        with open(os.path.join(abs_work_dir, "workflow.log"), "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {message}\n")
    except Exception:
        pass


def resolve_work_dir_for_logging() -> str | None:
    """Resolve workflow work dir from environment when available."""
    for key in ("WORKFLOW_WORK_DIR", "_WF_WORK_DIR"):
        work_dir = os.environ.get(key, "").strip()
        if work_dir and os.path.isdir(work_dir):
            return work_dir
    return None


def _extract_tag_content(text: str, tag: str) -> str | None:
    """태그 내용을 추출한다. 존재하지 않으면 None을 반환.

    자기 중첩 태그(예: <goal>...<goal>...</goal>...</goal>)를
    스택 기반으로 파싱하여 가장 외부 태그 쌍의 내용을 반환한다.

    XML 구조 호환성 주석:
        이 함수는 전체 텍스트에서 태그를 검색하므로 <prompt> 래퍼 내부 깊이와
        무관하게 동작한다. flat 구조(<prompt>가 루트 직하)와 레거시 구조
        (<submit>/<subnumber>/<prompt> 중첩) 모두에서 정규식 패턴이
        전체 텍스트를 대상으로 검색하므로 정상 매칭된다.

    Args:
        text: 검색할 전체 텍스트
        tag: 추출할 태그 이름 (꺾쇠 제외)

    Returns:
        태그 내부 텍스트. 태그가 없으면 None.
    """
    tag_escaped = re.escape(tag)
    open_pat = re.compile(rf"<{tag_escaped}>", re.IGNORECASE)
    close_pat = re.compile(rf"</{tag_escaped}>", re.IGNORECASE)

    # Collect all open/closed tag positions
    events = []
    for m in open_pat.finditer(text):
        events.append((m.start(), "open", m.end()))
    for m in close_pat.finditer(text):
        events.append((m.start(), "close", m.end()))

    if not events:
        return None

    # Sort by position order
    events.sort(key=lambda e: e[0])

    # Explore the most external tag pairs based on the stack
    depth = 0
    outer_start = None
    for pos, kind, end_pos in events:
        if kind == "open":
            if depth == 0:
                outer_start = end_pos  # Tag content start position
            depth += 1
        else:  # close
            if depth > 0:
                depth -= 1
                if depth == 0 and outer_start is not None:
                    return text[outer_start:pos]

    return None


def extract_active_prompt(xml_text: str) -> str:
    """전체 XML에서 <prompt> 내용을 추출한다.

    flat 구조의 티켓 XML에서 루트 직하 <prompt> 태그 내용을 직접 추출한다.

    레거시 폴백: <submit> 래퍼가 감지되면 기존 subnumber 구조로 파싱하여
    active="true" subnumber 내부의 <prompt> 내용을 반환한다 (done 티켓 참조 등).

    Args:
        xml_text: 전체 티켓 XML 텍스트

    Returns:
        <prompt> 내용. 추출 실패 시 원본 xml_text 반환.
    """
    # Legacy fallback: If a <submit> wrapper exists, parse it as the existing subnumber structure.
    submit_content = _extract_tag_content(xml_text, "submit")
    if submit_content is not None:
        return _extract_active_prompt_legacy(xml_text, submit_content)

    # Flat structure: directly extract the contents of the <prompt> tag directly under the root
    prompt_content = _extract_tag_content(xml_text, "prompt")
    if prompt_content is None:
        return xml_text

    return prompt_content


def _extract_active_prompt_legacy(xml_text: str, submit_content: str) -> str:
    """레거시 subnumber 구조에서 활성 <prompt> 내용을 추출한다.

    <submit> 래퍼 내부에서 active="true" 속성을 가진 <subnumber> 요소를
    찾아 해당 요소 내부의 <prompt> 태그 내용을 반환한다.

    Args:
        xml_text: 전체 티켓 XML 텍스트 (폴백 반환용)
        submit_content: <submit> 태그 내부 텍스트

    Returns:
        활성 subnumber의 <prompt> 내용. 추출 실패 시 원본 xml_text 반환.
    """
    active_open_pat = re.compile(
        r'<subnumber[^>]*\bactive\s*=\s*"true"[^>]*>', re.IGNORECASE
    )
    close_pat = re.compile(r'</subnumber>', re.IGNORECASE)

    match = active_open_pat.search(submit_content)
    if match is None:
        return xml_text

    open_any_pat = re.compile(r'<subnumber[^>]*>', re.IGNORECASE)

    events: list[tuple[int, str, int]] = []
    for m in open_any_pat.finditer(submit_content):
        events.append((m.start(), "open", m.end()))
    for m in close_pat.finditer(submit_content):
        events.append((m.start(), "close", m.end()))
    events.sort(key=lambda e: e[0])

    depth = 0
    outer_start: int | None = None
    outer_end: int | None = None
    active_start = match.start()
    found_active = False

    for pos, kind, end_pos in events:
        if kind == "open":
            if depth == 0 and pos == active_start:
                found_active = True
                outer_start = end_pos
            depth += 1
        else:  # close
            if depth > 0:
                depth -= 1
                if depth == 0 and found_active and outer_start is not None:
                    outer_end = pos
                    break

    if outer_start is None or outer_end is None:
        return xml_text

    subnumber_content = submit_content[outer_start:outer_end]

    prompt_content = _extract_tag_content(subnumber_content, "prompt")
    if prompt_content is None:
        return xml_text

    return prompt_content


def _is_valid_content(content: str) -> bool:
    """태그 내용이 유효한지 판별한다.

    유효 조건: 공백 제거 후 10자 이상이며, TODO: 패턴만으로 구성되지 않음.

    Args:
        content: 검사할 태그 내용 문자열

    Returns:
        내용이 유효하면 True, 그렇지 않으면 False.
    """
    stripped = content.strip()
    if len(stripped) < 10:
        return False
    if _TODO_PATTERN.match(stripped):
        return False
    return True


def validate(prompt_text: str) -> dict[str, object]:
    """prompt_text를 검증하고 결과 dict를 반환한다.

    Args:
        prompt_text: 검증할 프롬프트 텍스트

    Returns:
        검증 결과 딕셔너리. 다음 키를 포함한다:
        - quality_score (float): 0.0~1.0 품질 점수
        - has_tags (bool): 필수 태그가 하나 이상 존재하는지 여부
        - missing_tags (list[str]): 누락된 필수 태그 목록
        - empty_tags (list[str]): 내용이 비어있는 필수 태그 목록
        - optional_tags (list[str]): 발견된 선택 태그 목록
        - feedback (list[str]): 개선 피드백 메시지 목록
    """
    present_tags: list[str] = []
    missing_tags: list[str] = []
    valid_tags: list[str] = []
    empty_tags: list[str] = []

    for tag in REQUIRED_TAGS:
        content = _extract_tag_content(prompt_text, tag)
        if content is None:
            missing_tags.append(tag)
        else:
            present_tags.append(tag)
            if _is_valid_content(content):
                valid_tags.append(tag)
            else:
                empty_tags.append(tag)

    present_count = len(present_tags)
    valid_count = len(valid_tags)
    quality_score = round((present_count / 4) * 0.6 + (valid_count / 4) * 0.4, 4)
    has_tags = present_count > 0

    # Check for existence of selection tag
    found_optional = [
        tag for tag in OPTIONAL_TAGS
        if _extract_tag_content(prompt_text, tag) is not None
    ]

    # Generate backward feedback
    feedback: list[str] = []
    for tag in missing_tags:
        feedback.append(
            f"No <{tag}> tag."
            f"Add the '{tag}' section to make it clearly recognizable to planners."
        )
    for tag in empty_tags:
        feedback.append(
            f"<{tag}> tag content is empty or contains only TODO text."
            f"Please be specific and at least 10 characters long."
        )

    return {
        "quality_score": quality_score,
        "has_tags": has_tags,
        "missing_tags": missing_tags,
        "empty_tags": empty_tags,
        "optional_tags": found_optional,
        "feedback": feedback,
    }


def _build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서를 생성하여 반환한다.

    Returns:
        설정된 ArgumentParser 인스턴스.
    """
    parser = argparse.ArgumentParser(
        prog="flow-validate-p",
        description="Validate Ticket File XML Contract Specification \n \n"
                    "Verification Item: \n"
                    "1. Required tags present: <goal>, <target>, <constraints>, <criteria> \n"
                    "2. Detect empty sections: no content / TODO: pattern / less than 10 characters \n"
                    "3. Quality score: (Existence tags/4)*0.6 + (Effective content/4)*0.4 \n"
                    "4. Optional tags: <context>, <approach>, <scope>, <reference> \n \n"
                    "Output (JSON): \n"
                    "  quality_score, has_tags, missing_tags, empty_tags,\n"
                    "  optional_tags, feedback\n\n"
                    "Exit code: \n"
                    "0 Verification completed \n"
                    "1 Failed to read file \n"
                    "2 argument error",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=build_common_epilog(),
    )
    parser.add_argument(
        "prompt_file_path",
        help="Path to the ticket file to validate (e.g. .agent-factory/tickets/active/T-NNN.xml)",
    )
    return parser


def main() -> None:
    """CLI 진입점. 인자를 파싱하여 validate()를 실행하고 JSON을 출력한다.

    Raises:
        SystemExit: 인자 오류(2), 파일 읽기 실패(1), 정상 완료(0).
    """
    parser = _build_parser()
    args = parser.parse_args()

    prompt_path = args.prompt_file_path

    # Convert relative path to absolute path based on call location
    if not os.path.isabs(prompt_path):
        prompt_path = os.path.join(os.getcwd(), prompt_path)

    _work_dir = resolve_work_dir_for_logging()
    if _work_dir:
        append_log(_work_dir, "INFO", f"prompt_validator: start path={prompt_path}")

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read()
    except OSError as e:
        sys.stderr.write(f"Error: Unable to read file — {e} \n")
        sys.exit(1)

    result = validate(prompt_text)

    if result["quality_score"] < QUALITY_THRESHOLD:
        if _work_dir:
            append_log(
                _work_dir,
                "WARN",
                f"prompt_validator: quality_score={result['quality_score']:.4f} below {QUALITY_THRESHOLD} path={prompt_path}",
            )

    print("[STATE] VALIDATE-P", flush=True)
    print(f">> quality_score={result['quality_score']:.4f}", flush=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
