#!/usr/bin/env -S python3 -u
"""plan validator.py - Plans (plan.md) and kanban ticket structure validation script.

Enter plan.md and validate: NEWS
(1) Warker water extraction by Phase in Mermaid Subgraph, warning at least 3 times the maximum/min rate
(2) Work list Warker's job item number parsing in table, warning when deviation exceeds 2
(3) T2(10+) TSK Skill 1 Personal warning
News 4) What/HOW Deletion Verification: Property/goal/context Reverting Detection (advisory, non-blocking)

--mode ticket will be valid for the kanban ticket XML structure NEWS
(TC-01) Directory Location vs XML status
(TC-02) count-from Derivative Ticket Unfinished + Original done Warning
(TC-03) Missing required tags (number/command/prompt)
(TC-04) command value validity
(TC-05) goal/target empty value warning
(TC-06) Revenue warning for revenge entry field
(TC-07) Whether the relevant link is present

Usage:
  flow-validate <plan_path|registryKey>
  flow-validate --mode ticket
  flow-validate --mode ticket --ticket T-001
  flow-validate --help

Output:
  "Verification passed"
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from typing import Any

# Determine project route
_engine_dir: str = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import resolve_project_root, resolve_work_dir
from flow.cli_utils import build_common_epilog
from flow.flow_logger import append_log, resolve_work_dir_for_logging

PROJECT_ROOT: str = resolve_project_root()


def parse_mermaid_phases(content: str) -> dict[str, int]:
    """Extract the number of Warkers per Phase in the Mermaid SubGraph.

    Multi Mermaid code blocks all congratulate results.
    The stack subgraph is handled as a stack, and the nodes of the W[Number]+ pattern are recognized as a Walker.

    Args:
        content: plan.md full content string

    Returns:
        {phase name: worker count}
    """
    phases = {}

    # Extract multiple Mermaid code blocks
    mermaid_blocks = re.findall(r"```mermaid\s*\n(.*?)```", content, re.DOTALL)
    if not mermaid_blocks:
        return phases

    for mermaid_content in mermaid_blocks:
        lines = mermaid_content.split("\n")

        current_phase = None
        worker_count = 0
        # Stack for nested subgraph support: stores (phase_name, worker_count) pairs
        phase_stack = []

        for line in lines:
            stripped = line.strip()

            # Start subgraph: standard format
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
                # Save current subgraph to stack (nesting supported)
                phase_stack.append((current_phase, worker_count))

                new_phase = subgraph_match.group(1)
                # Use if there is a subgraph label
                if subgraph_match.lastindex and subgraph_match.lastindex >= 2:
                    label = subgraph_match.group(2).strip()
                    if label:
                        new_phase = label
                current_phase = new_phase
                worker_count = 0
                continue

            # end keyword
            if stripped == "end":
                if current_phase is not None:
                    phases[current_phase] = phases.get(current_phase, 0) + worker_count
                # Restore external subgraph from stack (None if empty)
                if phase_stack:
                    current_phase, worker_count = phase_stack.pop()
                else:
                    current_phase = None
                    worker_count = 0
                continue

            # Worker node identification (W01[label], W01 [label] pattern)
            if current_phase is not None and re.match(r"^\s*W\d+[\[\s\(]", stripped):
                worker_count += 1

        # Save the last subgraph (if block ends without end)
        if current_phase is not None:
            phases[current_phase] = phases.get(current_phase, 0) + worker_count

    return phases


def _split_table_row(line: str) -> list[str]:
    """Decide the markdown table rows into the cell list.

    Remove the amount end blank cells and maintain the internal blank cells.

    Args:
        line: Markdown table line string (| with separator)

    Returns:
        List of cell values (each cell is striped string).
    """
    raw_parts = [p.strip() for p in line.split("|")]
    return raw_parts[1:-1] if len(raw_parts) >= 2 else raw_parts


def _find_table_start(lines: list[str], section_pattern: str | None, column_keywords: dict[str, list[str]]) -> int:
    """The table section determines the starting position.

    If section pattern, navigate the corresponding section header first,
    If not, navigate the table line directly with the first column keyword.

    Args:
        lines: Markdown file row list
        section pattern: section header regular pattern. If none is full navigation.
        column keywords: {field name: [keyword, ...]} column detection keyword map

    Returns:
        Table section Start row index. -1.
    """
    if section_pattern:
        for i, line in enumerate(lines):
            if re.search(section_pattern, line):
                return i

    # Direct table navigation without section header (determined by first column keyword)
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
    """Decide header lines and column index maps.

    Explore header lines within up to 15 lines at table start locations
    maps column indexes that correspond to each field of column keywords.

    Args:
        lines: Markdown file row list
        table start: table navigation start row index
        column keywords: {field name: [keyword, ...]} column detection keyword map

    Returns:
        (header idx, col map) tuple. Without header (-1, {}).
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
    Map the header column index in the Markdown table and parse data rows.

    Args:
        content: Markdown file full content string
        section pattern: regular pattern to find table section header (None-side full navigation)
        column keywords: {field name: [keyword, ...]} column detection keyword map

    Returns:
        list[dict]: Each line is {field name: cell value} dictionary.
                    The unacceptable field is not included.
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
    """The task list will parse the task information in the table.

    Args:
        content: plan.md full content string

    Returns:
        Task Dixiety list. Each item contains the following keys:
            id (str): task ID (W01 format)
            description (str): description of work
            complexity (str): complexity text string
            complexity score (int): Complex number score (if 0)
            Skill List
            Phase (str): Phase identifier
    """
    tasks = []

    column_keywords = {
        "id": ["id"],
        "description": ["work", "explanation", "description"],
        "complexity": ["complexity", "complexity"],
        "skills": ["skill", "skill"],
        "phase": ["phase"],
    }

    section_pattern = r"^##\s+Tasks\s*(list|list|table)"
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
        if raw_skills and raw_skills != "-" and raw_skills != "doesn't exist":
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
    """You can count the number of tasks in the task details section of the Walker.

    "### WXX:" returns the number of number list items within the H3 section.

    Args:
        content: plan.md full content string
        task id: Task ID counting (e.g. "W01")

    Returns:
        The number list of the corresponding tasks section.
    """
    lines = content.split("\n")
    in_section = False
    item_count = 0

    for line in lines:
        # Start that task section with an H3 header
        if re.match(rf"^###\s+{re.escape(task_id)}\b", line):
            in_section = True
            continue

        # End section with the following H2/H3 headers
        if in_section and re.match(r"^#{2,3}\s+", line):
            break

        if in_section:
            # Number list item count (1., 2., 3., ...)
            if re.match(r"^\d+\.\s+", line.strip()):
                item_count += 1

    return item_count


