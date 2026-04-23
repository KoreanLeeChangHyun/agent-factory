"""ticket_state.py - 칸반 티켓 상태 전이 규칙 및 상태 갱신 모듈.

상태 전이 규칙(COLUMN_MAP, ALLOWED_TRANSITIONS)과 상태 갱신 함수를 담당하는
비즈니스 계층 모듈이다. kanban.py에서 분리되었으며, ticket_repository.py에 의존한다.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from flow.ticket_repository import write_ticket_xml, err


# ─── 상수 ───────────────────────────────────────────────────────────────────

# 컬럼 이름 매핑: CLI 인자 → 컬럼명
COLUMN_MAP: dict[str, str] = {
    "todo": "To Do",
    "open": "Open",
    "submit": "Submit",
    "progress": "In Progress",
    "review": "Review",
    "done": "Done",
}

# 허용 상태 전이 규칙: 현재 상태 → 허용 대상 목록
# Done으로의 이동은 done 서브커맨드(force=True)만 허용.
# move 커맨드로 Done 직접 이동은 불가 (Review → Done도 done 서브커맨드 사용 필요).
# To Do는 Open과의 양방향 전이만 기본 허용하며, 그 외 상태에서의 복귀는 --force 필요.
ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "To Do": ["Open"],
    "Open": ["In Progress", "Submit", "To Do"],
    "Submit": ["In Progress", "Open"],
    "In Progress": ["Review", "Open"],
    "Review": ["Open", "In Progress"],
    "Done": ["Open"],
}


# ─── 상태 전이 검증 ─────────────────────────────────────────────────────────


def validate_transition(current_status: str, target_section: str, force: bool = False) -> str | None:
    """상태 전이 규칙을 검증한다.

    현재 상태에서 대상 상태로의 전이가 허용되는지 확인한다.
    이미 같은 상태이면 None을 반환하고, 규칙 위반 시 에러 메시지를 반환한다.
    force=True이면 규칙을 무시한다.

    Args:
        current_status: 현재 티켓 상태 (예: 'Open', 'In Progress').
        target_section: 대상 상태 (예: 'Review', 'Done').
        force: 강제 전이 여부.

    Returns:
        에러 메시지 문자열. 전이가 허용되면 None.
        이미 같은 상태이면 빈 문자열("")을 반환한다.
    """
    # 이미 같은 상태이면 빈 문자열 반환 (에러가 아닌 무시 케이스)
    if current_status == target_section:
        return ""

    # 상태 전이 규칙 검증
    allowed = ALLOWED_TRANSITIONS.get(current_status, [])
    if target_section not in allowed and not force:
        return (
            f"현재 {current_status}이므로 {target_section}으로 이동할 수 없습니다. "
            f"--force 플래그로 강제 이동 가능"
        )

    return None


# ─── 상태 갱신 ───────────────────────────────────────────────────────────────


def update_ticket_status(filepath: str, new_status: str) -> None:
    """티켓 XML의 <status> 요소를 갱신한다.

    <metadata> 래퍼 내부의 <status> 요소를 우선 탐색한다.

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
        err(f"티켓 파일 파싱 실패 ({filepath}): {e}")

    # <metadata> 래퍼 내부의 <status> 우선 탐색
    metadata_elem = root.find("metadata")
    if metadata_elem is not None:
        status_elem = metadata_elem.find("status")
        if status_elem is not None:
            status_elem.text = new_status
        else:
            ET.SubElement(metadata_elem, "status").text = new_status
    else:
        status_elem = root.find("status")
        if status_elem is not None:
            status_elem.text = new_status
        else:
            ET.SubElement(root, "status").text = new_status

    write_ticket_xml(filepath, root)
