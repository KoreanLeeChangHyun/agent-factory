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
#   실패: [WARN] <에러 내용> (stderr)

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
        waited=$((waited + 1))
        if [ "$waited" -ge "$max_wait" ]; then
            return 1
        fi
        sleep 1
    done
    return 0
}

release_lock() {
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
            print(f'[WARN] FSM guard: from_phase mismatch. expected={current_phase}, got={from_phase}. transition blocked.', file=sys.stderr)
            sys.exit(0)
        # 모드별 합법 전이 검증 (fsm-transitions.json 참조)
        allowed_table = fsm_data.get('modes', {}).get(workflow_mode, fsm_data.get('modes', {}).get('full', {}))
        allowed = allowed_table.get(from_phase, [])
        if to_phase not in allowed:
            print(f'[WARN] FSM guard: illegal transition {from_phase}->{to_phase}. allowed={allowed}. transition blocked.', file=sys.stderr)
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

    *)
        echo "[WARN] 알 수 없는 모드: $MODE (context|status|both|register|unregister|link-session 중 선택)" >&2
        ;;
esac

exit 0
