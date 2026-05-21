#!/usr/bin/env -S python3 -u
"""Skill catalog creation/update CLI (single source of truth).

Scans .claude/skills/*/SKILL.md to parse frontmatter,
Combined with the built-in Command Default Mapping data
Create skill-catalog.md.

This file is the single source of truth for mapping data.
The existing command-skill-map.md has been discarded, and when changing mapping, this file
Modify the COMMAND_DEFAULTS constant.

Main functions:
    parse_frontmatter: Parse SKILL.md frontmatter
    scan_skills: Scan entire skills directory
    build_command_default_mapping: Create command default skill mapping table
    generate_catalog: Generate content of skill-catalog.md
    main: CLI entry point

Usage:
    python3 .agent-factory/engine/sync/catalog_sync.py              # Create/Update Catalog
    python3 .agent-factory/engine/sync/catalog_sync.py --dry-run     # Preview (no file writing)

Exit code: 0 success, 1 failure
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
    """Parse name, description, and disable-model-invocation from YAML frontmatter in SKILL.md.

    Args:
        filepath: Absolute path to the SKILL.md file

    Returns:
        Parsed frontmatter dictionary. None if file read fails or frontmatter is not present.
        Keys: name, description, disable-model-invocation, scope
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
    """Scans all SKILL.mds and returns a list of active skills sorted by specialization/project.

    Traverses the SKILLS_DIR subdirectory and parses the frontmatter of each skill.
    disable-model-invocation: true Excludes skills and EXCLUDE_PREFIXES prefix skills.

    Returns:
        tuple: (global_skills, project_skills, excluded_count)
            - global_skills: scope=global list of skills (including name, description)
            - project_skills: scope=project skill list (including name and description)
            - excluded_count: Number of excluded skills
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
    """Create a basic skill mapping table for each command from the built-in COMMAND_DEFAULTS constant.

    Returns:
        Command-skill mapping string in Markdown table format (including newlines)
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
    """Create skill-catalog.md content.

    Args:
        global_skills: List of specialization (global) skills. Each item includes name and description keys.
        project_skills: List of project skills. Each item includes name and description keys.
        command_mapping: Command basic skill mapping markdown table string

    Returns:
        Full content string to write to skill-catalog.md file
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
    """CLI entry point. Create a skill catalog or print a preview.

    If the --dry-run flag is present, no file is written and only the expected results are output.
    Exit code: 0 success, 1 failure
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