def validate_phase_balance(phases: dict[str, int]) -> list[str]:
    """Verify the number of Warkers per Phase.

    When the maximum/min walker count ratio is more than 3 times, it generates a warning.

    Args:
        phases: {phase name: worker count}

    Returns:
        Send your inquiry directly to us blank list when balanced.
    """
    warnings = []

    if len(phases) < 2:
        return warnings

    # Excluding phases with 0 workers
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
            f"[Phase Balance] Worker count imbalance between phases (ratio {max_count/min_count:.1f}x):"
            f"{max_phase}={max_count} people vs {min_phase}={min_count} people"
            f"(Standard: recommended less than 3 times maximum/minimum)"
        )

    return warnings


def validate_work_item_deviation(tasks: list[dict[str, Any]], content: str) -> list[str]:
    """Verify the number of work entries per phase.

    The maximum number of work entries in the same Phase - generates a warning when the minimum difference exceeds 2.

    Args:
        tasks: parse task table()
        content: plan.md full content string

    Returns:
        Send your inquiry directly to us blank list if deviation is allowed.
    """
    warnings = []

    # Task grouping by phase
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

        # Count the number of work items for each task
        item_counts = {}
        for task in group:
            count = count_task_work_items(content, task["id"])
            item_counts[task["id"]] = count

        # Deviation calculation
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
                f"[Work Deviation] Work item deviation {deviation} between workers within Phase {phase}"
                f"(Standard: within 2): {max_task}={max_count} pieces vs {min_task}={min_count} pieces"
            )

    return warnings


