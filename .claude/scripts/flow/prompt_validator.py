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

import json
import re
import sys
import os

# 프로젝트 루트 결정 (flow_logger import를 위해)
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from flow.flow_logger import append_log, resolve_work_dir_for_logging

REQUIRED_TAGS = ["goal", "target", "constraints", "criteria"]
OPTIONAL_TAGS = ["context", "approach", "scope", "reference"]

# TODO 패턴: "TODO:" 로 시작하거나 전체가 TODO 텍스트만인 경우
_TODO_PATTERN = re.compile(r"^\s*TODO\s*:", re.IGNORECASE)


def _extract_tag_content(text: str, tag: str) -> str | None:
    """태그 내용을 추출한다. 존재하지 않으면 None을 반환.

    자기 중첩 태그(예: <goal>...<goal>...</goal>...</goal>)를
    스택 기반으로 파싱하여 가장 외부 태그 쌍의 내용을 반환한다.

    XML 구조 호환성 주석:
        이 함수는 전체 텍스트에서 태그를 검색하므로 <prompt> 래퍼 내부 깊이와
        무관하게 동작한다. 새 XML 구조에서 <goal>, <target>, <constraints>,
        <criteria> 태그가 <submit>/<history> 래퍼 → <subnumber> → <prompt> 래퍼
        내부에 위치하더라도 정규식 패턴이 전체 텍스트를 대상으로 검색하므로
        정상 매칭된다.

    Args:
        text: 검색할 전체 텍스트
        tag: 추출할 태그 이름 (꺾쇠 제외)

    Returns:
        태그 내부 텍스트. 태그가 없으면 None.
    """
    tag_escaped = re.escape(tag)
    open_pat = re.compile(rf"<{tag_escaped}>", re.IGNORECASE)
    close_pat = re.compile(rf"</{tag_escaped}>", re.IGNORECASE)

    # 개방/폐쇄 태그 위치를 모두 수집
    events = []
    for m in open_pat.finditer(text):
        events.append((m.start(), "open", m.end()))
    for m in close_pat.finditer(text):
        events.append((m.start(), "close", m.end()))

    if not events:
        return None

    # 위치 순서로 정렬
    events.sort(key=lambda e: e[0])

    # 스택 기반으로 가장 외부 태그 쌍 탐색
    depth = 0
    outer_start = None
    for pos, kind, end_pos in events:
        if kind == "open":
            if depth == 0:
                outer_start = end_pos  # 태그 내용 시작 위치
            depth += 1
        else:  # close
            if depth > 0:
                depth -= 1
                if depth == 0 and outer_start is not None:
                    return text[outer_start:pos]

    return None


