#!/usr/bin/env -S python3 -u
"""
skill_mapper.py - Phase 0 결정적 스킬 매핑 스크립트

plan.md의 태스크 skills 컬럼 + 명령어 기본 매핑 + 키워드 매칭으로
skill-map.md를 결정적으로 생성한다. LLM 불필요.

사용법:
  python3 .claude/scripts/flow/skill_mapper.py <registryKey>

입력:
  registryKey - YYYYMMDD-HHMMSS 형식 워크플로우 식별자
                workDir, plan.md 경로, command는 자동 해석

출력:
  <workDir>/work/skill-map.md (exit 0) 또는 에러 (exit 1)
  <workDir>/work/context/WXX-context.md (태스크별 컨텍스트 슬라이스)
"""

import os
import re
import sys

# 프로젝트 루트 결정
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import C_CLAUDE, C_DIM, C_RESET, load_json_file, resolve_abs_work_dir, resolve_project_root

# flow 디렉토리를 sys.path에 추가 (같은 디렉토리 내 모듈 직접 import용)
_flow_dir = os.path.dirname(os.path.abspath(__file__))
if _flow_dir not in sys.path:
    sys.path.insert(0, _flow_dir)

from plan_validator import parse_md_table_columns

PROJECT_ROOT = resolve_project_root()
SKILLS_DIR = os.path.join(PROJECT_ROOT, ".claude", "skills")
CATALOG_FILE = os.path.join(SKILLS_DIR, "skill-catalog.md")


