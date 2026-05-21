"""INIT Step — driver in-process. No LLM calls.

SPEC.md §9.1.1 (Stage 3-D): Worktree branching by command.
- implement → git worktree add + create feature_branch (reuse v1 worktree_manager)
- research|review → develop directly (allows worktree-less)

T-495 P2: V2_REGISTRY_KEY env priority — board kanban submit handler
Inject registry_key determinism externally to pre-issue session_id
Make it possible. If env is not set, existing new_registry_key() behavior is preserved.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from .._common import (
    WorkflowContext,
    append_log,
    kanban_move,
    kanban_show,
    make_work_dir,
    new_registry_key,
    update_step,
    write_context,
    write_metadata,
    write_status,
)
from .._emitter import session_create, step_end, step_start


_VALID_COMMANDS = {"implement", "research", "review"}


def _parse_ticket_meta(dump: str) -> tuple[str, str]:
    """Extract (command, title) from kanban show output. fallback: ("implement", "untitled")."""
    command = "implement"
    title = "untitled"
    for line in dump.splitlines():
        m = re.match(r"\s*-\s*Command:\s*(\S+)", line)
        if m:
            cand = m.group(1).strip().lower()
            if cand in _VALID_COMMANDS:
                command = cand
            continue
        m = re.match(r"\s*-\s*Title:\s*(.+)", line)
        if m:
            title = m.group(1).strip()
    return command, title


def _maybe_create_worktree(
    ticket_no: str, title: str, command: str
) -> tuple[str | None, Path | None]:
    """If command=implement, call v1 worktree_manager.create_worktree.

    Returns: (feature_branch_name, worktree_path). If command != implement (None, None).
    SystemExit(2) on failure.
    """
    if command != "implement":
        return None, None
    # v1 Infrastructure Reuse (SPEC.md §11.3 Conservation Area)
    # Fully-qualified within the PYTHONPATH=.agent-factory environment of the flow-wf wrapper
    # Only path (engine.flow) can be imported. short for assuming cwd=.agent-factory/engine
    # `from flow.worktree_manager` throws an ImportError (different environment from other v1 callers).
    from engine.flow.worktree_manager import create_worktree  # noqa: E402

    info = create_worktree(ticket_no, title, command=command)
    if info is None:
        sys.stderr.write(
            f"[driver] worktree create failed"
            f"(ticket={ticket_no}, command={command}) — INIT Abort \n"
        )
        raise SystemExit(2)
    return info.branch_name, Path(info.path)


def init_step(ticket_no: str) -> WorkflowContext:
    """INIT — kanban Open→In Progress, work_dir + worktree (command branch) + status.json.

    ticket presence guard: If token 'Number:' is not found in kanban_show result, SystemExit(2).
    Guard before creating work_dir — Avoid work_dir remnants.
    """
    # ticket guard first (before creating work_dir — avoiding remnants)
    ticket_dump = kanban_show(ticket_no)
    if not ticket_dump or "Number:" not in ticket_dump:
        sys.stderr.write(
            f"[driver] ticket {ticket_no} not found in kanban — aborting INIT\n"
        )
        raise SystemExit(2)

    command, title = _parse_ticket_meta(ticket_dump)
    feature_branch, worktree_path = _maybe_create_worktree(ticket_no, title, command)

    # T-495 P2 — Use V2_REGISTRY_KEY env first. The board pre-issued key
    # Once received, the backend's production_line_registry and driver's work_dir paths are
    # With a 1:1 match, the frontend can immediately launch the production-line tab right after LAUNCH_STARTED.
    # env format: v1-compatible timestamp, such as "YYYYMMDD-HHMMSS" or "YYYYMMDD-HHMMSS-NNN".
    env_key = (os.environ.get("V2_REGISTRY_KEY") or "").strip()
    registry_key = env_key if env_key else new_registry_key()
    # T-509 — work_dir is always on the main side (RUNS_DIR/<key> relative to PROJECT_ROOT).
    # Doesn't branch even if worktree_path exists — PROJECT_ROOT after a473334
    # Since it points to the parent (main worktree root) of git common-dir, it is located inside the worktree.
    # If you put the output in .agent-factory/runs/, finalization R-EXIST / history
    # The sync / SSE FileWatcher indexes are all out of sync with SSOT, which only looks at the main side.
    # The worktree itself is preserved as ctx.worktree_path — auto_commit / verify_code
    # The meaning of git add/commit in the worktree cwd remains the same.
    work_dir = make_work_dir(registry_key)

    # Stage 3-B — board side workflow_registry mapping ID. Issued by the driver itself
    # Maintain determinism (crash 0 because registry_key is already in timestamp format).
    wf_session_id = f"wf-{ticket_no}-{registry_key}"
    ctx = WorkflowContext(
        ticket_no=ticket_no,
        registry_key=registry_key,
        work_dir=work_dir,
        command=command,
        mode="multi",
        current_step="INIT",
        feature_branch=feature_branch,
        worktree_path=worktree_path,
        title=title,
        wf_session_id=wf_session_id,
    )
    ctx.user_prompt_path().write_text(ticket_dump, encoding="utf-8")
    write_status(ctx, {"workflow_step": "INIT", "transitions": []})
    write_context(ctx)
    write_metadata(ctx)
    append_log(
        ctx,
        f"INIT — registry_key={registry_key}, ticket={ticket_no}, "
        f"command={command}, feature_branch={feature_branch or '(none)'}",
    )
    # T-495 P1 — Session explicit registration (POST /api/v2/sessions). lazy create discard.
    # If V2_BOARD_POST is not set, silent skip — driver flow impact 0.
    session_create(ctx)
    step_start(ctx, "INIT", prev_step="NONE")
    kanban_move(ticket_no, "progress")
    step_end(ctx, "INIT", outcome="ok")
    update_step(ctx, "INIT", "PLAN")
    return ctx
