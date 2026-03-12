#!/bin/bash
set -euo pipefail

# ==============================================================================
# init-claude-workflow.sh
# Claude Code 워크플로우 환경 자동 초기화 스크립트
# 지원: Ubuntu 20.04+, macOS 13.0+
# 의존성: git, curl, python3, tmux
# ==============================================================================

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
# python3 및 tmux 자동 설치
# ==============================================================================
install_dependencies() {
    print_step "2" "의존성 설치 확인 (python3, tmux)"

    local missing_deps=()

    if ! command -v python3 &>/dev/null; then
        missing_deps+=("python3")
    fi

    if ! command -v tmux &>/dev/null; then
        missing_deps+=("tmux")
    fi

    if [ "${#missing_deps[@]}" -eq 0 ]; then
        print_success "의존성 이미 설치됨 (python3, tmux)"
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
            if ! sudo apt-get install -y "${missing_deps[@]}"; then
                print_error "패키지 설치 실패: ${missing_deps[*]}"
                return 1
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

    # .claude.aliases 파일 생성
    cat > "$aliases_file" << 'ALIASES_EOF'
# 이 파일은 init-claude-workflow.sh가 관리합니다. 수동 편집 내용은 스크립트 재실행 시 유실됩니다.
# Claude Code workflow aliases
export PATH="$HOME/.local/bin:$PATH"

alias claude='~/.local/bin/claude'

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
    local dirs=(".kanban" ".kanban/done" ".uploads" ".workflow/.history" ".workflow/.temp")
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
# ==============================================================================
# .claude.env — Claude Code 워크플로우 환경 변수
# 이 파일은 init-claude-workflow.sh가 생성합니다.
# 민감한 정보가 포함될 수 있으므로 .gitignore에 등록하세요.
# ==============================================================================

# === Slack Integration ===
# Slack Bot Token (Slack 알림 기능 사용 시 입력)
CLAUDE_CODE_SLACK_BOT_TOKEN=
# Slack Channel ID (알림을 받을 채널 ID)
CLAUDE_CODE_SLACK_CHANNEL_ID=

# === Git Configuration ===
# Git 커밋 시 사용할 사용자 이름
CLAUDE_CODE_GIT_USER_NAME=
# Git 커밋 시 사용할 이메일 주소
CLAUDE_CODE_GIT_USER_EMAIL=

# === Hook Flags (ON/OFF) ===
# 위험 명령어 실행 가드 (dangerous_command_guard.py)
HOOK_DANGEROUS_COMMAND=ON
# Hook 스크립트 자체 보호 가드 (hooks_self_guard.py)
HOOK_HOOKS_SELF_PROTECT=ON
# 칸반 현재 상태 가드 (kanban_current_guard.py)
HOOK_KANBAN_CURRENT=ON
# Slack 승인 요청 Hook (pre-tool-use.py) — 기본값 OFF
HOOK_SLACK_ASK=OFF
# 사용량 트래커 (subagent-stop.py)
HOOK_USAGE_TRACKER=ON
# 카탈로그 동기화 (post-tool-use.py)
HOOK_CATALOG_SYNC=ON

# === Workflow Settings ===
# .workflow/ 디렉터리 내 워크플로우 보관 개수 (초과 시 오래된 것부터 정리)
CLAUDE_WORKFLOW_KEEP_COUNT=10
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
        ".uploads/"
        ".kanban/"
        "CLAUDE.md"
        "__pycache__/"
        ".temp/"
        ".temp/*"
        "temp/"
        ".vscode/"
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
}

# ==============================================================================
# Step 9: 설치 검증
# ==============================================================================
verify_installation() {
    print_step "9" "설치 검증"

    local failed=0

    # (a) python3 실행 가능 여부
    if command -v python3 &>/dev/null; then
        print_success "python3 실행 가능 ($(python3 --version 2>&1))"
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
    local gitignore_entries=(".workflow/" ".claude/" ".claude.env" ".claude.env*" ".uploads/" ".kanban/" "CLAUDE.md" "__pycache__/" ".temp/" ".temp/*" "temp/" ".vscode/")
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
