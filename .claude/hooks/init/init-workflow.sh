#!/bin/bash
# init-workflow.sh - 워크플로우 초기화 통합 스크립트
# prompt.txt 읽기, 디렉터리 생성, 파일 복사/클리어, 메타데이터 생성, 좀비 정리, 레지스트리 등록을 일괄 수행
#
# 사용법:
#   init-workflow.sh <command> <title> [mode]
#
# 인자:
#   command - 실행 명령어 (implement, review, research, strategy, prompt)
#   title   - 작업 제목 (init 에이전트가 prompt.txt로부터 생성한 한글 제목)
#   mode    - (선택적) 워크플로우 모드 (full, no-plan, prompt). 기본값: full
#
# 환경변수:
#   CLAUDE_SESSION_ID - (자동) Claude Code 세션 UUID. status.json의 linked_sessions에 포함
#
# 스크립트가 내부에서 자동 생성하는 값:
#   registryKey - KST 기준 YYYYMMDD-HHMMSS 타임스탬프
#   workId      - registryKey 뒤 6자리 (HHMMSS)
#   workName    - title에서 정규식으로 변환 (공백→하이픈, 특수문자 제거, 20자 절단)
#   workDir     - .workflow/<registryKey>/<workName>/<command>
#
# 디렉터리 구조:
#   .workflow/
#     YYYYMMDD-HHMMSS/            <- registry key (타임스탬프)
#       <workName>/               <- 작업이름 (title에서 스크립트가 변환)
#         <command>/              <- 명령어 (implement, review 등)
#           .context.json
#           status.json
#           user_prompt.txt
#           plan.md
#           work/
#           report.md
#
# 수행 작업 (순서대로):
#   0. registryKey/workId/workName/workDir 자동 생성
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
# 출력 (stdout):
#   workDir=.workflow/<registryKey>/<workName>/<command>
#   registryKey=<YYYYMMDD-HHMMSS>
#   workId=<HHMMSS>
#   workName=<변환된 작업이름>
#
# 종료 코드:
#   0 - 성공
#   1 - 실패

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# --- 인자 확인 ---

if [ $# -lt 2 ]; then
    echo "[ERROR] 사용법: $0 <command> <title> [mode]" >&2
    exit 1
fi

COMMAND="$1"
TITLE="$2"
MODE="${3:-full}"

# Validate command
case "$COMMAND" in
  implement|review|research|strategy|prompt) ;;
  *)
    echo "[ERROR] Invalid command: '$COMMAND'. Allowed: implement, review, research, strategy, prompt" >&2
    exit 1
    ;;
esac

# Validate title is not empty
if [ -z "$TITLE" ] || [[ "$TITLE" =~ ^[[:space:]]*$ ]]; then
  echo "[ERROR] Title must not be empty" >&2
  exit 1
fi

