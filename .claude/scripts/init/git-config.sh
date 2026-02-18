#!/bin/bash
# Git Config 자동 설정 스크립트
# .claude.env에서 Git 설정 정보를 읽어 git config를 자동으로 설정합니다.
#
# 사용법: ./git-config.sh [--global|--local]
#   --global  전역 설정 (~/.gitconfig) [기본값]
#   --local   로컬 설정 (.git/config)
#
# 환경변수 (.claude.env에서 로드):
#   CLAUDE_CODE_GIT_USER_NAME    - Git user.name (필수)
#   CLAUDE_CODE_GIT_USER_EMAIL   - Git user.email (필수)
#   CLAUDE_CODE_GITHUB_USERNAME  - GitHub 사용자명 (선택)
#   CLAUDE_CODE_SSH_KEY_GITHUB   - GitHub SSH 키 경로 (선택)

set -euo pipefail

# ─── 경로 설정 ───
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.claude.env"

# ─── 옵션 파싱 ───
SCOPE="--global"
if [ $# -ge 1 ]; then
    case "$1" in
        --global)
            SCOPE="--global"
            ;;
        --local)
            SCOPE="--local"
            ;;
        *)
            echo "[ERROR] 알 수 없는 옵션: $1"
            echo "사용법: $0 [--global|--local]"
            exit 1
            ;;
    esac
fi

SCOPE_LABEL="global"
[ "$SCOPE" = "--local" ] && SCOPE_LABEL="local"

# ─── .claude.env 파일 확인 ───
if [ ! -f "$ENV_FILE" ]; then
    echo "[ERROR] .claude.env 파일이 존재하지 않습니다: $ENV_FILE"
    exit 1
fi

# ─── 공통 env 파싱 유틸리티 로드 ───
source "$SCRIPT_DIR/../_utils/env-utils.sh"

# ─── 환경변수 로드 (read_env: 따옴표 제거, $HOME/~ 확장, 중복 키 방어 포함) ───
GIT_USER_NAME=$(read_env "CLAUDE_CODE_GIT_USER_NAME")
GIT_USER_EMAIL=$(read_env "CLAUDE_CODE_GIT_USER_EMAIL")
# 현재 미사용 - 향후 GitHub API 연동 예정
GITHUB_USERNAME=$(read_env "CLAUDE_CODE_GITHUB_USERNAME")
SSH_KEY_GITHUB=$(read_env "CLAUDE_CODE_SSH_KEY_GITHUB")

# ─── 필수 환경변수 검증 ───
if [ -z "$GIT_USER_NAME" ]; then
    echo "[ERROR] CLAUDE_CODE_GIT_USER_NAME이 .claude.env에 설정되지 않았습니다."
    exit 1
fi

if [ -z "$GIT_USER_EMAIL" ]; then
    echo "[ERROR] CLAUDE_CODE_GIT_USER_EMAIL이 .claude.env에 설정되지 않았습니다."
    exit 1
fi

# ─── Before 상태 수집 ───
BEFORE_NAME=$(git config $SCOPE user.name 2>/dev/null || echo "(미설정)")
BEFORE_EMAIL=$(git config $SCOPE user.email 2>/dev/null || echo "(미설정)")
BEFORE_SSH=$(git config $SCOPE core.sshCommand 2>/dev/null || echo "(미설정)")

# ─── 설정 적용 ───
echo "[INFO] Git config ($SCOPE_LABEL) 설정을 적용합니다..."

git config $SCOPE user.name "$GIT_USER_NAME"
echo "[OK] user.name = $GIT_USER_NAME"

git config $SCOPE user.email "$GIT_USER_EMAIL"
echo "[OK] user.email = $GIT_USER_EMAIL"

# SSH 키 설정 (파일 존재 시)
if [ -n "$SSH_KEY_GITHUB" ]; then
    if [ -f "$SSH_KEY_GITHUB" ]; then
        git config $SCOPE core.sshCommand "ssh -i \"$SSH_KEY_GITHUB\" -o IdentitiesOnly=yes"
        echo "[OK] core.sshCommand = ssh -i \"$SSH_KEY_GITHUB\" -o IdentitiesOnly=yes"
    else
        echo "[WARN] SSH 키 파일이 존재하지 않습니다: $SSH_KEY_GITHUB (SSH 설정 스킵)"
    fi
fi

# ─── After 상태 수집 ───
AFTER_NAME=$(git config $SCOPE user.name 2>/dev/null || echo "(미설정)")
AFTER_EMAIL=$(git config $SCOPE user.email 2>/dev/null || echo "(미설정)")
AFTER_SSH=$(git config $SCOPE core.sshCommand 2>/dev/null || echo "(미설정)")

# ─── Before/After 비교 출력 ───
echo ""
echo "=========================================="
echo " Git Config 변경 결과 ($SCOPE_LABEL)"
echo "=========================================="
printf "%-20s %-30s %-30s\n" "설정" "Before" "After"
printf "%-20s %-30s %-30s\n" "----" "------" "-----"
printf "%-20s %-30s %-30s\n" "user.name" "$BEFORE_NAME" "$AFTER_NAME"
printf "%-20s %-30s %-30s\n" "user.email" "$BEFORE_EMAIL" "$AFTER_EMAIL"
printf "%-20s %-30s %-30s\n" "core.sshCommand" "$BEFORE_SSH" "$AFTER_SSH"
echo "=========================================="
echo ""
echo "[OK] Git config ($SCOPE_LABEL) 설정 완료"

exit 0
