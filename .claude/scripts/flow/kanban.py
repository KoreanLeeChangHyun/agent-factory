#!/usr/bin/env -S python3 -u
"""
kanban.py - 칸반 보드 상태 관리 CLI 스크립트.

XML 티켓 파일(.kanban/T-NNN.xml)을 Single Source of Truth(SSoT)로 사용하며,
board.html은 XML 데이터를 기반으로 자동 생성되는 정적 뷰이다.
LLM 호출 없음 (순수 IO).

사용법:
  python3 kanban.py create <title>
  python3 kanban.py move <ticket> <target>
  python3 kanban.py done <ticket>
  python3 kanban.py delete <ticket>
  python3 kanban.py add-subnumber <ticket> --command <cmd> --goal "<goal>" --target "<target>" [--workdir <path>] [--result "<text>"]
  python3 kanban.py update-subnumber <ticket> --id <N> --workdir <path> --result "<text>"

서브커맨드:
  create          새 티켓 XML을 생성하고 board.html을 재생성한다
  move            티켓 상태를 변경하고 board.html을 재생성한다
  done            티켓을 Done으로 변경하고 파일을 .kanban/done/으로 이동한다
  delete          티켓 XML 파일을 삭제하고 board.html을 재생성한다
  add-subnumber   티켓 XML에 새 subnumber 항목을 추가한다
  update-subnumber 기존 subnumber의 workdir/result 필드를 갱신한다

티켓 번호 형식:
  T-NNN, NNN, #N 형식을 모두 지원하며 내부적으로 T-NNN으로 정규화한다.

상태 전이 규칙:
  Open → In Progress → Review → Done (정방향)
  모든 상태 → Open (재오픈)
  --force 플래그로 규칙 무시 가능

종료 코드:
  0  성공
  1  에러 (티켓 없음, 잘못된 전이 등)
  2  인자 오류
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, NoReturn

# ─── 경로 상수 ───────────────────────────────────────────────────────────────

_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT: str = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
_SCRIPTS_DIR: str = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# ─── 상수 ───────────────────────────────────────────────────────────────────

# 컬럼 이름 매핑: CLI 인자 → 컬럼명
COLUMN_MAP: dict[str, str] = {
    "open": "Open",
    "progress": "In Progress",
    "review": "Review",
    "done": "Done",
}

# 허용 상태 전이 규칙: 현재 상태 → 허용 대상 목록
# Done으로의 이동은 done 서브커맨드(force=True)만 허용.
# move 커맨드로 Done 직접 이동은 불가 (Review → Done도 done 서브커맨드 사용 필요).
ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "Open": ["In Progress"],
    "In Progress": ["Review", "Open"],
    "Review": ["Open", "In Progress"],
    "Done": ["Open"],
}

# board.html 경로
_BOARD_PATH: str = os.path.join(_PROJECT_ROOT, ".kanban", "board.html")
_KANBAN_DIR: str = os.path.join(_PROJECT_ROOT, ".kanban")


# ─── XML 헬퍼 ────────────────────────────────────────────────────────────────


def _create_ticket_xml(ticket_number: str, title: str = "", datetime_str: str = "") -> str:
    """티켓 XML 문자열을 생성하여 반환한다.

    XML은 meta/current/history 섹션 주석으로 구분된다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).
        title: 티켓 제목. 빈 문자열 허용.
        datetime_str: 생성 일시 문자열 (YYYY-MM-DD HH:MM:SS 형식). 빈 문자열이면 현재 시간 사용.

    Returns:
        UTF-8 XML 선언을 포함한 티켓 XML 문자열.
    """
    root = ET.Element("ticket")
    # <!-- 메타데이터 --> 섹션
    meta_comment = ET.Comment(" 메타데이터 ")
    root.append(meta_comment)
    ET.SubElement(root, "number").text = ticket_number
    # <title>을 <number> 다음에 배치
    title_elem = ET.SubElement(root, "title")
    if title:
        title_elem.text = title
    ET.SubElement(root, "datetime").text = datetime_str or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ET.SubElement(root, "status").text = "Open"
    # <!-- 현재 프롬프트 --> 섹션
    current_comment = ET.Comment(" 현재 프롬프트 ")
    root.append(current_comment)
    ET.SubElement(root, "current").text = "0"
    # <!-- 이전 프롬프트 --> 섹션 (subnumber가 추가되면 여기 아래에 위치)
    history_comment = ET.Comment(" 이전 프롬프트 ")
    root.append(history_comment)
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=False)


def _write_ticket_xml(filepath: str, root: ET.Element) -> None:
    """XML Element를 파일에 저장한다.

    subnumber 요소 사이에 빈 줄을 삽입하여 가독성을 높인다.

    Args:
        filepath: 저장할 파일 경로.
        root: 저장할 XML 루트 Element.
    """
    ET.indent(root, space="  ")
    xml_str = ET.tostring(root, encoding="unicode")
    # </subnumber> 다음 <subnumber 앞에 빈 줄 삽입 (결함 #9, #11)
    xml_str = re.sub(r"(</subnumber>)\s*(<subnumber)", r"\1\n\n  \2", xml_str)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(xml_str)
        f.write("\n")


def _parse_ticket_xml(filepath: str) -> dict[str, Any]:
    """티켓 XML 파일을 파싱하여 딕셔너리로 반환한다.

    Args:
        filepath: 파싱할 티켓 파일 경로.

    Returns:
        파싱된 티켓 정보 딕셔너리:
            - number (str): 티켓 번호
            - status (str): 현재 상태
            - current (int): 현재 subnumber ID
            - title (str): 티켓 제목
            - subnumbers (list[dict]): subnumber 목록

    Raises:
        SystemExit: 파일 읽기 실패 또는 XML 파싱 오류 시.
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        _err(f"티켓 파일 파싱 실패 ({filepath}): {e}")

    def _text(elem: ET.Element, tag: str, default: str = "") -> str:
        """자식 Element의 텍스트를 반환하는 헬퍼."""
        child = elem.find(tag)
        return child.text.strip() if child is not None and child.text else default

    subnumbers: list[dict[str, Any]] = []
    for sub in root.findall("subnumber"):
        sub_id = sub.get("id", "")
        sub_data: dict[str, Any] = {"id": int(sub_id) if sub_id.isdigit() else 0}
        for child in sub:
            tag = child.tag
            text = child.text.strip() if child.text else ""
            sub_data[tag] = text
        subnumbers.append(sub_data)

    return {
        "number": _text(root, "number"),
        "status": _text(root, "status"),
        "current": int(_text(root, "current", "0")),
        "title": _text(root, "title"),
        "subnumbers": subnumbers,
    }


