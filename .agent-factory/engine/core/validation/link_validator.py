#!/usr/bin/env python3
"""Markdown/HTML file link validation script.

Extract the links from report.html and plan.md files in the .agent-factory/runs/ directory,
Verifies the existence of each internal link target file.

This script is not connected to an automatic hook; it is a manually run utility.
Used to check link validity after completing a workflow or creating a report.

Running example:
    python3 .agent-factory/engine/guards/link_validator.py
    python3 .agent-factory/engine/guards/link_validator.py --active-only

Main functions:
    main: Entry point, parses CLI arguments and performs verification
    scan_markdown_files: Returns a list of markdown files to scan
    extract_links: Extract links from markdown text
    validate_link: Validate a single link
    validate_all: Run link validation for the entire file list.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


# Markdown link pattern: [text](path)
_MD_LINK_PATTERN: re.Pattern[str] = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

# HTML href pattern: href="path" / href='path'
_HTML_HREF_PATTERN: re.Pattern[str] = re.compile(r"""href=["']([^"']+)["']""", re.IGNORECASE)

# External link prefix
_EXTERNAL_PREFIXES: tuple[str, ...] = ("http://", "https://")

# Placeholder pattern (template link detection)
_PLACEHOLDER_PATTERN: re.Pattern[str] = re.compile(r"\{\{[^}]+\}\}")

# Path prefix relative to project root
_PROJECT_ROOT_PREFIXES: tuple[str, ...] = (".agent-factory/", ".claude/")


def _find_project_root() -> Path:
    """Finds and returns the project root directory.

    Since this script is located under .agent-factory/engine/core/validation/,
    Level 4 The upper directory is the project root.

    Returns:
        Project root Path object.
    """
    return Path(__file__).resolve().parent.parent.parent.parent.parent


def scan_markdown_files(
    project_root: Path,
    active_only: bool = False,
) -> list[Path]:
    """Returns a list of Markdown files subject to verification.

    Collect report.html and plan.md files under the .agent-factory/runs/ directory.
    If active_only=True, .agent-factory/runs/.history/ is excluded.

    Args:
        project_root: Project root directory path.
        active_only: If True, only scan active workflows (direct children of .agent-factory/runs/).

    Returns:
        List of Markdown file paths to scan.
    """
    workflow_dir = project_root / ".agent-factory" / "runs"
    if not workflow_dir.exists():
        return []

    target_filenames: set[str] = {"report.html", "plan.md"}
    result: list[Path] = []

    # Scan for active workflows (.workflow/ direct children, excluding .history/)
    for entry in workflow_dir.iterdir():
        if entry.name == ".history":
            continue
        if entry.is_dir():
            for link_file in entry.rglob("*"):
                if link_file.is_file() and link_file.name in target_filenames:
                    result.append(link_file)

    # History scan (when active_only=False)
    if not active_only:
        history_dir = workflow_dir / ".history"
        if history_dir.exists():
            for link_file in history_dir.rglob("*"):
                if link_file.is_file() and link_file.name in target_filenames:
                    result.append(link_file)

    return sorted(result)


def extract_links(content: str) -> list[str]:
    """Extracts a list of link paths (hrefs) from Markdown/HTML text.

    Args:
        content: Markdown file text content.

    Returns:
        List of extracted link href strings.
    """
    md_matches = [href for _text, href in _MD_LINK_PATTERN.findall(content)]
    html_matches = _HTML_HREF_PATTERN.findall(content)
    return md_matches + html_matches


def _is_skip_link(href: str) -> bool:
    """Determine whether the link should be excluded from verification.

    External links (http/https) and template placeholder links are skipped.

    Args:
        href: Link path string.

    Returns:
        True if it is a skip target, False if it is a verification target.
    """
    # Skip anchor inside document
    if href.startswith("#"):
        return True

    # Skip external link
    for prefix in _EXTERNAL_PREFIXES:
        if href.startswith(prefix):
            return True

    # Skip link with placeholder (template)
    if _PLACEHOLDER_PATTERN.search(href):
        return True

    return False


def validate_link(
    href: str,
    md_file: Path,
    project_root: Path,
) -> bool:
    """Verifies the existence of a file in a single link path.

    The project root standard path (starting from .agent-factory/, .claude/) is interpreted from project_root,
    Other relative paths are interpreted based on the directory where md_file is located.

    Args:
        href: Link path string.
        md_file: Markdown file path containing the link.
        project_root: Project root directory path.

    Returns:
        True if the file exists, False if it does not exist.
    """
    # Path relative to project root
    for prefix in _PROJECT_ROOT_PREFIXES:
        if href.startswith(prefix):
            target = project_root / href
            return target.exists()

    # Relative path: relative to the Markdown file directory
    target = md_file.parent / href
    return target.exists()


def validate_all(
    md_files: list[Path],
    project_root: Path,
) -> tuple[int, int, list[tuple[Path, str]]]:
    """Checks link validity against the entire list of Markdown files.

    Args:
        md_files: List of Markdown file paths to check.
        project_root: Project root directory path.

    Returns:
        (Number of valid links, Number of invalid links, List of invalid links) tuple.
        Each item in the invalid link list is a (markdown file path, href) tuple.
    """
    valid_count: int = 0
    invalid_count: int = 0
    invalid_links: list[tuple[Path, str]] = []

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"[WARN] Failed to read file: {md_file} ({exc})", file=sys.stderr)
            continue

        hrefs = extract_links(content)
        for href in hrefs:
            if _is_skip_link(href):
                continue

            if validate_link(href, md_file, project_root):
                valid_count += 1
            else:
                invalid_count += 1
                invalid_links.append((md_file, href))

    return valid_count, invalid_count, invalid_links


def _print_results(
    valid_count: int,
    invalid_count: int,
    invalid_links: list[tuple[Path, str]],
    project_root: Path,
) -> None:
    """The verification results are output to stdout.

    Args:
        valid_count: Number of valid links.
        invalid_count: Number of invalid links.
        invalid_links: list of invalid links (markdown file path, href) tuple list.
        project_root: Project root path (to display relative paths).
    """
    total_count = valid_count + invalid_count
    print(f"Link inspection results: Total {total_count} (valid {valid_count}, invalid {invalid_count})")

    if invalid_links:
        print("\n List of invalid links (404 expected):")
        for md_file, href in invalid_links:
            # Display relative path relative to project root
            try:
                rel_md = md_file.relative_to(project_root)
            except ValueError:
                rel_md = md_file
            print(f"File: {rel_md}")
            print(f"Link: {href}")
            print()
    else:
        print("\n All internal links are valid.")


def main() -> None:
    """Entry point for the link validation script.

    After parsing the CLI arguments and performing verification,
    If there is an invalid link, it exits with exitcode 1, and if all are valid, it exits with 0.
    """
    parser = argparse.ArgumentParser(
        description=".agent-factory/runs/ Validates links in my markdown files.",
    )
    parser.add_argument(
        "--active-only",
        action="store_true",
        default=False,
        help="Only active workflows (.agent-factory/runs/ direct children) are checked. Excluding .agent-factory/runs/.history/.",
    )
    args = parser.parse_args()

    project_root = _find_project_root()

    # Collect files to scan
    md_files = scan_markdown_files(project_root, active_only=args.active_only)

    scope_label = "active workflow" if args.active_only else "Entire workflow (active+history)"
    print(f"Scan scope: {scope_label}")
    print(f"Number of scanned files: {len(md_files)}")
    print()

    if not md_files:
        print("There are no files to scan.")
        sys.exit(0)

    valid_count, invalid_count, invalid_links = validate_all(md_files, project_root)
    _print_results(valid_count, invalid_count, invalid_links, project_root)

    # exitcode 1 when invalid link exists
    sys.exit(1 if invalid_count > 0 else 0)


if __name__ == "__main__":
    main()
