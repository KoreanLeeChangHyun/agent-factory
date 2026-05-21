"""GitHub CLI adapter helpers."""

from __future__ import annotations

import shutil
import subprocess


_GH_AUTH_LOGIN_COMMAND = (
    "gh",
    "auth",
    "login",
    "--web",
    "--git-protocol",
    "https",
    "--hostname",
    "github.com",
)


def is_gh_available() -> bool:
    return shutil.which("gh") is not None


def read_authenticated_login() -> str:
    """Return the active GitHub CLI login, or an empty string."""
    if not is_gh_available():
        return ""
    try:
        proc = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def auth_status() -> dict[str, object]:
    """Return a board-safe GitHub CLI auth status snapshot."""
    if not is_gh_available():
        return {
            "installed": False,
            "authenticated": False,
            "login": "",
            "message": "GitHub CLI is not installed.",
            "command": " ".join(_GH_AUTH_LOGIN_COMMAND),
        }
    login = read_authenticated_login()
    return {
        "installed": True,
        "authenticated": bool(login),
        "login": login,
        "message": "Authenticated with GitHub CLI." if login else "GitHub CLI is not authenticated.",
        "command": " ".join(_GH_AUTH_LOGIN_COMMAND),
    }


def start_web_auth() -> dict[str, object]:
    """Start GitHub CLI web auth in the background."""
    if not is_gh_available():
        return {
            "ok": False,
            "started": False,
            "message": "GitHub CLI is not installed.",
            "command": " ".join(_GH_AUTH_LOGIN_COMMAND),
        }
    login = read_authenticated_login()
    if login:
        return {
            "ok": True,
            "started": False,
            "message": f"Already authenticated as {login}.",
            "login": login,
            "command": " ".join(_GH_AUTH_LOGIN_COMMAND),
        }
    try:
        subprocess.Popen(  # noqa: S603
            list(_GH_AUTH_LOGIN_COMMAND),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        return {
            "ok": False,
            "started": False,
            "message": f"Failed to start GitHub CLI auth: {exc}",
            "command": " ".join(_GH_AUTH_LOGIN_COMMAND),
        }
    return {
        "ok": True,
        "started": True,
        "message": "GitHub CLI web authentication started.",
        "command": " ".join(_GH_AUTH_LOGIN_COMMAND),
    }