def extract_active_prompt(xml_text: str) -> str:
    """전체 XML에서 활성 subnumber의 <prompt> 내용을 추출한다.

    <submit> 래퍼 내부에서 active="true" 속성을 가진 <subnumber> 요소를
    찾아 해당 요소 내부의 <prompt> 태그 내용을 반환한다.

    <submit> 래퍼 또는 active="true" subnumber가 없으면 원본 전체 텍스트를
    폴백으로 반환하여 하위 호환성을 보장한다.

    Args:
        xml_text: 전체 티켓 XML 텍스트

    Returns:
        활성 subnumber의 <prompt> 내용. 추출 실패 시 원본 xml_text 반환.
    """
    # Step 1: <submit> 블록 추출
    submit_content = _extract_tag_content(xml_text, "submit")
    if submit_content is None:
        return xml_text

    # Step 2: submit 내부에서 active="true" subnumber 블록 추출
    # <subnumber> 태그는 속성이 있으므로 _extract_tag_content 직접 사용 불가
    # 속성 포함 패턴으로 active subnumber 블록 시작 위치를 찾는다
    active_open_pat = re.compile(
        r'<subnumber[^>]*\bactive\s*=\s*"true"[^>]*>', re.IGNORECASE
    )
    close_pat = re.compile(r'</subnumber>', re.IGNORECASE)

    match = active_open_pat.search(submit_content)
    if match is None:
        return xml_text

    # Step 3: active subnumber 블록 전체를 스택 기반으로 추출
    # (중첩 <subnumber> 가능성에 대비하여 depth 추적)
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

    # Step 4: subnumber 내부의 <prompt> 내용 추출
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

    # 선택 태그 존재 여부 확인
    found_optional = [
        tag for tag in OPTIONAL_TAGS
        if _extract_tag_content(prompt_text, tag) is not None
    ]

    # 역방향 피드백 생성
    feedback: list[str] = []
    for tag in missing_tags:
        feedback.append(
            f"<{tag}> 태그가 없습니다. "
            f"'{tag}' 섹션을 추가하여 planner가 명확히 인식할 수 있도록 보완하세요."
        )
    for tag in empty_tags:
        feedback.append(
            f"<{tag}> 태그 내용이 비어있거나 TODO 텍스트만 있습니다. "
            f"10자 이상의 구체적인 내용을 작성하세요."
        )

    return {
        "quality_score": quality_score,
        "has_tags": has_tags,
        "missing_tags": missing_tags,
        "empty_tags": empty_tags,
        "optional_tags": found_optional,
        "feedback": feedback,
    }


def _print_help() -> None:
    """사용법을 stdout으로 출력한다."""
    print("prompt_validator.py - 티켓 파일 XML 계약 스펙 검증")
    print()
    print("사용법:")
    print("  python3 prompt_validator.py <prompt_file_path>")
    print("  python3 prompt_validator.py --help")
    print()
    print("검증 항목:")
    print("  1. 필수 태그 존재: <goal>, <target>, <constraints>, <criteria>")
    print("  2. 빈 섹션 감지: 내용 없음 / TODO: 패턴 / 10자 미만")
    print("  3. 품질 점수: (존재 태그/4)*0.6 + (유효 내용/4)*0.4")
    print("  4. 선택 태그: <context>, <approach>, <scope>, <reference>")
    print()
    print("출력 (JSON):")
    print("  quality_score, has_tags, missing_tags, empty_tags,")
    print("  optional_tags, feedback")
    print()
    print("종료 코드:")
    print("  0  검증 완료")
    print("  1  파일 읽기 실패")
    print("  2  인자 오류")
    print()
    print("예시:")
    print("  python3 prompt_validator.py .kanban/T-NNN.xml")


def main() -> None:
    """CLI 진입점. 인자를 파싱하여 validate()를 실행하고 JSON을 출력한다.

    Raises:
        SystemExit: 인자 오류(2), 파일 읽기 실패(1), 정상 완료(0).
    """
    if len(sys.argv) < 2:
        _print_help()
        sys.exit(2)

    if sys.argv[1] in ("--help", "-h"):
        _print_help()
        sys.exit(0)

    if len(sys.argv) > 2:
        sys.stderr.write("오류: 인자가 너무 많습니다.\n")
        sys.exit(2)

    prompt_path = sys.argv[1]

    # 상대 경로를 호출 위치 기준 절대 경로로 변환
    if not os.path.isabs(prompt_path):
        prompt_path = os.path.join(os.getcwd(), prompt_path)

    _work_dir = resolve_work_dir_for_logging()
    if _work_dir:
        append_log(_work_dir, "INFO", f"prompt_validator: start path={prompt_path}")

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read()
    except OSError as e:
        sys.stderr.write(f"오류: 파일을 읽을 수 없습니다 — {e}\n")
        sys.exit(1)

    result = validate(prompt_text)

    if result["quality_score"] < 0.5:
        if _work_dir:
            append_log(
                _work_dir,
                "WARN",
                f"prompt_validator: quality_score={result['quality_score']:.4f} below 0.5 path={prompt_path}",
            )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
