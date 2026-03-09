#!/usr/bin/env -S python3 -u
"""스킬 카탈로그 생성/갱신 CLI (단일 소스).

.claude/skills/*/SKILL.md를 전수 스캔하여 frontmatter를 파싱하고,
내장된 Command Default Mapping 데이터와 결합하여
skill-catalog.md를 생성합니다.

매핑 데이터는 이 파일이 단일 소스(Single Source of Truth)입니다.
기존 command-skill-map.md는 폐기되었으며, 매핑 변경 시 이 파일의
COMMAND_DEFAULTS 상수를 수정하세요.

주요 함수:
    parse_frontmatter: SKILL.md frontmatter 파싱
    scan_skills: 전체 스킬 디렉터리 스캔
    build_command_default_mapping: 명령어 기본 스킬 매핑 테이블 생성
    generate_catalog: skill-catalog.md 내용 생성
    main: CLI 진입점

사용법:
    python3 .claude/scripts/sync/catalog_sync.py              # 카탈로그 생성/갱신
    python3 .claude/scripts/sync/catalog_sync.py --dry-run     # 미리보기 (파일 쓰기 없음)

종료 코드: 0 성공, 1 실패
"""

from __future__ import annotations

import os
import re
import sys
from typing import Optional

# utils 패키지 import
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import (
    C_BOLD,
    C_CYAN,
    C_DIM,
    C_GREEN,
    C_RED,
    C_RESET,
    C_YELLOW,
    resolve_project_root,
)

PROJECT_ROOT = resolve_project_root()
SKILLS_DIR = os.path.join(PROJECT_ROOT, ".claude", "skills")
CATALOG_FILE = os.path.join(SKILLS_DIR, "skill-catalog.md")

# 제외 접두사: 워크플로우 전용 스킬
EXCLUDE_PREFIXES = ("workflow-agent-", "workflow-wf-")

# =============================================================================
# Command Default Mapping (단일 소스 — 기존 command-skill-map.md에서 통합)
# 매핑 변경 시 이 상수를 수정하세요.
# =============================================================================
COMMAND_DEFAULTS: list[tuple[str, str, str]] = [
    ("implement", "review-code-quality, workflow-system-verification", "코드 품질 검사(Generator-Critic 루프 포함), 완료 전 검증(점진적 검증 포함). 에셋 관리 키워드 감지 시 매니저 스킬 조건부 로드"),
    ("review", "review-requesting, review-code-quality", "리뷰 체크리스트 적용 + 정량적 품질 검사. 보안/아키텍처/프론트엔드/성능 키워드 감지 시 전문 리뷰 스킬 조건부 로드"),
    ("research", "research-general, research-integrated", "웹 조사(research-general) + 통합 조사(research-integrated). references/ 가이드로 교차 검증 및 출처 평가 지원. 키워드별 병렬/검증 스킬 자동 로드. 분석 키워드 감지 시 analyze-* 스킬 조건부 로드. 코드 탐색(research-deep)은 planner LLM 판단으로 조건부 로드"),
]


def parse_frontmatter(filepath: str) -> Optional[dict[str, object]]:
    """SKILL.md의 YAML frontmatter에서 name, description, disable-model-invocation을 파싱.

    Args:
        filepath: SKILL.md 파일의 절대 경로

    Returns:
        파싱된 frontmatter 딕셔너리. 파일 읽기 실패 또는 frontmatter 없으면 None.
        키: name, description, disable-model-invocation, scope
    """
    result: dict[str, object] = {"name": None, "description": None, "disable-model-invocation": False, "scope": "global"}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (IOError, OSError):
        return None

    # frontmatter 추출 (--- ... ---)
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None

    fm_text = match.group(1)

    # name 파싱
    name_match = re.search(r'^name:\s*"?([^"\n]+)"?\s*$', fm_text, re.MULTILINE)
    if name_match:
        result["name"] = name_match.group(1).strip()

    # description 파싱 (따옴표 내 문자열)
    desc_match = re.search(r'^description:\s*"((?:[^"\\]|\\.)*)"', fm_text, re.MULTILINE)
    if desc_match:
        result["description"] = desc_match.group(1).strip()
    else:
        # 따옴표 없는 description
        desc_match2 = re.search(r'^description:\s*(.+)$', fm_text, re.MULTILINE)
        if desc_match2:
            result["description"] = desc_match2.group(1).strip()

    # disable-model-invocation 파싱
    dmi_match = re.search(r'^disable-model-invocation:\s*(true|false)', fm_text, re.MULTILINE)
    if dmi_match:
        result["disable-model-invocation"] = dmi_match.group(1).lower() == "true"

    # scope 파싱 (global 기본값)
    scope_match = re.search(r'^scope:\s*(\S+)', fm_text, re.MULTILINE)
    if scope_match:
        result["scope"] = scope_match.group(1).strip().lower()
    else:
        result["scope"] = "global"

    return result


