#!/usr/bin/env -S python3 -u
"""Skill activation/archive status management CLI module.

Manage the active/archived status of a skill with the skill-state.json file.
Perform skill archive, activation, and status list queries through CLI.
Exclude archived skills from the catalog by importing them from catalog_sync.py.

Main functions:
    load_skill_state: Load skill-state.json
    save_skill_state: skill-state.json atomic save
    archive_skill: Switch skill to archived state
    activate_skill: Switch skill to active state
    list_skills: Active/archived status classification output
    is_archived: Archive status helper

Usage:
    flow-skill archive <skill_name>
    flow-skill activate <skill_name>
    flow-skill list [--archived | --active]

Exit code: 0 success, 1 failure
"""

from __future__ import annotations

import argparse
import os
import sys

# ─── sys.path settings ────────────────────────────────────────────────────────────────

_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_AGENT_FACTORY_DIR: str = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
if _AGENT_FACTORY_DIR not in sys.path:
    sys.path.insert(0, _AGENT_FACTORY_DIR)

# ─── Import common modules ─────────────────────────────────────────────────────────────

from engine.common import (  # noqa: E402
    C_BOLD,
    C_CYAN,
    C_DIM,
    C_GREEN,
    C_RED,
    C_RESET,
    C_YELLOW,
    atomic_write_json,
    load_json_file,
    resolve_project_root,
)


def _build_common_epilog() -> str:
    """Return CLI help footer without depending on flow runtime modules."""
    return (
        "Workflow version: 2.1.25 \n"
        "Documentation: See .agent-factory/docs/ or .claude/rules/workflow.md \n"
        "WorkRequest management: flow-conveyor <subcommand> --help"
    )

# ─── Constant ───────────────────────────────────────────────────────────────────────

PROJECT_ROOT: str = resolve_project_root()
SKILLS_DIR: str = os.path.join(PROJECT_ROOT, ".claude", "skills")
STATE_FILE: str = os.path.join(SKILLS_DIR, "skill-state.json")

_STATE_VERSION: int = 1


# ─── Core functions ───────────────────────────────────────────────────────────────────


def load_skill_state(state_path: str | None = None) -> dict[str, str]:
    """Load the skill state from skill-state.json.

    If the file does not exist, an empty dictionary is returned and all skills are considered active.

    Args:
        state_path: skill-state.json path. If None, use the default path.

    Returns:
        A dictionary with the skill name as the key and the status ("active" or "archived") as the value.
        Empty dictionary if file does not exist or parsing fails.
    """
    path = state_path or STATE_FILE
    data = load_json_file(path)
    if not isinstance(data, dict):
        return {}
    skills = data.get("skills")
    if not isinstance(skills, dict):
        return {}
    return skills


def save_skill_state(state: dict[str, str], state_path: str | None = None) -> None:
    """Store the skill state atomically in skill-state.json.

    Args:
        state: Skill name-state dictionary.
        state_path: skill-state.json path. If None, use the default path.
    """
    path = state_path or STATE_FILE
    data = {
        "version": _STATE_VERSION,
        "skills": state,
    }
    atomic_write_json(path, data)


def is_archived(name: str, state: dict[str, str]) -> bool:
    """Determine whether the skill is in archive status.

    If there is no key in the state, it is considered active and returns False.

    Args:
        name: Skill name.
        state: State dictionary returned by load_skill_state().

    Returns:
        True if archived, False if otherwise (active or no key).
    """
    return state.get(name) == "archived"


def _validate_skill_exists(name: str) -> bool:
    """Verifies whether the skill directory exists.

    Args:
        name: Skill name.

    Returns:
        True if the directory exists, False if it does not exist.
    """
    skill_dir = os.path.join(SKILLS_DIR, name)
    return os.path.isdir(skill_dir)


def _get_all_skill_names() -> list[str]:
    """Scans the entire list of skill names in the skills directory.

    Returns:
        Sorted list of skill names. Non-directory items and skill-state.json,
        Excluding files such as skill-catalog.md.
    """
    if not os.path.isdir(SKILLS_DIR):
        return []
    return sorted(
        entry
        for entry in os.listdir(SKILLS_DIR)
        if os.path.isdir(os.path.join(SKILLS_DIR, entry))
        and not entry.startswith(".")
    )


def archive_skill(name: str) -> None:
    """Switch the skill to archived state.

    If the skill directory does not exist, an error message is displayed and exit 1.
    If it is already archived, an information message is displayed and the operation terminates normally.

    Args:
        name: The name of the skill to archive.
    """
    if not _validate_skill_exists(name):
        print(
            f"{C_RED}[ERROR]{C_RESET} Skill '{name}' does not exist.",
            file=sys.stderr,
        )
        sys.exit(1)

    state = load_skill_state()

    if is_archived(name, state):
        print("[STATE] SKILL", flush=True)
        print(f">> [INFO] '{name}' is already archived.", flush=True)
        return

    state[name] = "archived"
    save_skill_state(state)
    print("[STATE] SKILL", flush=True)
    print(f">> [OK] '{name}' -> archived", flush=True)


