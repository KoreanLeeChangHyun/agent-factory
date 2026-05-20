"""session identifier.py - Session type identification abstraction layer.

We provide integrated interface that distinguishes workflow sessions and main sessions.
environment variable( WF SESSION TYPE,  WF TICKET ID) priority path and
The TMUX PANE-based poly bag path is abstracted into a single API.

Session Identification Crystal Flow:
  1. If the  WF SESSION TYPE environment variable exists, the value will be returned immediately.
  2. When the TMUX PANE environment variable exists, Windows name with tmux display-message
     P:T-* by inquiry.
  3. FAQs return "unknown" without both.

Tag:
  WINDOW PREFIX P, MAIN WINDOW DEFAULT
  The existing tmux utils.py consumption code can be switched to this module.
"""

from __future__ import annotations

import os
import subprocess

__all__ = [
    "get_session_type",
    "is_workflow_session",
    "get_session_ticket_id",
    "WINDOW_PREFIX_P",
    "MAIN_WINDOW_DEFAULT",
]

# ---------------------------------------------------------------------------
# Backwards compatible constants (migrated from tmux_utils.py)
# ---------------------------------------------------------------------------

WINDOW_PREFIX_P: str = "P:"
"""tmux workflow window name prefix."""

MAIN_WINDOW_DEFAULT: str = "main"
"""Main session default window name."""

# ---------------------------------------------------------------------------
# environment variable key
# ---------------------------------------------------------------------------

_ENV_SESSION_TYPE: str = "_WF_SESSION_TYPE"
"""Session type environment variable key. value:"workflow", "main"."""

_ENV_TICKET_ID: str = "_WF_TICKET_ID"
"""Ticket ID environment variable key. value:"T-NNN"."""

# ---------------------------------------------------------------------------
# session type constant
# ---------------------------------------------------------------------------

SESSION_TYPE_WORKFLOW: str = "workflow"
SESSION_TYPE_MAIN: str = "main"
SESSION_TYPE_UNKNOWN: str = "unknown"

# ---------------------------------------------------------------------------
# internal helper
# ---------------------------------------------------------------------------


def _get_current_window_name() -> str:
    """return the tmux window name in the current process.

    Using TMUX PANE environment variables, the process is actually running pane
    Please check the window name. If there is no TMUX PANE, return the active Windows name.

    Returns:
        current window name string. empty strings when failed.
    """
    tmux_pane = os.environ.get("TMUX_PANE")
    if tmux_pane:
        result = subprocess.run(
            ["tmux", "display-message", "-t", tmux_pane, "-p", "#W"],
            capture_output=True,
            text=True,
        )
    else:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#W"],
            capture_output=True,
            text=True,
        )
    if result.returncode == 0:
        return result.stdout.strip()
    return ""


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def get_session_type() -> str:
    """Returns the type of current session.

    Payment Terms:
      1. FAQ `` WF SESSION TYPE` environment variable value (if set, return immediately)
      2. If ``TMUX PANE` environment variable, look for tmux window name
         ``P:T-*` ``workflow``, or ``main'`
      3. FAQs "unknown"

    Returns:
        ``"workflow"`` | ``"main"`` | ``"unknown"``
    """
    # 1) Environment variable priority path
    env_type = os.environ.get(_ENV_SESSION_TYPE, "").strip().lower()
    if env_type:
        return env_type

    # 2) TMUX_PANE fallback path
    tmux_pane = os.environ.get("TMUX_PANE")
    if not tmux_pane:
        return SESSION_TYPE_UNKNOWN

    window_name = _get_current_window_name()
    if window_name.startswith(f"{WINDOW_PREFIX_P}T-"):
        return SESSION_TYPE_WORKFLOW
    return SESSION_TYPE_MAIN


def is_workflow_session() -> bool:
    """The current session is based on the workflow session.

    ``get session type()`''s result is ``workflow'`
    Convenience Rapper.

    Returns:
        If the workflow session is ``True``, and ``False```.
    """
    return get_session_type() == SESSION_TYPE_WORKFLOW


def get_session_ticket_id() -> str | None:
    """Returns the active ticket ID in the current session.

    Payment Terms:
      1. FAQ ` WF TICKET ID` environment variable value (if set, return immediately)
      2. ``TMUX PANE` if environment variable is in tmux window name
         ``P:T-NNN` returns ``T-NNN`
      3. FAQs [None]

    Returns:
        Ticket ID string (e.g. ""T-001" ). ``None``` when extraction failed.
    """
    # 1) Environment variable priority path
    env_ticket = os.environ.get(_ENV_TICKET_ID, "").strip()
    if env_ticket:
        return env_ticket

    # 2) TMUX_PANE fallback path
    tmux_pane = os.environ.get("TMUX_PANE")
    if not tmux_pane:
        return None

    window_name = _get_current_window_name()
    prefix = f"{WINDOW_PREFIX_P}T-"
    if not window_name.startswith(prefix):
        return None

    # Remove the "P:" prefix to return only the "T-NNN" part
    return window_name[len(WINDOW_PREFIX_P):]
