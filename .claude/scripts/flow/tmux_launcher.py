#!/usr/bin/env -S python3 -u
"""tmux_launcher.py - tmux 윈도우 생성/정리 독립 스크립트.

기능:
  launch  - 지정된 티켓 ID로 새 tmux 윈도우를 생성하고 명령을 전송한다.
  cleanup - 지정된 티켓 ID의 tmux 윈도우를 종료한다.

사용법:
  flow-tmux launch  T-NNN '<command>'
  flow-tmux cleanup T-NNN

exit code:
  0 - 성공 (윈도우 생성 또는 기존 윈도우에 명령 전송 완료)
  1 - 에러 (폴링 타임아웃 등)
  2 - 인라인 실행 필요 (비tmux 환경 또는 재진입 감지)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

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


def _is_in_tmux() -> bool:
    """현재 프로세스가 tmux 세션 내에서 실행 중인지 확인한다.

    Returns:
        $TMUX 환경변수가 존재하면 True, 그렇지 않으면 False.
    """
    return bool(os.environ.get("TMUX"))


def _get_current_window_name() -> str:
    """현재 프로세스가 속한 tmux 윈도우 이름을 반환한다.

    TMUX_PANE 환경변수를 사용하여 프로세스가 실제로 실행 중인 pane의
    윈도우 이름을 조회한다. TMUX_PANE이 없으면 활성 윈도우 이름을 반환한다.

    Returns:
        현재 윈도우 이름 문자열. 실패 시 빈 문자열.
    """
    tmux_pane = os.environ.get("TMUX_PANE")
    if tmux_pane:
        result = _run_tmux("display-message", "-t", tmux_pane, "-p", "#W")
    else:
        result = _run_tmux("display-message", "-p", "#W")
    if result.returncode == 0:
        return result.stdout.strip()
    return ""


def _window_exists(window_name: str) -> bool:
    """지정된 이름의 tmux 윈도우가 존재하는지 확인한다.

    Args:
        window_name: 확인할 윈도우 이름

    Returns:
        윈도우가 존재하면 True, 그렇지 않으면 False.
    """
    result = _run_tmux("list-windows", "-F", "#W")
    if result.returncode != 0:
        return False
    existing_windows = result.stdout.strip().splitlines()
    return window_name in existing_windows


def _create_window(window_name: str) -> bool:
    """새 tmux 윈도우를 생성하고 claude를 실행한다.

    Args:
        window_name: 생성할 윈도우 이름

    Returns:
        성공 시 True, 실패 시 False.
    """
    result = _run_tmux(
        "new-window",
        "-d",
        "-n",
        window_name,
        "bash -lc 'unset CLAUDECODE && claude --dangerously-skip-permissions'",
        capture_output=False,
    )
    return result.returncode == 0


def _poll_for_prompt(window_name: str) -> bool:
    """tmux 윈도우에서 프롬프트 패턴이 나타날 때까지 폴링한다.

    Args:
        window_name: 폴링할 윈도우 이름

    Returns:
        프롬프트가 감지되면 True, 타임아웃이면 False.
    """
    for _ in range(_POLL_MAX_RETRIES):
        result = _run_tmux("capture-pane", "-t", window_name, "-p")
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
    result = _run_tmux("send-keys", "-t", window_name, command, "Enter", capture_output=False)
    return result.returncode == 0


def _kill_window(window_name: str) -> bool:
    """tmux 윈도우를 종료한다.

    Args:
        window_name: 종료할 윈도우 이름

    Returns:
        성공 시 True, 실패 시 False.
    """
    result = _run_tmux("kill-window", "-t", window_name, capture_output=False)
    return result.returncode == 0


def cmd_launch(ticket_id: str, command: str) -> int:
    """새 tmux 윈도우를 생성하고 명령을 전송한다.

    stdout 메시지로 결과를 전달한다:
      - "LAUNCH: ..." → 새 윈도우에서 실행 중
      - "INLINE: ..." → 인라인 실행 필요 (비tmux 또는 재진입)

    Args:
        ticket_id: 윈도우 이름으로 사용할 티켓 ID (예: T-001)
        command: tmux 윈도우에 전송할 명령 문자열

    Returns:
        exit code: 0=성공(LAUNCH 또는 INLINE), 1=에러
    """
    # 비tmux 환경: 인라인 실행 폴백 신호
    if not _is_in_tmux():
        print("INLINE: 비tmux 환경, 인라인 실행 필요")
        return 0

    # 재진입 감지: 현재 윈도우가 T- 로 시작하면 인라인 실행 폴백 신호
    current_window = _get_current_window_name()
    if current_window.startswith("T-"):
        print(f"INLINE: 재진입 감지 (현재 윈도우: {current_window}), 인라인 실행 필요")
        return 0

    window_already_exists = _window_exists(ticket_id)

    if not window_already_exists:
        # 새 윈도우 생성
        if not _create_window(ticket_id):
            print(f"[ERROR] {ticket_id} 윈도우 생성 실패", file=sys.stderr)
            return 1

        # 프롬프트 감지 폴링
        if not _poll_for_prompt(ticket_id):
            # 타임아웃: 윈도우 kill 후 에러 반환
            _kill_window(ticket_id)
            print(
                f"[ERROR] {ticket_id} 윈도우에서 {_POLL_MAX_RETRIES}초 내 프롬프트 미감지, 윈도우 종료",
                file=sys.stderr,
            )
            return 1

    # 명령 전송
    if not _send_keys(ticket_id, command):
        print(f"[ERROR] {ticket_id} 윈도우에 명령 전송 실패", file=sys.stderr)
        return 1

    print(f"LAUNCH: {ticket_id} 윈도우에서 실행 중")
    return 0


def cmd_cleanup(ticket_id: str) -> int:
    """tmux 윈도우를 종료한다. 윈도우가 없으면 멱등적으로 성공을 반환한다.

    Args:
        ticket_id: 종료할 윈도우 이름 (예: T-001)

    Returns:
        exit code: 항상 0 (멱등성 보장)
    """
    if _window_exists(ticket_id):
        _kill_window(ticket_id)
        print(f"{ticket_id} 윈도우 종료")
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
