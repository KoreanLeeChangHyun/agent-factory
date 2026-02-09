#!/bin/bash
# =============================================================================
# init-claude.sh - Claude Code 사용자 환경 초기화 스크립트
# =============================================================================
#
# 사용법:
#   ./init-claude.sh <subcommand> [args]
#
# 서브커맨드:
#   check-alias          alias 존재 여부 체크 (JSON 출력)
#   setup-alias          alias 추가 (~/.zshrc에)
#   setup-statusline     StatusLine 전체 설정
#   setup-slack <url>    Slack 환경변수 설정 (.claude.env에 추가)
#   setup-git            Git global 설정 (.claude.env 읽어서 git config)
#   verify               전체 설정 검증
#
# 설계 원칙:
#   - stdout에 결과 출력 (JSON 형식)
#   - 독립 실행 가능 (Claude 없이도 터미널에서 직접 실행)
#   - ~/.zshrc 조작은 delete+append 방식 (중복 방지), 블록 마커로 관리
#   - .claude.env는 KEY=value 형식 (표준 .env)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.claude.env"
ZSHRC="$HOME/.zshrc"
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
STATUSLINE_SCRIPT="$HOME/.claude/statusline.sh"

# -----------------------------------------------------------------------------
# 유틸리티 함수
# -----------------------------------------------------------------------------

# JSON 문자열 이스케이프
json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

