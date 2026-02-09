#!/bin/bash
# .claude 디렉토리 원격 동기화 스크립트
# 사용법: ./init-sync.sh [--dry-run]
#
# 원격 리포(https://github.com/KoreanLeeChangHyun/claude-workflow.git)에서 .claude 디렉토리를 가져와
# 현재 프로젝트에 rsync --delete로 덮어쓰기합니다.
# .claude.env 파일은 보존됩니다.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

REMOTE_REPO="https://github.com/KoreanLeeChangHyun/claude-workflow.git"
TEMP_DIR=$(mktemp -d "/tmp/claude-sync-XXXXXX")
CLONE_DIR="$TEMP_DIR/claude-remote"
BACKUP_DIR="$TEMP_DIR/sync-backup"
ENV_FILE="$PROJECT_ROOT/.claude.env"

DRY_RUN=false
SYNC_SUCCESS=false

# --- 인자 파싱 ---
for arg in "$@"; do
    case "$arg" in
        --dry-run)
            DRY_RUN=true
            ;;
        -h|--help)
            echo "사용법: $(basename "$0") [--dry-run]"
            echo ""
            echo "원격 리포에서 .claude 디렉토리를 동기화합니다."
            echo ""
            echo "옵션:"
            echo "  --dry-run    실제 동기화 없이 변경 사항만 미리보기"
            echo "  -h, --help   도움말 출력"
            exit 0
            ;;
        *)
            echo "[ERROR] 알 수 없는 옵션: $arg"
            echo "사용법: $(basename "$0") [--dry-run]"
            exit 1
            ;;
    esac
done

# --- 정리 함수 (에러 시에도 임시 파일 제거) ---
cleanup() {
    if [ "$SYNC_SUCCESS" = true ]; then
        # 정상 종료 시 TEMP_DIR 전체 정리
        rm -rf "$TEMP_DIR"
    else
        rm -rf "$CLONE_DIR"
        if [ "$DRY_RUN" = false ] && [ -d "$BACKUP_DIR" ]; then
            echo "[WARN] 에러 발생으로 백업이 유지됩니다: $BACKUP_DIR"
        fi
    fi
}
trap cleanup EXIT

# --- 1. 사전 확인 ---
echo "=== .claude 동기화 시작 ==="
echo ""

LOCAL_ENV_EXISTS=false
if [ -f "$ENV_FILE" ]; then
    LOCAL_ENV_EXISTS=true
    echo "[INFO] .claude.env 파일 감지 - 동기화 시 보존됩니다."
else
    echo "[INFO] .claude.env 파일 없음 - 보존 대상 없음."
fi
echo ""

# --- 2. 로컬 보존 파일 임시 저장 ---
# .claude.env는 rsync 대상(.claude/) 외부에 있어 동기화 영향을 받지 않지만,
# 이중 보호 목적으로 백업/복원을 수행합니다.
if [ "$DRY_RUN" = false ] && [ "$LOCAL_ENV_EXISTS" = true ]; then
    mkdir -p "$BACKUP_DIR"
    cp "$ENV_FILE" "$BACKUP_DIR/.env"
    echo "[BACKUP] .claude.env -> $BACKUP_DIR/.env"
fi

# --- 3. 원격 리포지토리 클론 ---
echo "[CLONE] $REMOTE_REPO (shallow clone)..."
rm -rf "$CLONE_DIR"

if ! git clone --depth 1 "$REMOTE_REPO" "$CLONE_DIR" 2>&1; then
    echo ""
    echo "[ERROR] git clone 실패."
    echo "  - 네트워크 연결을 확인하세요."
    echo "  - 리포지토리 URL을 확인하세요: $REMOTE_REPO"
    echo ""
    echo "  HTTPS 접속이 차단되어 있다면 네트워크 환경(프록시, 방화벽 등)을 확인하세요."
    exit 1
fi
echo "[CLONE] 완료."
echo ""

# 원격에 .claude 디렉토리가 있는지 확인
if [ ! -d "$CLONE_DIR/.claude" ]; then
    echo "[ERROR] 원격 리포지토리에 .claude 디렉토리가 없습니다."
    exit 1
fi

# --- 4. .claude 디렉토리 동기화 ---
if [ "$DRY_RUN" = true ]; then
    echo "[DRY-RUN] 변경 사항 미리보기:"
    echo "---"
    # /.env: 루트 레벨의 .env만 제외 (하위 디렉토리의 .env는 동기화 대상)
    rsync -av --delete --dry-run \
        --exclude='/.env' \
        "$CLONE_DIR/.claude/" "$PROJECT_ROOT/.claude/"
    echo "---"
    echo ""
    echo "[DRY-RUN] 위 내용은 미리보기입니다. 실제 변경은 수행되지 않았습니다."
else
    # 삭제 대상 파일 사전 확인 (--dry-run으로 deleting 항목만 추출)
    DELETE_PREVIEW=$(rsync -av --delete --dry-run \
        --exclude='/.env' \
        "$CLONE_DIR/.claude/" "$PROJECT_ROOT/.claude/" 2>/dev/null \
        | grep '^deleting ' || true)
    if [ -n "$DELETE_PREVIEW" ]; then
        echo "[WARN] 다음 파일이 삭제됩니다:"
        echo "$DELETE_PREVIEW"
        echo ""
    fi

    echo "[SYNC] rsync --delete 실행 중..."
    # /.env: 루트 레벨의 .env만 제외 (하위 디렉토리의 .env는 동기화 대상)
    if ! rsync -av --delete \
        --exclude='/.env' \
        "$CLONE_DIR/.claude/" "$PROJECT_ROOT/.claude/"; then
        echo ""
        echo "[ERROR] rsync 동기화 실패."
        echo "  - 디스크 공간을 확인하세요."
        echo "  - 대상 디렉토리 쓰기 권한을 확인하세요: $PROJECT_ROOT/.claude/"
        exit 1
    fi
    echo "[SYNC] 완료."
    echo ""

    # --- 5. 보존 파일 복원 ---
    # rsync 범위 밖이나 이중 보호 목적으로 백업된 .claude.env를 복원
    if [ -f "$BACKUP_DIR/.env" ]; then
        if ! cp "$BACKUP_DIR/.env" "$ENV_FILE"; then
            echo ""
            echo "[ERROR] .claude.env 복원 실패."
            echo "  - 백업 파일 경로: $BACKUP_DIR/.env"
            echo "  - 수동으로 복원하세요: cp \"$BACKUP_DIR/.env\" \"$ENV_FILE\""
            exit 1
        fi
        echo "[RESTORE] .claude.env 복원 완료."
    fi
fi

SYNC_SUCCESS=true

# --- 6. 결과 출력 ---
echo ""
echo "=== .claude 동기화 완료 ==="
echo ""
echo "[소스] $REMOTE_REPO"
echo "[대상] .claude/"
echo "[방식] 덮어쓰기 (rsync --delete)"
echo "[보존] .claude.env"
if [ "$DRY_RUN" = true ]; then
    echo "[모드] dry-run (미리보기만 수행)"
fi
echo ""
echo "다음 단계:"
echo "  - /init:workflow 로 워크플로우를 재초기화하세요"
