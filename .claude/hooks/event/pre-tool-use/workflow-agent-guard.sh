#!/bin/bash
# 워크플로우 에이전트 호출 가드 Hook 스크립트
# PreToolUse(Task) 이벤트에서 phase별 허용 에이전트를 검증하여 불법 호출 차단
#
# 입력: stdin으로 JSON (tool_name, tool_input)
# 출력: 차단 시 hookSpecificOutput JSON, 통과 시 빈 출력
#
# 모드별 Phase별 허용 에이전트:
#   [full 모드 (기본)]
#     NONE/비존재: init만 허용
#     INIT: planner만 허용
#     PLAN: planner + worker 허용
#     WORK: worker(재호출) + reporter 허용
#     REPORT: reporter(재호출)만 허용
#     COMPLETED/FAILED/STALE/CANCELLED: 모든 에이전트 차단
#   [no-plan 모드]
#     NONE/비존재: init만 허용
#     INIT: worker만 허용 (planner 대신)
#     WORK: worker(재호출) + reporter 허용
#     REPORT: reporter(재호출)만 허용
#     COMPLETED/FAILED/STALE/CANCELLED: 모든 에이전트 차단
#   [prompt 모드]
#     NONE/비존재: init만 허용
#     INIT: 없음 (메인 에이전트 직접 작업, 에이전트 호출 없음)
#     COMPLETED: 모든 에이전트 차단

# 비상 우회
if [ "$WORKFLOW_SKIP_GUARD" = "1" ]; then
    exit 0
fi

# Bypass 메커니즘: 파일 기반 또는 환경변수 기반
SCRIPT_DIR_AG="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT_AG="$(cd "$SCRIPT_DIR_AG/../../../.." && pwd)"
if [ "$WORKFLOW_GUARD_DISABLE" = "1" ] || [ -f "$PROJECT_ROOT_AG/.workflow/bypass" ]; then
    exit 0
fi

# stdin에서 JSON 읽기
INPUT=$(cat)

# python3으로 전체 로직 처리
echo "$INPUT" | python3 -c "
import sys, json, os, re

data = json.load(sys.stdin)
tool_input = data.get('tool_input', {})

# subagent_type 확인
subagent_type = tool_input.get('subagent_type', '')
if not subagent_type:
    # subagent_type이 없으면 워크플로우 관련 Task가 아님 -> 통과
    sys.exit(0)

# prompt에서 workDir 추출
prompt = tool_input.get('prompt', '')
match = re.search(r'workDir:\s*(\S+)', prompt)
if not match:
    # workDir이 없으면 워크플로우 외 Task 호출 -> 통과
    sys.exit(0)

work_dir = match.group(1).rstrip(',')

# 절대 경로 구성
project_root = os.environ.get('PROJECT_ROOT', os.getcwd())
if project_root.endswith('.claude/hook') or '/hooks/' in project_root:
    # .claude/hooks/event/pre-tool-use -> project root (4 levels up)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(project_root))))

if not os.path.isabs(work_dir):
    work_dir = os.path.join(project_root, work_dir)

status_file = os.path.join(work_dir, 'status.json')

# status.json에서 현재 phase와 mode 읽기
current_phase = 'NONE'
workflow_mode = 'full'
if os.path.exists(status_file):
    try:
        with open(status_file, 'r', encoding='utf-8') as f:
            status_data = json.load(f)
        current_phase = status_data.get('phase', 'NONE')
        workflow_mode = status_data.get('mode', 'full').lower()
    except (json.JSONDecodeError, IOError):
        current_phase = 'NONE'
        workflow_mode = 'full'

# 에이전트 이름 정규화 (경로에서 파일명만 추출, .md 제거)
agent = subagent_type.strip().lower()
# 경로가 포함된 경우 basename 추출
if '/' in agent:
    agent = os.path.basename(agent)
if agent.endswith('.md'):
    agent = agent[:-3]

# init 에이전트는 phase 검증 제외 (NONE/INIT 이전 호출)
if agent == 'init':
    sys.exit(0)

# 모드별 Phase별 허용 에이전트 맵
ALLOWED_AGENTS_FULL = {
    'NONE': ['init'],
    'INIT': ['planner'],
    'PLAN': ['planner', 'worker'],
    'WORK': ['worker', 'reporter'],
    'REPORT': ['reporter'],
    'COMPLETED': [],
    'FAILED': [],
    'STALE': [],
    'CANCELLED': [],
}

ALLOWED_AGENTS_NO_PLAN = {
    'NONE': ['init'],
    'INIT': ['worker'],
    'WORK': ['worker', 'reporter'],
    'REPORT': ['reporter'],
    'COMPLETED': [],
    'FAILED': [],
    'STALE': [],
    'CANCELLED': [],
}

ALLOWED_AGENTS_PROMPT = {
    'NONE': ['init'],
    'INIT': [],
    'COMPLETED': [],
    'FAILED': [],
    'STALE': [],
    'CANCELLED': [],
}

MODE_AGENTS_MAP = {
    'full': ALLOWED_AGENTS_FULL,
    'no-plan': ALLOWED_AGENTS_NO_PLAN,
    'prompt': ALLOWED_AGENTS_PROMPT,
}

agents_table = MODE_AGENTS_MAP.get(workflow_mode, ALLOWED_AGENTS_FULL)
allowed = agents_table.get(current_phase, [])

if agent not in allowed:
    phase_desc = current_phase if current_phase != 'NONE' else 'NONE (초기화 전)'
    allowed_desc = ', '.join(allowed) if allowed else '없음 (종료 상태)'
    reason = f'불법 에이전트 호출: {current_phase} phase에서 {agent} 에이전트를 호출할 수 없습니다. (mode: {workflow_mode}) 허용: {allowed_desc}'
    result = {
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny',
            'permissionDecisionReason': reason
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)

# 허용된 호출 -> 통과 (빈 출력)
sys.exit(0)
" 2>/dev/null

exit 0
