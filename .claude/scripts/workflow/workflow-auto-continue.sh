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
#   - 종료 phase (COMPLETED/FAILED/CANCELLED/STALE/REPORT)에서는 차단하지 않음
#   - .done-marker 파일 존재 시 즉시 통과 (DONE 배너 이후 block 방지)
#   - stop_hook_active=true일 때는 이미 계속 진행 중이므로 카운터만 증가
#   - bypass 파일/환경변수로 비활성화 가능
#   - TTL 30분: 활성 워크플로우의 status.json이 30분 이상 갱신 없으면 STALE 자동 전환
#   - 세션 불일치: 현재 session_id와 워크플로우 session_id가 다르면 고아로 판단하여 차단하지 않음

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

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
import sys, json, os, tempfile, shutil
from datetime import datetime, timezone, timedelta

counter_file = os.environ['COUNTER_FILE']
project_root = os.environ['PROJECT_ROOT']

STALE_TTL_MINUTES = 30

def clear_counter():
    try:
        if os.path.exists(counter_file):
            os.remove(counter_file)
    except OSError:
        pass

# .done-marker 파일 존재 시 즉시 통과 (DONE 배너 이후 block 방지)
done_marker = os.path.join(project_root, '.workflow', '.done-marker')
if os.path.exists(done_marker):
    clear_counter()
    sys.exit(0)

# stdin에서 입력 읽기
try:
    data = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(0)

# stop_hook_active 확인 (이미 Stop Hook으로 계속 진행 중인지)
stop_hook_active = data.get('stop_hook_active', False)

# 현재 세션 ID (고아 워크플로우 판별에 사용)
current_session_id = data.get('session_id', '')

# registry.json에서 활성 워크플로우 확인
registry_path = os.path.join(project_root, '.workflow', 'registry.json')

if not os.path.exists(registry_path):
    clear_counter()
    sys.exit(0)

try:
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry = json.load(f)
except (json.JSONDecodeError, IOError):
    sys.exit(0)

if not registry:
    clear_counter()
    sys.exit(0)

# 활성 워크플로우 중 진행 중인 것 찾기
terminal_phases = ('COMPLETED', 'FAILED', 'CANCELLED', 'STALE', '', 'REPORT')
active_workflows = []
for key, entry in registry.items():
    phase = entry.get('phase', '').upper()
    if phase not in terminal_phases:
        active_workflows.append({'key': key, 'phase': phase, 'entry': entry})

if not active_workflows:
    clear_counter()
    sys.exit(0)

# --- TTL 검사: 활성 워크플로우의 status.json에서 updated_at 확인 ---
# 30분 이상 갱신 없는 워크플로우를 STALE로 자동 전환
kst = timezone(timedelta(hours=9))
now = datetime.now(kst)
stale_threshold = STALE_TTL_MINUTES * 60  # seconds

registry_changed = False
still_active = []

for wf in active_workflows:
    key = wf['key']
    entry = wf['entry']
    work_dir = entry.get('workDir', '')

    if not work_dir:
        continue

    if work_dir.startswith('/'):
        abs_work_dir = work_dir
    else:
        abs_work_dir = os.path.join(project_root, work_dir)

    status_file = os.path.join(abs_work_dir, 'status.json')
    is_stale = False

    if not os.path.isfile(status_file):
        # status.json 없음 = 고아 워크플로우 -> 레지스트리에서 제거
        registry[key]['phase'] = 'STALE'
        registry_changed = True
        continue

    try:
        with open(status_file, 'r', encoding='utf-8') as f:
            status_data = json.load(f)

        # 세션 ID 불일치 검사: 워크플로우가 다른 세션에서 시작되었으면 고아로 판단
        wf_session_id = status_data.get('session_id', '')
        wf_linked = status_data.get('linked_sessions', [])
        session_match = (
            current_session_id and wf_session_id and
            (current_session_id == wf_session_id or current_session_id in wf_linked)
        )

        # TTL 검사
        time_str = status_data.get('updated_at') or status_data.get('created_at', '')
        elapsed = 0
        if time_str:
            updated = datetime.fromisoformat(time_str)
            elapsed = (now - updated).total_seconds()

        # STALE 판정: 세션 불일치이거나 TTL 만료
        if (not session_match and current_session_id) or elapsed > stale_threshold:
                is_stale = True
                # status.json을 STALE로 전환
                transition_time = now.strftime('%Y-%m-%dT%H:%M:%S+09:00')
                old_phase = status_data.get('phase', '')
                status_data['phase'] = 'STALE'
                status_data['updated_at'] = transition_time
                if 'transitions' not in status_data:
                    status_data['transitions'] = []
                status_data['transitions'].append({
                    'from': old_phase,
                    'to': 'STALE',
                    'at': transition_time
                })

                # 원자적 쓰기
                status_dir = os.path.dirname(status_file)
                fd, tmp_path = tempfile.mkstemp(dir=status_dir, suffix='.tmp')
                try:
                    with os.fdopen(fd, 'w', encoding='utf-8') as f:
                        json.dump(status_data, f, ensure_ascii=False, indent=2)
                        f.write('\n')
                    shutil.move(tmp_path, status_file)
                except Exception:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)

                # 레지스트리도 STALE로 갱신
                registry[key]['phase'] = 'STALE'
                registry_changed = True
    except (json.JSONDecodeError, IOError, ValueError):
        pass

    if not is_stale:
        still_active.append(wf)

# 레지스트리 변경 시 저장
if registry_changed:
    registry_dir = os.path.dirname(registry_path)
    fd, tmp_path = tempfile.mkstemp(dir=registry_dir, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)
            f.write('\n')
        shutil.move(tmp_path, registry_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

# TTL 정리 후 활성 워크플로우가 없으면 통과
if not still_active:
    clear_counter()
    sys.exit(0)

# PLAN phase 예외: AskUserQuestion 대기 중일 수 있으므로 차단하지 않음
all_plan = all(w['phase'] == 'PLAN' for w in still_active)
if all_plan:
    sys.exit(0)

# 진행 중인 워크플로우가 있음 (INIT, WORK 등)
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
    clear_counter()
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
result = {
    'decision': 'block',
    'reason': f'Continue workflow. ({block_count}/3)'
}
print(json.dumps(result, ensure_ascii=False))
" 2>/dev/null

exit 0