def _add_subnumber(filepath: str, subnumber_data: dict[str, Any]) -> int:
    """티켓 XML에 새 subnumber를 추가하고 <current>를 갱신한다.

    신규 subnumber는 <current> 요소 바로 다음(기존 subnumber보다 상단)에 삽입하여
    최신 항목이 XML 상단에 위치하도록 한다 (결함 #8).
    새 subnumber에 active="true" 속성을 설정하고 기존 subnumber의 active 속성을 제거 (결함 #10).
    프롬프트 5요소 태그(goal, target, constraints, criteria, context)를 지원 (결함 #12).

    Args:
        filepath: 티켓 파일 경로.
        subnumber_data: 추가할 subnumber 필드 딕셔너리.
            공통 필드: command, goal, target, context, datetime, workdir(선택), result(선택)
            프롬프트 5요소: goal, target, context, constraints(선택), criteria(선택)

    Returns:
        새로 추가된 subnumber의 ID (정수).

    Raises:
        SystemExit: 파일 읽기/쓰기 실패 시.
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        _err(f"티켓 파일 파싱 실패 ({filepath}): {e}")

    current_elem = root.find("current")
    current_val = int(current_elem.text.strip()) if current_elem is not None and current_elem.text else 0
    new_id = current_val + 1

    # 기존 subnumber들의 active 속성 제거 (결함 #10)
    for existing_sub in root.findall("subnumber"):
        if "active" in existing_sub.attrib:
            del existing_sub.attrib["active"]

    # 신규 subnumber 요소 생성 (active="true" 설정, 결함 #10)
    sub_elem = ET.Element("subnumber")
    sub_elem.set("id", str(new_id))
    sub_elem.set("active", "true")

    # datetime 필드 (없으면 현재 시간)
    dt_str = subnumber_data.get("datetime", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    ET.SubElement(sub_elem, "datetime").text = dt_str

    # 공통 필수 필드 (command, goal, target, context)
    for field in ("command", "goal", "target", "context"):
        if field in subnumber_data:
            ET.SubElement(sub_elem, field).text = str(subnumber_data[field])

    # 프롬프트 5요소 선택 필드 (constraints, criteria, 결함 #12)
    for field in ("constraints", "criteria"):
        if subnumber_data.get(field):
            ET.SubElement(sub_elem, field).text = str(subnumber_data[field])

    # 선택 필드 (workdir, result)
    for field in ("workdir", "result"):
        if subnumber_data.get(field):
            ET.SubElement(sub_elem, field).text = str(subnumber_data[field])

    # <current> 요소 바로 다음에 삽입 (최신 항목이 XML 상단에 위치, 결함 #8)
    current_idx: int | None = None
    for i, child in enumerate(root):
        if child.tag == "current":
            current_idx = i
            break

    if current_idx is not None:
        root.insert(current_idx + 1, sub_elem)
    else:
        root.append(sub_elem)

    # <current> 갱신
    if current_elem is not None:
        current_elem.text = str(new_id)
    else:
        ET.SubElement(root, "current").text = str(new_id)

    _write_ticket_xml(filepath, root)
    return new_id


def _update_subnumber(filepath: str, subnumber_id: int, updates: dict[str, Any]) -> None:
    """기존 subnumber의 필드를 갱신한다.

    Args:
        filepath: 티켓 파일 경로.
        subnumber_id: 갱신할 subnumber ID.
        updates: 갱신할 필드 딕셔너리 (workdir, result 등).

    Raises:
        SystemExit: 파일 읽기/쓰기 실패 또는 subnumber를 찾지 못한 경우.
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        _err(f"티켓 파일 파싱 실패 ({filepath}): {e}")

    target_sub: ET.Element | None = None
    for sub in root.findall("subnumber"):
        if sub.get("id") == str(subnumber_id):
            target_sub = sub
            break

    if target_sub is None:
        _err(f"subnumber id={subnumber_id}를 찾을 수 없습니다: {filepath}")

    for field, value in updates.items():
        existing = target_sub.find(field)
        if existing is not None:
            existing.text = str(value)
        else:
            ET.SubElement(target_sub, field).text = str(value)

    _write_ticket_xml(filepath, root)


