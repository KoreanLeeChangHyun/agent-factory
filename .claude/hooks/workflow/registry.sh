#!/bin/bash
# registry.sh - 워크플로우 레지스트리 관리 CLI
#
# 사용법:
#   wf-registry list                    # 모든 엔트리 컬러 테이블 출력
#   wf-registry clean                   # 정리 대상 엔트리 제거
#   wf-registry clean --dry-run         # 정리 대상 미리보기만 (삭제 안 함)
#   wf-registry clean --force           # 전체 registry 초기화 ({})
#   wf-registry remove <key>            # 특정 키 단건 제거
#
# 종료 코드:
#   0 - 성공
#   1 - 실패 (인자 오류, 파일 없음 등)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
REGISTRY_FILE="${PROJECT_ROOT}/.workflow/registry.json"

# --- 색상 코드 ---
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'
RED='\033[0;31m'
BLUE='\033[0;34m'
GREEN='\033[0;32m'
PURPLE='\033[0;35m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'

# --- 도움말 함수 ---
cmd_help() {
    echo -e "${BOLD}wf-registry${RESET} - 워크플로우 레지스트리 관리"
    echo ""
    echo -e "  ${CYAN}list${RESET}                  모든 엔트리 조회 (컬러 테이블)"
    echo -e "  ${CYAN}clean${RESET}                 정리 대상 엔트리 제거"
    echo -e "  ${CYAN}clean --dry-run${RESET}       정리 대상 미리보기 (제거하지 않음)"
    echo -e "  ${CYAN}clean --force${RESET}         전체 레지스트리 초기화 ({})"
    echo -e "  ${CYAN}remove <key>${RESET}          특정 YYYYMMDD-HHMMSS 키 단건 제거"
    echo -e "  ${CYAN}help${RESET}                  이 도움말 표시"
    echo ""
    echo -e "${BOLD}정리 대상 (clean):${RESET}"
    echo "  - COMPLETED / FAILED / STALE / CANCELLED phase 엔트리"
    echo "  - status.json이 없는 고아 엔트리"
    echo "  - registry phase와 status.json phase가 불일치하는 엔트리"
    echo "  - REPORT phase인데 1시간 이상 경과한 잔류 엔트리"
    echo "  - INIT / PLAN phase인데 1시간 이상 경과한 잔류 엔트리 (중단된 워크플로우)"
    echo ""
    echo -e "${DIM}참고: .workflow/ 하위 디렉토리 물리 파일 삭제는 wf-clear를 사용하세요${RESET}"
}

# --- 인자 확인 ---
if [ $# -lt 1 ]; then
    cmd_help
    exit 1
fi

SUBCMD="$1"
shift

# --- registry.json 존재 확인 ---
check_registry() {
    if [ ! -f "$REGISTRY_FILE" ]; then
        echo -e "${YELLOW}[WARN] registry.json이 존재하지 않습니다: ${REGISTRY_FILE}${RESET}"
        exit 0
    fi
}

# =============================================================================
# list - 모든 엔트리를 컬러 테이블로 출력
# =============================================================================
cmd_list() {
    check_registry

    WF_REGISTRY="$REGISTRY_FILE" WF_PROJECT_ROOT="$PROJECT_ROOT" python3 -c "
import json, os, sys

registry_file = os.environ['WF_REGISTRY']
project_root = os.environ['WF_PROJECT_ROOT']

# ANSI 색상
BOLD = '\033[1m'
DIM = '\033[2m'
RESET = '\033[0m'
RED = '\033[0;31m'
BLUE = '\033[0;34m'
GREEN = '\033[0;32m'
PURPLE = '\033[0;35m'
YELLOW = '\033[0;33m'
GRAY = '\033[0;90m'
CYAN = '\033[0;36m'

phase_colors = {
    'INIT': RED,
    'PLAN': BLUE,
    'WORK': GREEN,
    'REPORT': PURPLE,
    'COMPLETED': GRAY,
    'STALE': GRAY,
    'FAILED': YELLOW,
    'CANCELLED': GRAY,
}

try:
    with open(registry_file, 'r', encoding='utf-8') as f:
        registry = json.load(f)
except (json.JSONDecodeError, IOError) as e:
    print(f'{RED}[ERROR] registry.json 읽기 실패: {e}{RESET}', file=sys.stderr)
    sys.exit(1)

if not isinstance(registry, dict) or not registry:
    print(f'{YELLOW}레지스트리가 비어있습니다.{RESET}')
    sys.exit(0)

# 컬럼 폭 계산
entries = []
max_key = len('KEY')
max_title = len('TITLE')
max_phase = len('PHASE')
max_cmd = len('COMMAND')

for key in sorted(registry.keys()):
    entry = registry[key]
    title = entry.get('title', '(없음)')
    phase = entry.get('phase', '(없음)')
    command = entry.get('command', '(없음)')
    entries.append((key, title, phase, command))
    max_key = max(max_key, len(key))
    max_title = max(max_title, len(title))
    max_phase = max(max_phase, len(phase))
    max_cmd = max(max_cmd, len(command))

# title이 너무 길면 제한
if max_title > 40:
    max_title = 40

separator_width = max_key + max_title + max_phase + max_cmd + 13
separator = '-' * separator_width

print()
print(f'  {BOLD}워크플로우 레지스트리{RESET}  {DIM}({len(entries)}개 엔트리){RESET}')
print(f'  {DIM}{separator}{RESET}')
print(f'  {BOLD}{CYAN}{\"KEY\":<{max_key}}{RESET}  {BOLD}{\"TITLE\":<{max_title}}{RESET}  {BOLD}{\"PHASE\":<{max_phase}}{RESET}  {BOLD}{\"COMMAND\":<{max_cmd}}{RESET}')
print(f'  {DIM}{separator}{RESET}')

for key, title, phase, command in entries:
    # title 자르기
    if len(title) > max_title:
        title = title[:max_title-2] + '..'
    color = phase_colors.get(phase, '')
    reset = RESET if color else ''
    print(f'  {key:<{max_key}}  {title:<{max_title}}  {color}{phase:<{max_phase}}{reset}  {command:<{max_cmd}}')

print(f'  {DIM}{separator}{RESET}')
print()
" 2>&1
}

# =============================================================================
# clean - 정리 대상 엔트리 제거
# =============================================================================
cmd_clean() {
    local force=false
    local dry_run=false

    while [ $# -gt 0 ]; do
        case "$1" in
            --force) force=true ;;
            --dry-run) dry_run=true ;;
            *) echo -e "${RED}[ERROR] 알 수 없는 옵션: $1${RESET}"; exit 1 ;;
        esac
        shift
    done

    check_registry

    # --force: 전체 초기화
    if [ "$force" = true ]; then
        echo '{}' > "$REGISTRY_FILE"
        echo -e "${GREEN}[OK]${RESET} 레지스트리를 초기화했습니다. ({})"
        return
    fi

    # 일반 clean
    WF_REGISTRY="$REGISTRY_FILE" WF_PROJECT_ROOT="$PROJECT_ROOT" WF_DRY_RUN="$dry_run" python3 -c "
