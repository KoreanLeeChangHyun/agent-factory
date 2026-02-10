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
        if phase in ('COMPLETED', 'FAILED', 'STALE'):
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

# --- Step 2: registry.json 좀비 정리 (STALE/COMPLETED/FAILED/CANCELLED 제거 + 고아 정리) ---

WF_PROJECT_ROOT="$PROJECT_ROOT" python3 -c "
import json, os, sys, tempfile, shutil

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

remove_phases = {'STALE', 'COMPLETED', 'FAILED', 'CANCELLED'}
keys_to_remove = []

for key, entry in registry.items():
    work_dir = entry.get('workDir', '')
    if not work_dir:
        keys_to_remove.append(key)
        continue

    # status.json 존재 여부 확인 (고아 정리)
    if work_dir.startswith('/'):
        abs_work_dir = work_dir
    else:
        abs_work_dir = os.path.join(project_root, work_dir)

    status_file = os.path.join(abs_work_dir, 'status.json')

    if not os.path.isfile(status_file):
        keys_to_remove.append(key)
        continue

    # status.json의 phase 확인 (STALE/COMPLETED/FAILED/CANCELLED 제거)
    try:
        with open(status_file, 'r', encoding='utf-8') as f:
            status_data = json.load(f)
        phase = status_data.get('phase', '')
        if phase in remove_phases:
            keys_to_remove.append(key)
    except (json.JSONDecodeError, IOError):
        # 읽기 실패한 엔트리는 고아로 간주
        keys_to_remove.append(key)

if not keys_to_remove:
    sys.exit(0)

for key in keys_to_remove:
    del registry[key]

# 원자적 쓰기
registry_dir = os.path.dirname(registry_file)
fd, tmp_path = tempfile.mkstemp(dir=registry_dir, suffix='.tmp')
try:
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
        f.write('\n')
    shutil.move(tmp_path, registry_file)
    print(f'[INFO] registry cleanup: {len(keys_to_remove)} entry(ies) removed ({\", \".join(keys_to_remove)})', file=sys.stderr)
except Exception:
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
" 2>&1 || true

exit 0
