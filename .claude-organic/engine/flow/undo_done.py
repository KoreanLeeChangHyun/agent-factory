"""undo_done.py - Done 처리된 워크플로우를 Review 단계로 자동 롤백하는 모듈.

Done 후 발견된 치명 버그를 깨끗이 되돌리기 위해 다음 단계를 일관 수행한다:

  1. 사전 검증 — 티켓 Done 상태 / merge_commit 존재 / merge anchor 정합 /
     브랜치 + worktree 점유 검사
  2. 푸시 여부 분기 — `git branch -r --contains <merge_commit>` 출력으로
     local-only 인지 origin/develop 도달인지 origin/main 도달인지 식별
  3. develop 복원 —
       - 전략 1 reset: push 전 + 후속 commit 0개 → `git reset --hard merge_commit^`
       - 전략 2 revert: push 후 또는 후속 commit 누적 → `git revert -m 1 --no-edit`
  4. 워크트리 재생성 — `worktree_manager.create_worktree()` 호출
  5. 칸반 force 전이 — 티켓 XML 을 `done/T-NNN.xml` → `review/T-NNN.xml` 로 이동 +
     `<status>` 를 "Review" 로 갱신
  6. 사후 출력 — git status / log / 다음 절차 안내

공개 API:
    main: argparse 진입점 (flow-undo-done wrapper 가 호출)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Literal

# ─── sys.path 보장 ────────────────────────────────────────────────────────────

_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import resolve_project_root
from flow.branch_strategy import get_feature_branch_for_ticket
from flow.cli_utils import build_common_epilog, ticket_type
from flow.ticket_repository import (
    KANBAN_DONE_DIR,
    find_ticket_file,
    move_ticket_to_status_dir,
    parse_ticket_xml,
)
from flow.ticket_state import update_ticket_status
from flow.worktree_manager import (
    WorktreeInfo,
    create_worktree,
    get_worktree_path,
)

# ─── 타입 별칭 ────────────────────────────────────────────────────────────────

PushState = Literal["local", "pushed", "main"]


# ─── 로깅 ─────────────────────────────────────────────────────────────────────


def _log(msg: str) -> None:
    """단계별 진행 로그를 stdout 으로 출력한다."""
    print(f"[undo-done] {msg}", flush=True)


def _err(msg: str) -> None:
    """에러 로그를 stderr 로 출력하고 SystemExit(2) 를 던진다."""
    print(f"[undo-done] ERROR: {msg}", file=sys.stderr, flush=True)
    raise SystemExit(2)


def _warn(msg: str) -> None:
    """경고 로그를 stderr 로 출력한다 (계속 진행)."""
    print(f"[undo-done] WARN: {msg}", file=sys.stderr, flush=True)


# ─── git 헬퍼 ────────────────────────────────────────────────────────────────


def _git(
    *args: str, repo_path: str | None = None, check: bool = False
) -> subprocess.CompletedProcess[str]:
    """git 명령을 실행한다.

    Args:
        *args: git 서브커맨드 및 인자.
        repo_path: 저장소 경로. None 이면 프로젝트 루트.
        check: True 이면 returncode != 0 시 _err 로 abort.

    Returns:
        CompletedProcess 인스턴스.
    """
    cwd = repo_path or resolve_project_root()
    cmd = ["git", "-C", cwd] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if check and result.returncode != 0:
        _err(
            f"git {' '.join(args)} 실패 (exit={result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result


# ─── 사전 검증 (T2.2) ────────────────────────────────────────────────────────


def _validate_ticket_done(ticket_id: str) -> str:
    """티켓이 Done 디렉터리에 존재하고 status="Done" 인지 검증한다.

    Args:
        ticket_id: T-NNN 형식 티켓 번호.

    Returns:
        티켓 XML 파일 절대 경로.

    Raises:
        SystemExit: Done 상태가 아니거나 파일이 없을 때.
    """
    ticket_file = find_ticket_file(ticket_id)
    if ticket_file is None:
        _err(f"{ticket_id} 티켓 파일을 찾을 수 없습니다")

    ticket_data = parse_ticket_xml(ticket_file)
    status = ticket_data.get("status", "")
    if status != "Done":
        _err(
            f"{ticket_id} 은 Done 상태가 아닙니다 (현재: {status!r}). "
            "undo-done 은 Done 티켓 전용입니다."
        )

    # 파일이 done 디렉터리에 위치해 있는지 확인 (방어적 검증)
    if os.path.normpath(os.path.dirname(ticket_file)) != os.path.normpath(
        KANBAN_DONE_DIR
    ):
        _warn(
            f"티켓 status 는 Done 이지만 파일이 done/ 외부에 있습니다: "
            f"{ticket_file}"
        )

    _log(f"티켓 검증 통과: {ticket_id} status=Done file={ticket_file}")
    return ticket_file


def _load_merge_commit(ticket_id: str, ticket_file: str, force: bool) -> str:
    """티켓 result.merge_commit 를 로드하고, 누락 시 reflog fallback 을 시도한다.

    Args:
        ticket_id: T-NNN 형식.
        ticket_file: 티켓 XML 절대 경로.
        force: True 이면 누락 시 reflog 에서 추정 시도.

    Returns:
        merge_commit SHA (40자리 hex 또는 짧은 형식).

    Raises:
        SystemExit: merge_commit 가 없고 force 가 False 이거나 fallback 실패.
    """
    ticket_data = parse_ticket_xml(ticket_file)
    result = ticket_data.get("result") or {}
    merge_commit = (result.get("merge_commit") or "").strip()

    if merge_commit:
        _log(f"merge_commit 로드: {merge_commit[:8]} (티켓 result 에서)")
        return merge_commit

    if not force:
        _err(
            f"{ticket_id} result.merge_commit 가 비어있습니다. "
            "Phase 1 인프라 도입 이전에 Done 처리된 티켓일 수 있습니다. "
            "--force 플래그로 reflog fallback 을 시도하거나, "
            f"flow-kanban update-result {ticket_id} --merge-commit <SHA> 로 수동 보강하세요."
        )

    # reflog fallback: feat/T-NNN-* 머지 메시지 탐색
    _warn("merge_commit 누락, --force 로 reflog fallback 시도")
    reflog_result = _git(
        "reflog",
        "--grep-reflog=" + f"merge.*feat/{ticket_id}",
        "--format=%H %gs",
        "develop",
    )
    if reflog_result.returncode != 0 or not reflog_result.stdout.strip():
        _err(
            "reflog 에서 후보 merge commit 을 찾지 못했습니다. "
            "reflog 가 만료되었거나 다른 브랜치에 머지된 것으로 추정됩니다. "
            "수동으로 git log 에서 SHA 를 식별한 후 --merge-commit 로 지정하세요."
        )

    candidate = reflog_result.stdout.strip().splitlines()[0].split(" ", 1)[0]
    _warn(
        f"reflog fallback 후보 SHA={candidate[:8]} — 신뢰성이 낮으니 사후 git log 를 반드시 검토하세요"
    )
    return candidate


def _verify_merge_anchor(merge_commit: str, expected_branch: str) -> None:
    """merge_commit^2 == feature 브랜치 tip 인지 검증한다.

    merge_pipeline._stage2_5_verify_merge_anchor 패턴을 답습한다.
    feature 브랜치가 이미 삭제된 경우는 비차단 (정상 정리 후 상태).

    Args:
        merge_commit: 검증 대상 머지 커밋 SHA.
        expected_branch: feat/T-NNN-* 형식 feature 브랜치명 (또는 빈 문자열).

    Raises:
        SystemExit: parent2 가 expected_branch tip 과 다른 경우 (anchor 깨짐).
    """
    parent2 = _git("rev-parse", f"{merge_commit}^2")
    if parent2.returncode != 0:
        # fast-forward 또는 비-merge commit. revert 전략으로만 가능.
        _warn(
            f"merge_commit {merge_commit[:8]} 가 parent 가 1개입니다. "
            "fast-forward 머지로 보이며 reset 전략은 위험합니다. "
            "revert 전략 강제로 진행됩니다."
        )
        return

    parent2_sha = parent2.stdout.strip()
    if not expected_branch:
        # feature 브랜치가 이미 삭제되어 있는 정상 경로.
        _log(f"anchor 검증 스킵: feature 브랜치 미존재 (parent2={parent2_sha[:8]})")
        return

    fb_head = _git("rev-parse", expected_branch)
    if fb_head.returncode != 0:
        _log(
            f"anchor 검증 스킵: feature 브랜치 {expected_branch} 가 이미 삭제됨 "
            f"(parent2={parent2_sha[:8]})"
        )
        return

    fb_sha = fb_head.stdout.strip()
    if parent2_sha != fb_sha:
        _err(
            f"anchor 검증 실패: merge_commit^2 ({parent2_sha[:8]}) ≠ "
            f"{expected_branch} tip ({fb_sha[:8]}). "
            "다른 브랜치가 머지되었거나 history 가 변조되었을 가능성. 수동 조사 필요."
        )

    _log(f"anchor 검증 통과: parent2={parent2_sha[:8]} == {expected_branch} tip")


def _check_branch_worktree_clear(
    ticket_id: str, force: bool = False
) -> tuple[str | None, str | None]:
    """feature 브랜치 + worktree 가 점유 중이지 않은지 검사한다.

    Args:
        ticket_id: T-NNN 형식.
        force: True 이면 점유 중이어도 경고만 출력 (실제 정리 책임은 사용자).

    Returns:
        (existing_branch, existing_worktree_path) 튜플. 점유 없으면 (None, None).

    Raises:
        SystemExit: 점유 발견 + force=False.
    """
    existing_branch = get_feature_branch_for_ticket(ticket_id)
    existing_wt = get_worktree_path(ticket_id)

    if existing_branch is None and existing_wt is None:
        _log("브랜치/워크트리 점유 검사 통과 (둘 다 비어있음)")
        return (None, None)

    msg_parts = []
    if existing_branch:
        msg_parts.append(f"feature 브랜치 {existing_branch} 존재")
    if existing_wt:
        msg_parts.append(f"worktree {existing_wt} 존재")
    msg = ", ".join(msg_parts)

    if force:
        _warn(f"점유 발견 (force 통과): {msg}")
        return (existing_branch, existing_wt)

    _err(
        f"브랜치/워크트리 점유 감지 — {msg}. "
        "--force 로 진행 가능하나 충돌 가능성이 큽니다. "
        f"먼저 'git worktree remove' 와 'git branch -D {existing_branch}' 로 정리하세요."
    )
    return (existing_branch, existing_wt)  # 도달 불가 (방어용)


# ─── 푸시 여부 분기 (T2.3) ───────────────────────────────────────────────────


def _detect_push_state(merge_commit: str) -> PushState:
    """merge_commit 의 푸시 상태를 식별한다.

    `git branch -r --contains <merge_commit>` 출력을 파싱하여
    origin/develop / origin/main 매칭 여부로 분류한다.

    Args:
        merge_commit: 검사 대상 SHA.

    Returns:
        - "main": origin/main (또는 origin/master) 에 도달
        - "pushed": origin/develop 에만 도달
        - "local": origin/* 에 미도달
    """
    result = _git("branch", "-r", "--contains", merge_commit)
    if result.returncode != 0:
        _warn(
            f"git branch -r --contains 실패 — local 로 가정: {result.stderr.strip()}"
        )
        return "local"

    remote_refs = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    has_main = any(
        ref in ("origin/main", "origin/master") for ref in remote_refs
    )
    has_develop = "origin/develop" in remote_refs

    if has_main:
        _log(f"push state: main (refs={remote_refs})")
        return "main"
    if has_develop:
        _log(f"push state: pushed (refs={remote_refs})")
        return "pushed"

    _log(f"push state: local (refs 없음 또는 origin/* 비포함)")
    return "local"


def _has_followup_commits(merge_commit: str) -> bool:
    """develop 의 HEAD 가 merge_commit 보다 앞서있는지 (후속 commit 누적) 검사한다.

    `git rev-list develop ^merge_commit --count` > 0 이면 후속 commit 존재.

    Args:
        merge_commit: 기준 SHA.

    Returns:
        후속 commit 이 1개 이상이면 True.
    """
    result = _git("rev-list", "develop", f"^{merge_commit}", "--count")
    if result.returncode != 0:
        _warn(
            f"후속 commit 검사 실패 — 안전하게 True 반환: {result.stderr.strip()}"
        )
        return True
    try:
        count = int(result.stdout.strip())
    except ValueError:
        return True
    _log(f"후속 commit 수 (develop ^merge_commit): {count}")
    return count > 0


# ─── 전략 1: reset (T2.4) ───────────────────────────────────────────────────


def _strategy_reset(merge_commit: str, ticket_id: str) -> None:
    """develop 을 merge_commit 직전으로 reset --hard 한다.

    백업 reflog 마커(`refs/backup/undo-T-NNN`) 를 사전 작성하여
    잘못된 입력 시 복구 가능성을 남긴다.

    Args:
        merge_commit: 제거할 머지 커밋 SHA.
        ticket_id: T-NNN (백업 ref 이름에 사용).

    Raises:
        SystemExit: 후속 commit 누적 시 (자동 revert 분기 강제).
    """
    if _has_followup_commits(merge_commit):
        _err(
            "develop 에 후속 commit 이 누적되어 reset 전략을 사용할 수 없습니다 "
            "(데이터 유실 위험). revert 전략으로만 진행 가능 — "
            "푸시 여부와 무관하게 _strategy_revert 가 자동 호출되도록 main() 흐름이 보장합니다."
        )

    _log("전략 1: reset --hard 진행")

    # develop checkout
    _git("checkout", "develop", check=True)

    # 백업 reflog 마커
    backup_ref = f"refs/backup/undo-{ticket_id}"
    update_ref = _git(
        "update-ref",
        "-m",
        f"undo-done {ticket_id} backup before reset",
        backup_ref,
        "HEAD",
    )
    if update_ref.returncode == 0:
        _log(f"백업 ref 작성: {backup_ref} -> HEAD")
    else:
        _warn(
            f"백업 ref 작성 실패 (계속 진행): {update_ref.stderr.strip()}"
        )

    # reset --hard merge_commit^
    _git("reset", "--hard", f"{merge_commit}^", check=True)
    _log(f"develop reset 완료: HEAD = {merge_commit}^ (merge commit 제거)")


# ─── 전략 2: revert (T2.5) ──────────────────────────────────────────────────


def _strategy_revert(merge_commit: str) -> None:
    """develop 에 merge_commit 의 역방향 변경을 추가한다 (revert -m 1).

    Args:
        merge_commit: 되돌릴 머지 커밋 SHA.
    """
    _log("전략 2: revert -m 1 진행")

    _git("checkout", "develop", check=True)
    revert = _git(
        "revert", "-m", "1", "--no-edit", merge_commit
    )
    if revert.returncode != 0:
        # 충돌 시 abort
        _git("revert", "--abort")
        _err(
            f"revert 실패 — 충돌 또는 변경 없음일 수 있습니다: {revert.stderr.strip()}"
        )

    head = _git("rev-parse", "HEAD")
    new_head = head.stdout.strip() if head.returncode == 0 else "?"
    _log(f"revert 완료: 새 HEAD = {new_head[:8]}")


# ─── 워크트리 재생성 (T2.6) ─────────────────────────────────────────────────


def _recreate_worktree(ticket_id: str, ticket_file: str) -> WorktreeInfo:
    """worktree_manager.create_worktree() 로 feature 브랜치 + worktree 를 재생성한다.

    Args:
        ticket_id: T-NNN 형식.
        ticket_file: 티켓 XML 경로 (title 추출용).

    Returns:
        생성된 WorktreeInfo.

    Raises:
        SystemExit: 생성 실패 시.
    """
    ticket_data = parse_ticket_xml(ticket_file)
    title = ticket_data.get("title", "") or "untitled"

    _log(f"워크트리 재생성 시작: {ticket_id} (title={title!r})")
    info = create_worktree(ticket_id, title, command="implement")
    if info is None:
        _err(
            f"worktree 재생성 실패 ({ticket_id}). "
            "feature 브랜치 또는 디렉터리 점유 가능성. "
            "수동 정리 후 재시도하세요."
        )
    _log(f"워크트리 재생성 완료: path={info.path} branch={info.branch_name}")
    return info


# ─── 칸반 force 전이 (T2.7) ─────────────────────────────────────────────────


def _force_done_to_review(ticket_id: str, ticket_file: str) -> str:
    """티켓 XML 파일을 done/ -> review/ 로 이동하고 status 를 갱신한다.

    Args:
        ticket_id: T-NNN 형식.
        ticket_file: 현재 done/ 에 있는 티켓 파일 경로.

    Returns:
        이동 후 새 파일 경로.
    """
    _log(f"칸반 force 전이: Done → Review ({ticket_id})")

    # 1. XML <status> 를 Review 로 갱신 (파일은 아직 done/ 위치)
    update_ticket_status(ticket_file, "Review")
    _log(f"  XML <status> 갱신: Review")

    # 2. 파일을 review/ 디렉터리로 이동
    new_path = move_ticket_to_status_dir(ticket_file, "Review")
    _log(f"  파일 이동: {ticket_file} → {new_path}")

    return new_path


# ─── 사후 출력 (T2.8) ───────────────────────────────────────────────────────


def _print_postscript(ticket_id: str, worktree: WorktreeInfo) -> None:
    """git status / log + 다음 절차 안내를 출력한다."""
    _log("=" * 60)
    _log("롤백 완료 — 사후 상태")
    _log("=" * 60)

    status_result = _git("status", "--short", "--branch")
    if status_result.returncode == 0:
        _log("git status:")
        for line in status_result.stdout.rstrip().splitlines():
            print(f"  {line}", flush=True)

    log_result = _git("log", "--oneline", "-5")
    if log_result.returncode == 0:
        _log("git log (최근 5개):")
        for line in log_result.stdout.rstrip().splitlines():
            print(f"  {line}", flush=True)

    print("", flush=True)
    _log(f"다음 절차:")
    _log(f"  1. 워크트리로 이동: cd {worktree.path}")
    _log(f"     (feature 브랜치 {worktree.branch_name} 가 재생성되었습니다)")
    _log(f"  2. 티켓 편집:        /wf -e {ticket_id}")
    _log(f"  3. 워크플로우 재실행: /wf -s {ticket_id}")
    _log("")
    _log(
        f"칸반 상태: {ticket_id} 는 Review 컬럼으로 복귀했습니다. "
        "/wf -e 로 Open 강등 또는 직접 수정 후 /wf -d 로 재완료할 수 있습니다."
    )


# ─── main entry (T2.1) ──────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """argparse 진입점. flow-undo-done wrapper 가 호출한다.

    Args:
        argv: 테스트용 인자 리스트 (None 이면 sys.argv 사용).

    Returns:
        0 (성공) / 2 (실패; SystemExit 로 raise).
    """
    parser = argparse.ArgumentParser(
        prog="flow-undo-done",
        description=(
            "Done 처리된 워크플로우를 Review 단계로 자동 롤백합니다. "
            "develop 의 merge 결과를 reset 또는 revert 로 되돌리고, "
            "feature 브랜치 + worktree 를 재생성한 후, 칸반을 Done → Review 로 이동합니다."
        ),
        epilog=build_common_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "ticket",
        type=ticket_type,
        help="롤백할 Done 티켓 번호 (T-NNN, NNN, #N 형식).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "검증 단계에서 발견된 점유/누락 등을 경고로 격하시킵니다. "
            "merge_commit 누락 시 reflog fallback 도 활성화됩니다."
        ),
    )
    args = parser.parse_args(argv)
    ticket_id: str = args.ticket
    force: bool = args.force

    _log(f"=== Done 롤백 시작: {ticket_id} (force={force}) ===")

    # T2.2 — 사전 검증
    ticket_file = _validate_ticket_done(ticket_id)
    merge_commit = _load_merge_commit(ticket_id, ticket_file, force)

    # 기존 feature 브랜치 (있다면 anchor 검증에 사용)
    existing_branch = get_feature_branch_for_ticket(ticket_id) or ""
    _verify_merge_anchor(merge_commit, existing_branch)

    # 점유 검사
    _check_branch_worktree_clear(ticket_id, force=force)

    # T2.3 — 푸시 여부 분기
    push_state = _detect_push_state(merge_commit)
    has_followup = _has_followup_commits(merge_commit)

    if push_state == "main":
        if not force:
            _err(
                f"merge_commit {merge_commit[:8]} 가 origin/main 에 도달했습니다. "
                "main 직접 commit 룰 위반을 피하기 위해 reset 전략은 사용 불가, "
                "revert 전략만 가능합니다. 진행하려면 --force 를 명시하세요."
            )
        _log("main 도달 케이스 — revert 전략 강제 + force 동의 확인")
        _strategy_revert(merge_commit)
    elif push_state == "pushed" or has_followup:
        # 푸시되었거나 후속 commit 누적 시 revert 전략 강제 (force-push 회피 + 데이터 유실 방지)
        if push_state == "pushed":
            _log("origin/develop 도달 — revert 전략 (force-push 회피)")
        else:
            _log("후속 commit 누적 — revert 전략 (데이터 유실 방지)")
        _strategy_revert(merge_commit)
    else:
        # local-only + 후속 commit 없음 → reset 가능
        _log("local-only + 후속 commit 없음 — reset 전략")
        _strategy_reset(merge_commit, ticket_id)

    # T2.6 — 워크트리 재생성
    worktree = _recreate_worktree(ticket_id, ticket_file)

    # T2.7 — 칸반 force 전이 (Done → Review)
    _force_done_to_review(ticket_id, ticket_file)

    # T2.8 — 사후 출력
    _print_postscript(ticket_id, worktree)

    _log(f"=== Done 롤백 완료: {ticket_id} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
