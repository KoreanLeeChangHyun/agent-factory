#!/usr/bin/env -S python3 -u
"""http_launcher.py - HTTP API 기반 워크플로우 런처 스크립트.

기능:
  launch  - Board server의 HTTP API를 통해 워크플로우 세션을 시작한다.
            서버 미기동 시 INLINE: 폴백 신호를 출력하여 메인 세션 직접 실행을 유도한다.
  cleanup - 지정된 티켓 ID의 워크플로우 세션을 종료한다.

사용법:
  flow-launcher launch  T-NNN '<command>'
  flow-launcher cleanup T-NNN

stdout 출력 프로토콜:
  LAUNCH: {session_id} 실행 중  → HTTP API로 세션 시작 성공
  INLINE: {사유}                → 폴백 필요 (서버 미기동, 재진입 등)

exit code:
  0 - 성공 (LAUNCH 또는 INLINE)
  1 - 에러 (HTTP API 호출 실패 등)

NOTE: HTTP 통신은 urllib.request만 사용하여 외부 의존성을 배제한다.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

# sys.path 보장: flow/ 패키지 import를 위해 scripts/ 디렉터리 추가
_engine_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from flow.flow_logger import append_log as _fl_append_log, resolve_work_dir_for_logging as _fl_resolve  # noqa: E402


# ---------------------------------------------------------------------------
# 로깅 헬퍼
# ---------------------------------------------------------------------------

def _log(level: str, message: str) -> None:
    """workflow.log에 로그를 기록한다. abs_work_dir 해석 실패 시 조용히 건너뛴다."""
    try:
        work_dir = _fl_resolve()
        if work_dir:
            _fl_append_log(work_dir, level, message)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# .board.url 파일 경로
# ---------------------------------------------------------------------------

def _board_url_path() -> str:
    """프로젝트 루트 기준 .board.url 파일 절대 경로를 반환한다."""
    # scripts/flow/http_launcher.py -> scripts/ -> .claude-organic/
    wf_root = os.path.dirname(_engine_dir)
    return os.path.join(wf_root, ".board.url")


# ---------------------------------------------------------------------------
# 서버 포트 해석
# ---------------------------------------------------------------------------

def _resolve_server_port() -> int | None:
    """`.claude-organic/.board.url` 파일에서 서버 포트를 추출한다.

    파일 형식 예시:
        http://127.0.0.1:9927/.claude-organic/board/index.html

    첫 번째 줄의 URL에서 포트 번호를 파싱하여 반환한다.
    파일이 존재하지 않거나 파싱에 실패하면 None을 반환한다.

    Returns:
        포트 번호(int) 또는 None.
    """
    url_file = _board_url_path()
    if not os.path.isfile(url_file):
        return None

    try:
        with open(url_file, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
        if not first_line:
            return None

        # URL에서 포트 추출: http://127.0.0.1:PORT/...
        from urllib.parse import urlparse
        parsed = urlparse(first_line)
        if parsed.port:
            return parsed.port
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# 서버 상태 확인
# ---------------------------------------------------------------------------

def _is_server_running(port: int) -> bool:
    """Board 서버가 기동 중인지 확인한다.

    ``GET http://127.0.0.1:{port}/terminal/status`` 에 요청을 보내
    HTTP 200 응답이 돌아오면 True를 반환한다.

    Args:
        port: 확인할 서버 포트 번호.

    Returns:
        서버 기동 중이면 True, 그 외 False.
    """
    url = f"http://127.0.0.1:{port}/terminal/status"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# HTTP 요청 헬퍼
# ---------------------------------------------------------------------------

def _http_post_json(port: int, path: str, data: dict) -> dict:
    """서버에 JSON POST 요청을 전송하고 응답을 dict로 반환한다.

    Args:
        port: 서버 포트 번호.
        path: 요청 경로 (예: ``/terminal/workflow/start``).
        data: 요청 본문 딕셔너리.

    Returns:
        응답 JSON을 dict로 파싱한 결과.

    Raises:
        urllib.error.URLError: 네트워크 오류 시.
        urllib.error.HTTPError: HTTP 에러 응답 시.
        json.JSONDecodeError: 응답 파싱 실패 시.
    """
    url = f"http://127.0.0.1:{port}{path}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_get_json(port: int, path: str) -> dict | list:
    """서버에 GET 요청을 전송하고 응답을 JSON으로 파싱하여 반환한다.

    Args:
        port: 서버 포트 번호.
        path: 요청 경로 (예: ``/terminal/workflow/list``).

    Returns:
        응답 JSON을 파싱한 결과 (dict 또는 list).

    Raises:
        urllib.error.URLError: 네트워크 오류 시.
        urllib.error.HTTPError: HTTP 에러 응답 시.
        json.JSONDecodeError: 응답 파싱 실패 시.
    """
    url = f"http://127.0.0.1:{port}{path}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# 티켓 라이프사이클 헬퍼 (launcher 가 칸반 전이 책임을 흡수)
# ---------------------------------------------------------------------------

def _read_ticket_status(ticket_id: str) -> str | None:
    """`.claude-organic/tickets/<status>/<ticket_id>.xml` 에서 status 를 읽는다.

    todo/open/progress/review/done 디렉터리를 순서대로 검색한다.

    Returns:
        status 문자열 ("To Do", "Open", "In Progress", "Review", "Done") 또는
        티켓 미발견 시 None.
    """
    wf_root = os.path.dirname(_engine_dir)
    tickets_dir = os.path.join(wf_root, "tickets")
    if not os.path.isdir(tickets_dir):
        return None
    for status_dir in ("todo", "open", "progress", "review", "done"):
        path = os.path.join(tickets_dir, status_dir, f"{ticket_id}.xml")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            return None
        m = re.search(r"<status>([^<]+)</status>", content)
        if m:
            return m.group(1).strip()
        return None
    return None


def _kanban_move_submit(ticket_id: str, current_status: str | None = None) -> bool:
    """``flow-kanban move <ticket_id> submit`` 호출 (멱등 + 상태 가드).

    /wf -s 정식 흐름에서 메인 세션이 launch 직전에 호출하던 단계를 launcher
    본체가 흡수한다. 이를 통해 launcher 단독 호출 경로(자연어 실행, 외부 스크립트
    등)에서도 칸반-실제 상태 동기화가 구조적으로 보장된다.

    상태별 동작:
      - Open: move submit 정상 호출
      - To Do: cmd_launch 가 사전 거부하므로 여기 도달 안 함
      - Submit / In Progress / Review / Done: skip (이미 Submit 이거나 그 이후
        단계라 되돌릴 필요 없음). 이 가드가 없으면 kanban_cli 가 거부하면서
        ``현재 X이므로 Submit으로 이동할 수 없습니다`` ERROR 로그를 남기는
        회귀가 누적된다 (로그 분석 2026-04-29 에서 11회 발생 패턴 확인).

    실패해도 워크플로우 실행은 계속 진행 (비차단, wf.md:459 의 정책과 동일).

    Args:
        ticket_id: 티켓 ID.
        current_status: 호출 전 미리 읽어둔 status. None 이면 함수 내부에서 재조회.

    Returns:
        실제 move 호출 성공 여부 (skip 도 True 반환 — 호출자가 결과로 분기 안 하도록).
    """
    if current_status is None:
        current_status = _read_ticket_status(ticket_id)

    if current_status in ("Submit", "In Progress", "Review", "Done"):
        _log(
            "INFO",
            f"http_launcher: kanban move submit skipped "
            f"(already {current_status}): {ticket_id}",
        )
        return True

    wf_root = os.path.dirname(_engine_dir)
    bin_path = os.path.join(wf_root, "bin", "flow-kanban")
    if not os.path.isfile(bin_path):
        _log("WARN", f"http_launcher: flow-kanban binary missing: {bin_path}")
        return False
    try:
        result = subprocess.run(
            [bin_path, "move", ticket_id, "submit"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            _log(
                "WARN",
                f"http_launcher: kanban move submit failed (non-blocking): "
                f"{result.stderr.strip()}",
            )
            return False
        return True
    except (OSError, subprocess.SubprocessError) as exc:
        _log("WARN", f"http_launcher: kanban move submit error (non-blocking): {exc}")
        return False


def _normalize_command(ticket_id: str, command: str) -> str:
    """command 인자가 단순 명령이면 ``/wf -s N`` 형태로 변환한다.

    워크플로우 세션 첫 user 메시지가 정식 진입점(/wf -s) 이 되도록 보장하여
    워크플로우 세션 안에서 flow-init → step-init 자동 흐름이 트리거되도록 한다.

    - ``implement`` / ``research`` / ``review`` → ``/wf -s N``
    - ``/wf`` 로 시작하는 형태 → 그대로 (정식 호출자)
    - 그 외 → 그대로 (호환성)

    Args:
        ticket_id: 티켓 ID (예: T-902).
        command: 원본 command 인자.

    Returns:
        정규화된 command 문자열.
    """
    cmd_stripped = command.strip()
    if cmd_stripped in ("implement", "research", "review"):
        m = re.search(r"(\d+)", ticket_id)
        n = m.group(1).lstrip("0") or "0" if m else ticket_id
        return f"/wf -s {n}"
    return command


# ---------------------------------------------------------------------------
# launch 서브커맨드
# ---------------------------------------------------------------------------

def cmd_launch(ticket_id: str, command: str) -> int:
    """HTTP API를 통해 워크플로우 세션을 시작한다.

    서버 미기동, 포트 해석 실패, 재진입 감지 시에는 INLINE: 신호를 출력하여
    메인 세션에서의 직접 실행을 유도한다.

    티켓 라이프사이클 책임 흡수 (2026-04-29 패치):
      - 사전 검증: status == "To Do" 면 거부 (정식 /wf -s 흐름과 정합)
      - 칸반 전이: submit 으로 자동 이동 (멱등) — 단독 호출 경로 desync 차단
      - command 정규화: implement/research/review → /wf -s N

    stdout 메시지로 결과를 전달한다:
      - ``LAUNCH: {session_id} 실행 중`` -> HTTP API 세션 시작 성공
      - ``INLINE: {사유}`` -> 폴백 필요

    Args:
        ticket_id: 티켓 ID (예: T-001).
        command: 워크플로우에서 실행할 명령 문자열.

    Returns:
        exit code: 0=성공(LAUNCH 또는 INLINE), 1=에러.
    """
    _log("INFO", f"http_launcher: cmd_launch start ticket_id={ticket_id}")

    # 0-1) 티켓 상태 사전 검증: To Do 는 거부.
    current_status = _read_ticket_status(ticket_id)
    if current_status == "To Do":
        msg = (
            f"{ticket_id} 은 To Do 상태입니다. 먼저 Open 으로 승격 후 다시 제출하세요."
        )
        _log("ERROR", f"http_launcher: cmd_launch rejected (To Do): {ticket_id}")
        print(f"[ERROR] {msg}", file=sys.stderr)
        return 1

    # 0-2) 칸반 전이 (멱등 + 상태 가드). 호출 경로 무관하게 launcher 가 단일 진입점에서 처리.
    # current_status 를 한 번 읽고 _kanban_move_submit 에 전달해 race 회피 + 중복 IO 절감.
    _kanban_move_submit(ticket_id, current_status)

    # 0-3) command 정규화: 단순 명령 → /wf -s N 변환.
    command = _normalize_command(ticket_id, command)

    # 1) 서버 포트 해석
    port = _resolve_server_port()
    if port is None:
        print("INLINE: 서버 포트 해석 실패, 인라인 실행 필요")
        return 0

    # 2) 서버 상태 확인
    if not _is_server_running(port):
        print("INLINE: 서버 미기동, 인라인 실행 필요")
        return 0

    # 3) 재진입 감지: 이미 워크플로우 세션 내부에서 호출된 경우
    if os.environ.get("_WF_SESSION_TYPE") == "workflow":
        print("INLINE: 재진입 감지, 인라인 실행 필요")
        return 0

    # 4) POST /terminal/workflow/start
    try:
        resp = _http_post_json(port, "/terminal/workflow/start", {
            "ticket": ticket_id,
            "command": command,
            "work_dir": "",
        })
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        _log("ERROR", f"http_launcher: start API failed status={e.code} body={error_body}")
        print(f"[ERROR] 워크플로우 세션 시작 실패 (HTTP {e.code}): {error_body}", file=sys.stderr)
        return 1
    except Exception as e:
        _log("ERROR", f"http_launcher: start API error {e}")
        print(f"[ERROR] 워크플로우 세션 시작 실패: {e}", file=sys.stderr)
        return 1

    # 5) 응답 처리
    if resp.get("ok"):
        session_id = resp.get("session_id", "unknown")
        _log("INFO", f"http_launcher: cmd_launch complete session_id={session_id}")
        print(f"LAUNCH: {session_id} 실행 중")
        return 0
    else:
        error_msg = resp.get("error", "알 수 없는 오류")
        _log("ERROR", f"http_launcher: start API returned ok=false error={error_msg}")
        print(f"[ERROR] 워크플로우 세션 시작 실패: {error_msg}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# cleanup 서브커맨드
# ---------------------------------------------------------------------------

def cmd_cleanup(ticket_id: str) -> int:
    """지정된 티켓 ID의 워크플로우 세션을 종료한다.

    서버 미기동이거나 해당 티켓의 세션이 없으면 조용히 성공을 반환한다 (멱등성).

    Args:
        ticket_id: 종료할 티켓 ID (예: T-001).

    Returns:
        exit code: 항상 0 (멱등성 보장).
    """
    _log("INFO", f"http_launcher: cmd_cleanup start ticket_id={ticket_id}")

    # 1) 서버 포트 해석
    port = _resolve_server_port()
    if port is None:
        return 0

    # 2) 서버 상태 확인 (미기동 시 조용히 종료)
    if not _is_server_running(port):
        return 0

    # 3) GET /terminal/workflow/list 로 해당 ticket_id 세션 조회
    try:
        sessions = _http_get_json(port, "/terminal/workflow/list")
    except Exception as e:
        _log("WARN", f"http_launcher: list API error during cleanup: {e}")
        return 0

    # ticket_id와 매칭되는 세션 찾기
    matching_sessions = [
        s for s in sessions
        if isinstance(s, dict) and s.get("ticket_id") == ticket_id
    ]

    if not matching_sessions:
        return 0

    # 4) 매칭 세션을 POST /terminal/workflow/kill 로 종료
    for session in matching_sessions:
        session_id = session.get("session_id", "")
        if not session_id:
            continue
        try:
            _http_post_json(port, "/terminal/workflow/kill", {
                "session_id": session_id,
            })
            _log("INFO", f"http_launcher: cleanup killed session_id={session_id}")
        except Exception as e:
            _log("WARN", f"http_launcher: kill API error session_id={session_id}: {e}")
            # 멱등성: kill 실패해도 계속 진행
            pass

    return 0


# ---------------------------------------------------------------------------
# CLI 인터페이스
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서를 생성한다.

    tmux_launcher.py와 동일한 서브커맨드 구조를 유지한다.

    Returns:
        구성된 ArgumentParser 인스턴스.
    """
    parser = argparse.ArgumentParser(
        prog="flow-launcher",
        description="HTTP API 기반 워크플로우 런처 스크립트",
    )
    subparsers = parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    # launch 서브커맨드
    launch_parser = subparsers.add_parser(
        "launch",
        help="HTTP API로 워크플로우 세션 시작",
    )
    launch_parser.add_argument("ticket_id", metavar="T-NNN", help="티켓 ID")
    launch_parser.add_argument("command", metavar="COMMAND", help="실행할 명령 문자열")

    # cleanup 서브커맨드
    cleanup_parser = subparsers.add_parser(
        "cleanup",
        help="워크플로우 세션 종료",
    )
    cleanup_parser.add_argument("ticket_id", metavar="T-NNN", help="티켓 ID")

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
