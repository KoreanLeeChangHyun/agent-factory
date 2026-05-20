"""User visibility policy single helper.

SSE live broadcast and REST history replay must be applied equally on both sides
Manage user visibility rules in one place. Event exposed to user UI channels
All points must be called this helper.

If you add a new data path, this helper push is identified in the code review stage and regression
Default object view.
"""

from __future__ import annotations


def is_user_visible(data: dict) -> bool:
    """This site uses cookies. By continuing to browse the site you are agreeing to our use of cookies.

    isMeta=True is a Skill/command wrapper user message that is injected by Claude Code harness,
    The actual user input/tool result is not field. exclude user channel exposure.

    Args:
        data: original NDJSON event dict

    Returns:
        True if user UI exposure is allowed, False should be excluded.
    """
    if data.get('isMeta') is True:
        return False
    return True
