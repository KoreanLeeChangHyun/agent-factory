"""inject_kanban_context.py — UserPromptSubmit hook: 칸반/세션 스냅샷 컨텍스트 빌더.

입력: stdin JSON (UserPromptSubmit 페이로드, 내용 무시 가능)
출력: stdout JSON
  {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "<text>"}}

사용 목적:
  메인 세션이 사용자 turn마다 칸반 보드 현황 + 활성 워크플로우 세션을 자동으로 인지하도록
  additionalContext로 주입한다. 워크플로우 세션에서는 W03 디스패처가 호출을 생략하므로
  이 모듈은 메인 세션 식별 로직을 포함하지 않는다.

출력 제한:
  - 페이로드 4096 chars 초과 시 Open/In Progress 상세는 상위 10건만 표기
  - 0.8s soft deadline: 초과 시 partial 페이로드 출력 후 종료

실패 정책:
  - 어떤 예외에서도 exit 0 + 빈 stdout 보장 (사용자 turn 차단 금지)
"""

from __future__ import annotations

import glob
import json
import os
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from typing import Any

# ── 상수 ─────────────────────────────────────────────────────────────────────

MAX_PAYLOAD_CHARS = 4096
MAX_DETAIL_ITEMS = 10
SESSIONS_TIMEOUT = 0.7   # flow-sessions subprocess timeout (초)
SOFT_DEADLINE = 0.8      # 전체 soft deadline (초)

# 컬럼 디렉터리명 → 표시 레이블
COLUMN_LABELS: dict[str, str] = {
    "open": "Open",
    "progress": "In Progress",
    "review": "Review",
    "todo": "To Do",
    "done": "Done",
}

# ── 프로젝트 루트 탐색 ────────────────────────────────────────────────────────

def _find_project_root() -> str:
    """dispatcher.py 와 동일 로직: git-common-dir 로 메인 리포 루트 탐색."""
    d = os.path.dirname(os.path.abspath(__file__))
    # .claude-organic/engine/hook-handlers/ → project root = ../../..
    root = os.path.normpath(os.path.join(d, '..', '..', '..'))

    # 메인 리포이면 그대로 반환 (.settings 존재 확인)
    if os.path.exists(os.path.join(root, '.claude-organic', '.settings')):
        return root

    # 워크트리일 수 있음 — git-common-dir로 메인 리포 탐색
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'],
            capture_output=True, text=True, timeout=5, cwd=root,
        )
        if result.returncode == 0:
            git_common = result.stdout.strip()
            main_root = os.path.dirname(git_common)
            main_cw_dir = os.path.join(main_root, '.claude-organic')
            if os.path.exists(os.path.join(main_cw_dir, '.settings')):
                return main_root
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return root


# ── 칸반 요약 수집 ─────────────────────────────────────────────────────────────

def _parse_ticket_header(xml_path: str) -> dict[str, str] | None:
    """XML 파일에서 metadata 필드만 빠르게 추출한다.

    ET.iterparse를 사용하여 metadata 섹션 파싱 후 조기 중단.
    입력/출력:
        xml_path: T-NNN.xml 절대경로
        return: {"number": "T-NNN", "title": "...", "status": "..."} 또는 None
    """
    try:
        fields: dict[str, str] = {}
        target_tags = {"number", "title", "status"}
        context = ET.iterparse(xml_path, events=("end",))
        for _event, elem in context:
            tag = elem.tag
            if tag in target_tags:
                text = (elem.text or "").strip()
                if text:
                    fields[tag] = text
                # 세 필드 모두 모으면 조기 중단
                if len(fields) >= 3:
                    break
            # metadata 닫힘 태그 이후는 불필요 — 조기 중단
            if tag == "metadata" and len(fields) >= 1:
                break
        if "number" not in fields:
            return None
        return fields
    except Exception:
        return None


def _collect_kanban_summary(project_root: str) -> dict[str, Any]:
    """칸반 컬럼별 티켓 요약을 수집한다.

    open/progress/review 컬럼은 ID + 제목 + status 추출.
    todo/done 컬럼은 카운트만 반환 (페이로드 부피 절감).

    입력: project_root — 메인 리포 루트 경로
    출력: {
        "counts": {"open": N, "progress": M, "review": K, "todo": A, "done": B},
        "details": [{"number": "T-NNN", "title": "...", "status": "...", "column": "open"}, ...]
    }
    """
    tickets_dir = os.path.join(project_root, '.claude-organic', 'tickets')
    counts: dict[str, int] = {}
    details: list[dict[str, str]] = []

    for col in ("open", "progress", "review", "todo", "done"):
        col_dir = os.path.join(tickets_dir, col)
        if not os.path.isdir(col_dir):
            counts[col] = 0
            continue

        xml_files = glob.glob(os.path.join(col_dir, "T-*.xml"))
        counts[col] = len(xml_files)

        # todo/done 은 카운트만 (상세 불필요)
        if col in ("todo", "done"):
            continue

        for xml_path in sorted(xml_files):
            header = _parse_ticket_header(xml_path)
            if header:
                details.append({
                    "number": header.get("number", ""),
                    "title": header.get("title", ""),
                    "status": header.get("status", ""),
                    "column": col,
                })

    return {"counts": counts, "details": details}


