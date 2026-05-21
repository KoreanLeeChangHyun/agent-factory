"""work_request_repository.py - Conveyor WorkRequest XML CRUD and file navigation module.

Creating, reading, and XML WorkRequest files
(.agent-factory/work-requests/{draft,accepted,executing,verifying,complete}/WR-NNN.xml).
This is a data layer module responsible for update and delete. Separated from conveyor.py,
Only pure IO operations are performed.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, NoReturn

# ─── Path constant ──────────────────────────────────────────────────────────────────

_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR: str = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from common import resolve_project_root

_PROJECT_ROOT: str = resolve_project_root()
CONVEYOR_DIR: str = os.path.join(_PROJECT_ROOT, ".agent-factory", "work-requests")

# ─── Directory constants by state ────────────────────────────────────────────────────────
CONVEYOR_DRAFT_DIR: str = os.path.join(CONVEYOR_DIR, "draft")
CONVEYOR_ACCEPTED_DIR: str = os.path.join(CONVEYOR_DIR, "accepted")
CONVEYOR_EXECUTING_DIR: str = os.path.join(CONVEYOR_DIR, "executing")
CONVEYOR_VERIFYING_DIR: str = os.path.join(CONVEYOR_DIR, "verifying")
CONVEYOR_COMPLETE_DIR: str = os.path.join(CONVEYOR_DIR, "complete")

CONVEYOR_ACTIVE_DIR: str = CONVEYOR_ACCEPTED_DIR

# XML <status> value -> directory path mapping
STATUS_DIR_MAP: dict[str, str] = {
    "Draft": CONVEYOR_DRAFT_DIR,
    "Accepted": CONVEYOR_ACCEPTED_DIR,
    "Executing": CONVEYOR_EXECUTING_DIR,
    "Verifying": CONVEYOR_VERIFYING_DIR,
    "Complete": CONVEYOR_COMPLETE_DIR,
}

# ─── Debug reserved area constant ────────────────────────────────────────────────────────
# Constant to exclude this range when automatically counting. Explicit --number calls have no effect (force blocking X).
DEBUG_RESERVED_RANGE_START: int = 900
DEBUG_RESERVED_RANGE_END: int = 999


# ─── Logging Helper ───────────────────────────────────────────────────────────────────

def resolve_work_dir_for_logging() -> str | None:
    """The abs_work_dir of the current workflow is interpreted from the environment variable or .context.json.

    If interpretation is not possible, None is returned to prevent logging failure from affecting script execution.
    """
    try:
        # Delegate if flow_logger exists
        _flow_dir = os.path.dirname(os.path.abspath(__file__))
        if _flow_dir not in sys.path:
            sys.path.insert(0, _flow_dir)
        from flow_logger import resolve_work_dir_for_logging
        return resolve_work_dir_for_logging()
    except Exception:
        pass
    try:
        # Direct reference to the environment variable WORKFLOW_WORK_DIR
        work_dir = os.environ.get("WORKFLOW_WORK_DIR", "")
        if work_dir and os.path.isdir(work_dir):
            return work_dir
        # Browse the most recent active workflows in the .workflow/ directory
        workflow_base = os.path.join(_PROJECT_ROOT, ".agent-factory", "runs")
        if not os.path.isdir(workflow_base):
            return None
        import glob as _glob
        context_files = _glob.glob(os.path.join(workflow_base, "*", "*", "*", ".context.json"))
        if not context_files:
            return None
        context_files.sort(key=os.path.getmtime, reverse=True)
        for cf in context_files:
            candidate = os.path.dirname(cf)
            if os.path.isdir(candidate):
                return candidate
    except Exception:
        pass
    return None


def log(level: str, message: str) -> None:
    """Records events in workflow.log. If abs_work_dir parsing fails, it is quietly skipped."""
    try:
        # Delegate if flow_logger exists
        _flow_dir = os.path.dirname(os.path.abspath(__file__))
        if _flow_dir not in sys.path:
            sys.path.insert(0, _flow_dir)
        from flow_logger import append_log, resolve_work_dir_for_logging
        abs_work_dir = resolve_work_dir_for_logging()
        if abs_work_dir:
            append_log(abs_work_dir, level, message)
        return
    except Exception:
        pass
    try:
        abs_work_dir = resolve_work_dir_for_logging()
        if not abs_work_dir:
            return
        from datetime import timezone, timedelta
        kst = timezone(timedelta(hours=9))
        ts = datetime.now(kst).strftime("%Y-%m-%dT%H:%M:%S")
        log_path = os.path.join(abs_work_dir, "workflow.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {message}\n")
    except Exception:
        pass


# ─── Error Helper ───────────────────────────────────────────────────────────────────

def err(msg: str, code: int = 1) -> NoReturn:
    """Prints an error message to stderr and exits.

    Args:
        msg: error message
        code: exit code (default 1)
    """
    log("ERROR", f"conveyor.py: ERROR {msg}")
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(code)


# ─── XML Helper ───────────────────────────────────────────────────────────────────


def create_work_request_xml(work_request_number: str, title: str = "", datetime_str: str = "", command: str = "") -> str:
    """Creates and returns a work_request XML string.

    XML is a flat structure consisting of five top-level elements:
      - <metadata>: WorkRequest number, title, date, status, command (required)
      - <relations>: list of relationship links (optional — omitted if not relevant)
      - <prompt>: Action prompt (goal/target/constraints/criteria/context) (required)
      - <result>: Workflow execution result (registrykey/workdir/plan/report/merge_commit) (Optional — self-closing if not executed)
      - <failure>: FAIL status metadata (reason/phase/retry_count/context) (optional — does not exist upon normal completion)

    When creating a new work_request, the <failure> element is not created (failure does not exist == normal state,
    See WR-452 §9.2 Option A). The <failure> element is newly inserted when update_failure() is called.

    Args:
        work_request_number: WorkRequest number (WR-NNN format).
        title: WorkRequest title. Allows empty strings.
        datetime_str: Creation date string (YYYY-MM-DD HH:MM:SS format). If the string is empty, use the current time.
        command: Execution command (implement, research, etc.). Allows empty strings.

    Returns:
        WorkRequest XML string containing UTF-8 XML declaration.
    """
    root = ET.Element("work_request")
    # <metadata> wrapper element
    metadata_elem = ET.SubElement(root, "metadata")
    ET.SubElement(metadata_elem, "number").text = work_request_number
    title_sub = ET.SubElement(metadata_elem, "title")
    if title:
        title_sub.text = title
    now_str = datetime_str or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ET.SubElement(metadata_elem, "created").text = now_str
    ET.SubElement(metadata_elem, "updated").text = now_str
    ET.SubElement(metadata_elem, "status").text = "Accepted"
    if command:
        ET.SubElement(metadata_elem, "command").text = command
    # <prompt /> self-closing element
    ET.SubElement(root, "prompt")
    # <result /> self-closing element
    ET.SubElement(root, "result")
    ET.indent(root, space="  ")
    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=False)
    # Insert section comments: Add comments just before <metadata>, <prompt>, and <result> tags.
    # Handles both self-closing tags (<prompt />, <result />) and regular tags (<prompt>, <result>)
    xml_str = re.sub(r"(<metadata[ />])", r"<!-- metadata -->\n  \1", xml_str)
    xml_str = re.sub(r"(<prompt[ />])", r"\n  <!-- prompt -->\n  \1", xml_str)
    xml_str = re.sub(r"(<result[ />])", r"\n  <!-- result -->\n  \1", xml_str)
    return xml_str


def write_work_request_xml(filepath: str, root: ET.Element, allow_create: bool = False) -> None:
    """Save the XML Element to a file.

    Maintain the <metadata>, <prompt>, <result> flat structure,
    Wraps the field text inside the prompt for readability.

    Args:
        filepath: File path to save.
        root: XML root element to save.
        allow_create: If True, new creation is allowed even if the file does not exist.
            If False (default), FileNotFoundError is raised when the file does not exist.
            Prevents creation of empty files due to race conditions.

    Raises:
        FileNotFoundError: when allow_create=False and filepath does not exist.
    """
    # Reject write if file does not exist (prevent creation of empty file)
    if not allow_create and not os.path.isfile(filepath):
        raise FileNotFoundError(
            f"No file to write to (may have been moved by another session): {filepath}"
        )
    # updated Timestamp auto-renewal
    metadata_elem = root.find("metadata")
    if metadata_elem is not None:
        updated_elem = metadata_elem.find("updated")
        if updated_elem is not None:
            updated_elem.text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            # Legacy Compatibility: Create updated if not present
            ET.SubElement(metadata_elem, "updated").text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ET.indent(root, space="  ")
    xml_str = ET.tostring(root, encoding="unicode")
    # Ensure readability by wrapping the field text inside the prompt with newline + indentation (only 10 characters or more)
    _PROMPT_FIELD_INLINE_LIMIT = 10

    def _wrap_prompt_field(m: re.Match[str]) -> str:
        indent = m.group(1)
        tag = m.group(2)
        content = m.group(3).strip()
        # \n Converts a literal (2 characters) to an actual newline character.
        content = content.replace("\\n", "\n")
        # List pattern automatic newline: Insert a newline before numeric) patterns and dash (-) patterns (except at the beginning of a string)
        content = re.sub(r"(?<!^)(?<!\n)(?<!\()(\s)(\d{1,2}\))", r"\n\2", content)
        content = re.sub(r"(?<!^)(?<!\n)(\s*)(- )", r"\n\2", content)
        if len(content) < _PROMPT_FIELD_INLINE_LIMIT:
            return f"{indent}<{tag}>{content}</{tag}>"
        inner_indent = indent + "  "
        # Strip existing white space in each line, remove blank lines, and re-indent (prevent ET.indent overlap)
        lines = content.split("\n")
        lines = [line.strip() for line in lines if line.strip()]
        indented_content = f"\n{inner_indent}".join(lines)
        return f"{indent}<{tag}>\n{inner_indent}{indented_content}\n{indent}</{tag}>"

    xml_str = re.sub(
        r"( *)<(goal|target|constraints|criteria|context)>(.+)</\2>",
        _wrap_prompt_field,
        xml_str,
        flags=re.DOTALL,
    )
    # Insert section comments: Add comments immediately before <metadata>, <relations>, <prompt>, <result> tags (only if not present)
    # Handles both self-closing tags (<prompt />, <result />) and regular tags (<prompt>, <result>)
    if "<!-- metadata -->" not in xml_str:
        xml_str = re.sub(r"(<metadata[ />])", r"<!-- metadata -->\n  \1", xml_str)
    if "<!-- relations -->" not in xml_str and "<relations" in xml_str:
        xml_str = re.sub(r"(<relations[ />])", r"\n  <!-- relations -->\n  \1", xml_str)
    if "<!-- prompt -->" not in xml_str:
        xml_str = re.sub(r"(<prompt[ />])", r"\n  <!-- prompt -->\n  \1", xml_str)
    if "<!-- result -->" not in xml_str:
        xml_str = re.sub(r"(<result[ />])", r"\n  <!-- result -->\n  \1", xml_str)
    if "<!-- failure -->" not in xml_str and "<failure" in xml_str:
        xml_str = re.sub(r"(<failure[ />])", r"\n  <!-- failure -->\n  \1", xml_str)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(xml_str)
        f.write("\n")


def parse_work_request_xml(filepath: str) -> dict[str, Any]:
    """Parse the work_request XML file and return it as a dictionary.

    Parses based on flat structures (<metadata>, <prompt>, <result>).
    Legacy work_requests (<submit>/<subnumber> or <history>/<subnumber> structures) in the complete directory are processed with fallback logic.

    Args:
        filepath: WorkRequest file path to parse.

    Returns:
        Dictionary of parsed work_request information:
            - number (str): work_request number
            - status (str): current status
            - title (str): work_request title
            - command (str): Execution command
            - prompt (dict): goal, target, constraints, criteria, context
            - result (dict | None): registrykey, workdir, plan, report (None if not executed)
            - relations (list[dict]): list of relationships

    Raises:
        SystemExit: When file reading fails or XML parsing error occurs.
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"Failed to parse work_request file ({filepath}): {e}")

    def _text(elem: ET.Element, tag: str, default: str = "") -> str:
        """A helper that returns the text of a child Element."""
        child = elem.find(tag)
        return child.text.strip() if child is not None and child.text else default

    # Parse number/title/datetime/status/command in <metadata> wrapper
    metadata_elem = root.find("metadata")

    if metadata_elem is not None:
        number = _text(metadata_elem, "number")
        status = _text(metadata_elem, "status")
        title = _text(metadata_elem, "title")
        command = _text(metadata_elem, "command")
    else:
        number = _text(root, "number")
        status = _text(root, "status")
        title = _text(root, "title")
        command = _text(root, "command")

    # complete Directory legacy fallback: If a <submit>/<subnumber> or <history>/<subnumber> structure is detected, parse it with existing logic.
    submit_elem = root.find("submit")
    history_elem = root.find("history")
    has_legacy_structure = (
        (submit_elem is not None and submit_elem.find("subnumber") is not None) or
        (history_elem is not None and history_elem.find("subnumber") is not None)
    )
    if has_legacy_structure:
        return _parse_legacy_work_request(filepath, root, number, status, title, _text)

    # Flat structure: <prompt> Parse 5 elements directly under the root
    prompt_fields = ("goal", "target", "constraints", "criteria", "context")
    prompt_data: dict[str, str] = {}
    prompt_elem = root.find("prompt")
    if prompt_elem is not None:
        for field in prompt_fields:
            prompt_data[field] = _text(prompt_elem, field)
    else:
        for field in prompt_fields:
            prompt_data[field] = ""

    # Flat structure: <result> parses subelements directly below the root
    result_fields = ("registrykey", "workdir", "plan", "report", "merge_commit")
    result_data: dict[str, str] | None = None
    result_elem = root.find("result")
    if result_elem is not None and len(result_elem) > 0:
        result_data = {}
        for field in result_fields:
            result_data[field] = _text(result_elem, field)

    # Flat structure: <failure> Parse sub-elements directly below the root (optional — exists only in FAIL state)
    failure_fields = ("reason", "phase", "retry_count", "context")
    failure_data: dict[str, str] | None = None
    failure_elem = root.find("failure")
    if failure_elem is not None and len(failure_elem) > 0:
        failure_data = {}
        for field in failure_fields:
            failure_data[field] = _text(failure_elem, field)

    # Parsing <relations> elements (backwards compatible: empty list if none)
    relations = _parse_relations(root)

    return {
        "number": number,
        "status": status,
        "title": title,
        "command": command,
        "prompt": prompt_data,
        "result": result_data,
        "failure": failure_data,
        "relations": relations,
    }


