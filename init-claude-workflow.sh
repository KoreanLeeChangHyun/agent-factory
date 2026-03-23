#!/bin/bash
set -euo pipefail

# ==============================================================================
# init-claude-workflow.sh
# Claude Code 워크플로우 환경 자동 초기화 스크립트
# 지원: Ubuntu 20.04+, macOS 13.0+
# 의존성: git, curl, python3, tmux, gh
# ==============================================================================

# --- Python 최소 버전 ---
REQUIRED_PYTHON_MAJOR=3
REQUIRED_PYTHON_MINOR=10

# --- 색상 변수 ---
if [ -t 1 ]; then
    GREEN=$'\033[0;32m'
    RED=$'\033[0;31m'
    YELLOW=$'\033[0;33m'
    NC=$'\033[0m' # No Color
else
    GREEN=""
    RED=""
    YELLOW=""
    NC=""
fi

# --- 쉘 판별 헬퍼 ---
# $SHELL은 로그인 쉘을 반환하며, 현재 실행 중인 쉘(예: bash에서 zsh 실행)과
# 다를 수 있습니다. 이 함수는 로그인 쉘 기준으로 설정 파일 경로를 판별합니다.
detect_shell_rc() {
    local _shell_name
    _shell_name="$(basename "$SHELL")"
    case "$_shell_name" in
        zsh)
            DETECTED_SHELL_NAME="zsh"
            DETECTED_SHELL_RC="$HOME/.zshrc"
            ;;
        bash)
            DETECTED_SHELL_NAME="bash"
            DETECTED_SHELL_RC="$HOME/.bashrc"
            ;;
        *)
            DETECTED_SHELL_NAME="$_shell_name"
            DETECTED_SHELL_RC="$HOME/.bashrc"
            ;;
    esac
}

# --- 공통 출력 함수 ---
print_success() {
    printf '%s  ✓ %s%s\n' "${GREEN}" "$1" "${NC}"
}

print_error() {
    printf '%s  ✗ %s%s\n' "${RED}" "$1" "${NC}"
}

print_info() {
    printf '%s  → %s%s\n' "${YELLOW}" "$1" "${NC}"
}

print_step() {
    printf '\n%s[Step %s]%s %s\n' "${GREEN}" "$1" "${NC}" "$2"
}

# ==============================================================================
# OS 감지 및 버전 검증
# ==============================================================================
detect_os() {
    local os_type
    os_type="$(uname -s)"

    case "$os_type" in
        Linux)
            DETECTED_OS="linux"
            if [ ! -f /etc/os-release ]; then
                print_error "지원되지 않는 Linux 배포판입니다. /etc/os-release 파일이 없습니다."
                exit 1
            fi
            # shellcheck source=/dev/null
            . /etc/os-release
            local version_id="${VERSION_ID:-0}"
            local major_version
            major_version="$(echo "$version_id" | cut -d. -f1)"
            if [ "$major_version" -lt 20 ] 2>/dev/null; then
                print_error "Ubuntu 20.04 이상이 필요합니다. 현재 버전: $version_id"
                exit 1
            fi
            print_success "OS 감지: Linux (Ubuntu $version_id)"
            ;;
        Darwin)
            DETECTED_OS="macos"
            local macos_version
            macos_version="$(sw_vers -productVersion 2>/dev/null || echo '0.0')"
            local macos_major
            macos_major="$(echo "$macos_version" | cut -d. -f1)"
            if [ "$macos_major" -lt 13 ] 2>/dev/null; then
                print_error "macOS 13.0 (Ventura) 이상이 필요합니다. 현재 버전: $macos_version"
                exit 1
            fi
            print_success "OS 감지: macOS ($macos_version)"
            ;;
        *)
            print_error "지원되지 않는 OS입니다: $os_type (Ubuntu 20.04+ 또는 macOS 13.0+ 필요)"
            exit 1
            ;;
    esac
}