# ── 활성 세션 수집 ─────────────────────────────────────────────────────────────

def _parse_sessions_json(raw: str) -> list[dict[str, str]]:
    """flow-sessions --json 출력을 dict 리스트로 정규화한다.

    flow-sessions --json 은 세션 배열 JSON 또는 빈 배열을 반환한다.
    출력 형식: [{"ticket": "T-NNN", "command": "implement", "started_at": "HHMMSS", "status": "running"}, ...]
    """
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        sessions: list[dict[str, str]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            sessions.append({
                "ticket": str(item.get("ticket_id") or item.get("ticket") or ""),
                "command": str(item.get("command") or ""),
                "started_at": str(item.get("started_at") or item.get("start_time") or ""),
                "status": str(item.get("status") or "running"),
                "registry_key": str(item.get("registry_key") or ""),
            })
        return sessions
    except Exception:
        return []


def _fallback_sessions(project_root: str) -> list[dict[str, str]]:
    """.claude-organic/runs/ 하위 context.json mtime stat fallback.

    Board 서버 미기동 + flow-sessions 실패 시 runs/ 디렉터리 직접 스캔.
    가장 최근 mtime 기준 상위 5개만 반환.
    """
    runs_dir = os.path.join(project_root, '.claude-organic', 'runs')
    if not os.path.isdir(runs_dir):
        return []

    sessions: list[dict[str, str]] = []
    # 새 구조: runs/{registryKey}/.context.json (폴드)
    pattern_new = os.path.join(runs_dir, '*', '.context.json')
    # 구 구조 fallback: runs/{registryKey}/{slug}/implement/.context.json
    pattern_old = os.path.join(runs_dir, '*', '*', 'implement', '.context.json')
    ctx_files = glob.glob(pattern_new) + glob.glob(pattern_old)

    for ctx_path in ctx_files:
        try:
            mtime = os.path.getmtime(ctx_path)
            with open(ctx_path, 'r', encoding='utf-8') as f:
                ctx = json.load(f)
            if not isinstance(ctx, dict):
                continue
            ticket = str(ctx.get("ticket_id") or ctx.get("ticketNumber") or "")
            command = str(ctx.get("command") or "")
            registry_key = str(ctx.get("registry_key") or ctx.get("registryKey") or "")
            started_at = ""
            if registry_key and len(registry_key) >= 15:
                # registryKey = YYYYMMDD-HHMMSS → HHMMSS 추출
                started_at = registry_key[9:15] if "-" in registry_key else registry_key[-6:]
            sessions.append({
                "ticket": ticket,
                "command": command,
                "started_at": started_at,
                "status": "running",
                "registry_key": registry_key,
                "_mtime": mtime,  # 정렬용
            })
        except Exception:
            continue

    # mtime 내림차순 정렬 후 상위 5개만
    sessions.sort(key=lambda x: float(x.get("_mtime", 0)), reverse=True)
    for s in sessions:
        s.pop("_mtime", None)

    return sessions[:5]


def _collect_active_sessions(project_root: str) -> list[dict[str, str]]:
    """활성 워크플로우 세션 목록을 수집한다.

    1차: flow-sessions --json subprocess 호출 (timeout=0.7s)
    2차 fallback: .claude-organic/runs/ 직접 stat

    출력: [{"ticket": "T-NNN", "command": "implement", "started_at": "HHMMSS", "status": "running"}, ...]
    """
    bin_dir = os.path.join(project_root, '.claude-organic', 'bin')
    flow_sessions = os.path.join(bin_dir, 'flow-sessions')

    if os.path.isfile(flow_sessions):
        try:
            result = subprocess.run(
                [flow_sessions, '--json'],
                capture_output=True,
                text=True,
                timeout=SESSIONS_TIMEOUT,
                cwd=project_root,
            )
            if result.returncode == 0 and result.stdout.strip():
                parsed = _parse_sessions_json(result.stdout)
                if parsed is not None:  # 빈 리스트도 유효한 결과
                    return parsed
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError, Exception):
            pass

    # fallback: runs/ 직접 스캔
    return _fallback_sessions(project_root)


# ── 컨텍스트 포맷팅 ────────────────────────────────────────────────────────────

def _format_hhmm(started_at: str) -> str:
    """HHMMSS 또는 YYYYMMDD-HHMMSS 형식에서 HH:MM 추출."""
    s = started_at.strip()
    if not s:
        return ""
    # ISO datetime 형식 처리
    if "T" in s or " " in s:
        parts = s.replace("T", " ").split(" ")
        if len(parts) >= 2:
            time_part = parts[1][:5]  # HH:MM
            return time_part
    # HHMMSS 형식
    if len(s) >= 6 and s.isdigit():
        return f"{s[:2]}:{s[2:4]}"
    # 기타: 그대로 반환 (최대 8자)
    return s[:8]