def activate_skill(name: str) -> None:
    """Switches the skill to active state.

    When switching to active, the key is deleted from the state dictionary and restored to the default value (active).
    If the skill directory does not exist, an error message is displayed and exit 1.
    If it is already in the active state, an information message is displayed and the system terminates normally.

    Args:
        name: The name of the skill to activate.
    """
    if not _validate_skill_exists(name):
        print(
            f"{C_RED}[ERROR]{C_RESET} Skill '{name}' does not exist.",
            file=sys.stderr,
        )
        sys.exit(1)

    state = load_skill_state()

    if not is_archived(name, state):
        print("[STATE] SKILL", flush=True)
        print(f">> [INFO] '{name}' is already active.", flush=True)
        return

    # Restore active default by deleting key
    state.pop(name, None)
    save_skill_state(state)
    print("[STATE] SKILL", flush=True)
    print(f">> [OK] '{name}' -> active", flush=True)


def list_skills(filter_mode: str | None = None) -> None:
    """Prints a list of skill status.

    Depending on filter_mode, all, only archived, and only active are output.

    Args:
        filter_mode: If "archived", only archived, if "active", only active, if None, output all.
    """
    all_names = _get_all_skill_names()
    if not all_names:
        print("[STATE] SKILL", flush=True)
        print(">> [INFO] There is no skill.", flush=True)
        return

    state = load_skill_state()

    active_names: list[str] = []
    archived_names: list[str] = []

    for name in all_names:
        if is_archived(name, state):
            archived_names.append(name)
        else:
            active_names.append(name)

    print("[STATE] SKILL list", flush=True)
    print(f">> Total: {len(all_names)} skills (active: {len(active_names)}, archived: {len(archived_names)})", flush=True)

    if filter_mode == "archived":
        if not archived_names:
            return
        print(f"{C_BOLD}Archived ({len(archived_names)}){C_RESET}")
        for name in archived_names:
            print(f"  {C_DIM}{name}{C_RESET}")
    elif filter_mode == "active":
        if not active_names:
            return
        print(f"{C_BOLD}Active ({len(active_names)}){C_RESET}")
        for name in active_names:
            print(f"  {C_CYAN}{name}{C_RESET}")
    else:
        # Total output: active first, archived later
        print(f"{C_BOLD}Active ({len(active_names)}){C_RESET}")
        for name in active_names:
            print(f"  {C_CYAN}{name}{C_RESET}")
        if archived_names:
            print(f"\n{C_BOLD}Archived ({len(archived_names)}){C_RESET}")
            for name in archived_names:
                print(f"  {C_DIM}{name}{C_RESET}")


# ─── argparse parser configuration ──────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Constructs and returns an argparse-based CLI parser.

    Returns:
        A configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="flow-skill",
        description="Skill active/archived status management CLI",
        epilog=_build_common_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # archive subcommand
    archive_parser = subparsers.add_parser(
        "archive",
        help="Switch the skill to archived state",
    )
    archive_parser.add_argument("skill_name", help="Skill name to archive")

    # activate subcommand
    activate_parser = subparsers.add_parser(
        "activate",
        help="Switch the skill to active state",
    )
    activate_parser.add_argument("skill_name", help="Skill name to activate")

    # list subcommand
    list_parser = subparsers.add_parser(
        "list",
        help="Check the skill status list",
    )
    list_filter_group = list_parser.add_mutually_exclusive_group()
    list_filter_group.add_argument(
        "--archived",
        action="store_true",
        default=False,
        help="Only archived status skills are displayed.",
    )
    list_filter_group.add_argument(
        "--active",
        action="store_true",
        default=False,
        help="Displays only skills in active state",
    )

    return parser


# ─── CLI entry point ──────────────────────────────────────────────────────────────────


def main() -> None:
    """CLI entry point. Parse the subcommand with argparse subparsers and call the corresponding handler."""
    parser = build_parser()
    args = parser.parse_args()

    if args.subcommand == "archive":
        archive_skill(args.skill_name)

    elif args.subcommand == "activate":
        activate_skill(args.skill_name)

    elif args.subcommand == "list":
        filter_mode: str | None = None
        if args.archived:
            filter_mode = "archived"
        elif args.active:
            filter_mode = "active"
        list_skills(filter_mode)


if __name__ == "__main__":
    main()