# JSON 결과 출력
json_result() {
    local status="$1"
    local message="$2"
    shift 2

    printf '{"status":"%s","message":"%s"' "$status" "$(json_escape "$message")"

    # 추가 key-value 쌍 출력
    while [ $# -ge 2 ]; do
        local key="$1"
        local value="$2"
        printf ',"%s":"%s"' "$key" "$(json_escape "$value")"
        shift 2
    done

    printf '}\n'
}

# 공통 env 파싱 유틸리티 로드 (read_env, set_env)
source "$SCRIPT_DIR/../_utils/env-utils.sh"

# -----------------------------------------------------------------------------
# check-alias: alias 존재 여부 체크
# -----------------------------------------------------------------------------
cmd_check_alias() {
    local cc_exists="false"
    local ccc_exists="false"
    local cc_value=""
    local ccc_value=""

    if [ -f "$ZSHRC" ]; then
        # cc alias 체크 (정확히 "alias cc=" 패턴)
        cc_value=$(grep "^alias cc=" "$ZSHRC" 2>/dev/null | head -1 || true)
        if [ -n "$cc_value" ]; then
            cc_exists="true"
        fi

        # ccc alias 체크
        ccc_value=$(grep "^alias ccc=" "$ZSHRC" 2>/dev/null | head -1 || true)
        if [ -n "$ccc_value" ]; then
            ccc_exists="true"
        fi
    fi

    # JSON 출력
    printf '{"status":"ok","cc_exists":%s,"ccc_exists":%s' "$cc_exists" "$ccc_exists"

    if [ -n "$cc_value" ]; then
        printf ',"cc_value":"%s"' "$(json_escape "$cc_value")"
    fi
    if [ -n "$ccc_value" ]; then
        printf ',"ccc_value":"%s"' "$(json_escape "$ccc_value")"
    fi

    printf '}\n'
}

# -----------------------------------------------------------------------------
# setup-alias: alias 추가 (~/.zshrc에)
# -----------------------------------------------------------------------------

# 블록 마커 상수
ALIAS_BLOCK_BEGIN="# >>> Claude Code aliases"
ALIAS_BLOCK_END="# <<< Claude Code aliases"

cmd_setup_alias() {
    # ~/.zshrc 없으면 생성
    if [ ! -f "$ZSHRC" ]; then
        touch "$ZSHRC"
    fi

    local changed=0

    # --- 1. 블록 마커 방식으로 기존 블록 제거 ---
    if grep -qF "$ALIAS_BLOCK_BEGIN" "$ZSHRC" 2>/dev/null; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "/$ALIAS_BLOCK_BEGIN/,/$ALIAS_BLOCK_END/d" "$ZSHRC"
        else
            sed -i "/$ALIAS_BLOCK_BEGIN/,/$ALIAS_BLOCK_END/d" "$ZSHRC"
        fi
        changed=1
    fi

    # --- 2. 레거시 패턴 호환 삭제 (블록 마커 없는 이전 형식) ---
    if grep -q "^alias cc=" "$ZSHRC" 2>/dev/null; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' '/^alias cc=/d' "$ZSHRC"
        else
            sed -i '/^alias cc=/d' "$ZSHRC"
        fi
        changed=1
    fi

    if grep -q "^alias ccc=" "$ZSHRC" 2>/dev/null; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' '/^alias ccc=/d' "$ZSHRC"
        else
            sed -i '/^alias ccc=/d' "$ZSHRC"
        fi
        changed=1
    fi

    if grep -q "^# Claude Code aliases$" "$ZSHRC" 2>/dev/null; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' '/^# Claude Code aliases$/d' "$ZSHRC"
        else
            sed -i '/^# Claude Code aliases$/d' "$ZSHRC"
        fi
    fi

    # --- 3. 연속 빈 줄 정리 (2줄 이상 -> 1줄) ---
    local tmpfile
    tmpfile=$(mktemp)
    awk 'NF{blank=0} !NF{blank++} blank<=1' "$ZSHRC" > "$tmpfile" && mv "$tmpfile" "$ZSHRC"

    # --- 4. 새 alias 블록 추가 (블록 마커 포함, PATH export 포함) ---
    {
        echo ""
        echo "$ALIAS_BLOCK_BEGIN"
        echo 'export PATH="$HOME/.local/bin:$PATH"'
        echo "alias cc='claude --dangerously-skip-permissions \"/init:workflow\"'"
        echo "alias ccc='claude --dangerously-skip-permissions --continue'"
        echo "$ALIAS_BLOCK_END"
    } >> "$ZSHRC"

    if [ "$changed" -eq 1 ]; then
        json_result "ok" "alias cc, ccc가 업데이트되었습니다." "action" "updated"
    else
        json_result "ok" "alias cc, ccc가 추가되었습니다." "action" "created"
    fi
}

# -----------------------------------------------------------------------------
# setup-statusline: StatusLine 전체 설정
# -----------------------------------------------------------------------------
cmd_setup_statusline() {
    local settings_updated="false"
    local script_created="false"

    # --- 1. settings.json 설정 ---
    mkdir -p "$HOME/.claude"

    if [ ! -f "$CLAUDE_SETTINGS" ]; then
        # 파일이 없으면 새로 생성
        cat > "$CLAUDE_SETTINGS" << 'SETTINGS_EOF'
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh",
    "padding": 0
  }
}
SETTINGS_EOF
        settings_updated="true"
    else
        # 파일이 있으면 statusLine 항목 존재 여부 체크
        if ! grep -q '"statusLine"' "$CLAUDE_SETTINGS" 2>/dev/null; then
            # python3 사전 체크
            if ! command -v python3 >/dev/null 2>&1; then
                json_result "error" "python3이 설치되지 않았습니다. settings.json에 statusLine을 수동으로 추가하거나 python3을 설치하세요." \
                    "settings_updated" "false" "script_created" "false" "error_detail" "python3 not found"
                return 1
            fi

            # statusLine 항목이 없으면 추가 (python3으로 JSON 안전 병합)
            local py_error
            py_error=$(python3 -c "
import json, sys

with open('$CLAUDE_SETTINGS', 'r') as f:
    data = json.load(f)

data['statusLine'] = {
    'type': 'command',
    'command': '~/.claude/statusline.sh',
    'padding': 0
}

with open('$CLAUDE_SETTINGS', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')
" 2>&1)
            if [ $? -ne 0 ]; then
                json_result "error" "settings.json 병합 중 python3 오류가 발생했습니다." \
                    "settings_updated" "false" "script_created" "false" "error_detail" "$py_error"
                return 1
            fi
            settings_updated="true"
        fi
    fi

    # --- 2. statusline.sh 스크립트 생성 ---
    if [ ! -f "$STATUSLINE_SCRIPT" ]; then
        cat > "$STATUSLINE_SCRIPT" << 'STATUSLINE_EOF'
#!/usr/bin/env python3
import json, sys, subprocess

data = json.load(sys.stdin)

model = data.get("model", {}).get("display_name", "?")
added = data.get("cost", {}).get("total_lines_added", 0)
removed = data.get("cost", {}).get("total_lines_removed", 0)
ctx_size = data.get("context_window", {}).get("context_window_size", 0)
usage = data.get("context_window", {}).get("current_usage")
cwd = data.get("workspace", {}).get("current_dir", "")

pct = 0
if usage and ctx_size:
    tokens = (usage.get("input_tokens", 0)
              + usage.get("cache_creation_input_tokens", 0)
              + usage.get("cache_read_input_tokens", 0))
    pct = tokens * 100 // ctx_size

branch = ""
try:
    b = subprocess.check_output(
        ["git", "-C", cwd, "branch", "--show-current"],
        stderr=subprocess.DEVNULL, timeout=2
    ).decode().strip()
    if b:
        branch = f" \033[33m{b}\033[0m"
except Exception:
    pass

print(f"\033[36m{model}\033[0m{branch} \033[35mctx:{pct}%\033[0m \033[32m+{added}\033[0m/\033[31m-{removed}\033[0m")
STATUSLINE_EOF
        chmod +x "$STATUSLINE_SCRIPT"
        script_created="true"
    fi

    # JSON 출력
    printf '{"status":"ok","message":"StatusLine 설정 완료","settings_updated":%s,"script_created":%s' \
        "$settings_updated" "$script_created"
    printf ',"settings_path":"%s","script_path":"%s"}\n' \
        "$(json_escape "$CLAUDE_SETTINGS")" "$(json_escape "$STATUSLINE_SCRIPT")"
}

# -----------------------------------------------------------------------------
# setup-slack: Slack 환경변수 설정 (.claude.env에 추가)
# -----------------------------------------------------------------------------
cmd_setup_slack() {
    local url="${1:-}"

    if [ -z "$url" ]; then
        json_result "error" "Slack Webhook URL이 필요합니다. 사용법: init-claude.sh setup-slack <url>"
        return 1
    fi

    # URL 형식 기본 검증 (https://로 시작하는지)
    if [[ ! "$url" =~ ^https?:// ]]; then
        json_result "error" "올바른 URL 형식이 아닙니다: $url"
        return 1
    fi

    # .claude.env에 CLAUDE_CODE_SLACK_WEBHOOK_URL 설정
    set_env "CLAUDE_CODE_SLACK_WEBHOOK_URL" "$url"

    # ~/.zshrc에 export 추가 (중복 체크)
    if [ -f "$ZSHRC" ]; then
        if grep -q "^export CLAUDE_CODE_SLACK_WEBHOOK_URL=" "$ZSHRC" 2>/dev/null; then
            # 기존 값 업데이트 (임시 파일 + mv 방식으로 sed 인젝션 방어)
            local tmpfile
            tmpfile=$(mktemp "${ZSHRC}.tmp.XXXXXX")
            while IFS= read -r line || [ -n "$line" ]; do
                if [[ "$line" == export\ CLAUDE_CODE_SLACK_WEBHOOK_URL=* ]]; then
                    printf '%s\n' "export CLAUDE_CODE_SLACK_WEBHOOK_URL=\"${url}\""
                else
                    printf '%s\n' "$line"
                fi
            done < "$ZSHRC" > "$tmpfile"
            mv "$tmpfile" "$ZSHRC"
            json_result "ok" "CLAUDE_CODE_SLACK_WEBHOOK_URL이 업데이트되었습니다." "action" "updated"
        else
            # 새로 추가 (주석 중복 방지: 기존 주석이 없을 때만 추가)
            {
                if ! grep -q "^# Slack Webhook for Claude Code$" "$ZSHRC" 2>/dev/null; then
                    echo ""
                    echo "# Slack Webhook for Claude Code"
                fi
                echo "export CLAUDE_CODE_SLACK_WEBHOOK_URL=\"${url}\""
            } >> "$ZSHRC"
            json_result "ok" "CLAUDE_CODE_SLACK_WEBHOOK_URL이 추가되었습니다." "action" "created"
        fi
    else
        touch "$ZSHRC"
        {
            echo "# Slack Webhook for Claude Code"
            echo "export CLAUDE_CODE_SLACK_WEBHOOK_URL=\"${url}\""
        } >> "$ZSHRC"
        json_result "ok" "CLAUDE_CODE_SLACK_WEBHOOK_URL이 추가되었습니다." "action" "created"
    fi
}

# -----------------------------------------------------------------------------
# setup-git: Git global 설정 (.claude.env 읽어서 git config)
# -----------------------------------------------------------------------------
cmd_setup_git() {
    # .claude.env 존재 확인
    if [ ! -f "$ENV_FILE" ]; then
        # 템플릿 생성
        cat > "$ENV_FILE" << 'ENV_TEMPLATE'
# ============================================
# Claude Code 환경 변수
# ============================================
#
# 이 파일은 Claude Code Hook 스크립트에서 사용하는 환경 변수를 정의합니다.
# 형식: KEY=value (표준 .env 문법)
# ============================================

# ============================================
# [REQUIRED] Git 설정
# ============================================
CLAUDE_CODE_GIT_USER_NAME=
CLAUDE_CODE_GIT_USER_EMAIL=

# ============================================
# [REQUIRED] SSH 키
# ============================================
CLAUDE_CODE_SSH_KEY_GITHUB=

# ============================================
# [OPTIONAL] 추가 설정
# ============================================
# CLAUDE_CODE_GITHUB_USERNAME=
# CLAUDE_CODE_SSH_CONFIG=
ENV_TEMPLATE
        json_result "skip" ".claude.env 파일을 생성했습니다. 편집 후 다시 실행하세요." "env_path" "$ENV_FILE"
        return 0
    fi

    # 환경변수 읽기
    local git_user_name
    local git_user_email
    local ssh_key_github
    git_user_name=$(read_env "CLAUDE_CODE_GIT_USER_NAME")
    git_user_email=$(read_env "CLAUDE_CODE_GIT_USER_EMAIL")
    ssh_key_github=$(read_env "CLAUDE_CODE_SSH_KEY_GITHUB")
    # 참고: $HOME/~ 확장은 read_env에서 자동 처리됨

    # 필수 필드 검증
    if [ -z "$git_user_name" ] || [ -z "$git_user_email" ]; then
        json_result "error" "CLAUDE_CODE_GIT_USER_NAME 또는 CLAUDE_CODE_GIT_USER_EMAIL이 설정되지 않았습니다." "env_path" "$ENV_FILE"
        return 1
    fi

    # Before 상태 수집
    local before_name before_email before_ssh
    before_name=$(git config --global user.name 2>/dev/null || echo "(unset)")
    before_email=$(git config --global user.email 2>/dev/null || echo "(unset)")
    before_ssh=$(git config --global core.sshCommand 2>/dev/null || echo "(unset)")

    # Git config 설정
    git config --global user.name "$git_user_name"
    git config --global user.email "$git_user_email"

    # SSH 키 설정 (파일 존재 시)
    local ssh_configured="false"
    local ssh_key_warning=""
    if [ -n "$ssh_key_github" ]; then
        if [ -f "$ssh_key_github" ]; then
            git config --global core.sshCommand "ssh -i \"$ssh_key_github\" -o IdentitiesOnly=yes"
            ssh_configured="true"
        else
            ssh_key_warning="파일 미존재: $ssh_key_github"
        fi
    fi

    # After 상태 수집
    local after_name after_email after_ssh
    after_name=$(git config --global user.name 2>/dev/null || echo "(unset)")
    after_email=$(git config --global user.email 2>/dev/null || echo "(unset)")
    after_ssh=$(git config --global core.sshCommand 2>/dev/null || echo "(unset)")

    # JSON 결과 출력
    printf '{"status":"ok","message":"Git global 설정 완료",'
    printf '"before":{"user_name":"%s","user_email":"%s","ssh_command":"%s"},' \
        "$(json_escape "$before_name")" "$(json_escape "$before_email")" "$(json_escape "$before_ssh")"
    printf '"after":{"user_name":"%s","user_email":"%s","ssh_command":"%s"},' \
        "$(json_escape "$after_name")" "$(json_escape "$after_email")" "$(json_escape "$after_ssh")"
    printf '"ssh_configured":%s' "$ssh_configured"
    if [ -n "$ssh_key_warning" ]; then
        printf ',"ssh_key_warning":"%s"' "$(json_escape "$ssh_key_warning")"
    fi
    printf '}\n'
}

# -----------------------------------------------------------------------------
# verify: 전체 설정 검증
# -----------------------------------------------------------------------------
cmd_verify() {
    local all_ok=true

    # 1. Shell alias 검증
    local alias_cc="false"
    local alias_ccc="false"
    if [ -f "$ZSHRC" ]; then
        grep -q "^alias cc=" "$ZSHRC" 2>/dev/null && alias_cc="true"
        grep -q "^alias ccc=" "$ZSHRC" 2>/dev/null && alias_ccc="true"
    fi
    if [ "$alias_cc" = "false" ] || [ "$alias_ccc" = "false" ]; then
        all_ok=false
    fi

    # 2. StatusLine settings.json 검증
    local statusline_settings="false"
    if [ -f "$CLAUDE_SETTINGS" ] && grep -q '"statusLine"' "$CLAUDE_SETTINGS" 2>/dev/null; then
        statusline_settings="true"
    fi
    if [ "$statusline_settings" = "false" ]; then
        all_ok=false
    fi

    # 3. StatusLine 스크립트 검증
    local statusline_script="false"
    if [ -f "$STATUSLINE_SCRIPT" ] && [ -x "$STATUSLINE_SCRIPT" ]; then
        statusline_script="true"
    fi
    if [ "$statusline_script" = "false" ]; then
        all_ok=false
    fi

    # 4. Slack 환경변수 검증 (선택사항이므로 all_ok에 영향 없음)
    #    빈값(KEY= 또는 KEY="") 제외: ^KEY=.\+ 패턴으로 값이 있는 경우만 매칭
    local slack_env="false"
    local slack_source=""
    if [ -f "$ENV_FILE" ] && grep -q "^CLAUDE_CODE_SLACK_BOT_TOKEN=.\+" "$ENV_FILE" 2>/dev/null; then
        slack_env="true"
        slack_source="claude_env"
    elif [ -f "$ENV_FILE" ] && grep -q "^CLAUDE_CODE_SLACK_WEBHOOK_URL=.\+" "$ENV_FILE" 2>/dev/null; then
        slack_env="true"
        slack_source="claude_env"
    elif [ -f "$ZSHRC" ] && grep -q "^export CLAUDE_CODE_SLACK_WEBHOOK_URL=.\+" "$ZSHRC" 2>/dev/null; then
        slack_env="true"
        slack_source="zshrc"
    fi

    # 5. PATH에 ~/.local/bin 포함 여부 검증
    local path_local_bin="false"
    if echo "$PATH" | tr ':' '\n' | grep -qx "$HOME/.local/bin"; then
        path_local_bin="true"
    fi
    local path_local_bin_zshrc="false"
    if [ -f "$ZSHRC" ] && grep -q 'export PATH=.*\$HOME/\.local/bin' "$ZSHRC" 2>/dev/null; then
        path_local_bin_zshrc="true"
    fi
    if [ "$path_local_bin" = "false" ] && [ "$path_local_bin_zshrc" = "false" ]; then
        all_ok=false
    fi

    # 6. Git 설정 검증
    local git_name git_email
    git_name=$(git config --global user.name 2>/dev/null || echo "")
    git_email=$(git config --global user.email 2>/dev/null || echo "")
    local git_configured="false"
    if [ -n "$git_name" ] && [ -n "$git_email" ]; then
        git_configured="true"
    else
        all_ok=false
    fi

    # JSON 결과 출력
    printf '{"status":"%s","message":"%s",' \
        "$([ "$all_ok" = true ] && echo "ok" || echo "partial")" \
        "$([ "$all_ok" = true ] && echo "전체 설정 검증 완료" || echo "일부 설정이 누락되었습니다")"

    printf '"checks":{'
    printf '"alias_cc":%s,' "$alias_cc"
    printf '"alias_ccc":%s,' "$alias_ccc"
    printf '"statusline_settings":%s,' "$statusline_settings"
    printf '"statusline_script":%s,' "$statusline_script"
    printf '"slack_configured":%s,' "$slack_env"
    if [ -n "$slack_source" ]; then
        printf '"slack_source":"%s",' "$slack_source"
    fi
    printf '"path_local_bin":%s,' "$path_local_bin"
    printf '"path_local_bin_zshrc":%s,' "$path_local_bin_zshrc"
    printf '"git_configured":%s,' "$git_configured"
    printf '"git_user_name":"%s",' "$(json_escape "$git_name")"
    printf '"git_user_email":"%s"' "$(json_escape "$git_email")"
    printf '}}\n'
}

# -----------------------------------------------------------------------------
# 도움말
# -----------------------------------------------------------------------------
cmd_help() {
    cat << 'HELP_EOF'
init-claude.sh - Claude Code 사용자 환경 초기화 스크립트

사용법:
  ./init-claude.sh <subcommand> [args]

서브커맨드:
  check-alias          alias 존재 여부 체크 (JSON 출력)
  setup-alias          alias 추가 (~/.zshrc에)
  setup-statusline     StatusLine 전체 설정 (settings.json + statusline.sh)
  setup-slack <url>    Slack Webhook URL 설정 (.claude.env + ~/.zshrc에 추가)
  setup-git            Git global 설정 (.claude.env 읽어서 git config)
  verify               전체 설정 검증 (JSON 출력)
  help                 이 도움말 표시

예시:
  ./init-claude.sh check-alias
  ./init-claude.sh setup-alias
  ./init-claude.sh setup-statusline
  ./init-claude.sh setup-slack "https://hooks.slack.com/services/xxx/yyy/zzz"
  ./init-claude.sh setup-git
  ./init-claude.sh verify
HELP_EOF
}

# -----------------------------------------------------------------------------
# 메인 디스패치
# -----------------------------------------------------------------------------
main() {
    local subcommand="${1:-help}"
    shift || true

    case "$subcommand" in
        check-alias)
            cmd_check_alias "$@"
            ;;
        setup-alias)
            cmd_setup_alias "$@"
            ;;
        setup-statusline)
            cmd_setup_statusline "$@"
            ;;
        setup-slack)
            cmd_setup_slack "$@"
            ;;
        setup-git)
            cmd_setup_git "$@"
            ;;
        verify)
            cmd_verify "$@"
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            json_result "error" "알 수 없는 서브커맨드: $subcommand"
            echo ""
            cmd_help
            return 1
            ;;
    esac
}

main "$@"