import json, os, sys, tempfile, shutil
from datetime import datetime, timezone, timedelta

registry_file = os.environ['WF_REGISTRY']
project_root = os.environ['WF_PROJECT_ROOT']
dry_run = os.environ.get('WF_DRY_RUN', 'false') == 'true'

# ANSI 색상
BOLD = '\033[1m'
DIM = '\033[2m'
RESET = '\033[0m'
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[0;33m'
GRAY = '\033[0;90m'

try:
    with open(registry_file, 'r', encoding='utf-8') as f:
        registry = json.load(f)
except (json.JSONDecodeError, IOError) as e:
    print(f'{RED}[ERROR] registry.json 읽기 실패: {e}{RESET}', file=sys.stderr)
    sys.exit(1)

if not isinstance(registry, dict) or not registry:
    print(f'{YELLOW}레지스트리가 비어있습니다.{RESET}')
    sys.exit(0)

kst = timezone(timedelta(hours=9))
now = datetime.now(kst)
report_ttl_hours = 1

remove_phases = {'STALE', 'COMPLETED', 'FAILED', 'CANCELLED'}
targets = []  # (key, reason)

for key, entry in registry.items():
    work_dir = entry.get('workDir', '')
    registry_phase = entry.get('phase', '')

    if not work_dir:
        targets.append((key, 'empty workDir'))
        continue

    if work_dir.startswith('/'):
        abs_work_dir = work_dir
    else:
        abs_work_dir = os.path.join(project_root, work_dir)

    status_file = os.path.join(abs_work_dir, 'status.json')

    # 고아: status.json 없음
    if not os.path.isfile(status_file):
        targets.append((key, 'orphan (no status.json)'))
        continue

    # status.json 읽기
    try:
        with open(status_file, 'r', encoding='utf-8') as f:
            status_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        targets.append((key, 'orphan (status.json unreadable)'))
        continue

    status_phase = status_data.get('phase', '')

    # STALE/COMPLETED/FAILED/CANCELLED
    if status_phase in remove_phases:
        targets.append((key, f'status phase={status_phase}'))
        continue

    # registry phase가 종료 상태 (status.json과 무관)
    if registry_phase in remove_phases and status_phase not in remove_phases:
        targets.append((key, f'registry phase={registry_phase} (status={status_phase})'))
        continue

    # registry-status phase 불일치 (status가 COMPLETED인데 registry가 REPORT 등)
    if status_phase != registry_phase and status_phase in remove_phases:
        targets.append((key, f'phase mismatch: registry={registry_phase}, status={status_phase}'))
        continue

    # REPORT 잔류 1시간 초과
    if registry_phase == 'REPORT' or status_phase == 'REPORT':
        time_str = status_data.get('updated_at') or status_data.get('created_at', '')
        if time_str:
            try:
                updated = datetime.fromisoformat(time_str)
                elapsed = now - updated
                if elapsed.total_seconds() > report_ttl_hours * 3600:
                    targets.append((key, f'REPORT stale ({elapsed.total_seconds()/3600:.1f}h)'))
                    continue
            except (ValueError, TypeError):
                pass

    # INIT/PLAN 잔류 1시간 초과 (중단된 워크플로우 정리)
    if status_phase in ('INIT', 'PLAN'):
        time_str = status_data.get('updated_at') or status_data.get('created_at', '')
        if time_str:
            try:
                updated = datetime.fromisoformat(time_str)
                elapsed = now - updated
                if elapsed.total_seconds() > report_ttl_hours * 3600:
                    targets.append((key, f'{status_phase} stale ({elapsed.total_seconds()/3600:.1f}h)'))
                    continue
            except (ValueError, TypeError):
                pass

if not targets:
    print(f'{GREEN}[OK]{RESET} 정리 대상 엔트리가 없습니다.')
    sys.exit(0)

# 목록 출력
mode_label = f'{YELLOW}[DRY-RUN]{RESET}' if dry_run else f'{RED}[CLEAN]{RESET}'
print()
print(f'  {mode_label} 정리 대상: {len(targets)}개')
print()
max_key = max(len(k) for k, _ in targets)
for key, reason in sorted(targets):
    print(f'  {RED}x{RESET} {key:<{max_key}}  {DIM}{reason}{RESET}')
print()

if dry_run:
    print(f'  {DIM}실제 삭제하려면: wf-registry clean{RESET}')
    print()
    sys.exit(0)

# 삭제 실행
for key, _ in targets:
    del registry[key]

# 원자적 쓰기
registry_dir = os.path.dirname(registry_file)
fd, tmp_path = tempfile.mkstemp(dir=registry_dir, suffix='.tmp')
try:
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
        f.write('\n')
    shutil.move(tmp_path, registry_file)
    print(f'  {GREEN}[OK]{RESET} {len(targets)}개 엔트리를 제거했습니다. (잔여: {len(registry)}개)')
    print()
except Exception as e:
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
    print(f'{RED}[ERROR] registry.json 쓰기 실패: {e}{RESET}', file=sys.stderr)
    sys.exit(1)
" 2>&1
}