def parse_catalog():
    """skill-catalog.md에서 command defaults와 keyword index를 파싱."""
    defaults = {}   # command -> [skill_names]
    keywords = {}   # keyword -> [skill_names]

    if not os.path.isfile(CATALOG_FILE):
        return defaults, keywords

    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")

    # Command Default Mapping 섹션 파싱
    in_cmd = False
    for line in lines:
        if "## Command Default Mapping" in line:
            in_cmd = True
            continue
        if in_cmd and line.startswith("## "):
            break
        if in_cmd and line.startswith("|") and not line.startswith("| 명령어") and not line.startswith("|---"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                cmd = parts[1].strip()
                skills_str = parts[2].strip()
                if cmd and skills_str:
                    defaults[cmd] = [s.strip() for s in skills_str.split(",")]

    # Keyword Index 섹션 파싱
    in_kw = False
    for line in lines:
        if "## Keyword Index" in line:
            in_kw = True
            continue
        if in_kw and line.startswith("## "):
            break
        if in_kw and line.startswith("|") and not line.startswith("| 키워드") and not line.startswith("|---"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                kw_str = parts[1].strip()
                skills_str = parts[2].strip()
                if kw_str and skills_str:
                    skill_list = [s.strip() for s in skills_str.split(",")]
                    for kw in kw_str.split(","):
                        kw = kw.strip()
                        if kw:
                            keywords[kw] = skill_list

    return defaults, keywords


def parse_plan_tasks(plan_path):
    """plan.md에서 태스크 테이블을 파싱하여 taskId, description, skills를 추출."""
    tasks = []

    if not os.path.isfile(plan_path):
        print(f"[ERROR] plan.md를 찾을 수 없습니다: {plan_path}", file=sys.stderr)
        return tasks

    with open(plan_path, "r", encoding="utf-8") as f:
        content = f.read()

    column_keywords = {
        "taskId": ["taskid", "태스크", "id"],
        "description": ["설명", "작업 내용", "description", "작업"],
        "skills": ["스킬", "skill"],
    }

    rows = parse_md_table_columns(content, None, column_keywords)

    for row in rows:
        task_id = row.get("taskId", "")
        if not (task_id and re.match(r"^W\d+", task_id)):
            continue

        raw_skills = row.get("skills", "")
        if raw_skills and raw_skills != "-" and raw_skills != "없음":
            skills = [s.strip() for s in raw_skills.split("+") if s.strip()]
        else:
            skills = []

        tasks.append(
            {
                "taskId": task_id,
                "description": row.get("description", ""),
                "skills": skills,
            }
        )

    return tasks


def read_compact(skill_name):
    """스킬의 COMPACT.md 또는 SKILL.md 상위 30줄을 반환."""
    # COMPACT.md 우선
    compact_path = os.path.join(SKILLS_DIR, skill_name, "COMPACT.md")
    if os.path.isfile(compact_path):
        with open(compact_path, "r", encoding="utf-8") as f:
            return f.read().strip()

    # SKILL.md 폴백 (상위 30줄, frontmatter 제외)
    skill_path = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
    if os.path.isfile(skill_path):
        with open(skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        # frontmatter 제거
        fm_match = re.match(r"^---\s*\n.*?\n---\s*\n", content, re.DOTALL)
        if fm_match:
            content = content[fm_match.end():]

        lines = content.strip().split("\n")
        return "\n".join(lines[:30]).strip()

    return f"(스킬 '{skill_name}' 파일 없음)"


def deduplicate(skills):
    """순서 유지하면서 중복 제거."""
    seen = set()
    result = []
    for s in skills:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


def resolve_skills(task: dict, command: str, defaults: dict, keywords: dict) -> list[str]:
    """3단계 결정적 매칭으로 태스크의 최종 스킬 목록 결정.

    Level 0~2 매칭 결과가 비어있으면 skill_recommender.py의 TF-IDF 추천을 fallback으로 호출한다.
    """
    skills = []

    # Level 0: plan.md에 명시된 스킬
    if task["skills"]:
        skills.extend(task["skills"])

    # Level 1: 명령어 기본 매핑
    if command in defaults:
        skills.extend(defaults[command])

    # Level 2: 키워드 매칭
    desc_lower = task["description"].lower()
    for kw, skill_list in keywords.items():
        if kw.lower() in desc_lower:
            skills.extend(skill_list)

    skills = deduplicate(skills)

    # Level 3 (fallback): 3계층 매칭 결과가 없을 때 TF-IDF 추천 호출
    fallback_skills = []
    if not skills and task.get("description"):
        try:
            # lazy import: fallback이 필요한 경우에만 로드
            from skill_recommender import recommend
            candidates = recommend(task["description"])
            # score 0.1 이상인 스킬명만 추출
            fallback_skills = [name for name, score in candidates if score >= 0.1]
            skills = list(fallback_skills)
        except Exception as e:
            # import 실패 또는 예상치 못한 오류 시 경고 로그 출력, 폴백 체인 정상 진행
            print(f"[WARN] skill_recommender 호출 실패: {e}", file=sys.stderr)

    task["fallback_skills"] = fallback_skills
    return skills


def _build_skill_map_header(tasks):
    """skill-map.md의 헤더 및 요약 테이블 행 목록을 생성."""
    lines = []
    lines.append("# Skill Map")
    lines.append("")
    lines.append("> 이 파일은 `skill_mapper.py`에 의해 자동 생성됩니다.")
    lines.append("> Worker는 자신의 태스크 섹션(## WXX: 스킬 지침)만 참조합니다.")
    lines.append("")
    lines.append("## 태스크별 스킬 매핑")
    lines.append("")
    lines.append("| 태스크 | 스킬 |")
    lines.append("|--------|------|")
    for task in tasks:
        lines.extend(_build_skill_map_rows(task))
    lines.append("")
    return lines


def _build_skill_map_rows(task):
    """태스크별 요약 테이블 행과 인라인 스킬 지침 섹션 행 목록을 생성."""
    lines = []
    resolved = task.get("resolved", [])
    fallback = set(task.get("fallback_skills", []))
    if resolved:
        skill_parts = [f"{s} (추천)" if s in fallback else s for s in resolved]
        skill_str = ", ".join(skill_parts)
    else:
        skill_str = "(없음)"
    lines.append(f"| {task['taskId']} | {skill_str} |")
    return lines


def _build_task_skill_section(task):
    """태스크별 인라인 스킬 지침 섹션 행 목록을 생성."""
    task_resolved = task.get("resolved", [])
    if not task_resolved:
        return []
    lines = ["---", "", f"## {task['taskId']}: 스킬 지침", ""]
    task_instructions = task.get("instructions", {})
    for skill_name in task_resolved:
        compact = task_instructions.get(skill_name, "")
        if compact:
            lines.extend([f"### {skill_name}", "", compact, ""])
    return lines


def write_skill_map(work_dir, tasks):
    """skill-map.md를 생성.

    각 태스크 섹션에는 해당 태스크에 배정된 스킬 지침만 포함된다.
    다른 태스크의 스킬 지침이 혼재되지 않도록 태스크별 resolved 스킬로 필터링한다.
    """
    output_dir = os.path.join(work_dir, "work")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "skill-map.md")

    lines = _build_skill_map_header(tasks)
    for task in tasks:
        lines.extend(_build_task_skill_section(task))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


def slice_plan_context(plan_path, tasks, output_dir):
    """plan.md에서 각 워커의 태스크 섹션만 추출하여 work/context/WXX-context.md로 저장.

    "### WXX:" H3 서브섹션을 태스크별로 분리하여 워커가 자신에게 필요한
    컨텍스트(1-2K 토큰)만 읽을 수 있도록 슬라이싱한다.
    plan.md 전체(5-10K)를 로드하는 대신 태스크별 컨텍스트만 제공하여
    워커 컨텍스트 예산을 절감한다.

    Args:
        plan_path: plan.md 절대 경로
        tasks: parse_plan_tasks()에서 반환된 태스크 목록 (taskId 필드 필요)
        output_dir: work/context/ 디렉터리 기준 (work_dir/work/context/)

    Returns:
        생성된 컨텍스트 파일 경로 목록 (생성 성공한 파일만)
    """
    if not os.path.isfile(plan_path):
        print(f"[WARN] slice_plan_context: plan.md를 찾을 수 없습니다: {plan_path}", file=sys.stderr)
        return []

    with open(plan_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")

    # 태스크 ID 집합 (W01, W02 등)
    task_ids = {task["taskId"] for task in tasks if task.get("taskId")}

    # plan.md에서 "### WXX:" 패턴의 H3 섹션 위치를 탐색
    # 섹션 시작: "### W01:" 또는 "### W01 " 형태
    section_starts = {}  # taskId -> line_index
    h3_pattern = re.compile(r"^###\s+(W\d+)[:\s]")

    for i, line in enumerate(lines):
        m = h3_pattern.match(line)
        if m:
            tid = m.group(1)
            if tid in task_ids:
                section_starts[tid] = i

    if not section_starts:
        # H3 섹션이 없으면 스킵
        return []

    # 각 태스크 섹션 끝 위치 결정: 다음 H4 이하/H3/H2/H1이 나오거나 파일 끝
    sorted_starts = sorted(section_starts.items(), key=lambda x: x[1])
    end_pattern = re.compile(r"^#{1,4}\s+")

    os.makedirs(output_dir, exist_ok=True)
    created = []

    for idx, (task_id, start_line) in enumerate(sorted_starts):
        # 섹션 끝 탐색: 다음 H1/H2/H3 라인 또는 파일 끝
        end_line = len(lines)
        for j in range(start_line + 1, len(lines)):
            if end_pattern.match(lines[j]):
                end_line = j
                break

        section_lines = lines[start_line:end_line]

        # 후미 빈 줄 제거
        while section_lines and not section_lines[-1].strip():
            section_lines.pop()

        if not section_lines:
            continue

        section_content = "\n".join(section_lines) + "\n"

        # 파일명: WXX-context.md
        out_path = os.path.join(output_dir, f"{task_id}-context.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(section_content)

        created.append(out_path)

    return created


def main():
    if len(sys.argv) < 2:
        print("사용법: python3 skill_mapper.py <registryKey>", file=sys.stderr)
        sys.exit(1)

    registry_key = sys.argv[1]

    # registryKey → workDir, plan.md, command 자동 해석
    work_dir = resolve_abs_work_dir(registry_key, PROJECT_ROOT)
    plan_path = os.path.join(work_dir, "plan.md")
    ctx = load_json_file(os.path.join(work_dir, ".context.json"))
    command = ctx.get("command", "") if isinstance(ctx, dict) else ""

    if not command:
        print(f"[ERROR] .context.json에서 command를 찾을 수 없습니다: {work_dir}", file=sys.stderr)
        sys.exit(1)

    # 1. 카탈로그 파싱
    defaults, keywords = parse_catalog()

    # 2. plan.md 태스크 파싱
    tasks = parse_plan_tasks(plan_path)
    if not tasks:
        print(f"[WARN] plan.md에서 태스크를 찾을 수 없습니다: {plan_path}", file=sys.stderr)
        # 빈 skill-map.md라도 생성
        os.makedirs(os.path.join(work_dir, "work"), exist_ok=True)
        with open(os.path.join(work_dir, "work", "skill-map.md"), "w", encoding="utf-8") as f:
            f.write("# Skill Map\n\n> 태스크 없음\n")
        sys.exit(0)

    # 3. 각 태스크별 스킬 결정 + COMPACT.md 인라인
    for task in tasks:
        task["resolved"] = resolve_skills(task, command, defaults, keywords)
        task["instructions"] = {}
        for skill_name in task["resolved"]:
            task["instructions"][skill_name] = read_compact(skill_name)

    # 4. skill-map.md 생성
    output_path = write_skill_map(work_dir, tasks)

    # 5. 태스크별 컨텍스트 슬라이싱 (plan.md → work/context/WXX-context.md)
    context_dir = os.path.join(work_dir, "work", "context")
    created_contexts = slice_plan_context(plan_path, tasks, context_dir)

    # 배너 출력
    rel_path = os.path.relpath(output_path, PROJECT_ROOT)
    print(f"{C_CLAUDE}║ STATE:{C_RESET} {C_DIM}스킬 탐색{C_RESET}", flush=True)
    print(f"{C_CLAUDE}║{C_RESET} {C_CLAUDE}>>{C_RESET} {C_DIM}{rel_path}{C_RESET}", flush=True)
    if created_contexts:
        rel_ctx = os.path.relpath(context_dir, PROJECT_ROOT)
        print(f"{C_CLAUDE}║{C_RESET} {C_CLAUDE}>>{C_RESET} {C_DIM}{rel_ctx}/ ({len(created_contexts)}개 컨텍스트 슬라이스){C_RESET}", flush=True)


if __name__ == "__main__":
    main()
