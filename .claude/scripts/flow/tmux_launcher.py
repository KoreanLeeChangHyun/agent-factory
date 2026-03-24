#!/usr/bin/env -S python3 -u
"""tmux_launcher.py - tmux 윈도우 생성/정리 독립 스크립트.

기능:
  launch  - 지정된 티켓 ID로 새 tmux 윈도우를 생성하고 명령을 전송한다.
            윈도우명은 P:T-NNN 형식으로 생성되며, _WF_MAIN_WINDOW 환경변수에 메인 윈도우명을 전달한다.
  cleanup - 지정된 티켓 ID의 tmux 윈도우를 종료한다.

사용법:
  flow-tmux launch  T-NNN '<command>'
  flow-tmux cleanup T-NNN

exit code:
  0 - 성공 (윈도우 생성 또는 기존 윈도우에 명령 전송 완료)
  1 - 에러 (폴링 타임아웃 등)
  2 - 인라인 실행 필요 (비tmux 환경 또는 재진입 감지)

NOTE: tmux -t 옵션에서 콜론(:)은 세션:윈도우 구분자로 해석되므로,
      P:T-NNN 형식 윈도우명은 인덱스 기반 타겟으로 변환하여 사용한다.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

# sys.path 보장: flow/ 패키지 import를 위해 scripts/ 디렉터리 추가
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from flow.tmux_utils import (  # noqa: E402
    get_current_window_name,
    WINDOW_PREFIX_P as _WINDOW_PREFIX_P,
    MAIN_WINDOW_DEFAULT,
)
from flow.flow_logger import append_log as _fl_append_log, resolve_work_dir_for_logging as _fl_resolve  # noqa: E402

# ─── 로깅 헬퍼 ───────────────────────────────────────────────────────────────

def _log(level: str, message: str) -> None:
    """workflow.log에 로그를 기록한다. abs_work_dir 해석 실패 시 조용히 건너뛴다."""
    try:
        work_dir = _fl_resolve()
        if work_dir:
            _fl_append_log(work_dir, level, message)
    except Exception:
        pass


# 폴링 설정
_POLL_INTERVAL_SECONDS: float = 1.0
_POLL_MAX_RETRIES: int = 30

# tmux 프롬프트 감지 패턴
_PROMPT_PATTERN: str = "❯"


def _run_tmux(*args: str, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    """tmux 명령을 실행하고 결과를 반환한다.

    Args:
        *args: tmux 명령 인자 목록
        capture_output: 출력 캡처 여부

    Returns:
        subprocess.CompletedProcess 인스턴스
    """
    cmd = ["tmux"] + list(args)
    return subprocess.run(
        cmd,
        capture_output=capture_output,
        text=True,
    )


def _tmux_window_target(window_name: str) -> str:
    """tmux -t 옵션에 사용할 안전한 윈도우 타겟 문자열을 반환한다.

    콜론(:)이 포함된 윈도우명(예: P:T-NNN)은 tmux가 '세션:윈도우'로 오해석하므로,
    list-windows로 윈도우 인덱스를 조회하여 인덱스 기반 타겟을 반환한다.

    Args:
        window_name: 타겟으로 사용할 윈도우 이름

    Returns:
        tmux -t 옵션에 전달할 타겟 문자열 (윈도우 인덱스 또는 폴백으로 원본 이름)
    """
    result = _run_tmux("list-windows", "-F", "#{window_index}\t#{window_name}")
    if result.returncode == 0:
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t", 1)
            if len(parts) == 2 and parts[1] == window_name:
                return parts[0]
    return window_name


def _is_in_tmux() -> bool:
    """현재 프로세스가 tmux 세션 내에서 실행 중인지 확인한다.

    Returns:
        $TMUX 환경변수가 존재하면 True, 그렇지 않으면 False.
    """
    return bool(os.environ.get("TMUX"))


def _get_current_window_name() -> str:
    """현재 프로세스가 속한 tmux 윈도우 이름을 반환한다.

    tmux_utils.get_current_window_name()에 위임한다.

    Returns:
        현재 윈도우 이름 문자열. 실패 시 빈 문자열.
    """
    return get_current_window_name()


def _window_exists(window_name: str) -> bool:
    """지정된 이름의 tmux 윈도우가 존재하는지 확인한다.

    Args:
        window_name: 확인할 윈도우 이름

    Returns:
        윈도우가 존재하면 True, 그렇지 않으면 False.
    """
    # list-windows -F 는 정확한 이름 비교이므로 콜론 이슈 없음
    result = _run_tmux("list-windows", "-F", "#W")
    if result.returncode != 0:
        return False
    existing_windows = result.stdout.strip().splitlines()
    return window_name in existing_windows


def _get_worktree_path() -> str | None:
    """현재 워크플로우의 worktree 경로를 반환한다.

    다음 순서로 경로를 결정한다:
    1. WORKFLOW_WORKTREE_PATH 환경변수
    2. .context.json의 worktree.absPath 필드

    경로가 존재하지 않으면 None을 반환한다.

    Returns:
        worktree 절대 경로 또는 None.
    """
    import json as _json

    # 1순위: 환경변수
    env_path = os.environ.get("WORKFLOW_WORKTREE_PATH", "").strip()
    if env_path and os.path.isdir(env_path):
        return env_path

    # 2순위: .context.json의 worktree.absPath
    try:
        work_dir = _fl_resolve()
        if work_dir:
            context_path = os.path.join(work_dir, ".context.json")
            if os.path.isfile(context_path):
                with open(context_path, "r", encoding="utf-8") as f:
                    ctx = _json.load(f)
                wt_info = ctx.get("worktree")
                if isinstance(wt_info, dict):
                    abs_path = wt_info.get("absPath", "")
                    if abs_path and os.path.isdir(abs_path):
                        return abs_path
    except Exception:
        pass

    return None


def _create_window(window_name: str) -> bool:
    """새 tmux 윈도우를 생성하고 claude를 실행한다.

    _WF_MAIN_WINDOW 환경변수에 메인 윈도우명을 전달한다.
    tmux new-window 에 -e 옵션으로 환경변수를 직접 주입하여 셸 이스케이프 문제를 방지한다.
    worktree 경로가 있으면 -c 옵션으로 cwd를 설정한다.

    Args:
        window_name: 생성할 윈도우 이름 (P:T-NNN 형식)

    Returns:
        성공 시 True, 실패 시 False.
    """
    worktree_path = _get_worktree_path()

    # tmux new-window 기본 인자
    tmux_args = [
        "new-window",
        "-d",
        "-n",
        window_name,
    ]

    # worktree_path가 있으면 -c <worktree_path>로 cwd 설정
    if worktree_path:
        tmux_args.extend(["-c", worktree_path])

    tmux_args.extend([
        "-e",
        f"_WF_MAIN_WINDOW={os.environ.get('_WF_MAIN_WINDOW', MAIN_WINDOW_DEFAULT)}",
        # WARNING: bash -lc 문자열에 변수를 직접 삽입하지 마시오 (셸 인젝션 위험)
        "bash -lc 'unset CLAUDECODE && claude --dangerously-skip-permissions'",
    ])

    result = _run_tmux(*tmux_args, capture_output=False)
    return result.returncode == 0


def _poll_for_prompt(window_name: str) -> bool:
    """tmux 윈도우에서 프롬프트 패턴이 나타날 때까지 폴링한다.

    Args:
        window_name: 폴링할 윈도우 이름

    Returns:
        프롬프트가 감지되면 True, 타임아웃이면 False.
    """
    target = _tmux_window_target(window_name)
    for _ in range(_POLL_MAX_RETRIES):
        result = _run_tmux("capture-pane", "-t", target, "-p")
        if result.returncode == 0 and _PROMPT_PATTERN in result.stdout:
            return True
        time.sleep(_POLL_INTERVAL_SECONDS)
    return False


def _send_keys(window_name: str, command: str) -> bool:
    """tmux 윈도우에 명령 키를 전송한다.

    Args:
        window_name: 명령을 전송할 윈도우 이름
        command: 전송할 명령 문자열

    Returns:
        성공 시 True, 실패 시 False.
    """
    target = _tmux_window_target(window_name)
    result = _run_tmux("send-keys", "-t", target, command, "Enter", capture_output=False)
    return result.returncode == 0


def _kill_window(window_name: str) -> bool:
    """tmux 윈도우를 종료한다.

    Args:
        window_name: 종료할 윈도우 이름

    Returns:
        성공 시 True, 실패 시 False.
    """
    target = _tmux_window_target(window_name)
    result = _run_tmux("kill-window", "-t", target, capture_output=False)
    return result.returncode == 0


def _rename_current_window(new_name: str) -> bool:
    """현재 프로세스가 속한 tmux 윈도우를 지정된 이름으로 리네임한다.

    TMUX_PANE 환경변수를 사용하여 현재 pane의 윈도우를 리네임한다.

    Args:
        new_name: 새 윈도우 이름

    Returns:
        성공 시 True, 실패 시 False.
    """
    tmux_pane = os.environ.get("TMUX_PANE", "")
    if tmux_pane:
        result = _run_tmux("rename-window", "-t", tmux_pane, new_name, capture_output=False)
    else:
        result = _run_tmux("rename-window", new_name, capture_output=False)
    return result.returncode == 0


def cmd_launch(ticket_id: str, command: str) -> int:
    """새 tmux 윈도우를 생성하고 명령을 전송한다.

    윈도우명은 P:T-NNN 형식으로 생성되며, _WF_MAIN_WINDOW 환경변수에 메인 윈도우명을 전달한다.

    stdout 메시지로 결과를 전달한다:
      - "LAUNCH: ..." → 새 윈도우에서 실행 중
      - "INLINE: ..." → 인라인 실행 필요 (비tmux 또는 재진입)

    Args:
        ticket_id: 티켓 ID (예: T-001). 내부적으로 P:T-NNN 형식 윈도우명으로 변환됨
        command: tmux 윈도우에 전송할 명령 문자열

    Returns:
        exit code: 0=성공(LAUNCH 또는 INLINE), 1=에러
    """
    _log("INFO", f"tmux_launcher: cmd_launch start ticket_id={ticket_id}")

    # 비tmux 환경: 인라인 실행 폴백 신호
    if not _is_in_tmux():
        print("INLINE: 비tmux 환경, 인라인 실행 필요")
        return 0

    # 재진입 감지: 현재 윈도우가 P:T- 로 시작하면 인라인 실행 폴백 신호
    current_window = _get_current_window_name()
    if current_window.startswith(_WINDOW_PREFIX_P + "T-"):
        print(f"INLINE: 재진입 감지 (현재 윈도우: {current_window}), 인라인 실행 필요")
        return 0

    # ticket_id(T-NNN)를 P:T-NNN 형식 윈도우명으로 변환
    window_name = f"{_WINDOW_PREFIX_P}{ticket_id}"

    window_already_exists = _window_exists(window_name)

    if not window_already_exists:
        # 새 윈도우 생성
        if not _create_window(window_name):
            _log("ERROR", f"tmux_launcher: window creation failed window={window_name}")
            print(f"[ERROR] {window_name} 윈도우 생성 실패", file=sys.stderr)
            return 1

        # 프롬프트 감지 폴링
        if not _poll_for_prompt(window_name):
            # 타임아웃: 윈도우 kill 후 에러 반환
            _kill_window(window_name)
            _log("ERROR", f"tmux_launcher: prompt not detected in {window_name} after {_POLL_MAX_RETRIES}s, window killed")
            print(
                f"[ERROR] {window_name} 윈도우에서 {_POLL_MAX_RETRIES}초 내 프롬프트 미감지, 윈도우 종료",
                file=sys.stderr,
            )
            return 1

    # 명령 전송
    if not _send_keys(window_name, command):
        print(f"[ERROR] {window_name} 윈도우에 명령 전송 실패", file=sys.stderr)
        return 1

    _log("INFO", f"tmux_launcher: cmd_launch complete window={window_name}")
    print(f"LAUNCH: {window_name} 윈도우에서 실행 중")
    return 0


def cmd_cleanup(ticket_id: str) -> int:
    """tmux 윈도우를 종료한다. 윈도우가 없으면 멱등적으로 성공을 반환한다.

    ticket_id(T-NNN)를 내부적으로 P:T-NNN 형식 윈도우명으로 변환한다.

    Args:
        ticket_id: 종료할 티켓 ID (예: T-001). 내부적으로 P:T-NNN 형식으로 변환됨

    Returns:
        exit code: 항상 0 (멱등성 보장)
    """
    _log("INFO", f"tmux_launcher: cmd_cleanup start ticket_id={ticket_id}")
    window_name = f"{_WINDOW_PREFIX_P}{ticket_id}"
    if _window_exists(window_name):
        _kill_window(window_name)
        print(f"{window_name} 윈도우 종료")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서를 생성한다.

    Returns:
        구성된 ArgumentParser 인스턴스
    """
    parser = argparse.ArgumentParser(
        prog="flow-tmux",
        description="tmux 윈도우 생성/정리 스크립트",
    )
    subparsers = parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    # launch 서브커맨드
    launch_parser = subparsers.add_parser(
        "launch",
        help="tmux 윈도우 생성 + 명령 전송",
    )
    launch_parser.add_argument("ticket_id", metavar="T-NNN", help="티켓 ID (윈도우 이름)")
    launch_parser.add_argument("command", metavar="COMMAND", help="전송할 명령 문자열")

    # cleanup 서브커맨드
    cleanup_parser = subparsers.add_parser(
        "cleanup",
        help="tmux 윈도우 종료",
    )
    cleanup_parser.add_argument("ticket_id", metavar="T-NNN", help="티켓 ID (윈도우 이름)")

    return parser


def main() -> None:
    """CLI 진입점. launch/cleanup 서브커맨드를 파싱하고 실행한다."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.subcommand is None:
        parser.print_usage()
        sys.exit(2)

    if args.subcommand == "launch":
        exit_code = cmd_launch(args.ticket_id, args.command)
    elif args.subcommand == "cleanup":
        exit_code = cmd_cleanup(args.ticket_id)
    else:
        parser.print_usage()
        exit_code = 2

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