def validate_skill_coverage(tasks: list[dict[str, Any]]) -> list[str]:
    """In T2(10+) tasks, we generate alerts if one skill is assigned.

    If you have more than 10 skills in the task,
    Returns the potential warning of domain coverage.

    Args:
        tasks: parse task table()

    Returns:
        Send your inquiry directly to us If all T2 tasks have enough skills, empty list.
    """
    warnings = []

    for task in tasks:
        if task["complexity_score"] >= 10 and len(task["skills"]) == 1:
            warnings.append(
                f"[Lack of skill] {task['id']} is complexity {task['complexity']} or"
                f"Only one skill ({task['skills'][0]}) is assigned."
                f"Please check whether it contains 2 or more domains."
            )

    return warnings


def _extract_xml_tag(content: str, tag: str) -> str:
    """Extract XML tags.

    Args:
        content: search target string
        tag: tag name (e.g. "criteria", "goal", "context")

    Returns:
        Tag content string. Empty string without tag.
    """
    match = re.search(rf"<{tag}>(.*?)</{tag}>", content, re.DOTALL)
    return match.group(1) if match else ""


def _extract_section(content: str, section_names: list[str]) -> str:
    """Extracts section content that corresponds to the specified section name in plan.md.

    ## Searches the section starting with the header and returns the contents up to the next ## header.

    Args:
        content: plan.md full content string
        section names: List of sections to navigate (Return the first matching section)

    Returns:
        Section content string. blank string without section.
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
    """Returns a row with spaces normalized."""
    return re.sub(r"\s+", " ", line).strip()


def _count_consecutive_matches(source_lines: list[str], target_text: str) -> int:
    """returns the maximum number of consecutive matches included in target text.

    Use the substring match, including strings after regularization.
    The empty row is excluded from the comparison.

    Args:
        source lines: List of comparison criteria (XML tag content, etc.)
        target text: subject text (plan.md section content)

    Returns:
        Maximum serial number.
    """
    target_normalized = _normalize_line(target_text)
    max_streak = 0
    current_streak = 0

    for line in source_lines:
        norm = _normalize_line(line)
        if not norm:
            # Blank rows don't break continuation count (allow optional continuation)
            continue
        if norm in target_normalized:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0

    return max_streak


def validate_what_how_separation(plan_path: str, user_prompt_path: str) -> list[str]:
    """What/HOW Deletion Verification: Property/goal/context Revert Detection.

    XML tag content of user prompt.txt was reverted to the corresponding section of plan.md
    Detects string comparison. All warnings are the advisory level.

    Tag:
      - standard re-subscription: <criteria> warning when consecutive matches over 3 lines
      - Responsibilities: <goal> warning when the main phrase is included (more than 10 characters)
      - context original copy: <context> warning when consecutive matches over two lines

    Args:
        plan path: plan.md file path
        user prompt path: user prompt.txt file path

    Returns:
        advisory warning message list. If not, empty list.
    """
    warnings = []

    if not os.path.isfile(user_prompt_path):
        return warnings

    with open(user_prompt_path, "r", encoding="utf-8") as f:
        prompt_content = f.read()

    with open(plan_path, "r", encoding="utf-8") as f:
        plan_content = f.read()

    # Rule 1: criteria redescription detection
    criteria_text = _extract_xml_tag(prompt_content, "criteria")
    if criteria_text:
        criteria_section = _extract_section(plan_content, ["Technology verification criteria"])
        if criteria_section:
            criteria_lines = [l for l in criteria_text.split("\n") if _normalize_line(l)]
            match_count = _count_consecutive_matches(criteria_lines, criteria_section)
            if match_count >= 3:
                warnings.append(
                    f"[WHAT/HOW advisory] criteria Suspicious redescription:"
                    f"Detection of <criteria> {match_count} lines similar to the original text in the technical verification criteria section"
                )

    # Rule 2: Detect goal redescription
    goal_text = _extract_xml_tag(prompt_content, "goal")
    if goal_text:
        summary_section = _extract_section(plan_content, ["task summary"])
        if summary_section:
            summary_normalized = _normalize_line(summary_section)
            # goal Extract consecutive phrases of 10 or more characters from the original text and check whether they are included
            goal_normalized = _normalize_line(goal_text)
            found_phrase = False
            # Detect phrases longer than 10 characters with a sliding window
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
                    "[WHAT/HOW advisory] Suspect goal re-statement:"
                    "Detect inclusion of <goal> text passage in task summary"
                )

    # Rule 3: Detect copy of context original block
    context_text = _extract_xml_tag(prompt_content, "context")
    if context_text:
        note_section = _extract_section(plan_content, ["note", "Status snapshot"])
        if note_section:
            context_lines = [l for l in context_text.split("\n") if _normalize_line(l)]
            match_count = _count_consecutive_matches(context_lines, note_section)
            if match_count >= 2:
                warnings.append(
                    f"[WHAT/HOW advisory] context suspected of copying original text:"
                    f"Detection of copying {match_count} lines of <context> original text block in remarks section"
                )

    return warnings


def validate(plan_path: str) -> list[str]:
    """validate the plan.md and return the warning list.

    advisory is a validation function of non-blocking nature.
    The return value does not block the workflow flow of the orchestra,
    Warning messages are only used for log output.

    Args:
        plan path: plan.md file path

    Returns:
        list[str]: List of warning messages (passes empty list-side verification).
                   You do not block the flow of the caller regardless of the return value.
    """
    if not os.path.isfile(plan_path):
        return [f"[ERROR] File not found: {plan_path}"]

    with open(plan_path, "r", encoding="utf-8") as f:
        content = f.read()

    warnings = []

    # 1. Extracting the number of workers by phase from the Mermaid subgraph
    phases = parse_mermaid_phases(content)
    if phases:
        warnings.extend(validate_phase_balance(phases))

    # 2. Parse the task list table
    tasks = parse_task_table(content)

    # 3. Verification of deviation in the number of work items for each worker
    if tasks:
        warnings.extend(validate_work_item_deviation(tasks, content))

    # 4. Verification of T2(10+) task skill count
    if tasks:
        warnings.extend(validate_skill_coverage(tasks))

    # 5. WHAT/HOW separate verification (advisory, non-blocking)
    plan_dir = os.path.dirname(plan_path)
    user_prompt_path = os.path.join(plan_dir, "user_prompt.txt")
    warnings.extend(validate_what_how_separation(plan_path, user_prompt_path))

    if warnings:
        _work_dir = resolve_work_dir_for_logging()
        if _work_dir:
            append_log(_work_dir, "WARN", f"plan_validator: {len(warnings)} warnings found")

    return warnings


# ---------------------------------------------------------------------------
# ticket mode helper function
# ---------------------------------------------------------------------------

# Directory name → XML status value mapping (for normalization)
_DIR_TO_STATUS: dict[str, str] = {
    "todo": "To Do",
    "open": "Open",
    "progress": "In Progress",
    "review": "Review",
    "done": "Done",
}

# Valid command value (chain delimiter > verification of each token when included)
_VALID_COMMANDS: set[str] = {"implement", "review", "research"}

# Multiple Item Field List (for TC-06)
_MULTI_FIELDS: list[str] = ["goal", "target", "constraints", "criteria", "context"]


def find_kanban_root(project_root: str) -> str:
    """returns the Kanban root directory path.

    Args:
        project root: Project route absolute path

    Returns:
        . agent-factory/kanban absolute path
    """
    return os.path.join(project_root, ".agent-factory", "tickets")


def load_ticket_xml(xml_path: str) -> dict[str, Any]:
    """return the ticket XML file to dict.

    return empty dict when parsing fails.

    Args:
        xml path: ticket XML file absolute path

    Returns:
        {number, title, status, command, goal, target, constraints,
         . . . . . . .
        An empty dict when parsing failed.
    """
    if not os.path.isfile(xml_path):
        return {}

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError:
        return {}

    def _text(tag: str) -> str:
        """Returns the text inside the tag. If not, an empty string."""
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
    """Turn 4 directories of the Kanban route to return ticket number → directory location map.

    Args:
        kanban root: Kanban route absolute path (.agent-factory/kanban)

    Returns:
        {T-NNN: "open"|"progress"|"review"|"done"} Dinner.
    """
    location_map: dict[str, str] = {}
    for dir_name in ("todo", "open", "progress", "review", "done"):
        dir_path = os.path.join(kanban_root, dir_name)
        if not os.path.isdir(dir_path):
            continue
        for fname in os.listdir(dir_path):
            if not fname.endswith(".xml"):
                continue
            ticket_number = fname[:-4]  # Remove extension
            location_map[ticket_number] = dir_name
    return location_map


def extract_relations(ticket_data: dict[str, Any]) -> list[dict[str, str]]:
    """returns a statement in the ticket data.

    Args:
        Ticket data: load ticket xml

    Returns:
        [{type, ticket}, ...] list.
    """
    return ticket_data.get("relations", [])


def validate_ticket_status_consistency(
    kanban_root: str, location_map: dict[str, str]
) -> list[str]:
    """TC-01: Directory location vs XML <status> validation.

    If the directory location and XML <status> value is invalid, it creates a warning.

    Args:
        kanban root: Kanban Route Absolute Route
        location map: build ticket location map() return value

    Returns:
        Send your inquiry directly to us
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
                f"[TC-01] {ticket_number}: directory ({dir_name}) vs XML status ({xml_status}) mismatch"
                f"(Expected value: {expected_status})"
            )
    return warnings