# =============================================================================
# remove - 특정 키 단건 제거
# =============================================================================
cmd_remove() {
    if [ $# -lt 1 ] || [ -z "$1" ]; then
        echo -e "${RED}[ERROR] 사용법: wf-registry remove <YYYYMMDD-HHMMSS>${RESET}"
        exit 1
    fi

    local target_key="$1"
    check_registry

    WF_REGISTRY="$REGISTRY_FILE" WF_KEY="$target_key" python3 -c "
import json, os, sys, tempfile, shutil

registry_file = os.environ['WF_REGISTRY']
target_key = os.environ['WF_KEY']

RESET = '\033[0m'
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[0;33m'

try:
    with open(registry_file, 'r', encoding='utf-8') as f:
        registry = json.load(f)
except (json.JSONDecodeError, IOError) as e:
    print(f'{RED}[ERROR] registry.json 읽기 실패: {e}{RESET}', file=sys.stderr)
    sys.exit(1)

if not isinstance(registry, dict):
    print(f'{RED}[ERROR] registry.json 형식이 올바르지 않습니다.{RESET}', file=sys.stderr)
    sys.exit(1)

if target_key not in registry:
    print(f'{YELLOW}[WARN] 키를 찾을 수 없습니다: {target_key}{RESET}')
    sys.exit(0)

# 삭제 대상 정보 출력
entry = registry[target_key]
title = entry.get('title', '(없음)')
phase = entry.get('phase', '(없음)')
print(f'  제거: {target_key} ({title}, phase={phase})')

del registry[target_key]

# 원자적 쓰기
registry_dir = os.path.dirname(registry_file)
fd, tmp_path = tempfile.mkstemp(dir=registry_dir, suffix='.tmp')
try:
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
        f.write('\n')
    shutil.move(tmp_path, registry_file)
    print(f'{GREEN}[OK]{RESET} 키 {target_key}을 제거했습니다. (잔여: {len(registry)}개)')
except Exception as e:
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
    print(f'{RED}[ERROR] registry.json 쓰기 실패: {e}{RESET}', file=sys.stderr)
    sys.exit(1)
" 2>&1
}

# =============================================================================
# 서브커맨드 라우팅
# =============================================================================
case "$SUBCMD" in
    list)
        cmd_list
        ;;
    clean)
        cmd_clean "$@"
        ;;
    remove)
        cmd_remove "$@"
        ;;
    help|--help|-h)
        cmd_help
        ;;
    *)
        echo -e "${RED}[ERROR] 알 수 없는 서브커맨드: $SUBCMD${RESET}"
        echo -e "${DIM}사용법: wf-registry list | clean [--dry-run|--force] | remove <key> | help${RESET}"
        exit 1
        ;;
esac

exit 0
