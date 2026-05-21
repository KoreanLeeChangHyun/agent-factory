#!/usr/bin/env -S python3 -u
"""prompt_validator.py - Ticket file XML contract specification validation script.

Take the ticket file as input and verify the following:
(1) Check the presence of 4 required tags (<goal>, <target>, <constraints>, <criteria>)
(2) Detect empty sections (no content or TODO: only patterns, less than 10 characters)
(3) Calculate quality score: (Number of required tags / 4) * 0.6 + (Number of valid content tags / 4) * 0.4
(4) Describe the presence of optional tags (<context>, <approach>, <scope>, <reference>)

Usage:
  python3 prompt_validator.py <prompt_file_path>
  python3 prompt_validator.py --help

output of power:
  JSON stdout: quality_score, has_tags, missing_tags, empty_tags,
               optional_tags, feedback

Exit code:
  0 Verification completed
  1 File read failed
  2 argument error
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

# Determine project route
_engine_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from constants import QUALITY_THRESHOLD

REQUIRED_TAGS = ["goal", "target", "constraints", "criteria"]
OPTIONAL_TAGS = ["context", "approach", "scope", "reference"]
_KST = timezone(timedelta(hours=9))

# TODO pattern: Starts with "TODO:" or is entirely TODO text
_TODO_PATTERN = re.compile(r"^\s*TODO\s*:", re.IGNORECASE)


def build_common_epilog() -> str:
    """Return the common CLI footer without importing flow runtime helpers."""
    return "Agent Factory CLI"


def append_log(abs_work_dir: str, level: str, message: str) -> None:
    """Append workflow log entries without coupling core validation to flow."""
    try:
        ts = datetime.now(_KST).strftime("%Y-%m-%dT%H:%M:%S")
        with open(os.path.join(abs_work_dir, "workflow.log"), "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {message}\n")
    except Exception:
        pass


def resolve_work_dir_for_logging() -> str | None:
    """Resolve workflow work dir from environment when available."""
    for key in ("WORKFLOW_WORK_DIR", "_WF_WORK_DIR"):
        work_dir = os.environ.get(key, "").strip()
        if work_dir and os.path.isdir(work_dir):
            return work_dir
    return None


def _extract_tag_content(text: str, tag: str) -> str | None:
    """Extract tag contents. Returns None if not present.

    Self-nested tags (e.g. <goal>...<goal>...</goal>...</goal>)
    Parses on a stack basis and returns the contents of the outermost tag pair.

    XML structure compatibility comments:
        This function searches the entire text for tags, so the depth inside the <prompt> wrapper and
        It operates regardless. Flat structure (<prompt> is directly below the root) and legacy structure
        (<submit>/<subnumber>/<prompt> nested) The regex pattern in all
        Since the search targets the entire text, it matches normally.

    Args:
        text: the entire text to search for
        tag: Tag name to extract (excluding angle brackets)

    Returns:
        Text inside tag. None if there is no tag.
    """
    tag_escaped = re.escape(tag)
    open_pat = re.compile(rf"<{tag_escaped}>", re.IGNORECASE)
    close_pat = re.compile(rf"</{tag_escaped}>", re.IGNORECASE)

    # Collect all open/closed tag positions
    events = []
    for m in open_pat.finditer(text):
        events.append((m.start(), "open", m.end()))
    for m in close_pat.finditer(text):
        events.append((m.start(), "close", m.end()))

    if not events:
        return None

    # Sort by position order
    events.sort(key=lambda e: e[0])

    # Explore the most external tag pairs based on the stack
    depth = 0
    outer_start = None
    for pos, kind, end_pos in events:
        if kind == "open":
            if depth == 0:
                outer_start = end_pos  # Tag content start position
            depth += 1
        else:  # close
            if depth > 0:
                depth -= 1
                if depth == 0 and outer_start is not None:
                    return text[outer_start:pos]

    return None


def extract_active_prompt(xml_text: str) -> str:
    """Extract the <prompt> content from the entire XML.

    The contents of the <prompt> tag directly under the root are directly extracted from the flat-structured ticket XML.

    Legacy fallback: When a <submit> wrapper is detected, it is parsed into the existing subnumber structure and
    active="true" Returns the contents of the <prompt> inside subnumber (see done ticket, etc.).

    Args:
        xml_text: Full ticket XML text

    Returns:
        <prompt> content. Returns the original xml_text when extraction fails.
    """
    # Legacy fallback: If a <submit> wrapper exists, parse it as the existing subnumber structure.
    submit_content = _extract_tag_content(xml_text, "submit")
    if submit_content is not None:
        return _extract_active_prompt_legacy(xml_text, submit_content)

    # Flat structure: directly extract the contents of the <prompt> tag directly under the root
    prompt_content = _extract_tag_content(xml_text, "prompt")
    if prompt_content is None:
        return xml_text

    return prompt_content


def _extract_active_prompt_legacy(xml_text: str, submit_content: str) -> str:
    """Extracts the active <prompt> content from the legacy subnumber structure.

    Inside the <submit> wrapper, you create a <subnumber> element with the active="true" attribute.
    Finds and returns the contents of the <prompt> tag inside the element.

    Args:
        xml_text: Full ticket XML text (for fallback return)
        submit_content: Text inside <submit> tag

    Returns:
        <prompt> content of the active subnumber. Returns the original xml_text when extraction fails.
    """
    active_open_pat = re.compile(
        r'<subnumber[^>]*\bactive\s*=\s*"true"[^>]*>', re.IGNORECASE
    )
    close_pat = re.compile(r'</subnumber>', re.IGNORECASE)

    match = active_open_pat.search(submit_content)
    if match is None:
        return xml_text

    open_any_pat = re.compile(r'<subnumber[^>]*>', re.IGNORECASE)

    events: list[tuple[int, str, int]] = []
    for m in open_any_pat.finditer(submit_content):
        events.append((m.start(), "open", m.end()))
    for m in close_pat.finditer(submit_content):
        events.append((m.start(), "close", m.end()))
    events.sort(key=lambda e: e[0])

    depth = 0
    outer_start: int | None = None
    outer_end: int | None = None
    active_start = match.start()
    found_active = False

    for pos, kind, end_pos in events:
        if kind == "open":
            if depth == 0 and pos == active_start:
                found_active = True
                outer_start = end_pos
            depth += 1
        else:  # close
            if depth > 0:
                depth -= 1
                if depth == 0 and found_active and outer_start is not None:
                    outer_end = pos
                    break

    if outer_start is None or outer_end is None:
        return xml_text

    subnumber_content = submit_content[outer_start:outer_end]

    prompt_content = _extract_tag_content(subnumber_content, "prompt")
    if prompt_content is None:
        return xml_text

    return prompt_content


def _is_valid_content(content: str) -> bool:
    """Determines whether the tag content is valid.

    Valid conditions: At least 10 characters after removing spaces, and does not consist of only the TODO: pattern.

    Args:
        content: tag content string to inspect

    Returns:
        True if the content is valid, False otherwise.
    """
    stripped = content.strip()
    if len(stripped) < 10:
        return False
    if _TODO_PATTERN.match(stripped):
        return False
    return True


def validate(prompt_text: str) -> dict[str, object]:
    """Verifies prompt_text and returns the resulting dict.

    Args:
        prompt_text: Prompt text to verify

    Returns:
        Verification result dictionary. Includes the following keys:
        - quality_score (float): 0.0~1.0 quality score
        - has_tags (bool): Whether one or more required tags exist
        - missing_tags (list[str]): List of required missing tags.
        - empty_tags (list[str]): List of required tags with empty content
        - optional_tags (list[str]): List of optional tags found.
        - feedback (list[str]): List of improvement feedback messages
    """
    present_tags: list[str] = []
    missing_tags: list[str] = []
    valid_tags: list[str] = []
    empty_tags: list[str] = []

    for tag in REQUIRED_TAGS:
        content = _extract_tag_content(prompt_text, tag)
        if content is None:
            missing_tags.append(tag)
        else:
            present_tags.append(tag)
            if _is_valid_content(content):
                valid_tags.append(tag)
            else:
                empty_tags.append(tag)

    present_count = len(present_tags)
    valid_count = len(valid_tags)
    quality_score = round((present_count / 4) * 0.6 + (valid_count / 4) * 0.4, 4)
    has_tags = present_count > 0

    # Check for existence of selection tag
    found_optional = [
        tag for tag in OPTIONAL_TAGS
        if _extract_tag_content(prompt_text, tag) is not None
    ]

    # Generate backward feedback
    feedback: list[str] = []
    for tag in missing_tags:
        feedback.append(
            f"No <{tag}> tag."
            f"Add the '{tag}' section to make it clearly recognizable to planners."
        )
    for tag in empty_tags:
        feedback.append(
            f"<{tag}> tag content is empty or contains only TODO text."
            f"Please be specific and at least 10 characters long."
        )

    return {
        "quality_score": quality_score,
        "has_tags": has_tags,
        "missing_tags": missing_tags,
        "empty_tags": empty_tags,
        "optional_tags": found_optional,
        "feedback": feedback,
    }


def _build_parser() -> argparse.ArgumentParser:
    """Creates and returns a CLI argument parser.

    Returns:
        Set ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="flow-validate-p",
        description="Validate Ticket File XML Contract Specification \n \n"
                    "Verification Item: \n"
                    "1. Required tags present: <goal>, <target>, <constraints>, <criteria> \n"
                    "2. Detect empty sections: no content / TODO: pattern / less than 10 characters \n"
                    "3. Quality score: (Existence tags/4)*0.6 + (Effective content/4)*0.4 \n"
                    "4. Optional tags: <context>, <approach>, <scope>, <reference> \n \n"
                    "Output (JSON): \n"
                    "  quality_score, has_tags, missing_tags, empty_tags,\n"
                    "  optional_tags, feedback\n\n"
                    "Exit code: \n"
                    "0 Verification completed \n"
                    "1 Failed to read file \n"
                    "2 argument error",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=build_common_epilog(),
    )
    parser.add_argument(
        "prompt_file_path",
        help="Path to the ticket file to validate (e.g. .agent-factory/tickets/active/T-NNN.xml)",
    )
    return parser


def main() -> None:
    """CLI entry point. Parses the arguments, executes validate(), and outputs JSON.

    Raises:
        SystemExit: Argument error (2), file read failure (1), normal completion (0).
    """
    parser = _build_parser()
    args = parser.parse_args()

    prompt_path = args.prompt_file_path

    # Convert relative path to absolute path based on call location
    if not os.path.isabs(prompt_path):
        prompt_path = os.path.join(os.getcwd(), prompt_path)

    _work_dir = resolve_work_dir_for_logging()
    if _work_dir:
        append_log(_work_dir, "INFO", f"prompt_validator: start path={prompt_path}")

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read()
    except OSError as e:
        sys.stderr.write(f"Error: Unable to read file — {e} \n")
        sys.exit(1)

    result = validate(prompt_text)

    if result["quality_score"] < QUALITY_THRESHOLD:
        if _work_dir:
            append_log(
                _work_dir,
                "WARN",
                f"prompt_validator: quality_score={result['quality_score']:.4f} below {QUALITY_THRESHOLD} path={prompt_path}",
            )

    print("[STATE] VALIDATE-P", flush=True)
    print(f">> quality_score={result['quality_score']:.4f}", flush=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
