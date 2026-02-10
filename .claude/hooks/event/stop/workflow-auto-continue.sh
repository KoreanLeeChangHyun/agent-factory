#!/bin/bash
# 워크플로우 자동 계속 Stop Hook 스크립트
# Stop 이벤트에서 활성 워크플로우가 진행 중이면 Claude의 중단을 차단
#
# 입력: stdin으로 JSON (session_id, transcript_path, cwd, stop_hook_active 등)
# 출력: 차단 시 {"decision":"block","reason":"..."}, 통과 시 빈 출력
#
# 안전장치:
#   - 연속 3회 차단 시 허용 (무한 루프 방지)
#   - PLAN phase에서는 차단하지 않음 (AskUserQuestion 대기 존중)
#   - 종료 phase (COMPLETED/FAILED/CANCELLED/STALE)에서는 차단하지 않음
#   - stop_hook_active=true일 때는 이미 계속 진행 중이므로 카운터만 증가
#   - bypass 파일/환경변수로 비활성화 가능

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# bypass 체크
if [ "$WORKFLOW_GUARD_DISABLE" = "1" ]; then
    exit 0
fi

if [ -f "$PROJECT_ROOT/.workflow/bypass" ]; then
    exit 0
fi

# stdin에서 JSON 읽기
INPUT=$(cat)

# 카운터 파일 경로
COUNTER_FILE="$PROJECT_ROOT/.workflow/.stop-block-counter"

# Python3으로 전체 로직 처리
echo "$INPUT" | COUNTER_FILE="$COUNTER_FILE" PROJECT_ROOT="$PROJECT_ROOT" python3 -c "
import sys, json, os

counter_file = os.environ['COUNTER_FILE']
project_root = os.environ['PROJECT_ROOT']

# stdin에서 입력 읽기
try:
    data = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    # JSON 파싱 실패 시 통과
    sys.exit(0)

# stop_hook_active 확인 (이미 Stop Hook으로 계속 진행 중인지)
stop_hook_active = data.get('stop_hook_active', False)

# registry.json에서 활성 워크플로우 확인
registry_path = os.path.join(project_root, '.workflow', 'registry.json')

if not os.path.exists(registry_path):
    # 레지스트리 없음 = 활성 워크플로우 없음 -> 통과
    # 카운터 초기화
    if os.path.exists(counter_file):
        os.remove(counter_file)
    sys.exit(0)

try:
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry = json.load(f)
except (json.JSONDecodeError, IOError):
    sys.exit(0)

if not registry:
    # 빈 레지스트리 -> 통과
    if os.path.exists(counter_file):
        os.remove(counter_file)
    sys.exit(0)

# 활성 워크플로우 중 진행 중인 것 찾기
terminal_phases = ('COMPLETED', 'FAILED', 'CANCELLED', 'STALE', '')
active_workflows = []
for key, entry in registry.items():
    phase = entry.get('phase', '').upper()
    # 종료 상태가 아닌 워크플로우
    if phase not in terminal_phases:
        active_workflows.append({'key': key, 'phase': phase, 'entry': entry})

if not active_workflows:
    # 모든 워크플로우가 종료 상태 -> 카운터 확실히 정리 후 통과
    try:
        if os.path.exists(counter_file):
            os.remove(counter_file)
    except OSError:
        pass
    sys.exit(0)

# PLAN phase 예외: AskUserQuestion 대기 중일 수 있으므로 차단하지 않음
# 모든 활성 워크플로우가 PLAN phase이면 통과
all_plan = all(w['phase'] == 'PLAN' for w in active_workflows)
if all_plan:
    # PLAN phase에서는 사용자 입력 대기를 존중
    sys.exit(0)

# 진행 중인 워크플로우가 있음 (INIT, WORK, REPORT 등)
# 카운터 확인 (연속 차단 횟수)
block_count = 0
try:
    if os.path.exists(counter_file):
        with open(counter_file, 'r') as f:
            block_count = int(f.read().strip())
except (ValueError, IOError):
    block_count = 0

# 연속 3회 차단 시 허용 (무한 루프 방지)
if block_count >= 3:
    # 카운터 초기화 후 통과
    try:
        os.remove(counter_file)
    except OSError:
        pass
    sys.exit(0)

# 카운터 증가
block_count += 1
try:
    os.makedirs(os.path.dirname(counter_file), exist_ok=True)
    with open(counter_file, 'w') as f:
        f.write(str(block_count))
except IOError:
    pass

# 차단: 워크플로우가 진행 중
# block reason은 최소한의 정보만 포함 (LLM이 불필요한 상태 설명을 출력하지 않도록)
result = {
    'decision': 'block',
    'reason': f'Continue workflow. ({block_count}/3)'
}
print(json.dumps(result, ensure_ascii=False))
" 2>/dev/null

exit 0
