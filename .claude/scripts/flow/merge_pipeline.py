#!/usr/bin/env -S python3 -u
"""merge_pipeline.py - 워크트리 병합 파이프라인 자동화 스크립트.

worktree 환경에서 feature 브랜치를 develop에 병합하고 정리하는
5단계 파이프라인을 단일 커맨드로 실행한다.

사용법:
  flow-merge <ticket_number> [--dry-run] [--force]

파이프라인 단계:
  1. 미커밋 변경사항 감지 및 자동 커밋
  2. feature 브랜치를 develop에 --no-ff 병합
  3. worktree unlock + remove (+ feature 브랜치 삭제)
  4. kanban done 처리 (worktree merge hook 중복 방지)
  5. (feature 브랜치 삭제는 3단계에서 처리됨)

옵션:
  --dry-run   각 단계의 예상 동작만 출력하고 실제 수행하지 않음
  --force     merge 승인 검사를 우회 (직접 호출 시)

종료 코드:
  0  성공
  1  병합 충돌 또는 실패
  2  인자 오류 또는 승인 미비
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

# ─── sys.path 보장 ────────────────────────────────────────────────────────────

_scripts_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import resolve_project_root

# ─── 상수 ─────────────────────────────────────────────────────────────────────

_MERGE_APPROVED_ENV: str = "WORKFLOW_MERGE_APPROVED"


# ─── 내부 유틸리티 ────────────────────────────────────────────────────────────


def _git(
    *args: str, repo_path: str | None = None
) -> subprocess.CompletedProcess[str]:
    """git 명령을 실행하고 결과를 반환한다.

    Args:
        *args: git 서브커맨드 및 인자.
        repo_path: git 저장소 경로. None이면 resolve_project_root() 사용.

    Returns:
        CompletedProcess 인스턴스.
    """
    cwd = repo_path or resolve_project_root()
    cmd = ["git", "-C", cwd] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def _info(msg: str) -> None:
    """정보 메시지를 stderr로 출력한다."""
    print(f"[INFO] flow-merge: {msg}", file=sys.stderr, flush=True)


def _error(msg: str) -> None:
    """에러 메시지를 stderr로 출력한다."""
    print(f"[ERROR] flow-merge: {msg}", file=sys.stderr, flush=True)


def _step(num: int, desc: str) -> None:
    """파이프라인 단계 헤더를 출력한다."""
    print(f"\n── Stage {num}: {desc} ──", flush=True)


# ─── 파이프라인 단계 ──────────────────────────────────────────────────────────


def _normalize_ticket(ticket_number: str) -> str:
    """티켓 번호를 T-NNN 형식으로 정규화한다.

    Args:
        ticket_number: 원본 티켓 번호. 숫자만 있으면 T- 접두사 추가.

    Returns:
        T-NNN 형식 티켓 번호.
    """
    if not ticket_number.startswith("T-"):
        ticket_number = f"T-{ticket_number}"
    return ticket_number


def _check_merge_approval(force: bool) -> bool:
    """merge 승인 여부를 검사한다.

    직접 flow-merge 호출 시 WORKFLOW_MERGE_APPROVED 환경변수가
    설정되어 있거나 --force 옵션이 있어야 실행을 허용한다.

    Args:
        force: --force 옵션 사용 여부.

    Returns:
        승인되었으면 True, 미승인이면 False.
    """
    if force:
        return True
    if os.environ.get(_MERGE_APPROVED_ENV) == "1":
        return True
    return False


def _stage1_auto_commit(
    ticket_number: str, worktree_path: str, dry_run: bool
) -> bool:
    """Stage 1: worktree 내 미커밋 변경사항을 감지하고 자동 커밋한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN).
        worktree_path: worktree 절대 경로.
        dry_run: True이면 변경 파일 목록만 출력.

    Returns:
        성공 시 True, 실패 시 False.
    """
    _step(1, "미커밋 변경사항 감지 및 자동 커밋")

    # git status --porcelain으로 변경사항 감지
    result = _git("status", "--porcelain", repo_path=worktree_path)
    if result.returncode != 0:
        _error(f"git status 실패: {result.stderr.strip()}")
        return False

    changed_files = [
        line.strip() for line in result.stdout.splitlines() if line.strip()
    ]

    if not changed_files:
        print("  변경사항 없음 (커밋 불필요)", flush=True)
        return True

    print(f"  미커밋 파일 {len(changed_files)}개 감지:", flush=True)
    for f in changed_files:
        print(f"    {f}", flush=True)

    if dry_run:
        print("  [DRY-RUN] 자동 커밋 건너뜀", flush=True)
        return True

    # git add -A + commit
    add_result = _git("add", "-A", repo_path=worktree_path)
    if add_result.returncode != 0:
        _error(f"git add 실패: {add_result.stderr.strip()}")
        return False

    commit_msg = f"chore: auto-commit before merge ({ticket_number})"
    commit_result = _git(
        "commit", "-m", commit_msg, repo_path=worktree_path
    )
    if commit_result.returncode != 0:
        _error(f"git commit 실패: {commit_result.stderr.strip()}")
        return False

    print(f"  자동 커밋 완료: {commit_msg}", flush=True)
    return True


def _stage2_merge_to_develop(
    ticket_number: str, dry_run: bool
) -> bool:
    """Stage 2: feature 브랜치를 develop에 --no-ff 병합한다.

    worktree_manager.merge_to_develop()를 재사용한다.
    병합 충돌 시 abort 후 충돌 파일 목록을 출력한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN).
        dry_run: True이면 예상 동작만 출력.

    Returns:
        성공 시 True, 실패 시 False.
    """
    _step(2, "feature 브랜치 -> develop 병합")

    from flow.branch_strategy import get_feature_branch_for_ticket
    from flow.worktree_manager import merge_to_develop

    branch_name = get_feature_branch_for_ticket(ticket_number)
    if not branch_name:
        _error(f"{ticket_number}에 연결된 feature 브랜치를 찾을 수 없습니다")
        return False

    print(f"  대상 브랜치: {branch_name}", flush=True)

    if dry_run:
        print(
            f"  [DRY-RUN] git merge --no-ff {branch_name} into develop",
            flush=True,
        )
        return True

    merge_result = merge_to_develop(ticket_number)
    if not merge_result.success:
        if merge_result.conflicts:
            _error("병합 충돌 발생 (merge --abort 완료)")
            print("  충돌 파일:", flush=True)
            for cf in merge_result.conflicts:
                print(f"    - {cf}", flush=True)
            print(
                "  worktree에서 충돌을 해결한 후 다시 시도하세요.",
                flush=True,
            )
        else:
            _error(f"병합 실패: {merge_result.error_message}")
        return False

    print(
        f"  병합 완료: {merge_result.merged_branch} -> develop "
        f"({merge_result.merge_commit[:8]})",
        flush=True,
    )
    return True


def _stage3_remove_worktree(
    ticket_number: str, dry_run: bool
) -> bool:
    """Stage 3: worktree unlock + remove (+ feature 브랜치 삭제).

    worktree_manager.remove_worktree()를 재사용한다.
    merge_to_develop()가 이미 remove_worktree를 호출하므로,
    잔여 worktree가 있는 경우에만 정리한다 (멱등).

    Args:
        ticket_number: 티켓 번호 (T-NNN).
        dry_run: True이면 예상 동작만 출력.

    Returns:
        성공 시 True, 실패 시 False.
    """
    _step(3, "worktree 제거 + feature 브랜치 삭제")

    from flow.worktree_manager import get_worktree_path, remove_worktree

    wt_path = get_worktree_path(ticket_number)
    if wt_path:
        print(f"  worktree 경로: {wt_path}", flush=True)
    else:
        print(
            "  worktree 이미 제거됨 (Stage 2에서 정리 완료)",
            flush=True,
        )
        return True

    if dry_run:
        print(
            f"  [DRY-RUN] worktree unlock + remove: {wt_path}",
            flush=True,
        )
        print("  [DRY-RUN] feature 브랜치 삭제", flush=True)
        return True

    success = remove_worktree(
        ticket_number, delete_branch=True
    )
    if not success:
        _error("worktree 제거 실패")
        return False

    print("  worktree 제거 완료", flush=True)
    return True


def _stage4_kanban_done(
    ticket_number: str, dry_run: bool
) -> bool:
    """Stage 4: kanban done 처리.

    kanban_cli.cmd_done()을 호출한다. cmd_done() 내부의 worktree
    merge hook은 feature 브랜치가 이미 삭제된 상태이므로
    get_feature_branch_for_ticket()이 None을 반환하여 자동으로
    중복 merge를 건너뛴다.

    Args:
        ticket_number: 티켓 번호 (T-NNN).
        dry_run: True이면 예상 동작만 출력.

    Returns:
        성공 시 True, 실패 시 False.
    """
    _step(4, "kanban done 처리")

    if dry_run:
        print(
            f"  [DRY-RUN] kanban done {ticket_number}",
            flush=True,
        )
        print(
            "  [DRY-RUN] worktree merge hook은 feature 브랜치 미존재로 건너뜀",
            flush=True,
        )
        return True

    try:
        from flow.kanban_cli import cmd_done

        cmd_done(ticket_number)
        print(f"  kanban done 완료: {ticket_number}", flush=True)
        return True
    except SystemExit as e:
        if e.code and e.code != 0:
            _error(f"kanban done 실패 (exit code: {e.code})")
            return False
        return True
    except Exception as e:
        _error(f"kanban done 실패: {e}")
        return False


# ─── 메인 파이프라인 ──────────────────────────────────────────────────────────


def run_pipeline(
    ticket_number: str, dry_run: bool = False, force: bool = False
) -> int:
    """5단계 병합 파이프라인을 순차 실행한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식 또는 숫자).
        dry_run: True이면 각 단계의 예상 동작만 출력.
        force: True이면 merge 승인 검사를 우회.

    Returns:
        종료 코드. 0=성공, 1=병합실패, 2=승인미비.
    """
    ticket_number = _normalize_ticket(ticket_number)

    print(f"=== flow-merge: {ticket_number} ===", flush=True)
    if dry_run:
        print("[DRY-RUN 모드] 실제 실행하지 않습니다\n", flush=True)

    # ── 승인 검사 ──
    if not _check_merge_approval(force):
        _error(
            "merge 승인이 필요합니다. "
            "/wf -d 명령을 사용하거나 --force 옵션을 추가하세요."
        )
        return 2

    # ── worktree 경로 탐색 ──
    from flow.worktree_manager import get_worktree_path

    worktree_path = get_worktree_path(ticket_number)

    # ── Stage 1: 미커밋 변경사항 자동 커밋 ──
    if worktree_path:
        if not _stage1_auto_commit(ticket_number, worktree_path, dry_run):
            return 1
    else:
        _step(1, "미커밋 변경사항 감지 및 자동 커밋")
        print("  worktree 없음 (Stage 1 건너뜀)", flush=True)

    # ── Stage 2: feature -> develop 병합 ──
    if not _stage2_merge_to_develop(ticket_number, dry_run):
        return 1

    # ── Stage 3: worktree 제거 + branch 삭제 ──
    if not _stage3_remove_worktree(ticket_number, dry_run):
        # worktree 제거 실패는 경고만 출력하고 계속 진행
        _info("worktree 제거 실패했으나 병합은 완료되었으므로 계속 진행합니다")

    # ── Stage 4: kanban done ──
    if not _stage4_kanban_done(ticket_number, dry_run):
        # kanban done 실패는 경고만 출력
        _info("kanban done 실패했으나 병합은 완료되었습니다")

    # ── Stage 5: feature 브랜치 삭제 (Stage 3에서 처리 완료) ──
    _step(5, "feature 브랜치 삭제")
    print("  Stage 3에서 처리 완료 (delete_branch=True)", flush=True)

    print(f"\n=== flow-merge 완료: {ticket_number} ===", flush=True)
    return 0


# ─── CLI ──────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서를 구성한다.

    Returns:
        구성된 ArgumentParser 인스턴스.
    """
    parser = argparse.ArgumentParser(
        prog="flow-merge",
        description="워크트리 병합 파이프라인 자동화",
    )
    parser.add_argument(
        "ticket_number",
        help="티켓 번호 (T-NNN 또는 숫자)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="예상 동작만 출력하고 실제 수행하지 않음",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="merge 승인 검사 우회 (직접 호출 시)",
    )
    return parser


def main() -> None:
    """CLI 진입점."""
    parser = build_parser()
    args = parser.parse_args()

    exit_code = run_pipeline(
        ticket_number=args.ticket_number,
        dry_run=args.dry_run,
        force=args.force,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
