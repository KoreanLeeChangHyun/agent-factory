#!/usr/bin/env -S python3 -u
"""stop.py - 워크플로우 강제 중지 진입점 (T-904).

이 모듈은 Board UI [중지] 버튼 / CLI `flow-stop` / launcher timeout fallback
세 진입점이 모두 호출하는 단일 함수 `stop_workflow()` 를 제공한다.

W01 단계 책임:
  - 함수 시그니처 및 반환 dict 골격 정의
  - PID 트리 수집 (`pgrep -P` 재귀 + `/proc/<pid>/task/<tid>/children` 폴백)
  - SIGTERM → poll(0.1s × 30) → SIGKILL escalation
  - `sessions.get_sessions()` 재사용 (활성 세션 자동 감지)

W02 단계 책임:
  - jsonl `process_exit` 마커 append (kill 후 0.2s flush 대기)
  - sessions.py `_parse_jsonl_status` 가 `stopped_by_flow_stop` 도 인식

W03 단계 책임 (본 파일에 추가):
  - 칸반 In Progress → Open 자동 전이 (`flow-kanban move T-NNN open`)
  - 워크트리 정리는 `cmd_move` 내부 `_cleanup_worktree_on_leave` 가 자동 수행
  - 호출 순서 강제 (Decision A): PID wait 완료 → jsonl 마커 → 칸반 전이
  - `kanban_transition`, `worktree_action` 필드 실제 값으로 채움

후속 W04 에서 추가될 책임:
  - argparse CLI 진입점 (`if __name__ == "__main__":`)

설계 결정 (plan.md Decision A/B 참조):
  - PID 트리 수집은 Linux 한정 — `pgrep -P` 재귀, 실패 시 `/proc/<pid>/task/<tid>/children` 폴백
  - leaves → root 순으로 SIGTERM (자식 먼저 정리하여 좀비 회피)
  - escalation: 0.1s × 30 = 3s 폴링, 미종료 시 SIGKILL
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

# sys.path 보장: flow/ 패키지 import를 위해 engine/ 디렉터리 추가
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ENGINE_DIR = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from flow.sessions import (  # noqa: E402
    _SESSIONS_DIR,
    _resolve_server_port,
    _is_server_running,
    get_sessions,
)


# ---------------------------------------------------------------------------
# 경로 상수
# ---------------------------------------------------------------------------

# .claude-organic/ 루트
_WF_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", ".."))
# .claude-organic/bin/ 디렉터리 (W03 에서 flow-kanban 호출 시 사용)
_BIN_DIR = os.path.join(_WF_ROOT, "bin")
# 프로젝트 루트 (.claude-organic/ 의 부모)
_PROJECT_ROOT = os.path.normpath(os.path.join(_WF_ROOT, ".."))


# ---------------------------------------------------------------------------
# PID 트리 수집
# ---------------------------------------------------------------------------

def _collect_children_via_pgrep(pid: int) -> list[int]:
    """`pgrep -P <pid>` 로 직접 자식 PID 목록을 수집한다.

    pgrep 미설치 또는 자식 없음 시 빈 리스트.
    """
    try:
        result = subprocess.run(
            ["pgrep", "-P", str(pid)],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if result.returncode not in (0, 1):
        # 0 = 매치 있음, 1 = 매치 없음. 그 외는 비정상
        return []
    children = []
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            children.append(int(line))
        except ValueError:
            continue
    return children


def _collect_children_via_proc(pid: int) -> list[int]:
    """`/proc/<pid>/task/<tid>/children` 폴백으로 자식 PID 를 수집한다.

    Linux 한정. `/proc` 미존재 또는 권한 없음 시 빈 리스트.
    """
    children: list[int] = []
    task_dir = f"/proc/{pid}/task"
    if not os.path.isdir(task_dir):
        return []
    try:
        tids = os.listdir(task_dir)
    except OSError:
        return []
    for tid in tids:
        children_file = os.path.join(task_dir, tid, "children")
        try:
            with open(children_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except (IOError, OSError):
            continue
        for token in content.split():
            try:
                children.append(int(token))
            except ValueError:
                continue
    # 중복 제거 (여러 thread 가 동일 자식을 보고할 수 있음)
    return sorted(set(children))


def _collect_pid_tree(root_pid: int) -> list[int]:
    """root_pid 부터 모든 자손 PID 를 BFS 로 수집한다.

    반환 순서: leaves → root (SIGTERM 시 자식부터 정리하기 위함).
    `pgrep -P` 우선, 실패 시 `/proc` 폴백, 둘 다 실패 시 root 만 반환.
    """
    visited: set[int] = set()
    order: list[int] = []  # BFS 순서 (root, level1, level2, ...)
    queue: list[int] = [root_pid]
    while queue:
        pid = queue.pop(0)
        if pid in visited:
            continue
        visited.add(pid)
        order.append(pid)
        # 자식 수집: pgrep 우선, 폴백 /proc
        children = _collect_children_via_pgrep(pid)
        if not children:
            children = _collect_children_via_proc(pid)
        for child in children:
            if child not in visited:
                queue.append(child)
    # leaves → root 순으로 뒤집어 반환 (자식 먼저 SIGTERM)
    return list(reversed(order))


# ---------------------------------------------------------------------------
# PID 종료 확인
# ---------------------------------------------------------------------------

def _pid_alive(pid: int) -> bool:
    """PID 가 살아있는지 확인한다.

    `/proc/<pid>` 가 존재하더라도 `State: Z (zombie)` 인 경우 종료된 것으로 간주.
    좀비는 부모가 wait()/reap 하지 않아 잠시 남아있는 상태로, 시그널 응답 불가.
    """
    proc_dir = f"/proc/{pid}"
    if not os.path.isdir(proc_dir):
        return False
    # 좀비 상태 검사: /proc/<pid>/status 의 State 필드 확인
    try:
        with open(f"{proc_dir}/status", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("State:"):
                    # 형식: "State:\tR (running)" 또는 "State:\tZ (zombie)"
                    parts = line.split()
                    if len(parts) >= 2 and parts[1].upper() == "Z":
                        return False
                    break
    except (IOError, OSError):
        # status 파일 읽기 실패는 종료 직전일 수 있음 → 살아있다고 보수적 판단
        pass
    return True


def _send_signal(pid: int, sig: int) -> bool:
    """PID 에 시그널을 전송한다. 이미 종료된 PID 는 False 반환 (에러 아님)."""
    try:
        os.kill(pid, sig)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return False
    except OSError:
        return False


def _terminate_pid_tree(
    pid_tree: list[int],
    *,
    force_kill_timeout: float = 3.0,
    poll_interval: float = 0.1,
) -> tuple[list[int], str]:
    """PID 트리에 SIGTERM 을 보내고, force_kill_timeout 후에도 살아있으면 SIGKILL.

    Args:
        pid_tree: leaves → root 순서의 PID 리스트
        force_kill_timeout: SIGTERM 후 대기 시간(초)
        poll_interval: 폴링 간격(초)

    Returns:
        (killed_pids, exit_signal)
        killed_pids: 시그널이 전달된 PID 목록 (이미 죽어있던 PID 제외)
        exit_signal: "SIGTERM" 또는 "SIGKILL" — escalation 발생 여부
    """
    killed_pids: list[int] = []
    # 1단계: SIGTERM (leaves → root)
    for pid in pid_tree:
        if _send_signal(pid, signal.SIGTERM):
            killed_pids.append(pid)

    # 2단계: poll 대기
    deadline = time.monotonic() + force_kill_timeout
    while time.monotonic() < deadline:
        if not any(_pid_alive(pid) for pid in pid_tree):
            return killed_pids, "SIGTERM"
        time.sleep(poll_interval)

    # 3단계: SIGKILL escalation (살아있는 것만)
    escalated = False
    for pid in pid_tree:
        if _pid_alive(pid):
            if _send_signal(pid, signal.SIGKILL):
                escalated = True
                if pid not in killed_pids:
                    killed_pids.append(pid)
    return killed_pids, ("SIGKILL" if escalated else "SIGTERM")


# ---------------------------------------------------------------------------
# PID 추적: jsonl _meta.pid + Board API + pgrep -af 폴백
# ---------------------------------------------------------------------------

def _read_jsonl_meta_pid(session_id: str) -> int | None:
    """jsonl 첫 줄 `_meta.pid` 를 읽는다. 없으면 None."""
    filepath = os.path.join(_SESSIONS_DIR, f"{session_id}.jsonl")
    if not os.path.isfile(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
        if not first_line:
            return None
        data = json.loads(first_line)
    except (IOError, OSError, json.JSONDecodeError):
        return None
    meta = data.get("_meta") if isinstance(data, dict) else None
    if not isinstance(meta, dict):
        meta = data if isinstance(data, dict) else {}
    pid = meta.get("pid")
    if isinstance(pid, int) and pid > 0:
        return pid
    return None


def _fetch_pid_via_board_api(session_id: str) -> int | None:
    """Board API `GET /terminal/workflow/status?session_id=...` 응답에서 PID 추출."""
    port = _resolve_server_port()
    if port is None or not _is_server_running(port):
        return None
    url = f"http://127.0.0.1:{port}/terminal/workflow/status?session_id={session_id}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    # 응답 필드명은 환경마다 다를 수 있어 다중 후보 확인
    for key in ("pid", "process_pid", "claude_pid"):
        candidate = data.get(key)
        if isinstance(candidate, int) and candidate > 0:
            return candidate
    process = data.get("process")
    if isinstance(process, dict):
        for key in ("pid", "process_pid"):
            candidate = process.get(key)
            if isinstance(candidate, int) and candidate > 0:
                return candidate
    return None


def _find_pid_via_pgrep_session(session_id: str) -> int | None:
    """`pgrep -af 'claude -p.*--session-id <SID>'` 로 워커 PID 탐색."""
    # session_id 에 정규식 메타문자가 들어갈 수 있어 re.escape
    pattern = f"claude -p.*--session-id {re.escape(session_id)}"
    try:
        result = subprocess.run(
            ["pgrep", "-af", pattern],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # "<pid> <command...>" 형식
        parts = line.split(None, 1)
        if not parts:
            continue
        try:
            return int(parts[0])
        except ValueError:
            continue
    return None


def _resolve_root_pid(session_id: str) -> int | None:
    """세션의 root PID 를 다단계로 탐색한다.

    탐색 순서: jsonl _meta.pid → Board API → pgrep -af.
    """
    pid = _read_jsonl_meta_pid(session_id)
    if pid is not None and _pid_alive(pid):
        return pid
    pid = _fetch_pid_via_board_api(session_id)
    if pid is not None and _pid_alive(pid):
        return pid
    pid = _find_pid_via_pgrep_session(session_id)
    if pid is not None and _pid_alive(pid):
        return pid
    return None


# ---------------------------------------------------------------------------
# 활성 세션 자동 감지
# ---------------------------------------------------------------------------

def _resolve_target_session(
    ticket: str | None,
    session_id: str | None,
) -> tuple[str | None, str | None, str | None]:
    """ticket/session_id 입력으로 정리 대상 세션을 결정한다.

    Returns:
        (resolved_session_id, resolved_ticket_id, error)
        error 가 None 이 아니면 매칭 실패.
    """
    sessions, _source = get_sessions()
    active = [s for s in sessions if s.get("status") == "실행중"]

    # 1) session_id 명시 → 해당 세션 찾기
    if session_id:
        for s in active:
            if s.get("session_id") == session_id:
                return session_id, s.get("ticket_id") or None, None
        # 활성에 없으면 전체에서 찾기 (이미 종료된 세션도 정리 대상으로 허용)
        for s in sessions:
            if s.get("session_id") == session_id:
                return session_id, s.get("ticket_id") or None, None
        return None, None, f"session not found: {session_id}"

    # 2) ticket 명시 → ticket_id 매칭
    if ticket:
        matched = [s for s in active if s.get("ticket_id") == ticket]
        if not matched:
            return None, None, f"no active session for ticket {ticket}"
        if len(matched) > 1:
            return None, None, f"multiple active sessions for ticket {ticket}"
        sid = matched[0].get("session_id") or None
        return sid, ticket, None

    # 3) 둘 다 None → 활성 세션 자동 감지
    if not active:
        return None, None, "no active session"
    if len(active) > 1:
        return None, None, f"multiple active sessions ({len(active)}); specify --ticket or --session-id"
    s = active[0]
    return s.get("session_id") or None, s.get("ticket_id") or None, None


# ---------------------------------------------------------------------------
# jsonl process_exit 마커 append (W02)
# ---------------------------------------------------------------------------

def _append_process_exit_marker(
    session_id: str,
    *,
    killed_pids: list[int],
    exit_signal: str,
    flush_wait: float = 0.2,
    by_launcher_timeout: bool = False,
) -> tuple[bool, str | None]:
    """jsonl 파일에 `process_exit` 마커를 append 한다.

    마커 형식 (T-400 수동 정리 패턴 답습 + plan.md W02 명세):
      ```json
      {"type": "system", "subtype": "process_exit", "stopped_by": "flow-stop",
       "timestamp": "<iso8601>", "killed_pids": [...], "exit_signal": "SIGTERM|SIGKILL"}
      ```

    동시성 가드: kill 직후 `flush_wait` 초 sleep 후 append (Board side flush 대기).

    Args:
        session_id: 대상 세션 ID
        killed_pids: SIGTERM/SIGKILL 이 전달된 PID 목록
        exit_signal: "SIGTERM" 또는 "SIGKILL"
        flush_wait: append 전 대기 시간(초). 기본 0.2초

    Returns:
        (added, error_message)
        added: 마커 추가 성공 여부
        error_message: 실패 사유 (None 이면 성공)
    """
    filepath = os.path.join(_SESSIONS_DIR, f"{session_id}.jsonl")
    if not os.path.isfile(filepath):
        return False, f"jsonl not found: {filepath}"

    # Board side buffered write flush 대기
    if flush_wait > 0:
        time.sleep(flush_wait)

    timestamp = _dt.datetime.now(_dt.timezone.utc).isoformat()
    marker: dict[str, Any] = {
        "type": "system",
        "subtype": "process_exit",
        "stopped_by": "flow-stop",
        "timestamp": timestamp,
        "killed_pids": list(killed_pids),
        "exit_signal": exit_signal,
    }
    if by_launcher_timeout:
        marker["by_launcher_timeout"] = True
    line = json.dumps(marker, ensure_ascii=False) + "\n"

    # 파일 끝 newline 보강 (last-line 판독 안정성):
    # `"ab"` 모드는 모든 write 가 강제 EOF 라 seek/read 가 의미 없음 → "r+b" 사용
    needs_leading_newline = False
    try:
        with open(filepath, "rb") as fr:
            fr.seek(0, os.SEEK_END)
            size = fr.tell()
            if size > 0:
                fr.seek(size - 1, os.SEEK_SET)
                last = fr.read(1)
                if last != b"\n":
                    needs_leading_newline = True
    except (IOError, OSError):
        # 읽기 실패는 아래 append 단계에서 다시 잡힘
        pass

    try:
        # append-only 단일 write (atomic 성)
        with open(filepath, "ab") as f:
            payload = ((b"\n" if needs_leading_newline else b"") + line.encode("utf-8"))
            f.write(payload)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
    except (IOError, OSError) as exc:
        return False, f"jsonl append failed: {exc}"

    return True, None


# ---------------------------------------------------------------------------
# 칸반 현재 상태 조회 + In Progress → Open 자동 전이 (W03)
# ---------------------------------------------------------------------------

# bin wrapper 의 절대 경로 (memory: feedback_flow_bin_invocation 준수 — python3 직접 호출 금지)
_FLOW_KANBAN_BIN = os.path.join(_BIN_DIR, "flow-kanban")


def _read_kanban_status(ticket: str) -> tuple[str | None, str | None]:
    """`flow-kanban show <T-NNN>` 출력에서 현재 status 라벨을 추출한다.

    bin wrapper 사용 (python3 직접 호출 금지). show 출력은 사람이 읽는 텍스트라
    `Status: In Progress` 같은 라인을 정규식으로 파싱한다.

    Returns:
        (status_label, error)
        status_label: "To Do" / "Open" / "In Progress" / "Review" / "Done" 중 하나, 또는 None
        error: 조회 실패 사유 (None 이면 성공)
    """
    if not ticket:
        return None, "ticket is empty"
    if not os.path.isfile(_FLOW_KANBAN_BIN):
        return None, f"flow-kanban bin not found: {_FLOW_KANBAN_BIN}"
    try:
        result = subprocess.run(
            [_FLOW_KANBAN_BIN, "show", ticket],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return None, f"flow-kanban show failed: {exc}"
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        return None, f"flow-kanban show exit={result.returncode}: {stderr[:200]}"
    output = result.stdout or ""
    # show 출력 형식 예: "Status: In Progress" 또는 "상태: In Progress"
    # 양쪽 모두 매칭 (한/영 라벨 변형 방어)
    match = re.search(
        r"(?:Status|상태)\s*[:\s]\s*(To Do|Open|In Progress|Review|Done|Submit)",
        output,
    )
    if match:
        return match.group(1), None
    return None, "status label not found in flow-kanban show output"


def _kanban_move_to_open(
    ticket: str,
    *,
    timeout: float = 15.0,
) -> tuple[str, str | None]:
    """`flow-kanban move <ticket> open` 으로 칸반을 Open 으로 전이한다.

    cmd_move 가 In Progress → Open 전이 시 자동으로 `_cleanup_worktree_on_leave`
    를 호출한다. 따라서 본 함수는 워크트리 정리 코드를 별도 작성하지 않는다.

    현재 상태가 In Progress 가 아니면 skip + warn (errors[]에 비치명 기록).

    Args:
        ticket: 티켓 ID (예: "T-904")
        timeout: subprocess 타임아웃(초). 기본 15초

    Returns:
        (transition_label, error)
        transition_label:
          - "In Progress → Open"  : 정상 전이 성공
          - "skipped:<현재상태>"   : In Progress 가 아니어서 skip
          - "error"                : 실패
        error: 비치명 사유 (skip/error 모두 원인 메시지). None 이면 정상 성공.
    """
    # 1) 현재 상태 조회
    current_status, status_err = _read_kanban_status(ticket)
    if status_err:
        return "error", f"kanban status read failed: {status_err}"

    # 2) In Progress 가 아니면 skip
    if current_status != "In Progress":
        return f"skipped:{current_status}", (
            f"current status is '{current_status}', not 'In Progress' — skip transition"
        )

    # 3) flow-kanban move <ticket> open 호출
    if not os.path.isfile(_FLOW_KANBAN_BIN):
        return "error", f"flow-kanban bin not found: {_FLOW_KANBAN_BIN}"
    try:
        result = subprocess.run(
            [_FLOW_KANBAN_BIN, "move", ticket, "open"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return "error", f"flow-kanban move failed: {exc}"
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        msg = stderr or stdout or f"exit code {result.returncode}"
        return "error", f"flow-kanban move exit={result.returncode}: {msg[:300]}"
    return "In Progress → Open", None


# ---------------------------------------------------------------------------
# 메인 진입점
# ---------------------------------------------------------------------------

def stop_workflow(
    ticket: str | None,
    session_id: str | None,
    *,
    force_kill_timeout: float = 3.0,
    by_launcher_timeout: bool = False,
) -> dict[str, Any]:
    """워크플로우를 강제 중지하고 4축(프로세스/jsonl/칸반/워크트리) 정리를 수행한다.

    Decision A 순서 강제 (plan.md):
      1. 프로세스 트리 SIGTERM → poll(3s) → SIGKILL escalation
      2. PID `wait()` 또는 `/proc/<pid>` 부재 확인으로 종료 사실 확정
      3. jsonl `process_exit` 마커 append (kill 후 0.2s flush 대기)
      4. 칸반 In Progress → Open 전이 (`_cleanup_worktree_on_leave` 자동 호출됨)
      5. 워크트리 제거는 cmd_move 내부 자동 (미커밋 변경 보존 정책 유지)

    Args:
        ticket: 티켓 ID (예: "T-904"). None 이면 자동 감지 또는 session_id 사용
        session_id: 세션 ID (예: "wf-T-904-20260507-141555"). None 이면 ticket 또는 자동 감지
        force_kill_timeout: SIGTERM 후 SIGKILL escalation 까지 대기 시간(초)

    Returns:
        dict with keys:
          - ok: bool — 전체 정리 성공 여부
          - session_id: str | None — 정리 대상 세션 ID
          - ticket_id: str | None — 정리 대상 티켓 ID
          - killed_pids: list[int] — SIGTERM/SIGKILL 이 전달된 PID 목록
          - jsonl_marker_added: bool — process_exit 마커 추가 여부 (W02)
          - kanban_transition: str | None — 칸반 전이 결과 (W03)
          - worktree_action: str | None — 워크트리 정리 결과 (W03)
          - errors: list[str] — 비치명 오류/경고 메시지
    """
    result: dict[str, Any] = {
        "ok": False,
        "session_id": None,
        "ticket_id": None,
        "killed_pids": [],
        "jsonl_marker_added": False,
        "kanban_transition": None,
        "worktree_action": None,
        "errors": [],
    }

    # 1) 정리 대상 세션 결정
    resolved_sid, resolved_tid, err = _resolve_target_session(ticket, session_id)
    if err:
        result["errors"].append(err)
        return result
    result["session_id"] = resolved_sid
    result["ticket_id"] = resolved_tid

    if resolved_sid is None:
        result["errors"].append("session_id resolution failed")
        return result

    # 2) PID 추적
    root_pid = _resolve_root_pid(resolved_sid)
    if root_pid is None:
        # 살아있는 PID 가 없음 — 이미 종료된 상태일 가능성
        result["errors"].append(f"no live worker process for {resolved_sid}")
        # 프로세스가 이미 죽었어도 jsonl 마커는 멱등적으로 시도 (process_exit 누락 보강)
        added, marker_err = _append_process_exit_marker(
            resolved_sid,
            killed_pids=[],
            exit_signal="SIGTERM",
            flush_wait=0.0,  # 죽은 프로세스 → 대기 불필요
            by_launcher_timeout=by_launcher_timeout,
        )
        result["jsonl_marker_added"] = added
        if marker_err:
            result["errors"].append(marker_err)
        # W03: 프로세스가 이미 죽었어도 칸반이 In Progress 잔류일 수 있어 멱등 전이 시도.
        # _kanban_move_to_open 내부에서 현재 상태가 In Progress 가 아니면 skip + warn.
        if resolved_tid:
            transition, kanban_err = _kanban_move_to_open(resolved_tid)
            result["kanban_transition"] = transition
            if kanban_err:
                result["errors"].append(kanban_err)
            # 워크트리 정리는 cmd_move 내부 _cleanup_worktree_on_leave 가 처리
            result["worktree_action"] = (
                "cleaned_via_cmd_move"
                if transition == "In Progress → Open"
                else "skipped"
            )
        else:
            result["errors"].append("ticket_id missing — kanban transition skipped")
            result["kanban_transition"] = "skipped:no_ticket"
            result["worktree_action"] = "skipped"
        result["ok"] = True  # 프로세스 자체는 정리 불필요 → 성공으로 처리
        return result

    # 3) PID 트리 수집
    pid_tree = _collect_pid_tree(root_pid)

    # 4) SIGTERM → poll → SIGKILL escalation
    killed_pids, exit_signal = _terminate_pid_tree(
        pid_tree, force_kill_timeout=force_kill_timeout
    )
    result["killed_pids"] = killed_pids

    # 5) 종료 사실 확정 (Decision A 순서 강제)
    still_alive = [p for p in pid_tree if _pid_alive(p)]
    if still_alive:
        result["errors"].append(
            f"some pids still alive after SIGKILL: {still_alive}"
        )
        # 부분 성공 — 호출자가 errors 를 보고 판단
    result["ok"] = not still_alive

    # 6) jsonl process_exit 마커 append (W02)
    #    동시성 가드: kill 직후 0.2s sleep 후 append (Board side flush 대기)
    added, marker_err = _append_process_exit_marker(
        resolved_sid,
        killed_pids=killed_pids,
        exit_signal=exit_signal,
        flush_wait=0.2,
        by_launcher_timeout=by_launcher_timeout,
    )
    result["jsonl_marker_added"] = added
    if marker_err:
        result["errors"].append(marker_err)

    # 7) 칸반 In Progress → Open 자동 전이 (W03)
    #    Decision A 순서 강제: PID wait 완료 + jsonl 마커 append 완료 후에만 호출.
    #    cmd_move 가 _cleanup_worktree_on_leave 를 자동 호출하므로 워크트리 정리 코드 불필요.
    #    워커가 이미 죽은 상태에서 호출되므로 has_uncommitted_changes 검사가 정확하게 동작.
    if resolved_tid:
        transition, kanban_err = _kanban_move_to_open(resolved_tid)
        result["kanban_transition"] = transition
        if kanban_err:
            # 비치명: skip + warn 또는 실패는 errors[]에 기록하되 ok 는 변경하지 않음
            result["errors"].append(kanban_err)
        # 워크트리 정리 결과: cmd_move 내부 자동 정리 위임
        # - 정상 전이: cmd_move 가 _cleanup_worktree_on_leave 호출 (미커밋 보존 정책 유지)
        # - skip 케이스 (In Progress 가 아님): 워크트리는 이미 정리되었거나 별도 처리됨
        if transition == "In Progress → Open":
            result["worktree_action"] = "cleaned_via_cmd_move"
        else:
            result["worktree_action"] = "skipped"
    else:
        # ticket_id 가 없으면 칸반 전이 자체 불가 (session_id 만으로는 티켓 매칭 불가)
        result["errors"].append("ticket_id missing — kanban transition skipped")
        result["kanban_transition"] = "skipped:no_ticket"
        result["worktree_action"] = "skipped"

    return result


# ---------------------------------------------------------------------------
# CLI 진입점 (W04)
# ---------------------------------------------------------------------------

def _build_result_table(result: dict[str, Any]) -> str:
    """4축 정리 결과를 컬러 테이블 문자열로 반환한다.

    sessions.py 의 C_GREEN/C_DIM/C_RED 와 동일 상수를 재사용한다.
    터미널 출력에 이모지/아이콘 사용 금지 (MUST NOT — general.md).
    """
    # 엔진 경로 sys.path 에 _ENGINE_DIR 이 이미 추가되어 있으므로 직접 import
    try:
        from common import C_GREEN, C_RED, C_DIM, C_RESET, C_BOLD, C_YELLOW  # noqa: E402
    except ImportError:
        C_GREEN = C_RED = C_DIM = C_RESET = C_BOLD = C_YELLOW = ""

    ok = result.get("ok", False)
    session_id = result.get("session_id") or "-"
    ticket_id = result.get("ticket_id") or "-"
    killed_pids = result.get("killed_pids") or []
    jsonl_marker = result.get("jsonl_marker_added", False)
    kanban = result.get("kanban_transition") or "-"
    worktree = result.get("worktree_action") or "-"
    errors = result.get("errors") or []

    ok_label = f"{C_GREEN}ok{C_RESET}" if ok else f"{C_RED}fail{C_RESET}"
    pid_str = ", ".join(str(p) for p in killed_pids) if killed_pids else "(none)"
    marker_label = (
        f"{C_GREEN}yes{C_RESET}" if jsonl_marker else f"{C_DIM}no{C_RESET}"
    )

    lines = [
        f"{C_BOLD}flow-stop 결과{C_RESET}",
        f"  result       : {ok_label}",
        f"  ticket       : {ticket_id}",
        f"  session_id   : {C_DIM}{session_id}{C_RESET}",
        f"  killed_pids  : {pid_str}",
        f"  jsonl_marker : {marker_label}",
        f"  kanban       : {kanban}",
        f"  worktree     : {worktree}",
    ]
    if errors:
        lines.append(f"  {C_YELLOW}warnings{C_RESET}     :")
        for e in errors:
            lines.append(f"    - {e}")
    return "\n".join(lines)


def _main() -> None:
    """argparse CLI 진입점.

    호출 패턴:
      flow-stop [T-NNN | --ticket T-NNN | --session-id <sid>]
                [--force] [--json] [--by-launcher-timeout]
                [--force-kill-timeout SECONDS]

    종료 코드:
      0 — 성공
      2 — 활성 세션 없음 (no active session)
      1 — 기타 에러
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="flow-stop",
        description="워크플로우를 강제 중지하고 4축(프로세스/jsonl/칸반/워크트리)을 정리합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "예시:\n"
            "  flow-stop T-904                   # 티켓 번호로 정리\n"
            "  flow-stop --ticket T-904          # 동일 (명시 플래그)\n"
            "  flow-stop --session-id wf-T-904-20260507-141555\n"
            "  flow-stop                         # 활성 세션 자동 감지\n"
            "  flow-stop T-904 --json            # JSON 출력\n"
            "  flow-stop T-904 --force-kill-timeout 5.0\n"
        ),
    )
    parser.add_argument(
        "ticket_pos",
        nargs="?",
        metavar="T-NNN",
        help="정리할 티켓 번호 (위치 인자). --ticket 과 동일.",
    )
    parser.add_argument(
        "--ticket",
        metavar="T-NNN",
        dest="ticket_flag",
        help="정리할 티켓 번호 (명시 플래그). 위치 인자와 동일.",
    )
    parser.add_argument(
        "--session-id",
        metavar="SID",
        dest="session_id",
        help="세션 ID 로 직접 지정 (wf-T-NNN-YYYYMMDD-HHMMSS 형식).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="확인 없이 즉시 강제 중지 (현재 구현에서는 기본 동작과 동일).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="결과를 JSON 으로 출력합니다.",
    )
    parser.add_argument(
        "--by-launcher-timeout",
        action="store_true",
        dest="by_launcher_timeout",
        help="launcher timeout fallback 경로에서 호출되었음을 마커에 기록합니다.",
    )
    parser.add_argument(
        "--force-kill-timeout",
        type=float,
        default=3.0,
        metavar="SECONDS",
        dest="force_kill_timeout",
        help="SIGTERM 후 SIGKILL escalation 대기 시간(초). 기본 3.0.",
    )

    args = parser.parse_args()

    # 위치 인자와 --ticket 플래그 중 하나만 허용
    ticket: str | None = None
    if args.ticket_pos and args.ticket_flag:
        parser.error("위치 인자 T-NNN 과 --ticket 을 동시에 지정할 수 없습니다.")
    elif args.ticket_pos:
        ticket = args.ticket_pos
    elif args.ticket_flag:
        ticket = args.ticket_flag

    result = stop_workflow(
        ticket=ticket,
        session_id=args.session_id,
        force_kill_timeout=args.force_kill_timeout,
        by_launcher_timeout=args.by_launcher_timeout,
    )

    if args.output_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(_build_result_table(result))

    # 종료 코드 결정
    errors = result.get("errors") or []
    no_active = any(
        "no active session" in e or "no active session for ticket" in e
        for e in errors
    )
    if no_active and not result.get("ok"):
        sys.exit(2)
    elif not result.get("ok"):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    _main()
