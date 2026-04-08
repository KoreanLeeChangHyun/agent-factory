#!/usr/bin/env -S python3 -u
"""plan_validator.py - 계획서(plan.md) 및 칸반 티켓 구조 검증 스크립트.

plan.md를 입력받아 다음을 검증한다:
(1) Mermaid 서브그래프에서 Phase별 워커 수 추출, 최대/최소 비율 3배 이상 시 경고
(2) 작업 목록 테이블에서 워커별 작업 항목 수 파싱, 편차 2 초과 시 경고
(3) T2(10+) 태스크에서 스킬 1개인 경우 경고
(4) WHAT/HOW 분리 검증: criteria/goal/context 재서술 탐지 (advisory, 비차단)

--mode ticket 시 칸반 티켓 XML 구조 검증을 수행한다:
(TC-01) 디렉터리 위치 vs XML status 불일치
(TC-02) derived-from 파생 티켓 미완료 + 원본 done 경고
(TC-03) 필수 태그 누락 (number/command/prompt)
(TC-04) command 값 유효성
(TC-05) goal/target 빈 값 경고
(TC-06) 복수 항목 필드 개행 누락 경고
(TC-07) 관계 링크 대상 티켓 존재 여부

사용법:
  flow-validate <plan_path|registryKey>
  flow-validate --mode ticket
  flow-validate --mode ticket --ticket T-001
  flow-validate --help

출력:
  경고 목록 또는 "검증 통과"
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from typing import Any

# 프로젝트 루트 결정
_scripts_dir: str = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import resolve_project_root, resolve_work_dir
from flow.cli_utils import build_common_epilog
from flow.flow_logger import append_log, resolve_work_dir_for_logging

PROJECT_ROOT: str = resolve_project_root()


def parse_mermaid_phases(content: str) -> dict[str, int]:
    """Mermaid 서브그래프에서 Phase별 워커 수를 추출한다.

    다중 Mermaid 코드 블록을 모두 순회하여 결과를 병합한다.
    중첩 subgraph를 스택으로 처리하며, W[숫자]+ 패턴의 노드를 워커로 인식한다.

    Args:
        content: plan.md 전체 내용 문자열

    Returns:
        {phase_name: worker_count} 형태의 딕셔너리.
    """
    phases = {}

    # 다중 Mermaid 코드 블록 추출
    mermaid_blocks = re.findall(r"```mermaid\s*\n(.*?)```", content, re.DOTALL)
    if not mermaid_blocks:
        return phases

    for mermaid_content in mermaid_blocks:
        lines = mermaid_content.split("\n")

        current_phase = None
        worker_count = 0
        # 중첩 subgraph 지원을 위한 스택: (phase_name, worker_count) 쌍 저장
        phase_stack = []

        for line in lines:
            stripped = line.strip()

            # subgraph 시작: 표준 형식
            #   subgraph id["label"]  or  subgraph id[label]  or  subgraph id
            subgraph_match = re.match(
                r'subgraph\s+(\S+)\s*\[\s*"([^"]*)"\s*\]', stripped
            )
            if not subgraph_match:
                subgraph_match = re.match(
                    r'subgraph\s+(\S+)\s*\[\s*([^\]]*)\s*\]', stripped
                )
            if not subgraph_match:
                subgraph_match = re.match(r'subgraph\s+(\S+)', stripped)

            if subgraph_match:
                # 현재 subgraph를 스택에 저장 (중첩 지원)
                phase_stack.append((current_phase, worker_count))

                new_phase = subgraph_match.group(1)
                # subgraph label이 있으면 사용
                if subgraph_match.lastindex and subgraph_match.lastindex >= 2:
                    label = subgraph_match.group(2).strip()
                    if label:
                        new_phase = label
                current_phase = new_phase
                worker_count = 0
                continue

            # end 키워드
            if stripped == "end":
                if current_phase is not None:
                    phases[current_phase] = phases.get(current_phase, 0) + worker_count
                # 스택에서 외부 subgraph 복원 (비어있으면 None)
                if phase_stack:
                    current_phase, worker_count = phase_stack.pop()
                else:
                    current_phase = None
                    worker_count = 0
                continue

            # 워커 노드 식별 (W01[label], W01 [label] 패턴)
            if current_phase is not None and re.match(r"^\s*W\d+[\[\s\(]", stripped):
                worker_count += 1

        # 마지막 subgraph 저장 (end 없이 블록이 끝난 경우)
        if current_phase is not None:
            phases[current_phase] = phases.get(current_phase, 0) + worker_count

    return phases


def _split_table_row(line: str) -> list[str]:
    """마크다운 테이블 행을 셀 목록으로 분리한다.

    양 끝 빈 셀만 제거하고 내부 빈 셀은 유지한다.

    Args:
        line: 마크다운 테이블 행 문자열 (| 구분자 포함)

    Returns:
        셀 값 목록 (각 셀은 strip된 문자열).
    """
    raw_parts = [p.strip() for p in line.split("|")]
    return raw_parts[1:-1] if len(raw_parts) >= 2 else raw_parts


def _find_table_start(lines: list[str], section_pattern: str | None, column_keywords: dict[str, list[str]]) -> int:
    """테이블 섹션 시작 위치를 결정한다.

    section_pattern이 있으면 해당 섹션 헤더를 먼저 탐색하고,
    없으면 첫 번째 컬럼 키워드로 테이블 행을 직접 탐색한다.

    Args:
        lines: 마크다운 파일 행 목록
        section_pattern: 섹션 헤더 정규식 패턴. None이면 전체 탐색.
        column_keywords: {field_name: [keyword, ...]} 형태의 컬럼 탐지 키워드 맵

    Returns:
        테이블 섹션 시작 행 인덱스. 없으면 -1.
    """
    if section_pattern:
        for i, line in enumerate(lines):
            if re.search(section_pattern, line):
                return i

    # 섹션 헤더 없이 테이블 직접 탐색 (첫 번째 컬럼 키워드로 판별)
    first_field_keywords = next(iter(column_keywords.values()), [])
    for i, line in enumerate(lines):
        if line.startswith("|") and any(k.lower() in line.lower() for k in first_field_keywords):
            return i

    return -1


def _find_header_and_col_map(
    lines: list[str],
    table_start: int,
    column_keywords: dict[str, list[str]],
) -> tuple[int, dict[str, int]]:
    """헤더 행과 컬럼 인덱스 맵을 결정한다.

    table_start 위치에서 최대 15행 내에서 헤더 행을 탐색하고
    column_keywords의 각 필드에 대응하는 컬럼 인덱스를 매핑한다.

    Args:
        lines: 마크다운 파일 행 목록
        table_start: 테이블 탐색 시작 행 인덱스
        column_keywords: {field_name: [keyword, ...]} 형태의 컬럼 탐지 키워드 맵

    Returns:
        (header_idx, col_map) 튜플. 헤더 없으면 (-1, {}).
    """
    col_map: dict[str, int] = {}
    first_field = next(iter(column_keywords))
    search_end = min(table_start + 15, len(lines))

    for i in range(table_start, search_end):
        line = lines[i]
        if not line.startswith("|"):
            continue

        parts = _split_table_row(line)
        for j, part in enumerate(parts):
            lower = part.lower()
            for field, keywords in column_keywords.items():
                if field not in col_map and any(k.lower() in lower for k in keywords):
                    col_map[field] = j

        if first_field in col_map:
            return i, col_map

    return -1, {}


def parse_md_table_columns(content, section_pattern, column_keywords):
    """
    마크다운 테이블에서 헤더 컬럼 인덱스를 매핑하고 데이터 행을 파싱.

    Args:
        content: 마크다운 파일 전체 내용 문자열
        section_pattern: 테이블 섹션 헤더를 찾는 정규식 패턴 (None이면 전체 탐색)
        column_keywords: {field_name: [keyword, ...]} 형태의 컬럼 탐지 키워드 맵

    Returns:
        list[dict]: 각 행이 {field_name: cell_value} 딕셔너리인 리스트.
                    인식되지 않은 필드는 포함되지 않음.
    """
    lines = content.split("\n")

    table_start = _find_table_start(lines, section_pattern, column_keywords)
    if table_start < 0:
        return []

    header_idx, col_map = _find_header_and_col_map(lines, table_start, column_keywords)
    if header_idx < 0:
        return []

    rows = []
    for i in range(header_idx + 1, len(lines)):
        line = lines[i]
        if not line.startswith("|"):
            break
        if re.match(r"^\|\s*[-:]+", line):
            continue

        parts = _split_table_row(line)
        row = {
            field: parts[col_idx].strip() if col_idx < len(parts) else ""
            for field, col_idx in col_map.items()
        }
        rows.append(row)

    return rows


def parse_task_table(content: str) -> list[dict[str, Any]]:
    """작업 목록 테이블에서 태스크 정보를 파싱한다.

    Args:
        content: plan.md 전체 내용 문자열

    Returns:
        태스크 딕셔너리 목록. 각 항목은 다음 키를 포함:
            id (str): 태스크 ID (W01 형식)
            description (str): 작업 설명
            complexity (str): 복잡도 원문 문자열
            complexity_score (int): 복잡도 숫자 점수 (없으면 0)
            skills (list[str]): 스킬 목록
            phase (str): Phase 식별자
    """
    tasks = []

    column_keywords = {
        "id": ["id"],
        "description": ["작업", "설명", "description"],
        "complexity": ["복잡도", "complexity"],
        "skills": ["스킬", "skill"],
        "phase": ["phase"],
    }

    section_pattern = r"^##\s+작업\s*(목록|리스트|테이블)"
    rows = parse_md_table_columns(content, section_pattern, column_keywords)

    for row in rows:
        task_id = row.get("id", "")
        if not (task_id and re.match(r"^W\d+", task_id)):
            continue

        raw_complexity = row.get("complexity", "")
        complexity_score = 0
        score_match = re.search(r"\((\d+)\)", raw_complexity)
        if score_match:
            complexity_score = int(score_match.group(1))

        raw_skills = row.get("skills", "")
        if raw_skills and raw_skills != "-" and raw_skills != "없음":
            skills = [s.strip() for s in re.split(r"[+,]", raw_skills) if s.strip()]
        else:
            skills = []

        tasks.append(
            {
                "id": task_id,
                "description": row.get("description", ""),
                "complexity": raw_complexity,
                "complexity_score": complexity_score,
                "skills": skills,
                "phase": row.get("phase", ""),
            }
        )

    return tasks


def count_task_work_items(content: str, task_id: str) -> int:
    """워커별 작업 상세 섹션에서 해당 태스크의 작업 항목 수를 카운트한다.

    "### WXX:" H3 섹션 내의 번호 리스트 항목 수를 반환한다.

    Args:
        content: plan.md 전체 내용 문자열
        task_id: 카운트할 태스크 ID (예: "W01")

    Returns:
        해당 태스크 섹션의 번호 리스트 항목 수.
    """
    lines = content.split("\n")
    in_section = False
    item_count = 0

    for line in lines:
        # H3 헤더로 해당 태스크 섹션 시작
        if re.match(rf"^###\s+{re.escape(task_id)}\b", line):
            in_section = True
            continue

        # 다음 H2/H3 헤더로 섹션 종료
        if in_section and re.match(r"^#{2,3}\s+", line):
            break

        if in_section:
            # 번호 리스트 항목 카운트 (1., 2., 3., ...)
            if re.match(r"^\d+\.\s+", line.strip()):
                item_count += 1

    return item_count


def validate_phase_balance(phases: dict[str, int]) -> list[str]:
    """Phase별 워커 수 균형을 검증한다.

    최대/최소 워커 수 비율이 3배 이상이면 경고를 생성한다.

    Args:
        phases: {phase_name: worker_count} 형태의 딕셔너리

    Returns:
        경고 메시지 목록. 균형이 맞으면 빈 리스트.
    """
    warnings = []

    if len(phases) < 2:
        return warnings

    # 워커가 0인 Phase 제외
    active_phases = {k: v for k, v in phases.items() if v > 0}
    if len(active_phases) < 2:
        return warnings

    counts = list(active_phases.values())
    max_count = max(counts)
    min_count = min(counts)

    if min_count > 0 and max_count / min_count >= 3:
        max_phase = [k for k, v in active_phases.items() if v == max_count][0]
        min_phase = [k for k, v in active_phases.items() if v == min_count][0]
        warnings.append(
            f"[Phase 균형] Phase 간 워커 수 불균형 (비율 {max_count/min_count:.1f}x): "
            f"{max_phase}={max_count}명 vs {min_phase}={min_count}명 "
            f"(기준: 최대/최소 3배 미만 권장)"
        )

    return warnings


def validate_work_item_deviation(tasks: list[dict[str, Any]], content: str) -> list[str]:
    """같은 Phase 내 워커 간 작업 항목 수 편차를 검증한다.

    동일 Phase 내 작업 항목 수 최대-최소 차이가 2를 초과하면 경고를 생성한다.

    Args:
        tasks: parse_task_table()이 반환한 태스크 딕셔너리 목록
        content: plan.md 전체 내용 문자열

    Returns:
        경고 메시지 목록. 편차가 허용 범위 내이면 빈 리스트.
    """
    warnings = []

    # Phase별 태스크 그룹화
    phase_groups = {}
    for task in tasks:
        phase = task.get("phase", "")
        if not phase:
            continue
        if phase not in phase_groups:
            phase_groups[phase] = []
        phase_groups[phase].append(task)

    for phase, group in phase_groups.items():
        if len(group) < 2:
            continue

        # 각 태스크의 작업 항목 수 카운트
        item_counts = {}
        for task in group:
            count = count_task_work_items(content, task["id"])
            item_counts[task["id"]] = count

        # 편차 계산
        counts = [c for c in item_counts.values() if c > 0]
        if len(counts) < 2:
            continue

        max_count = max(counts)
        min_count = min(counts)
        deviation = max_count - min_count

        if deviation > 2:
            max_task = [k for k, v in item_counts.items() if v == max_count][0]
            min_task = [k for k, v in item_counts.items() if v == min_count][0]
            warnings.append(
                f"[작업 편차] Phase {phase} 내 워커 간 작업 항목 편차 {deviation} "
                f"(기준: 2 이내): {max_task}={max_count}개 vs {min_task}={min_count}개"
            )

    return warnings


def validate_skill_coverage(tasks: list[dict[str, Any]]) -> list[str]:
    """T2(10+) 태스크에서 스킬이 1개만 배정된 경우 경고를 생성한다.

    복잡도 점수 10 이상인 태스크에 스킬이 1개만 배정되면
    도메인 커버리지 부족 가능성 경고를 반환한다.

    Args:
        tasks: parse_task_table()이 반환한 태스크 딕셔너리 목록

    Returns:
        경고 메시지 목록. 모든 T2 태스크가 충분한 스킬을 가지면 빈 리스트.
    """
    warnings = []

    for task in tasks:
        if task["complexity_score"] >= 10 and len(task["skills"]) == 1:
            warnings.append(
                f"[스킬 부족] {task['id']}는 복잡도 {task['complexity']}이나 "
                f"스킬이 1개({task['skills'][0]})만 배정됨. "
                f"2개 이상의 도메인 포함 여부를 확인하세요."
            )

    return warnings


def _extract_xml_tag(content: str, tag: str) -> str:
    """XML 태그 내용을 추출한다.

    Args:
        content: 검색 대상 문자열
        tag: 태그 이름 (예: "criteria", "goal", "context")

    Returns:
        태그 내용 문자열. 태그가 없으면 빈 문자열.
    """
    match = re.search(rf"<{tag}>(.*?)</{tag}>", content, re.DOTALL)
    return match.group(1) if match else ""


def _extract_section(content: str, section_names: list[str]) -> str:
    """plan.md에서 지정된 섹션 이름에 해당하는 섹션 내용을 추출한다.

    ## 헤더로 시작하는 섹션을 탐색하며 다음 ## 헤더까지의 내용을 반환한다.

    Args:
        content: plan.md 전체 내용 문자열
        section_names: 탐색할 섹션 이름 목록 (첫 번째 일치 섹션 반환)

    Returns:
        섹션 내용 문자열. 섹션이 없으면 빈 문자열.
    """
    lines = content.split("\n")
    in_section = False
    section_lines = []

    for line in lines:
        if re.match(r"^##\s+", line):
            if in_section:
                break
            header_text = re.sub(r"^##\s+", "", line).strip()
            if any(name in header_text for name in section_names):
                in_section = True
            continue

        if in_section:
            section_lines.append(line)

    return "\n".join(section_lines)


def _normalize_line(line: str) -> str:
    """공백을 정규화한 행을 반환한다."""
    return re.sub(r"\s+", " ", line).strip()


def _count_consecutive_matches(source_lines: list[str], target_text: str) -> int:
    """source_lines의 연속 행이 target_text에 포함되는 최대 연속 일치 수를 반환한다.

    공백 정규화 후 문자열 포함 비교(substring match)를 사용한다.
    빈 행은 비교에서 제외한다.

    Args:
        source_lines: 비교 기준 행 목록 (XML 태그 내용 등)
        target_text: 대상 텍스트 (plan.md 섹션 내용)

    Returns:
        최대 연속 일치 행 수.
    """
    target_normalized = _normalize_line(target_text)
    max_streak = 0
    current_streak = 0

    for line in source_lines:
        norm = _normalize_line(line)
        if not norm:
            # 빈 행은 연속 카운트를 끊지 않음 (선택적 연속 허용)
            continue
        if norm in target_normalized:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0

    return max_streak


def validate_what_how_separation(plan_path: str, user_prompt_path: str) -> list[str]:
    """WHAT/HOW 분리 검증: criteria/goal/context 재서술 탐지.

    user_prompt.txt의 XML 태그 내용이 plan.md의 해당 섹션에 재서술되었는지를
    문자열 비교로 탐지한다. 모든 경고는 advisory(비차단) 수준이다.

    탐지 룰:
      - criteria 재서술: <criteria> 원문 3줄 이상 연속 일치 시 경고
      - goal 재서술: <goal> 원문 핵심 구절(10자 이상) 포함 시 경고
      - context 원문 복사: <context> 원문 2줄 이상 연속 일치 시 경고

    Args:
        plan_path: plan.md 파일 경로
        user_prompt_path: user_prompt.txt 파일 경로

    Returns:
        advisory 경고 메시지 목록. 이상 없으면 빈 리스트.
    """
    warnings = []

    if not os.path.isfile(user_prompt_path):
        return warnings

    with open(user_prompt_path, "r", encoding="utf-8") as f:
        prompt_content = f.read()

    with open(plan_path, "r", encoding="utf-8") as f:
        plan_content = f.read()

    # 룰 1: criteria 재서술 탐지
    criteria_text = _extract_xml_tag(prompt_content, "criteria")
    if criteria_text:
        criteria_section = _extract_section(plan_content, ["기술 검증 기준"])
        if criteria_section:
            criteria_lines = [l for l in criteria_text.split("\n") if _normalize_line(l)]
            match_count = _count_consecutive_matches(criteria_lines, criteria_section)
            if match_count >= 3:
                warnings.append(
                    f"[WHAT/HOW advisory] criteria 재서술 의심: "
                    f"기술 검증 기준 섹션에 <criteria> 원문과 유사한 내용 {match_count}줄 감지"
                )

    # 룰 2: goal 재서술 탐지
    goal_text = _extract_xml_tag(prompt_content, "goal")
    if goal_text:
        summary_section = _extract_section(plan_content, ["작업 요약"])
        if summary_section:
            summary_normalized = _normalize_line(summary_section)
            # goal 원문에서 10자 이상 연속 구절 추출 후 포함 여부 확인
            goal_normalized = _normalize_line(goal_text)
            found_phrase = False
            # 슬라이딩 윈도우로 10자 이상 구절 탐지
            words = goal_normalized.split()
            for i in range(len(words)):
                for j in range(i + 2, len(words) + 1):
                    phrase = " ".join(words[i:j])
                    if len(phrase) >= 10 and phrase in summary_normalized:
                        found_phrase = True
                        break
                if found_phrase:
                    break
            if found_phrase:
                warnings.append(
                    "[WHAT/HOW advisory] goal 재서술 의심: "
                    "작업 요약에 <goal> 원문 구절 포함 감지"
                )

    # 룰 3: context 원문 블록 복사 탐지
    context_text = _extract_xml_tag(prompt_content, "context")
    if context_text:
        note_section = _extract_section(plan_content, ["비고", "현황 스냅샷"])
        if note_section:
            context_lines = [l for l in context_text.split("\n") if _normalize_line(l)]
            match_count = _count_consecutive_matches(context_lines, note_section)
            if match_count >= 2:
                warnings.append(
                    f"[WHAT/HOW advisory] context 원문 복사 의심: "
                    f"비고 섹션에 <context> 원문 블록 {match_count}줄 복사 감지"
                )

    return warnings


def validate(plan_path: str) -> list[str]:
    """plan.md를 검증하고 경고 목록을 반환.

    advisory, non-blocking 성격의 검증 함수이다.
    반환값은 오케스트레이터의 워크플로우 흐름을 차단하지 않으며,
    경고 메시지는 로그 출력용으로만 사용된다.

    Args:
        plan_path: plan.md 파일 경로

    Returns:
        list[str]: 경고 메시지 목록 (빈 리스트면 검증 통과).
                   반환값에 관계없이 호출자의 흐름을 차단하지 않는다.
    """
    if not os.path.isfile(plan_path):
        return [f"[ERROR] 파일을 찾을 수 없습니다: {plan_path}"]

    with open(plan_path, "r", encoding="utf-8") as f:
        content = f.read()

    warnings = []

    # 1. Mermaid 서브그래프에서 Phase별 워커 수 추출
    phases = parse_mermaid_phases(content)
    if phases:
        warnings.extend(validate_phase_balance(phases))

    # 2. 작업 목록 테이블 파싱
    tasks = parse_task_table(content)

    # 3. 워커별 작업 항목 수 편차 검증
    if tasks:
        warnings.extend(validate_work_item_deviation(tasks, content))

    # 4. T2(10+) 태스크 스킬 수 검증
    if tasks:
        warnings.extend(validate_skill_coverage(tasks))

    # 5. WHAT/HOW 분리 검증 (advisory, 비차단)
    plan_dir = os.path.dirname(plan_path)
    user_prompt_path = os.path.join(plan_dir, "user_prompt.txt")
    warnings.extend(validate_what_how_separation(plan_path, user_prompt_path))

    if warnings:
        _work_dir = resolve_work_dir_for_logging()
        if _work_dir:
            append_log(_work_dir, "WARN", f"plan_validator: {len(warnings)} warnings found")

    return warnings


# ---------------------------------------------------------------------------
# ticket 모드 헬퍼 함수
# ---------------------------------------------------------------------------

# 디렉터리명 → XML status 값 매핑 (정규화용)
_DIR_TO_STATUS: dict[str, str] = {
    "open": "Open",
    "progress": "In Progress",
    "review": "Review",
    "done": "Done",
}

# 유효한 command 값 (체인 구분자 > 포함 시 각 토큰 검증)
_VALID_COMMANDS: set[str] = {"implement", "review", "research"}

# 복수 항목 필드 목록 (TC-06 대상)
_MULTI_FIELDS: list[str] = ["goal", "target", "constraints", "criteria", "context"]


def find_kanban_root(project_root: str) -> str:
    """칸반 루트 디렉터리 경로를 반환한다.

    Args:
        project_root: 프로젝트 루트 절대 경로

    Returns:
        .claude.workflow/kanban 절대 경로
    """
    return os.path.join(project_root, ".claude.workflow", "kanban")


def load_ticket_xml(xml_path: str) -> dict[str, Any]:
    """티켓 XML 파일을 파싱하여 dict로 반환한다.

    파싱 실패 시 빈 dict를 반환한다.

    Args:
        xml_path: 티켓 XML 파일 절대 경로

    Returns:
        {number, title, status, command, goal, target, constraints,
         criteria, context, relations(list[dict])} 형태의 딕셔너리.
        파싱 실패 시 빈 dict.
    """
    if not os.path.isfile(xml_path):
        return {}

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError:
        return {}

    def _text(tag: str) -> str:
        """태그 내부 텍스트를 반환한다. 없으면 빈 문자열."""
        el = root.find(".//" + tag)
        return (el.text or "").strip() if el is not None else ""

    relations: list[dict[str, str]] = []
    for rel in root.findall(".//relations/relation"):
        rel_type = rel.get("type", "")
        rel_ticket = rel.get("ticket", "")
        if rel_type and rel_ticket:
            relations.append({"type": rel_type, "ticket": rel_ticket})

    return {
        "number": _text("number"),
        "title": _text("title"),
        "status": _text("status"),
        "command": _text("command"),
        "goal": _text("goal"),
        "target": _text("target"),
        "constraints": _text("constraints"),
        "criteria": _text("criteria"),
        "context": _text("context"),
        "relations": relations,
        "_path": xml_path,
    }


def build_ticket_location_map(kanban_root: str) -> dict[str, str]:
    """칸반 루트의 4개 디렉터리를 순회하여 티켓 번호 → 디렉터리 위치 매핑을 반환한다.

    Args:
        kanban_root: 칸반 루트 절대 경로 (.claude.workflow/kanban)

    Returns:
        {T-NNN: "open"|"progress"|"review"|"done"} 딕셔너리.
    """
    location_map: dict[str, str] = {}
    for dir_name in ("open", "progress", "review", "done"):
        dir_path = os.path.join(kanban_root, dir_name)
        if not os.path.isdir(dir_path):
            continue
        for fname in os.listdir(dir_path):
            if not fname.endswith(".xml"):
                continue
            ticket_number = fname[:-4]  # 확장자 제거
            location_map[ticket_number] = dir_name
    return location_map


def extract_relations(ticket_data: dict[str, Any]) -> list[dict[str, str]]:
    """ticket_data에서 relations 목록을 반환한다.

    Args:
        ticket_data: load_ticket_xml()이 반환한 딕셔너리

    Returns:
        [{type, ticket}, ...] 목록.
    """
    return ticket_data.get("relations", [])


def validate_ticket_status_consistency(
    kanban_root: str, location_map: dict[str, str]
) -> list[str]:
    """TC-01: 디렉터리 위치 vs XML <status> 불일치 검증.

    디렉터리 위치와 XML <status> 값이 불일치하면 경고를 생성한다.

    Args:
        kanban_root: 칸반 루트 절대 경로
        location_map: build_ticket_location_map() 반환값

    Returns:
        경고 메시지 목록.
    """
    warnings: list[str] = []
    for ticket_number, dir_name in location_map.items():
        xml_path = os.path.join(kanban_root, dir_name, f"{ticket_number}.xml")
        data = load_ticket_xml(xml_path)
        if not data:
            continue
        xml_status = data.get("status", "")
        expected_status = _DIR_TO_STATUS.get(dir_name, "")
        if expected_status and xml_status and xml_status != expected_status:
            warnings.append(
                f"[TC-01] {ticket_number}: 디렉터리({dir_name}) vs XML status({xml_status}) 불일치 "
                f"(기대값: {expected_status})"
            )
    return warnings


def validate_derived_ticket_completion(
    kanban_root: str, location_map: dict[str, str]
) -> list[str]:
    """TC-02: derived-from 파생 티켓 미완료 + 원본 done 경고.

    파생 티켓이 done이 아닌 상태에서 원본 티켓이 done에 있으면 경고를 생성한다.

    Args:
        kanban_root: 칸반 루트 절대 경로
        location_map: build_ticket_location_map() 반환값

    Returns:
        경고 메시지 목록.
    """
    warnings: list[str] = []
    for ticket_number, dir_name in location_map.items():
        xml_path = os.path.join(kanban_root, dir_name, f"{ticket_number}.xml")
        data = load_ticket_xml(xml_path)
        if not data:
            continue
        for rel in data.get("relations", []):
            if rel.get("type") != "derived-from":
                continue
            origin_ticket = rel.get("ticket", "")
            if not origin_ticket:
                continue
            origin_dir = location_map.get(origin_ticket, "")
            if origin_dir == "done" and dir_name != "done":
                warnings.append(
                    f"[TC-02] {ticket_number}(파생 티켓)이 미완료({dir_name})인데 "
                    f"원본 {origin_ticket}이 done 상태임"
                )
    return warnings


def validate_ticket_xml_fields(
    ticket_data: dict[str, Any], ticket_number: str, dir_name: str
) -> list[str]:
    """TC-03/04/05/06: 단일 티켓 XML 필드 검증.

    TC-03: open/progress/review 티켓에 number/command/prompt 필수 태그 존재
    TC-04: command 값이 implement|review|research (체인 > 포함)
    TC-05: open/progress/review 티켓에 goal/target 비어있으면 WARN
    TC-06: 복수 항목 필드에 \\n 개행 누락 시 WARN (줄 수 대비 개행 비율 기반)

    Args:
        ticket_data: load_ticket_xml()이 반환한 딕셔너리
        ticket_number: 티켓 번호 (예: T-001)
        dir_name: 디렉터리 위치 (open/progress/review/done)

    Returns:
        경고 메시지 목록.
    """
    warnings: list[str] = []
    is_active = dir_name in ("open", "progress", "review")

    if not is_active:
        return warnings

    # TC-03: 필수 태그 존재 여부
    if not ticket_data.get("number"):
        warnings.append(f"[TC-03] {ticket_number}: <number> 태그 누락 또는 빈 값")
    if not ticket_data.get("command"):
        warnings.append(f"[TC-03] {ticket_number}: <command> 태그 누락 또는 빈 값")
    # prompt 존재 여부: goal 또는 target 중 하나라도 있으면 prompt 블록 존재로 간주
    has_prompt = bool(ticket_data.get("goal") or ticket_data.get("target"))
    if not has_prompt:
        warnings.append(f"[TC-03] {ticket_number}: <prompt> 블록 내 내용 없음")

    # TC-04: command 값 유효성
    raw_command = ticket_data.get("command", "")
    if raw_command:
        # 체인 구분자 > 로 분리 후 각 토큰 검증
        tokens = [t.strip() for t in raw_command.split(">") if t.strip()]
        invalid_tokens = [t for t in tokens if t not in _VALID_COMMANDS]
        if invalid_tokens:
            warnings.append(
                f"[TC-04] {ticket_number}: 유효하지 않은 command 값 {invalid_tokens} "
                f"(허용: {sorted(_VALID_COMMANDS)})"
            )

    # TC-05: goal/target 빈 값
    if not ticket_data.get("goal", "").strip():
        warnings.append(f"[TC-05] {ticket_number}: <goal> 비어있음")
    if not ticket_data.get("target", "").strip():
        warnings.append(f"[TC-05] {ticket_number}: <target> 비어있음")

    # TC-06: 복수 항목 필드 개행 누락
    for field in _MULTI_FIELDS:
        value = ticket_data.get(field, "")
        if not value:
            continue
        lines = [ln for ln in value.split("\n") if ln.strip()]
        # 2줄 이상인데 개행 문자(\n)가 없으면 경고
        # XML 파싱 시 실제 개행은 \n으로 이미 존재하므로,
        # 원본 텍스트의 실제 줄 수 vs 개행 수로 판단
        line_count = len(lines)
        # 2줄 이상이고 실제 줄 수가 1이면 개행 없이 한 줄에 붙여 쓴 것
        # (XML 파싱 후 stripped 결과로 판단)
        raw_value = ticket_data.get(field, "")
        actual_newlines = raw_value.count("\n")
        if line_count >= 2 and actual_newlines == 0:
            warnings.append(
                f"[TC-06] {ticket_number}: <{field}> 복수 항목({line_count}개)에 \\n 개행 누락"
            )

    return warnings


def validate_all_tickets_xml_fields(
    kanban_root: str, location_map: dict[str, str]
) -> list[str]:
    """TC-03~06: 전체 티켓 XML 필드 일괄 검증.

    Args:
        kanban_root: 칸반 루트 절대 경로
        location_map: build_ticket_location_map() 반환값

    Returns:
        경고 메시지 목록.
    """
    warnings: list[str] = []
    for ticket_number, dir_name in sorted(location_map.items()):
        xml_path = os.path.join(kanban_root, dir_name, f"{ticket_number}.xml")
        data = load_ticket_xml(xml_path)
        if not data:
            continue
        warnings.extend(validate_ticket_xml_fields(data, ticket_number, dir_name))
    return warnings


def validate_relation_links(
    kanban_root: str,
    location_map: dict[str, str],
    full_location_map: dict[str, str] | None = None,
) -> list[str]:
    """TC-07: 관계 링크 대상 티켓 존재 여부 검증.

    relations에 참조된 티켓이 칸반에 존재하지 않으면 경고를 생성한다.

    Args:
        kanban_root: 칸반 루트 절대 경로
        location_map: 검증 대상 티켓 맵 (단일 또는 전체)
        full_location_map: 링크 존재 여부 확인용 전체 티켓 맵.
            None이면 location_map을 전체 맵으로 사용한다.

    Returns:
        경고 메시지 목록.
    """
    existence_map = full_location_map if full_location_map is not None else location_map
    warnings: list[str] = []
    for ticket_number, dir_name in location_map.items():
        xml_path = os.path.join(kanban_root, dir_name, f"{ticket_number}.xml")
        data = load_ticket_xml(xml_path)
        if not data:
            continue
        for rel in data.get("relations", []):
            target_ticket = rel.get("ticket", "")
            if not target_ticket:
                continue
            if target_ticket not in existence_map:
                warnings.append(
                    f"[TC-07] {ticket_number}: 관계 링크 대상 {target_ticket}({rel.get('type', '')})이 "
                    f"칸반에 존재하지 않음"
                )
    return warnings


def validate_tickets(
    kanban_root: str, single_ticket: str | None = None
) -> list[str]:
    """칸반 티켓 전체 또는 단일 티켓을 검증하고 경고 목록을 반환한다.

    TC-01~TC-07 7종 검증 규칙을 순차 실행한다.

    Args:
        kanban_root: 칸반 루트 절대 경로
        single_ticket: 단일 티켓 검증 시 티켓 번호 (예: T-001). None이면 전체 검증.

    Returns:
        경고 메시지 목록.
    """
    if not os.path.isdir(kanban_root):
        return [f"[ERROR] 칸반 루트 디렉터리를 찾을 수 없습니다: {kanban_root}"]

    full_location_map = build_ticket_location_map(kanban_root)
    if not full_location_map:
        return ["[WARN] 칸반에서 티켓을 찾을 수 없습니다."]

    # 단일 티켓 모드: TC-01~06은 단일 티켓 맵, TC-07은 전체 맵으로 링크 검증
    if single_ticket:
        if single_ticket not in full_location_map:
            return [f"[ERROR] 티켓 {single_ticket}을 칸반에서 찾을 수 없습니다."]
        target_map = {single_ticket: full_location_map[single_ticket]}
    else:
        target_map = full_location_map

    warnings: list[str] = []

    # TC-01: 디렉터리 vs XML status 불일치
    warnings.extend(validate_ticket_status_consistency(kanban_root, target_map))

    # TC-02: derived-from 파생 미완료 + 원본 done
    warnings.extend(validate_derived_ticket_completion(kanban_root, target_map))

    # TC-03~06: XML 필드 검증
    warnings.extend(validate_all_tickets_xml_fields(kanban_root, target_map))

    # TC-07: 관계 링크 끊김 (TC-07은 전체 location_map 기준으로 존재 여부 확인)
    warnings.extend(validate_relation_links(kanban_root, target_map, full_location_map))

    return warnings


def _print_validate_result(warnings: list[str], mode_label: str) -> None:
    """검증 결과를 표준 출력 형식으로 출력한다.

    Args:
        warnings: 경고 메시지 목록
        mode_label: 모드 레이블 (예: "PLAN", "TICKET")
    """
    if not warnings:
        print(
            f"[STATE] VALIDATE-{mode_label} 검증 통과",
            flush=True,
        )
        print(
            ">> 경고 0건",
            flush=True,
        )
        return

    print(
        f"[STATE] VALIDATE-{mode_label} [WARN]",
        flush=True,
    )
    print(
        f">> 경고 {len(warnings)}건 발견",
        flush=True,
    )
    print()
    for i, warning in enumerate(warnings, 1):
        print(f"  {i}. {warning}")


def _build_parser() -> argparse.ArgumentParser:
    """plan_validator CLI용 ArgumentParser를 생성하여 반환한다."""
    parser = argparse.ArgumentParser(
        prog="flow-validate",
        description=(
            "plan.md 구조 검증 — Phase 균형·작업 편차·스킬 부족·WHAT/HOW 분리를 검사한다.\n"
            "--mode ticket 시 칸반 티켓 XML 구조 검증(TC-01~07)을 수행한다."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "입력 형식:\n"
            "  1. registryKey (YYYYMMDD-HHMMSS 패턴):\n"
            "       flow-validate 20260303-124206\n"
            "  2. workDir 경로:\n"
            "       flow-validate .workflow/20260303-124206/작업명/implement\n"
            "  3. plan.md 직접 경로:\n"
            "       flow-validate .workflow/20260303-124206/.../implement/plan.md\n"
            "  4. ticket 모드 (전체):\n"
            "       flow-validate --mode ticket\n"
            "  5. ticket 모드 (단일):\n"
            "       flow-validate --mode ticket --ticket T-001\n"
            "\n"
            "검증 항목 (plan 모드):\n"
            "  1. Phase 균형  : Mermaid 서브그래프에서 Phase별 워커 수 추출,\n"
            "                   최대/최소 비율 3배 이상 시 경고\n"
            "  2. 작업 편차   : 같은 Phase 내 워커 간 작업 항목 수 편차 2 초과 시 경고\n"
            "  3. 스킬 부족   : T2(10+) 태스크에서 스킬 1개만 배정 시 경고\n"
            "  4. WHAT/HOW   : criteria/goal/context 재서술 탐지 (advisory)\n"
            "\n"
            "검증 항목 (ticket 모드):\n"
            "  TC-01: 디렉터리 위치 vs XML status 불일치\n"
            "  TC-02: derived-from 파생 미완료 + 원본 done 경고\n"
            "  TC-03: 필수 태그 누락 (number/command/prompt)\n"
            "  TC-04: command 값 유효성 (implement|review|research)\n"
            "  TC-05: goal/target 빈 값 경고\n"
            "  TC-06: 복수 항목 필드 개행 누락 경고\n"
            "  TC-07: 관계 링크 대상 티켓 존재 여부\n"
            "\n"
            + build_common_epilog()
        ),
    )
    parser.add_argument(
        "plan_path",
        metavar="plan_path",
        nargs="?",
        default=None,
        help=(
            "검증할 plan.md 경로, workDir 경로, 또는 registryKey "
            "(YYYYMMDD-HHMMSS 형식). --mode ticket 시 생략 가능."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["plan", "ticket"],
        default="plan",
        help="검증 모드 선택: plan(기본값) 또는 ticket",
    )
    parser.add_argument(
        "--ticket",
        metavar="TICKET_NUMBER",
        default=None,
        help="단일 티켓 검증 (--mode ticket 시 사용, 예: T-001)",
    )
    return parser


def main() -> None:
    """CLI 진입점. 인자 파싱 후 검증 결과를 출력한다."""
    parser = _build_parser()
    args = parser.parse_args()

    mode: str = args.mode
    _work_dir = resolve_work_dir_for_logging()

    # --- ticket 모드 ---
    if mode == "ticket":
        if _work_dir:
            append_log(_work_dir, "INFO", "plan_validator: start mode=ticket")
        kanban_root = find_kanban_root(PROJECT_ROOT)
        warnings = validate_tickets(kanban_root, single_ticket=args.ticket)
        if _work_dir and warnings:
            append_log(
                _work_dir,
                "WARN",
                f"plan_validator: ticket mode {len(warnings)} warnings found",
            )
        _print_validate_result(warnings, "TICKET")
        sys.exit(0)

    # --- plan 모드 (기본) ---
    plan_path: str | None = args.plan_path
    if plan_path is None:
        parser.error("plan 모드에서는 plan_path 인자가 필요합니다.")
        return  # unreachable, mypy 대응

    # 3단계 경로 해석 분기
    if not plan_path.endswith(".md"):
        # .md로 끝나지 않는 경우: registryKey 또는 workDir로 해석
        resolved_dir: str = resolve_work_dir(plan_path, PROJECT_ROOT)
        plan_path = os.path.join(resolved_dir, "plan.md")

    # 상대 경로를 절대 경로로 변환
    if not os.path.isabs(plan_path):
        plan_path = os.path.join(PROJECT_ROOT, plan_path)

    if _work_dir:
        append_log(_work_dir, "INFO", f"plan_validator: start path={plan_path}")

    warnings = validate(plan_path)
    if _work_dir and warnings:
        append_log(
            _work_dir,
            "WARN",
            f"plan_validator: plan mode {len(warnings)} warnings found",
        )

    _print_validate_result(warnings, "PLAN")
    sys.exit(0)


if __name__ == "__main__":
    main()