def validate_derived_ticket_completion(
    kanban_root: str, location_map: dict[str, str]
) -> list[str]:
    """TC-02: count-from derivative ticket unfinished + original done alert.

    If the original ticket is done not done, it will generate a warning.

    Args:
        kanban root: Kanban Route Absolute Route
        location map: build ticket location map() return value

    Returns:
        Send your inquiry directly to us
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
                    f"[TC-02] {ticket_number} (derived ticket) is incomplete ({dir_name})"
                    f"Original {origin_ticket} is done"
                )
    return warnings


def validate_ticket_xml_fields(
    ticket_data: dict[str, Any], ticket_number: str, dir_name: str
) -> list[str]:
    """TC-03/04/05/06: Single ticket XML field validation.

    TC-03: number/command/prompt required tag presence on open/progress/review ticket
    TC-04: command value implementation review research (included >)
    TC-05: Open/progress/review Go to the ticket WARN
    TC-06: WARN when missing \\n in plural field (based on the return rate of the line)

    Args:
        Ticket data: load ticket xml
        ticket number: ticket number (e.g. T-001)
        dir name: directory location (open/progress/review/done)

    Returns:
        Send your inquiry directly to us
    """
    warnings: list[str] = []
    # Todo is in a backlog state and there is no obligation to complete prompt required fields — only open/progress/review is subject to active verification
    is_active = dir_name in ("open", "progress", "review")

    if not is_active:
        return warnings

    # TC-03: Presence of required tags
    if not ticket_data.get("number"):
        warnings.append(f"[TC-03] {ticket_number}: <number> tag missing or empty value")
    if not ticket_data.get("command"):
        warnings.append(f"[TC-03] {ticket_number}: <command> tag missing or empty value")
    # Existence of prompt: If either goal or target is present, the prompt block is considered to exist.
    has_prompt = bool(ticket_data.get("goal") or ticket_data.get("target"))
    if not has_prompt:
        warnings.append(f"[TC-03] {ticket_number}: No content in <prompt> block")

    # TC-04: Command value validity
    raw_command = ticket_data.get("command", "")
    if raw_command:
        # Separate with chain separator > and verify each token
        tokens = [t.strip() for t in raw_command.split(">") if t.strip()]
        invalid_tokens = [t for t in tokens if t not in _VALID_COMMANDS]
        if invalid_tokens:
            warnings.append(
                f"[TC-04] {ticket_number}: Invalid command value {invalid_tokens}"
                f"(Allow: {sorted(_VALID_COMMANDS)})"
            )

    # TC-05: goal/target empty value
    if not ticket_data.get("goal", "").strip():
        warnings.append(f"[TC-05] {ticket_number}: <goal> empty")
    if not ticket_data.get("target", "").strip():
        warnings.append(f"[TC-05] {ticket_number}: <target> empty")

    # TC-06: Missing newlines in multiple entry fields
    for field in _MULTI_FIELDS:
        value = ticket_data.get(field, "")
        if not value:
            continue
        lines = [ln for ln in value.split("\n") if ln.strip()]
        # If there are more than 2 lines and there is no newline character ( \n ), a warning is issued.
        # When parsing XML, the actual newline already exists as \n,
        # Judging by the actual number of lines vs. the number of newlines in the original text
        line_count = len(lines)
        # If there are more than 2 lines and the actual number of lines is 1, they are written on one line without a newline.
        # (Judged by stripped results after XML parsing)
        raw_value = ticket_data.get(field, "")
        actual_newlines = raw_value.count("\n")
        if line_count >= 2 and actual_newlines == 0:
            warnings.append(
                f"[TC-06] {ticket_number}: Missing \n newlines in multiple <{field}> items ({line_count} items)"
            )

    return warnings


def validate_all_tickets_xml_fields(
    kanban_root: str, location_map: dict[str, str]
) -> list[str]:
    """TC-03~06: Full ticket XML field batch verification.

    Args:
        kanban root: Kanban Route Absolute Route
        location map: build ticket location map() return value

    Returns:
        Send your inquiry directly to us
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
    """TC-07: Validation of whether the relevant link is present.

    If the ticket referenced in the field does not exist in the field, it will generate a warning.

    Args:
        kanban root: Kanban Route Absolute Route
        location map: valid ticket map (single or full)
        full location map: Full ticket map for check whether the link exists.
            If none, use the location map to the full map.

    Returns:
        Send your inquiry directly to us
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
                    f"[TC-07] {ticket_number}: Relationship link target {target_ticket}({rel.get('type', '')}) is"
                    f"Doesn't exist in Kanban"
                )
    return warnings


def validate_tickets(
    kanban_root: str, single_ticket: str | None = None
) -> list[str]:
    """Validate the entire Kanban ticket or a single ticket and return the warning list.

    TC-01~TC-07 7 types of verification rules are executed.

    Args:
        kanban root: Kanban Route Absolute Route
        single ticket: Ticket number (e.g. T-001) when validating a single ticket. If none, the full validation.

    Returns:
        Send your inquiry directly to us
    """
    if not os.path.isdir(kanban_root):
        return [f"[ERROR] Kanban root directory not found: {kanban_root}"]

    full_location_map = build_ticket_location_map(kanban_root)
    if not full_location_map:
        return ["[WARN] Ticket not found in Kanban."]

    # Single ticket mode: TC-01~06 is a single ticket map, TC-07 is a full map to verify link
    if single_ticket:
        if single_ticket not in full_location_map:
            return [f"[ERROR] Ticket {single_ticket} not found in Kanban."]
        target_map = {single_ticket: full_location_map[single_ticket]}
    else:
        target_map = full_location_map

    warnings: list[str] = []

    # TC-01: Directory vs XML status mismatch
    warnings.extend(validate_ticket_status_consistency(kanban_root, target_map))

    # TC-02: derived-from derived incomplete + original done
    warnings.extend(validate_derived_ticket_completion(kanban_root, target_map))

    # TC-03~06: XML field validation
    warnings.extend(validate_all_tickets_xml_fields(kanban_root, target_map))

    # TC-07: Relationship link lost (TC-07 checks for existence based on the entire location_map)
    warnings.extend(validate_relation_links(kanban_root, target_map, full_location_map))

    return warnings


def _print_validate_result(warnings: list[str], mode_label: str) -> None:
    """Output verification results in standard output format.

    Args:
        alerts: alert message list
        mode label: mode label (e.g. "PLAN", "TICKET")
    """
    if not warnings:
        print(
            f"[STATE] VALIDATE-{mode_label} validation passed",
            flush=True,
        )
        print(
            ">> 0 warnings",
            flush=True,
        )
        return

    print(
        f"[STATE] VALIDATE-{mode_label} [WARN]",
        flush=True,
    )
    print(
        f">> Warning {len(warnings)} found",
        flush=True,
    )
    print()
    for i, warning in enumerate(warnings, 1):
        print(f"  {i}. {warning}")


def _build_parser() -> argparse.ArgumentParser:
    """plan_validator Creates and returns ArgumentParser for CLI."""
    parser = argparse.ArgumentParser(
        prog="flow-validate",
        description=(
            "plan.md structure verification — Check phase balance, work deviation, skill deficiency, and WHAT/HOW separation. \n"
            "In --mode ticket, Kanban ticket XML structure verification (TC-01~07) is performed."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Input format: \n"
            "1. registryKey (YYYYMMDD-HHMMSS pattern): \n"
            "       flow-validate 20260303-124206\n"
            "2. workDir path: \n"
            "flow-validate .workflow/20260303-124206/task name/implement \n"
            "3. plan.md direct path: \n"
            "       flow-validate .workflow/20260303-124206/.../implement/plan.md\n"
            "4. ticket mode (all): \n"
            "       flow-validate --mode ticket\n"
            "5. ticket mode (single): \n"
            "       flow-validate --mode ticket --ticket T-001\n"
            "\n"
            "Verification items (plan mode): \n"
            "1. Phase balance: Extracting the number of workers per phase from the Mermaid subgraph, \n"
            "Warning when the maximum/minimum ratio is more than 3 times \n"
            "2. Work deviation: Warning when the deviation in the number of work items between workers in the same phase exceeds 2. \n"
            "3. Skill shortage: Warning when only 1 skill is assigned in T2 (10+) task \n"
            "4. WHAT/HOW: criteria/goal/context redescription detection (advisory) \n"
            "\n"
            "Verification items (ticket mode): \n"
            "TC-01: Directory location vs XML status mismatch \n"
            "TC-02: derived-from derived incomplete + original done warning \n"
            "TC-03: Required tag missing (number/command/prompt) \n"
            "TC-04: Command value validity (implement|review|research) \n"
            "TC-05: goal/target empty value warning \n"
            "TC-06: Multi-entry field missing newline warning \n"
            "TC-07: Relationship link target ticket exists \n"
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
            "plan.md path, workDir path, or registryKey to verify"
            "(YYYYMMDD-HHMMSS format). Can be omitted when using --mode ticket."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["plan", "ticket"],
        default="plan",
        help="Select verification mode: plan (default) or ticket",
    )
    parser.add_argument(
        "--ticket",
        metavar="TICKET_NUMBER",
        default=None,
        help="Single ticket verification (used when --mode ticket, e.g. T-001)",
    )
    return parser


def main() -> None:
    """CLI entry point. After parsing the arguments, the verification results are output."""
    parser = _build_parser()
    args = parser.parse_args()

    mode: str = args.mode
    _work_dir = resolve_work_dir_for_logging()

    # --- ticket mode ---
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

    # --- plan mode (default) ---
    plan_path: str | None = args.plan_path
    if plan_path is None:
        parser.error("In plan mode, the plan_path argument is required.")
        return  # unreachable, mypy response

    # Step 3 Path Analysis Branching
    if not plan_path.endswith(".md"):
        # If not ending in .md: interpreted as registryKey or workDir
        resolved_dir: str = resolve_work_dir(plan_path, PROJECT_ROOT)
        plan_path = os.path.join(resolved_dir, "plan.md")

    # Convert relative path to absolute path
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
