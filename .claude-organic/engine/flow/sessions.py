#!/usr/bin/env -S python3 -u
"""sessions.py - 워크플로우 세션 목록 조회 스크립트.

기능:
  - 현재 실행 중인 워크플로우 세션 목록을 테이블 형태로 출력한다.
  - Board 서버 기동 시 HTTP API(`GET /terminal/workflow/list`)를 우선 사용한다.
  - 서버 미기동 시 `.workflow-sessions/*.jsonl` 파일을 직접 파싱하여 상태를 판별한다.

사용법:
  flow-sessions            # 실행중 세션만 출력
  flow-sessions --all      # 완료/실패 세션 포함 전체 출력
  flow-sessions --json     # JSON 형식 출력
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

# sys.path 보장: flow/ 패키지 import를 위해 scripts/ 디렉터리 추가
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from common import C_GREEN, C_RED, C_DIM, C_RESET  # noqa: E402
from flow.cli_utils import build_common_epilog  # noqa: E402


# ---------------------------------------------------------------------------
# 상수 / 경로
# ---------------------------------------------------------------------------

# .claude-organic/ 루트 (.workflow-sessions/ 디렉터리의 부모)
_WF_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", ".."))
_SESSIONS_DIR = os.path.join(_WF_ROOT, ".workflow-sessions")
_BOARD_URL_FILE = os.path.join(_WF_ROOT, ".board.url")

# HTTP API status 값 → 정규화 상태
_HTTP_STATUS_MAP = {
    "running": "실행중",
    "stopped": "완료",
    "error": "실패",
}

# ANSI 색상: 실행중=녹색, 완료=흰색(dim), 실패=빨강
_STATUS_COLOR_MAP = {
    "실행중": C_GREEN,
    "완료": C_DIM,
    "실패": C_RED,
}


# ---------------------------------------------------------------------------
# HTTP API 헬퍼 (http_launcher.py 패턴 재사용)
# ---------------------------------------------------------------------------

def _resolve_server_port() -> int | None:
    """.board.url 파일에서 서버 포트를 추출한다."""
    if not os.path.isfile(_BOARD_URL_FILE):
        return None
    try:
        with open(_BOARD_URL_FILE, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
        if not first_line:
            return None
        from urllib.parse import urlparse
        parsed = urlparse(first_line)
        return parsed.port or None
    except Exception:
        return None


def _is_server_running(port: int) -> bool:
    """Board 서버 기동 여부 확인 (GET /terminal/status)."""
    url = f"http://127.0.0.1:{port}/terminal/status"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def _http_get_json(port: int, path: str) -> list | dict:
    """서버에 GET 요청을 전송하고 응답을 JSON으로 파싱하여 반환한다."""
    url = f"http://127.0.0.1:{port}{path}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# 경로 A: HTTP API로 세션 목록 수집
# ---------------------------------------------------------------------------

def _fetch_sessions_via_http(port: int) -> list[dict] | None:
    """HTTP API로 세션 목록을 가져온다. 실패 시 None 반환."""
    try:
        raw = _http_get_json(port, "/terminal/workflow/list")
        if not isinstance(raw, list):
            return None
        sessions = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            http_status = item.get("status", "stopped")
            # running → 실행중, stopped → 완료, 그 외 → 실패
            if http_status == "running":
                status = "실행중"
            elif http_status == "stopped":
                status = "완료"
            else:
                status = "실패"
            sessions.append({
                "session_id": item.get("session_id", ""),
                "ticket_id": item.get("ticket_id", ""),
                "command": item.get("command", ""),
                "created_at": item.get("created_at", ""),
                "status": status,
            })
        return sessions
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 경로 B: JSONL 직접 파싱 (폴백)
# ---------------------------------------------------------------------------

def _parse_jsonl_status(filepath: str) -> str:
    """JSONL 파일을 역방향으로 스캔하여 세션 상태를 판별한다.

    판별 규칙:
      - `process_exit` subtype 미존재 → 실행중
      - `process_exit` 존재 + 이전에 `result.subtype == "success"` → 완료
      - `process_exit` 존재 + result 없음 또는 success가 아님 → 실패
    """
    has_process_exit = False
    has_success_result = False
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # 역방향 탐색으로 마지막 이벤트 우선 확인
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            subtype = event.get("subtype", "")
            etype = event.get("type", "")
            if subtype == "process_exit":
                has_process_exit = True
            if etype == "result" and subtype == "success":
                has_success_result = True
    except (IOError, OSError):
        return "실행중"

    if not has_process_exit:
        return "실행중"
    return "완료" if has_success_result else "실패"


def _fetch_sessions_via_jsonl() -> list[dict]:
    """`.workflow-sessions/` 디렉터리의 JSONL 파일을 파싱하여 세션 목록을 반환한다."""
    if not os.path.isdir(_SESSIONS_DIR):
        return []

    sessions = []
    for filename in os.listdir(_SESSIONS_DIR):
        if not filename.endswith(".jsonl"):
            continue
        filepath = os.path.join(_SESSIONS_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
            if not first_line:
                continue
            meta_data = json.loads(first_line)
        except (IOError, OSError, json.JSONDecodeError):
            continue

        # 첫 줄이 _meta 블록인지 확인
        meta = meta_data.get("_meta")
        if not isinstance(meta, dict):
            # 첫 줄 자체가 메타 필드를 포함하는 경우 (구버전 호환)
            meta = meta_data

        session_id = meta.get("session_id", os.path.splitext(filename)[0])
        ticket_id = meta.get("ticket_id", "")
        command = meta.get("command", "")
        created_at = meta.get("created_at", "")

        status = _parse_jsonl_status(filepath)

        sessions.append({
            "session_id": session_id,
            "ticket_id": ticket_id,
            "command": command,
            "created_at": created_at,
            "status": status,
        })

    # created_at 기준 오름차순 정렬
    sessions.sort(key=lambda s: s.get("created_at", ""))
    return sessions


# ---------------------------------------------------------------------------
# 세션 데이터 수집 (이중 경로)
# ---------------------------------------------------------------------------

def get_sessions() -> tuple[list[dict], str]:
    """세션 목록을 수집한다. HTTP API 우선, 폴백 시 JSONL 파싱.

    Returns:
        (sessions, source) 튜플.
        source: "http" | "jsonl"
    """
    port = _resolve_server_port()
    if port is not None and _is_server_running(port):
        sessions = _fetch_sessions_via_http(port)
        if sessions is not None:
            return sessions, "http"

    return _fetch_sessions_via_jsonl(), "jsonl"


# ---------------------------------------------------------------------------
# 출력 포맷
# ---------------------------------------------------------------------------

def _format_created_at(created_at: str) -> str:
    """created_at ISO 문자열에서 날짜+시간 부분만 추출한다."""
    if not created_at:
        return "-"
    # "2026-04-06T16:54:00" → "04-06 16:54"
    try:
        # T 구분자로 분리
        parts = created_at.split("T")
        date_part = parts[0]  # "2026-04-06"
        time_part = parts[1][:5] if len(parts) > 1 else ""  # "16:54"
        # 날짜에서 연도 제거: "04-06"
        date_short = "-".join(date_part.split("-")[1:])
        return f"{date_short} {time_part}".strip()
    except Exception:
        return created_at[:16] if len(created_at) >= 16 else created_at


def _truncate(text: str, max_len: int) -> str:
    """텍스트를 max_len 이하로 자른다. 초과 시 끝에 '…' 추가."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def print_table(sessions: list[dict]) -> None:
    """세션 목록을 ANSI 색상이 포함된 테이블로 출력한다."""
    # 헤더
    header = f"{'세션ID':<38}  {'티켓':<7}  {'명령어':<18}  {'시작시간':<13}  {'상태'}"
    separator = "-" * len(header)
    print(f"{C_DIM}{header}{C_RESET}")
    print(f"{C_DIM}{separator}{C_RESET}")

    for s in sessions:
        session_id = _truncate(s.get("session_id", ""), 38)
        ticket_id = _truncate(s.get("ticket_id", "-"), 7)
        command = _truncate(s.get("command", "-"), 18)
        created_at = _format_created_at(s.get("created_at", ""))
        status = s.get("status", "")
        color = _STATUS_COLOR_MAP.get(status, "")
        print(
            f"{session_id:<38}  {ticket_id:<7}  {command:<18}  {created_at:<13}  "
            f"{color}{status}{C_RESET}"
        )