# ==============================================================================
# Python 최소 버전 검증
# ==============================================================================
check_python_version() {
    local current_version
    current_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

    if python3 -c "import sys; sys.exit(0 if (sys.version_info.major, sys.version_info.minor) >= ($REQUIRED_PYTHON_MAJOR, $REQUIRED_PYTHON_MINOR) else 1)" 2>/dev/null; then
        return 0
    fi

    print_error "Python 버전 미달: 현재 $current_version, 최소 요구 ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
    print_info "Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR} 이상으로 업그레이드하세요:"
    case "${DETECTED_OS:-linux}" in
        macos)
            print_info "  brew install python@${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
            ;;
        linux)
            print_info "  sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt-get update"
            print_info "  sudo apt-get install python${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
            ;;
        *)
            print_info "  https://www.python.org/downloads/ 에서 Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}+ 를 설치하세요"
            ;;
    esac
    exit 1
}

# ==============================================================================
# python3 및 tmux 자동 설치
# ==============================================================================
install_dependencies() {
    print_step "2" "의존성 설치 확인 (python3, tmux, gh)"

    local missing_deps=()

    if ! command -v python3 &>/dev/null; then
        missing_deps+=("python3")
    else
        check_python_version
    fi

    if ! command -v tmux &>/dev/null; then
        missing_deps+=("tmux")
    fi

    if ! command -v gh &>/dev/null; then
        missing_deps+=("gh")
    fi

    if [ "${#missing_deps[@]}" -eq 0 ]; then
        print_success "의존성 이미 설치됨 (python3, tmux, gh)"
        return 0
    fi

    print_info "미설치 의존성: ${missing_deps[*]}"

    case "${DETECTED_OS:-linux}" in
        linux)
            print_info "apt-get으로 설치합니다 (sudo 권한이 필요합니다)..."
            if ! sudo apt-get update -qq; then
                print_error "apt-get update 실패"
                return 1
            fi

            # gh CLI는 apt 기본 저장소에 없으므로 GitHub 공식 APT 저장소를 먼저 등록
            if printf '%s\n' "${missing_deps[@]}" | grep -qx 'gh'; then
                print_info "GitHub CLI 공식 APT 저장소를 등록합니다..."
                if ! command -v curl &>/dev/null; then
                    print_error "curl이 없어 gh APT 저장소 등록에 실패했습니다. curl을 먼저 설치하세요."
                    return 1
                fi
                if curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
                        | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg 2>/dev/null \
                   && sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
                   && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
                        | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
                   && sudo apt-get update -qq; then
                    print_success "GitHub CLI APT 저장소 등록 완료"
                else
                    print_error "GitHub CLI APT 저장소 등록 실패. gh를 수동으로 설치하세요: https://cli.github.com"
                    # gh를 missing_deps에서 제외하고 나머지 의존성만 설치
                    missing_deps=("${missing_deps[@]/gh}")
                    # 배열 재구성 (빈 원소 제거)
                    local filtered=()
                    for dep in "${missing_deps[@]}"; do
                        [ -n "$dep" ] && filtered+=("$dep")
                    done
                    missing_deps=("${filtered[@]}")
                fi
            fi

            if [ "${#missing_deps[@]}" -gt 0 ]; then
                if ! sudo apt-get install -y "${missing_deps[@]}"; then
                    print_error "패키지 설치 실패: ${missing_deps[*]}"
                    return 1
                fi
            fi
            ;;
        macos)
            if ! command -v brew &>/dev/null; then
                print_error "Homebrew가 설치되어 있지 않습니다. https://brew.sh 에서 먼저 설치해 주세요."
                return 1
            fi
            if ! brew install "${missing_deps[@]}"; then
                print_error "brew install 실패: ${missing_deps[*]}"
                return 1
            fi
            ;;
        *)
            print_error "알 수 없는 OS에서는 자동 설치를 지원하지 않습니다."
            return 1
            ;;
    esac

    # 설치 후 재확인
    local still_missing=()
    for dep in "${missing_deps[@]}"; do
        if ! command -v "$dep" &>/dev/null; then
            still_missing+=("$dep")
        fi
    done

    if [ "${#still_missing[@]}" -gt 0 ]; then
        print_error "설치 후에도 다음 의존성을 찾을 수 없습니다: ${still_missing[*]}"
        return 1
    fi

    print_success "의존성 설치 완료 (${missing_deps[*]})"
}

