#!/usr/bin/env -S python3 -u
"""chain_launcher.py - 체인 스테이지 비동기 발사 스크립트.

finalization.py에서 체인 감지 후 호출하는 독립 스크립트.
이전 세션 종료를 대기한 뒤, 새 티켓을 생성하고
HTTP API 또는 tmux 윈도우를 통해 `/wf -s N` 명령을 전송한다.

실행 경로:
  - HTTP API 우선: _WF_SERVER_PORT 환경변수 또는 .board.url에서 포트 해석 가능 시
    POST /terminal/workflow/start + POST /terminal/workflow/input 으로 세션 시작
  - TMUX 폴백: 서버 포트 미해석 시 기존 tmux 윈도우 생성 방식으로 폴백

사용법:
  python3 chain_launcher.py <ticket_number> <remaining_chain> <prev_report_path> [--retry-count <N>]

인자:
  ticket_number     T-NNN 형식 티켓 번호
  remaining_chain   남은 체인 문자열 (예: "implement>review")
  prev_report_path  이전 스테이지 report.md 절대 경로
  --retry-count     현재 재시도 횟수 (기본값: 0)

동작 순서:
  1. 이전 세션 종료 대기 (HTTP: session status 폴링 / TMUX: 윈도우 사망 폴링, 최대 30초)
  2. kanban.py create로 새 티켓 생성 + kanban.py link로 derived-from 관계 링크 + update-prompt로 prompt 복사
  3. HTTP API로 세션 시작 + 명령 전송 (또는 TMUX 폴백: 윈도우 생성 + 프롬프트 대기 + 키 전송)
  4. 실패 시 CHAIN_MAX_RETRY 횟수만큼 재시도

프로세스 모델:
  finalization.py에서 subprocess.Popen(start_new_session=True)로 백그라운드 실행.
  현재 프로세스(finalization.py)와 독립적으로 동작하여
  현재 세션 종료에 영향받지 않는다.

로그 모델:
  스크립트 시작 시 _LOG_FILE 경로에 로그 파일을 생성한다. _log() 함수는
  stderr와 로그 파일 양쪽에 동시 출력하여 독립 프로세스 실행 시에도 로그가 보존된다.
  로그 파일 열기 실패 시에는 stderr 단독 출력으로 폴백한다.

종료 코드:
  0  성공 (다음 스테이지 발사 완료)
  1  실패 (재시도 소진 또는 복구 불가 에러)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import IO
from urllib.parse import urlparse

# ─── sys.path 보장 ──────────────────────────────────────────────────────────
_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR: str = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

_PROJECT_ROOT: str = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))

from constants import CHAIN_MAX_RETRY, CHAIN_SEPARATOR  # noqa: E402
from flow.session_identifier import WINDOW_PREFIX_P  # noqa: E402
from flow.flow_logger import append_log as _fl_append_log  # noqa: E402

# ─── 경로 상수 ──────────────────────────────────────────────────────────────
KANBAN_PY: str = os.path.join(_SCRIPT_DIR, "kanban.py")
KANBAN_DIR: str = os.path.join(_PROJECT_ROOT, ".claude-organic", "tickets")

# ─── 폴링 설정 ──────────────────────────────────────────────────────────────
_SESSION_EXIT_POLL_INTERVAL: float = 1.0
_SESSION_EXIT_POLL_MAX: int = 30

# ─── 로그 파일 설정 ──────────────────────────────────────────────────────────
_LOG_FILE: str = os.path.join(_PROJECT_ROOT, ".claude-organic", "runs", "chain_launcher.log")
_log_handle: IO[str] | None = None


def _init_log_file() -> None:
    """로그 파일 핸들을 초기화한다.

    _LOG_FILE 경로에 로그 파일을 append 모드로 열어 _log_handle에 설정한다.
    부모 디렉터리가 없으면 생성을 시도하고, 실패 시 stderr 단독 출력으로 폴백한다.
    """
    global _log_handle
    try:
        log_dir = os.path.dirname(_LOG_FILE)
        if log_dir and not os.path.isdir(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        _log_handle = open(_LOG_FILE, "a", encoding="utf-8")  # noqa: WPS515
    except Exception as e:
        print(f"[WARN] chain_launcher: failed to open log file {_LOG_FILE}: {e}", file=sys.stderr, flush=True)
        _log_handle = None


# ─── 로그 유틸 ──────────────────────────────────────────────────────────────

def _log(level: str, message: str) -> None:
    """stderr 및 로그 파일에 로그를 출력한다.

    _log_handle이 초기화되어 있으면 로그 파일에도 동시 기록하여
    독립 프로세스로 실행될 때에도 로그가 보존된다.
    """
    formatted: str = f"[{level}] chain_launcher: {message}"
    print(formatted, file=sys.stderr, flush=True)
    if _log_handle is not None:
        try:
            print(formatted, file=_log_handle, flush=True)
        except Exception:
            pass


# ─── workflow.log 헬퍼 ──────────────────────────────────────────────────────

_wf_work_dir: str | None = None  # prev_report_path에서 해석한 abs_work_dir


def _init_wf_log(prev_report_path: str) -> None:
    """prev_report_path의 상위 디렉터리에서 abs_work_dir을 추론하여 _wf_work_dir에 설정한다.

    chain_launcher.py는 finalization.py에서 백그라운드로 실행되므로
    WORKFLOW_WORK_DIR 환경변수가 없을 수 있다. prev_report_path를 통해
    abs_work_dir을 직접 추론한다.

    Args:
        prev_report_path: 이전 스테이지 report.md 절대 경로.
    """
    global _wf_work_dir
    try:
        # prev_report_path: <abs_work_dir>/report.md
        candidate = os.path.dirname(os.path.abspath(prev_report_path))
        if os.path.isdir(candidate) and os.path.exists(os.path.join(candidate, "status.json")):
            _wf_work_dir = candidate
            return
        # 1단계 상위 탐색 (report가 서브디렉터리에 있는 경우 폴백)
        candidate2 = os.path.dirname(candidate)
        if os.path.isdir(candidate2) and os.path.exists(os.path.join(candidate2, "status.json")):
            _wf_work_dir = candidate2
    except Exception:
        pass


def _wf_log(level: str, message: str) -> None:
    """workflow.log에 추가로 이벤트를 기록한다. 실패 시 조용히 건너뛴다."""
    try:
        if _wf_work_dir:
            _fl_append_log(_wf_work_dir, level, message)
    except Exception:
        pass


# ─── 서버 포트 해석 ────────────────────────────────────────────────────────

def _resolve_server_port() -> int | None:
    """`.board.url` 파일 또는 `_WF_SERVER_PORT` 환경변수에서 서버 포트를 추출한다.

    우선순위:
      1. ``_WF_SERVER_PORT`` 환경변수
      2. ``.claude-organic/.board.url`` 파일 첫 줄 URL 파싱

    Returns:
        포트 번호(int) 또는 None.
    """
    # 1) 환경변수 우선
    env_port = os.environ.get("_WF_SERVER_PORT", "").strip()
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass

    # 2) .board.url 파일 파싱
    url_file = os.path.join(_PROJECT_ROOT, ".claude-organic", ".board.url")
    if not os.path.isfile(url_file):
        return None

    try:
        with open(url_file, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
        if not first_line:
            return None
        parsed = urlparse(first_line)
        if parsed.port:
            return parsed.port
    except Exception:
        pass

    return None


# ─── HTTP 요청 헬퍼 ────────────────────────────────────────────────────────

def _http_request(
    method: str,
    port: int,
    path: str,
    body: dict | None = None,
) -> dict | list | None:
    """urllib.request 기반 JSON API 호출 래퍼.

    Args:
        method: HTTP 메서드 ("GET" 또는 "POST").
        port: 서버 포트 번호.
        path: 요청 경로 (예: ``/terminal/workflow/start``).
        body: POST 요청 시 JSON 본문 딕셔너리. GET 시 None.

    Returns:
        응답 JSON을 파싱한 결과. 오류 시 None.
    """
    url = f"http://127.0.0.1:{port}{path}"
    try:
        data = None
        headers: dict[str, str] = {}
        if method == "POST" and body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        _log("WARN", f"_http_request: {method} {path} HTTP {e.code}")
        return None
    except Exception as e:
        _log("WARN", f"_http_request: {method} {path} error: {e}")
        return None


# ─── 세션 상태 헬퍼 ────────────────────────────────────────────────────────

def _wait_for_session_exit(session_id: str, port: int) -> bool:
    """워크플로우 세션이 종료될 때까지 최대 30초 폴링한다.

    ``GET /terminal/workflow/status?session_id={id}`` 를 반복 호출하여
    status=="stopped" 이거나 404 응답이면 세션 종료로 판정한다.

    Args:
        session_id: 감시할 세션 ID.
        port: 서버 포트 번호.

    Returns:
        세션이 종료되면 True, 타임아웃이면 False.
    """
    for i in range(_SESSION_EXIT_POLL_MAX):
        resp = _http_request("GET", port, f"/terminal/workflow/status?session_id={session_id}")
        if resp is None:
            # 404 또는 네트워크 오류 → 세션 종료로 판정
            _log("INFO", f"session {session_id} is gone (after {i}s)")
            return True
        if isinstance(resp, dict) and resp.get("status") == "stopped":
            _log("INFO", f"session {session_id} stopped (after {i}s)")
            return True
        time.sleep(_SESSION_EXIT_POLL_INTERVAL)
    _log("WARN", f"session {session_id} still alive after {_SESSION_EXIT_POLL_MAX}s timeout")
    return False


def _start_workflow_session(port: int, ticket_id: str, command: str) -> str | None:
    """HTTP API를 통해 새 워크플로우 세션을 시작한다.

    ``POST /terminal/workflow/start`` 단일 호출로 세션을 생성한다.

    Args:
        port: 서버 포트 번호.
        ticket_id: 티켓 ID (예: T-001).
        command: 워크플로우 실행 명령 (예: "/wf -s 1").

    Returns:
        세션 ID 문자열, 실패 시 None.
    """
    resp = _http_request("POST", port, "/terminal/workflow/start", {
        "ticket": ticket_id,
        "command": command,
        "work_dir": "",
    })
    if isinstance(resp, dict) and resp.get("ok"):
        session_id = resp.get("session_id", "")
        _log("INFO", f"workflow session started: session_id={session_id} ticket={ticket_id}")
        return session_id if session_id else None
    if isinstance(resp, dict):
        _log("ERROR", f"workflow session start failed: {resp.get('error', 'unknown')}")
    return None


def _send_command(port: int, session_id: str, command: str) -> bool:
    """HTTP API를 통해 워크플로우 세션에 명령을 전송한다.

    ``POST /terminal/workflow/input`` 호출로 stdin에 텍스트를 전송한다.

    Args:
        port: 서버 포트 번호.
        session_id: 대상 세션 ID.
        command: 전송할 명령 문자열.

    Returns:
        성공 시 True, 실패 시 False.
    """
    resp = _http_request("POST", port, "/terminal/workflow/input", {
        "session_id": session_id,
        "text": command,
    })
    if isinstance(resp, dict) and resp.get("ok"):
        _log("INFO", f"command sent to session {session_id}: {command}")
        return True
    _log("ERROR", f"send_command failed for session {session_id}")
    return False


def _kill_session(port: int, session_id: str) -> bool:
    """HTTP API를 통해 워크플로우 세션을 종료한다.

    ``POST /terminal/workflow/kill`` 호출로 세션을 강제 종료한다.

    Args:
        port: 서버 포트 번호.
        session_id: 종료할 세션 ID.

    Returns:
        성공 시 True, 실패 시 False.
    """
    resp = _http_request("POST", port, "/terminal/workflow/kill", {
        "session_id": session_id,
    })
    if isinstance(resp, dict) and resp.get("ok"):
        _log("INFO", f"session {session_id} killed")
        return True
    _log("WARN", f"session {session_id} kill failed or already gone")
    return False


# ─── TMUX 폴백 유틸 (서버 미기동 시 하위호환) ───────────────────────────────

def _run_tmux(*args: str) -> subprocess.CompletedProcess[str]:
    """tmux 명령을 실행하고 결과를 반환한다. (폴백 전용)"""
    return subprocess.run(
        ["tmux"] + list(args),
        capture_output=True,
        text=True,
        timeout=10,
    )


def _tmux_window_exists(window_name: str) -> bool:
    """지정된 이름의 tmux 윈도우가 존재하는지 확인한다. (폴백 전용)"""
    try:
        result = _run_tmux("list-windows", "-F", "#W")
        if result.returncode != 0:
            return False
        existing = result.stdout.strip().splitlines()
        return window_name in existing
    except Exception:
        return False


def _tmux_window_target(window_name: str) -> str:
    """콜론 포함 윈도우명을 인덱스 기반 타겟으로 변환한다. (폴백 전용)"""
    try:
        result = _run_tmux("list-windows", "-F", "#{window_index}\t#{window_name}")
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                parts = line.split("\t", 1)
                if len(parts) == 2 and parts[1] == window_name:
                    return parts[0]
    except Exception:
        pass
    if ":" in window_name:
        _log("WARN", f"_tmux_window_target: failed to resolve index for '{window_name}', returning empty")
        return ""
    return window_name


def _tmux_wait_for_window_death(window_name: str) -> bool:
    """P:T-NNN 윈도우가 사라질 때까지 최대 30초 폴링한다. (폴백 전용)"""
    for i in range(_SESSION_EXIT_POLL_MAX):
        if not _tmux_window_exists(window_name):
            _log("INFO", f"window {window_name} is gone (after {i}s)")
            return True
        time.sleep(_SESSION_EXIT_POLL_INTERVAL)
    _log("WARN", f"window {window_name} still exists after {_SESSION_EXIT_POLL_MAX}s timeout")
    return False


def _tmux_kill_window(window_name: str) -> bool:
    """tmux 윈도우를 종료한다. (폴백 전용)"""
    target = _tmux_window_target(window_name)
    if not target:
        _log("WARN", f"_tmux_kill_window: invalid target for '{window_name}', skipping")
        return False
    try:
        result = _run_tmux("kill-window", "-t", target)
        return result.returncode == 0
    except Exception:
        return False


def _tmux_create_window(window_name: str) -> bool:
    """새 tmux 윈도우를 생성하고 claude를 실행한다. (폴백 전용)"""
    from flow.session_identifier import MAIN_WINDOW_DEFAULT

    worktree_path = _get_worktree_path()
    tmux_args = ["new-window", "-d", "-n", window_name]
    if worktree_path:
        tmux_args.extend(["-c", worktree_path])
    tmux_args.extend(["-e", f"_WF_MAIN_WINDOW={os.environ.get('_WF_MAIN_WINDOW', MAIN_WINDOW_DEFAULT)}"])
    if worktree_path:
        tmux_args.extend(["-e", f"WORKFLOW_WORKTREE_PATH={worktree_path}"])
    if _wf_work_dir:
        tmux_args.extend(["-e", f"WORKFLOW_WORK_DIR={_wf_work_dir}"])
    tmux_args.append("bash -lc 'unset CLAUDECODE && claude --dangerously-skip-permissions'")

    try:
        result = _run_tmux(*tmux_args)
        return result.returncode == 0
    except Exception as e:
        _log("ERROR", f"tmux create_window failed: {e}")
        return False


def _tmux_poll_for_prompt(window_name: str) -> bool:
    """tmux 윈도우에서 프롬프트 패턴이 나타날 때까지 폴링한다. (폴백 전용)"""
    _PROMPT_PATTERN = "\u276f"  # ❯
    _PROMPT_POLL_MAX = 30
    _PROMPT_POLL_INTERVAL = 1.0
    target = _tmux_window_target(window_name)
    if not target:
        _log("ERROR", f"_tmux_poll_for_prompt: invalid target for '{window_name}'")
        return False
    for _ in range(_PROMPT_POLL_MAX):
        try:
            result = _run_tmux("capture-pane", "-t", target, "-p")
            if result.returncode == 0 and _PROMPT_PATTERN in result.stdout:
                return True
        except Exception:
            pass
        time.sleep(_PROMPT_POLL_INTERVAL)
    return False


def _tmux_send_keys(window_name: str, command: str) -> bool:
    """tmux 윈도우에 명령 키를 전송한다. (폴백 전용)"""
    target = _tmux_window_target(window_name)
    if not target:
        _log("ERROR", f"_tmux_send_keys: invalid target for '{window_name}'")
        return False
    try:
        result = _run_tmux("send-keys", "-t", target, command, "Enter")
        return result.returncode == 0
    except Exception as e:
        _log("ERROR", f"tmux send_keys failed: {e}")
        return False


def _get_worktree_path() -> str | None:
    """현재 워크플로우의 worktree 경로를 반환한다.

    다음 순서로 경로를 결정한다:
    1. WORKFLOW_WORKTREE_PATH 환경변수
    2. _wf_work_dir에서 해석한 .context.json의 worktree.absPath 필드

    경로가 존재하지 않으면 None을 반환한다.

    Returns:
        worktree 절대 경로 또는 None.
    """
    import json as _json

    # 1순위: 환경변수
    env_path = os.environ.get("WORKFLOW_WORKTREE_PATH", "").strip()
    if env_path and os.path.isdir(env_path):
        return env_path

    # 2순위: _wf_work_dir의 .context.json에서 worktree.absPath 읽기
    try:
        if _wf_work_dir:
            context_path = os.path.join(_wf_work_dir, ".context.json")
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


# ─── 티켓 파싱 유틸 ─────────────────────────────────────────────────────────

def _read_previous_prompt(ticket_number: str) -> dict[str, str]:
    """티켓 XML에서 prompt의 goal/target을 읽어 반환한다.

    flat 구조의 티켓 XML에서 루트 직하 <prompt> 요소의
    <goal>, <target> 필드를 직접 추출한다.

    레거시 폴백: <submit> 래퍼가 존재하면 기존 subnumber 구조로 파싱한다.

    Args:
        ticket_number: T-NNN 형식 티켓 번호

    Returns:
        goal/target을 포함한 딕셔너리. 파싱 실패 시 빈 딕셔너리.
    """
    result: dict[str, str] = {}
    for subdir in ("open", "progress", "review", "done"):
        path = os.path.join(KANBAN_DIR, subdir, f"{ticket_number}.xml")
        if not os.path.isfile(path):
            continue
        try:
            tree = ET.parse(path)
            root = tree.getroot()

            # 레거시 폴백: <submit> 래퍼가 존재하면 기존 subnumber 구조로 파싱
            submit_elem = root.find("submit")
            if submit_elem is not None:
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
                return result

            # flat 구조: 루트 직하 <prompt> 요소에서 직접 추출
            prompt_elem = root.find("prompt")
            if prompt_elem is not None:
                goal_el = prompt_elem.find("goal")
                target_el = prompt_elem.find("target")
                if goal_el is not None and goal_el.text:
                    result["goal"] = goal_el.text.strip()
                if target_el is not None and target_el.text:
                    result["target"] = target_el.text.strip()
            return result
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

    HTTP API 우선 경로와 TMUX 폴백 경로를 지원한다.
    서버 포트를 해석할 수 있으면 HTTP API 경로로 진행하고,
    해석 불가 시 기존 tmux 폴백 경로로 진행한다.

    실패 시 while 루프로 CHAIN_MAX_RETRY 횟수만큼 재시도한다.

    Args:
        ticket_number: T-NNN 형식 티켓 번호
        remaining_chain: 남은 체인 문자열 (예: "implement>review")
        prev_report_path: 이전 스테이지 report.md 절대 경로
        retry_count: 시작 재시도 횟수 (기본값 0)

    Returns:
        0=성공, 1=실패
    """
    _wf_log("INFO", f"chain_launcher: launch_next_stage start ticket={ticket_number} remaining={remaining_chain}")

    # 서버 포트 해석: HTTP API 경로 또는 TMUX 폴백 결정
    port = _resolve_server_port()
    use_http = port is not None

    if use_http:
        _log("INFO", f"using HTTP API path (port={port})")
    else:
        _log("INFO", "using TMUX fallback path (server port not resolved)")

    # 이전 세션 식별: HTTP 경로에서는 _WF_SESSION_ID 환경변수, TMUX 경로에서는 윈도우명
    prev_session_id = os.environ.get("_WF_SESSION_ID", "").strip()
    window_name = f"{WINDOW_PREFIX_P}{ticket_number}"

    current_retry: int = retry_count
    _new_ticket_created: bool = False
    new_ticket_number: str = ""
    new_ticket_num_int: str = ""
    while current_retry <= CHAIN_MAX_RETRY:
        _log("INFO", f"ticket={ticket_number} remaining={remaining_chain} retry={current_retry}/{CHAIN_MAX_RETRY}")

        # ── Step 1: 이전 세션 종료 대기 ──
        if use_http and prev_session_id:
            _log("INFO", f"waiting for session {prev_session_id} to exit...")
            session_gone: bool = _wait_for_session_exit(prev_session_id, port)
            if not session_gone:
                _log("WARN", f"session {prev_session_id} still alive after timeout, force killing")
                _kill_session(port, prev_session_id)
                time.sleep(1)
        else:
            # TMUX 폴백: 윈도우 사망 대기
            _log("INFO", f"waiting for window {window_name} to die...")
            window_gone: bool = _tmux_wait_for_window_death(window_name)
            if not window_gone:
                _log("WARN", f"window {window_name} still alive after timeout, force killing")
                _tmux_kill_window(window_name)
                time.sleep(1)

        # ── Step 2: 새 티켓 생성 + 관계 링크 + prompt 복사 (경로 무관, 동일 로직) ──
        if not _new_ticket_created:
            # 이전 티켓에서 goal/target 복사
            prev_data = _read_previous_prompt(ticket_number)
            goal = prev_data.get("goal", "(체인 자동 생성)")
            target = prev_data.get("target", "(체인 자동 생성)")

            # context에 이전 스테이지 report 경로 주입
            context = f"이전 스테이지 report: {prev_report_path}"

            # Step 2a: 새 티켓 생성
            create_cmd = [
                "python3", KANBAN_PY, "create", f"[chain] {goal[:40]}",
                "--command", remaining_chain,
            ]

            _log("INFO", f"create new ticket: command={remaining_chain}")
            try:
                result = subprocess.run(create_cmd, capture_output=True, text=True, timeout=30)
                if result.returncode != 0:
                    _log("ERROR", f"create ticket failed: exit {result.returncode} stderr={result.stderr.strip()}")
                    current_retry, should_continue = _increment_retry(current_retry, ticket_number)
                    if should_continue:
                        continue
                    break
                # stdout에서 새 티켓 번호 파싱: "T-NNN: 제목" 형식
                stdout_text = result.stdout.strip()
                _log("INFO", f"create ticket ok: {stdout_text}")
                ticket_match = re.match(r"(T-\d+):", stdout_text)
                if not ticket_match:
                    _log("ERROR", f"failed to parse new ticket number from stdout: {stdout_text}")
                    current_retry, should_continue = _increment_retry(current_retry, ticket_number)
                    if should_continue:
                        continue
                    break
                new_ticket_number = ticket_match.group(1)
                new_ticket_num_int = _extract_ticket_number_int(new_ticket_number)
                _log("INFO", f"new ticket created: {new_ticket_number}")
            except Exception as e:
                _log("ERROR", f"create ticket exception: {e}")
                current_retry, should_continue = _increment_retry(current_retry, ticket_number)
                if should_continue:
                    continue
                break

            # Step 2b: 관계 링크 (derived-from)
            link_cmd = [
                "python3", KANBAN_PY, "link", new_ticket_number,
                "--derived-from", ticket_number,
            ]
            _log("INFO", f"link {new_ticket_number} --derived-from {ticket_number}")
            try:
                result = subprocess.run(link_cmd, capture_output=True, text=True, timeout=30)
                if result.returncode != 0:
                    _log("WARN", f"link failed: exit {result.returncode} stderr={result.stderr.strip()}")
                    # 링크 실패는 치명적이지 않으므로 계속 진행
            except Exception as e:
                _log("WARN", f"link exception: {e}")

            # Step 2c: prompt 복사 (goal, target, context)
            prompt_cmd = [
                "python3", KANBAN_PY, "update-prompt", new_ticket_number,
                "--goal", goal,
                "--target", target,
                "--context", context,
                "--skip-validation",
            ]
            _log("INFO", f"update-prompt for {new_ticket_number}")
            try:
                result = subprocess.run(prompt_cmd, capture_output=True, text=True, timeout=30)
                if result.returncode != 0:
                    _log("WARN", f"update-prompt failed: exit {result.returncode} stderr={result.stderr.strip()}")
            except Exception as e:
                _log("WARN", f"update-prompt exception: {e}")

            _new_ticket_created = True
        else:
            _log("INFO", "new ticket already created, skipping")

        # ── Step 3: 새 세션 시작 + 명령 전송 ──
        wf_command = f"/wf -s {new_ticket_num_int}"

        if use_http:
            # HTTP API 경로: _start_workflow_session (server.py가 command를 자동 주입)
            # _send_command()는 호출하지 않는다 — server.py /terminal/workflow/start 가
            # spawn 직후 send_input(command)를 실행하므로 여기서 추가 전송하면 이중 전송이 된다.
            _log("INFO", f"starting workflow session for {new_ticket_number} via HTTP API")
            session_id = _start_workflow_session(port, new_ticket_number, wf_command)
            if not session_id:
                _log("ERROR", f"workflow session start failed for {new_ticket_number}")
                _wf_log("ERROR", f"chain_launcher: http session start failed ticket={new_ticket_number}")
                current_retry, should_continue = _increment_retry(current_retry, ticket_number)
                if should_continue:
                    continue
                break

            _log("INFO", f"chain stage launched via HTTP: prev={ticket_number} new={new_ticket_number} session={session_id}")
            _wf_log("INFO", f"chain_launcher: launch_next_stage complete (http) prev={ticket_number} new={new_ticket_number} session={session_id}")
            return 0

        else:
            # TMUX 폴백 경로: 기존 윈도우 생성 + 프롬프트 대기 + 키 전송
            new_window_name = f"{WINDOW_PREFIX_P}{new_ticket_number}"
            _log("INFO", f"creating tmux window {new_window_name} (fallback)")

            if not _tmux_create_window(new_window_name):
                _log("ERROR", f"tmux window creation failed: {new_window_name}")
                _wf_log("ERROR", f"chain_launcher: tmux window creation failed window={new_window_name}")
                current_retry, should_continue = _increment_retry(current_retry, ticket_number)
                if should_continue:
                    continue
                break

            _log("INFO", f"polling for prompt in {new_window_name}")
            if not _tmux_poll_for_prompt(new_window_name):
                _log("ERROR", f"prompt not detected in {new_window_name} after timeout")
                _wf_log("ERROR", f"chain_launcher: prompt not detected window={new_window_name}")
                _tmux_kill_window(new_window_name)
                current_retry, should_continue = _increment_retry(current_retry, ticket_number)
                if should_continue:
                    continue
                break

            _log("INFO", f"sending command: {wf_command}")
            if not _tmux_send_keys(new_window_name, wf_command):
                _log("ERROR", f"tmux send_keys failed for {new_window_name}")
                current_retry, should_continue = _increment_retry(current_retry, ticket_number)
                if should_continue:
                    continue
                break

            _log("INFO", f"chain stage launched via tmux: prev={ticket_number} new={new_ticket_number}")
            _wf_log("INFO", f"chain_launcher: launch_next_stage complete (tmux) prev={ticket_number} new={new_ticket_number}")
            return 0

    # 루프 탈출: 재시도 소진
    fallback_num = new_ticket_num_int if new_ticket_num_int else _extract_ticket_number_int(ticket_number)
    _log("ERROR", f"max retry exceeded ({CHAIN_MAX_RETRY}), chain aborted: ticket={ticket_number}")
    _log("ERROR", f"수동으로 다음 스테이지를 시작하려면: /wf -s {fallback_num}")
    _wf_log("ERROR", f"chain_launcher: launch_next_stage failed max_retry_exceeded ticket={ticket_number}")
    return 1


