#!/usr/bin/env -S python3 -u
"""inject_prompt.py - SessionStart hook으로 워크플로우 세션 전용 system-prompt를 주입한다.

T-483 (2026-05-13): system-prompt-wf.xml 폐기 + SKILL.md 직접 inject 로 통합.
워크플로우 세션의 system prompt = .claude/skills/workflow-orchestration/SKILL.md
(frontmatter 제거 후 본문). 워크플로우 엔진 실행에 필요한 SKILL.md 가 이미 매
세션 로드되어야 하므로 단일 진실 공급원으로 통합.

동작:
  - 워크플로우 세션 판별 (session_identifier.is_workflow_session) → 아닌 경우 즉시 종료
  - .claude/skills/workflow-orchestration/SKILL.md 본문(frontmatter 제거) 을 stdout 출력
  - 활성 티켓(T-NNN) 감지 시 <ticket-prefix> XML 블록 추가 inject
"""

from __future__ import annotations

import os
import sys

_engine_dir: str = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import resolve_project_root
from flow.flow_logger import append_log, resolve_work_dir_for_logging
from flow.session_identifier import is_workflow_session, get_session_ticket_id


def _extract_ticket_id() -> str | None:
    """현재 세션의 활성 티켓 ID(T-NNN)를 반환한다.

    session_identifier.get_session_ticket_id()에 위임한다.

    Returns:
        티켓 ID 문자열 (예: "T-001"). 워크플로우 세션이 아니거나 추출 실패 시 None.
    """
    return get_session_ticket_id()


def _is_workflow_session() -> bool:
    """현재 세션이 워크플로우 세션인지 판별한다.

    session_identifier.is_workflow_session()에 위임한다.

    Returns:
        워크플로우 세션이면 True, 그 외 False.
    """
    return is_workflow_session()


def _strip_frontmatter(content: str) -> str:
    """SKILL.md 의 YAML frontmatter (--- ... ---) 를 제거하고 본문만 반환한다.

    frontmatter 가 없으면 원본 그대로 반환.
    """
    if not content.startswith("---\n"):
        return content
    # 두 번째 '---' 위치 탐색
    end_idx = content.find("\n---\n", 4)
    if end_idx == -1:
        return content
    return content[end_idx + 5 :].lstrip()


def main() -> None:
    """세션 유형을 판별하고 워크플로우 세션일 때만 SKILL.md 본문을 stdout에 출력한다.

    메인 세션(워크플로우 세션이 아닌 경우)에서는 아무것도 출력하지 않고 즉시 종료한다.
    메인 세션 정책은 CLAUDE.md + .claude/rules/workflow.md 가 담당한다.
    """
    project_root = resolve_project_root()

    if not _is_workflow_session():
        sys.exit(0)

    skill_file = os.path.join(
        project_root, ".claude", "skills", "workflow-orchestration", "SKILL.md"
    )

    _log_dir = resolve_work_dir_for_logging(project_root)
    if _log_dir:
        append_log(_log_dir, "INFO", "inject_prompt: session_type=workflow source=SKILL.md")

    if not os.path.exists(skill_file):
        sys.exit(0)

    with open(skill_file, encoding="utf-8") as f:
        raw = f.read()
    content = _strip_frontmatter(raw)

    ticket_id = _extract_ticket_id()
    if ticket_id:
        ticket_prefix_block = (
            f"\n<ticket-prefix>\n"
            f"매 응답의 첫 줄에 [{ticket_id}] 접두사를 반드시 출력하라.\n"
            f"예시: [{ticket_id}] 응답 내용...\n"
            f"</ticket-prefix>"
        )
        content = content + ticket_prefix_block

    print(content, end="")
    sys.exit(0)


if __name__ == "__main__":
    main()