# ==============================================================================
# Step 1: Claude Code 설치 (OS 감지 후 실행)
# ==============================================================================
install_claude_code() {
    print_step "1" "Claude Code 설치 확인"

    if command -v claude &>/dev/null; then
        print_success "Claude Code가 이미 설치되어 있습니다 ($(claude --version 2>/dev/null || echo 'version unknown'))"
        return 0
    fi

    print_info "Claude Code가 설치되어 있지 않습니다. 설치를 시작합니다..."

    if ! command -v curl &>/dev/null; then
        print_error "curl이 설치되어 있지 않습니다. curl을 먼저 설치해 주세요."
        return 1
    fi

    local install_script
    install_script="$(mktemp)"

    if ! curl -fsSL -o "$install_script" https://claude.ai/install.sh; then
        print_error "Claude Code 설치 스크립트 다운로드에 실패했습니다"
        rm -f "$install_script"
        return 1
    fi

    if bash "$install_script"; then
        print_success "Claude Code 설치 완료"
    else
        print_error "Claude Code 설치에 실패했습니다"
        rm -f "$install_script"
        return 1
    fi

    rm -f "$install_script"
}

# ==============================================================================
# Step 7: 쉘 aliases 설정
# ==============================================================================
setup_shell_aliases() {
    print_step "7" "쉘 aliases 설정"

    local aliases_file="$HOME/.claude.aliases"

    # 쉘 판별
    detect_shell_rc
    local shell_name="$DETECTED_SHELL_NAME"
    local shell_rc="$DETECTED_SHELL_RC"
    if [ "$shell_name" != "zsh" ] && [ "$shell_name" != "bash" ]; then
        print_info "감지된 쉘: $shell_name (bash 설정으로 대체합니다)"
    fi

    # .claude.aliases 파일이 이미 존재하면 스킵 (사용자 설정 보존)
    if [ -f "$aliases_file" ]; then
        print_info ".claude.aliases 파일이 이미 존재합니다. 기존 내용을 유지합니다. ($aliases_file)"
    else
        # Claude 실행 파일 경로 동적 감지
        local claude_path
        claude_path="$(command -v claude 2>/dev/null || echo '')"

        cat > "$aliases_file" << 'ALIASES_EOF'
# 이 파일은 init-claude-workflow.sh가 생성합니다.
# Claude Code workflow aliases
export PATH="$HOME/.local/bin:$PATH"

alias cc='claude --dangerously-skip-permissions'
alias ccc='claude --dangerously-skip-permissions --continue'
alias ccv='claude --dangerously-skip-permissions'
cct() {
  local i=0 name="main"
  while tmux has-session -t "$name" 2>/dev/null; do
    name="main-$((++i))"
  done
  tmux new-session -s "$name" "claude --dangerously-skip-permissions"
}

# flow-* 배너 alias
alias flow-claude='.claude/scripts/banner/flow_claude_banner.sh'
alias flow-step='.claude/scripts/banner/flow_step_banner.sh'
alias flow-phase='.claude/scripts/banner/flow_phase_banner.sh'

# flow-* 스크립트 alias
alias flow-init='python3 .claude/scripts/flow/initialization.py'
alias flow-finish='python3 .claude/scripts/flow/finalization.py'
alias flow-reload='python3 .claude/scripts/flow/reload_prompt.py'
alias flow-update='python3 .claude/scripts/flow/update_state.py'
alias flow-skillmap='python3 .claude/scripts/flow/skill_mapper.py'
alias flow-validate='python3 .claude/scripts/flow/plan_validator.py'
alias flow-validate-p='python3 .claude/scripts/flow/prompt_validator.py'
alias flow-recommend='python3 .claude/scripts/flow/skill_recommender.py'
alias flow-gc='python3 .claude/scripts/flow/garbage_collect.py'
alias flow-kanban='python3 .claude/scripts/flow/kanban.py'
alias flow-tmux='python3 .claude/scripts/flow/tmux_launcher.py'
ALIASES_EOF

        print_success ".claude.aliases 파일 생성 완료 ($aliases_file)"
    fi

    # 쉘 설정 파일에 source 라인 추가 (중복 확인)
    local source_line="# Claude Code workflow aliases"
    local source_cmd="[ -f \"$aliases_file\" ] && source \"$aliases_file\""

    if [ ! -f "$shell_rc" ]; then
        touch "$shell_rc"
    fi

    if grep -q ".claude.aliases" "$shell_rc" 2>/dev/null; then
        print_success "쉘 설정 파일에 source 라인이 이미 등록되어 있습니다 ($shell_rc)"
    else
        {
            echo ""
            echo "$source_line"
            echo "$source_cmd"
        } >> "$shell_rc"
        print_success "쉘 설정 파일에 source 라인 추가 완료 ($shell_rc)"
    fi
}

