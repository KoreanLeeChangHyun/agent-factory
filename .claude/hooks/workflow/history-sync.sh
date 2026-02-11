#!/bin/bash
# wf-history: 히스토리 동기화 및 상태 확인 명령어
#
# 사용법:
#   wf-history sync [--dry-run] [--all] [--target PATH]
#   wf-history status
#
# 서브커맨드:
#   sync     - .workflow/ 디렉토리를 스캔하여 history.md에 누락 항목을 추가하고 상태를 업데이트
#   status   - .workflow/ 디렉토리 수, history.md 행 수, 누락 수 요약 출력
#
# 옵션 (sync 전용):
#   --dry-run    변경 예정 사항을 출력만 하고 실제 파일 수정은 하지 않음
#   --all        중단 작업(INIT/PLAN 단계) 포함하여 동기화
#   --target PATH  history.md 파일 경로 지정 (기본: .prompt/history.md)
#
# 종료 코드:
#   0 - 성공
#   1 - 인자 오류 또는 실행 실패

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# ANSI 색상
C_GREEN='\033[0;32m'
C_YELLOW='\033[0;33m'
C_RED='\033[0;31m'
C_BLUE='\033[0;34m'
C_CYAN='\033[0;36m'
C_RESET='\033[0m'

# 인자 확인
if [ $# -lt 1 ]; then
    echo -e "${C_RED}[ERROR]${C_RESET} 사용법: wf-history <sync|status> [옵션]"
    echo ""
    echo "  sync [--dry-run] [--all] [--target PATH]"
    echo "    .workflow/ 디렉토리를 스캔하여 history.md에 누락 항목 추가"
    echo ""
    echo "  status"
    echo "    .workflow/ 디렉토리 수, history.md 행 수, 누락 수 요약"
    exit 1
fi

SUBCMD="$1"
shift

# 옵션 파싱
DRY_RUN=""
INCLUDE_ALL=""
TARGET_PATH=""

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run)
            DRY_RUN="--dry-run"
            ;;
        --all)
            INCLUDE_ALL="--all"
            ;;
        --target)
            shift
            if [ -z "$1" ]; then
                echo -e "${C_RED}[ERROR]${C_RESET} --target 옵션에 경로가 필요합니다." >&2
                exit 1
            fi
            TARGET_PATH="$1"
            ;;
        *)
            echo -e "${C_RED}[ERROR]${C_RESET} 알 수 없는 옵션: $1" >&2
            exit 1
            ;;
    esac
    shift
done

# 기본 target 경로
if [ -z "$TARGET_PATH" ]; then
    TARGET_PATH="$PROJECT_ROOT/.prompt/history.md"
fi

# 절대 경로 변환
if [[ "$TARGET_PATH" != /* ]]; then
    TARGET_PATH="$PROJECT_ROOT/$TARGET_PATH"
fi

WORKFLOW_DIR="$PROJECT_ROOT/.workflow"

# Python 코어 스크립트 경로
CORE_SCRIPT="$SCRIPT_DIR/history-sync-core.py"

if [ ! -f "$CORE_SCRIPT" ]; then
    echo -e "${C_RED}[ERROR]${C_RESET} Python 코어 스크립트를 찾을 수 없습니다: $CORE_SCRIPT" >&2
    exit 1
fi

# 서브커맨드 실행
case "$SUBCMD" in
    sync)
        echo -e "${C_CYAN}[wf-history]${C_RESET} sync 시작..."

        ARGS=("$CORE_SCRIPT" "sync" "--workflow-dir" "$WORKFLOW_DIR" "--target" "$TARGET_PATH")
        [ -n "$DRY_RUN" ] && ARGS+=("$DRY_RUN")
        [ -n "$INCLUDE_ALL" ] && ARGS+=("$INCLUDE_ALL")

        RESULT=$(python3 "${ARGS[@]}" 2>&1)
        EXIT_CODE=$?

        if [ $EXIT_CODE -eq 0 ]; then
            echo "$RESULT"
            echo -e "${C_GREEN}[OK]${C_RESET} sync 완료"
        else
            echo "$RESULT" >&2
            echo -e "${C_RED}[FAIL]${C_RESET} sync 실패 (exit code: $EXIT_CODE)" >&2
            exit 1
        fi
        ;;

    status)
        ARGS=("$CORE_SCRIPT" "status" "--workflow-dir" "$WORKFLOW_DIR" "--target" "$TARGET_PATH")
        [ -n "$INCLUDE_ALL" ] && ARGS+=("$INCLUDE_ALL")

        RESULT=$(python3 "${ARGS[@]}" 2>&1)
        EXIT_CODE=$?

        if [ $EXIT_CODE -eq 0 ]; then
            echo "$RESULT"
        else
            echo "$RESULT" >&2
            echo -e "${C_RED}[FAIL]${C_RESET} status 조회 실패" >&2
            exit 1
        fi
        ;;

    *)
        echo -e "${C_RED}[ERROR]${C_RESET} 알 수 없는 서브커맨드: $SUBCMD"
        echo "사용법: wf-history <sync|status> [옵션]"
        exit 1
        ;;
esac

exit 0
