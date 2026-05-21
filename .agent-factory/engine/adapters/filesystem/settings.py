"""settings.py - Environment variable settings file management adapter.

Responsible for setting/unsetting environment variables in the .agent-factory/.settings file.
Allows only HOOK_*, GUARD_* prefixes and HOOKS_EDIT_ALLOWED keys.
Performs whitelist-based environment variable management.

Scope of responsibility:
    - .agent-factory/.settings environment variable settings (set)
    - Unset .agent-factory/.settings environment variables
    - KEY whitelist verification
    - Atomic file writes
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

# Add engine directory to sys.path to allow common module import
_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import resolve_project_root

PROJECT_ROOT: str = resolve_project_root()


def env_manage(action: str, key: str, value: str = "") -> str:
    """Manage environment variables in the .agent-factory/.settings file.

    Edit the .settings file.

    Args:
        action: Action to perform. Allowed values: 'set', 'unset'.
        key: Environment variable key. Only HOOK_* or GUARD_* prefixes, or HOOKS_EDIT_ALLOWED are allowed.
        value: Value to set (required when action='set')

    Returns:
        Processing result string. Example: 'env -> set HOOK_FOO=bar',
        'env -> unset GUARD_BAR', 'env -> skipped (missing args)', 'env -> failed'.
    """
    if not action or not key:
        print("[WARN] env: action(set|unset) and KEY arguments are required.", file=sys.stderr)
        return "env -> skipped (missing args)"

    if action not in ("set", "unset"):
        print(f"[WARN] env: action only allows set or unset. got={action}", file=sys.stderr)
        return "env -> skipped (invalid action)"

    if action == "set" and not value:
        print("[WARN] env: The set command requires a VALUE argument.", file=sys.stderr)
        return "env -> skipped (missing value)"

    # KEY whitelist verification
    if not key.startswith("HOOK_") and not key.startswith("GUARD_") and key != "HOOKS_EDIT_ALLOWED":
        print(f"[WARN] env: KEY not allowed: {key} (allowed: HOOK_*, GUARD_* prefixes)", file=sys.stderr)
        return "env -> skipped (disallowed key)"

    cw_dir: str = os.path.join(PROJECT_ROOT, ".agent-factory")
    env_file: str = os.path.join(cw_dir, ".settings")
    if not os.path.isfile(env_file):
        print(f"[WARN] env: Cannot find configuration file: {env_file}", file=sys.stderr)
        return "env -> skipped (file not found)"

    try:
        with open(env_file, "r", encoding="utf-8") as f:
            lines: list[str] = f.readlines()

        label: str = ""

        if action == "set":
            found: bool = False
            new_lines: list[str] = []
            for line in lines:
                stripped: str = line.strip()
                if stripped.startswith(key + "="):
                    new_lines.append(f"{key}={value}\n")
                    found = True
                else:
                    new_lines.append(line)

            if not found:
                if new_lines and not new_lines[-1].endswith("\n"):
                    new_lines[-1] += "\n"
                new_lines.append(f"{key}={value}\n")

            lines = new_lines
            label = f"env -> set {key}={value}"

        elif action == "unset":
            new_lines = []
            i: int = 0
            while i < len(lines):
                stripped = lines[i].strip()
                if stripped.startswith(key + "="):
                    if new_lines and new_lines[-1].strip().startswith("#"):
                        new_lines.pop()
                    i += 1
                    continue
                new_lines.append(lines[i])
                i += 1

            lines = new_lines
            label = f"env -> unset {key}"

        # Atomic Write
        dir_name: str = os.path.dirname(env_file)
        fd: int
        tmp_path: str
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.writelines(lines)
            shutil.move(tmp_path, env_file)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        return label
    except Exception as e:
        print(f"[WARN] env failed: {e}", file=sys.stderr)
        return "env -> failed"