# ==============================================================================
# Step 4: 디렉터리 및 파일 생성
# ==============================================================================
create_directories_and_files() {
    print_step "4" "디렉터리 및 파일 생성"

    # 디렉터리 생성 (.kanban 기반)
    local dirs=(".kanban" ".kanban/active" ".kanban/done" ".workflow/.history" ".workflow/.temp")
    for dir in "${dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            print_success "디렉터리 생성: $dir"
        else
            print_info "디렉터리 이미 존재: $dir"
        fi
    done

    # 파일 생성 (존재하지 않는 경우만)
    local files=(
        ".kanban/.memo.txt"
        ".kanban/.todo.txt"
        "CLAUDE.md"
    )
    for file in "${files[@]}"; do
        if [ ! -f "$file" ]; then
            touch "$file"
            print_success "파일 생성: $file"
        else
            print_info "파일 이미 존재: $file"
        fi
    done

}

# ==============================================================================
# Step 4.5: .claude/settings.json 생성
# ==============================================================================
setup_settings_json() {
    print_step "4.5" ".claude/settings.json 생성"

    local settings_file=".claude/settings.json"

    if [ -f "$settings_file" ]; then
        print_info ".claude/settings.json 파일이 이미 존재합니다. 기존 내용을 유지합니다."
        return 0
    fi

    if [ ! -d ".claude" ]; then
        print_info ".claude/ 디렉터리가 없습니다. settings.json 생성을 스킵합니다."
        return 0
    fi

    cat > "$settings_file" << 'SETTINGS_EOF'
{
  "statusLine": {
    "type": "command",
    "command": "python3 -u .claude/scripts/statusline.py"
  },
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume|compact|clear",
        "hooks": [
          {
            "type": "command",
            "command": "python3 -u .claude/scripts/sync/history_sync.py sync && python3 -u .claude/scripts/sync/history_sync.py archive",
            "timeout": 30,
            "async": true
          }
        ]
      },
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "python3 -u .claude/board/server.py",
            "timeout": 5,
            "async": true
          }
        ]
      },
      {
        "matcher": "startup|resume|compact|clear",
        "hooks": [
          {
            "type": "command",
            "command": "python3 -u .claude/hooks/session-start.py",
            "timeout": 5
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 -u .claude/hooks/pre-tool-use.py",
            "statusMessage": "pre-tool-use 디스패처 실행 중..."
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 -u .claude/hooks/subagent-stop.py",
            "timeout": 10,
            "statusMessage": "subagent-stop 디스패처 실행 중..."
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 -u .claude/hooks/post-tool-use.py",
            "timeout": 30,
            "async": true,
            "statusMessage": "post-tool-use 디스패처 실행 중..."
          }
        ]
      }
    ]
  }
}
SETTINGS_EOF

    # JSON 유효성 검증
    if python3 -c 'import json, sys; json.load(open(sys.argv[1]))' "$settings_file" 2>/dev/null; then
        print_success ".claude/settings.json 생성 완료 (JSON 유효성 검증 통과)"
    else
        print_error ".claude/settings.json JSON 유효성 검증 실패. 파일을 확인하세요."
        return 1
    fi
}

