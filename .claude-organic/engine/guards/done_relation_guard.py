#!/usr/bin/env -S python3 -u
"""flow-kanban done 실행 시 파생 티켓 완료 여부 검증 가드.

PreToolUse(Bash) 이벤트에서 flow-kanban done 명령을 감지하고,
해당 티켓에서 derived-from으로 파생된 티켓이 Done이 아니면 차단한다.

토글: 환경변수 HOOK_DONE_RELATION_GUARD (false/0 = 비활성, 기본 활성)
"""

from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ET

# utils 패키지 import 경로 설정
_engine_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

_prompt_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../prompt"))
if _prompt_dir not in sys.path:
    sys.path.insert(0, _prompt_dir)

from common import read_env

# flow-kanban done T-NNN 패턴
_DONE_PATTERN = re.compile(r"\bflow-kanban\s+done\s+(T-\d{3})\b")

# 칸반 디렉터리
KANBAN_DIRS = ["open", "progress", "review"]


def _deny(reason: str) -> None:
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


def _find_ticket_xml(kanban_base: str, ticket_num: str) -> str | None:
    """모든 칸반 디렉터리에서 티켓 XML 경로를 찾는다."""
    for d in KANBAN_DIRS + ["done"]:
        path = os.path.join(kanban_base, d, f"{ticket_num}.xml")
        if os.path.isfile(path):
            return path
    return None


def _get_ticket_status(kanban_base: str, ticket_num: str) -> str | None:
    """티켓의 현재 status를 반환한다."""
    path = _find_ticket_xml(kanban_base, ticket_num)
    if not path:
        return None
    try:
        tree = ET.parse(path)
        status_el = tree.find(".//metadata/status")
        return status_el.text.strip() if status_el is not None and status_el.text else None
    except (ET.ParseError, OSError):
        return None


def _find_derived_tickets(kanban_base: str, source_ticket: str) -> list[str]:
    """source_ticket을 derived-from으로 참조하는 티켓 목록을 반환한다."""
    derived = []
    for d in KANBAN_DIRS + ["done"]:
        dir_path = os.path.join(kanban_base, d)
        if not os.path.isdir(dir_path):
            continue
        try:
            for entry in os.scandir(dir_path):
                if not entry.is_file() or not entry.name.endswith(".xml"):
                    continue
                try:
                    tree = ET.parse(entry.path)
                    for rel in tree.findall(".//relations/relation"):
                        if (rel.get("type") == "derived-from"
                                and rel.get("ticket") == source_ticket):
                            num_el = tree.find(".//metadata/number")
                            if num_el is not None and num_el.text:
                                derived.append(num_el.text.strip())
                except (ET.ParseError, OSError):
                    continue
        except OSError:
            continue
    return derived


def main() -> None:
    hook_flag = os.environ.get("HOOK_DONE_RELATION_GUARD") or read_env("HOOK_DONE_RELATION_GUARD")
    if hook_flag in ("false", "0"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    match = _DONE_PATTERN.search(command)
    if not match:
        sys.exit(0)

    ticket_num = match.group(1)

    # 프로젝트 루트 추정
    project_root = os.environ.get("PROJECT_ROOT", os.getcwd())
    kanban_base = os.path.join(project_root, ".claude-organic", "tickets")

    if not os.path.isdir(kanban_base):
        sys.exit(0)

    # 이 티켓을 derived-from으로 참조하는 파생 티켓 찾기
    derived = _find_derived_tickets(kanban_base, ticket_num)
    if not derived:
        sys.exit(0)

    # 파생 티켓 중 Done이 아닌 것 확인
    not_done = []
    for dt in derived:
        st = _get_ticket_status(kanban_base, dt)
        if st != "Done":
            not_done.append(f"{dt}({st or '?'})")

    if not_done:
        _deny(
            f"{ticket_num} Done 차단: 파생 티켓 {', '.join(not_done)}이 "
            f"아직 완료되지 않았습니다. 파생 티켓 완료 후 진행하세요."
        )


if __name__ == "__main__":
    main()