def scan_skills() -> tuple[list[dict[str, str]], list[dict[str, str]], int]:
    """모든 SKILL.md를 스캔하여 활성 스킬 목록을 전문화/프로젝트로 분류하여 반환.

    SKILLS_DIR 하위 디렉터리를 순회하며 각 스킬의 frontmatter를 파싱한다.
    disable-model-invocation: true 스킬과 EXCLUDE_PREFIXES 접두사 스킬은 제외한다.

    Returns:
        tuple: (global_skills, project_skills, excluded_count)
            - global_skills: scope=global 스킬 목록 (name, description 포함)
            - project_skills: scope=project 스킬 목록 (name, description 포함)
            - excluded_count: 제외된 스킬 수
    """
    global_skills: list[dict[str, str]] = []
    project_skills: list[dict[str, str]] = []
    excluded_count = 0

    if not os.path.isdir(SKILLS_DIR):
        print(f"{C_RED}[ERROR] skills 디렉터리가 존재하지 않습니다: {SKILLS_DIR}{C_RESET}", file=sys.stderr)
        sys.exit(1)

    for entry in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, entry)
        if not os.path.isdir(skill_dir):
            continue

        skill_file = os.path.join(skill_dir, "SKILL.md")
        if not os.path.isfile(skill_file):
            continue

        fm = parse_frontmatter(skill_file)
        if fm is None:
            continue

        name = fm["name"] or entry

        # 제외 조건: disable-model-invocation: true 또는 워크플로우 접두사
        if fm["disable-model-invocation"]:
            excluded_count += 1
            continue

        if any(name.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
            excluded_count += 1
            continue

        skill_entry: dict[str, str] = {
            "name": str(name),
            "description": str(fm["description"] or "(설명 없음)"),
        }

        # scope에 따라 분류
        if fm.get("scope") == "project":
            project_skills.append(skill_entry)
        else:
            global_skills.append(skill_entry)

    return global_skills, project_skills, excluded_count


def build_command_default_mapping() -> str:
    """내장 COMMAND_DEFAULTS 상수에서 명령어별 기본 스킬 매핑 테이블을 생성.

    Returns:
        마크다운 테이블 형식의 명령어-스킬 매핑 문자열 (개행 문자 포함)
    """
    lines = []
    lines.append("| 명령어 | 자동 로드 스킬 | 용도 |")
    lines.append("|--------|---------------|------|")
    for cmd, skills, desc in COMMAND_DEFAULTS:
        lines.append(f"| {cmd} | {skills} | {desc} |")
    return "\n".join(lines) + "\n"


def generate_catalog(
    global_skills: list[dict[str, str]],
    project_skills: list[dict[str, str]],
    command_mapping: str,
) -> str:
    """skill-catalog.md 내용을 생성.

    Args:
        global_skills: 전문화(global) 스킬 목록. 각 항목은 name, description 키를 포함.
        project_skills: 프로젝트(project) 스킬 목록. 각 항목은 name, description 키를 포함.
        command_mapping: 명령어 기본 스킬 매핑 마크다운 테이블 문자열

    Returns:
        skill-catalog.md 파일에 쓸 전체 내용 문자열
    """
    total = len(global_skills) + len(project_skills)
    lines = []

    lines.append("# Skill Catalog")
    lines.append("")
    lines.append("> 이 파일은 `catalog_sync.py`에 의해 자동 생성됩니다. 직접 편집하지 마세요.")
    lines.append(f"> 활성 스킬: {total}개 (전문화: {len(global_skills)}, 프로젝트: {len(project_skills)})")
    lines.append("")

    # Section 1: Command Default Mapping
    lines.append("## Command Default Mapping")
    lines.append("")
    lines.append(command_mapping.rstrip())
    lines.append("")

    # Section 2: Skill Descriptions (전문화 스킬)
    lines.append("## Skill Descriptions")
    lines.append("")
    lines.append("| 스킬명 | description |")
    lines.append("|--------|-------------|")
    for skill in global_skills:
        # description 내 파이프 문자 이스케이프
        desc = skill["description"].replace("|", "\\|")
        lines.append(f"| {skill['name']} | {desc} |")
    lines.append("")

    # Section 3: Project Skills (프로젝트 스킬)
    lines.append("## Project Skills")
    lines.append("")
    if project_skills:
        lines.append("| 스킬명 | description |")
        lines.append("|--------|-------------|")
        for skill in project_skills:
            desc = skill["description"].replace("|", "\\|")
            lines.append(f"| {skill['name']} | {desc} |")
    else:
        lines.append("(프로젝트 스킬 없음)")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    """CLI 진입점. 스킬 카탈로그를 생성하거나 미리보기를 출력한다.

    --dry-run 플래그가 있으면 파일을 쓰지 않고 예상 결과만 출력한다.
    종료 코드: 0 성공, 1 실패
    """
    dry_run = "--dry-run" in sys.argv

    # 스킬 스캔
    global_skills, project_skills, excluded_count = scan_skills()
    total = len(global_skills) + len(project_skills)

    # 매핑 테이블 생성 (내장 데이터에서)
    command_mapping = build_command_default_mapping()

    # 카탈로그 생성
    catalog_content = generate_catalog(global_skills, project_skills, command_mapping)
    catalog_size = len(catalog_content.encode("utf-8"))

    if dry_run:
        print(f"{C_CYAN}[DRY-RUN]{C_RESET} 스킬 카탈로그 미리보기")
        print(f"  활성 스킬: {C_BOLD}{total}{C_RESET}개 (전문화: {len(global_skills)}, 프로젝트: {len(project_skills)})")
        print(f"  제외 스킬: {C_DIM}{excluded_count}{C_RESET}개")
        print(f"  예상 크기: {C_BOLD}{catalog_size:,}{C_RESET} bytes")
        print(f"  대상 파일: {C_DIM}{CATALOG_FILE}{C_RESET}")
        print()
        print(f"  {C_DIM}실제 생성하려면: python3 .claude/scripts/sync/catalog_sync.py{C_RESET}")
        print(flush=True)
        sys.exit(0)

    # 파일 쓰기
    try:
        with open(CATALOG_FILE, "w", encoding="utf-8") as f:
            f.write(catalog_content)

        actual_size = os.path.getsize(CATALOG_FILE)
        print(f"{C_GREEN}[OK]{C_RESET} 스킬 카탈로그 생성 완료")
        print(f"  활성 스킬: {C_BOLD}{total}{C_RESET}개 (전문화: {len(global_skills)}, 프로젝트: {len(project_skills)})")
        print(f"  제외 스킬: {C_DIM}{excluded_count}{C_RESET}개")
        print(f"  파일 크기: {C_BOLD}{actual_size:,}{C_RESET} bytes")
        print(f"  저장 위치: {C_DIM}{CATALOG_FILE}{C_RESET}")
        print(flush=True)
    except (IOError, OSError) as e:
        print(f"{C_RED}[ERROR] 카탈로그 파일 쓰기 실패: {e}{C_RESET}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
