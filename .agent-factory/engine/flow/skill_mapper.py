#!/usr/bin/env -S python3 -u
"""skill_mapper.py - Phase 0 skill mapping script.

Task skills column in plan.md + basic command mapping
Create skill-map.md. No LLM required.

Usage:
  python3 .agent-factory/engine/flow/skill_mapper.py <registryKey>

input:
  registryKey - Workflow identifier in YYYYMMDD-HHMMSS format.
                workDir, plan.md path, and command are automatically interpreted

output of power:
  <workDir>/work/skill-map.md (exit 0) or error (exit 1) or verification failure (exit 2)
  <workDir>/work/context/WXX-context.md (context slice per task)

exit code:
  0 - Success (skill mapping completed and validation passed)
  1 - Error (execution error such as missing argument, command not found, etc.)
  2 - Verification failed (skill not assigned or skill name does not exist)
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone, timedelta

# Determine project route
_engine_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import acquire_lock, load_json_file, release_lock, resolve_abs_work_dir, resolve_project_root

# Add flow directory to sys.path (for direct import of modules in the same directory)
_flow_dir = os.path.dirname(os.path.abspath(__file__))
if _flow_dir not in sys.path:
    sys.path.insert(0, _flow_dir)

from plan_validator import parse_md_table_columns
from cli_utils import registry_key_type, build_common_epilog

PROJECT_ROOT = resolve_project_root()


# ─── Logging Helper ───────────────────────────────────────────────────────────────────

def _append_log(abs_work_dir: str, level: str, message: str) -> None:
    """Records events in workflow.log. In case of failure, quietly skip."""
    try:
        # Delegate if flow_logger exists
        from flow_logger import append_log
        append_log(abs_work_dir, level, message)
        return
    except Exception:
        pass
    try:
        from datetime import timezone, timedelta
        kst = timezone(timedelta(hours=9))
        ts = datetime.now(kst).strftime("%Y-%m-%dT%H:%M:%S")
        log_path = os.path.join(abs_work_dir, "workflow.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {message}\n")
    except Exception:
        pass
SKILLS_DIR = os.path.join(PROJECT_ROOT, ".claude", "skills")
CATALOG_FILE = os.path.join(SKILLS_DIR, "skill-catalog.md")

# Context token budget guardrail (25% based on 200K)
TOKEN_BUDGET_LIMIT = 50_000

EXTENSION_SKILL_MAP: dict[str, str] = {
    ".py": "convention-python",
    ".js": "convention-front",
    ".ts": "convention-front",
    ".jsx": "convention-front",
    ".tsx": "convention-front",
}

# Section name pattern used for P1 priority search in parse_plan_tasks()
# If matching fails, section_pattern=None falls back to full search.
SECTION_PATTERNS = r"##\s*(Task\s*List|Task\s*List|Task\s*List|Task\s*Decomposition|Task\s*Plan)"


def resolve_skill_file(skill_name: str) -> str:
    """Returns the load path of the skill.

    If COMPACT.md exists, the COMPACT.md path is returned. If COMPACT.md does not exist, the SKILL.md path is returned.
    If both files do not exist, the path to SKILL.md is returned (existence cannot be guaranteed).

    Args:
        skill_name: Skill name (e.g. 'convention-python', 'review-code-quality')

    Returns:
        Absolute path to COMPACT.md or SKILL.md.

    Raises:
        When attempting to traverse the path, the workflow-agent/SKILL.md path is returned as a fallback.
    """
    skill_dir = os.path.join(SKILLS_DIR, skill_name)
    skill_dir = os.path.normpath(skill_dir)
    if not skill_dir.startswith(os.path.normpath(SKILLS_DIR)):
        print(f"[WARN] Block path traversal attempt: {skill_name}", file=sys.stderr)
        skill_dir = os.path.join(SKILLS_DIR, "workflow-agent")
        return os.path.join(skill_dir, "SKILL.md")
    compact_path = os.path.join(skill_dir, "COMPACT.md")
    skill_path = os.path.join(skill_dir, "SKILL.md")
    if os.path.isfile(compact_path):
        return compact_path
    return skill_path


def estimate_token_budget(resolved_skills: list[str]) -> int:
    """Returns the sum of the expected tokens in the skill list.

    Read each skill's COMPACT.md or SKILL.md file as binary.
    ASCII bytes (ascii_bytes // 4) and non-ASCII bytes (non_ascii_bytes // 6)
    Tokens are estimated using the Korean content correction method that is calculated separately.
    If the sum exceeds TOKEN_BUDGET_LIMIT, a warning log is output.

    Args:
        resolved_skills: List of skill names

    Returns:
        Expected token sum integer value.
    """
    total_tokens = 0
    for skill_name in resolved_skills:
        file_path = resolve_skill_file(skill_name)
        if os.path.isfile(file_path):
            try:
                with open(file_path, "rb") as f:
                    data = f.read()
                ascii_bytes = sum(1 for b in data if b < 0x80)
                non_ascii_bytes = len(data) - ascii_bytes
                total_tokens += ascii_bytes // 4 + non_ascii_bytes // 6
            except OSError:
                pass

    if total_tokens > TOKEN_BUDGET_LIMIT:
        print(
            f"[WARN] Skill token budget exceeded: {total_tokens} > {TOKEN_BUDGET_LIMIT}",
            file=sys.stderr,
        )

    return total_tokens


def parse_catalog() -> dict[str, list[str]]:
    """Parse command defaults from skill-catalog.md.

    Returns:
        defaults: command -> [skill_names] dictionary.
    """
    defaults: dict[str, list[str]] = {}

    if not os.path.isfile(CATALOG_FILE):
        return defaults

    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")

    # Command Default Mapping section parsing
    in_cmd = False
    for line in lines:
        if "## Command Default Mapping" in line:
            in_cmd = True
            continue
        if in_cmd and line.startswith("## "):
            break
        if in_cmd and line.startswith("|") and not line.startswith("| command") and not line.startswith("|---"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                cmd = parts[1].strip()
                skills_str = parts[2].strip()
                if cmd and skills_str:
                    defaults[cmd] = [s.strip() for s in skills_str.split(",")]

    return defaults


def parse_plan_tasks(plan_path):
    """Parse the task table from plan.md and extract taskId, description, and skills.

    Returns:
        tuple[list[dict], bool]: (tasks, p4_triggered)
            tasks — List of parsed tasks
            p4_triggered — P4 fallback (#True if ## T# heading) is used
    """
    tasks = []
    p4_triggered = False

    if not os.path.isfile(plan_path):
        print(f"[ERROR] Unable to find plan.md: {plan_path}", file=sys.stderr)
        return tasks, p4_triggered

    with open(plan_path, "r", encoding="utf-8") as f:
        content = f.read()

    column_keywords = {
        "taskId": ["taskid", "task", "id"],
        "description": ["explanation", "work detail", "description", "work"],
        "skills": ["skill", "skill"],
    }

    # P1: Search first with SECTION_PATTERNS, fallback to full search if no W-prefix rows exist
    rows = parse_md_table_columns(content, SECTION_PATTERNS, column_keywords)
    if not any(re.match(r"^W\d+", r.get("taskId", "")) for r in rows):
        rows = parse_md_table_columns(content, None, column_keywords)

    for row in rows:
        task_id = row.get("taskId", "")
        if not (task_id and re.match(r"^W\d+", task_id)):
            continue

        raw_skills = row.get("skills", "")
        if raw_skills and raw_skills != "-" and raw_skills != "doesn't exist":
            skills = [s.strip() for s in re.split(r"[+,]", raw_skills) if s.strip()]
        else:
            skills = []

        tasks.append(
            {
                "taskId": task_id,
                "description": row.get("description", ""),
                "skills": skills,
            }
        )

    # If there are no table parsing results, a fallback parse is attempted based on the W-prefix heading.
    if not tasks:
        heading_pattern = re.compile(r"^#{2,3}\s+(W\d+)[:\s]\s*(.+)", re.MULTILINE)
        for m in heading_pattern.finditer(content):
            tasks.append(
                {
                    "taskId": m.group(1),
                    "description": m.group(2).strip(),
                    "skills": [],
                }
            )
        if tasks:
            print(
                "[WARN] Table not found, use heading-based fallback parsing",
                file=sys.stderr,
            )

    # P3: If W-prefix heading fallback also fails, attempt Task X.Y heading fallback
    if not tasks:
        task_xy_pattern = re.compile(
            r"^#{2,4}\s+Task\s*\d+[\.\-]\d+[:\s]\s*(.+)",
            re.MULTILINE | re.IGNORECASE,
        )
        for idx, m in enumerate(task_xy_pattern.finditer(content), start=1):
            tasks.append(
                {
                    "taskId": f"W{idx:02d}",
                    "description": m.group(1).strip(),
                    "skills": [],
                }
            )
        if tasks:
            print(
                "[WARN] Use Task X.Y heading fallback parsing (skill not assigned, command defaults applied)",
                file=sys.stderr,
            )

    # P4: Try ### T# / ### T## heading fallback (if Planner used T-prefix instead of W-prefix)
    # Normalize to T1 → W01, T01 → W01 to block empty skill-map.md regression.
    if not tasks:
        t_prefix_pattern = re.compile(
            r"^#{2,4}\s+T(\d{1,2})[:\s]\s*(.+)",
            re.MULTILINE,
        )
        for m in t_prefix_pattern.finditer(content):
            n = int(m.group(1))
            task_id = f"W{n:02d}"
            tasks.append(
                {
                    "taskId": task_id,
                    "description": m.group(2).strip(),
                    "skills": [],
                }
            )
        if tasks:
            p4_triggered = True
            print(
                "[WARN] Use fallback parsing for '### T#' format headings"
                "(taskId 'T#' → 'W##' normalized, skill not assigned → command defaults applied)",
                file=sys.stderr,
            )

    return tasks, p4_triggered


def deduplicate(skills):
    """Remove duplicates while maintaining order."""
    seen = set()
    result = []
    for s in skills:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


def detect_extension_skills(description: str) -> list[str]:
    """Detects the file extension in the task description and returns a list of convention skills."""
    found_exts = set()

    # (a) File path.Extension: Word letters + dot + extension
    pattern_a = re.compile(r"\w+(\.[a-zA-Z]+)")
    for m in pattern_a.finditer(description):
        found_exts.add(m.group(1).lower())

    # (b) *.extension
    pattern_b = re.compile(r"\*(\.[a-zA-Z]+)")
    for m in pattern_b.finditer(description):
        found_exts.add(m.group(1).lower())

    # (c) Space/punctuation mark/Hangul after .extension (independent extension notation)
    pattern_c = re.compile(r"(\.[a-zA-Z]+)(?=[\s,.\u3131-\uD7A3]|$)")
    for m in pattern_c.finditer(description):
        found_exts.add(m.group(1).lower())

    result = []
    seen = set()
    for ext in sorted(found_exts):
        skill = EXTENSION_SKILL_MAP.get(ext)
        if skill and skill not in seen:
            seen.add(skill)
            result.append(skill)

    return result


def resolve_skills(task: dict, command: str, defaults: dict) -> list[str]:
    """Determine the final skill list of the task through 4-level (Level 0-1.5-2) matching.

    If the Level 0~1 matching result is empty, the TF-IDF recommendation in skill_recommender.py is called as a fallback.
    """
    if not command:
        return []

    skills = []

    # Level 0: Skills specified in plan.md
    if task["skills"]:
        skills.extend(task["skills"])

    # Level 1: Command basic mapping
    if command in defaults:
        skills.extend(defaults[command])

    skills = deduplicate(skills)

    # Level 1.5: Automatic mapping of extension-based convention skills
    if task.get("description"):
        ext_skills = detect_extension_skills(task["description"])
        for s in ext_skills:
            if s not in skills:
                skills.append(s)

    # Level 2 (fallback): Call TF-IDF recommendation when there are no matching results
    fallback_skills = []
    if not skills and task.get("description"):
        try:
            # lazy import: load only when a fallback is needed
            from skill_recommender import recommend
            candidates = recommend(task["description"])
            # Extract only skill names with score 0.1 or higher
            fallback_skills = [name for name, score in candidates if score >= 0.1]
            skills = list(fallback_skills)
        except Exception as e:
            # In case of import failure or unexpected error, warning log is output and fallback chain continues normally.
            print(f"[WARN] skill_recommender call failed: {e}", file=sys.stderr)

    task["fallback_skills"] = fallback_skills
    return skills


def _build_skill_map_header(tasks):
    """Create a list of header and summary table rows in skill-map.md."""
    lines = []
    lines.append("# Skill Map")
    lines.append("")
    lines.append("> This file is automatically generated by `skill_mapper.py`.")
    lines.append("> After checking the list of skills in the mapping table, the worker obtains instructions by directly reading COMPACT.md (if not present, SKILL.md) in each skill directory.")
    lines.append("> Based on `resolve_skill_file()`: If COMPACT.md exists, load it first, if not, load SKILL.md.")
    lines.append("")
    lines.append("## Skill mapping by task")
    lines.append("")
    lines.append("| task | Skill |")
    lines.append("|--------|------|")
    for task in tasks:
        lines.extend(_build_skill_map_rows(task))
    lines.append("")
    return lines


def _build_skill_map_rows(task):
    """Create a list of mapping table rows for each task."""
    lines = []
    resolved = task.get("resolved", [])
    fallback = set(task.get("fallback_skills", []))
    if resolved:
        skill_parts = [f"{s} (recommended)" if s in fallback else s for s in resolved]
        skill_str = ", ".join(skill_parts)
    else:
        skill_str = "(doesn't exist)"
    lines.append(f"| {task['taskId']} | {skill_str} |")
    return lines


def write_skill_map(work_dir, tasks):
    """Create skill-map.md.

    Contains only mapping tables. Skill instructions are read directly by the worker.
    """
    output_dir = os.path.join(work_dir, "work")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "skill-map.md")

    lines = _build_skill_map_header(tasks)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


# =============================================================================
# Update .dashboard/.skills.md
# =============================================================================

def _update_skills_md(registry_key: str, command: str, tasks: list, all_resolved: list, token_budget: int) -> None:
    """Insert the result of skill_mapper.py execution as a line in .dashboard/.skills.md.

    Non-blocking: All exceptions are swallowed and do not affect workflow execution.
    """
    try:
        KST = timezone(timedelta(hours=9))
        skills_md = os.path.join(PROJECT_ROOT, ".agent-factory", "board", "data", ".skills.md")
        lock_dir = os.path.join(PROJECT_ROOT, ".agent-factory", "board", "data", ".skills.md.lock")
        marker = "<!-- New entries will be added below this line -->"

        # Extract date from registryKey: YYYYMMDD-HHMMSS → MM-DD HH:MM
        try:
            date_part, time_part = registry_key.split("/")[0].split("-")
            date_str = f"{date_part[4:6]}-{date_part[6:8]} {time_part[0:2]}:{time_part[2:4]}"
        except Exception:
            date_str = datetime.now(KST).strftime("%m-%d %H:%M")

        # Job ID: registryKey all (including path)
        work_id = registry_key

        # skill-map.md link: relative path based on .agent-factory/board/data/
        # Fold structure: ../.agent-factory/runs/{timestamp}/work/skill-map.md
        try:
            rel_work_dir = resolve_abs_work_dir(registry_key, PROJECT_ROOT)
            rel_work_dir = os.path.relpath(rel_work_dir, PROJECT_ROOT)
            skill_map_link = f"[{work_id}](../{rel_work_dir}/work/skill-map.md)"
        except Exception:
            skill_map_link = work_id

        # Skill list (<br> tag newline separated, full display)
        skills_joined = "<br>".join(all_resolved) if all_resolved else "(doesn't exist)"

        # Fallback or not?
        has_fallback = any(task.get("fallback_skills") for task in tasks)
        fallback_str = "Y" if has_fallback else "N"

        # Token exceeded?
        over_budget = "Y" if token_budget > TOKEN_BUDGET_LIMIT else "N"

        # create row
        row = (
            f"| {date_str} | {skill_map_link} | {command} "
            f"| {len(tasks)} | {len(all_resolved)} | {skills_joined} "
            f"| {fallback_str} | {over_budget} |"
        )

        # Read skills.md
        from constants import SKILLS_HEADER_LINE, SKILLS_SEPARATOR_LINE

        content = ""
        if os.path.exists(skills_md):
            with open(skills_md, "r", encoding="utf-8") as f:
                content = f.read()

        if marker not in content:
            content = f"# Track skill mapping \n \n {marker} \n \n {SKILLS_HEADER_LINE} \n {SKILLS_SEPARATOR_LINE} \n"

        separator_line = SKILLS_SEPARATOR_LINE

        if separator_line in content:
            marker_pos = content.find(marker)
            if marker_pos >= 0:
                sep_pos = content.find(separator_line, marker_pos)
                if sep_pos >= 0:
                    insert_pos = sep_pos + len(separator_line)
                    if insert_pos < len(content) and content[insert_pos] == "\n":
                        insert_pos += 1
                    content = content[:insert_pos] + row + "\n" + content[insert_pos:]
                else:
                    content = content.replace(
                        marker, f"{marker}\n\n{SKILLS_HEADER_LINE}\n{separator_line}\n{row}"
                    )
            else:
                content = content.replace(
                    marker, f"{marker}\n\n{SKILLS_HEADER_LINE}\n{separator_line}\n{row}"
                )
        else:
            content = content.replace(
                marker, f"{marker}\n\n{SKILLS_HEADER_LINE}\n{separator_line}\n{row}"
            )

        # Atomic Write
        os.makedirs(os.path.dirname(skills_md), exist_ok=True)
        locked = acquire_lock(lock_dir)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(skills_md), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            shutil.move(tmp, skills_md)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        finally:
            if locked:
                release_lock(lock_dir)

    except Exception:
        pass


def _get_known_skills() -> set[str]:
    """Returns a set of skill names registered in skill-catalog.md.

    Parse the Skill Descriptions section in CATALOG_FILE to extract a list of registered skill names.
    If the file does not exist or parsing fails, an empty set is returned and verification is skipped.

    Returns:
        A set of registered skill names. Empty set if parsing fails.
    """
    known: set[str] = set()

    if not os.path.isfile(CATALOG_FILE):
        return known

    try:
        with open(CATALOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return known

    lines = content.split("\n")
    in_skills = False
    for line in lines:
        if "## Skill Descriptions" in line:
            in_skills = True
            continue
        if in_skills and line.startswith("## "):
            break
        if in_skills and line.startswith("|") and not line.startswith("| Skill name") and not line.startswith("|---"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2 and parts[1]:
                known.add(parts[1].strip())

    return known


def _suggest_similar_skills(unknown_skill: str, known_skills: set[str]) -> list[str]:
    """Up to 3 registration skills similar to unknown_skill are suggested.

    prefix matching method: with the first '-' separator prefix of unknown_skill (e.g. 'workflow-')
    Filters known_skills and returns up to 3.
    If there are no prefix matching results, an empty list is returned.

    Args:
        unknown_skill: Unregistered skill name (e.g. ‘workflow-unknwon’)
        known_skills: Set of registered skill names

    Returns:
        List of similar skill names (maximum 3). If not, an empty list.
    """
    if not unknown_skill or not known_skills:
        return []

    parts = unknown_skill.split("-", 1)
    if len(parts) < 2:
        return []

    prefix = parts[0] + "-"
    candidates = sorted(s for s in known_skills if s.startswith(prefix))
    return candidates[:3]


def validate_skill_mapping(tasks: list[dict]) -> tuple[bool, str]:
    """Verify the effectiveness of task skill mapping.

    For each task, verify the following:
    (a) Check whether one or more resolved skills are assigned
    (b) Check whether the assigned skill is a skill registered in skill-catalog.md

    If skill-catalog.md parsing fails, (b) verification is skipped.
    Perform only (a).

    Args:
        tasks: List of tasks returned by parse_plan_tasks().
               Each task must contain 'taskId' and 'resolved' keys.

    Returns:
        (True, "") - Pass all validations
        (False, "Failure Reason Details") - Includes failed task ID and reason when verification fails.
    """
    known_skills = _get_known_skills()
    failures: list[str] = []

    for task in tasks:
        task_id = task.get("taskId", "(unknown)")
        resolved = task.get("resolved", [])

        # (a) Confirmation of skill non-assignment
        if not resolved:
            failures.append(
                f"- {task_id}: [Reason for Failure] Skill not assigned (no resolved skill) \n"
                f"[How to fix] Enter the skill registered in skill-catalog.md in the {task_id} skill column of plan.md \n"
                f"[To be modified] Modify only the task list table skill column in plan.md (no changes to other sections)"
            )
            continue

        # (b) Check non-existent skill name (only when catalog parsing is successful)
        if known_skills:
            unknown = [s for s in resolved if s not in known_skills]
            if unknown:
                suggestions = []
                for u in unknown:
                    suggestions.extend(_suggest_similar_skills(u, known_skills))
                # Deduplication and up to 3
                seen_sugg: list[str] = []
                for s in suggestions:
                    if s not in seen_sugg:
                        seen_sugg.append(s)
                seen_sugg = seen_sugg[:3]

                sugg_str = (
                    f"Similar skill suggestions: {seen_sugg}" if seen_sugg else "No similar skills"
                )
                failures.append(
                    f"- {task_id}: [Reason for failure] Non-existent skill name {unknown} (skill-catalog.md not registered) \n"
                    f"[How to edit] Modify only the skill column in plan.md. Do not change other sections \n"
                    f"    [{sugg_str}]\n"
                    f"[To be modified] Modify only the task list table skill column in plan.md (no changes to other sections)"
                )

    if failures:
        reason = "Skill mapping verification failed: \n" + "\n".join(failures)
        return False, reason

    return True, ""


def slice_plan_context(plan_path, tasks, output_dir):
    """Extract only the task section of each worker from plan.md and save it as work/context/WXX-context.md.

    "### WXX:" Separates H3 subsections by task so that workers can
    Slicing so that only the context (1-2K tokens) is read.
    Instead of loading the entire plan.md (5-10K), you only need to provide task-specific context.
    Reduce worker context budget.

    Args:
        plan_path: absolute path to plan.md
        tasks: List of tasks returned by parse_plan_tasks() (requires taskId field)
        output_dir: Based on work/context/ directory (work_dir/work/context/)

    Returns:
        List of generated context file paths (only successfully created files)
    """
    if not os.path.isfile(plan_path):
        print(f"[WARN] slice_plan_context: Cannot find plan.md: {plan_path}", file=sys.stderr)
        return []

    with open(plan_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")

    # Set of task IDs (W01, W02, etc.)
    task_ids = {task["taskId"] for task in tasks if task.get("taskId")}

    # Navigate to the location of the H3 section for the pattern "### WXX:" in plan.md
    # Start section: "### W01:" or "### W01 " format
    section_starts = {}  # taskId -> line_index
    h3_pattern = re.compile(r"^###\s+(W\d+)[:\s]")

    for i, line in enumerate(lines):
        m = h3_pattern.match(line)
        if m:
            tid = m.group(1)
            if tid in task_ids:
                section_starts[tid] = i

    if not section_starts:
        # Skip if there is no H3 section
        return []

    # Determine where each task section ends: next H3/H2/H1 or end of file
    sorted_starts = sorted(section_starts.items(), key=lambda x: x[1])
    end_pattern = re.compile(r"^#{1,3}\s+")

    os.makedirs(output_dir, exist_ok=True)
    created = []

    for idx, (task_id, start_line) in enumerate(sorted_starts):
        # End-of-section navigation: next H1/H2/H3 line or end of file
        end_line = len(lines)
        for j in range(start_line + 1, len(lines)):
            if end_pattern.match(lines[j]):
                end_line = j
                break

        section_lines = lines[start_line:end_line]

        # Remove trailing blank lines
        while section_lines and not section_lines[-1].strip():
            section_lines.pop()

        if not section_lines:
            continue

        section_content = "\n".join(section_lines) + "\n"

        # File name: WXX-context.md
        out_path = os.path.join(output_dir, f"{task_id}-context.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(section_content)

        created.append(out_path)

    return created


def main():
    parser = argparse.ArgumentParser(
        prog="flow-skillmap",
        description="Create skill-map.md with the task skills column of plan.md.",
        epilog=build_common_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "registry_key",
        type=registry_key_type,
        metavar="registryKey",
        help="Workflow identifier in YYYYMMDD-HHMMSS format",
    )
    args = parser.parse_args()

    registry_key = args.registry_key

    # registryKey → workDir, plan.md, command automatic interpretation
    work_dir = resolve_abs_work_dir(registry_key, PROJECT_ROOT)
    plan_path = os.path.join(work_dir, "plan.md")
    ctx = load_json_file(os.path.join(work_dir, ".context.json"))
    command = ctx.get("command", "") if isinstance(ctx, dict) else ""

    _append_log(work_dir, "INFO", f"skill_mapper: start registryKey={registry_key}")

    if not command:
        print(f"[ERROR] Command not found in .context.json: {work_dir}", file=sys.stderr)
        sys.exit(1)

    # 1. Catalog parsing
    defaults = parse_catalog()

    # 2. Parsing the plan.md task
    tasks, p4_triggered = parse_plan_tasks(plan_path)
    if p4_triggered:
        _append_log(work_dir, "WARN", "planner_id_normalized: T# → W## format normalized")
    if not tasks:
        print(f"[WARN] Task not found in plan.md: {plan_path}", file=sys.stderr)
        # Create even an empty skill-map.md
        os.makedirs(os.path.join(work_dir, "work"), exist_ok=True)
        with open(os.path.join(work_dir, "work", "skill-map.md"), "w", encoding="utf-8") as f:
            f.write("# Skill Map \n \n > No task \n")
        sys.exit(0)

    # 3. Determine skills for each task
    for task in tasks:
        task["resolved"] = resolve_skills(task, command, defaults)

    # 3.5. Token budget verification (just before write_skill_map)
    all_resolved = []
    for task in tasks:
        for skill in task.get("resolved", []):
            if skill not in all_resolved:
                all_resolved.append(skill)
    token_budget = estimate_token_budget(all_resolved)

    # 4. Create skill-map.md
    output_path = write_skill_map(work_dir, tasks)

    # 5. Context slicing by task (plan.md → work/context/WXX-context.md)
    context_dir = os.path.join(work_dir, "work", "context")
    created_contexts = slice_plan_context(plan_path, tasks, context_dir)

    # 5.5. Skill mapping dashboard update (non-blocking)
    _update_skills_md(registry_key, command, tasks, all_resolved, token_budget)

    # 5.55. Token budget exceeded WARN record
    if token_budget > TOKEN_BUDGET_LIMIT:
        _append_log(
            work_dir,
            "WARN",
            f"TOKEN_BUDGET_EXCEEDED: total={token_budget} limit={TOKEN_BUDGET_LIMIT}",
        )

    # 5.6. Skill mapping validation (exit code 2 = validation failed)
    valid, reason = validate_skill_mapping(tasks)
    if not valid:
        _append_log(work_dir, "WARN", f"skill_mapper: validate_skill_mapping failed - {reason.splitlines()[0]}")
        print(reason, file=sys.stderr)
        sys.exit(2)

    _append_log(work_dir, "INFO", f"skill_mapper: complete tasks={len(tasks)} skills={len(all_resolved)}")

    # Banner output
    rel_path = os.path.relpath(output_path, PROJECT_ROOT)
    print("[STATE] Skill Mapping", flush=True)
    print(f">> {rel_path}", flush=True)
    if created_contexts:
        rel_ctx = os.path.relpath(context_dir, PROJECT_ROOT)
        print(f">> {rel_ctx}/ ({len(created_contexts)} context slices)", flush=True)


if __name__ == "__main__":
    main()
