"""worktree_status.py - 워크트리 상태 조회 단일 진입점.

기존 ad-hoc git 명령 조합 (lock 파일 stat / git status --porcelain /
rev-list --count / rev-parse --short) 을 표준 schema 한 벌로 통일한다.

CLI / REST API / Board UI 가 동일한 응답 구조를 공유하도록 단일 진실
공급원 역할을 한다.

공개 API:
    get_worktree_status: 단일 티켓의 워크트리 상태 dict 반환
    get_all_worktree_statuses: 전체 활성 워크트리 상태 list 반환

CLI 진입점:
    python3 worktree_status.py [T-NNN | --all] [--json | --table]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any

# ─── sys.path 보장 ────────────────────────────────────────────────────────────

_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import resolve_project_root
from flow.worktree_manager import (
    count_feature_branch_commits,
    get_worktree_path,
    list_worktrees,
)

# ─── 내부 헬퍼 ─────────────────────────────────────────────────────────────────


def _git(
    *args: str, repo_path: str | None = None
) -> subprocess.CompletedProcess[str]:
    """git 명령을 실행한다 (timeout=30, capture).

    worktree_manager._git 와 동일한 동작이지만 모듈 분리를 위해 자체 보유.
    repo_path 가 None 이면 프로젝트 루트로 폴백.
    """
    cwd = repo_path or resolve_project_root()
    cmd = ["git", "-C", cwd] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def _git_common_dir(worktree_path: str) -> str:
    """worktree 의 공통 .git 디렉터리 (메인 저장소 .git) 절대 경로를 반환.

    `git rev-parse --git-common-dir` 은 worktree 안에서도 메인 저장소의
    .git 위치를 가리킨다. lock 파일이 메인 저장소
    `.git/worktrees/<dir>/locked` 에 있으므로 이 경로 해석이 필수다.

    실패 시 빈 문자열 반환 (lock 판정 시 False 폴백).
    """
    result = _git("rev-parse", "--git-common-dir", repo_path=worktree_path)
    if result.returncode != 0:
        return ""
    raw = result.stdout.strip()
    if not raw:
        return ""
    if not os.path.isabs(raw):
        # git 이 worktree 안에서 호출되면 상대 경로를 줄 수 있으므로 정규화
        raw = os.path.normpath(os.path.join(worktree_path, raw))
    return raw


def _is_locked(worktree_path: str) -> bool:
    """worktree lock 마커 파일 존재 여부.

    `git worktree add --lock` 으로 생성된 워크트리는 메인 저장소
    `.git/worktrees/<dir_name>/locked` 파일이 marker 로 존재한다.
    """
    common_dir = _git_common_dir(worktree_path)
    if not common_dir:
        return False
    dir_name = os.path.basename(os.path.normpath(worktree_path))
    locked_marker = os.path.join(common_dir, "worktrees", dir_name, "locked")
    return os.path.isfile(locked_marker)


def _classify_porcelain(stdout: str) -> tuple[int, int, int]:
    """porcelain 출력에서 (총 라인 수, modified 수, untracked 수) 분류.

    porcelain v1 형식은 `XY <path>` 2자 코드로 시작한다.
    - `??` -> untracked
    - 그 외 (M / A / D / R / U 조합) -> modified 카테고리로 일괄 집계
    """
    total = 0
    modified = 0
    untracked = 0
    for line in stdout.splitlines():
        if not line.strip():
            continue
        total += 1
        xy = line[:2] if len(line) >= 2 else ""
        if xy == "??":
            untracked += 1
        else:
            modified += 1
    return total, modified, untracked


def _uncommitted_breakdown(worktree_path: str) -> dict[str, int]:
    """worktree 의 미커밋 변경 수와 분류를 반환한다.

    실패 시 모든 값 0 (false-positive 방지).
    """
    result = _git("status", "--porcelain", repo_path=worktree_path)
    if result.returncode != 0:
        return {"count": 0, "modified": 0, "untracked": 0}
    total, modified, untracked = _classify_porcelain(result.stdout)
    return {"count": total, "modified": modified, "untracked": untracked}


def _head_short(worktree_path: str) -> str:
    """현재 HEAD 의 짧은 SHA 를 반환한다. 실패 시 빈 문자열."""
    result = _git("rev-parse", "--short", "HEAD", repo_path=worktree_path)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _base_diff(
    worktree_path: str, base: str = "develop"
) -> dict[str, int | str]:
    """`git rev-list --left-right --count <base>...HEAD` 결과 파싱.

    출력 형식: `<behind>\t<ahead>` (left=base, right=HEAD).
    실패 시 ahead=0, behind=0 반환.
    """
    result = _git(
        "rev-list",
        "--left-right",
        "--count",
        f"{base}...HEAD",
        repo_path=worktree_path,
    )
    if result.returncode != 0:
        return {"ahead": 0, "behind": 0, "base": base}
    raw = result.stdout.strip()
    parts = raw.split()
    if len(parts) != 2:
        return {"ahead": 0, "behind": 0, "base": base}
    try:
        behind = int(parts[0])
        ahead = int(parts[1])
    except ValueError:
        return {"ahead": 0, "behind": 0, "base": base}
    return {"ahead": ahead, "behind": behind, "base": base}


def _empty_status(ticket: str) -> dict[str, Any]:
    """미존재 워크트리의 default schema (exists=false)."""
    return {
        "ticket": ticket,
        "path": "",
        "exists": False,
        "lock": False,
        "uncommitted_count": 0,
        "uncommitted": {"modified": 0, "untracked": 0},
        "feature_commits": 0,
        "head": "",
        "base_diff": {"ahead": 0, "behind": 0, "base": "develop"},
        "branch": "",
    }


def _hydrate_status(
    ticket: str,
    worktree_path: str,
    branch_name: str,
    base: str = "develop",
    repo_path: str | None = None,
) -> dict[str, Any]:
    """단일 워크트리의 모든 필드를 채운 dict 를 반환한다.

    git 호출 4건 (status / rev-parse common-dir / rev-parse HEAD /
    rev-list left-right) + count_feature_branch_commits 1건 + lock stat 1건.
    """
    uncommitted = _uncommitted_breakdown(worktree_path)
    locked = _is_locked(worktree_path)
    head = _head_short(worktree_path)
    base_diff = _base_diff(worktree_path, base=base)
    feature_commits = count_feature_branch_commits(
        branch_name, base_branch=base, repo_path=repo_path
    )
    if feature_commits < 0:
        # 검사 불가 (-1) 는 0 으로 표면화 — 호출자는 raw 신호를 다루지 않음
        feature_commits = 0
    return {
        "ticket": ticket,
        "path": worktree_path,
        "exists": True,
        "lock": locked,
        "uncommitted_count": uncommitted["count"],
        "uncommitted": {
            "modified": uncommitted["modified"],
            "untracked": uncommitted["untracked"],
        },
        "feature_commits": feature_commits,
        "head": head,
        "base_diff": base_diff,
        "branch": branch_name,
    }


# ─── 공개 API ─────────────────────────────────────────────────────────────────


def get_worktree_status(
    ticket: str, repo_path: str | None = None
) -> dict[str, Any] | None:
    """단일 티켓의 워크트리 상태 dict 를 반환한다.

    Args:
        ticket: 티켓 번호. 'T-' 접두사 자동 보강.
        repo_path: 메인 저장소 경로. None 이면 프로젝트 루트.

    Returns:
        상태 dict. 워크트리 미존재 시 ``exists=False`` default schema.
        ``None`` 반환은 schema 일관성을 위해 사용하지 않는다.
    """
    if not ticket.startswith("T-"):
        ticket = f"T-{ticket}"

    matched_branch = ""
    wt_path = ""
    for wt in list_worktrees(repo_path):
        if wt.ticket_number == ticket:
            matched_branch = wt.branch_name
            wt_path = wt.path
            break

    if not wt_path:
        # 활성 worktree 목록에 없으면 path 추론 시도
        wt_path = get_worktree_path(ticket, repo_path) or ""

    if not wt_path or not os.path.isdir(wt_path):
        return _empty_status(ticket)

    if not matched_branch:
        # path 는 있는데 branch 매칭이 안 된 케이스 — HEAD 의 abbrev-ref 폴백
        result = _git("rev-parse", "--abbrev-ref", "HEAD", repo_path=wt_path)
        if result.returncode == 0:
            matched_branch = result.stdout.strip()

    return _hydrate_status(
        ticket=ticket,
        worktree_path=wt_path,
        branch_name=matched_branch,
        repo_path=repo_path,
    )


def get_all_worktree_statuses(
    repo_path: str | None = None,
) -> list[dict[str, Any]]:
    """전체 활성 워크트리 상태 list 를 반환한다.

    `list_worktrees()` 가 반환한 feature 워크트리 (feat/T-NNN-* 패턴) 만
    포함한다. 메인 저장소·기타 worktree 는 자동 필터링.
    """
    results: list[dict[str, Any]] = []
    for wt in list_worktrees(repo_path):
        if not os.path.isdir(wt.path):
            continue
        results.append(
            _hydrate_status(
                ticket=wt.ticket_number,
                worktree_path=wt.path,
                branch_name=wt.branch_name,
                repo_path=repo_path,
            )
        )
    return results


# ─── CLI 진입점 ───────────────────────────────────────────────────────────────


def _format_table(rows: list[dict[str, Any]]) -> str:
    """list[status dict] 을 ASCII 표로 직렬화한다 (Box-drawing 미사용).

    컬럼: ticket / branch / lock / uncommitted / commits / head / ahead.
    """
    if not rows:
        return "(워크트리 없음)"

    headers = ["ticket", "branch", "lock", "uncommitted", "commits", "head", "ahead"]
    table_rows: list[list[str]] = []
    for r in rows:
        bd = r.get("base_diff", {}) or {}
        table_rows.append(
            [
                str(r.get("ticket", "")),
                str(r.get("branch", "")),
                "yes" if r.get("lock") else "no",
                str(r.get("uncommitted_count", 0)),
                str(r.get("feature_commits", 0)),
                str(r.get("head", "")),
                str(bd.get("ahead", 0)),
            ]
        )

    widths = [len(h) for h in headers]
    for row in table_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def _fmt_row(cells: list[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    out = [_fmt_row(headers), _fmt_row(["-" * w for w in widths])]
    for row in table_rows:
        out.append(_fmt_row(row))
    return "\n".join(out)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flow-worktree-status",
        description="워크트리 상태 조회 (lock / 미커밋 / commit count / HEAD / base diff)",
    )
    parser.add_argument(
        "ticket",
        nargs="?",
        default=None,
        help="티켓 번호 (예: T-419). --all 과 배타적.",
    )
    parser.add_argument(
        "--all",
        dest="all_flag",
        action="store_true",
        help="전체 활성 워크트리 list 출력.",
    )
    fmt = parser.add_mutually_exclusive_group()
    fmt.add_argument(
        "--json",
        dest="fmt_json",
        action="store_true",
        help="JSON 출력 (기본).",
    )
    fmt.add_argument(
        "--table",
        dest="fmt_table",
        action="store_true",
        help="표 출력 (사람용).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.ticket and args.all_flag:
        print(
            "[ERROR] ticket 인자와 --all 은 동시에 사용할 수 없습니다",
            file=sys.stderr,
        )
        return 2
    if not args.ticket and not args.all_flag:
        parser.print_help(sys.stderr)
        return 2

    use_table = bool(args.fmt_table)

    if args.all_flag:
        rows = get_all_worktree_statuses()
        if use_table:
            print(_format_table(rows))
        else:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    status = get_worktree_status(args.ticket)
    if status is None or not status.get("exists"):
        # 미존재 케이스도 schema 출력하되 exit 1 (CLI 약속)
        if use_table:
            print(_format_table([status] if status else []))
        else:
            print(
                json.dumps(
                    status if status else _empty_status(args.ticket),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        print(f"[INFO] 워크트리 없음: {args.ticket}", file=sys.stderr)
        return 1

    if use_table:
        print(_format_table([status]))
    else:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
