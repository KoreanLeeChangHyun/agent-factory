#!/usr/bin/env -S python3 -u
"""
워크플로우 전이 가드 Hook 스크립트

PreToolUse(Bash) 이벤트에서 update_state.py 또는 update-workflow-state.sh 호출의
phase 전이를 검증.

입력: stdin으로 JSON (tool_name, tool_input)
출력: 불법 전이 시 hookSpecificOutput JSON, 통과 시 빈 출력

deny 시 exit 2 + JSON hookSpecificOutput 병행 출력
  exit 2는 stderr 피드백 경로 제공, JSON deny는 공식 차단 시그널

모드별 합법 전이 테이블:
  .claude/scripts/workflow/state/fsm-transitions.json 참조 (단일 정의 소스)
  full, strategy, prompt 3개 모드의 전이 규칙이 JSON으로 정의됨
"""

import json
import os
import re
import sys

# utils 패키지 import 경로 설정
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from utils.env_utils import read_env
from utils.common import resolve_project_root, load_json_file, resolve_work_dir, TS_PATTERN


def _deny(reason, exit_code=2):
    """차단 JSON을 출력하고 종료."""
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(exit_code)


def _parse_command(command):
    """
    update_state.py / update-workflow-state.sh 호출에서 workDir, fromPhase, toPhase를 추출.

    Returns:
        tuple: (work_dir, from_phase, to_phase) or (None, None, None)
    """
    m = re.search(r"(?:update_state\.py|update-workflow-state\.sh|wf-state)\s+(.+)", command)
    if not m:
        return None, None, None

    args = m.group(1).split()
    mode = args[0] if args else ""

    if mode == "status" and len(args) >= 4:
        # status <workDir> <fromPhase> <toPhase>
        return args[1], args[2].upper(), args[3].upper()
    elif mode == "both" and len(args) >= 5:
        # both <workDir> <agent> <fromPhase> <toPhase>
        return args[1], args[3].upper(), args[4].upper()

    return None, None, None


def main():
    project_root = resolve_project_root()

    # .claude.env에서 설정 로드
    hook_flag = os.environ.get("HOOK_WORKFLOW_TRANSITION") or read_env("HOOK_WORKFLOW_TRANSITION")
    skip_guard = os.environ.get("WORKFLOW_SKIP_GUARD") or read_env("WORKFLOW_SKIP_GUARD")

    # 비상 우회 수단
    if skip_guard == "1":
        sys.exit(0)

    # Hook disable check (false = disabled)
    if hook_flag in ("false", "0"):
        sys.exit(0)

    # Bypass 메커니즘: 파일 기반 또는 환경변수 기반
    if os.environ.get("WORKFLOW_GUARD_DISABLE") == "1":
        sys.exit(0)
    if os.path.isfile(os.path.join(project_root, ".workflow", "bypass")):
        sys.exit(0)

    # stdin에서 JSON 읽기
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    # Bash가 아니면 통과
    if tool_name != "Bash":
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    # update_state.py 또는 update-workflow-state.sh 호출이 아니면 통과
    if "update_state.py" not in command and "update-workflow-state.sh" not in command and "wf-state" not in command:
        sys.exit(0)

    # command에서 workDir, fromPhase, toPhase 파싱
    work_dir_raw, from_phase, to_phase = _parse_command(command)
    if work_dir_raw is None:
        sys.exit(0)

    # YYYYMMDD-HHMMSS 단축 형식이면 registry에서 해석
    if TS_PATTERN.match(work_dir_raw):
        work_dir = resolve_work_dir(work_dir_raw, project_root)
    else:
        work_dir = work_dir_raw

    # 상대 경로를 절대 경로로 변환
    if not os.path.isabs(work_dir):
        work_dir = os.path.join(project_root, work_dir)

    # workDir의 status.json에서 현재 phase와 mode 읽기
    current_phase = "NONE"
    workflow_mode = "full"
    status_file = os.path.join(work_dir, "status.json")
    status_data = load_json_file(status_file)
    if isinstance(status_data, dict):
        current_phase = status_data.get("phase", "NONE").upper()
        workflow_mode = status_data.get("mode", "full").lower()

    # 현재 phase와 fromPhase 일치 검증
    if current_phase != from_phase:
        _deny(
            f"Phase 불일치: status.json의 현재 phase({current_phase})가 "
            f"요청한 fromPhase({from_phase})와 다릅니다."
        )

    # fsm-transitions.json에서 모드별 합법 전이 테이블 로드
    fsm_file = os.path.join(project_root, ".claude", "scripts", "workflow", "state", "fsm-transitions.json")
    fsm_data = load_json_file(fsm_file)
    if fsm_data is None:
        _deny(f"FSM 전이 규칙 파일(fsm-transitions.json) 로드 실패")

    modes = fsm_data.get("modes", {})
    allowed_table = modes.get(workflow_mode, modes.get("full", {}))
    allowed_targets = allowed_table.get(from_phase, [])

    if to_phase in allowed_targets:
        # 합법 전이 -> 통과
        sys.exit(0)

    # 불법 전이 -> 차단
    allowed_list = ", ".join(allowed_targets) if allowed_targets else "없음"
    _deny(
        f"불법 전이: {from_phase}에서 {to_phase}로 직접 전이할 수 없습니다. "
        f"(mode: {workflow_mode}) 허용된 전이 대상: {allowed_list}"
    )


if __name__ == "__main__":
    main()
