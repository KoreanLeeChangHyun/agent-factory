#!/bin/bash
# init-workflow.sh - 워크플로우 초기화 통합 스크립트
# prompt.txt 읽기, 디렉터리 생성, 파일 복사/클리어, 메타데이터 생성, 좀비 정리, 레지스트리 등록을 일괄 수행
#
# 사용법:
#   init-workflow.sh <command> <workDir> <workId> <title> [claude_session_id] [mode]
#
# 인자:
#   command           - 실행 명령어 (implement, refactor, review, research, build, analyze, architect, framework)
#   workDir           - 작업 디렉터리 경로 (예: .workflow/20260208-133900/디렉터리-구조-변경/implement)
#   workId            - 작업 ID (예: 133900)
#   title             - 작업 제목
#   claude_session_id - (선택적) Claude Code 세션 UUID. 전달 시 status.json의 linked_sessions에 포함
#   mode              - (선택적) 워크플로우 모드 (full, no-plan, prompt). 기본값: full
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
#   3-B. .uploads/ 파일 -> <workDir>/files/ 복사 + .uploads/ 클리어
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
MODE="${6:-full}"

# 5번째 인자가 mode 값이고 6번째 인자가 비어있으면 인자 보정
# (에이전트가 session_id를 생략하고 mode를 5번째에 넣는 버그 방어)
if [ -z "${6:-}" ]; then
    case "$CLAUDE_SID" in
        full|no-plan|prompt)
            MODE="$CLAUDE_SID"
            CLAUDE_SID=""
            ;;
    esac
fi

# mode 값 검증 (허용: full, no-plan, prompt)
case "$MODE" in
    full|no-plan|prompt) ;;
    *) echo "[WARN] Unknown mode '$MODE', defaulting to 'full'" >&2; MODE="full" ;;
esac

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

# --- Step 3-B: .uploads/ 파일 처리 ---

if [ -d "$PROJECT_ROOT/.uploads" ] && [ "$(ls -A "$PROJECT_ROOT/.uploads" 2>/dev/null)" ]; then
    # workDir/files/ 디렉터리 생성 및 파일 복사
    mkdir -p "$ABS_WORK_DIR/files"
    cp -r "$PROJECT_ROOT/.uploads/"* "$ABS_WORK_DIR/files/"

    # .uploads/ 내용 클리어 (디렉터리 자체는 유지)
    rm -rf "$PROJECT_ROOT/.uploads/"*
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

WF_WORK_DIR="$ABS_WORK_DIR" WF_CLAUDE_SID="$CLAUDE_SID" WF_MODE="$MODE" python3 -c "
import json, os, tempfile, shutil
from datetime import datetime, timezone, timedelta

work_dir = os.environ['WF_WORK_DIR']
claude_sid = os.environ.get('WF_CLAUDE_SID', '')
mode = os.environ.get('WF_MODE', 'full')

# KST 시간
kst = timezone(timedelta(hours=9))
now = datetime.now(kst).strftime('%Y-%m-%dT%H:%M:%S+09:00')

# session_id 생성
import uuid
session_id = str(uuid.uuid4())[:8]

data = {
    'phase': 'INIT',
    'mode': mode,
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
# 분리된 cleanup-zombie.sh 스크립트를 호출하여 좀비 워크플로우 및 레지스트리 정리 수행
# (1) .workflow/ 하위에서 TTL(24시간) 만료 + 미완료 워크플로우 -> STALE 전환
# (2) registry.json에서 STALE/COMPLETED/FAILED/CANCELLED 엔트리 제거 + 고아 정리

bash "$SCRIPT_DIR/cleanup-zombie.sh" "$PROJECT_ROOT" 2>&1 || true

# --- Step 9: 전역 레지스트리 등록 ---

bash "$SCRIPT_DIR/../workflow/update-state.sh" register "$WORK_DIR" "$TITLE" "$COMMAND" 2>&1 || true

exit 0