def _parse_relations(root: ET.Element) -> list[dict[str, str]]:
    """Parses the <relations> element and returns a list of relationships."""
    relations: list[dict[str, str]] = []
    relations_elem = root.find("relations")
    if relations_elem is not None:
        for rel in relations_elem.findall("relation"):
            rel_type = rel.get("type", "")
            rel_work_request = rel.get("work_request", "")
            if rel_type and rel_work_request:
                relations.append({"type": rel_type, "work_request": rel_work_request})
    return relations


def _parse_legacy_work_request(
    filepath: str,
    root: ET.Element,
    number: str,
    status: str,
    title: str,
    _text: Any,
) -> dict[str, Any]:
    """Parses the legacy <submit>/<subnumber> structure and returns it in a new flat format.

    Used for backward compatibility with existing work_requests in the complete directory.
    """
    submit_elem = root.find("submit")
    history_elem = root.find("history")

    # Command and prompt are extracted from the most recent (largest ID) subnumber
    all_subs: list[ET.Element] = []
    if submit_elem is not None:
        all_subs.extend(submit_elem.findall("subnumber"))
    if history_elem is not None:
        all_subs.extend(history_elem.findall("subnumber"))
    if not all_subs:
        all_subs.extend(root.findall("subnumber"))

    # Sort by ID in descending order, giving priority to the most recent subnumber.
    all_subs.sort(key=lambda s: int(s.get("id", "0")) if s.get("id", "0").isdigit() else 0, reverse=True)

    command = ""
    prompt_data: dict[str, str] = {"goal": "", "target": "", "constraints": "", "criteria": "", "context": ""}
    result_data: dict[str, str] | None = None

    if all_subs:
        latest = all_subs[0]
        # command: subnumber
        cmd_elem = latest.find("command")
        if cmd_elem is not None and cmd_elem.text:
            command = cmd_elem.text.strip()

        # prompt: subnumber inside <prompt> wrapper
        prompt_elem = latest.find("prompt")
        if prompt_elem is not None:
            for field in ("goal", "target", "constraints", "criteria", "context"):
                child = prompt_elem.find(field)
                if child is not None and child.text:
                    prompt_data[field] = child.text.strip()

        # result: subnumber inside <result> wrapper
        result_elem = latest.find("result")
        if result_elem is not None and len(result_elem) > 0:
            result_data = {}
            for result_child in result_elem:
                text = result_child.text.strip() if result_child.text else ""
                result_data[result_child.tag] = text

    # Parsing <relations> elements
    relations = _parse_relations(root)

    return {
        "number": number,
        "status": status,
        "title": title,
        "command": command,
        "prompt": prompt_data,
        "result": result_data,
        "failure": None,
        "relations": relations,
    }