def _increment_retry(current_retry: int, ticket_number: str) -> tuple[int, bool]:
    """재시도 횟수를 증가시키고, 계속 시도 가능 여부를 반환한다.

    Args:
        current_retry: 현재 재시도 횟수
        ticket_number: 로그 출력용 티켓 번호

    Returns:
        (next_retry, should_continue) 튜플.
        should_continue가 False이면 루프를 탈출해야 한다.
    """
    next_retry = current_retry + 1
    if next_retry > CHAIN_MAX_RETRY:
        return next_retry, False
    _log("WARN", f"retrying ({next_retry}/{CHAIN_MAX_RETRY}): ticket={ticket_number}")
    # 재시도 전 잠시 대기 (백오프)
    time.sleep(3)
    return next_retry, True


# ─── CLI ────────────────────────────────────────────────────────────────────

def main() -> None:
    """CLI 진입점."""
    # 로그 파일 초기화: 독립 프로세스 실행 시에도 로그가 파일에 보존된다
    _init_log_file()

    parser = argparse.ArgumentParser(
        prog="chain_launcher",
        description="체인 스테이지 비동기 발사 스크립트 (HTTP API 우선, TMUX 폴백)",
    )
    parser.add_argument("ticket_number", help="T-NNN 형식 티켓 번호")
    parser.add_argument("remaining_chain", help='남은 체인 문자열 (예: "implement>review")')
    parser.add_argument("prev_report_path", help="이전 스테이지 report.md 절대 경로")
    parser.add_argument("--retry-count", type=int, default=0, help="현재 재시도 횟수 (기본값: 0)")

    args = parser.parse_args()

    # workflow.log 헬퍼 초기화 (prev_report_path에서 abs_work_dir 추론)
    _init_wf_log(args.prev_report_path)

    exit_code = launch_next_stage(
        ticket_number=args.ticket_number,
        remaining_chain=args.remaining_chain,
        prev_report_path=args.prev_report_path,
        retry_count=args.retry_count,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