def _update_ticket_status(filepath: str, new_status: str) -> None:
    """티켓 XML의 <status> 요소를 갱신한다.

    Args:
        filepath: 티켓 파일 경로.
        new_status: 새 상태 문자열 (예: 'Open', 'In Progress', 'Review', 'Done').

    Raises:
        SystemExit: 파일 읽기/쓰기 실패 시.
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        _err(f"티켓 파일 파싱 실패 ({filepath}): {e}")

    status_elem = root.find("status")
    if status_elem is not None:
        status_elem.text = new_status
    else:
        ET.SubElement(root, "status").text = new_status

    _write_ticket_xml(filepath, root)


# ─── 유틸리티 ────────────────────────────────────────────────────────────────


def _find_ticket_file(ticket_number: str) -> str | None:
    """T-NNN.xml 정확 매칭으로 티켓 파일 경로를 탐색하여 반환한다.

    탐색 순서: .kanban/T-NNN.xml -> .kanban/done/T-NNN.xml

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).

    Returns:
        발견된 파일 절대 경로 문자열. 미발견 시 None.
    """
    primary = os.path.join(_KANBAN_DIR, f"{ticket_number}.xml")
    if os.path.isfile(primary):
        return primary
    done_path = os.path.join(_KANBAN_DIR, "done", f"{ticket_number}.xml")
    if os.path.isfile(done_path):
        return done_path
    return None


def _err(msg: str, code: int = 1) -> NoReturn:
    """에러 메시지를 stderr에 출력하고 종료한다.

    Args:
        msg: 에러 메시지
        code: 종료 코드 (기본값 1)
    """
    print(f"에러: {msg}", file=sys.stderr)
    sys.exit(code)


def _normalize_ticket_number(raw: str) -> str | None:
    """티켓 번호 문자열을 'T-NNN' 형식으로 정규화한다.

    T-NNN, NNN, #N 형식을 모두 지원한다.

    Args:
        raw: 원본 티켓 번호 문자열 (예: '#1', 'T-001', '001', '1')

    Returns:
        정규화된 'T-NNN' 형식 문자열. 변환 불가능하면 None.
    """
    raw = raw.strip().lstrip("#")
    # 이미 T-NNN 형식
    if re.match(r"^T-\d+$", raw, re.IGNORECASE):
        parts = raw.split("-")
        num = int(parts[1])
        return f"T-{num:03d}"
    # 순수 숫자
    if re.match(r"^\d+$", raw):
        return f"T-{int(raw):03d}"
    return None


# ─── 보드 생성 (XML → JSON → HTML) ──────────────────────────────────────────


def _scan_all_tickets() -> list[dict]:
    """Scan .kanban/*.xml and .kanban/done/*.xml, parse each, return list of ticket dicts.

    Each dict has: number, title, status, datetime.

    Returns:
        티켓 정보 딕셔너리 리스트.
    """
    tickets: list[dict] = []
    for d in [_KANBAN_DIR, os.path.join(_KANBAN_DIR, "done")]:
        if not os.path.isdir(d):
            continue
        for fname in os.listdir(d):
            if not re.match(r"^T-\d+\.xml$", fname):
                continue
            filepath = os.path.join(d, fname)
            try:
                data = _parse_ticket_xml(filepath)
                tickets.append({
                    "number": data["number"],
                    "title": data["title"],
                    "status": data["status"],
                    "datetime": data.get("datetime", ""),
                })
            except SystemExit:
                # 파싱 실패한 파일은 스킵
                continue
    return tickets


def _get_max_ticket_number() -> int:
    """Scan .kanban/ and .kanban/done/ XML filenames to find max T-NNN number.

    Returns:
        현재 최대 티켓 번호 정수. 티켓이 없으면 0.
    """
    max_num = 0
    for d in [_KANBAN_DIR, os.path.join(_KANBAN_DIR, "done")]:
        if not os.path.isdir(d):
            continue
        for fname in os.listdir(d):
            m = re.match(r"^T-(\d+)\.xml$", fname)
            if m:
                num = int(m.group(1))
                if num > max_num:
                    max_num = num
    return max_num


_BOARD_TEMPLATE: str = """\
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Claude Code Workflow Kanbanboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  ::-webkit-scrollbar { width: 0; }
  html, body {
    height: 100%;
    overflow: hidden;
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: #0d1117;
    color: #c9d1d9;
    padding: 8px;
    display: flex;
    flex-direction: column;
  }
  h1 {
    font-size: 14px;
    font-weight: 600;
    color: #e6edf3;
    margin-bottom: 6px;
  }
  .board {
    display: flex;
    gap: 8px;
    flex: 1;
    min-height: 0;
  }
  .column {
    flex: 1;
    min-width: 0;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    display: flex;
    flex-direction: column;
  }
  .column-header {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 10px 12px;
    border-bottom: 1px solid #30363d;
    font-size: 12px;
    font-weight: 600;
    color: #e6edf3;
  }
  .column-header .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }
  .dot-open     { background: #3fb950; }
  .dot-progress { background: #d29922; }
  .dot-review   { background: #a371f7; }
  .dot-done     { background: #8b949e; }
  .column-header .count {
    color: #8b949e;
    font-weight: 400;
    margin-left: auto;
  }
  .cards {
    padding: 8px;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .card {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 10px 12px;
    cursor: pointer;
    transition: border-color 0.15s;
  }
  .card:hover {
    border-color: #58a6ff;
  }
  .card-title {
    font-size: 12px;
    font-weight: 500;
    color: #e6edf3;
    line-height: 1.4;
  }
  .card-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 6px;
    font-size: 11px;
    color: #58a6ff;
    font-weight: 600;
  }
  a.card {
    text-decoration: none;
    display: block;
    color: inherit;
  }
  .card.done {
    opacity: 0.6;
  }
  .empty {
    font-size: 11px;
    color: #484f58;
    text-align: center;
    padding: 16px 0;
  }
</style>
</head>
<body>
<h1>Claude Code Workflow Kanbanboard</h1>
<div class="board" id="board"></div>

<script>
const TICKETS = [];

const COLUMNS = [
  { key: "Open", display: "Open", dot: "dot-open" },
  { key: "In Progress", display: "Progress", dot: "dot-progress" },
  { key: "Review", display: "Review", dot: "dot-review" },
  { key: "Done", display: "Done", dot: "dot-done" }
];

function render() {
  const board = document.getElementById("board");
  board.innerHTML = "";

  COLUMNS.forEach(col => {
    const tickets = TICKETS.filter(t => t.status === col.key);
    const column = document.createElement("div");
    column.className = "column";

    const header = document.createElement("div");
    header.className = "column-header";
    header.innerHTML = '<span class="dot ' + col.dot + '"></span> ' + col.display + ' <span class="count">' + tickets.length + '</span>';
    column.appendChild(header);

    const cards = document.createElement("div");
    cards.className = "cards";

    if (tickets.length === 0) {
      cards.innerHTML = '<div class="empty">No items</div>';
    } else {
      tickets.forEach(t => {
        const card = document.createElement("div");
        card.className = col.key === "Done" ? "card done" : "card";
        card.innerHTML = '<div class="card-title">' + escapeHtml(t.title || "") + '</div><div class="card-meta">' + t.number + '</div>';
        cards.appendChild(card);
      });
    }

    column.appendChild(cards);
    board.appendChild(column);
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

render();
</script>
</body>
</html>
"""


def _regenerate_board() -> None:
    """Read all XML tickets, convert to JSON array, inject into board.html template.

    The HTML template contains CSS+JS that renders the kanban board from the JSON data.
    """
    tickets = _scan_all_tickets()
    tickets_json = json.dumps(tickets, ensure_ascii=False, indent=2)
    html = _BOARD_TEMPLATE.replace(
        'const TICKETS = [];',
        f'const TICKETS = {tickets_json};'
    )
    os.makedirs(os.path.dirname(_BOARD_PATH), exist_ok=True)
    with open(_BOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html)


# ─── 서브커맨드 구현 ─────────────────────────────────────────────────────────


def cmd_create(title: str, command: str) -> None:
    """새 티켓 XML을 생성하고 board.html을 재생성한다.

    XML 파일명에서 최대 T-NNN 번호를 스캔하여 +1 채번 후,
    .kanban/T-NNN.xml 파일을 생성하고 board.html을 재생성한다.

    Args:
        title: 티켓 제목. 빈 문자열 허용.
        command: 워크플로우 커맨드 (implement, review, research 등). 현재 미사용 (하위 호환용).
    """
    max_num = _get_max_ticket_number()
    new_num = max_num + 1
    ticket_number = f"T-{new_num:03d}"

    # 파일명: T-NNN.xml 고정
    ticket_file = os.path.join(_KANBAN_DIR, f"{ticket_number}.xml")

    os.makedirs(_KANBAN_DIR, exist_ok=True)
    datetime_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    xml_content = _create_ticket_xml(ticket_number, title, datetime_str)
    try:
        with open(ticket_file, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(xml_content)
            f.write("\n")
    except OSError as e:
        _err(f"티켓 파일 생성 실패: {e}")

    _regenerate_board()

    suffix = f" ({command})" if command else ""
    print(f"{ticket_number}: {title}{suffix}")


def cmd_move(ticket_number: str, target_key: str, force: bool = False) -> None:
    """티켓 상태를 변경하고 board.html을 재생성한다.

    허용 상태 전이 규칙을 검증하고, 위반 시 에러를 출력한다.
    --force 플래그가 있으면 규칙을 무시하고 강제 이동한다.
    XML <status> 요소를 갱신한 후 board.html을 재생성한다.

    Args:
        ticket_number: 이동할 티켓 번호 (T-NNN 형식).
        target_key: 대상 컬럼 키 (open/progress/review/done).
        force: 강제 이동 여부.

    Raises:
        SystemExit: 티켓이 없거나 전이 규칙 위반 시.
    """
    target_section = COLUMN_MAP.get(target_key)
    if target_section is None:
        _err(f"잘못된 대상 컬럼: '{target_key}'. 허용값: {', '.join(COLUMN_MAP.keys())}")

    ticket_file = _find_ticket_file(ticket_number)
    if ticket_file is None:
        _err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

    ticket_data = _parse_ticket_xml(ticket_file)
    current_section = ticket_data["status"]

    # 이미 같은 상태이면 무시
    if current_section == target_section:
        print(f"{ticket_number}은 이미 {target_section} 상태입니다.")
        return

    # 상태 전이 규칙 검증
    allowed = ALLOWED_TRANSITIONS.get(current_section, [])
    if target_section not in allowed and not force:
        _err(
            f"{ticket_number}은 현재 {current_section}이므로 {target_section}으로 이동할 수 없습니다. "
            f"--force 플래그로 강제 이동 가능"
        )

    # XML <status> 갱신
    _update_ticket_status(ticket_file, target_section)

    _regenerate_board()

    print(f"{ticket_number}: {current_section} → {target_section}")


def cmd_done(ticket_number: str) -> None:
    """티켓을 Done으로 변경하고 파일을 .kanban/done/으로 이동한다.

    XML의 <status>를 Done으로 갱신하고,
    .kanban/T-NNN.xml를 .kanban/done/T-NNN.xml로 이동한 뒤 board.html을 재생성한다.

    Args:
        ticket_number: 완료할 티켓 번호 (T-NNN 형식).
    """
    ticket_file = _find_ticket_file(ticket_number)
    if ticket_file is None:
        _err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

    ticket_data = _parse_ticket_xml(ticket_file)
    current_section = ticket_data["status"]

    # XML <status> Done으로 갱신
    _update_ticket_status(ticket_file, "Done")

    # 파일을 .kanban/done/T-NNN.xml로 이동
    done_dir = os.path.join(_KANBAN_DIR, "done")
    dst_filename = f"{ticket_number}.xml"
    dst_file = os.path.join(done_dir, dst_filename)

    if os.path.isfile(ticket_file):
        os.makedirs(done_dir, exist_ok=True)
        try:
            shutil.move(ticket_file, dst_file)
        except OSError as e:
            _err(f"티켓 파일 이동 실패: {e}")
        src_rel = os.path.relpath(ticket_file, _PROJECT_ROOT)
        print(f"파일 이동: {src_rel} → .kanban/done/{dst_filename}")

    _regenerate_board()

    print(f"{ticket_number}: {current_section} → Done")


def cmd_delete(ticket_number: str) -> None:
    """티켓 XML 파일을 삭제하고 board.html을 재생성한다.

    Done과 달리 히스토리를 보존하지 않고 파일을 삭제한다.

    Args:
        ticket_number: 삭제할 티켓 번호 (T-NNN 형식).

    Raises:
        SystemExit: 티켓을 찾을 수 없는 경우.
    """
    ticket_file = _find_ticket_file(ticket_number)
    if ticket_file is None:
        _err(f"{ticket_number} 티켓을 찾을 수 없습니다")

    try:
        os.remove(ticket_file)
    except OSError as e:
        _err(f"티켓 파일 삭제 실패: {e}")

    _regenerate_board()

    print(f"{ticket_number}: 삭제됨")


def cmd_add_subnumber(
    ticket_number: str,
    command: str,
    goal: str,
    target: str,
    workdir: str = "",
    result: str = "",
    constraints: str = "",
    criteria: str = "",
    context: str = "",
) -> None:
    """티켓 XML에 새 subnumber 항목을 추가한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).
        command: 워크플로우 커맨드 (implement, review, research 등).
        goal: 해당 사이클 목표.
        target: 대상.
        workdir: .workflow/ 산출물 경로 (선택).
        result: 실행 결과 요약 (선택).
        constraints: 제약사항 (선택, 프롬프트 5요소).
        criteria: 완료 기준 (선택, 프롬프트 5요소).
        context: 맥락 정보 (선택, 프롬프트 5요소).

    Raises:
        SystemExit: 티켓 파일을 찾을 수 없거나 쓰기 실패 시.
    """
    ticket_file = _find_ticket_file(ticket_number)
    if ticket_file is None:
        _err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

    subnumber_data: dict[str, Any] = {
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "command": command,
        "goal": goal,
        "target": target,
    }
    if constraints:
        subnumber_data["constraints"] = constraints
    if criteria:
        subnumber_data["criteria"] = criteria
    if context:
        subnumber_data["context"] = context
    if workdir:
        subnumber_data["workdir"] = workdir
    if result:
        subnumber_data["result"] = result

    new_id = _add_subnumber(ticket_file, subnumber_data)
    print(f"{ticket_number}: subnumber id={new_id} 추가됨")


def cmd_update_subnumber(
    ticket_number: str,
    subnumber_id: int,
    workdir: str = "",
    result: str = "",
) -> None:
    """기존 subnumber의 workdir/result 필드를 갱신한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).
        subnumber_id: 갱신할 subnumber ID.
        workdir: 갱신할 workdir 경로 (선택).
        result: 갱신할 결과 요약 (선택).

    Raises:
        SystemExit: 티켓 파일을 찾을 수 없거나 쓰기 실패 시.
    """
    ticket_file = _find_ticket_file(ticket_number)
    if ticket_file is None:
        _err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

    updates: dict[str, Any] = {}
    if workdir:
        updates["workdir"] = workdir
    if result:
        updates["result"] = result

    if not updates:
        _err("갱신할 필드가 없습니다. --workdir 또는 --result를 지정하세요.", 2)

    _update_subnumber(ticket_file, subnumber_id, updates)
    print(f"{ticket_number}: subnumber id={subnumber_id} 갱신됨")


# ─── argparse 설정 ───────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    """argparse 기반 CLI 파서를 구성하여 반환한다.

    Returns:
        구성된 ArgumentParser 인스턴스.
    """
    parser = argparse.ArgumentParser(
        prog="kanban.py",
        description="칸반 보드 상태 관리 CLI",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # create 서브커맨드
    create_parser = subparsers.add_parser("create", help="새 티켓을 생성한다")
    create_parser.add_argument("title", help="티켓 제목")
    create_parser.add_argument("--command", default="", help="워크플로우 커맨드 (implement, review, research 등)")

    # move 서브커맨드
    move_parser = subparsers.add_parser("move", help="티켓을 지정 컬럼으로 이동한다")
    move_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")
    move_parser.add_argument(
        "target",
        choices=list(COLUMN_MAP.keys()),
        help="대상 컬럼 (open/progress/review/done)",
    )
    move_parser.add_argument("--force", action="store_true", help="상태 전이 규칙 무시하고 강제 이동")

    # done 서브커맨드
    done_parser = subparsers.add_parser("done", help="티켓을 Done으로 이동하고 파일을 .kanban/done/으로 이동한다")
    done_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")

    # delete 서브커맨드
    delete_parser = subparsers.add_parser("delete", help="티켓을 삭제한다")
    delete_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")

    # add-subnumber 서브커맨드
    add_sub_parser = subparsers.add_parser("add-subnumber", help="티켓 XML에 새 subnumber 항목을 추가한다")
    add_sub_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")
    add_sub_parser.add_argument("--command", required=True, help="워크플로우 커맨드 (implement, review, research 등)")
    add_sub_parser.add_argument("--goal", required=True, help="해당 사이클 목표")
    add_sub_parser.add_argument("--target", required=True, help="대상")
    add_sub_parser.add_argument("--constraints", default="", help="제약사항 (선택, 프롬프트 5요소)")
    add_sub_parser.add_argument("--criteria", default="", help="완료 기준 (선택, 프롬프트 5요소)")
    add_sub_parser.add_argument("--context", default="", help="맥락 정보 (선택, 프롬프트 5요소)")
    add_sub_parser.add_argument("--workdir", default="", help=".workflow/ 산출물 경로 (선택)")
    add_sub_parser.add_argument("--result", default="", help="실행 결과 요약 (선택)")

    # update-subnumber 서브커맨드
    update_sub_parser = subparsers.add_parser("update-subnumber", help="기존 subnumber의 workdir/result 필드를 갱신한다")
    update_sub_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")
    update_sub_parser.add_argument("--id", dest="subnumber_id", required=True, type=int, help="갱신할 subnumber ID")
    update_sub_parser.add_argument("--workdir", default="", help="갱신할 workdir 경로")
    update_sub_parser.add_argument("--result", default="", help="갱신할 결과 요약")

    return parser


# ─── main ────────────────────────────────────────────────────────────────────


def main() -> None:
    """CLI 진입점. 서브커맨드를 파싱하여 해당 핸들러를 호출한다."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.subcommand == "create":
        cmd_create(args.title, args.command)

    elif args.subcommand == "move":
        ticket = _normalize_ticket_number(args.ticket)
        if ticket is None:
            _err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_move(ticket, args.target, force=args.force)

    elif args.subcommand == "done":
        ticket = _normalize_ticket_number(args.ticket)
        if ticket is None:
            _err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_done(ticket)

    elif args.subcommand == "delete":
        ticket = _normalize_ticket_number(args.ticket)
        if ticket is None:
            _err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_delete(ticket)

    elif args.subcommand == "add-subnumber":
        ticket = _normalize_ticket_number(args.ticket)
        if ticket is None:
            _err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_add_subnumber(
            ticket,
            command=args.command,
            goal=args.goal,
            target=args.target,
            workdir=args.workdir,
            result=args.result,
            constraints=args.constraints,
            criteria=args.criteria,
            context=args.context,
        )

    elif args.subcommand == "update-subnumber":
        ticket = _normalize_ticket_number(args.ticket)
        if ticket is None:
            _err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_update_subnumber(
            ticket,
            subnumber_id=args.subnumber_id,
            workdir=args.workdir,
            result=args.result,
        )


if __name__ == "__main__":
    main()
