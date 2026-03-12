#!/usr/bin/env -S python3 -u
"""칸반 현재 티켓 추적 가드 스크립트.

PreToolUse(Read|Write|Edit|Bash) 이벤트에서 .kanban/T-*.xml 파일 접근을 감지하고
.kanban/.current 파일에 해당 티켓 번호를 기록한다.

주요 함수:
    main: Hook 진입점, stdin JSON 파싱 후 .current 파일 갱신

입력: stdin으로 JSON (tool_name, tool_input)
출력: 없음 (항상 종료 코드 0, 차단하지 않음)
"""

from __future__ import annotations

import json
import os
import re
import sys


# .kanban 디렉터리 경로 계산 (프로젝트 루트 기준)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, '..', '..', '..'))
_KANBAN_DIR = os.path.join(_PROJECT_ROOT, '.kanban')
_CURRENT_FILE = os.path.join(_KANBAN_DIR, '.current')

# .kanban/T-NNN.xml 패턴
_TICKET_PATTERN = re.compile(r'\.kanban[/\\](T-\d+)\.xml')


def _extract_ticket_number(text: str) -> str | None:
    """텍스트에서 T-NNN 티켓 번호를 추출한다.

    .kanban/T-NNN.xml 패턴을 탐색한다.

    Args:
        text: 검사할 텍스트 문자열 (파일 경로 또는 Bash 명령어)

    Returns:
        매칭된 T-NNN 형식의 티켓 번호, 없으면 None
    """
    m = _TICKET_PATTERN.search(text)
    if m:
        return m.group(1)
    return None


def _write_current(ticket_number: str) -> None:
    """티켓 번호를 .kanban/.current 파일에 기록한다.

    티켓 XML 파일이 실제로 존재하는 경우에만 기록한다.
    삭제된 티켓에 대해서는 .current를 갱신하지 않는다.

    Args:
        ticket_number: T-NNN 형식의 티켓 번호
    """
    ticket_xml = os.path.join(_KANBAN_DIR, f'{ticket_number}.xml')
    if not os.path.exists(ticket_xml):
        return

    try:
        with open(_CURRENT_FILE, 'w', encoding='utf-8') as f:
            f.write(ticket_number)
    except OSError:
        pass


def main() -> None:
    """칸반 현재 티켓 추적 가드의 진입점.

    stdin에서 JSON을 읽어 Read/Write/Edit/Bash 도구의 .kanban/T-*.xml 접근을
    감지하고 .kanban/.current 파일을 갱신한다.
    항상 종료 코드 0을 반환하여 도구 실행을 차단하지 않는다.
    """
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get('tool_name', '')
    tool_input = data.get('tool_input', {})

    ticket_number: str | None = None

    if tool_name in ('Read', 'Write', 'Edit'):
        file_path = tool_input.get('file_path', '')
        if file_path:
            ticket_number = _extract_ticket_number(file_path)

    elif tool_name == 'Bash':
        command = tool_input.get('command', '')
        if command:
            ticket_number = _extract_ticket_number(command)

    if ticket_number:
        _write_current(ticket_number)

    sys.exit(0)


if __name__ == '__main__':
    main()
