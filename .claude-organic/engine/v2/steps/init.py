"""INIT Step — driver in-process. LLM 호출 없음.

SPEC.md §9.1.1 (Stage 3-D): command 별 worktree 분기.
- implement → git worktree add + feature_branch 생성 (v1 worktree_manager 재사용)
- research|review → develop 직접 (worktree-less 허용)
"""

from __future__ import annotations

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
    write_status,
)
from .._emitter import step_end, step_start


_VALID_COMMANDS = {"implement", "research", "review"}


def _parse_ticket_meta(dump: str) -> tuple[str, str]:
    """kanban show 출력에서 (command, title) 추출. fallback: ("implement", "untitled")."""
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
    """command=implement 면 v1 worktree_manager.create_worktree 호출.

    Returns: (feature_branch_name, worktree_path). command != implement 면 (None, None).
    실패 시 SystemExit(2).
    """
    if command != "implement":
        return None, None
    # v1 인프라 재사용 (SPEC.md §11.3 보존 영역)
    from flow.worktree_manager import create_worktree  # noqa: E402

    info = create_worktree(ticket_no, title, command=command)
    if info is None:
        sys.stderr.write(
            f"[driver] worktree create 실패 "
            f"(ticket={ticket_no}, command={command}) — INIT 중단\n"
        )
        raise SystemExit(2)
    return info.branch_name, Path(info.path)


def init_step(ticket_no: str) -> WorkflowContext:
    """INIT — kanban Open→In Progress, work_dir + worktree (command 분기) + status.json.

    ticket 존재 가드: kanban_show 결과 'Number:' 토큰 없으면 SystemExit(2).
    work_dir 생성 전에 가드 — work_dir 잔재 회피.
    """
    # ticket guard 먼저 (work_dir 생성 전 — 잔재 회피)
    ticket_dump = kanban_show(ticket_no)
    if not ticket_dump or "Number:" not in ticket_dump:
        sys.stderr.write(
            f"[driver] ticket {ticket_no} not found in kanban — aborting INIT\n"
        )
        raise SystemExit(2)

    command, title = _parse_ticket_meta(ticket_dump)
    feature_branch, worktree_path = _maybe_create_worktree(ticket_no, title, command)

    registry_key = new_registry_key()
    # work_dir 위치: worktree 있으면 그 안, 없으면 메인 .claude-organic/runs/
    if worktree_path is not None:
        runs_root = worktree_path / ".claude-organic" / "runs"
        runs_root.mkdir(parents=True, exist_ok=True)
        work_dir = runs_root / registry_key
        work_dir.mkdir(parents=True, exist_ok=True)
    else:
        work_dir = make_work_dir(registry_key)

    ctx = WorkflowContext(
        ticket_no=ticket_no,
        registry_key=registry_key,
        work_dir=work_dir,
        command=command,
        mode="multi",
        current_step="INIT",
        feature_branch=feature_branch,
    )
    ctx.user_prompt_path().write_text(ticket_dump, encoding="utf-8")
    write_status(ctx, {"workflow_step": "INIT", "transitions": []})
    write_context(ctx)
    append_log(
        ctx,
        f"INIT — registry_key={registry_key}, ticket={ticket_no}, "
        f"command={command}, feature_branch={feature_branch or '(none)'}",
    )
    step_start(ctx, "INIT")
    kanban_move(ticket_no, "progress")
    step_end(ctx, "INIT", outcome="ok")
    update_step(ctx, "INIT", "PLAN")
    return ctx