# ==============================================================================
# Step 5: .claude.env 템플릿 생성
# ==============================================================================
generate_claude_env() {
    print_step "5" ".claude.env 템플릿 생성"

    local env_file=".claude.env"

    if [ -f "$env_file" ]; then
        print_info ".claude.env 파일이 이미 존재합니다. 기존 내용을 유지합니다."
        return 0
    fi

    cat > "$env_file" << 'CLAUDE_ENV_EOF'
# =========================================================================================
# .claude.env — Claude Code 워크플로우 환경 변수
# 이 파일은 init-claude-workflow.sh가 생성합니다.
# 형식: KEY=value (표준 .env 문법)
# 민감한 정보가 포함될 수 있으므로 .gitignore에 등록하세요.
# =========================================================================================

# -----------------------------------------------------------------------------------------
# (1) Slack 연동
# -----------------------------------------------------------------------------------------

# Slack Bot OAuth Token (xoxb-로 시작)
# 용도: Claude Code 작업 완료/대기 알림 전송
CLAUDE_CODE_SLACK_BOT_TOKEN=

# Slack 채널 ID (C로 시작)
# 용도: 알림이 전송될 채널 지정
CLAUDE_CODE_SLACK_CHANNEL_ID=

# -----------------------------------------------------------------------------------------
# (2) Git 설정
# -----------------------------------------------------------------------------------------

CLAUDE_CODE_GIT_USER_NAME=
CLAUDE_CODE_GIT_USER_EMAIL=
CLAUDE_CODE_GITHUB_USERNAME=
CLAUDE_CODE_SSH_KEY_GITHUB=

# -----------------------------------------------------------------------------------------
# (3) Hook 제어 플래그 (HOOK_* 체계)
# true/false로 각 hook의 활성/비활성을 제어합니다.
# -----------------------------------------------------------------------------------------

# pre-tool-use hooks
HOOK_DANGEROUS_COMMAND=false
HOOK_HOOKS_SELF_PROTECT=false
HOOK_SLACK_ASK=false
HOOK_TASK_HISTORY_SYNC=false
HOOK_AGENT_INVESTIGATION_GUARD=false
HOOK_MAIN_BRANCH_GUARD=false
HOOK_MAIN_SESSION_GUARD=false
HOOK_KANBAN_SUBCOMMAND_GUARD=false

# session-start hooks
HOOK_SESSION_SYSTEM_PROMPT=true

# stop hooks
HOOK_WORKFLOW_AUTO_CONTINUE=false

# subagent-stop hooks
HOOK_USAGE_TRACKER=true
HOOK_HISTORY_SYNC_TRIGGER=false

# post-tool-use hooks
HOOK_CATALOG_SYNC=true

# -----------------------------------------------------------------------------------------
# (4) 강제 규칙 제어 플래그 (ENFORCE_* 체계)
# true/false로 각 강제 규칙의 활성/비활성을 제어합니다.
# -----------------------------------------------------------------------------------------

# CSO 원칙 (스킬 description 트리거 조건만으로 제한)
ENFORCE_CSO_PRINCIPLE=true

# 합리화 방지 테이블 강제
ENFORCE_RATIONALIZATION_GUARD=true

# Verification Result Table 필수화
ENFORCE_VRT=true

# Self-Review 체크리스트 강제
ENFORCE_SELF_REVIEW=true

# 토큰 효율 목표값 강제
ENFORCE_TOKEN_EFFICIENCY=true

# -----------------------------------------------------------------------------------------
# (5) 워크플로우 설정
# -----------------------------------------------------------------------------------------

# .workflow/ 디렉터리에 유지할 최대 워크플로우 수 (기본값: 10)
CLAUDE_WORKFLOW_KEEP_COUNT=10

# 체인 스테이지 실패 시 최대 재시도 횟수 (기본값: 2)
CLAUDE_CHAIN_MAX_RETRY=2
CLAUDE_ENV_EOF

    print_success ".claude.env 템플릿 생성 완료 ($env_file)"
}

