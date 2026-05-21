"""cli utils.py - flow-* script Common argparse butyl module.

argparse type function, provides a common epLog builder, deprecation warning utilities.
When argparse conversion of each script after W02, import this module.

Tag:
    from flow.cli_utils import registry_key_type, work_request_type, build_common_epilog

    parser = argparse.ArgumentParser(
        prog="flow-update",
        epilog=build_common_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("registry_key", type=registry_key_type)
"""

from __future__ import annotations

import argparse
import os
import re
import sys


# ─── Load version ───────────────────────────────────────────────────────────────────

def _load_version() -> str:
    """return the workflow version from .version file.

    returns "unknown" when file read failed.

    Returns:
        Version string (e.g. "2.1.17") or "unknown".
    """
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # scripts/flow/ → scripts/ → .agent-factory/
        workflow_root = os.path.normpath(os.path.join(script_dir, "..", ".."))
        version_path = os.path.join(workflow_root, ".version")
        with open(version_path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return "unknown"


# ─── argparse type function ───────────────────────────────────────────────────────────

def registry_key_type(value: str) -> str:
    """YYYYMMDD-HMMSS format registryKey verification argparse type function.

    argparse add argument(..., type=registry key type)
    argparse.ArgumentTypeError does not match the format and handle it with error.

    Args:
        value: the registryKey string you entered.

    Returns:
        If valid, return the input value.

    Raises:
        argparse.ArgumentTypeError: format YYYYMMDD-HMMSS and other occasions.

    Examples:
        >>> registry_key_type("20260329-224421")
        '20260329-224421'
        >>> registry_key_type("bad-key")
        # ArgumentTypeError occurs
    """
    pattern = r"^\d{8}-\d{6}$"
    if not re.match(pattern, value):
        raise argparse.ArgumentTypeError(
            f"registryKey format error: '{value}' — must be in YYYYMMDD-HHMMSS format (e.g. 20260329-224421)"
        )
    return value


def work_request_type(value: str) -> str:
    """argparse type function that normalizes WR-NNN / NNN / #N WorkRequest numbers.

    conveyor_cli.py / work_request_repository.py
    argparse type

    Tag:

        - 001, 1 (pure number)
        - #001, #1 (# prefix)

    Args:
        value: a WorkRequest number string.

    Returns:
        Normalized string in WR-NNN format (e.g. "WR-042").

    Raises:
        argparse.ArgumentTypeError: In case of an unknown WorkRequest number format.

    Examples:
        >>> work_request_type("42")
        'WR-042'
        >>> work_request_type("#5")
        'WR-005'
        >>> work_request_type("WR-007")
        'WR-007'
    """
    raw = value.strip().lstrip("#")
    # WR-NNN format (ignoring case)
    if re.match(r"^[Ww][Rr]-\d+$", raw):
        parts = raw.split("-", 1)
        num = int(parts[1])
        return f"WR-{num:03d}"
    # pure numbers
    if re.match(r"^\d+$", raw):
        return f"WR-{int(raw):03d}"
    raise argparse.ArgumentTypeError(
        f"WorkRequest number format error: '{value}' — must be one of the following formats: WR-NNN, NNN, #N"
    )


# ─── Common Epilogue ───────────────────────────────────────────────────────────────

def build_common_epilog() -> str:
    """argparse returns a common help erpilgrimage to use.

    We use cookies to ensure that we give you the best experience on our website.
    RawDescriptionHelpFormatter

    Returns:
        Epilot string consisting of multiple lines.

    Examples:
        parser = argparse.ArgumentParser(
            epilog=build_common_epilog(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
    """
    version = _load_version()
    return (
        f"Workflow version: {version} \n"
        "Documentation: See .agent-factory/docs/ or .claude/rules/workflow.md \n"
        "WorkRequest management: flow-conveyor <subcommand> --help"
    )


# ─── deprecation warning utility ────────────────────────────────────────────────────

def deprecation_warning(old: str, new: str) -> None:
    """output sub-compatible warning to stderr.

    argparse while the existing call pattern is temporarily allowed after switching
    Use the user to guide the new format.

    Warning is always output with stderr and does not interrupt the program execution.

    Args:
        old: the existing (deprecated) call format or the optional name.
        new: New calling format or optional name to replace.

    Examples:
        deprecation_warning(
            "update_state.py context <workDir> <agent>",
            "flow-update context <registryKey> <agent>",
        )
    """
    print(
        f"[DEPRECATED] The '{old}' format will be removed in the future."
        f"Use the '{new}' format instead.",
        file=sys.stderr,
    )