# ─── prompt/result update ─────────────────────────────────────────────────────────


def update_prompt(filepath: str, updates: dict[str, str]) -> None:
    """Update the <prompt> sub-element and <metadata>/<command> of the work_request XML.

    Automatically converts self-closing <prompt /> tags into <prompt> tags with content.

    Args:
        filepath: WorkRequest file path.
        updates: Dictionary of fields to update.
            - command: <metadata>/<command> update
            - Goal, target, constraints, criteria, context: <prompt> sub-element update
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"Failed to parse work_request file ({filepath}): {e}")

    # Update <metadata>/<command>
    if "command" in updates:
        metadata_elem = root.find("metadata")
        if metadata_elem is not None:
            cmd_elem = metadata_elem.find("command")
            if cmd_elem is not None:
                cmd_elem.text = updates["command"]
            else:
                ET.SubElement(metadata_elem, "command").text = updates["command"]

    # Update <prompt> child elements
    prompt_fields = ("goal", "target", "constraints", "criteria", "context")
    prompt_updates = {k: v for k, v in updates.items() if k in prompt_fields}

    if prompt_updates:
        prompt_elem = root.find("prompt")
        if prompt_elem is None:
            # Create a <prompt> element if it does not exist (insert it after metadata)
            prompt_elem = ET.Element("prompt")
            insert_idx = 0
            for i, child in enumerate(root):
                if child.tag in ("metadata", "relations"):
                    insert_idx = i + 1
            root.insert(insert_idx, prompt_elem)

        for field, value in prompt_updates.items():
            # \n Convert literals to actual newlines
            text = str(value).strip().replace("\\n", "\n")
            existing = prompt_elem.find(field)
            if existing is not None:
                existing.text = text
            else:
                ET.SubElement(prompt_elem, field).text = text

    write_work_request_xml(filepath, root)


def update_result(filepath: str, updates: dict[str, str]) -> None:
    """Updates the <result> sub-element of work_request XML.

    Automatically converts the self-closing <result /> tag into a <result> tag with content.

    Args:
        filepath: WorkRequest file path.
        updates: Dictionary of fields to update.
            - registrykey, workdir, plan, report, merge_commit: update <result> sub-elements
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"Failed to parse work_request file ({filepath}): {e}")

    result_fields = ("registrykey", "workdir", "plan", "report", "merge_commit")
    result_updates = {k: v for k, v in updates.items() if k in result_fields}

    if result_updates:
        result_elem = root.find("result")
        if result_elem is None:
            # Create a <result> element if it does not exist (add it to the end of the root)
            result_elem = ET.SubElement(root, "result")

        for field, value in result_updates.items():
            existing = result_elem.find(field)
            if existing is not None:
                existing.text = str(value)
            else:
                ET.SubElement(result_elem, field).text = str(value)

    write_work_request_xml(filepath, root)


