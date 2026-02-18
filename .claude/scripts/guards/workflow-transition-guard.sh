#!/bin/bash
# 워크플로우 전이 가드 Hook 스크립트
# PreToolUse(Bash) 이벤트에서 update-workflow-state.sh 또는 wf-state alias 호출의 phase 전이를 검증
#
# 입력: stdin으로 JSON (tool_name, tool_input)
# 출력: 불법 전이 시 hookSpecificOutput JSON, 통과 시 빈 출력
#
# deny 시 exit 2 + JSON hookSpecificOutput 병행 출력
#   exit 2는 stderr 피드백 경로 제공, JSON deny는 공식 차단 시그널
#
# 모드별 합법 전이 테이블:
#   .claude/scripts/workflow/fsm-transitions.json 참조 (단일 정의 소스)
#   full, no-plan, prompt 3개 모드의 전이 규칙이 JSON으로 정의됨

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load variables from .claude.env (process env takes precedence)
ENV_FILE_WTG="$PROJECT_ROOT/.claude.env"
if [ -f "$ENV_FILE_WTG" ]; then
    if [ -z "$GUARD_WORKFLOW_TRANSITION" ]; then
        GUARD_WORKFLOW_TRANSITION=$(grep "^GUARD_WORKFLOW_TRANSITION=" "$ENV_FILE_WTG" | head -1 | sed "s/^GUARD_WORKFLOW_TRANSITION=//")
    fi
    if [ -z "$WORKFLOW_SKIP_GUARD" ]; then
        WORKFLOW_SKIP_GUARD=$(grep "^WORKFLOW_SKIP_GUARD=" "$ENV_FILE_WTG" | head -1 | sed "s/^WORKFLOW_SKIP_GUARD=//")
    fi
fi

# 비상 우회 수단
if [ "$WORKFLOW_SKIP_GUARD" = "1" ]; then
    exit 0
fi

# Guard disable check
if [ "$GUARD_WORKFLOW_TRANSITION" = "0" ]; then exit 0; fi

# Bypass 메커니즘: 파일 기반 또는 환경변수 기반
if [ "$WORKFLOW_GUARD_DISABLE" = "1" ] || [ -f "$PROJECT_ROOT/.workflow/bypass" ]; then
    exit 0
fi

# stdin에서 JSON 읽기
INPUT=$(cat)

# tool_name 확인 (Bash가 아니면 통과)
TOOL_NAME=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_name', ''))
except:
    print('')
" 2>/dev/null)

if [ "$TOOL_NAME" != "Bash" ]; then
    exit 0
fi

# command 필드 추출
COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tool_input = data.get('tool_input', {})
    print(tool_input.get('command', ''))
except:
    print('')
" 2>/dev/null)

if [ -z "$COMMAND" ]; then
    exit 0
fi

# update-workflow-state.sh 또는 wf-state alias 호출이 아니면 통과
if ! echo "$COMMAND" | grep -qE 'update-workflow-state\.sh|wf-state' 2>/dev/null; then
    exit 0
fi

