#!/bin/bash
# 오래된 워크플로우 디렉토리를 .workflow/.history/로 아카이브하는 스크립트
#
# 사용법:
#   archive-workflow.sh <registryKey>
#
# 인자:
#   registryKey  - 현재 활성 워크플로우의 레지스트리 키 (YYYYMMDD-HHMMSS 형식)
#                  이 키에 해당하는 디렉토리는 아카이브 대상에서 제외됨
#
# 동작:
#   1. .workflow/ 내 [0-9]* 패턴 디렉토리를 역순 정렬하여 수집
#   2. 현재 워크플로우(registryKey)를 목록에서 제외
#   3. 최신 10개를 유지하고 11번째 이후 항목을 .workflow/.history/로 이동
#
# 종료 코드:
#   0 - 성공 (이동 대상 없어도 성공)
#   1 - 인자 오류 또는 아카이브 이동 실패

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# ANSI 색상 코드
C_GREEN='\033[0;32m'
C_YELLOW='\033[0;33m'
C_RED='\033[0;31m'
C_CYAN='\033[0;36m'
C_RESET='\033[0m'

WORKFLOW_DIR="$PROJECT_ROOT/.workflow"
HISTORY_DIR="$WORKFLOW_DIR/.history"

# 인자 확인
if [ $# -lt 1 ]; then
    echo -e "${C_RED}[ERROR]${C_RESET} 사용법: archive-workflow.sh <registryKey>" >&2
    exit 1
fi

CURRENT_KEY="$1"

# .workflow/ 디렉토리 존재 확인
if [ ! -d "$WORKFLOW_DIR" ]; then
    echo -e "${C_YELLOW}[WARN]${C_RESET} .workflow/ 디렉토리가 존재하지 않습니다." >&2
    exit 0
fi

# [0-9]* 패턴 디렉토리를 역순 정렬하여 배열에 저장
DIRS=()
while IFS= read -r dir; do
    [ -n "$dir" ] && DIRS+=("$(basename "$dir")")
done < <(ls -d "$WORKFLOW_DIR"/[0-9]* 2>/dev/null | sort -r)

# 디렉토리가 없으면 종료
if [ ${#DIRS[@]} -eq 0 ]; then
    exit 0
fi

# 현재 워크플로우를 배열에서 제외
FILTERED=()
for dir in "${DIRS[@]}"; do
    if [ "$dir" != "$CURRENT_KEY" ]; then
        FILTERED+=("$dir")
    fi
done

# 보존 개수: 최신 10개 유지
KEEP_COUNT=10

# 이동 대상이 없으면 종료
if [ ${#FILTERED[@]} -le $KEEP_COUNT ]; then
    exit 0
fi

# .history/ 디렉토리 생성
mkdir -p "$HISTORY_DIR"

# 11번째 이후 항목을 .history/로 이동
MOVED=0
FAILED=0
for (( i=KEEP_COUNT; i<${#FILTERED[@]}; i++ )); do
    target="${FILTERED[$i]}"
    if mv "$WORKFLOW_DIR/$target" "$HISTORY_DIR/$target" 2>/dev/null; then
        MOVED=$((MOVED + 1))
        echo -e "${C_GREEN}[OK]${C_RESET} archived: $target"
    else
        FAILED=$((FAILED + 1))
        echo -e "${C_YELLOW}[WARN]${C_RESET} archive failed: $target (skipping)" >&2
        continue
    fi
done

if [ $MOVED -gt 0 ]; then
    echo -e "${C_CYAN}[archive]${C_RESET} $MOVED directories archived to .history/"
fi

if [ $FAILED -gt 0 ]; then
    echo "[WARN] $FAILED directories failed to archive" >&2
fi

if [ $FAILED -gt 0 ]; then exit 1; fi
exit 0
