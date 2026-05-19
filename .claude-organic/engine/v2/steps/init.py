"""INIT Step — driver in-process. LLM 호출 없음.

SPEC.md §9.1.1 (Stage 3-D): command 별 worktree 분기.
- implement → git worktree add + feature_branch 생성 (v1 worktree_manager 재사용)
- research|review → develop 직접 (worktree-less 허용)

T-495 P2: V2_REGISTRY_KEY env 우선 — board kanban submit 핸들러가
session_id 를 사전 발급할 수 있도록 registry_key 결정론을 외부에서 주입
가능하게 한다. env 미설정 시 기존 new_registry_key() 동작 보존.
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
    # flow-wf wrapper 의 PYTHONPATH=.claude-organic 환경 안에서는 fully-qualified
    # path (engine.flow) 만 import 가능. cwd=.claude-organic/engine 가정의 짧은
    # `from flow.worktree_manager` 는 ImportError (다른 v1 호출자와 환경 차이).
    from engine.flow.worktree_manager import create_worktree  # noqa: E402

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

    # T-495 P2 — V2_REGISTRY_KEY env 우선 사용. board 가 사전 발급한 키를
    # 받으면 backend 의 v2_workflow_registry 와 driver 의 work_dir 경로가
    # 1:1 정합되어, frontend 가 LAUNCH_STARTED 직후 v2 탭을 즉시 띄울 수 있다.
    # env 형식: "YYYYMMDD-HHMMSS" 또는 "YYYYMMDD-HHMMSS-NNN" 등 v1 호환 timestamp.
    env_key = (os.environ.get("V2_REGISTRY_KEY") or "").strip()
    registry_key = env_key if env_key else new_registry_key()
    # T-509 — work_dir 는 항상 메인 측 (PROJECT_ROOT 기준 RUNS_DIR / <key>).
    # worktree_path 가 있어도 분기하지 않는다 — a473334 이후 PROJECT_ROOT 는
    # git common-dir 의 부모 (메인 워크트리 root) 를 가리키므로, worktree 안쪽
    # .claude-organic/runs/ 에 산출물을 박으면 finalization R-EXIST / history
    # sync / SSE FileWatcher 인덱스가 모두 메인 측만 보는 SSOT 와 어긋난다.
    # worktree 자체는 ctx.worktree_path 로 보존 — auto_commit / verify_code 가
    # 워크트리 cwd 에서 git add/commit 하는 의미는 그대로 유지된다.
    work_dir = make_work_dir(registry_key)

    # Stage 3-B — board side workflow_registry 매핑 ID. driver 측 자체 발급으로
    # 결정론 유지 (registry_key 가 이미 timestamp 형식이라 충돌 0).
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
    # T-495 P1 — session 명시 등록 (POST /api/v2/sessions). lazy create 폐기.
    # V2_BOARD_POST 미설정 시 silent skip — driver 흐름 영향 0.
    session_create(ctx)
    step_start(ctx, "INIT", prev_step="NONE")
    kanban_move(ticket_no, "progress")
    step_end(ctx, "INIT", outcome="ok")
    update_step(ctx, "INIT", "PLAN")
    return ctx
