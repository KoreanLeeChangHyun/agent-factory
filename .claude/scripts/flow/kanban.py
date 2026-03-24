#!/usr/bin/env -S python3 -u
"""kanban.py - 칸반 보드 상태 관리 CLI 라우터.

XML 티켓 파일(.kanban/active/T-NNN.xml)을 Single Source of Truth(SSoT)로 사용한다.
LLM 호출 없음 (순수 IO).

사용법:
  python3 kanban.py create <title>
  python3 kanban.py move <ticket> <target>
  python3 kanban.py done <ticket>
  python3 kanban.py delete <ticket>
  python3 kanban.py add-subnumber <ticket> --command <cmd> --goal "<goal>" --target "<target>"
  python3 kanban.py update-title <ticket> <title>
  python3 kanban.py update-subnumber <ticket> --id <N>
  python3 kanban.py archive-subnumber <ticket>
  python3 kanban.py set-editing <ticket> <on|off>

비즈니스 로직은 아래 모듈에 위임한다:
  flow.ticket_repository  - XML CRUD, 파일 탐색, 유틸리티
  flow.ticket_state        - 상태 전이 규칙, 상태 갱신
  flow.kanban_cli          - 서브커맨드 구현, argparse 파서, dispatch
"""

from __future__ import annotations

import os
import sys

# ─── sys.path 설정 ────────────────────────────────────────────────────────────

_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR: str = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# ─── 모듈 임포트 ─────────────────────────────────────────────────────────────

from flow.kanban_cli import build_parser, dispatch  # noqa: E402
from flow.ticket_repository import log  # noqa: E402


# ─── main ────────────────────────────────────────────────────────────────────


def main() -> None:
    """CLI 진입점. 서브커맨드를 파싱하여 해당 핸들러를 호출한다."""
    parser = build_parser()
    args = parser.parse_args()
    log("INFO", f"kanban.py: subcommand={args.subcommand}")
    dispatch(args)


if __name__ == "__main__":
    main()
