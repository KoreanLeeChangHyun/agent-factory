#!/usr/bin/env python3
"""SessionStart Hook: workflow-orchestration summary를 additionalContext로 주입

Context optimization: SKILL.md 전체(~9KB) 대신 summary.md(~3KB)만 주입하여
세션 시작 시 컨텍스트 소비를 ~67% 절감. 상세 규칙은 SKILL.md 및
Supporting Files(step0~3, common-reference)에서 필요 시 로드.
"""
import json
import sys
from pathlib import Path


def main() -> int:
    # __file__ = .claude/hooks/event/session-start/inject-workflow-orchestrator.py
    # parent chain: session-start -> event -> hooks -> .claude -> project_root
    project_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
    skill_dir = project_dir / ".claude" / "skills" / "workflow-orchestration"

    # Primary: summary.md (compact ~3KB)
    summary_path = skill_dir / "summary.md"
    # Fallback: SKILL.md (full, in case summary.md is missing)
    skill_path = skill_dir / "SKILL.md"

    if summary_path.exists():
        content = summary_path.read_text(encoding="utf-8")
    elif skill_path.exists():
        content = skill_path.read_text(encoding="utf-8")
    else:
        return 0

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": content,
        }
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
