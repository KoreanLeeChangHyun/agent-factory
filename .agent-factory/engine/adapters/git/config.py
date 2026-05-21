#!/usr/bin/env -S python3 -u
"""Git Config auto-configuration script.

Automatically configures git config from the current project git identity.

Main functions:
    main: Git configuration application entry point

Usage: python3 git_config.py [--global|--local]
  --global Global settings (~/.gitconfig) [default]
  --local Local configuration (.git/config)

Environment variables (loaded from .agent-factory/.settings):
  GIT_USER_NAME - Git user.name override (optional)
  GIT_USER_EMAIL - Git user.email override (optional)
  GITHUB_USERNAME - GitHub username (optional)
  SSH_KEY_GITHUB - GitHub SSH key path (optional)

Legacy AGENT_FACTORY_* and CLAUDE_CODE_* names are still accepted for existing installations.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ENGINE_DIR = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", ".."))
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from common import read_env
from flow.cli_utils import build_common_epilog

_PROJECT_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", "..", ".."))
_CW_DIR = os.path.join(_PROJECT_ROOT, ".agent-factory")
_ENV_FILE = os.path.join(_CW_DIR, ".settings")


def _read_setting(key: str, *legacy_keys: str) -> str:
    for candidate in (key, *legacy_keys):
        value = read_env(candidate, env_file=_ENV_FILE)
        if value:
            return value
    return ""


def _read_project_git_config(key: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", _PROJECT_ROOT, "config", "--get", key],
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).decode().strip()
    except Exception:
        return ""


def _git_config_get(scope: str, key: str) -> str:
    """Reads and returns the git config value.

    Args:
        scope: git config scope ('--global' or '--local')
        key: configuration key to read (e.g. 'user.name')

    Returns:
        Setting value string. If there is no setting or an error occurs, '(Not set)' is returned.
    """
    try:
        return subprocess.check_output(
            ["git", "config", scope, key],
            stderr=subprocess.DEVNULL, timeout=5
        ).decode().strip()
    except Exception:
        return "(Not set)"


def _build_parser() -> argparse.ArgumentParser:
    """Creates and returns an ArgumentParser exclusive to git_config.

    --global / --local are composed of mutually exclusive groups.
    The default is --global.

    Returns:
        A configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="flow-gitconfig",
        description=(
            "Read Git identity from the current project git config and "
            "apply it to the requested git config scope."
        ),
        epilog=build_common_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    scope_group = parser.add_mutually_exclusive_group()
    scope_group.add_argument(
        "--global",
        dest="scope",
        action="store_const",
        const="--global",
        help="Applies to global settings (~/.gitconfig) [default]",
    )
    scope_group.add_argument(
        "--local",
        dest="scope",
        action="store_const",
        const="--local",
        help="Applies to local settings (.git/config)",
    )
    return parser


def main() -> None:
    """Entry point for Git config autoconfiguration.

    Read environment variables from .agent-factory/.settings to create git user.name, user.email,
    Apply core.sshCommand to the specified scope (global/local).
    Compare and output the status before and after the change.

    Raises:
        SystemExit: When a configuration file is missing, git identity is missing, or an unknown option is specified.
    """
    # --- Option parsing ---
    parser = _build_parser()
    args = parser.parse_args()

    scope = args.scope if args.scope is not None else "--global"
    scope_label = "global" if scope == "--global" else "local"

    # --- Check .settings file ---
    if not os.path.isfile(_ENV_FILE):
        print(f"[ERROR] Configuration file does not exist: {_ENV_FILE}", file=sys.stderr)
        sys.exit(1)

    # --- Load environment variables ---
    git_user_name = _read_setting("GIT_USER_NAME", "AGENT_FACTORY_GIT_USER_NAME", "CLAUDE_CODE_GIT_USER_NAME")
    git_user_email = _read_setting("GIT_USER_EMAIL", "AGENT_FACTORY_GIT_USER_EMAIL", "CLAUDE_CODE_GIT_USER_EMAIL")
    git_user_name = git_user_name or _read_project_git_config("user.name")
    git_user_email = git_user_email or _read_project_git_config("user.email")
    # Currently not in use - expected to be integrated with GitHub API in the future
    _github_username = _read_setting("GITHUB_USERNAME", "AGENT_FACTORY_GITHUB_USERNAME", "CLAUDE_CODE_GITHUB_USERNAME")
    ssh_key_github = _read_setting("SSH_KEY_GITHUB", "AGENT_FACTORY_SSH_KEY_GITHUB", "CLAUDE_CODE_SSH_KEY_GITHUB")

    # --- Verification of project git identity ---
    if not git_user_name:
        print("[ERROR] git config user.name is not set for this project.", file=sys.stderr)
        sys.exit(1)

    if not git_user_email:
        print("[ERROR] git config user.email is not set for this project.", file=sys.stderr)
        sys.exit(1)

    # --- Before state collection ---
    before_name = _git_config_get(scope, "user.name")
    before_email = _git_config_get(scope, "user.email")
    before_ssh = _git_config_get(scope, "core.sshCommand")

    # --- Apply settings ---
    print(f"[STATE] GITCONFIG ({scope_label})", flush=True)
    print(f">> user.name={git_user_name}, user.email={git_user_email}", flush=True)
    print(f"[INFO] Git config ({scope_label}) Apply settings...")

    subprocess.run(["git", "config", scope, "user.name", git_user_name], check=True, timeout=5)
    print(f"[OK] user.name = {git_user_name}")

    subprocess.run(["git", "config", scope, "user.email", git_user_email], check=True, timeout=5)
    print(f"[OK] user.email = {git_user_email}")

    # Set SSH key (if file exists)
    if ssh_key_github:
        if os.path.isfile(ssh_key_github):
            ssh_cmd = f'ssh -i "{ssh_key_github}" -o IdentitiesOnly=yes'
            subprocess.run(["git", "config", scope, "core.sshCommand", ssh_cmd], check=True, timeout=5)
            print(f"[OK] core.sshCommand = {ssh_cmd}")
        else:
            print(f"[WARN] SSH key file does not exist: {ssh_key_github} (Skip SSH configuration)")

    # --- After status collection ---
    after_name = _git_config_get(scope, "user.name")
    after_email = _git_config_get(scope, "user.email")
    after_ssh = _git_config_get(scope, "core.sshCommand")

    # --- Before/After comparison output ---
    print()
    print("==========================================")
    print(f"Git Config change results ({scope_label})")
    print("==========================================")
    print(f"{'Set':<20s} {'Before':<30s} {'After':<30s}")
    print(f"{'----':<20s} {'------':<30s} {'-----':<30s}")
    print(f"{'user.name':<20s} {before_name:<30s} {after_name:<30s}")
    print(f"{'user.email':<20s} {before_email:<30s} {after_email:<30s}")
    print(f"{'core.sshCommand':<20s} {before_ssh:<30s} {after_ssh:<30s}")
    print("==========================================")
    print()
    print(f"[OK] Git config ({scope_label}) setup complete")


if __name__ == "__main__":
    main()