# command 문자열에서 mode, workDir, fromPhase, toPhase 파싱
# update-workflow-state.sh 또는 wf-state 호출 형식:
#   status 모드: wf-state status <workDir> <fromPhase> <toPhase>
#   both 모드:   wf-state both <workDir> <agent> <fromPhase> <toPhase>
#   context 모드: wf-state context <workDir> <agent> (전이 검증 불필요)
PARSED=$(echo "$COMMAND" | python3 -c "
import sys, re

cmd = sys.stdin.read().strip()

# update-workflow-state.sh 또는 wf-state 이후의 모든 인자를 추출
m = re.search(r'(?:update-workflow-state\.sh|wf-state)\s+(.+)', cmd)
if not m:
    print('')
    sys.exit()

args = m.group(1).split()
mode = args[0] if len(args) > 0 else ''

if mode == 'status' and len(args) >= 4:
    # status <workDir> <fromPhase> <toPhase>
    work_dir = args[1]
    from_phase = args[2].upper()
    to_phase = args[3].upper()
    print(f'{work_dir}|{from_phase}|{to_phase}')
elif mode == 'both' and len(args) >= 5:
    # both <workDir> <agent> <fromPhase> <toPhase>
    work_dir = args[1]
    from_phase = args[3].upper()
    to_phase = args[4].upper()
    print(f'{work_dir}|{from_phase}|{to_phase}')
else:
    print('')
" 2>/dev/null)

if [ -z "$PARSED" ]; then
    exit 0
fi

WORK_DIR=$(echo "$PARSED" | cut -d'|' -f1)
FROM_PHASE=$(echo "$PARSED" | cut -d'|' -f2)
TO_PHASE=$(echo "$PARSED" | cut -d'|' -f3)

# YYYYMMDD-HHMMSS 단축 형식이면 registry.json에서 실제 workDir 해석
if [[ "$WORK_DIR" =~ ^[0-9]{8}-[0-9]{6}$ ]]; then
    REGISTRY_FILE="$PROJECT_ROOT/.workflow/registry.json"
    if [ -f "$REGISTRY_FILE" ]; then
        RESOLVED=$(WF_KEY="$WORK_DIR" WF_REGISTRY="$REGISTRY_FILE" python3 -c "
import json, os, sys
key = os.environ['WF_KEY']
registry_file = os.environ['WF_REGISTRY']
try:
    with open(registry_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if key in data and 'workDir' in data[key]:
        print(data[key]['workDir'])
    else:
        print('')
except:
    print('')
" 2>/dev/null)
        if [ -n "$RESOLVED" ]; then
            WORK_DIR="$RESOLVED"
        else
            # 레거시 폴백: .workflow/YYYYMMDD-HHMMSS (플랫 구조)
            WORK_DIR=".workflow/$WORK_DIR"
        fi
    else
        WORK_DIR=".workflow/$WORK_DIR"
    fi
fi

# 상대 경로를 절대 경로로 변환
if [[ "$WORK_DIR" != /* ]]; then
    WORK_DIR="$PROJECT_ROOT/$WORK_DIR"
fi

# workDir의 status.json에서 현재 phase와 mode 읽기
CURRENT_PHASE=""
WORKFLOW_MODE=""
if [ -f "${WORK_DIR}/status.json" ]; then
    STATUS_INFO=$(WORK_DIR_PATH="${WORK_DIR}" python3 -c "
import json, os, sys
try:
    work_dir = os.environ['WORK_DIR_PATH']
    with open(os.path.join(work_dir, 'status.json'), 'r') as f:
        data = json.load(f)
    phase = data.get('phase', 'NONE').upper()
    mode = data.get('mode', 'full').lower()
    print(f'{phase}|{mode}')
except:
    print('NONE|full')
" 2>/dev/null)
    CURRENT_PHASE=$(echo "$STATUS_INFO" | cut -d'|' -f1)
    WORKFLOW_MODE=$(echo "$STATUS_INFO" | cut -d'|' -f2)
fi

if [ -z "$CURRENT_PHASE" ]; then
    CURRENT_PHASE="NONE"
fi

if [ -z "$WORKFLOW_MODE" ]; then
    WORKFLOW_MODE="full"
fi

# 현재 phase와 fromPhase 일치 검증
if [ "$CURRENT_PHASE" != "$FROM_PHASE" ]; then
    GUARD_CURRENT_PHASE="${CURRENT_PHASE}" GUARD_FROM_PHASE="${FROM_PHASE}" python3 -c "
import json, os
cur = os.environ['GUARD_CURRENT_PHASE']
frm = os.environ['GUARD_FROM_PHASE']
result = {
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': f'Phase 불일치: status.json의 현재 phase({cur})가 요청한 fromPhase({frm})와 다릅니다.'
    }
}
print(json.dumps(result, ensure_ascii=False))
" 2>/dev/null
    exit 2
fi

# fsm-transitions.json에서 모드별 합법 전이 테이블 로드 및 검증
FSM_FILE="$PROJECT_ROOT/.claude/scripts/workflow/fsm-transitions.json"

VALID=$(GUARD_FROM_PHASE="${FROM_PHASE}" GUARD_TO_PHASE="${TO_PHASE}" GUARD_MODE="${WORKFLOW_MODE}" GUARD_FSM_FILE="${FSM_FILE}" python3 -c "
import json, os, sys

fsm_file = os.environ['GUARD_FSM_FILE']
try:
    with open(fsm_file, 'r', encoding='utf-8') as f:
        fsm_data = json.load(f)
except Exception as e:
    # JSON 로드 실패 시 차단 (페일-세이프)
    print('deny:' + str(e))
    sys.exit()

mode = os.environ.get('GUARD_MODE', 'full')
modes = fsm_data.get('modes', {})
allowed_table = modes.get(mode, modes.get('full', {}))

from_phase = os.environ['GUARD_FROM_PHASE']
to_phase = os.environ['GUARD_TO_PHASE']

allowed_targets = allowed_table.get(from_phase, [])
if to_phase in allowed_targets:
    print('yes')
else:
    print('no')
" 2>/dev/null)

# FSM 파일 로드 실패 시 페일-세이프 차단
if [[ "$VALID" == deny:* ]]; then
    FSM_ERROR_MSG="${VALID#deny:}"
    GUARD_FSM_ERROR="$FSM_ERROR_MSG" python3 -c "
import json, os
err = os.environ['GUARD_FSM_ERROR']
result = {
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': f'FSM 전이 규칙 파일(fsm-transitions.json) 로드 실패: {err}'
    }
}
print(json.dumps(result, ensure_ascii=False))
" 2>/dev/null
    exit 2
fi

if [ "$VALID" = "no" ]; then
    # 모드별 합법 전이 대상 목록 생성
    ALLOWED_LIST=$(GUARD_FROM_PHASE="${FROM_PHASE}" GUARD_MODE="${WORKFLOW_MODE}" GUARD_FSM_FILE="${FSM_FILE}" python3 -c "
import json, os, sys

fsm_file = os.environ['GUARD_FSM_FILE']
try:
    with open(fsm_file, 'r', encoding='utf-8') as f:
        fsm_data = json.load(f)
except Exception:
    print('없음')
    sys.exit()

mode = os.environ.get('GUARD_MODE', 'full')
modes = fsm_data.get('modes', {})
allowed_table = modes.get(mode, modes.get('full', {}))
targets = allowed_table.get(os.environ['GUARD_FROM_PHASE'], [])
print(', '.join(targets) if targets else '없음')
" 2>/dev/null)

    GUARD_FROM_PHASE="${FROM_PHASE}" GUARD_TO_PHASE="${TO_PHASE}" GUARD_ALLOWED_LIST="${ALLOWED_LIST}" GUARD_MODE="${WORKFLOW_MODE}" python3 -c "
import json, os
frm = os.environ['GUARD_FROM_PHASE']
to = os.environ['GUARD_TO_PHASE']
allowed = os.environ['GUARD_ALLOWED_LIST']
mode = os.environ.get('GUARD_MODE', 'full')
result = {
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': f'불법 전이: {frm}에서 {to}로 직접 전이할 수 없습니다. (mode: {mode}) 허용된 전이 대상: {allowed}'
    }
}
print(json.dumps(result, ensure_ascii=False))
" 2>/dev/null
    exit 2
fi

# 합법 전이 - 통과 (빈 출력)
exit 0