def update_failure(filepath: str, updates: dict[str, str]) -> None:
    """Update the <failure> sub-element of work_request XML.

    Optional element — Called only in FAIL status.
    If <failure> does not exist, a new one is created at the end of the root (automatically placed after <result>).

    Args:
        filepath: WorkRequest file path.
        updates: Dictionary of fields to update.
            - reason: Failure reason identifier (verifier_failure / validator_failure / sentinel / retry_max, etc.)
            - phase: Workflow phase where failure occurs (INIT / PLAN / WORK / VALIDATE / REPORT)
            - retry_count: Cumulative number of retries (integer → string serialization)
            - context: Free-form description (multiline allowed)
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"Failed to parse work_request file ({filepath}): {e}")

    failure_fields = ("reason", "phase", "retry_count", "context")
    failure_updates = {k: v for k, v in updates.items() if k in failure_fields}

    if failure_updates:
        failure_elem = root.find("failure")
        if failure_elem is None:
            # Create a <failure> element if it does not exist (add it to the end of the root — after <result>)
            failure_elem = ET.SubElement(root, "failure")

        for field, value in failure_updates.items():
            existing = failure_elem.find(field)
            if existing is not None:
                existing.text = str(value)
            else:
                ET.SubElement(failure_elem, field).text = str(value)

    write_work_request_xml(filepath, root)

# ─── relations ───────────────────────────────────────────────────────────


def add_relation(filepath: str, relation_type: str, target_work_request: str) -> None:
    """Add a relationship element to the work_request XML.

    If the <relations> element does not exist, a new one is created after <metadata> and before <prompt>.
    If the same type+work_request combination already exists, it is not added again.

    Args:
        filepath: WorkRequest file path.
        relation_type: Relationship type (depends-on, derived-from, blocks).
        target_work_request: Target work_request number (WR-NNN format).
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"Failed to parse work_request file ({filepath}): {e}")

    relations_elem = root.find("relations")

    # duplicate check
    if relations_elem is not None:
        for rel in relations_elem.findall("relation"):
            if rel.get("type") == relation_type and rel.get("work_request") == target_work_request:
                return  # Skip if already exists

    # Create <relations> element if it does not exist
    if relations_elem is None:
        relations_elem = ET.Element("relations")
        # Insert after <metadata> and before <prompt>
        insert_idx = 0
        for i, child in enumerate(root):
            if child.tag == "metadata":
                insert_idx = i + 1
                break
        root.insert(insert_idx, relations_elem)

    # Add <relation type="..." work_request="..."/>
    rel_elem = ET.SubElement(relations_elem, "relation")
    rel_elem.set("type", relation_type)
    rel_elem.set("work_request", target_work_request)

    write_work_request_xml(filepath, root)