def _format_context(
    kanban: dict[str, Any],
    sessions: list[dict[str, str]],
) -> str:
    """칸반 요약 + 활성 세션을 markdown 형식으로 합성한다.

    출력 예시:
        ## 칸반 스냅샷 (자동 주입, 사용자 turn 시점)
        - Open: 1건, In Progress: 1건, Review: 6건 / To Do: 41건, Done: 358건

        ### Open / In Progress 상세



        ### 활성 세션

    """
    counts = kanban.get("counts", {})
    details = kanban.get("details", [])

    open_c = counts.get("open", 0)
    progress_c = counts.get("progress", 0)
    review_c = counts.get("review", 0)
    todo_c = counts.get("todo", 0)
    done_c = counts.get("done", 0)

    lines: list[str] = []
    lines.append("## 칸반 스냅샷 (자동 주입, 사용자 turn 시점)")
    lines.append(
        f"- Open: {open_c}건, In Progress: {progress_c}건, Review: {review_c}건"
        f" / To Do: {todo_c}건, Done: {done_c}건"
    )

    # Open / In Progress 상세
    if details:
        # 최대 MAX_DETAIL_ITEMS 건 제한
        display_details = details[:MAX_DETAIL_ITEMS]
        lines.append("")
        lines.append("### Open / In Progress 상세")
        for item in display_details:
            number = item.get("number", "")
            title = item.get("title", "")
            status = item.get("status", "")
            label = "In Progress" if "progress" in status.lower() or "in progress" in status.lower() else status
            lines.append(f"- {number} [{label}] {title}")
        if len(details) > MAX_DETAIL_ITEMS:
            lines.append(f"  _(상위 {MAX_DETAIL_ITEMS}건만 표시, 전체 {len(details)}건)_")

    # 활성 세션
    if sessions:
        lines.append("")
        lines.append("### 활성 세션")
        for session in sessions:
            ticket = session.get("ticket", "")
            command = session.get("command", "")
            started = _format_hhmm(session.get("started_at", ""))
            time_str = f" ({started})" if started else ""
            lines.append(f"- {ticket} {command}{time_str}")

    return "\n".join(lines)


# ── 메인 ──────────────────────────────────────────────────────────────────────

def build_context(project_root: str | None = None) -> str:
    """칸반 + 세션 스냅샷 컨텍스트 텍스트를 빌드한다.

    외부에서 직접 호출 가능한 진입점 (W03 디스패처에서 import 가능).

    Args:
        project_root: 메인 리포 루트 경로. None이면 자동 탐색.

    Returns:
        markdown 형식의 컨텍스트 텍스트. 실패 시 빈 문자열.
    """
    if project_root is None:
        project_root = _find_project_root()

    kanban = _collect_kanban_summary(project_root)
    sessions = _collect_active_sessions(project_root)
    return _format_context(kanban, sessions)


def main() -> None:
    """UserPromptSubmit hook 컨텍스트 빌더 메인 함수.

    stdin: UserPromptSubmit JSON 페이로드 (내용 무시)
    stdout: {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "<text>"}}
    exit code: 항상 0 (사용자 turn 차단 금지)

    0.8s soft deadline: 초과 시 partial 페이로드 출력.
    페이로드 4096 chars 초과 시 Open/In Progress 상세는 상위 10건만.
    """
    start_time = time.monotonic()

    # soft deadline 초과 시 SIGALRM으로 partial 출력 후 종료
    # (SIGALRM은 Unix 전용)
    deadline_hit = [False]

    def _on_deadline(_signum: int, _frame: Any) -> None:
        deadline_hit[0] = True

    try:
        if hasattr(signal, 'SIGALRM'):
            signal.signal(signal.SIGALRM, _on_deadline)
            # 0.8s + 여유 0.05s (float → int 올림)
            signal.setitimer(signal.ITIMER_REAL, SOFT_DEADLINE)
    except Exception:
        pass

    try:
        # stdin 읽기 (내용 무시 가능, 단 block 없이 빠르게)
        _stdin_raw = sys.stdin.buffer.read()

        if deadline_hit[0]:
            sys.exit(0)

        project_root = _find_project_root()

        if deadline_hit[0]:
            sys.exit(0)

        context_text = build_context(project_root)

        if deadline_hit[0] and not context_text:
            sys.exit(0)

        # 페이로드 4096 chars 초과 시 트리밍
        if len(context_text) > MAX_PAYLOAD_CHARS:
            context_text = context_text[:MAX_PAYLOAD_CHARS] + "\n_(트리밍됨)_"

        elapsed = time.monotonic() - start_time
        if elapsed > SOFT_DEADLINE and not context_text:
            sys.exit(0)

        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context_text,
            }
        }

        sys.stdout.write(json.dumps(output, ensure_ascii=False))
        sys.stdout.flush()

    except Exception:
        # 어떤 예외에서도 빈 stdout + exit 0 보장
        pass
    finally:
        # SIGALRM 해제
        try:
            if hasattr(signal, 'SIGALRM'):
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, signal.SIG_DFL)
        except Exception:
            pass

    sys.exit(0)


if __name__ == '__main__':
    main()
