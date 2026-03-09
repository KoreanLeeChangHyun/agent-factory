#!/usr/bin/env -S python3 -u
"""reload_prompt.py - 수정 피드백을 워크플로우에 반영하는 스크립트.

현재 워크플로우의 티켓 파일(.kanban/T-NNN.xml)에서 피드백을 읽어
user_prompt.txt에 append하고, .uploads/ 파일 복사를 수행한다.

티켓 파일은 환경변수 TICKET_NUMBER, .context.json의 ticketNumber 필드,
또는 board.html In Progress 컬럼에서 순서대로 탐색한다.

사용법:
  python3 reload_prompt.py <workDir>

인자:
  workDir - 작업 디렉터리 상대 경로

환경변수:
  TICKET_NUMBER  티켓 번호 (T-NNN 또는 NNN 형식)

수행 작업 (순서대로):
  1. .kanban/T-NNN.xml 읽기 (티켓 미발견 또는 비어있으면 경고 후 종료)
  2. <workDir>/user_prompt.txt에 구분선 + 피드백 append
  3. .uploads/ -> <workDir>/files/ 복사 후 .uploads/ 클리어

출력 (stdout):
  피드백 내용 전문
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
_SCRIPTS_DIR = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from data.constants import KST

_KST = KST


def _normalize_ticket_number(raw: str) -> str | None:
    """티켓 번호 문자열을 'T-NNN' 형식으로 정규화한다.

    Args:
        raw: 원본 티켓 번호 문자열 (예: 'T-001', '001', '1')

    Returns:
        정규화된 'T-NNN' 형식 문자열. 변환 불가능하면 None.
    """
    raw = raw.strip().lstrip("#")
    if re.match(r"^T-\d+$", raw, re.IGNORECASE):
        parts = raw.split("-")
        return f"T-{int(parts[1]):03d}"
    if re.match(r"^\d+$", raw):
        return f"T-{int(raw):03d}"
    return None


def _find_ticket_file_by_number(kanban_dir: Path, ticket_number: str) -> str | None:
    """kanban 디렉터리에서 티켓 번호에 해당하는 파일을 정확 매칭으로 탐색한다.

    루트 파일(T-NNN.xml)을 먼저 탐색하고, 없으면 done 서브디렉터리도 탐색한다.

    Args:
        kanban_dir: .kanban 디렉터리 절대 경로
        ticket_number: 'T-NNN' 형식 티켓 번호

    Returns:
        찾은 티켓 파일의 절대 경로 문자열. 없으면 None.
    """
    candidate: Path = kanban_dir / f"{ticket_number}.xml"
    if candidate.is_file():
        return str(candidate)
    # done 서브디렉터리 탐색
    done_candidate: Path = kanban_dir / "done" / f"{ticket_number}.xml"
    if done_candidate.is_file():
        return str(done_candidate)
    return None


def _resolve_ticket_file(abs_work_dir: str) -> str | None:
    """현재 워크플로우에 연결된 티켓 파일 경로를 결정한다.

    탐색 우선순위:
      1. 환경변수 TICKET_NUMBER
      2. .context.json의 ticketNumber 필드
      3. .kanban/board.html In Progress 컬럼의 첫 번째 티켓

    Args:
        abs_work_dir: 현재 워크플로우 디렉터리 절대 경로

    Returns:
        .kanban/T-NNN.xml 절대 경로. 결정 불가능하면 None.
    """
    kanban_dir: Path = Path(_PROJECT_ROOT) / ".kanban"

    # 1순위: 환경변수
    env_ticket = os.environ.get("TICKET_NUMBER", "").strip()
    if env_ticket:
        normalized = _normalize_ticket_number(env_ticket)
        if normalized:
            return _find_ticket_file_by_number(kanban_dir, normalized)

    # 2순위: .context.json ticketNumber
    context_path = os.path.join(abs_work_dir, ".context.json")
    if os.path.isfile(context_path):
        try:
            with open(context_path, "r", encoding="utf-8") as f:
                context = json.load(f)
            ticket_num = context.get("ticketNumber", "").strip()
            if ticket_num:
                normalized = _normalize_ticket_number(ticket_num)
                if normalized:
                    return _find_ticket_file_by_number(kanban_dir, normalized)
        except Exception:
            pass

    # 3순위: board.html In Progress 컬럼
    board_path = os.path.join(_PROJECT_ROOT, ".kanban", "board.html")
    if os.path.isfile(board_path):
        try:
            from html.parser import HTMLParser

            class _InProgressTicketParser(HTMLParser):
                """board.html In Progress 컬럼에서 첫 번째 티켓 번호를 추출하는 파서."""

                def __init__(self) -> None:
                    super().__init__()
                    self._current_column: str | None = None
                    self._in_column_header: bool = False
                    self._in_card_meta: bool = False
                    self._header_text_parts: list[str] = []
                    self._meta_buf: str = ""
                    self._in_count: bool = False
                    self.first_progress_ticket: str | None = None

                def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                    """태그 시작 이벤트를 처리한다."""
                    attr_dict: dict[str, str] = {k: (v or "") for k, v in attrs}
                    cls_parts: list[str] = attr_dict.get("class", "").split()
                    if tag == "div" and "column-header" in cls_parts:
                        self._in_column_header = True
                        self._header_text_parts = []
                    elif tag == "span" and "count" in cls_parts:
                        self._in_count = True
                    elif tag == "div" and "card-meta" in cls_parts and self._current_column == "In Progress":
                        self._in_card_meta = True
                        self._meta_buf = ""

                def handle_endtag(self, tag: str) -> None:
                    """태그 종료 이벤트를 처리한다."""
                    if tag == "div" and self._in_column_header:
                        self._in_column_header = False
                        header_text: str = " ".join(self._header_text_parts).strip()
                        if "Progress" in header_text:
                            self._current_column = "In Progress"
                        elif any(k in header_text for k in ("Open", "Review", "Done")):
                            self._current_column = None
                    elif tag == "span" and self._in_count:
                        self._in_count = False
                    elif tag == "div" and self._in_card_meta:
                        self._in_card_meta = False
                        if self.first_progress_ticket is None:
                            meta_text: str = self._meta_buf.strip()
                            m = re.search(r"T-\d+", meta_text)
                            if m:
                                self.first_progress_ticket = m.group(0)

                def handle_data(self, data: str) -> None:
                    """텍스트 데이터를 처리한다."""
                    if self._in_card_meta and self._current_column == "In Progress":
                        self._meta_buf += data
                    elif self._in_column_header and not self._in_count:
                        self._header_text_parts.append(data.strip())

            with open(board_path, "r", encoding="utf-8") as f:
                content = f.read()
            parser = _InProgressTicketParser()
            parser.feed(content)
            if parser.first_progress_ticket:
                normalized = _normalize_ticket_number(parser.first_progress_ticket)
                if normalized:
                    return _find_ticket_file_by_number(kanban_dir, normalized)
        except Exception:
            pass

    return None


def main() -> None:
    """CLI 진입점. workDir 인자를 받아 티켓 피드백 반영 작업을 수행한다.

    수행 작업:
      1. .kanban/T-NNN.xml 읽기 (티켓 미발견 또는 비어있으면 경고 후 종료)
      2. <workDir>/user_prompt.txt에 구분선 + 피드백 append
      3. .uploads/ 파일을 <workDir>/files/로 복사 후 .uploads/ 클리어

    Raises:
        SystemExit: 인자 누락(1), workDir 미존재(1), 정상 완료(0).
    """
    # --- 인자 확인 ---
    if len(sys.argv) < 2:
        print(f"[ERROR] 사용법: {sys.argv[0]} <workDir>", file=sys.stderr)
        sys.exit(1)

    work_dir = sys.argv[1]
    abs_work_dir = os.path.join(_PROJECT_ROOT, work_dir)

    if not os.path.isdir(abs_work_dir):
        print(f"[ERROR] workDir not found: {work_dir}", file=sys.stderr)
        sys.exit(1)

    ticket_file = _resolve_ticket_file(abs_work_dir)

    # --- Step 1: 티켓 파일 읽기 ---
    feedback = ""
    if ticket_file and os.path.isfile(ticket_file):
        with open(ticket_file, "r", encoding="utf-8") as f:
            feedback = f.read()

    if not feedback:
        print("FAIL", flush=True)
        print("[WARN] 티켓 파일을 찾을 수 없거나 비어있습니다 (.kanban/T-NNN.xml)", flush=True)
        sys.exit(0)

    # --- Step 2: user_prompt.txt에 피드백 append ---
    kst_date = datetime.now(_KST).strftime("%Y-%m-%d %H:%M")
    user_prompt_file = os.path.join(abs_work_dir, "user_prompt.txt")

    with open(user_prompt_file, "a", encoding="utf-8") as f:
        f.write(f"\n\n--- (수정 피드백, {kst_date}) ---\n\n")
        f.write(feedback)

    # --- Step 3: .uploads/ 파일 처리 ---
    uploads_dir = os.path.join(_PROJECT_ROOT, ".uploads")
    if os.path.isdir(uploads_dir) and os.listdir(uploads_dir):
        files_dir = os.path.join(abs_work_dir, "files")
        os.makedirs(files_dir, exist_ok=True)
        for item in os.listdir(uploads_dir):
            src = os.path.join(uploads_dir, item)
            dst = os.path.join(files_dir, item)
            try:
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
            except Exception:
                pass
        # .uploads/ 클리어
        for item in os.listdir(uploads_dir):
            item_path = os.path.join(uploads_dir, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.unlink(item_path)
            except Exception:
                pass

    print(feedback, end="", flush=True)


if __name__ == "__main__":
    main()