def remove_relation(filepath: str, relation_type: str, target_work_request: str) -> None:
    """Remove the relationship element from the work_request XML.

    Remove the relation element of the type+work_request combination,
    If <relations> is empty, the element itself is also removed.

    Args:
        filepath: WorkRequest file path.
        relation_type: Relationship type (depends-on, derived-from, blocks).
        target_work_request: Target work_request number (WR-NNN format).
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"Failed to parse work_request file ({filepath}): {e}")

    relations_elem = root.find("relations")
    if relations_elem is None:
        return  # Ignored if there is no relations element

    # Remove matching relation
    for rel in relations_elem.findall("relation"):
        if rel.get("type") == relation_type and rel.get("work_request") == target_work_request:
            relations_elem.remove(rel)

    # If <relations> is empty, remove the element itself
    if len(relations_elem) == 0:
        root.remove(relations_elem)

    write_work_request_xml(filepath, root)


# ─── Utilities ──────────────────────────────────────────────────────────────────


def find_work_request_file(work_request_number: str) -> str | None:
    """WR-NNN.xml Searches for and returns the work_request file path through exact matching.

    Navigation order: draft/ -> accepted/ -> executing/ -> verifying/ -> complete/ -> active/ (fallback) -> conveyor/ (root fallback)

    Args:
        work_request_number: WorkRequest number (WR-NNN format).

    Returns:
        Absolute path string to the file found. None if not found.
    """
    filename = f"{work_request_number}.xml"
    # Directory traversal by state
    for status_dir in [CONVEYOR_DRAFT_DIR, CONVEYOR_ACCEPTED_DIR, CONVEYOR_EXECUTING_DIR, CONVEYOR_VERIFYING_DIR, CONVEYOR_COMPLETE_DIR]:
        candidate = os.path.join(status_dir, filename)
        if os.path.isfile(candidate):
            return candidate
    # Fallback: active/ or conveyor/ root if migration is incomplete
    active_path = os.path.join(CONVEYOR_DIR, "active", filename)
    if os.path.isfile(active_path):
        return active_path
    root_path = os.path.join(CONVEYOR_DIR, filename)
    if os.path.isfile(root_path):
        return root_path
    return None


def normalize_work_request_number(raw: str) -> str | None:
    """Normalize the work_request number string to 'WR-NNN' format.

    WR-NNN, NNN, #All N formats are supported.

    Args:
        raw: original WorkRequest number string (e.g. '#1', 'WR-001', '001', '1')

    Returns:
        Normalized 'WR-NNN' format string. None if conversion is not possible.
    """
    raw = raw.strip().lstrip("#")
    # Already in WR-NNN format
    if re.match(r"^WR-\d+$", raw, re.IGNORECASE):
        parts = raw.split("-")
        num = int(parts[1])
        return f"WR-{num:03d}"
    # pure numbers
    if re.match(r"^\d+$", raw):
        return f"WR-{int(raw):03d}"
    return None


def extract_report_summary(report_path: str) -> str:
    """Extracts key sections from report.md and returns a summary string.

    Extract the "## Final decision" or "## Judgment" section and the "## Issue" or "## Findings" section.
    If the above section does not exist, the first 50 lines of report.md are used as a fallback.
    To save tokens, limit to a maximum of 2000 characters.

    Args:
        report_path: Absolute path to report.md file.

    Returns:
        Extracted summary string. Empty string if file read failure.
    """
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return ""

    if not content.strip():
        return ""

    lines = content.split("\n")

    # Section extraction helper: From the beginning of the ## header to just before the next ## header.
    def _extract_section(header_patterns: list[str]) -> str:
        for pattern in header_patterns:
            for i, line in enumerate(lines):
                if line.strip().lower().startswith(f"## {pattern.lower()}"):
                    section_lines = [lines[i]]
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip().startswith("## "):
                            break
                        section_lines.append(lines[j])
                    return "\n".join(section_lines).strip()
        return ""

    verdict = _extract_section(["final decision", "verdict"])
    issues = _extract_section(["issue", "Findings"])

    summary_parts = [p for p in [verdict, issues] if p]

    if summary_parts:
        summary = "\n\n".join(summary_parts)
    else:
        # fallback: first 50 lines
        summary = "\n".join(lines[:50]).strip()

    # 2000 character limit
    if len(summary) > 2000:
        summary = summary[:2000] + "..."

    return summary


def get_predecessor_reports(work_request_number: str) -> list[dict[str, str]]:
    """Extracts and returns the report summary of the preceding work_request.

    Find depends-on and derived-from relationships in work_request XML,
    If each preceding work_request has a status of Complete and a report file exists, a summary is extracted.

    Args:
        work_request_number: Current work_request number (WR-NNN format).

    Returns:
        List of advance work_request report information. Each item is
        {"work_request": "WR-NNN", "type": "depends-on", "summary": "..."} form.
        Empty list if there are no advance work_requests or conditions are not met.
    """
    work_request_file = find_work_request_file(work_request_number)
    if not work_request_file:
        return []

    try:
        work_request_data = parse_work_request_xml(work_request_file)
    except SystemExit:
        return []

    relations = work_request_data.get("relations", [])
    predecessor_types = {"depends-on", "derived-from"}
    results: list[dict[str, str]] = []

    for rel in relations:
        rel_type = rel.get("type", "")
        rel_work_request = rel.get("work_request", "")
        if rel_type not in predecessor_types or not rel_work_request:
            continue

        # Find advance work_request file
        pred_file = find_work_request_file(rel_work_request)
        if not pred_file:
            continue

        try:
            pred_data = parse_work_request_xml(pred_file)
        except SystemExit:
            continue

        # Skip if not Complete
        if pred_data.get("status", "") != "Complete":
            continue

        # Extract report path directly from result dict
        report_path_str = ""
        result = pred_data.get("result")
        if isinstance(result, dict) and result.get("report"):
            report_path_str = result["report"]

        if not report_path_str:
            continue

        # Convert relative path to absolute path
        abs_report_path = os.path.join(_PROJECT_ROOT, report_path_str)
        if not os.path.isfile(abs_report_path):
            continue

        summary = extract_report_summary(abs_report_path)
        if summary:
            results.append({
                "work_request": rel_work_request,
                "type": rel_type,
                "summary": summary,
            })

    return results


def get_max_work_request_number(exclude_debug_range: bool = False) -> int:
    """Scan .conveyor/{draft,accepted,executing,verifying,complete}/ XML filenames to find max WR-NNN number.

    Root fallback: The .conveyor/ root is also scanned to prevent number conflicts when migration is not completed.

    Args:
        exclude_debug_range: When True, past debug reserved areas are excluded from scanning.
            2026-05-05 Automatic number call according to debug area abolition (see workflow.md "Number Area Policy")
            Used as True only in the `--number` unspecified branch of `conveyor_cli.py`. Existing active remaining
