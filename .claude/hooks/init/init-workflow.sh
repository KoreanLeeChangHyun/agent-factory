#!/bin/bash
# init-workflow.sh - 워크플로우 초기화 통합 스크립트
# prompt.txt 읽기, 디렉터리 생성, 파일 복사/클리어, 메타데이터 생성, 좀비 정리, 레지스트리 등록을 일괄 수행
#
# 사용법:
#   init-workflow.sh <command> <workDir> <workId> <title> [claude_session_id]
#
# 인자:
#   command           - 실행 명령어 (implement, refactor, review, research, build, analyze, architect, framework)
#   workDir           - 작업 디렉터리 경로 (예: .workflow/20260208-133900/디렉터리-구조-변경/implement)
#   workId            - 작업 ID (예: 133900)
#   title             - 작업 제목
#   claude_session_id - (선택적) Claude Code 세션 UUID. 전달 시 status.json의 linked_sessions에 포함
#
# 디렉터리 구조:
#   .workflow/
#     YYYYMMDD-HHMMSS/            <- registry key (타임스탬프)
#       <workName>/               <- 작업이름 (title 하이픈 변환)
#         <command>/              <- 명령어 (implement, refactor 등)
#           .context.json
#           status.json
#           user_prompt.txt
#           plan.md
#           work/
#           report.md
#
# 수행 작업 (순서대로):
#   1. .prompt/prompt.txt 읽기
#   2. 작업 디렉터리 생성 (mkdir -p)
#   3. prompt.txt -> <workDir>/user_prompt.txt 복사
#   4. .prompt/prompt.txt 클리어 (파일 유지, 내용 비움)
#   5. .prompt/querys.txt에 날짜+제목 append
#   6. <workDir>/.context.json 생성
#   7. <workDir>/status.json 생성
#   8. 좀비 정리 (TTL 24시간 만료 + 미완료 워크플로우 -> STALE)
#   9. 전역 레지스트리 등록
#
# 출력:
#   성공: exit 0 (stdout 출력 없음, 에이전트는 user_prompt.txt를 직접 읽음)
#   실패: exit 1
#
# 종료 코드:
#   0 - 성공
#   1 - 실패

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# --- 인자 확인 ---

if [ $# -lt 4 ]; then
    echo "[ERROR] 사용법: $0 <command> <workDir> <workId> <title>" >&2
    exit 1
fi

COMMAND="$1"
WORK_DIR="$2"
WORK_ID="$3"
TITLE="$4"
CLAUDE_SID="${5:-}"

# 절대 경로 구성
if [[ "$WORK_DIR" = /* ]]; then
    ABS_WORK_DIR="$WORK_DIR"
else
    ABS_WORK_DIR="$PROJECT_ROOT/$WORK_DIR"
fi

PROMPT_DIR="$PROJECT_ROOT/.prompt"
PROMPT_FILE="$PROMPT_DIR/prompt.txt"
QUERYS_FILE="$PROMPT_DIR/querys.txt"

# --- Step 1: prompt.txt 읽기 ---

PROMPT_CONTENT=""
if [ -f "$PROMPT_FILE" ]; then
    PROMPT_CONTENT="$(cat "$PROMPT_FILE")"
fi

# prompt.txt가 비어있거나 없으면 빈 문자열 반환 (호출자가 분기 처리)

# --- Step 2: 작업 디렉터리 생성 ---

mkdir -p "$ABS_WORK_DIR"

# --- Step 3: user_prompt.txt 저장 ---

if [ -n "$PROMPT_CONTENT" ]; then
    printf '%s' "$PROMPT_CONTENT" > "$ABS_WORK_DIR/user_prompt.txt"
else
    # 빈 파일 생성
    touch "$ABS_WORK_DIR/user_prompt.txt"
fi

# --- Step 4: prompt.txt 클리어 ---

if [ -f "$PROMPT_FILE" ]; then
    > "$PROMPT_FILE"
    # 클리어 검증
    if [ -s "$PROMPT_FILE" ]; then
        echo "[WARN] prompt.txt 클리어 실패, 재시도" >&2
        : > "$PROMPT_FILE"
    fi
fi

# --- Step 5: querys.txt 갱신 ---

mkdir -p "$PROMPT_DIR"

# KST 날짜 생성
KST_DATE="$(TZ='Asia/Seoul' date '+%Y-%m-%d %H:%M')"

# querys.txt에 append (없으면 생성)
echo "${KST_DATE} [${COMMAND}] ${TITLE}" >> "$QUERYS_FILE"
if [ -n "$PROMPT_CONTENT" ]; then
    echo "$PROMPT_CONTENT" >> "$QUERYS_FILE"
    echo "" >> "$QUERYS_FILE"
fi

# --- Step 6: .context.json 생성 ---

WF_WORK_DIR="$ABS_WORK_DIR" WF_TITLE="$TITLE" WF_WORK_ID="$WORK_ID" WF_COMMAND="$COMMAND" python3 -c "
import json, os, re, tempfile, shutil
from datetime import datetime, timezone, timedelta

work_dir = os.environ['WF_WORK_DIR']
title = os.environ['WF_TITLE']
work_id = os.environ['WF_WORK_ID']
command = os.environ['WF_COMMAND']

# KST 시간
kst = timezone(timedelta(hours=9))
now = datetime.now(kst).strftime('%Y-%m-%dT%H:%M:%S+09:00')

# workName: title을 하이픈 구분 형식으로 변환 (공백 -> 하이픈)
work_name = re.sub(r'\s+', '-', title.strip())

data = {
    'title': title,
    'workId': work_id,
    'workName': work_name,
    'command': command,
    'agent': 'init',
    'created_at': now
}

context_file = os.path.join(work_dir, '.context.json')

# 원자적 쓰기
fd, tmp_path = tempfile.mkstemp(dir=work_dir, suffix='.tmp')
try:
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    shutil.move(tmp_path, context_file)
except Exception:
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
    raise
"

# --- Step 7: status.json 생성 ---

WF_WORK_DIR="$ABS_WORK_DIR" WF_CLAUDE_SID="$CLAUDE_SID" python3 -c "
import json, os, tempfile, shutil
from datetime import datetime, timezone, timedelta

work_dir = os.environ['WF_WORK_DIR']
claude_sid = os.environ.get('WF_CLAUDE_SID', '')

# KST 시간
kst = timezone(timedelta(hours=9))
now = datetime.now(kst).strftime('%Y-%m-%dT%H:%M:%S+09:00')

# session_id 생성
import uuid
session_id = str(uuid.uuid4())[:8]

data = {
    'phase': 'INIT',
    'session_id': session_id,
    'linked_sessions': [claude_sid] if claude_sid else [],
    'created_at': now,
    'updated_at': now,
    'transitions': [
        {
            'from': 'NONE',
            'to': 'INIT',
            'at': now
        }
    ]
}

status_file = os.path.join(work_dir, 'status.json')

# 원자적 쓰기
fd, tmp_path = tempfile.mkstemp(dir=work_dir, suffix='.tmp')
try:
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    shutil.move(tmp_path, status_file)
except Exception:
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
    raise
"

# --- Step 8: 좀비 정리 ---
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

# --- Step 8b: registry.json 좀비 정리 (STALE/COMPLETED/FAILED/CANCELLED 제거 + 고아 정리) ---

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

# --- Step 9: 전역 레지스트리 등록 ---

bash "$SCRIPT_DIR/../workflow/update-state.sh" register "$WORK_DIR" "$TITLE" "$COMMAND" 2>&1 || true

exit 0
