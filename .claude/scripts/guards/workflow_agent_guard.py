#!/usr/bin/env -S python3 -u
"""
워크플로우 에이전트 호출 가드 Hook 스크립트

PreToolUse(Task) 이벤트에서 phase별 허용 에이전트를 검증하여 불법 호출 차단.

입력: stdin으로 JSON (tool_name, tool_input)
출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력

설계 의도: 워크플로우는 FSM(유한 상태 기계) 기반으로 Phase를 전이하며,
각 Phase에 전담 에이전트만 허용한다.
허용 에이전트 6종(init, planner, worker, explorer, reporter, done)은
INIT->PLAN->WORK->REPORT->COMPLETED 전이 경로의 각 단계를 전담한다.

모드별 Phase별 허용 에이전트:
  [full 모드 (기본)]
    NONE/비존재: init만 허용
    INIT: planner만 허용
    PLAN: planner + worker 허용
    WORK: worker + explorer + reporter 허용
    REPORT: reporter(재호출) + done 허용
    COMPLETED/FAILED/STALE/CANCELLED: 모든 에이전트 차단
  [no-plan 모드]
    NONE/비존재: init만 허용
    INIT: worker만 허용 (planner 대신)
    WORK: worker + explorer + reporter 허용
    REPORT: reporter(재호출) + done 허용
    COMPLETED/FAILED/STALE/CANCELLED: 모든 에이전트 차단
  [prompt 모드]
    NONE/비존재: init만 허용
    INIT: worker 허용
    WORK: worker + explorer + reporter 허용
    REPORT: reporter + done 허용
    COMPLETED/FAILED/STALE/CANCELLED: 모든 에이전트 차단
"""

import json
import os
import re
import sys

# _utils 패키지 import 경로 설정
_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from _utils.env_utils import read_env
from _utils.common import resolve_project_root, load_json_file


def _deny(reason):
    """차단 JSON을 출력하고 종료."""
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


# 모드별 Phase별 허용 에이전트 맵
ALLOWED_AGENTS_FULL = {
    "NONE": ["init"],
    "INIT": ["planner"],
    "PLAN": ["planner", "worker"],
    "WORK": ["worker", "explorer", "reporter"],
    "REPORT": ["reporter", "done"],
    "COMPLETED": [],
    "FAILED": [],
    "STALE": [],
    "CANCELLED": [],
}

ALLOWED_AGENTS_NO_PLAN = {
    "NONE": ["init"],
    "INIT": ["worker"],
    "WORK": ["worker", "explorer", "reporter"],
    "REPORT": ["reporter", "done"],
    "COMPLETED": [],
    "FAILED": [],
    "STALE": [],
    "CANCELLED": [],
}

ALLOWED_AGENTS_PROMPT = {
    "NONE": ["init"],
    "INIT": ["worker"],
    "WORK": ["worker", "explorer", "reporter"],
    "REPORT": ["reporter", "done"],
    "COMPLETED": [],
    "FAILED": [],
    "STALE": [],
    "CANCELLED": [],
}

MODE_AGENTS_MAP = {
    "full": ALLOWED_AGENTS_FULL,
    "no-plan": ALLOWED_AGENTS_NO_PLAN,
    "prompt": ALLOWED_AGENTS_PROMPT,
}


def main():
    project_root = resolve_project_root()

    # .claude.env에서 설정 로드
    guard_agent = os.environ.get("GUARD_WORKFLOW_AGENT") or read_env("GUARD_WORKFLOW_AGENT")
    skip_guard = os.environ.get("WORKFLOW_SKIP_GUARD") or read_env("WORKFLOW_SKIP_GUARD")

    # 비상 우회
    if skip_guard == "1":
        sys.exit(0)

    # Guard disable check
    if guard_agent == "0":
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

    tool_input = data.get("tool_input", {})

    # subagent_type 확인
    subagent_type = tool_input.get("subagent_type", "")
    if not subagent_type:
        # subagent_type이 없으면 워크플로우 관련 Task가 아님 -> 통과
        sys.exit(0)

    # prompt에서 workDir 추출
    prompt = tool_input.get("prompt", "")
    match = re.search(r"workDir:\s*(\S+)", prompt)
    if not match:
        # workDir이 없으면 워크플로우 외 Task 호출 -> 통과
        sys.exit(0)

    work_dir = match.group(1).rstrip(",")

    # 절대 경로 구성
    if not os.path.isabs(work_dir):
        work_dir = os.path.join(project_root, work_dir)

    status_file = os.path.join(work_dir, "status.json")

    # status.json에서 현재 phase와 mode 읽기
    current_phase = "NONE"
    workflow_mode = "full"
    status_data = load_json_file(status_file)
    if isinstance(status_data, dict):
        current_phase = status_data.get("phase", "NONE")
        workflow_mode = status_data.get("mode", "full").lower()

    # 에이전트 이름 정규화
    agent = subagent_type.strip().lower()
    if "/" in agent:
        agent = os.path.basename(agent)
    if agent.endswith(".md"):
        agent = agent[:-3]

    # init 에이전트는 phase 검증 제외
    if agent == "init":
        sys.exit(0)

    # 모드별 허용 에이전트 테이블
    agents_table = MODE_AGENTS_MAP.get(workflow_mode, ALLOWED_AGENTS_FULL)
    allowed = agents_table.get(current_phase, [])

    if agent not in allowed:
        allowed_desc = ", ".join(allowed) if allowed else "없음 (종료 상태)"
        reason = (
            f"불법 에이전트 호출: {current_phase} phase에서 {agent} 에이전트를 호출할 수 없습니다. "
            f"(mode: {workflow_mode}) 허용: {allowed_desc}"
        )
        _deny(reason)

    # 허용된 호출 -> 통과
    sys.exit(0)


if __name__ == "__main__":
    main()
