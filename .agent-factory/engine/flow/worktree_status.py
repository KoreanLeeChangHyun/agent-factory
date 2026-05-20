"""Worktree status — kanban card uncommitted indicator + commit action.

T-419 진단 도구는 가치 미달로 폐지(commit 99c9ce0). 본 모듈은 워크플로우
회귀(워커 commit 누락) 시 사용자가 칸반 카드 우상단 인디케이터를 클릭해
즉시 commit 할 수 있도록 단순화된 부활 버전.

공개 API:
    get_all_uncommitted: 전체 워크트리의 ticket + uncommitted_count list
    commit_worktree:     워크트리에서 git add -A && git commit -m 실행
"""

from __future__ import annotations

import os
import subprocess
import sys

_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from flow.worktree_manager import (  # noqa: E402
    get_worktree_path,
    is_worktree_enabled,
    list_worktrees,
)


def _count_uncommitted(worktree_path: str) -> int:
    """워크트리 미커밋 변경(modified + untracked) 파일 수 반환.

    git status --porcelain 라인 수로 계산. 실패 시 0 폴백.
    """
    if not os.path.isdir(worktree_path):
        return 0
    try:
        result = subprocess.run(
            ["git", "-C", worktree_path, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return 0
    if result.returncode != 0:
        return 0
    return sum(1 for line in result.stdout.splitlines() if line.strip())


def get_all_uncommitted() -> list[dict]:
    """전체 워크트리의 미커밋 카운트 list 반환 (카드 인디케이터 일괄 조회용).

    Returns:
        [{ticket, path, uncommitted_count}, ...] — 워크트리 모드 비활성 시 빈 list.
    """
    if not is_worktree_enabled():
        return []
    items: list[dict] = []
    for wt in list_worktrees():
        if not wt.ticket_number:
            continue
        items.append(
            {
                "ticket": wt.ticket_number,
                "path": wt.path,
                "uncommitted_count": _count_uncommitted(wt.path),
            }
        )
    return items


def commit_worktree(ticket: str, message: str | None = None) -> dict:
    """워크트리에서 git add -A && git commit -m <msg> 실행.

    워크플로우 회귀(워커 commit 누락) 시 사용자 수동 수습 경로.
    message 가 비어있으면 자동 메시지(`wip(T-NNN): pending worktree changes`)
    로 채운다.

    Returns:
        {ok: bool, ticket, path, message, stdout?} | {ok: False, error}
    """
    if not ticket.startswith("T-"):
        ticket = f"T-{ticket}"
    wt_path = get_worktree_path(ticket)
    if not wt_path or not os.path.isdir(wt_path):
        return {"ok": False, "error": f"worktree not found for {ticket}"}

    if not message or not message.strip():
        message = f"wip({ticket}): pending worktree changes"

    add = subprocess.run(
        ["git", "-C", wt_path, "add", "-A"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if add.returncode != 0:
        return {
            "ok": False,
            "error": f"git add failed: {add.stderr.strip() or add.stdout.strip()}",
        }

    commit = subprocess.run(
        ["git", "-C", wt_path, "commit", "-m", message],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if commit.returncode != 0:
        return {
            "ok": False,
            "error": (
                f"git commit failed: "
                f"{commit.stderr.strip() or commit.stdout.strip() or 'nothing to commit'}"
            ),
        }

    return {
        "ok": True,
        "ticket": ticket,
        "path": wt_path,
        "message": message,
        "stdout": commit.stdout.strip(),
    }