Exclude from the max calculation when automatically picking to prevent this from being encroached upon.
            It is for this purpose. There is no effect on explicit `--number` calls, and conflict checking is performed in a separate path.

    Returns:
        Current maximum work_request number integer. 0 if there is no work_request.
    """
    max_num = 0
    for d in [CONVEYOR_DRAFT_DIR, CONVEYOR_ACCEPTED_DIR, CONVEYOR_EXECUTING_DIR, CONVEYOR_VERIFYING_DIR, CONVEYOR_COMPLETE_DIR, CONVEYOR_DIR]:
        if not os.path.isdir(d):
            continue
        for fname in os.listdir(d):
            m = re.match(r"^WR-(\d+)\.xml$", fname)
            if m:
                num = int(m.group(1))
                # Skip debug reserved area (900~999) — Abolished on 2026-05-05, preventing automatic number encroachment.
                if exclude_debug_range and DEBUG_RESERVED_RANGE_START <= num <= DEBUG_RESERVED_RANGE_END:
                    continue
                if num > max_num:
                    max_num = num
    return max_num


def move_work_request_to_status_dir(filepath: str, target_status: str) -> str:
    """Move the work_request file to the directory corresponding to the target state.

    STATUS_DIR_MAP is looked up for the target directory, and the current file already exists in that directory.
    If it is already in the target directory, the movement is skipped.

    Args:
        filepath: Absolute path to the work_request file to be moved.
        target_status: Target status string (Draft, Accepted, Executing, Verifying, Complete).

    Returns:
        New file path after moving. Returns original route if skipped.

    Raises:
        ValueError: If the status string is not in STATUS_DIR_MAP.
        OSError: When file movement fails.
    """
    target_dir = STATUS_DIR_MAP.get(target_status)
    if target_dir is None:
        raise ValueError(f"Unknown status: '{target_status}'. Allowed values: {', '.join(STATUS_DIR_MAP.keys())}")

    current_dir = os.path.dirname(filepath)
    if os.path.normpath(current_dir) == os.path.normpath(target_dir):
        # Same directory — no need to move.
        return filepath

    filename = os.path.basename(filepath)
    new_path = os.path.join(target_dir, filename)

    # If the original file does not exist, another session has already moved it.
    if not os.path.isfile(filepath):
        expected_path = os.path.join(target_dir, filename)
        if os.path.isfile(expected_path):
            return expected_path  # Already moved
        raise FileNotFoundError(f"No original file: {filepath}")

    # If the same file already exists in the destination path, only the original is deleted (idempotency)
    if os.path.isfile(new_path) and os.path.normpath(filepath) != os.path.normpath(new_path):
        os.remove(filepath)
        return new_path

    os.makedirs(target_dir, exist_ok=True)
    shutil.move(filepath, new_path)
    return new_path



# Column name mapping: CLI argument → column name
COLUMN_MAP: dict[str, str] = {
    "draft": "Draft",
    "accepted": "Accepted",
    "executing": "Executing",
    "verifying": "Verifying",
    "complete": "Complete",
}

# Allowed state transition rule: Current state → Allowed target list
# Only the complete subcommand (force=True) is allowed to move to Complete.
# It is not possible to move directly to Complete with the move command.
# Verifying → Complete requires the complete subcommand.
# Draft only allows a default transition to Accepted, and returning from other states requires --force.
ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "Draft": ["Accepted"],
    "Accepted": ["Executing", "Draft", "Verifying"],
    "Executing": ["Verifying", "Accepted"],
    "Verifying": ["Accepted", "Complete"],
    "Complete": ["Accepted"],
}
# Verifying → Executing transition is intentionally not allowed.
# Verifying phase possible actions: (a) Rework with Accepted (/wf -e or right-click menu);
# (b) attach to chat to create follow-up analysis/implementation WorkRequest, (c) complete with Complete (complete subcommand).


def validate_transition(current_status: str, target_section: str, force: bool = False) -> str | None:
    """Verify state transition rules.

    Check whether a transition from the current state to the target state is allowed.
    If the status is already the same, None is returned, and if the rule is violated, an error message is returned.
    If force=True, the rule is ignored.

    Args:
        current_status: Current WorkRequest status (e.g. 'Accepted', 'Executing').
        target_section: Target status (e.g. 'Verifying', 'Complete').
        force: Whether to force transition.

    Returns:
        Error message string. None if transitions are allowed.
        If it is already in the same state, an empty string ("") is returned.
    """
    # If the state is already the same, an empty string is returned (ignored case, not an error).
    if current_status == target_section:
        return ""

    # State transition rule verification
    allowed = ALLOWED_TRANSITIONS.get(current_status, [])
    if target_section not in allowed and not force:
        return (
            f"You cannot navigate to {target_section} because it is currently {current_status}."
            f"You can force movement with the --force flag."
        )

    return None


def update_work_request_status(filepath: str, new_status: str) -> None:
    """Update the <status> element of work_request XML.

    The <status> element inside the <metadata> wrapper is first searched.

    Args:
        filepath: WorkRequest file path.
        new_status: New status string (e.g. 'Accepted', 'Executing', 'Verifying', 'Complete').

    Raises:
        SystemExit: When file read/write fails.
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"Failed to parse work_request file ({filepath}): {e}")

    # First look for <status> inside the <metadata> wrapper
    metadata_elem = root.find("metadata")
    if metadata_elem is not None:
        status_elem = metadata_elem.find("status")
        if status_elem is not None:
            status_elem.text = new_status
        else:
            ET.SubElement(metadata_elem, "status").text = new_status
    else:
        status_elem = root.find("status")
        if status_elem is not None:
            status_elem.text = new_status
        else:
            ET.SubElement(root, "status").text = new_status

    write_work_request_xml(filepath, root)
