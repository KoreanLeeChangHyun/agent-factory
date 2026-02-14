#!/bin/bash
# 워크플로우 상태 일괄 업데이트 스크립트
# 로컬 .context.json + status.json 업데이트, 전역 레지스트리 등록/해제
#
# 사용법:
#   update-workflow-state.sh context <workDir> <agent>
#   update-workflow-state.sh status <workDir> <fromPhase> <toPhase>
#   update-workflow-state.sh both <workDir> <agent> <fromPhase> <toPhase>
#   update-workflow-state.sh register <workDir> [title] [command]
#   update-workflow-state.sh unregister <workDir>
#   update-workflow-state.sh link-session <workDir> <sessionId>
#   update-workflow-state.sh usage-pending <workDir> <agent_id> <task_id>
#   update-workflow-state.sh usage <workDir> <agent_name> <input_tokens> <output_tokens> [cache_creation] [cache_read] [task_id]
#   update-workflow-state.sh usage-finalize <workDir>
#   update-workflow-state.sh env <workDir> set|unset <KEY> [VALUE]
#
# workDir 형식 (3가지, 하위 호환):
#   단축 형식: YYYYMMDD-HHMMSS (registry.json에서 자동 해석)
#   중첩 구조: .workflow/YYYYMMDD-HHMMSS/<workName>/<command>
#   절대 경로: /full/path/to/.workflow/YYYYMMDD-HHMMSS/<workName>/<command>
#
# 단축 형식 예시:
#   update-workflow-state.sh both 20260208-185417 planner INIT PLAN
#   update-workflow-state.sh status 20260208-185417 PLAN WORK
#
# 모드:
#   context      - <workDir>/.context.json의 agent 필드만 업데이트 (로컬만)
#                  3번째 인자 <agent>는 에이전트 이름 문자열 (예: "planner", "worker", "reporter")
#                  주의: JSON 문자열을 인자로 받지 않음. agent 필드 외 다른 필드는 변경하지 않음
#   status       - <workDir>/status.json의 phase 변경, transitions 추가, updated_at 갱신
#                  + 전역 registry.json의 phase 동기화
#   both         - context + status 모두 한번에 처리
#   register     - 전역 레지스트리(.workflow/registry.json)에 워크플로우 등록 (mkdir 잠금)
#   unregister   - 전역 레지스트리에서 워크플로우 해제 (mkdir 잠금)
#   link-session - <workDir>/status.json의 linked_sessions 배열에 세션 ID를 중복 없이 추가
#                  빈 sessionId는 무시 (안전장치). 실패 시 경고만 출력, 워크플로우 비차단
#   usage-pending - <workDir>/usage.json의 _pending_workers 객체에 agent_id->taskId 매핑 등록
#                  Worker 호출 직전에 오케스트레이터가 실행. mkdir 잠금으로 원자적 기록
#   usage        - <workDir>/usage.json의 agents 객체에 에이전트별 토큰 데이터 기록
#                  Hook(usage-tracker.sh)에서 호출. Worker는 agents.workers.<taskId> 하위에 기록
#   usage-finalize - 워크플로우 완료 시 totals 계산, effective_tokens 산출, .prompt/usage.md 행 추가
#                  오케스트레이터가 reporter 반환 후 unregister 전에 호출
#   env          - .claude.env 파일의 환경 변수를 관리 (set/unset)
#                  허용 KEY: HOOKS_EDIT_ALLOWED, GUARD_ 접두사. 비허용 KEY는 경고 후 무시
#
# 레지스트리 스키마 (.workflow/registry.json):
#   {
#     "<YYYYMMDD>-<HHMMSS>": {
#       "title": "...",
#       "phase": "...",
#       "workDir": "...",
#       "command": "..."
#     }
#   }
#
# 종료 코드:
#   항상 0 (비차단 원칙: 실패 시에도 워크플로우 정상 진행)
#
# 출력:
#   성공: [OK] state updated: <상세>
#   FSM 가드 차단 시: [ERROR] <에러 내용> (stderr)
#   기타 실패: [WARN] <에러 내용> (stderr)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# ANSI 색상 코드
C_RED='\033[0;31m'
C_BLUE='\033[0;34m'
C_GREEN='\033[0;32m'
C_PURPLE='\033[0;35m'
C_YELLOW='\033[0;33m'
C_RESET='\033[0m'

# phase별 색상 함수 (phase 이름을 ANSI 색상으로 감싸서 반환)
colorize_phase() {
    local phase="$1"
    case "$phase" in
        INIT)       echo "${C_RED}${phase}${C_RESET}" ;;
        PLAN)       echo "${C_BLUE}${phase}${C_RESET}" ;;
        WORK)       echo "${C_GREEN}${phase}${C_RESET}" ;;
        REPORT)     echo "${C_PURPLE}${phase}${C_RESET}" ;;
        *)          echo "${phase}" ;;
    esac
}

