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
    python3 .agent-factory/engine/sync/catalog_sync.py              # Create/Update Catalog
    python3 .agent-factory/engine/sync/catalog_sync.py --dry-run     # Preview (no file writing)

종료 코드: 0 성공, 1 실패
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Optional

_agent_factory_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
)
if _agent_factory_dir not in sys.path:
    sys.path.insert(0, _agent_factory_dir)

from engine.core.skills.state import is_archived, load_skill_state
from engine.flow.cli_utils import build_common_epilog

from engine.common import (
    resolve_project_root,
)

PROJECT_ROOT = resolve_project_root()
SKILLS_DIR = os.path.join(PROJECT_ROOT, ".claude", "skills")
CATALOG_FILE = os.path.join(SKILLS_DIR, "skill-catalog.md")

# Excluded prefixes: Workflow-specific skills
EXCLUDE_PREFIXES = ("workflow-agent", "workflow-wf")

# =============================================================================
# Command Default Mapping (single source — integrated from existing command-skill-map.md)
# Modify this constant when changing mappings.
# =============================================================================
COMMAND_DEFAULTS: list[tuple[str, str, str]] = [
    ("implement", "review-code-quality, workflow-system", "Code quality checks (including Generator-Critic loops), verification before completion (including incremental verification). Conditional loading of manager skills when detecting asset management keywords"),
    ("review", "review-requesting, review-code-quality", "Apply review checklist + quantitative quality check. Conditional loading of expert review skills when security/architecture/frontend/performance keywords are detected"),
    ("research", "research-general, research-integrated", "Web research (research-general) + research-integrated. Supports cross-validation and source evaluation with references/ guide. Automatically loads parallel/verification skills for each keyword. Conditional loading of analyze-* skills when analysis keyword is detected. Code exploration (research-deep) is conditionally loaded based on planner LLM judgment"),
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

    # extract frontmatter (--- ... ---)
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None

    fm_text = match.group(1)

    # name parsing
    name_match = re.search(r'^name:\s*"?([^"\n]+)"?\s*$', fm_text, re.MULTILINE)
    if name_match:
        result["name"] = name_match.group(1).strip()

    # Parsing description (string within quotes)
    desc_match = re.search(r'^description:\s*"((?:[^"\\]|\\.)*)"', fm_text, re.MULTILINE)
    if desc_match:
        result["description"] = desc_match.group(1).strip()
    else:
        # description without quotes
        desc_match2 = re.search(r'^description:\s*(.+)$', fm_text, re.MULTILINE)
        if desc_match2:
            result["description"] = desc_match2.group(1).strip()

    # disable-model-invocation parsing
    dmi_match = re.search(r'^disable-model-invocation:\s*(true|false)', fm_text, re.MULTILINE)
    if dmi_match:
        result["disable-model-invocation"] = dmi_match.group(1).lower() == "true"

    # scope parsing (global default)
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

    skill_state = load_skill_state()

    if not os.path.isdir(SKILLS_DIR):
        print(f"[ERROR] skills directory does not exist: {SKILLS_DIR}", file=sys.stderr)
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

        # Exclusion conditions: disable-model-invocation: true or workflow prefix
        if fm["disable-model-invocation"]:
            excluded_count += 1
            continue

        if any(name.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
            excluded_count += 1
            continue

        # Exclusion 3: Archived Skills
        if is_archived(name, skill_state):
            excluded_count += 1
            continue

        skill_entry: dict[str, str] = {
            "name": str(name),
            "description": str(fm["description"] or "(no description)"),
        }

        # Classified according to scope
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
    lines.append("| command | Autoload Skill | Use |")
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
    lines.append("> This file is automatically created by `catalog_sync.py`. Please do not edit it yourself.")
    lines.append(f"> Active Skills: {total} (Specialization: {len(global_skills)}, Project: {len(project_skills)})")
    lines.append("")

    # Section 1: Command Default Mapping
    lines.append("## Command Default Mapping")
    lines.append("")
    lines.append(command_mapping.rstrip())
    lines.append("")

    # Section 2: Skill Descriptions (Specialization Skills)
    lines.append("## Skill Descriptions")
    lines.append("")
    lines.append("| Skill name | description |")
    lines.append("|--------|-------------|")
    for skill in global_skills:
        # description escaping my pipe character
        desc = skill["description"].replace("|", "\\|")
        lines.append(f"| {skill['name']} | {desc} |")
    lines.append("")

    # Section 3: Project Skills
    lines.append("## Project Skills")
    lines.append("")
    if project_skills:
        lines.append("| Skill name | description |")
        lines.append("|--------|-------------|")
        for skill in project_skills:
            desc = skill["description"].replace("|", "\\|")
            lines.append(f"| {skill['name']} | {desc} |")
    else:
        lines.append("(No project skills)")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    """CLI 진입점. 스킬 카탈로그를 생성하거나 미리보기를 출력한다.

    --dry-run 플래그가 있으면 파일을 쓰지 않고 예상 결과만 출력한다.
    종료 코드: 0 성공, 1 실패
    """
    parser = argparse.ArgumentParser(
        prog="flow-catalog",
        description="Create/update skill catalog (skill-catalog.md)",
        epilog=build_common_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prints only expected results without writing a file",
    )
    args = parser.parse_args()
    dry_run = args.dry_run

    # Skill Scan
    global_skills, project_skills, excluded_count = scan_skills()
    total = len(global_skills) + len(project_skills)

    # Create mapping table (from embedded data)
    command_mapping = build_command_default_mapping()

    # Create catalog
    catalog_content = generate_catalog(global_skills, project_skills, command_mapping)
    catalog_size = len(catalog_content.encode("utf-8"))

    if dry_run:
        print("[STATE] CATALOG", flush=True)
        print(f">> DRY-RUN active skills {total}", flush=True)
        print("[DRY-RUN] Skill Catalog Preview")
        print(f"Active Skills: {total} (Specialization: {len(global_skills)}, Project: {len(project_skills)})")
        print(f"Excluded skills: {excluded_count}")
        print(f"Expected size: {catalog_size:,} bytes")
        print(f"Target file: {CATALOG_FILE}")
        print()
        print("To actually create it: python3 .agent-factory/engine/sync/catalog_sync.py")
        print(flush=True)
        sys.exit(0)

    # write file
    try:
        with open(CATALOG_FILE, "w", encoding="utf-8") as f:
            f.write(catalog_content)

        actual_size = os.path.getsize(CATALOG_FILE)
        print("[STATE] CATALOG", flush=True)
        print(f">> {total} active skills, {actual_size:,} bytes", flush=True)
        print("[OK] Skill catalog creation completed")
        print(f"Active Skills: {total} (Specialization: {len(global_skills)}, Project: {len(project_skills)})")
        print(f"Excluded skills: {excluded_count}")
        print(f"File size: {actual_size:,} bytes")
        print(f"Save location: {CATALOG_FILE}")
        print(flush=True)
    except (IOError, OSError) as e:
        print(f"[ERROR] Failed to write catalog file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