# ==============================================================================
# Step 6: 레거시 .prompt/ 마이그레이션
# ==============================================================================
migrate_legacy_prompt() {
    print_step "6" "레거시 .prompt/ 마이그레이션"

    local prompt_dir=".prompt"
    local kanban_dir=".kanban"

    if [ ! -d "$prompt_dir" ]; then
        print_info "레거시 .prompt/ 디렉터리 없음, 마이그레이션 스킵"
        return 0
    fi

    print_info "레거시 .prompt/ 디렉터리 발견. .kanban/으로 마이그레이션을 시작합니다..."

    # .kanban/ 디렉터리가 없으면 생성
    if [ ! -d "$kanban_dir" ]; then
        mkdir -p "$kanban_dir"
        print_success ".kanban/ 디렉터리 생성"
    fi

    # prompt.txt 내용을 .kanban/.memo.txt에 append (내용 보존)
    if [ -f "$prompt_dir/prompt.txt" ] && [ -s "$prompt_dir/prompt.txt" ]; then
        {
            echo ""
            echo "# === 마이그레이션된 .prompt/prompt.txt 내용 ($(date +%Y%m%d)) ==="
            cat "$prompt_dir/prompt.txt"
        } >> "$kanban_dir/.memo.txt"
        print_success ".prompt/prompt.txt 내용을 .kanban/.memo.txt에 보존했습니다"
    fi

    # .prompt/ 내 모든 .txt 파일을 .kanban/으로 복사 (원본 보존)
    local copied=0
    for txt_file in "$prompt_dir"/*.txt; do
        if [ -f "$txt_file" ]; then
            local filename
            filename="$(basename "$txt_file")"
            if cp "$txt_file" "$kanban_dir/$filename"; then
                print_success "복사: $txt_file → $kanban_dir/$filename"
                copied=$((copied + 1))
            else
                print_error "복사 실패: $txt_file"
            fi
        fi
    done

    if [ "$copied" -eq 0 ]; then
        print_info ".prompt/ 디렉터리에 .txt 파일이 없습니다"
    else
        print_success "${copied}개 파일을 .kanban/으로 복사 완료"
    fi

    # .prompt/ 디렉터리를 .prompt.bak.YYYYMMDD로 리네임하여 백업 보존
    local backup_name=".prompt.bak.$(date +%Y%m%d)"
    if mv "$prompt_dir" "$backup_name"; then
        print_success ".prompt/ 디렉터리를 ${backup_name}으로 백업 완료"
    else
        print_error ".prompt/ 디렉터리 백업 이름 변경에 실패했습니다"
        return 1
    fi
}

# ==============================================================================
# Step 8: .gitignore 업데이트
# ==============================================================================
update_gitignore() {
    print_step "8" ".gitignore 업데이트"

    # .gitignore 파일 존재 확인
    if [ ! -f ".gitignore" ]; then
        touch ".gitignore"
        print_success ".gitignore 파일 생성"
    fi

    local entries=(
        " "
        ".workflow/"
        ".claude/"
        ".claude.env"
        ".claude.env*"
        ".kanban/"
        "CLAUDE.md"
        "__pycache__/"
        ".temp/"
        ".temp/*"
        "temp/"
        ".vscode/"
        ".dashboard/"
    )

    local added=0
    for entry in "${entries[@]}"; do
        if ! grep -qxF "$entry" ".gitignore" 2>/dev/null; then
            echo "$entry" >> ".gitignore"
            print_success ".gitignore에 추가: $entry"
            added=$((added + 1))
        fi
    done

    if [ "$added" -eq 0 ]; then
        print_info ".gitignore에 모든 필수 항목이 이미 등록되어 있습니다"
    else
        print_success ".gitignore에 ${added}개 항목 추가 완료"
    fi
}

# ==============================================================================
# Step 3: .claude 디렉터리 클론
# ==============================================================================
clone_claude_directory() {
    print_step "3" ".claude 디렉터리 클론 (원격 저장소)"

    local repo_url="https://github.com/KoreanLeeChangHyun/claude-workflow.git"
    local tmp_dir

    if ! command -v git &>/dev/null; then
        print_error "git이 설치되어 있지 않습니다"
        return 1
    fi

    tmp_dir="$(mktemp -d)"

    # 기존 EXIT trap 저장 후, 임시 디렉터리 정리 trap 설정
    local old_trap
    old_trap="$(trap -p EXIT)"
    trap 'rm -rf "$tmp_dir"' EXIT

    print_info "원격 저장소 클론 중... ($repo_url)"

    if ! git clone --depth 1 "$repo_url" "$tmp_dir/claude-workflow" 2>/dev/null; then
        print_error "원격 저장소 클론에 실패했습니다. 기존 .claude 디렉터리를 유지합니다."
        rm -rf "$tmp_dir"
        eval "$old_trap"
        return 1
    fi

    # 클론된 저장소에 .claude 디렉터리가 있는지 확인
    if [ ! -d "$tmp_dir/claude-workflow/.claude" ]; then
        print_error "클론된 저장소에 .claude 디렉터리가 없습니다. 기존 .claude 디렉터리를 유지합니다."
        rm -rf "$tmp_dir"
        eval "$old_trap"
        return 1
    fi

    # 심볼릭 링크 검사 (SEC-005)
    if [ -L ".claude" ]; then
        print_info ".claude가 심볼릭 링크입니다. 링크를 제거하고 실제 디렉터리로 교체합니다."
        rm -f ".claude"
    fi

    # 원자적 교체: .claude.new에 복사 후 기존 .claude 삭제, mv로 교체
    rm -rf ".claude.new"
    if ! cp -r "$tmp_dir/claude-workflow/.claude" ".claude.new"; then
        print_error ".claude 디렉터리 복사에 실패했습니다. 기존 .claude 디렉터리를 유지합니다."
        rm -rf ".claude.new"
        rm -rf "$tmp_dir"
        eval "$old_trap"
        return 1
    fi
    rm -rf ".claude"
    mv ".claude.new" ".claude"
    print_success ".claude 디렉터리 교체 완료"

    # 임시 디렉터리 정리 및 기존 trap 복원
    rm -rf "$tmp_dir"
    eval "$old_trap"

    print_success "임시 클론 디렉터리 정리 완료"

    # .claude/ 내 모든 .sh 파일에 실행 권한 부여
    find ".claude/" -name '*.sh' -exec chmod +x {} +
    print_success ".claude/ 내 .sh 파일 chmod +x 완료"
}

# ==============================================================================
# Step 9: 설치 검증
# ==============================================================================
verify_installation() {
    print_step "9" "설치 검증"

    local failed=0

    # (a) python3 실행 가능 여부 및 최소 버전 검증
    if command -v python3 &>/dev/null; then
        local py_version
        py_version="$(python3 --version 2>&1)"
        print_success "python3 실행 가능 ($py_version)"

        # 버전 요구사항 검증
        if python3 -c "import sys; sys.exit(0 if (sys.version_info.major, sys.version_info.minor) >= ($REQUIRED_PYTHON_MAJOR, $REQUIRED_PYTHON_MINOR) else 1)" 2>/dev/null; then
            print_success "python3 버전 검증 PASS (>= ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR})"
        else
            local current_ver
            current_ver="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
            print_error "python3 버전 검증 FAIL: 현재 ${current_ver}, 최소 요구 ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
            failed=$((failed + 1))
        fi
    else
        print_error "python3 명령어를 찾을 수 없습니다"
        failed=$((failed + 1))
    fi

    # (b) tmux 실행 가능 여부
    if command -v tmux &>/dev/null; then
        print_success "tmux 실행 가능 ($(tmux -V 2>/dev/null || echo 'version unknown'))"
    else
        print_error "tmux 명령어를 찾을 수 없습니다"
        failed=$((failed + 1))
    fi

    # (b2) gh CLI 실행 가능 여부
    if command -v gh &>/dev/null; then
        print_success "gh CLI 실행 가능 ($(gh --version 2>/dev/null | head -1 || echo 'version unknown'))"
    else
        print_error "gh 명령어를 찾을 수 없습니다"
        failed=$((failed + 1))
    fi

    # (c) claude 명령어 실행 가능 여부
    if command -v claude &>/dev/null; then
        print_success "claude 명령어 실행 가능"
    else
        print_error "claude 명령어를 찾을 수 없습니다"
        failed=$((failed + 1))
    fi

    # (d) .kanban/, .kanban/done/ 디렉터리 존재
    local kanban_ok=true
    for dir in ".kanban" ".kanban/done"; do
        if [ ! -d "$dir" ]; then
            print_error "필수 디렉터리 없음: $dir"
            kanban_ok=false
            failed=$((failed + 1))
        fi
    done
    if [ "$kanban_ok" = true ]; then
        print_success ".kanban/, .kanban/done/ 디렉터리 존재 확인"
    fi

    # (e) .claude.env 파일 존재
    if [ -f ".claude.env" ]; then
        print_success ".claude.env 파일 존재 확인"
    else
        print_error ".claude.env 파일이 없습니다"
        failed=$((failed + 1))
    fi

    # (f) .claude/ 디렉터리 존재
    if [ -d ".claude" ]; then
        print_success ".claude/ 디렉터리 존재 확인"
    else
        print_error ".claude/ 디렉터리가 없습니다"
        failed=$((failed + 1))
    fi

    # (g) aliases 파일 존재 및 shell rc에 source 라인 등록
    local aliases_file="$HOME/.claude.aliases"
    detect_shell_rc
    local shell_rc="$DETECTED_SHELL_RC"

    if [ -f "$aliases_file" ] && grep -q ".claude.aliases" "$shell_rc" 2>/dev/null; then
        print_success "aliases 파일 존재 및 쉘 설정 파일에 source 라인 등록 확인"
    else
        if [ ! -f "$aliases_file" ]; then
            print_error "aliases 파일이 없습니다: $aliases_file"
        fi
        if ! grep -q ".claude.aliases" "$shell_rc" 2>/dev/null; then
            print_error "쉘 설정 파일에 source 라인이 없습니다: $shell_rc"
        fi
        failed=$((failed + 1))
    fi

    # (h) .gitignore 필수 항목 등록 확인 (.kanban 기준)
    local gitignore_entries=(".workflow/" ".claude/" ".claude.env" ".claude.env*" ".kanban/" "CLAUDE.md" "__pycache__/" ".temp/" ".temp/*" "temp/" ".vscode/" ".dashboard/")
    local gitignore_ok=true
    for entry in "${gitignore_entries[@]}"; do
        if ! grep -qxF "$entry" ".gitignore" 2>/dev/null; then
            print_error ".gitignore에 미등록: $entry"
            gitignore_ok=false
            failed=$((failed + 1))
        fi
    done
    if [ "$gitignore_ok" = true ]; then
        print_success ".gitignore 필수 항목 모두 등록 확인"
    fi

    # 결과 요약
    echo ""
    if [ "$failed" -eq 0 ]; then
        printf '%s  ========================================%s\n' "${GREEN}" "${NC}"
        printf '%s  모든 검증 항목을 통과했습니다!%s\n' "${GREEN}" "${NC}"
        printf '%s  ========================================%s\n' "${GREEN}" "${NC}"
    else
        printf '%s  ========================================%s\n' "${YELLOW}" "${NC}"
        printf '%s  경고: %s개 검증 항목에서 문제가 발견되었습니다%s\n' "${YELLOW}" "${failed}" "${NC}"
        printf '%s  ========================================%s\n' "${YELLOW}" "${NC}"
    fi
}

# ==============================================================================
# main
# ==============================================================================
main() {
    trap 'print_error "초기화가 실패했습니다. 위의 에러 메시지를 확인해 주세요."' EXIT

    echo ""
    printf '%s=================================================%s\n' "${GREEN}" "${NC}"
    printf '%s  Claude Code 워크플로우 환경 초기화%s\n' "${GREEN}" "${NC}"
    printf '%s=================================================%s\n' "${GREEN}" "${NC}"

    # 사전 의존성 확인
    if ! command -v git &>/dev/null; then
        print_error "git이 설치되어 있지 않습니다. git을 먼저 설치해 주세요."
        exit 1
    fi

    if ! command -v curl &>/dev/null; then
        print_error "curl이 설치되어 있지 않습니다. curl을 먼저 설치해 주세요."
        exit 1
    fi

    print_success "사전 의존성 확인 완료 (git, curl)"

    # Step 0~11 순차 실행
    detect_os
    install_claude_code
    install_dependencies
    clone_claude_directory
    create_directories_and_files
    setup_settings_json
    generate_claude_env
    migrate_legacy_prompt
    setup_shell_aliases
    update_gitignore
    verify_installation

    # 정상 종료 직전 EXIT trap 해제
    trap - EXIT

    detect_shell_rc
    echo ""
    printf '%s=================================================%s\n' "${GREEN}" "${NC}"
    printf '%s  초기화가 완료되었습니다!%s\n' "${GREEN}" "${NC}"
    printf '%s  새 터미널을 열거나 '\''source %s'\''를 실행하세요%s\n' "${GREEN}" "${DETECTED_SHELL_RC}" "${NC}"
    printf '%s=================================================%s\n' "${GREEN}" "${NC}"
    echo ""
}

main "$@"
