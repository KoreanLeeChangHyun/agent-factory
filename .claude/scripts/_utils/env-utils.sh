#!/bin/bash
# =============================================================================
# _env-utils.sh - .claude.env 공통 파싱 유틸리티
# =============================================================================
#
# .claude.env 파일에서 KEY=value 형식의 환경변수를 읽고 쓰는 공통 함수를 제공합니다.
# 기존에 init-claude.sh, git-config.sh, slack-common.sh에서 독립 구현되던 파싱 로직을
# 하나로 통합하여 일관된 동작을 보장합니다.
#
# 제공 함수:
#   read_env <key> [default]  - .claude.env에서 값 읽기 (따옴표 제거, 경로 확장 포함)
#   set_env <key> <value>     - .claude.env에 KEY=value 추가/갱신
#
# 사전 조건:
#   - ENV_FILE 변수가 설정되어 있어야 함 (호출자 책임)
#   - ENV_FILE이 미설정이면 함수가 기본값을 반환
#
# 사용법:
#   SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
#   PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
#   ENV_FILE="$PROJECT_ROOT/.claude.env"
#   source "$SCRIPT_DIR/_env-utils.sh"
#
#   value=$(read_env "CLAUDE_CODE_SSH_KEY_GITHUB")
# =============================================================================

# .claude.env에서 환경변수 읽기
# - 중복 키 방어: head -1로 첫 번째 매칭만 사용
# - 따옴표 제거: 앞뒤 큰따옴표/작은따옴표 제거
# - $HOME 확장: $HOME을 실제 홈 디렉토리로 치환
# - ~ 확장: 선두 ~를 실제 홈 디렉토리로 치환
read_env() {
    local key="$1"
    local default="${2:-}"
    if [ -n "${ENV_FILE:-}" ] && [ -f "$ENV_FILE" ]; then
        local value
        value=$(grep "^${key}=" "$ENV_FILE" 2>/dev/null | head -1 | sed "s/^${key}=//")
        if [ -n "$value" ]; then
            # 따옴표 제거 (앞뒤 큰따옴표 또는 작은따옴표)
            value=$(printf '%s' "$value" | sed 's/^["'\''"]//;s/["'\''"]$//')
            # $HOME 확장
            value="${value/\$HOME/$HOME}"
            # ~ 확장 (선두 ~ 만)
            value="${value/#\~/$HOME}"
            printf '%s' "$value"
            return
        fi
    fi
    printf '%s' "$default"
}

# .claude.env에 KEY=value 추가/갱신
# - 파일이 없으면 헤더와 함께 생성
# - 기존 키가 있으면 업데이트 (임시 파일 + mv 방식, sed 인젝션 방어)
# - 새 키이면 파일 끝에 추가
set_env() {
    local key="$1"
    local value="$2"

    if [ ! -f "$ENV_FILE" ]; then
        # 파일이 없으면 헤더와 함께 생성
        cat > "$ENV_FILE" << 'ENVHEADER'
# ============================================
# Claude Code 환경 변수
# ============================================
#
# 이 파일은 Claude Code Hook 스크립트에서 사용하는 환경 변수를 정의합니다.
# 형식: KEY=value (표준 .env 문법)
# ============================================

ENVHEADER
    fi

    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        # 기존 키 업데이트 (임시 파일 + mv 방식으로 sed 인젝션 방어)
        local tmpfile
        tmpfile=$(mktemp "${ENV_FILE}.tmp.XXXXXX")
        while IFS= read -r line || [ -n "$line" ]; do
            if [[ "$line" == "${key}="* ]]; then
                printf '%s\n' "${key}=${value}"
            else
                printf '%s\n' "$line"
            fi
        done < "$ENV_FILE" > "$tmpfile"
        mv "$tmpfile" "$ENV_FILE"
    else
        # 새 키 추가
        echo "${key}=${value}" >> "$ENV_FILE"
    fi
}