# 인자 확인
if [ $# -lt 2 ]; then
    echo "[WARN] 사용법: $0 context|status|both|register|unregister <workDir> [args...]" >&2
    exit 0
fi

MODE="$1"
WORK_DIR="$2"

# YYYYMMDD-HHMMSS 단축 형식 해석
# 패턴 매칭: 정확히 15자리 (8자리-6자리)
if [[ "$WORK_DIR" =~ ^[0-9]{8}-[0-9]{6}$ ]]; then
    # registry.json에서 workDir 조회
    REGISTRY_KEY="$WORK_DIR"
    RESOLVED_DIR=$(WF_PROJECT_ROOT="$PROJECT_ROOT" WF_REGISTRY_KEY="$REGISTRY_KEY" python3 -c "
import json, sys, os
registry_file = os.path.join(os.environ['WF_PROJECT_ROOT'], '.workflow', 'registry.json')
if not os.path.exists(registry_file):
    sys.exit(1)
try:
    with open(registry_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    key = os.environ['WF_REGISTRY_KEY']
    if key in data and 'workDir' in data[key]:
        print(data[key]['workDir'])
    else:
        sys.exit(1)
except Exception:
    sys.exit(1)
" 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$RESOLVED_DIR" ]; then
        WORK_DIR="$RESOLVED_DIR"
    else
        # 레거시 폴백: .workflow/YYYYMMDD-HHMMSS (플랫 구조)
        WORK_DIR=".workflow/$REGISTRY_KEY"
        echo "[WARN] registry lookup failed for $REGISTRY_KEY, falling back to $WORK_DIR" >&2
    fi
fi

# 절대 경로 구성
if [[ "$WORK_DIR" = /* ]]; then
    ABS_WORK_DIR="$WORK_DIR"
else
    ABS_WORK_DIR="$PROJECT_ROOT/$WORK_DIR"
fi

GLOBAL_REGISTRY="$PROJECT_ROOT/.workflow/registry.json"
LOCAL_CONTEXT="$ABS_WORK_DIR/.context.json"
STATUS_FILE="$ABS_WORK_DIR/status.json"

# mkdir 기반 POSIX 잠금 (Linux/macOS 호환)
LOCK_DIR="${GLOBAL_REGISTRY}.lockdir"

acquire_lock() {
    local max_wait=5
    local waited=0
    while ! mkdir "$LOCK_DIR" 2>/dev/null; do
        # stale lock 감지: PID 파일에서 보유 프로세스 확인
        if [ -f "$LOCK_DIR/pid" ]; then
            local lock_pid
            lock_pid=$(cat "$LOCK_DIR/pid" 2>/dev/null)
            if [ -n "$lock_pid" ] && ! kill -0 "$lock_pid" 2>/dev/null; then
                # 프로세스가 존재하지 않으므로 stale lock 제거
                rm -rf "$LOCK_DIR"
                continue
            fi
        fi
        waited=$((waited + 1))
        if [ "$waited" -ge "$max_wait" ]; then
            return 1
        fi
        sleep 1
    done
    # 잠금 보유 프로세스 PID 기록
    echo $$ > "$LOCK_DIR/pid"
    return 0
}

release_lock() {
    rm -f "$LOCK_DIR/pid" 2>/dev/null
    rmdir "$LOCK_DIR" 2>/dev/null
}

# context 업데이트 함수 (로컬만, 원자적: 임시 파일 -> mv)
# agent 필드만 갱신. 다른 필드(title, workId, workName, command 등)는 변경하지 않음.
update_context() {
    local agent="$1"

    WF_AGENT="$agent" WF_CONTEXT_PATH="$LOCAL_CONTEXT" python3 -c "
import json, sys, os, tempfile, shutil

agent = os.environ['WF_AGENT']
fpath = os.environ['WF_CONTEXT_PATH']

if not os.path.exists(fpath):
    print(f'[WARN] .context.json not found: {fpath}', file=sys.stderr)
    sys.exit(0)

try:
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data['agent'] = agent

    # 원자적 업데이트: 임시 파일에 쓴 후 mv로 교체
    dir_name = os.path.dirname(fpath)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
        shutil.move(tmp_path, fpath)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
except Exception as e:
    print(f'[WARN] .context.json update failed ({fpath}): {e}', file=sys.stderr)
    sys.exit(0)

print(f'context -> agent={agent} (local)')
" 2>&1
}

# register 함수: 전역 레지스트리에 워크플로우 등록 (mkdir 잠금)
# 인자: [title] [command] (디렉터리명에서 추출 불가하므로 명시적 전달 권장)
register_workflow() {
    local reg_title="${1:-}"
    local reg_command="${2:-}"

    acquire_lock || {
        echo "[WARN] register: 잠금 획득 실패" >&2
        return
    }

    WF_WORK_DIR="$ABS_WORK_DIR" WF_REGISTRY="$GLOBAL_REGISTRY" WF_TITLE="$reg_title" WF_COMMAND="$reg_command" WF_PROJECT_ROOT="$PROJECT_ROOT" python3 -c "
import json, sys, os, tempfile, shutil, re

work_dir = os.environ['WF_WORK_DIR']
registry_file = os.environ['WF_REGISTRY']
reg_title = os.environ.get('WF_TITLE', '')
reg_command = os.environ.get('WF_COMMAND', '')

# workDir에서 키 추출
# 중첩 구조: .../<YYYYMMDD-HHMMSS>/<workName>/<command> -> 3단계 상위
# 레거시 플랫 구조: .../<YYYYMMDD-HHMMSS> -> basename 그대로
# YYYYMMDD-HHMMSS 패턴으로 판별
ts_pattern = re.compile(r'^\d{8}-\d{6}$')

basename = os.path.basename(work_dir)
if ts_pattern.match(basename):
    # 플랫 구조 (레거시 호환)
    registry_key = basename
else:
    # 중첩 구조: basename=<command>, parent=<workName>, grandparent=<YYYYMMDD-HHMMSS>
    grandparent = os.path.basename(os.path.dirname(os.path.dirname(work_dir)))
    if ts_pattern.match(grandparent):
        registry_key = grandparent
    else:
        # 폴백: 경로에서 YYYYMMDD-HHMMSS 패턴 탐색
        parts = work_dir.replace(os.sep, '/').split('/')
        registry_key = basename  # 최후 폴백
        for part in parts:
            if ts_pattern.match(part):
                registry_key = part
                break

# title과 command는 반드시 인자로 전달받아야 함 (디렉터리명에서 추출 불가)

# 상대 workDir 구성
project_root = os.environ['WF_PROJECT_ROOT']
if work_dir.startswith(project_root):
    rel_work_dir = os.path.relpath(work_dir, project_root)
else:
    rel_work_dir = work_dir

# 레지스트리 읽기 (없으면 빈 딕셔너리)
if os.path.exists(registry_file):
    try:
        with open(registry_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        data = {}
else:
    data = {}

# 딕셔너리가 아닌 경우(기존 형식) 초기화
if not isinstance(data, dict):
    data = {}

# 중복 등록 방지
if registry_key in data:
    print(f'register -> already registered: {registry_key}')
    sys.exit(0)

# 등록 (딕셔너리 스키마)
data[registry_key] = {
    'title': reg_title,
    'phase': 'INIT',
    'workDir': rel_work_dir,
    'command': reg_command
}

# 원자적 쓰기
dir_path = os.path.dirname(registry_file)
os.makedirs(dir_path, exist_ok=True)
fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix='.tmp')
try:
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    shutil.move(tmp_path, registry_file)
except Exception:
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
    raise

print(f'register -> key={registry_key}')
" 2>&1

    release_lock
}

# unregister 함수: 전역 레지스트리에서 워크플로우 해제 (mkdir 잠금)
unregister_workflow() {
    acquire_lock || {
        echo "[WARN] unregister: 잠금 획득 실패" >&2
        return
    }

    WF_WORK_DIR="$ABS_WORK_DIR" WF_REGISTRY="$GLOBAL_REGISTRY" python3 -c "
import json, sys, os, tempfile, shutil, re

work_dir = os.environ['WF_WORK_DIR']
registry_file = os.environ['WF_REGISTRY']

if not os.path.exists(registry_file):
    print(f'unregister -> registry not found, skipping')
    sys.exit(0)

try:
    with open(registry_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
except (json.JSONDecodeError, IOError):
    print(f'[WARN] unregister: registry read failed', file=sys.stderr)
    sys.exit(0)

if not isinstance(data, dict):
    print(f'unregister -> invalid registry format, skipping')
    sys.exit(0)

# workDir에서 키 추출 (중첩/플랫 구조 자동 감지)
ts_pattern = re.compile(r'^\d{8}-\d{6}$')
basename = os.path.basename(work_dir)
if ts_pattern.match(basename):
    registry_key = basename
else:
    grandparent = os.path.basename(os.path.dirname(os.path.dirname(work_dir)))
    if ts_pattern.match(grandparent):
        registry_key = grandparent
    else:
        parts = work_dir.replace(os.sep, '/').split('/')
        registry_key = basename
        for part in parts:
            if ts_pattern.match(part):
                registry_key = part
                break

if registry_key not in data:
    print(f'unregister -> key {registry_key} not found in registry, skipping')
    sys.exit(0)

# 키 삭제
del data[registry_key]

# 원자적 쓰기
dir_path = os.path.dirname(registry_file)
fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix='.tmp')
try:
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    shutil.move(tmp_path, registry_file)
except Exception:
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
    raise

print(f'unregister -> removed key={registry_key}')
" 2>&1

    release_lock
}

# 전역 레지스트리의 phase 동기화 함수 (mkdir 잠금)
sync_registry_phase() {
    local to_phase="$1"

    acquire_lock || {
        echo "[WARN] sync_registry_phase: 잠금 획득 실패" >&2
        return
    }

    WF_WORK_DIR="$ABS_WORK_DIR" WF_REGISTRY="$GLOBAL_REGISTRY" WF_TO_PHASE="$to_phase" python3 -c "
import json, sys, os, tempfile, shutil, re

work_dir = os.environ['WF_WORK_DIR']
registry_file = os.environ['WF_REGISTRY']
to_phase = os.environ['WF_TO_PHASE']

if not os.path.exists(registry_file):
    sys.exit(0)

try:
    with open(registry_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
except (json.JSONDecodeError, IOError):
    sys.exit(0)

if not isinstance(data, dict):
    sys.exit(0)

# workDir에서 키 추출 (중첩/플랫 구조 자동 감지)
ts_pattern = re.compile(r'^\d{8}-\d{6}$')
basename = os.path.basename(work_dir)
if ts_pattern.match(basename):
    registry_key = basename
else:
    grandparent = os.path.basename(os.path.dirname(os.path.dirname(work_dir)))
    if ts_pattern.match(grandparent):
        registry_key = grandparent
    else:
        parts = work_dir.replace(os.sep, '/').split('/')
        registry_key = basename
        for part in parts:
            if ts_pattern.match(part):
                registry_key = part
                break

if registry_key not in data:
    sys.exit(0)

# phase 동기화
data[registry_key]['phase'] = to_phase

# 원자적 쓰기
dir_path = os.path.dirname(registry_file)
fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix='.tmp')
try:
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    shutil.move(tmp_path, registry_file)
except Exception:
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
    raise
" 2>&1

    release_lock
}

# link-session 함수: status.json의 linked_sessions 배열에 세션 ID를 중복 없이 추가
link_session() {
    local session_id="$1"

    # 빈 sessionId 안전장치
    if [ -z "$session_id" ]; then
        echo "[WARN] link-session: sessionId가 비어있어 무시합니다." >&2
        return
    fi

    WF_SESSION_ID="$session_id" WF_STATUS_FILE="$STATUS_FILE" python3 -c "
import json, sys, os, tempfile, shutil

session_id = os.environ['WF_SESSION_ID']
status_file = os.environ['WF_STATUS_FILE']

if not os.path.exists(status_file):
    print(f'[WARN] status.json not found: {status_file}', file=sys.stderr)
    sys.exit(0)

try:
    with open(status_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # linked_sessions 배열 초기화 (없으면 생성)
    if 'linked_sessions' not in data or not isinstance(data.get('linked_sessions'), list):
        data['linked_sessions'] = []

    # 중복 체크 후 추가
    if session_id in data['linked_sessions']:
        print(f'link-session -> already linked: {session_id}')
        sys.exit(0)

    data['linked_sessions'].append(session_id)

    # 원자적 업데이트: 임시 파일에 쓴 후 mv로 교체
    dir_name = os.path.dirname(status_file)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
        shutil.move(tmp_path, status_file)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    print(f'link-session -> added: {session_id} (total: {len(data[\"linked_sessions\"])})')
except Exception as e:
    print(f'[WARN] link-session failed: {e}', file=sys.stderr)
    sys.exit(0)
" 2>&1
}

# status 업데이트 함수 (원자적: 임시 파일 -> mv)
# 로컬 status.json 업데이트 + 전역 registry.json phase 동기화
update_status() {
    local from_phase="$1"
    local to_phase="$2"

    WF_FROM_PHASE="$from_phase" WF_TO_PHASE="$to_phase" WF_STATUS_FILE="$STATUS_FILE" WF_SCRIPT_DIR="$SCRIPT_DIR" python3 -c "
import json, sys, os, tempfile, shutil
from datetime import datetime, timezone, timedelta

from_phase = os.environ['WF_FROM_PHASE']
to_phase = os.environ['WF_TO_PHASE']
status_file = os.environ['WF_STATUS_FILE']
script_dir = os.environ['WF_SCRIPT_DIR']
skip_guard = os.environ.get('WORKFLOW_SKIP_GUARD', '') == '1'

# 합법 전이 테이블을 fsm-transitions.json에서 로드
fsm_file = os.path.join(script_dir, 'fsm-transitions.json')
try:
    with open(fsm_file, 'r', encoding='utf-8') as f:
        fsm_data = json.load(f)
except Exception as e:
    print(f'[WARN] fsm-transitions.json load failed: {e}', file=sys.stderr)
    sys.exit(0)

if not os.path.exists(status_file):
    print(f'[WARN] status.json not found: {status_file}', file=sys.stderr)
    sys.exit(0)

try:
    with open(status_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # FSM 전이 검증 (WORKFLOW_SKIP_GUARD=1 시 우회)
    if not skip_guard:
        current_phase = data.get('phase', 'NONE')
        workflow_mode = data.get('mode', 'full').lower()
        # from_phase와 현재 phase 일치 검증
        if from_phase != current_phase:
            print(f'[ERROR] FSM guard: from_phase mismatch. expected={current_phase}, got={from_phase}. transition blocked.', file=sys.stderr)
            sys.exit(0)
        # 모드별 합법 전이 검증 (fsm-transitions.json 참조)
        allowed_table = fsm_data.get('modes', {}).get(workflow_mode, fsm_data.get('modes', {}).get('full', {}))
        allowed = allowed_table.get(from_phase, [])
        if to_phase not in allowed:
            print(f'[ERROR] FSM guard: illegal transition {from_phase}->{to_phase}. allowed={allowed}. transition blocked.', file=sys.stderr)
            sys.exit(0)

    # KST 시간 생성
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst).strftime('%Y-%m-%dT%H:%M:%S+09:00')

    # phase 업데이트
    data['phase'] = to_phase

    # updated_at 갱신
    data['updated_at'] = now

    # transitions 배열에 전이 추가
    if 'transitions' not in data:
        data['transitions'] = []
    data['transitions'].append({
        'from': from_phase,
        'to': to_phase,
        'at': now
    })

    # 원자적 업데이트: 임시 파일에 쓴 후 mv로 교체
    dir_name = os.path.dirname(status_file)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
        shutil.move(tmp_path, status_file)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    # 색상 매핑
    phase_colors = {
        'INIT': '\033[0;31m',
        'PLAN': '\033[0;34m',
        'WORK': '\033[0;32m',
        'REPORT': '\033[0;35m',
    }
    reset = '\033[0m'
    c_from = phase_colors.get(from_phase, '')
    r_from = reset if c_from else ''
    c_to = phase_colors.get(to_phase, '')
    r_to = reset if c_to else ''
    print(f'status -> {c_from}{from_phase}{r_from}->{c_to}{to_phase}{r_to}')
except Exception as e:
    print(f'[WARN] status.json update failed: {e}', file=sys.stderr)
" 2>&1

    # 전역 레지스트리 phase 동기화
    sync_registry_phase "$to_phase"
}

# usage-pending 함수: usage.json의 _pending_workers에 agent_id-taskId 매핑 등록
# Worker 호출 직전에 오케스트레이터가 실행하여, SubagentStop Hook에서 taskId를 조회할 수 있게 한다
usage_pending() {
    local agent_id="$1"
    local task_id="$2"

    if [ -z "$agent_id" ] || [ -z "$task_id" ]; then
        echo "[WARN] usage-pending: agent_id, task_id 인자가 필요합니다." >&2
        return
    fi

    local usage_file="$ABS_WORK_DIR/usage.json"
    local usage_lock="${usage_file}.lockdir"

    # mkdir 잠금 획득 (usage.json 전용)
    local max_wait=5 waited=0
    while ! mkdir "$usage_lock" 2>/dev/null; do
        # stale lock 감지: PID 파일에서 보유 프로세스 확인
        if [ -f "$usage_lock/pid" ]; then
            local lock_pid
            lock_pid=$(cat "$usage_lock/pid" 2>/dev/null)
            if [ -n "$lock_pid" ] && ! kill -0 "$lock_pid" 2>/dev/null; then
                rm -rf "$usage_lock"
                continue
            fi
        fi
        waited=$((waited + 1))
        if [ "$waited" -ge "$max_wait" ]; then
            echo "[WARN] usage-pending: 잠금 획득 실패" >&2
            return
        fi
        sleep 1
    done
    # 잠금 보유 프로세스 PID 기록
    echo $$ > "$usage_lock/pid"

    WF_USAGE_FILE="$usage_file" WF_AGENT_ID="$agent_id" WF_TASK_ID="$task_id" python3 -c "
import json, sys, os, tempfile, shutil

usage_file = os.environ['WF_USAGE_FILE']
agent_id = os.environ['WF_AGENT_ID']
task_id = os.environ['WF_TASK_ID']

# usage.json 읽기 (없으면 초기 구조 생성)
if os.path.exists(usage_file):
    try:
        with open(usage_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        data = {}
else:
    data = {}

# _pending_workers 초기화
if '_pending_workers' not in data or not isinstance(data.get('_pending_workers'), dict):
    data['_pending_workers'] = {}

data['_pending_workers'][agent_id] = task_id

# 원자적 쓰기
dir_name = os.path.dirname(usage_file)
os.makedirs(dir_name, exist_ok=True)
fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
try:
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    shutil.move(tmp_path, usage_file)
except Exception:
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
    raise

print(f'usage-pending -> {agent_id}={task_id}')
" 2>&1

    rm -f "$usage_lock/pid" 2>/dev/null
    rmdir "$usage_lock" 2>/dev/null
}

# env 관리 함수: .claude.env 파일의 환경 변수를 set/unset
# 허용 KEY: HOOKS_EDIT_ALLOWED, GUARD_ 접두사
# 원자적 수정: tmpfile + mv 패턴 적용
env_manage() {
    local action="$1"
    local key="$2"
    local value="$3"

    # 인자 검증
    if [ -z "$action" ] || [ -z "$key" ]; then
        echo "[WARN] env: action(set|unset)과 KEY 인자가 필요합니다." >&2
        return
    fi

    if [ "$action" != "set" ] && [ "$action" != "unset" ]; then
        echo "[WARN] env: action은 set 또는 unset만 허용됩니다. got=$action" >&2
        return
    fi

    if [ "$action" = "set" ] && [ -z "$value" ]; then
        echo "[WARN] env: set 명령에는 VALUE 인자가 필요합니다." >&2
        return
    fi

    # KEY 화이트리스트 검증: HOOKS_EDIT_ALLOWED 또는 GUARD_ 접두사만 허용
    if [ "$key" != "HOOKS_EDIT_ALLOWED" ] && [[ "$key" != GUARD_* ]]; then
        echo "[WARN] env: 허용되지 않는 KEY입니다: $key (허용: HOOKS_EDIT_ALLOWED, GUARD_* 접두사)" >&2
        return
    fi

    local env_file="$PROJECT_ROOT/.claude.env"

    # .claude.env 파일이 없으면 경고
    if [ ! -f "$env_file" ]; then
        echo "[WARN] env: .claude.env not found: $env_file" >&2
        return
    fi

    WF_ENV_FILE="$env_file" WF_ACTION="$action" WF_KEY="$key" WF_VALUE="$value" python3 -c "
import sys, os, tempfile, shutil

env_file = os.environ['WF_ENV_FILE']
action = os.environ['WF_ACTION']
key = os.environ['WF_KEY']
value = os.environ.get('WF_VALUE', '')

try:
    with open(env_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    if action == 'set':
        # KEY가 존재하면 값 갱신, 미존재 시 마지막 줄에 추가
        found = False
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(key + '='):
                new_lines.append(f'{key}={value}\n')
                found = True
            else:
                new_lines.append(line)

        if not found:
            # 마지막 줄이 빈 줄이 아니면 줄바꿈 추가
            if new_lines and not new_lines[-1].endswith('\n'):
                new_lines[-1] += '\n'
            new_lines.append(f'{key}={value}\n')

        lines = new_lines
        label = f'env -> set {key}={value}'

    elif action == 'unset':
        # KEY와 직전 주석 줄 함께 제거
        new_lines = []
        skip_prev_comment = False
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped.startswith(key + '='):
                # 직전 줄이 주석이면 함께 제거
                if new_lines and new_lines[-1].strip().startswith('#'):
                    new_lines.pop()
                # 현재 KEY 줄도 건너뜀
                i += 1
                continue
            new_lines.append(lines[i])
            i += 1

        lines = new_lines
        label = f'env -> unset {key}'

    # 원자적 쓰기: tmpfile + mv
    dir_name = os.path.dirname(env_file)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        shutil.move(tmp_path, env_file)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    print(label)
except Exception as e:
    print(f'[WARN] env failed: {e}', file=sys.stderr)
    sys.exit(0)
" 2>&1
}

# usage 함수: usage.json의 agents 객체에 에이전트별 토큰 데이터 기록
# Hook(usage-tracker.sh) 또는 오케스트레이터에서 호출
usage_record() {
    local agent_name="$1"
    local input_tokens="$2"
    local output_tokens="$3"
    local cache_creation="${4:-0}"
    local cache_read="${5:-0}"
    local task_id="${6:-}"

    if [ -z "$agent_name" ] || [ -z "$input_tokens" ] || [ -z "$output_tokens" ]; then
        echo "[WARN] usage: agent_name, input_tokens, output_tokens 인자가 필요합니다." >&2
        return
    fi

    local usage_file="$ABS_WORK_DIR/usage.json"
    local usage_lock="${usage_file}.lockdir"

    # mkdir 잠금 획득
    local max_wait=5 waited=0
    while ! mkdir "$usage_lock" 2>/dev/null; do
        # stale lock 감지: PID 파일에서 보유 프로세스 확인
        if [ -f "$usage_lock/pid" ]; then
            local lock_pid
            lock_pid=$(cat "$usage_lock/pid" 2>/dev/null)
            if [ -n "$lock_pid" ] && ! kill -0 "$lock_pid" 2>/dev/null; then
                rm -rf "$usage_lock"
                continue
            fi
        fi
        waited=$((waited + 1))
        if [ "$waited" -ge "$max_wait" ]; then
            echo "[WARN] usage: 잠금 획득 실패" >&2
            return
        fi
        sleep 1
    done
    # 잠금 보유 프로세스 PID 기록
    echo $$ > "$usage_lock/pid"

    WF_USAGE_FILE="$usage_file" WF_AGENT="$agent_name" WF_INPUT="$input_tokens" WF_OUTPUT="$output_tokens" WF_CACHE_CREATE="$cache_creation" WF_CACHE_READ="$cache_read" WF_TASK_ID="$task_id" python3 -c "
import json, sys, os, tempfile, shutil

usage_file = os.environ['WF_USAGE_FILE']
agent_name = os.environ['WF_AGENT']
input_tokens = int(os.environ['WF_INPUT'])
output_tokens = int(os.environ['WF_OUTPUT'])
cache_creation = int(os.environ.get('WF_CACHE_CREATE', '0'))
cache_read = int(os.environ.get('WF_CACHE_READ', '0'))
task_id = os.environ.get('WF_TASK_ID', '')

# usage.json 읽기
if os.path.exists(usage_file):
    try:
        with open(usage_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        data = {}
else:
    data = {}

if 'agents' not in data or not isinstance(data.get('agents'), dict):
    data['agents'] = {}

token_data = {
    'input_tokens': input_tokens,
    'output_tokens': output_tokens,
    'cache_creation_tokens': cache_creation,
    'cache_read_tokens': cache_read,
    'method': 'subagent_transcript'
}

# Worker인 경우 agents.workers.<taskId> 하위에 기록
if agent_name == 'worker' and task_id:
    if 'workers' not in data['agents'] or not isinstance(data['agents'].get('workers'), dict):
        data['agents']['workers'] = {}
    data['agents']['workers'][task_id] = token_data
    label = f'workers.{task_id}'
else:
    data['agents'][agent_name] = token_data
    label = agent_name

# 원자적 쓰기
dir_name = os.path.dirname(usage_file)
os.makedirs(dir_name, exist_ok=True)
fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
try:
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    shutil.move(tmp_path, usage_file)
except Exception:
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
    raise

print(f'usage -> {label}: in={input_tokens} out={output_tokens} cc={cache_creation} cr={cache_read}')
" 2>&1

    rm -f "$usage_lock/pid" 2>/dev/null
    rmdir "$usage_lock" 2>/dev/null
}

# usage-finalize 함수: totals 계산, effective_tokens 산출, .prompt/usage.md 행 추가
usage_finalize() {
    local usage_file="$ABS_WORK_DIR/usage.json"

    if [ ! -f "$usage_file" ]; then
        echo "[WARN] usage-finalize: usage.json not found: $usage_file" >&2
        return
    fi

    WF_USAGE_FILE="$usage_file" WF_REGISTRY="$GLOBAL_REGISTRY" WF_ABS_WORK_DIR="$ABS_WORK_DIR" WF_PROJECT_ROOT="$PROJECT_ROOT" python3 -c "
import json, sys, os, tempfile, shutil, re

usage_file = os.environ['WF_USAGE_FILE']
registry_file = os.environ['WF_REGISTRY']
work_dir = os.environ['WF_ABS_WORK_DIR']
project_root = os.environ['WF_PROJECT_ROOT']

def calc_effective(d):
    \"\"\"effective_tokens = input + output*5 + cache_creation*1.25 + cache_read*0.1\"\"\"
    return (
        d.get('input_tokens', 0)
        + d.get('output_tokens', 0) * 5
        + d.get('cache_creation_tokens', 0) * 1.25
        + d.get('cache_read_tokens', 0) * 0.1
    )

def sum_tokens(agents_list):
    \"\"\"에이전트 목록의 토큰 합산\"\"\"
    totals = {'input_tokens': 0, 'output_tokens': 0, 'cache_creation_tokens': 0, 'cache_read_tokens': 0}
    for a in agents_list:
        for k in totals:
            totals[k] += a.get(k, 0)
    return totals

def to_k(n):
    if n == 0:
        return '-'
    return f'{int(n) // 1000}k'

def to_k_precise(n):
    if n == 0:
        return '-'
    return f'{n / 1000:.1f}k'

try:
    # 1. usage.json 읽기
    with open(usage_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    agents = data.get('agents', {})

    # 2. 모든 에이전트 토큰 데이터 수집
    all_agents = []
    for key in ['orchestrator', 'init', 'planner', 'reporter']:
        if key in agents and isinstance(agents[key], dict):
            all_agents.append(agents[key])

    workers = agents.get('workers', {})
    if isinstance(workers, dict):
        for w in workers.values():
            if isinstance(w, dict):
                all_agents.append(w)

    # 3. totals 계산
    totals = sum_tokens(all_agents)
    totals['effective_tokens'] = calc_effective(totals)
    data['totals'] = totals

    # 4. usage.json 원자적 갱신
    dir_name = os.path.dirname(usage_file)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
        shutil.move(tmp_path, usage_file)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    # 5. registryKey 추출 (workDir에서)
    ts_pattern = re.compile(r'^\d{8}-\d{6}$')
    basename = os.path.basename(work_dir)
    if ts_pattern.match(basename):
        registry_key = basename
    else:
        grandparent = os.path.basename(os.path.dirname(os.path.dirname(work_dir)))
        if ts_pattern.match(grandparent):
            registry_key = grandparent
        else:
            parts = work_dir.replace(os.sep, '/').split('/')
            registry_key = basename
            for part in parts:
                if ts_pattern.match(part):
                    registry_key = part
                    break

    # 6. registry에서 메타데이터 조회
    reg_title = ''
    reg_command = ''
    if os.path.exists(registry_file):
        try:
            with open(registry_file, 'r', encoding='utf-8') as f:
                reg_data = json.load(f)
            if registry_key in reg_data:
                reg_title = reg_data[registry_key].get('title', '')
                reg_command = reg_data[registry_key].get('command', '')
        except Exception:
            pass

    # 제목 30자 절단
    title = reg_title[:30] if reg_title else ''

    # 날짜 추출: registryKey YYYYMMDD-HHMMSS -> MM-DD HH:MM
    date_str = ''
    if len(registry_key) >= 15:
        try:
            date_str = f'{registry_key[4:6]}-{registry_key[6:8]} {registry_key[9:11]}:{registry_key[11:13]}'
        except Exception:
            date_str = registry_key

    # 7. 에이전트별 effective_tokens 계산
    orch_eff = calc_effective(agents.get('orchestrator', {})) if 'orchestrator' in agents else 0
    init_eff = calc_effective(agents.get('init', {})) if 'init' in agents else 0
    plan_eff = calc_effective(agents.get('planner', {})) if 'planner' in agents else 0
    work_eff = sum(calc_effective(w) for w in workers.values() if isinstance(w, dict)) if isinstance(workers, dict) else 0
    report_eff = calc_effective(agents.get('reporter', {})) if 'reporter' in agents else 0
    total_eff = orch_eff + init_eff + plan_eff + work_eff + report_eff
    eff_weighted = totals.get('effective_tokens', total_eff)

    # 8. usage.md 행 생성
    row = (
        f'| {date_str} '
        f'| {registry_key} '
        f'| {title} '
        f'| {reg_command} '
        f'| {to_k(orch_eff)} '
        f'| {to_k(init_eff)} '
        f'| {to_k(plan_eff)} '
        f'| {to_k(work_eff)} '
        f'| {to_k(report_eff)} '
        f'| {to_k(total_eff)} '
        f'| {to_k_precise(eff_weighted)} |'
    )

    # 9. .prompt/usage.md 갱신
    usage_md = os.path.join(project_root, '.prompt', 'usage.md')
    marker = '<!-- 새 항목은 이 줄 아래에 추가됩니다 -->'
    header_line = '| 날짜 | 작업ID | 제목 | 명령어 | Orch | Init | Plan | Work | Report | 합계 | eff |'
    separator_line = '|------|--------|------|--------|------|------|------|------|--------|------|-----|'

    if os.path.exists(usage_md):
        with open(usage_md, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        content = ''

    # 마커가 없으면 초기 구조 생성
    if marker not in content:
        content = f'# 워크플로우 사용량 추적\n\n{marker}\n\n{header_line}\n{separator_line}\n'

    # separator 행 바로 아래에 데이터 행 삽입 (최신이 테이블 최상단)
    # 패턴: ...separator\n -> ...separator\nrow\n
    if separator_line in content:
        # separator 행의 첫 번째 출현 위치 찾기 (마커 이후)
        marker_pos = content.find(marker)
        if marker_pos >= 0:
            sep_pos = content.find(separator_line, marker_pos)
            if sep_pos >= 0:
                insert_pos = sep_pos + len(separator_line)
                # separator 다음에 이미 줄바꿈이 있으면 그 뒤에 삽입
                if insert_pos < len(content) and content[insert_pos] == '\n':
                    insert_pos += 1
                content = content[:insert_pos] + row + '\n' + content[insert_pos:]
            else:
                # separator를 찾지 못한 경우 마커 아래에 전체 테이블 구조 삽입
                content = content.replace(
                    marker,
                    f'{marker}\n\n{header_line}\n{separator_line}\n{row}'
                )
        else:
            content = content.replace(
                marker,
                f'{marker}\n\n{header_line}\n{separator_line}\n{row}'
            )
    else:
        # separator가 없는 경우 (마커만 존재) 전체 테이블 구조 생성
        content = content.replace(
            marker,
            f'{marker}\n\n{header_line}\n{separator_line}\n{row}'
        )

    # usage.md 원자적 쓰기
    os.makedirs(os.path.dirname(usage_md), exist_ok=True)
    fd2, tmp2 = tempfile.mkstemp(dir=os.path.dirname(usage_md), suffix='.tmp')
    try:
        with os.fdopen(fd2, 'w', encoding='utf-8') as f:
            f.write(content)
        shutil.move(tmp2, usage_md)
    except Exception:
        if os.path.exists(tmp2):
            os.unlink(tmp2)
        raise

    print(f'usage-finalize -> totals: eff={to_k_precise(eff_weighted)}, usage.md updated')

except Exception as e:
    print(f'[WARN] usage-finalize failed: {e}', file=sys.stderr)
" 2>&1
}

# 모드별 실행
case "$MODE" in
    context)
        AGENT="$3"
        if [ -z "$AGENT" ]; then
            echo "[WARN] context 모드: agent 인자가 필요합니다." >&2
            exit 0
        fi
        RESULT=$(update_context "$AGENT")
        echo -e "${C_YELLOW}[OK]${C_RESET} state updated: $RESULT"
        ;;

    status)
        FROM_PHASE="$3"
        TO_PHASE="$4"
        if [ -z "$FROM_PHASE" ] || [ -z "$TO_PHASE" ]; then
            echo "[WARN] status 모드: fromPhase, toPhase 인자가 필요합니다." >&2
            exit 0
        fi
        RESULT=$(update_status "$FROM_PHASE" "$TO_PHASE")
        echo -e "${C_YELLOW}[OK]${C_RESET} state updated: $RESULT"
        ;;

    both)
        AGENT="$3"
        FROM_PHASE="$4"
        TO_PHASE="$5"
        if [ -z "$AGENT" ] || [ -z "$FROM_PHASE" ] || [ -z "$TO_PHASE" ]; then
            echo "[WARN] both 모드: agent, fromPhase, toPhase 인자가 필요합니다." >&2
            exit 0
        fi
        RESULT_CTX=$(update_context "$AGENT")
        RESULT_STS=$(update_status "$FROM_PHASE" "$TO_PHASE")
        echo -e "${C_YELLOW}[OK]${C_RESET} state updated: $RESULT_CTX, $RESULT_STS"
        ;;

    register)
        REG_TITLE="${3:-}"
        REG_COMMAND="${4:-}"
        RESULT=$(register_workflow "$REG_TITLE" "$REG_COMMAND")
        echo -e "${C_YELLOW}[OK]${C_RESET} state updated: $RESULT"
        ;;

    unregister)
        RESULT=$(unregister_workflow)
        echo -e "${C_YELLOW}[OK]${C_RESET} state updated: $RESULT"
        ;;

    link-session)
        SESSION_ID="$3"
        if [ -z "$SESSION_ID" ]; then
            echo "[WARN] link-session 모드: sessionId 인자가 필요합니다." >&2
            exit 0
        fi
        RESULT=$(link_session "$SESSION_ID")
        echo -e "${C_YELLOW}[OK]${C_RESET} state updated: $RESULT"
        ;;

    usage-pending)
        AGENT_ID="$3"
        TASK_ID="$4"
        if [ -z "$AGENT_ID" ] || [ -z "$TASK_ID" ]; then
            echo "[WARN] usage-pending 모드: agent_id, task_id 인자가 필요합니다." >&2
            exit 0
        fi
        RESULT=$(usage_pending "$AGENT_ID" "$TASK_ID")
        echo -e "${C_YELLOW}[OK]${C_RESET} state updated: $RESULT"
        ;;

    usage)
        AGENT_NAME="$3"
        INPUT_TOKENS="$4"
        OUTPUT_TOKENS="$5"
        CACHE_CREATION="${6:-0}"
        CACHE_READ="${7:-0}"
        TASK_ID_ARG="${8:-}"
        if [ -z "$AGENT_NAME" ] || [ -z "$INPUT_TOKENS" ] || [ -z "$OUTPUT_TOKENS" ]; then
            echo "[WARN] usage 모드: agent_name, input_tokens, output_tokens 인자가 필요합니다." >&2
            exit 0
        fi
        RESULT=$(usage_record "$AGENT_NAME" "$INPUT_TOKENS" "$OUTPUT_TOKENS" "$CACHE_CREATION" "$CACHE_READ" "$TASK_ID_ARG")
        echo -e "${C_YELLOW}[OK]${C_RESET} state updated: $RESULT"
        ;;

    usage-finalize)
        RESULT=$(usage_finalize)
        echo -e "${C_YELLOW}[OK]${C_RESET} state updated: $RESULT"
        ;;

    env)
        ACTION="$3"
        KEY="$4"
        VALUE="${5:-}"
        if [ -z "$ACTION" ] || [ -z "$KEY" ]; then
            echo "[WARN] env 모드: action(set|unset), KEY 인자가 필요합니다." >&2
            exit 0
        fi
        RESULT=$(env_manage "$ACTION" "$KEY" "$VALUE")
        echo -e "${C_YELLOW}[OK]${C_RESET} state updated: $RESULT"
        ;;

    *)
        echo "[WARN] 알 수 없는 모드: $MODE (context|status|both|register|unregister|link-session|usage-pending|usage|usage-finalize|env 중 선택)" >&2
        ;;
esac

exit 0
