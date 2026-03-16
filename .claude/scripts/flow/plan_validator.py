#!/usr/bin/env -S python3 -u
"""plan_validator.py - 계획서(plan.md) 구조 검증 스크립트.

plan.md를 입력받아 다음을 검증한다:
(1) Mermaid 서브그래프에서 Phase별 워커 수 추출, 최대/최소 비율 3배 이상 시 경고
(2) 작업 목록 테이블에서 워커별 작업 항목 수 파싱, 편차 2 초과 시 경고
(3) T2(10+) 태스크에서 스킬 1개인 경우 경고

사용법:
  python3 plan_validator.py <plan_path>
  python3 plan_validator.py --help

출력:
  경고 목록 또는 "검증 통과"
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any

# 프로젝트 루트 결정
_scripts_dir: str = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import resolve_project_root, resolve_work_dir
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

    if warnings:
        _work_dir = resolve_work_dir_for_logging()
        if _work_dir:
            append_log(_work_dir, "WARN", f"plan_validator: {len(warnings)} warnings found")

    return warnings


def print_help() -> None:
    """사용법 및 검증 항목 설명을 stdout에 출력한다."""
    print("plan_validator.py - 계획서(plan.md) 구조 검증")
    print()
    print("사용법:")
    print("  python3 plan_validator.py <plan_path>")
    print("  python3 plan_validator.py --help")
    print()
    print("입력 형식:")
    print("  1. registryKey (YYYYMMDD-HHMMSS 패턴):")
    print("     python3 plan_validator.py 20260303-124206")
    print("  2. workDir 경로:")
    print("     python3 plan_validator.py .workflow/20260303-124206/plan_validator-경로해석-/implement")
    print("  3. plan.md 직접 경로:")
    print("     python3 plan_validator.py .workflow/20260303-124206/.../implement/plan.md")
    print()
    print("검증 항목:")
    print("  1. Phase 균형: Mermaid 서브그래프에서 Phase별 워커 수 추출,")
    print("     최대/최소 비율 3배 이상 시 경고")
    print("  2. 작업 편차: 같은 Phase 내 워커 간 작업 항목 수 편차")
    print("     2 초과 시 경고")
    print("  3. 스킬 부족: T2(10+) 태스크에서 스킬 1개만 배정 시 경고")
    print()
    print("출력:")
    print("  경고 목록 또는 '검증 통과'")


def main() -> None:
    """CLI 진입점. 인자 파싱 후 plan.md 검증 결과를 출력한다."""
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        print_help()
        sys.exit(0)

    plan_path: str = sys.argv[1]

    # 3단계 경로 해석 분기
    if not plan_path.endswith(".md"):
        # (b) .md로 끝나지 않는 경우: registryKey 또는 workDir로 해석
        resolved_dir: str = resolve_work_dir(plan_path, PROJECT_ROOT)
        plan_path = os.path.join(resolved_dir, "plan.md")

    # 상대 경로를 절대 경로로 변환
    if not os.path.isabs(plan_path):
        plan_path = os.path.join(PROJECT_ROOT, plan_path)

    _work_dir = resolve_work_dir_for_logging()
    if _work_dir:
        append_log(_work_dir, "INFO", f"plan_validator: start path={plan_path}")

    warnings = validate(plan_path)

    if not warnings:
        print("검증 통과")
        sys.exit(0)

    print(f"[WARN] plan_validator: 경고 {len(warnings)}건 발견:")
    print()
    for i, warning in enumerate(warnings, 1):
        print(f"  {i}. {warning}")

    sys.exit(0)


if __name__ == "__main__":
    main()
