#!/usr/bin/env -S python3 -u
"""
kanban.py - 칸반 보드 상태 관리 CLI 스크립트.

board.md 기반의 티켓 생성, 상태 이동, 완료 처리를 수행한다.
LLM 호출 없음 (순수 IO).

사용법:
  python3 kanban.py create <title> [--command <cmd>]
  python3 kanban.py move <ticket> <target>
  python3 kanban.py done <ticket>

서브커맨드:
  create  새 티켓을 생성하고 Open 섹션에 추가한다
  move    티켓을 지정 컬럼으로 이동한다 (open/progress/review/done)
  done    티켓을 Done으로 이동하고 파일을 .kanban/done/으로 이동한다

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
import os
import re
import shutil
import sys
from typing import NoReturn

# ─── 경로 상수 ───────────────────────────────────────────────────────────────

_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT: str = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
_SCRIPTS_DIR: str = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# ─── 상수 ───────────────────────────────────────────────────────────────────

# 상태 → 파일명 접두사 매핑
STATUS_PREFIX: dict[str, str] = {
    "Open": "open",
    "In Progress": "progress",
    "Review": "review",
    "Done": "done",
}

# 컬럼 이름 매핑: CLI 인자 → board.md 섹션명
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

# board.md 경로
_BOARD_PATH: str = os.path.join(_PROJECT_ROOT, ".kanban", "board.md")
_KANBAN_DIR: str = os.path.join(_PROJECT_ROOT, ".kanban")


# ─── 유틸리티 ────────────────────────────────────────────────────────────────


def _find_ticket_file(ticket_number: str) -> str | None:
    """접두사 포함 패턴으로 티켓 파일 경로를 탐색하여 반환한다.

    .kanban/*-{ticket_number}.txt 패턴으로 탐색하고,
    미발견 시 .kanban/done/*-{ticket_number}.txt도 탐색한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).

    Returns:
        발견된 파일 절대 경로 문자열. 미발견 시 None.
    """
    pattern = os.path.join(_KANBAN_DIR, f"*-{ticket_number}.txt")
    matches = glob.glob(pattern)
    if matches:
        return matches[0]
    done_pattern = os.path.join(_KANBAN_DIR, "done", f"*-{ticket_number}.txt")
    done_matches = glob.glob(done_pattern)
    if done_matches:
        return done_matches[0]
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


def _read_board() -> list[str]:
    """board.md 파일을 읽어 라인 리스트로 반환한다.

    Returns:
        board.md 내용의 라인 리스트.

    Raises:
        SystemExit: 파일이 없거나 읽기 실패 시.
    """
    if not os.path.isfile(_BOARD_PATH):
        _err(f"board.md를 찾을 수 없습니다: {_BOARD_PATH}")
    try:
        with open(_BOARD_PATH, "r", encoding="utf-8") as f:
            return f.readlines()
    except OSError as e:
        _err(f"board.md 읽기 실패: {e}")


def _write_board(lines: list[str]) -> None:
    """라인 리스트를 board.md 파일에 쓴다.

    Args:
        lines: 쓸 라인 리스트.

    Raises:
        SystemExit: 쓰기 실패 시.
    """
    try:
        with open(_BOARD_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except OSError as e:
        _err(f"board.md 쓰기 실패: {e}")


def _find_ticket_column(lines: list[str], ticket_number: str) -> str | None:
    """board.md에서 티켓이 속한 컬럼 이름을 찾는다.

    Args:
        lines: board.md 라인 리스트.
        ticket_number: 찾을 티켓 번호 (T-NNN 형식).

    Returns:
        컬럼 이름 문자열 (예: 'Open', 'In Progress'). 없으면 None.
    """
    ticket_pattern = re.compile(rf"^-\s+\[[ x]\]\s+{re.escape(ticket_number)}\s*:", re.IGNORECASE)
    current_section: str | None = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            current_section = stripped[3:].strip()
            continue
        if current_section and ticket_pattern.match(stripped):
            return current_section
    return None


def _get_max_ticket_number(lines: list[str]) -> int:
    """board.md 전체에서 최대 T-NNN 번호를 파싱하여 반환한다.

    Args:
        lines: board.md 라인 리스트.

    Returns:
        현재 최대 티켓 번호 정수. 티켓이 없으면 0.
    """
    max_num: int = 0
    ticket_pattern = re.compile(r"T-(\d+)", re.IGNORECASE)
    for line in lines:
        for match in ticket_pattern.finditer(line):
            num = int(match.group(1))
            if num > max_num:
                max_num = num
    # .kanban/ 디렉터리의 접두사 포함 티켓 파일도 확인
    if os.path.isdir(_KANBAN_DIR):
        for fname in os.listdir(_KANBAN_DIR):
            m = re.match(r"^(?:open|progress|review|done)-T-(\d+)\.txt$", fname, re.IGNORECASE)
            if m:
                num = int(m.group(1))
                if num > max_num:
                    max_num = num
    # .kanban/done/ 디렉터리도 확인
    done_dir = os.path.join(_KANBAN_DIR, "done")
    if os.path.isdir(done_dir):
        for fname in os.listdir(done_dir):
            m = re.match(r"^(?:open|progress|review|done)-T-(\d+)\.txt$", fname, re.IGNORECASE)
            if m:
                num = int(m.group(1))
                if num > max_num:
                    max_num = num
    return max_num


def _insert_ticket_into_section(lines: list[str], section_name: str, ticket_line: str) -> list[str]:
    """board.md 라인 리스트의 지정 섹션에 티켓 항목을 삽입한다.

    섹션 헤더 직후 (빈 줄/주석 줄 이후) 첫 번째 위치에 삽입한다.

    Args:
        lines: board.md 라인 리스트.
        section_name: 삽입할 섹션 이름 (예: 'Open', 'In Progress').
        ticket_line: 삽입할 티켓 라인 문자열 (개행 문자 포함).

    Returns:
        수정된 라인 리스트.

    Raises:
        SystemExit: 섹션을 찾을 수 없는 경우.
    """
    section_header = f"## {section_name}"
    section_idx: int = -1
    for i, line in enumerate(lines):
        if line.strip() == section_header:
            section_idx = i
            break

    if section_idx == -1:
        _err(f"board.md에 '{section_header}' 섹션이 없습니다.")

    # 섹션 헤더 다음 줄부터 빈 줄/주석 줄 건너뛰기
    insert_idx: int = section_idx + 1
    while insert_idx < len(lines):
        stripped = lines[insert_idx].strip()
        if stripped == "" or stripped.startswith("<!--"):
            insert_idx += 1
        else:
            break

    new_lines = list(lines)
    new_lines.insert(insert_idx, ticket_line)
    return new_lines


def _remove_ticket_from_board(lines: list[str], ticket_number: str) -> tuple[list[str], str | None]:
    """board.md에서 티켓 항목을 제거하고 제거된 라인을 반환한다.

    Args:
        lines: board.md 라인 리스트.
        ticket_number: 제거할 티켓 번호 (T-NNN 형식).

    Returns:
        (수정된 라인 리스트, 제거된 티켓 라인) 튜플.
        티켓을 찾지 못하면 두 번째 요소가 None.
    """
    ticket_pattern = re.compile(rf"^-\s+\[[ x]\]\s+{re.escape(ticket_number)}\s*:", re.IGNORECASE)
    removed_line: str | None = None
    new_lines: list[str] = []
    for line in lines:
        if ticket_pattern.match(line.strip()) and removed_line is None:
            removed_line = line.rstrip("\n")
        else:
            new_lines.append(line)
    return new_lines, removed_line


# ─── 서브커맨드 구현 ─────────────────────────────────────────────────────────


def cmd_create(title: str, command: str) -> None:
    """새 티켓을 생성하고 board.md Open 섹션에 추가한다.

    board.md에서 최대 T-NNN 번호를 파싱하여 +1 채번 후,
    Open 섹션에 항목을 추가하고 .kanban/T-NNN.txt 빈 파일을 생성한다.

    Args:
        title: 티켓 제목.
        command: 워크플로우 커맨드 (implement, review, research 등).
    """
    lines = _read_board()
    max_num = _get_max_ticket_number(lines)
    new_num = max_num + 1
    ticket_number = f"T-{new_num:03d}"

    # board.md에 티켓 항목 추가
    suffix = f" ({command})" if command else ""
    ticket_line = f"- [ ] {ticket_number}: {title}{suffix}\n"
    new_lines = _insert_ticket_into_section(lines, "Open", ticket_line)
    _write_board(new_lines)

    # .kanban/open-T-NNN.txt 빈 파일 생성
    ticket_file = os.path.join(_KANBAN_DIR, f"open-{ticket_number}.txt")
    os.makedirs(_KANBAN_DIR, exist_ok=True)
    try:
        with open(ticket_file, "w", encoding="utf-8") as f:
            f.write("")
    except OSError as e:
        _err(f"티켓 파일 생성 실패: {e}")

    print(f"{ticket_number}: {title}{suffix}")


def cmd_move(ticket_number: str, target_key: str, force: bool = False) -> None:
    """티켓을 지정 컬럼으로 이동한다.

    허용 상태 전이 규칙을 검증하고, 위반 시 에러를 출력한다.
    --force 플래그가 있으면 규칙을 무시하고 강제 이동한다.

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

    lines = _read_board()
    current_section = _find_ticket_column(lines, ticket_number)

    if current_section is None:
        _err(f"{ticket_number} 티켓을 board.md에서 찾을 수 없습니다")

    # 이미 같은 컬럼에 있으면 무시
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

    # 현재 컬럼에서 제거
    new_lines, removed_line = _remove_ticket_from_board(lines, ticket_number)
    if removed_line is None:
        _err(f"{ticket_number} 티켓을 board.md에서 찾을 수 없습니다")

    # 체크박스 상태 업데이트: Done으로 이동 시 [x], 그 외 [ ]
    if target_section == "Done":
        removed_line = re.sub(r"\[\s*\]", "[x]", removed_line)
    else:
        removed_line = re.sub(r"\[x\]", "[ ]", removed_line, flags=re.IGNORECASE)

    # 대상 컬럼에 삽입
    new_lines = _insert_ticket_into_section(new_lines, target_section, removed_line + "\n")
    _write_board(new_lines)

    # 파일 리네임: Done 이동은 cmd_done이 처리하므로 건너뜀
    if target_section != "Done":
        src_ticket_file = _find_ticket_file(ticket_number)
        if src_ticket_file is not None:
            target_prefix = STATUS_PREFIX.get(target_section, "open")
            dst_ticket_file = os.path.join(_KANBAN_DIR, f"{target_prefix}-{ticket_number}.txt")
            try:
                os.rename(src_ticket_file, dst_ticket_file)
            except OSError as e:
                _err(f"티켓 파일 리네임 실패: {e}")

    print(f"{ticket_number}: {current_section} → {target_section}")


def cmd_done(ticket_number: str) -> None:
    """티켓을 Done으로 이동하고 파일을 .kanban/done/으로 이동한다.

    내부적으로 move를 Done으로 호출한 뒤
    .kanban/*-T-NNN.txt를 .kanban/done/done-T-NNN.txt로 이동한다.

    Args:
        ticket_number: 완료할 티켓 번호 (T-NNN 형식).
    """
    lines = _read_board()
    current_section = _find_ticket_column(lines, ticket_number)
    if current_section is None:
        _err(f"{ticket_number} 티켓을 board.md에서 찾을 수 없습니다")

    # board.md에서 Done으로 이동 (force=True: Review → Done 직접 이동 허용)
    cmd_move(ticket_number, "done", force=True)

    # 파일을 .kanban/done/done-T-NNN.txt로 이동
    src_file = _find_ticket_file(ticket_number)
    done_dir = os.path.join(_KANBAN_DIR, "done")
    dst_file = os.path.join(done_dir, f"done-{ticket_number}.txt")

    if src_file is not None and os.path.isfile(src_file):
        os.makedirs(done_dir, exist_ok=True)
        try:
            shutil.move(src_file, dst_file)
        except OSError as e:
            _err(f"티켓 파일 이동 실패: {e}")
        src_rel = os.path.relpath(src_file, _PROJECT_ROOT)
        print(f"파일 이동: {src_rel} → .kanban/done/done-{ticket_number}.txt")
    else:
        print(f"경고: {ticket_number} 티켓 파일을 찾을 수 없습니다 (board.md는 업데이트됨).", file=sys.stderr)


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


if __name__ == "__main__":
    main()