# ---------------------------------------------------------------------------
# CLI 인터페이스
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서를 생성한다."""
    parser = argparse.ArgumentParser(
        prog="flow-sessions",
        description="워크플로우 세션 목록 조회",
        epilog=build_common_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="show_all",
        help="완료/실패 세션 포함 전체 출력",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="JSON 형식으로 출력",
    )
    return parser


def main() -> None:
    """CLI 진입점."""
    parser = _build_parser()
    args = parser.parse_args()

    sessions, source = get_sessions()

    # --all 없으면 실행중 세션만 필터링
    if not args.show_all:
        filtered = [s for s in sessions if s.get("status") == "실행중"]
    else:
        filtered = sessions

    # JSON 출력 모드
    if args.output_json:
        print(json.dumps(filtered, ensure_ascii=False, indent=2))
        return

    # 테이블 출력
    if not filtered:
        if args.show_all:
            print("세션이 없습니다.")
        else:
            print("실행 중인 세션이 없습니다.")
        return

    # 소스 안내 (jsonl 폴백 시)
    if source == "jsonl":
        print(f"{C_DIM}[폴백] Board 서버 미기동 - JSONL 직접 파싱{C_RESET}")

    print_table(filtered)
    print(f"\n{C_DIM}총 {len(filtered)}개{' (전체 ' + str(len(sessions)) + '개 중)' if not args.show_all else ''}{C_RESET}")


if __name__ == "__main__":
    main()