# Reject file path patterns in title
case "$TITLE" in
  .workflow/*|./*|/*)
    echo "[ERROR] Invalid title: must not be a file path" >&2
    exit 1
    ;;
esac

# mode 값 검증 (허용: full, no-plan, prompt)
case "$MODE" in
    full|no-plan|prompt) ;;
    *) echo "[WARN] Unknown mode '$MODE', defaulting to 'full'" >&2; MODE="full" ;;
esac

# CLAUDE_SESSION_ID는 환경변수에서 직접 읽음
CLAUDE_SID="${CLAUDE_SESSION_ID:-}"

# --- Step 0: registryKey/workId/workName/workDir 자동 생성 ---

REGISTRY_KEY="$(TZ=Asia/Seoul date +"%Y%m%d-%H%M%S")"
WORK_ID="${REGISTRY_KEY##*-}"  # 뒤 6자리 (HHMMSS)

# workName: title에서 정규식 변환 (Python으로 처리)
WORK_NAME=$(WF_TITLE="$TITLE" python3 -c "
import re, os
title = os.environ['WF_TITLE'].strip()
name = re.sub(r'\s+', '-', title)
name = re.sub(r'[!@#\$%^&*()/:;<>?|~\"\x60\\\\]', '', name)
name = re.sub(r'\.', '-', name)
name = re.sub(r'-{2,}', '-', name)
name = name.strip('-')
name = name[:20]
print(name)
")

# Validate workName is not empty after sanitization
if [ -z "$WORK_NAME" ]; then
  echo "[ERROR] Title produced empty workName after sanitization: '$TITLE'" >&2
  exit 1
fi

WORK_DIR=".workflow/${REGISTRY_KEY}/${WORK_NAME}/${COMMAND}"
ABS_WORK_DIR="$PROJECT_ROOT/$WORK_DIR"

PROMPT_DIR="$PROJECT_ROOT/.prompt"
PROMPT_FILE="$PROMPT_DIR/prompt.txt"
QUERYS_FILE="$PROMPT_DIR/querys.txt"

# --- Step 1: prompt.txt 읽기 ---

PROMPT_CONTENT=""
if [ -f "$PROMPT_FILE" ]; then
    PROMPT_CONTENT="$(cat "$PROMPT_FILE")"
fi

# --- Step 2: 작업 디렉터리 생성 ---

mkdir -p "$ABS_WORK_DIR"

# --- Step 3: user_prompt.txt 저장 ---

if [ -n "$PROMPT_CONTENT" ]; then
    printf '%s' "$PROMPT_CONTENT" > "$ABS_WORK_DIR/user_prompt.txt"
else
    touch "$ABS_WORK_DIR/user_prompt.txt"
fi

# --- Step 3-B: .uploads/ 파일 처리 ---

if [ -d "$PROJECT_ROOT/.uploads" ] && [ "$(ls -A "$PROJECT_ROOT/.uploads" 2>/dev/null)" ]; then
    mkdir -p "$ABS_WORK_DIR/files"
    cp -r "$PROJECT_ROOT/.uploads/"* "$ABS_WORK_DIR/files/"
    rm -rf "$PROJECT_ROOT/.uploads/"*
fi

# --- Step 4: prompt.txt 클리어 ---

if [ -f "$PROMPT_FILE" ]; then
    > "$PROMPT_FILE"
    if [ -s "$PROMPT_FILE" ]; then
        echo "[WARN] prompt.txt 클리어 실패, 재시도" >&2
        : > "$PROMPT_FILE"
    fi
fi

# --- Step 5: querys.txt 갱신 ---

mkdir -p "$PROMPT_DIR"

KST_DATE="$(TZ='Asia/Seoul' date '+%Y-%m-%d %H:%M')"

echo "${KST_DATE} [${COMMAND}] ${TITLE}" >> "$QUERYS_FILE"
if [ -n "$PROMPT_CONTENT" ]; then
    echo "$PROMPT_CONTENT" >> "$QUERYS_FILE"
    echo "" >> "$QUERYS_FILE"
fi

# --- Step 6: .context.json 생성 ---

WF_WORK_DIR="$ABS_WORK_DIR" WF_TITLE="$TITLE" WF_WORK_ID="$WORK_ID" WF_COMMAND="$COMMAND" WF_WORK_NAME="$WORK_NAME" python3 -c "
import json, os, tempfile, shutil
from datetime import datetime, timezone, timedelta

work_dir = os.environ['WF_WORK_DIR']
title = os.environ['WF_TITLE']
work_id = os.environ['WF_WORK_ID']
command = os.environ['WF_COMMAND']
work_name = os.environ['WF_WORK_NAME']

kst = timezone(timedelta(hours=9))
now = datetime.now(kst).strftime('%Y-%m-%dT%H:%M:%S+09:00')

data = {
    'title': title,
    'workId': work_id,
    'workName': work_name,
    'command': command,
    'agent': 'init',
    'created_at': now
}

context_file = os.path.join(work_dir, '.context.json')

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

kst = timezone(timedelta(hours=9))
now = datetime.now(kst).strftime('%Y-%m-%dT%H:%M:%S+09:00')

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

bash "$SCRIPT_DIR/cleanup-zombie.sh" "$PROJECT_ROOT" 2>&1 || true

# --- Step 9: 전역 레지스트리 등록 ---

bash "$SCRIPT_DIR/../workflow/update-state.sh" register "$WORK_DIR" "$TITLE" "$COMMAND" 2>&1 || true

# --- stdout 출력: init 에이전트가 파싱할 결과 ---

echo "workDir=${WORK_DIR}"
echo "registryKey=${REGISTRY_KEY}"
echo "workId=${WORK_ID}"
echo "workName=${WORK_NAME}"

exit 0
