#!/usr/bin/env -S python3 -u
"""chain_launcher.py - 체인 스테이지 비동기 tmux 발사 스크립트.

finalization.py에서 체인 감지 후 호출하는 독립 스크립트.
이전 tmux 윈도우 사망을 대기한 뒤, 다음 subnumber를 생성하고
새 tmux 윈도우에서 `/wf -s N` 명령을 전송한다.

사용법:
  python3 chain_launcher.py <ticket_number> <remaining_chain> <prev_report_path> [--retry-count <N>]

인자:
  ticket_number     T-NNN 형식 티켓 번호
  remaining_chain   남은 체인 문자열 (예: "implement>review")
  prev_report_path  이전 스테이지 report.md 절대 경로
  --retry-count     현재 재시도 횟수 (기본값: 0)

동작 순서:
  1. 이전 tmux 윈도우 사망 대기 (P:T-NNN 윈도우가 사라질 때까지 최대 30초 폴링)
  2. kanban.py add-subnumber 호출하여 다음 subnumber 자동 생성
  3. kanban.py move T-NNN open 호출하여 티켓을 Open 상태로 되돌림
  4. 새 tmux 윈도우 생성 + Claude 프롬프트 대기 + /wf -s N 명령 전송
  5. 실패 시 CHAIN_MAX_RETRY 횟수만큼 재시도

프로세스 모델:
  finalization.py에서 subprocess.Popen(start_new_session=True)로 백그라운드 실행.
  현재 프로세스(finalization.py)와 독립적으로 동작하여
  현재 tmux 윈도우 종료에 영향받지 않는다.

종료 코드:
  0  성공 (다음 스테이지 발사 완료)
  1  실패 (재시도 소진 또는 복구 불가 에러)
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

# ─── sys.path 보장 ──────────────────────────────────────────────────────────
_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR: str = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

_PROJECT_ROOT: str = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))

from data.constants import CHAIN_MAX_RETRY, CHAIN_SEPARATOR  # noqa: E402
from flow.tmux_utils import MAIN_WINDOW_DEFAULT, WINDOW_PREFIX_P  # noqa: E402

# ─── 경로 상수 ──────────────────────────────────────────────────────────────
KANBAN_PY: str = os.path.join(_SCRIPT_DIR, "kanban.py")
KANBAN_DIR: str = os.path.join(_PROJECT_ROOT, ".kanban")

# ─── 폴링 설정 ──────────────────────────────────────────────────────────────
_WINDOW_DEATH_POLL_INTERVAL: float = 1.0
_WINDOW_DEATH_POLL_MAX: int = 30
_PROMPT_POLL_INTERVAL: float = 1.0
_PROMPT_POLL_MAX: int = 30
_PROMPT_PATTERN: str = "\u276f"  # ❯


# ─── 로그 유틸 ──────────────────────────────────────────────────────────────

def _log(level: str, message: str) -> None:
    """stderr에 로그를 출력한다."""
    print(f"[{level}] chain_launcher: {message}", file=sys.stderr, flush=True)


# ─── tmux 유틸 ──────────────────────────────────────────────────────────────

def _run_tmux(*args: str) -> subprocess.CompletedProcess[str]:
    """tmux 명령을 실행하고 결과를 반환한다."""
    return subprocess.run(
        ["tmux"] + list(args),
        capture_output=True,
        text=True,
        timeout=10,
    )


def _window_exists(window_name: str) -> bool:
    """지정된 이름의 tmux 윈도우가 존재하는지 확인한다."""
    try:
        result = _run_tmux("list-windows", "-F", "#W")
        if result.returncode != 0:
            return False
        existing = result.stdout.strip().splitlines()
        return window_name in existing
    except Exception:
        return False


def _tmux_window_target(window_name: str) -> str:
    """콜론 포함 윈도우명을 인덱스 기반 타겟으로 변환한다."""
    try:
        result = _run_tmux("list-windows", "-F", "#{window_index}\t#{window_name}")
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                parts = line.split("\t", 1)
                if len(parts) == 2 and parts[1] == window_name:
                    return parts[0]
    except Exception:
        pass
    return window_name


def _wait_for_window_death(window_name: str) -> bool:
    """P:T-NNN 윈도우가 사라질 때까지 최대 30초 폴링한다.

    Args:
        window_name: 감시할 윈도우 이름 (P:T-NNN 형식)

    Returns:
        윈도우가 사라지면 True, 타임아웃이면 False.
    """
    for i in range(_WINDOW_DEATH_POLL_MAX):
        if not _window_exists(window_name):
            _log("INFO", f"window {window_name} is gone (after {i}s)")
            return True
        time.sleep(_WINDOW_DEATH_POLL_INTERVAL)
    _log("WARN", f"window {window_name} still exists after {_WINDOW_DEATH_POLL_MAX}s timeout")
    return False


def _create_window(window_name: str) -> bool:
    """새 tmux 윈도우를 생성하고 claude를 실행한다.

    tmux_launcher.py의 _create_window 로직을 재현한다.
    _WF_MAIN_WINDOW 환경변수를 주입하여 메인 윈도우 참조를 전달한다.

    Args:
        window_name: 생성할 윈도우 이름 (P:T-NNN 형식)

    Returns:
        성공 시 True, 실패 시 False.
    """
    try:
        result = _run_tmux(
            "new-window",
            "-d",
            "-n",
            window_name,
            "-e",
            f"_WF_MAIN_WINDOW={os.environ.get('_WF_MAIN_WINDOW', MAIN_WINDOW_DEFAULT)}",
            "bash -lc 'unset CLAUDECODE && claude --dangerously-skip-permissions'",
        )
        return result.returncode == 0
    except Exception as e:
        _log("ERROR", f"create_window failed: {e}")
        return False


def _poll_for_prompt(window_name: str) -> bool:
    """tmux 윈도우에서 프롬프트 패턴이 나타날 때까지 폴링한다.

    Args:
        window_name: 폴링할 윈도우 이름

    Returns:
        프롬프트가 감지되면 True, 타임아웃이면 False.
    """
    target = _tmux_window_target(window_name)
    for _ in range(_PROMPT_POLL_MAX):
        try:
            result = _run_tmux("capture-pane", "-t", target, "-p")
            if result.returncode == 0 and _PROMPT_PATTERN in result.stdout:
                return True
        except Exception:
            pass
        time.sleep(_PROMPT_POLL_INTERVAL)
    return False


def _send_keys(window_name: str, command: str) -> bool:
    """tmux 윈도우에 명령 키를 전송한다."""
    target = _tmux_window_target(window_name)
    try:
        result = _run_tmux("send-keys", "-t", target, command, "Enter")
        return result.returncode == 0
    except Exception as e:
        _log("ERROR", f"send_keys failed: {e}")
        return False


def _kill_window(window_name: str) -> bool:
    """tmux 윈도우를 종료한다."""
    target = _tmux_window_target(window_name)
    try:
        result = _run_tmux("kill-window", "-t", target)
        return result.returncode == 0
    except Exception:
        return False


# ─── 티켓 파싱 유틸 ─────────────────────────────────────────────────────────

def _read_previous_subnumber(ticket_number: str) -> dict[str, str]:
    """이전 subnumber에서 goal/target을 읽어 반환한다.

    kanban.py의 XML 파싱을 직접 수행하여
    현재 active subnumber의 prompt 필드(goal, target)를 추출한다.

    Args:
        ticket_number: T-NNN 형식 티켓 번호

    Returns:
        goal/target을 포함한 딕셔너리. 파싱 실패 시 빈 딕셔너리.
    """
    result: dict[str, str] = {}
    for subdir in ("", "done"):
        path = os.path.join(KANBAN_DIR, subdir, f"{ticket_number}.xml")
        if not os.path.isfile(path):
            continue
        try:
            tree = ET.parse(path)
            root = tree.getroot()

            # submit 내 active subnumber에서 prompt 필드 추출
            submit_elem = root.find("submit")
            if submit_elem is None:
                continue

            for sub in submit_elem.findall("subnumber"):
                if sub.get("active") == "true":
                    prompt_elem = sub.find("prompt")
                    if prompt_elem is not None:
                        goal_el = prompt_elem.find("goal")
                        target_el = prompt_elem.find("target")
                        if goal_el is not None and goal_el.text:
                            result["goal"] = goal_el.text.strip()
                        if target_el is not None and target_el.text:
                            result["target"] = target_el.text.strip()
                    break
        except Exception:
            continue
    return result


def _extract_ticket_number_int(ticket_number: str) -> str:
    """T-NNN에서 숫자 부분만 추출한다 (/wf -s N 명령에 사용)."""
    m = re.match(r"^T-(\d+)$", ticket_number, re.IGNORECASE)
    if m:
        return str(int(m.group(1)))
    return ticket_number


# ─── 메인 로직 ──────────────────────────────────────────────────────────────

def launch_next_stage(
    ticket_number: str,
    remaining_chain: str,
    prev_report_path: str,
    retry_count: int = 0,
) -> int:
    """다음 체인 스테이지를 발사한다.

    Args:
        ticket_number: T-NNN 형식 티켓 번호
        remaining_chain: 남은 체인 문자열 (예: "implement>review")
        prev_report_path: 이전 스테이지 report.md 절대 경로
        retry_count: 현재 재시도 횟수

    Returns:
        0=성공, 1=실패
    """
    window_name = f"{WINDOW_PREFIX_P}{ticket_number}"
    ticket_num_int = _extract_ticket_number_int(ticket_number)

    _log("INFO", f"ticket={ticket_number} remaining={remaining_chain} retry={retry_count}/{CHAIN_MAX_RETRY}")

    # ── Step 1: 이전 tmux 윈도우 사망 대기 ──
    _log("INFO", f"waiting for window {window_name} to die...")
    _wait_for_window_death(window_name)

    # ── Step 2: kanban.py add-subnumber 호출 ──
    # 이전 subnumber에서 goal/target 복사
    prev_data = _read_previous_subnumber(ticket_number)
    goal = prev_data.get("goal", "(체인 자동 생성)")
    target = prev_data.get("target", "(체인 자동 생성)")

    # context에 이전 스테이지 report 경로 주입
    context = f"이전 스테이지 report: {prev_report_path}"

    add_cmd = [
        "python3", KANBAN_PY, "add-subnumber", ticket_number,
        "--command", remaining_chain,
        "--goal", goal,
        "--target", target,
        "--context", context,
    ]

    _log("INFO", f"add-subnumber: command={remaining_chain}")
    try:
        result = subprocess.run(add_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            _log("ERROR", f"add-subnumber failed: exit {result.returncode} stderr={result.stderr.strip()}")
            return _handle_retry(ticket_number, remaining_chain, prev_report_path, retry_count)
        _log("INFO", f"add-subnumber ok: {result.stdout.strip()}")
    except Exception as e:
        _log("ERROR", f"add-subnumber exception: {e}")
        return _handle_retry(ticket_number, remaining_chain, prev_report_path, retry_count)

    # ── Step 3: kanban.py move T-NNN open (티켓을 Open 상태로 되돌림) ──
    move_cmd = ["python3", KANBAN_PY, "move", ticket_number, "open"]
    _log("INFO", f"move ticket to open")
    try:
        result = subprocess.run(move_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            stderr = result.stderr.strip()
            # "이미 Open 상태" 같은 경우는 무시
            _log("WARN", f"move open: exit {result.returncode} stderr={stderr}")
    except Exception as e:
        _log("WARN", f"move open exception: {e}")

    # ── Step 4: 새 tmux 윈도우 생성 + 프롬프트 대기 + /wf -s N 전송 ──
    _log("INFO", f"creating window {window_name}")

    if not _create_window(window_name):
        _log("ERROR", f"window creation failed: {window_name}")
        return _handle_retry(ticket_number, remaining_chain, prev_report_path, retry_count)

    _log("INFO", f"polling for prompt in {window_name}")
    if not _poll_for_prompt(window_name):
        _log("ERROR", f"prompt not detected in {window_name} after {_PROMPT_POLL_MAX}s")
        _kill_window(window_name)
        return _handle_retry(ticket_number, remaining_chain, prev_report_path, retry_count)

    # /wf -s N 명령 전송
    wf_command = f"/wf -s {ticket_num_int}"
    _log("INFO", f"sending command: {wf_command}")
    if not _send_keys(window_name, wf_command):
        _log("ERROR", f"send_keys failed for {window_name}")
        return _handle_retry(ticket_number, remaining_chain, prev_report_path, retry_count)

    _log("INFO", f"chain stage launched successfully: ticket={ticket_number} next={remaining_chain}")
    return 0


def _handle_retry(
    ticket_number: str,
    remaining_chain: str,
    prev_report_path: str,
    retry_count: int,
) -> int:
    """실패 시 재시도를 처리한다.

    CHAIN_MAX_RETRY 횟수만큼 자기 자신을 재귀 호출한다.

    Args:
        ticket_number: T-NNN 형식 티켓 번호
        remaining_chain: 남은 체인 문자열
        prev_report_path: 이전 스테이지 report.md 절대 경로
        retry_count: 현재 재시도 횟수

    Returns:
        0=재시도 성공, 1=재시도 소진
    """
    next_retry = retry_count + 1
    if next_retry > CHAIN_MAX_RETRY:
        _log("ERROR", f"max retry exceeded ({CHAIN_MAX_RETRY}), chain aborted: ticket={ticket_number}")
        return 1

    _log("WARN", f"retrying ({next_retry}/{CHAIN_MAX_RETRY}): ticket={ticket_number}")
    # 재시도 전 잠시 대기 (백오프)
    time.sleep(3)
    return launch_next_stage(ticket_number, remaining_chain, prev_report_path, next_retry)


# ─── CLI ────────────────────────────────────────────────────────────────────

def main() -> None:
    """CLI 진입점."""
    parser = argparse.ArgumentParser(
        prog="chain_launcher",
        description="체인 스테이지 비동기 tmux 발사 스크립트",
    )
    parser.add_argument("ticket_number", help="T-NNN 형식 티켓 번호")
    parser.add_argument("remaining_chain", help='남은 체인 문자열 (예: "implement>review")')
    parser.add_argument("prev_report_path", help="이전 스테이지 report.md 절대 경로")
    parser.add_argument("--retry-count", type=int, default=0, help="현재 재시도 횟수 (기본값: 0)")

    args = parser.parse_args()

    exit_code = launch_next_stage(
        ticket_number=args.ticket_number,
        remaining_chain=args.remaining_chain,
        prev_report_path=args.prev_report_path,
        retry_count=args.retry_count,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
