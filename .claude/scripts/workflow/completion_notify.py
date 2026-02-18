#!/usr/bin/env python3
"""
SubagentStop Hook: Worker/Reporter 완료 시 데스크톱 알림 발송
(completion-notify.sh -> completion_notify.py 1:1 포팅)

입력 (stdin JSON): agent_type, agent_id
비차단 원칙: 모든 에러 경로에서 exit 0
"""

import json
import os
import platform
import subprocess
import sys


def main():
    # stdin JSON 읽기
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    agent_type = input_data.get("agent_type", "")
    agent_id = input_data.get("agent_id", "")

    # worker 또는 reporter만 알림 발송
    if agent_type not in ("worker", "reporter"):
        sys.exit(0)

    # 알림 제목/본문 구성
    title = f"Claude Code: {agent_type.capitalize()} 완료"
    body = f"{agent_id} 태스크 완료"

    # OS 감지 및 알림 발송
    system = platform.system()
    try:
        if system == "Linux":
            subprocess.run(
                ["notify-send", title, body],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        elif system == "Darwin":
            subprocess.run(
                ["osascript", "-e", f'display notification "{body}" with title "{title}"'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
