#!/bin/bash
# reload-prompt.sh - 수정 피드백을 워크플로우에 반영하는 스크립트
# prompt.txt의 피드백을 user_prompt.txt에 append하고,
# .uploads/ 파일 복사, prompt.txt 클리어, querys.txt 갱신을 수행
#
# 사용법:
#   reload-prompt.sh <workDir>
#
# 인자:
#   workDir - 작업 디렉터리 상대 경로 (예: .workflow/20260215-010302/워크플로우-개선/implement)
#
# 수행 작업 (순서대로):
#   1. .prompt/prompt.txt 읽기 (비어있으면 경고 후 종료)
#   2. <workDir>/user_prompt.txt에 구분선 + 피드백 append
#   3. .uploads/ -> <workDir>/files/ 복사 후 .uploads/ 클리어
#   4. .prompt/prompt.txt 클리어
#   5. .prompt/querys.txt에 수정 기록 append
#
# 출력 (stdout):
#   피드백 내용 전문
#
# 종료 코드:
#   0 - 성공
#   1 - 실패

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# --- 인자 확인 ---

if [ $# -lt 1 ]; then
    echo "[ERROR] 사용법: $0 <workDir>" >&2
    exit 1
fi

WORK_DIR="$1"
ABS_WORK_DIR="$PROJECT_ROOT/$WORK_DIR"

if [ ! -d "$ABS_WORK_DIR" ]; then
    echo "[ERROR] workDir not found: $WORK_DIR" >&2
    exit 1
fi

PROMPT_DIR="$PROJECT_ROOT/.prompt"
PROMPT_FILE="$PROMPT_DIR/prompt.txt"
QUERYS_FILE="$PROMPT_DIR/querys.txt"

# --- Step 1: prompt.txt 읽기 ---

FEEDBACK=""
if [ -f "$PROMPT_FILE" ]; then
    FEEDBACK="$(cat "$PROMPT_FILE")"
fi

if [ -z "$FEEDBACK" ]; then
    echo "[WARN] prompt.txt is empty"
    exit 0
fi

# --- Step 2: user_prompt.txt에 피드백 append ---

KST_DATE="$(TZ='Asia/Seoul' date '+%Y-%m-%d %H:%M')"

USER_PROMPT_FILE="$ABS_WORK_DIR/user_prompt.txt"

{
    printf '\n\n--- (수정 피드백, %s) ---\n\n' "$KST_DATE"
    printf '%s' "$FEEDBACK"
} >> "$USER_PROMPT_FILE"

# --- Step 3: .uploads/ 파일 처리 ---

if [ -d "$PROJECT_ROOT/.uploads" ] && [ "$(ls -A "$PROJECT_ROOT/.uploads" 2>/dev/null)" ]; then
    mkdir -p "$ABS_WORK_DIR/files"
    cp -r "$PROJECT_ROOT/.uploads/"* "$ABS_WORK_DIR/files/" 2>/dev/null || true
    rm -f "$PROJECT_ROOT/.uploads/"* 2>/dev/null || true
fi

# --- Step 4: prompt.txt 클리어 ---

> "$PROMPT_FILE" 2>/dev/null || : > "$PROMPT_FILE"

# --- Step 5: querys.txt 갱신 ---

FEEDBACK_SUMMARY="${FEEDBACK:0:30}"
echo "${KST_DATE} [수정] ${FEEDBACK_SUMMARY}" >> "$QUERYS_FILE"

# --- stdout: 피드백 내용 전문 출력 ---

printf '%s\n' "$FEEDBACK"

exit 0
