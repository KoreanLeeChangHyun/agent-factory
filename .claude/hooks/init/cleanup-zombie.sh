#!/bin/bash
# cleanup-zombie.sh - 좀비 워크플로우 정리 독립 스크립트
# init-workflow.sh에서 분리된 좀비 정리 로직 (Step 8 + Step 8b)
#
# 기능:
#   1. .workflow/ 하위에서 TTL(24시간) 만료 + 미완료 status.json을 STALE로 전환
#   2. registry.json에서 STALE/COMPLETED/FAILED/CANCELLED 엔트리 제거 + 고아 정리
#
# 사용법:
#   cleanup-zombie.sh [project_root]
#
# 인자:
#   project_root - (선택적) 프로젝트 루트 경로. 미지정 시 스크립트 위치 기준으로 자동 탐지
#
# 종료 코드:
#   0 - 성공 (정리 대상 없음 포함)
#   1 - 실패

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 프로젝트 루트: 인자로 전달받거나 스크립트 위치 기준 자동 탐지
if [ $# -ge 1 ] && [ -n "$1" ]; then
    PROJECT_ROOT="$1"
else
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
fi

# --- Step 1: 워크플로우 좀비 정리 ---
# .workflow/ 하위에서 TTL(24시간) 만료 + COMPLETED/FAILED가 아닌 status.json을 STALE로 전환

WF_PROJECT_ROOT="$PROJECT_ROOT" python3 -c "
import json, os, sys, tempfile, shutil
from datetime import datetime, timezone, timedelta

project_root = os.environ['WF_PROJECT_ROOT']
workflow_root = os.path.join(project_root, '.workflow')

if not os.path.isdir(workflow_root):
    sys.exit(0)

kst = timezone(timedelta(hours=9))
now = datetime.now(kst)
ttl_hours = 24

stale_count = 0

def process_status_file(status_file, status_dir):
    \"\"\"status.json을 TTL 검사하여 STALE로 전환. 반환: 전환 여부.\"\"\"
    try:
        with open(status_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        phase = data.get('phase', '')
        if phase in ('COMPLETED', 'FAILED', 'STALE', 'CANCELLED'):
            return False

        time_str = data.get('updated_at') or data.get('created_at', '')
        if not time_str:
            return False

        created = datetime.fromisoformat(time_str)
        elapsed = now - created

        if elapsed.total_seconds() > ttl_hours * 3600:
            transition_time = now.strftime('%Y-%m-%dT%H:%M:%S+09:00')
            data['phase'] = 'STALE'
            data['updated_at'] = transition_time
            if 'transitions' not in data:
                data['transitions'] = []
            data['transitions'].append({
                'from': phase,
                'to': 'STALE',
                'at': transition_time
            })

            fd, tmp_path = tempfile.mkstemp(dir=status_dir, suffix='.tmp')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.write('\n')
                shutil.move(tmp_path, status_file)
                return True
            except Exception:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        return False
    except (json.JSONDecodeError, IOError, ValueError):
        return False

# .workflow/<YYYYMMDD-HHMMSS>/ 타임스탬프 디렉토리 순회
for entry in os.listdir(workflow_root):
    entry_path = os.path.join(workflow_root, entry)
    if not os.path.isdir(entry_path) or entry.startswith('.'):
        continue

    # 중첩 구조 탐색: .workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>/status.json
    found = False
    for work_name in os.listdir(entry_path):
        wn_path = os.path.join(entry_path, work_name)
        if not os.path.isdir(wn_path) or work_name.startswith('.'):
            continue
        for cmd_name in os.listdir(wn_path):
            cmd_path = os.path.join(wn_path, cmd_name)
            if not os.path.isdir(cmd_path):
                continue
            nested_status = os.path.join(cmd_path, 'status.json')
            if os.path.exists(nested_status):
                if process_status_file(nested_status, cmd_path):
                    stale_count += 1
                found = True

    if not found:
        # 레거시 플랫 구조 호환: .workflow/<YYYYMMDD-HHMMSS>/status.json
        flat_status = os.path.join(entry_path, 'status.json')
        if os.path.exists(flat_status):
            if process_status_file(flat_status, entry_path):
                stale_count += 1

if stale_count > 0:
    print(f'[INFO] zombie cleanup: {stale_count} workflow(s) marked as STALE', file=sys.stderr)
" 2>&1 || true

# --- Step 2: registry.json 좀비 정리 (STALE/COMPLETED/FAILED/CANCELLED 제거 + REPORT 잔류 + 고아 정리) ---

WF_PROJECT_ROOT="$PROJECT_ROOT" python3 -c "
import json, os, sys, tempfile, shutil
from datetime import datetime, timezone, timedelta

project_root = os.environ['WF_PROJECT_ROOT']
registry_file = os.path.join(project_root, '.workflow', 'registry.json')

if not os.path.isfile(registry_file):
    sys.exit(0)

try:
    with open(registry_file, 'r', encoding='utf-8') as f:
        registry = json.load(f)
except (json.JSONDecodeError, IOError):
    sys.exit(0)

if not isinstance(registry, dict) or not registry:
    sys.exit(0)

kst = timezone(timedelta(hours=9))
now = datetime.now(kst)
report_ttl_hours = 1  # REPORT 단계 잔류 TTL

remove_phases = {'STALE', 'COMPLETED', 'FAILED', 'CANCELLED'}
keys_to_remove = []   # (key, reason) 튜플 리스트
removed_keys = []     # 키만 보관 (삭제용)

for key, entry in registry.items():
    work_dir = entry.get('workDir', '')
    if not work_dir:
        keys_to_remove.append((key, 'empty workDir'))
        removed_keys.append(key)
        continue

    # status.json 존재 여부 확인 (고아 정리)
    if work_dir.startswith('/'):
        abs_work_dir = work_dir
    else:
        abs_work_dir = os.path.join(project_root, work_dir)

    status_file = os.path.join(abs_work_dir, 'status.json')

    if not os.path.isfile(status_file):
        keys_to_remove.append((key, 'orphan (no status.json)'))
        removed_keys.append(key)
        continue

    # status.json 읽기
    try:
        with open(status_file, 'r', encoding='utf-8') as f:
            status_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        # 읽기 실패한 엔트리는 고아로 간주
        keys_to_remove.append((key, 'orphan (status.json unreadable)'))
        removed_keys.append(key)
        continue

    status_phase = status_data.get('phase', '')
    registry_phase = entry.get('phase', '')

    # 1. 기존 정리: STALE/COMPLETED/FAILED/CANCELLED (status.json 기준)
    if status_phase in remove_phases:
        keys_to_remove.append((key, f'status phase={status_phase}'))
        removed_keys.append(key)
        continue

    # 2. registry와 status.json의 phase 불일치 정리
    #    status.json이 COMPLETED인데 registry에는 REPORT로 남은 경우 등
    if status_phase in remove_phases and registry_phase not in remove_phases:
        keys_to_remove.append((key, f'phase mismatch: registry={registry_phase}, status={status_phase}'))
        removed_keys.append(key)
        continue

    # 3. REPORT 단계 잔류 엔트리 정리 (1시간 초과)
    if registry_phase == 'REPORT' or status_phase == 'REPORT':
        time_str = status_data.get('updated_at') or status_data.get('created_at', '')
        if time_str:
            try:
                updated = datetime.fromisoformat(time_str)
                elapsed = now - updated
                if elapsed.total_seconds() > report_ttl_hours * 3600:
                    keys_to_remove.append((key, f'REPORT stale ({elapsed.total_seconds()/3600:.1f}h elapsed)'))
                    removed_keys.append(key)
                    continue
            except (ValueError, TypeError):
                pass

if not keys_to_remove:
    sys.exit(0)

for key in removed_keys:
    del registry[key]

# 원자적 쓰기
registry_dir = os.path.dirname(registry_file)
fd, tmp_path = tempfile.mkstemp(dir=registry_dir, suffix='.tmp')
try:
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
        f.write('\n')
    shutil.move(tmp_path, registry_file)
    # 사유 포함 로그 출력
    details = '; '.join(f'{k}({r})' for k, r in keys_to_remove)
    print(f'[INFO] registry cleanup: {len(keys_to_remove)} entry(ies) removed [{details}]', file=sys.stderr)
except Exception:
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
" 2>&1 || true

exit 0
