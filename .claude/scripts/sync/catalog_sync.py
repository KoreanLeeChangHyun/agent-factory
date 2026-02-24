#!/usr/bin/env -S python3 -u
"""
catalog_sync.py - 스킬 카탈로그 생성/갱신 CLI

.claude/skills/*/SKILL.md를 전수 스캔하여 frontmatter를 파싱하고,
command-skill-map.md의 매핑 테이블을 추출하여 skill-catalog.md를 생성합니다.

사용법:
  python3 .claude/scripts/sync/catalog_sync.py              # 카탈로그 생성/갱신
  python3 .claude/scripts/sync/catalog_sync.py --dry-run     # 미리보기 (파일 쓰기 없음)

종료 코드: 0 성공, 1 실패
"""

import os
import re
import sys

# utils 패키지 import
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from utils.common import (
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
COMMAND_SKILL_MAP = os.path.join(SKILLS_DIR, "workflow-agent-work", "command-skill-map.md")

# 제외 접두사: 워크플로우 전용 스킬
EXCLUDE_PREFIXES = ("workflow-agent-", "workflow-cc-")


def parse_frontmatter(filepath):
    """SKILL.md의 YAML frontmatter에서 name, description, disable-model-invocation을 파싱."""
    result = {"name": None, "description": None, "disable-model-invocation": False}
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

    return result


def scan_skills():
    """모든 SKILL.md를 스캔하여 활성 스킬 목록을 반환."""
    active_skills = []
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

        active_skills.append({
            "name": name,
            "description": fm["description"] or "(설명 없음)",
        })

    return active_skills, excluded_count


def extract_command_default_mapping():
    """command-skill-map.md에서 명령어별 기본 스킬 매핑 테이블을 추출."""
    if not os.path.isfile(COMMAND_SKILL_MAP):
        return "| (command-skill-map.md를 찾을 수 없음) |\n"

    try:
        with open(COMMAND_SKILL_MAP, "r", encoding="utf-8") as f:
            content = f.read()
    except (IOError, OSError):
        return "| (command-skill-map.md 읽기 실패) |\n"

    # "## 명령어별 기본 스킬 매핑" 섹션 추출
    lines = content.split("\n")
    section_lines = []
    in_section = False
    for line in lines:
        if "## 명령어별 기본 스킬 매핑" in line:
            in_section = True
            continue
        if in_section:
            if line.startswith("## "):
                break
            if line.startswith("|"):
                section_lines.append(line)

    return "\n".join(section_lines) + "\n" if section_lines else "| (섹션 없음) |\n"


def extract_keyword_index():
    """command-skill-map.md에서 키워드 기반 추가 스킬 로드 테이블을 추출."""
    if not os.path.isfile(COMMAND_SKILL_MAP):
        return "| (command-skill-map.md를 찾을 수 없음) |\n"

    try:
        with open(COMMAND_SKILL_MAP, "r", encoding="utf-8") as f:
            content = f.read()
    except (IOError, OSError):
        return "| (command-skill-map.md 읽기 실패) |\n"

    # "## 키워드 기반 추가 스킬 로드" 섹션 추출
    lines = content.split("\n")
    section_lines = []
    in_section = False
    for line in lines:
        if "## 키워드 기반 추가 스킬 로드" in line:
            in_section = True
            continue
        if in_section:
            if line.startswith("## "):
                break
            if line.startswith("|"):
                section_lines.append(line)

    return "\n".join(section_lines) + "\n" if section_lines else "| (섹션 없음) |\n"


def generate_catalog(active_skills, command_mapping, keyword_index):
    """skill-catalog.md 내용을 생성."""
    lines = []

    lines.append("# Skill Catalog")
    lines.append("")
    lines.append("> 이 파일은 `catalog_sync.py`에 의해 자동 생성됩니다. 직접 편집하지 마세요.")
    lines.append(f"> 활성 스킬: {len(active_skills)}개")
    lines.append("")

    # Section 1: Command Default Mapping
    lines.append("## Command Default Mapping")
    lines.append("")
    lines.append(command_mapping.rstrip())
    lines.append("")

    # Section 2: Keyword Index
    lines.append("## Keyword Index")
    lines.append("")
    lines.append(keyword_index.rstrip())
    lines.append("")

    # Section 3: Skill Descriptions
    lines.append("## Skill Descriptions")
    lines.append("")
    lines.append("| 스킬명 | description |")
    lines.append("|--------|-------------|")
    for skill in active_skills:
        # description 내 파이프 문자 이스케이프
        desc = skill["description"].replace("|", "\\|")
        lines.append(f"| {skill['name']} | {desc} |")
    lines.append("")

    return "\n".join(lines)


def main():
    dry_run = "--dry-run" in sys.argv

    # 스킬 스캔
    active_skills, excluded_count = scan_skills()

    # 매핑 테이블 추출
    command_mapping = extract_command_default_mapping()
    keyword_index = extract_keyword_index()

    # 카탈로그 생성
    catalog_content = generate_catalog(active_skills, command_mapping, keyword_index)
    catalog_size = len(catalog_content.encode("utf-8"))

    if dry_run:
        print(f"{C_CYAN}[DRY-RUN]{C_RESET} 스킬 카탈로그 미리보기")
        print(f"  활성 스킬: {C_BOLD}{len(active_skills)}{C_RESET}개")
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
        print(f"  활성 스킬: {C_BOLD}{len(active_skills)}{C_RESET}개")
        print(f"  제외 스킬: {C_DIM}{excluded_count}{C_RESET}개")
        print(f"  파일 크기: {C_BOLD}{actual_size:,}{C_RESET} bytes")
        print(f"  저장 위치: {C_DIM}{CATALOG_FILE}{C_RESET}")
        print(flush=True)
    except (IOError, OSError) as e:
        print(f"{C_RED}[ERROR] 카탈로그 파일 쓰기 실패: {e}{C_RESET}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
