#!/bin/bash
set -euo pipefail
# build.sh — Claude Code 워크플로우 환경 자동 초기화 스크립트
# 지원: Ubuntu 20.04+, macOS 13.0+ | 의존성: git, curl, python3, tmux, gh

# --- 상수 로드 ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULTS_CONF="${SCRIPT_DIR}/init/defaults.conf"
if [ ! -f "$DEFAULTS_CONF" ]; then
    echo "ERROR: defaults.conf not found: $DEFAULTS_CONF" >&2
    exit 1
fi
# shellcheck source=.claude.workflow/init/defaults.conf
source "$DEFAULTS_CONF"

# --- 색상 변수 ---
if [ -t 1 ]; then
    GREEN=$'\033[0;32m'; RED=$'\033[0;31m'; YELLOW=$'\033[0;33m'; NC=$'\033[0m'
else
    GREEN=""; RED=""; YELLOW=""; NC=""
fi

# --- 공통 출력 함수 ---
print_success() { printf '%s  ✓ %s%s\n' "${GREEN}"  "$1" "${NC}"; }
print_error()   { printf '%s  ✗ %s%s\n' "${RED}"    "$1" "${NC}"; }
print_warning() { printf '%s  ⚠ %s%s\n' "${YELLOW}" "$1" "${NC}"; }
print_info()    { printf '%s  → %s%s\n' "${YELLOW}"  "$1" "${NC}"; }
print_step()    { printf '\n%s[Step %s]%s %s\n' "${GREEN}" "$1" "${NC}" "$2"; }

# --- 쉘 판별 헬퍼 ---
# $SHELL은 로그인 쉘을 반환합니다. 이 함수는 로그인 쉘 기준으로 설정 파일 경로를 판별합니다.
detect_shell_rc() {
    local _shell_name
    _shell_name="$(basename "$SHELL")"
    case "$_shell_name" in
        zsh)  DETECTED_SHELL_NAME="zsh";  DETECTED_SHELL_RC="$HOME/.zshrc"  ;;
        bash) DETECTED_SHELL_NAME="bash"; DETECTED_SHELL_RC="$HOME/.bashrc" ;;
        *)    DETECTED_SHELL_NAME="$_shell_name"; DETECTED_SHELL_RC="$HOME/.bashrc" ;;
    esac
}

# --- 템플릿 검증 ---
validate_templates() {
    local missing=()
    for tmpl in "$TMPL_SETTINGS" "$TMPL_CLAUDE_ENV" "$TMPL_CLAUDE_ALIASES"; do
        [ ! -f "$tmpl" ] && missing+=("$tmpl")
    done
    if [ "${#missing[@]}" -gt 0 ]; then
        print_error "필수 템플릿 파일 부재: ${missing[*]}"
        print_info "build.sh 실행 전 .claude.workflow/init/templates/ 디렉터리를 확인하세요."
        exit 1
    fi
}

# --- 명령어 검증 헬퍼 ---
_verify_command() {
    local cmd="$1" label="$2"
    if command -v "$cmd" &>/dev/null; then
        print_success "$label 실행 가능 ($("$cmd" --version 2>/dev/null | head -1 || echo 'version unknown'))"
    else
        print_error "$label 명령어를 찾을 수 없습니다"; return 1
    fi
}

# --- OS 감지 및 버전 검증 ---
detect_os() {
    local os_type
    os_type="$(uname -s)"
    case "$os_type" in
        Linux)
            DETECTED_OS="linux"
            [ ! -f /etc/os-release ] && { print_error "지원되지 않는 Linux 배포판입니다. /etc/os-release 파일이 없습니다."; exit 1; }
            # shellcheck source=/dev/null
            . /etc/os-release
            local version_id="${VERSION_ID:-0}"
            local major_version
            major_version="$(echo "$version_id" | cut -d. -f1)"
            if [ "$major_version" -lt 20 ] 2>/dev/null; then
                print_error "Ubuntu 20.04 이상이 필요합니다. 현재 버전: $version_id"; exit 1
            fi
            print_success "OS 감지: Linux (Ubuntu $version_id)"
            ;;
        Darwin)
            DETECTED_OS="macos"
            local macos_version macos_major
            macos_version="$(sw_vers -productVersion 2>/dev/null || echo '0.0')"
            macos_major="$(echo "$macos_version" | cut -d. -f1)"
            if [ "$macos_major" -lt 13 ] 2>/dev/null; then
                print_error "macOS 13.0 (Ventura) 이상이 필요합니다. 현재 버전: $macos_version"; exit 1
            fi
            print_success "OS 감지: macOS ($macos_version)"
            ;;
        *) print_error "지원되지 않는 OS입니다: $os_type (Ubuntu 20.04+ 또는 macOS 13.0+ 필요)"; exit 1 ;;
    esac
}

# --- Python 최소 버전 검증 ---
check_python_version() {
    local current_version
    current_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    if python3 -c "import sys; sys.exit(0 if (sys.version_info.major, sys.version_info.minor) >= ($REQUIRED_PYTHON_MAJOR, $REQUIRED_PYTHON_MINOR) else 1)" 2>/dev/null; then
        return 0
    fi
    print_error "Python 버전 미달: 현재 $current_version, 최소 요구 ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
    print_info "Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR} 이상으로 업그레이드하세요:"
    case "${DETECTED_OS:-linux}" in
        macos) print_info "  brew install python@${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}" ;;
        linux)
            print_info "  sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt-get update"
            print_info "  sudo apt-get install python${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
            ;;
        *) print_info "  https://www.python.org/downloads/ 에서 Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}+ 를 설치하세요" ;;
    esac
    exit 1
}

# --- gh CLI APT 저장소 등록 (Linux 전용) ---
_register_gh_apt_repo() {
    print_info "GitHub CLI 공식 APT 저장소를 등록합니다..."
    if ! command -v curl &>/dev/null; then
        print_error "curl이 없어 gh APT 저장소 등록에 실패했습니다. curl을 먼저 설치하세요."; return 1
    fi
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
            | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg 2>/dev/null \
    && sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
            | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && sudo apt-get update -qq
}

# --- python3 및 tmux 자동 설치 ---
install_dependencies() {
    print_step "2" "의존성 설치 확인 (python3, tmux, gh)"
    local missing_deps=()
    if ! command -v python3 &>/dev/null; then missing_deps+=("python3"); else check_python_version; fi
    command -v tmux &>/dev/null || missing_deps+=("tmux")
    command -v gh   &>/dev/null || missing_deps+=("gh")
    if [ "${#missing_deps[@]}" -eq 0 ]; then
        print_success "의존성 이미 설치됨 (python3, tmux, gh)"; return 0
    fi
    print_info "미설치 의존성: ${missing_deps[*]}"
    case "${DETECTED_OS:-linux}" in
        linux)
            sudo apt-get update -qq || { print_error "apt-get update 실패"; return 1; }
            if printf '%s\n' "${missing_deps[@]}" | grep -qx 'gh'; then
                if _register_gh_apt_repo; then
                    print_success "GitHub CLI APT 저장소 등록 완료"
                else
                    print_error "GitHub CLI APT 저장소 등록 실패. gh를 수동으로 설치하세요: https://cli.github.com"
                    local filtered=()
                    for dep in "${missing_deps[@]}"; do [ -n "$dep" ] && [ "$dep" != "gh" ] && filtered+=("$dep"); done
                    missing_deps=("${filtered[@]}")
                fi
            fi
            [ "${#missing_deps[@]}" -gt 0 ] && { sudo apt-get install -y "${missing_deps[@]}" || { print_error "패키지 설치 실패: ${missing_deps[*]}"; return 1; }; }
            ;;
        macos)
            command -v brew &>/dev/null || { print_error "Homebrew가 설치되어 있지 않습니다. https://brew.sh 에서 먼저 설치해 주세요."; return 1; }
            brew install "${missing_deps[@]}" || { print_error "brew install 실패: ${missing_deps[*]}"; return 1; }
            ;;
        *) print_error "알 수 없는 OS에서는 자동 설치를 지원하지 않습니다."; return 1 ;;
    esac
    local still_missing=()
    for dep in "${missing_deps[@]}"; do command -v "$dep" &>/dev/null || still_missing+=("$dep"); done
    if [ "${#still_missing[@]}" -gt 0 ]; then
        print_error "설치 후에도 다음 의존성을 찾을 수 없습니다: ${still_missing[*]}"; return 1
    fi
    print_success "의존성 설치 완료 (${missing_deps[*]})"
}

# --- Step 1: Claude Code 설치 ---
install_claude_code() {
    print_step "1" "Claude Code 설치 확인"
    if command -v claude &>/dev/null; then
        print_success "Claude Code가 이미 설치되어 있습니다 ($(claude --version 2>/dev/null || echo 'version unknown'))"
        return 0
    fi
    print_info "Claude Code가 설치되어 있지 않습니다. 설치를 시작합니다..."
    command -v curl &>/dev/null || { print_error "curl이 설치되어 있지 않습니다. curl을 먼저 설치해 주세요."; return 1; }
    local install_script
    install_script="$(mktemp)"
    if ! curl -fsSL -o "$install_script" https://claude.ai/install.sh; then
        print_error "Claude Code 설치 스크립트 다운로드에 실패했습니다"
        rm -f "$install_script"; return 1
    fi
    if bash "$install_script"; then
        print_success "Claude Code 설치 완료"
    else
        print_error "Claude Code 설치에 실패했습니다"
        rm -f "$install_script"; return 1
    fi
    rm -f "$install_script"
}

# --- Step 7: 쉘 aliases 설정 ---
setup_shell_aliases() {
    print_step "7" "쉘 aliases 설정"
    local aliases_file="$HOME/.claude.aliases"
    detect_shell_rc
    local shell_name="$DETECTED_SHELL_NAME" shell_rc="$DETECTED_SHELL_RC"
    if [ "$shell_name" != "zsh" ] && [ "$shell_name" != "bash" ]; then
        print_info "감지된 쉘: $shell_name (bash 설정으로 대체합니다)"
    fi
    # .claude.aliases 파일이 이미 존재하면 스킵 (사용자 설정 보존)
    if [ -f "$aliases_file" ]; then
        print_info ".claude.aliases 파일이 이미 존재합니다. 기존 내용을 유지합니다. ($aliases_file)"
    else
        cp "$TMPL_CLAUDE_ALIASES" "$aliases_file"
        print_success ".claude.aliases 파일 생성 완료 ($aliases_file)"
    fi
    local source_line="# Claude Code workflow aliases"
    local source_cmd="[ -f \"$aliases_file\" ] && source \"$aliases_file\""
    [ ! -f "$shell_rc" ] && touch "$shell_rc"
    if grep -q ".claude.aliases" "$shell_rc" 2>/dev/null; then
        print_success "쉘 설정 파일에 source 라인이 이미 등록되어 있습니다 ($shell_rc)"
    else
        { echo ""; echo "$source_line"; echo "$source_cmd"; } >> "$shell_rc"
        print_success "쉘 설정 파일에 source 라인 추가 완료 ($shell_rc)"
    fi
}

# --- Step 4: 디렉터리 및 파일 생성 ---
create_directories_and_files() {
    print_step "4" "디렉터리 및 파일 생성"
    for dir in "${INIT_DIRS[@]}"; do
        if [ ! -d "$dir" ]; then mkdir -p "$dir"; print_success "디렉터리 생성: $dir"
        else print_info "디렉터리 이미 존재: $dir"; fi
    done
    for file in "${INIT_FILES[@]}"; do
        if [ ! -f "$file" ]; then touch "$file"; print_success "파일 생성: $file"
        else print_info "파일 이미 존재: $file"; fi
    done
    local skill_state_file=".claude/skills/skill-state.json"
    if [ -f "$skill_state_file" ]; then
        print_info "파일 이미 존재: $skill_state_file"
    elif [ -d ".claude/skills" ]; then
        python3 -c "import json; f=open('$skill_state_file','w'); json.dump({'version':1,'skills':{}},f,indent=2); f.write('\n'); f.close()"
        print_success "파일 생성: $skill_state_file"
    else
        print_info ".claude/skills/ 디렉터리가 없습니다. skill-state.json 생성을 스킵합니다."
    fi
}

# --- Step 4.5: .claude/settings.json 생성 ---
setup_settings_json() {
    print_step "4.5" ".claude/settings.json 생성"
    local settings_file=".claude/settings.json"
    [ -f "$settings_file" ] && { print_info ".claude/settings.json 파일이 이미 존재합니다. 기존 내용을 유지합니다."; return 0; }
    [ ! -d ".claude" ] && { print_info ".claude/ 디렉터리가 없습니다. settings.json 생성을 스킵합니다."; return 0; }
    cp "$TMPL_SETTINGS" "$settings_file"
    if python3 -c 'import json, sys; json.load(open(sys.argv[1]))' "$settings_file" 2>/dev/null; then
        print_success ".claude/settings.json 생성 완료 (JSON 유효성 검증 통과)"
    else
        print_error ".claude/settings.json JSON 유효성 검증 실패. 파일을 확인하세요."; return 1
    fi
}

# --- Step 5: .claude.workflow/.settings 템플릿 생성 ---
generate_claude_settings() {
    print_step "5" ".claude.workflow/.settings 템플릿 생성"
    local settings_file=".claude.workflow/.settings"
    local env_file=".claude.workflow/.env"
    # .settings가 이미 존재하면 스킵
    if [ -f "$settings_file" ]; then
        print_info ".claude.workflow/.settings 파일이 이미 존재합니다. 기존 내용을 유지합니다."; return 0
    fi
    # .settings가 없고 .env가 있으면 .env를 복사하여 .settings 생성
    if [ -f "$env_file" ]; then
        cp "$env_file" "$settings_file"
        print_success ".claude.workflow/.settings 생성 완료 (.env에서 복사) ($settings_file)"
        return 0
    fi
    # 둘 다 없으면 템플릿에서 생성
    cp "$TMPL_CLAUDE_ENV" "$settings_file"
    print_success ".claude.workflow/.settings 템플릿 생성 완료 ($settings_file)"
}

# --- 마이그레이션 플래그 (Phase 3 검증용) ---
_MIGRATION_PERFORMED=false

# --- Step 2.5: 레거시 루트 디렉터리 마이그레이션 ---
# v1 구조의 .kanban/, .dashboard/, .workflow/ 를 .claude.workflow/ 하위로 이동
migrate_legacy_directories() {
    print_step "2.5" "레거시 루트 디렉터리 마이그레이션"
    local legacy_dirs=(".kanban" ".dashboard" ".workflow")
    local target_dirs=(".claude.workflow/kanban" ".claude.workflow/dashboard" ".claude.workflow/workflow")
    # 구 디렉터리 존재 여부 확인
    local found=false
    for dir in "${legacy_dirs[@]}"; do
        [ -d "$dir" ] && found=true
    done
    if [ "$found" = false ]; then
        print_info "레거시 루트 디렉터리 없음 (.kanban/, .dashboard/, .workflow/). 마이그레이션 스킵"
        return 0
    fi
    _MIGRATION_PERFORMED=true
    print_info "레거시 루트 디렉터리가 감지되었습니다. 마이그레이션을 시작합니다..."
    local i
    for i in "${!legacy_dirs[@]}"; do
        local src="${legacy_dirs[$i]}"
        local dst="${target_dirs[$i]}"
        if [ ! -d "$src" ]; then
            print_info "$src 디렉터리 없음, 스킵"
            continue
        fi
        [ ! -d "$dst" ] && mkdir -p "$dst"
        # cp -rn (no-clobber): 기존 파일 우선 보존
        if [ "${DETECTED_OS:-linux}" = "macos" ]; then
            cp -Rn "$src"/ "$dst"/ 2>/dev/null || true
        else
            cp -rn "$src"/ "$dst"/ 2>/dev/null || true
        fi
        # 원본 삭제
        if rm -rf "$src"; then
            print_success "$src → $dst 마이그레이션 완료"
        else
            print_error "$src 삭제 실패"
        fi
    done
    print_success "레거시 루트 디렉터리 마이그레이션 완료"
}

# --- Step 3.5: 레거시 .claude 경로 정리 ---
# v1의 .claude/scripts/, .claude/hooks/ 삭제 (settings.json 보존)
cleanup_legacy_claude_paths() {
    print_step "3.5" "레거시 .claude 경로 정리"
    local has_legacy=false
    [ -d ".claude/scripts" ] && has_legacy=true
    [ -d ".claude/hooks" ]   && has_legacy=true
    if [ "$has_legacy" = false ]; then
        print_info "레거시 .claude/scripts/, .claude/hooks/ 없음. 정리 스킵"
        return 0
    fi
    _MIGRATION_PERFORMED=true
    # settings 백업
    local tmp_backup
    tmp_backup="$(mktemp -d)"
    for sf in "settings.json" "settings.local.json"; do
        [ -f ".claude/$sf" ] && cp ".claude/$sf" "$tmp_backup/$sf"
    done
    # 구 경로 삭제
    if [ -d ".claude/scripts" ]; then
        rm -rf ".claude/scripts"
        print_success ".claude/scripts/ 삭제 완료"
    fi
    if [ -d ".claude/hooks" ]; then
        rm -rf ".claude/hooks"
        print_success ".claude/hooks/ 삭제 완료"
    fi
    # settings 복원
    for sf in "settings.json" "settings.local.json"; do
        if [ -f "$tmp_backup/$sf" ]; then
            cp "$tmp_backup/$sf" ".claude/$sf"
            print_success ".claude/$sf 복원 완료"
        fi
    done
    rm -rf "$tmp_backup"
    print_success "레거시 .claude 경로 정리 완료"
}

# --- Step 3.6: 레거시 alias 경로 갱신 ---
# ~/.claude.aliases 내 구 경로(.claude/scripts/, .claude/hooks/)를 신 경로로 치환
update_legacy_aliases() {
    print_step "3.6" "레거시 alias 경로 갱신"
    local aliases_file="$HOME/.claude.aliases"
    if [ ! -f "$aliases_file" ]; then
        print_info "$aliases_file 파일 없음 (신규 설치). 갱신 스킵"
        return 0
    fi
    local changed=0
    # .claude/scripts/ → .claude.workflow/scripts/
    if grep -q '\.claude/scripts/' "$aliases_file" 2>/dev/null; then
        sed -i.mig-bak 's|\.claude/scripts/|.claude.workflow/scripts/|g' "$aliases_file"
        changed=$((changed + 1))
        _MIGRATION_PERFORMED=true
    fi
    # .claude/hooks/ → .claude.workflow/hooks/
    if grep -q '\.claude/hooks/' "$aliases_file" 2>/dev/null; then
        sed -i.mig-bak 's|\.claude/hooks/|.claude.workflow/hooks/|g' "$aliases_file"
        changed=$((changed + 1))
        _MIGRATION_PERFORMED=true
    fi
    # macOS sed -i 백업 파일 정리
    rm -f "${aliases_file}.mig-bak"
    if [ "$changed" -gt 0 ]; then
        print_success "alias 경로 치환 완료 (${changed}개 패턴)"
    else
        print_info "레거시 경로 패턴 없음. 갱신 불필요"
    fi
}

# --- Step 6: 레거시 .prompt/ 마이그레이션 ---
migrate_legacy_prompt() {
    print_step "6" "레거시 .prompt/ 마이그레이션"
    local prompt_dir=".prompt" kanban_dir=".claude.workflow/kanban"
    if [ ! -d "$prompt_dir" ]; then
        print_info "레거시 .prompt/ 디렉터리 없음, 마이그레이션 스킵"; return 0
    fi
    print_info "레거시 .prompt/ 디렉터리 발견. .claude.workflow/kanban/으로 마이그레이션을 시작합니다..."
    [ ! -d "$kanban_dir" ] && { mkdir -p "$kanban_dir"; print_success ".claude.workflow/kanban/ 디렉터리 생성"; }
    if [ -f "$prompt_dir/prompt.txt" ] && [ -s "$prompt_dir/prompt.txt" ]; then
        { echo ""; echo "# === 마이그레이션된 .prompt/prompt.txt 내용 ($(date +%Y%m%d)) ==="; cat "$prompt_dir/prompt.txt"; } >> "$kanban_dir/.memo.txt"
        print_success ".prompt/prompt.txt 내용을 .claude.workflow/kanban/.memo.txt에 보존했습니다"
    fi
    local copied=0
    for txt_file in "$prompt_dir"/*.txt; do
        if [ -f "$txt_file" ]; then
            local filename
            filename="$(basename "$txt_file")"
            if cp "$txt_file" "$kanban_dir/$filename"; then
                print_success "복사: $txt_file → $kanban_dir/$filename"; copied=$((copied + 1))
            else
                print_error "복사 실패: $txt_file"
            fi
        fi
    done
    if [ "$copied" -eq 0 ]; then print_info ".prompt/ 디렉터리에 .txt 파일이 없습니다"
    else print_success "${copied}개 파일을 .claude.workflow/kanban/으로 복사 완료"; fi
    local backup_name=".prompt.bak.$(date +%Y%m%d)"
    if mv "$prompt_dir" "$backup_name"; then print_success ".prompt/ 디렉터리를 ${backup_name}으로 백업 완료"
    else print_error ".prompt/ 디렉터리 백업 이름 변경에 실패했습니다"; return 1; fi
}

# --- Step 8: .gitignore 업데이트 ---
update_gitignore() {
    print_step "8" ".gitignore 업데이트"
    [ ! -f ".gitignore" ] && { touch ".gitignore"; print_success ".gitignore 파일 생성"; }
    local added=0
    for entry in "${GITIGNORE_ENTRIES[@]}"; do
        if ! grep -qxF "$entry" ".gitignore" 2>/dev/null; then
            echo "$entry" >> ".gitignore"; print_success ".gitignore에 추가: $entry"; added=$((added + 1))
        fi
    done
    if [ "$added" -eq 0 ]; then print_info ".gitignore에 모든 필수 항목이 이미 등록되어 있습니다"
    else print_success ".gitignore에 ${added}개 항목 추가 완료"; fi
}

# --- Step 3: .claude + .claude.workflow 디렉터리 클론 ---
clone_claude_directory() {
    print_step "3" ".claude + .claude.workflow 디렉터리 클론 (원격 저장소)"
    command -v git &>/dev/null || { print_error "git이 설치되어 있지 않습니다"; return 1; }
    local tmp_dir old_trap
    tmp_dir="$(mktemp -d)"
    old_trap="$(trap -p EXIT)"
    trap 'rm -rf "$tmp_dir"' EXIT
    print_info "원격 저장소 클론 중... ($CLAUDE_REPO_URL)"
    if ! git clone --depth 1 "$CLAUDE_REPO_URL" "$tmp_dir/claude-workflow" 2>/dev/null; then
        print_error "원격 저장소 클론에 실패했습니다. 기존 디렉터리를 유지합니다."
        rm -rf "$tmp_dir"; eval "$old_trap"; return 1
    fi
    # .claude 디렉터리 교체
    if [ ! -d "$tmp_dir/claude-workflow/.claude" ]; then
        print_error "클론된 저장소에 .claude 디렉터리가 없습니다."
        rm -rf "$tmp_dir"; eval "$old_trap"; return 1
    fi
    [ -L ".claude" ] && { print_info ".claude가 심볼릭 링크입니다. 제거합니다."; rm -f ".claude"; }
    rm -rf ".claude.new"
    if ! cp -r "$tmp_dir/claude-workflow/.claude" ".claude.new"; then
        print_error ".claude 디렉터리 복사 실패."
        rm -rf ".claude.new" "$tmp_dir"; eval "$old_trap"; return 1
    fi
    rm -rf ".claude"; mv ".claude.new" ".claude"
    print_success ".claude 디렉터리 교체 완료"
    # .claude.workflow 디렉터리 교체 (kanban, workflow, .settings는 보존)
    if [ -d "$tmp_dir/claude-workflow/.claude.workflow" ]; then
        # 사용자 데이터 백업 (kanban, workflow, .settings, .env, .version)
        local preserve_dirs=("kanban" "workflow" "dashboard")
        local preserve_files=(".settings" ".env" ".version" ".board.url" "build.url")
        for pd in "${preserve_dirs[@]}"; do
            [ -d ".claude.workflow/$pd" ] && cp -r ".claude.workflow/$pd" "$tmp_dir/_preserve_$pd"
        done
        for pf in "${preserve_files[@]}"; do
            [ -f ".claude.workflow/$pf" ] && cp ".claude.workflow/$pf" "$tmp_dir/_preserve_$pf"
        done
        # 교체
        rm -rf ".claude.workflow.new"
        cp -r "$tmp_dir/claude-workflow/.claude.workflow" ".claude.workflow.new"
        rm -rf ".claude.workflow"; mv ".claude.workflow.new" ".claude.workflow"
        # 사용자 데이터 복원
        for pd in "${preserve_dirs[@]}"; do
            [ -d "$tmp_dir/_preserve_$pd" ] && { rm -rf ".claude.workflow/$pd"; mv "$tmp_dir/_preserve_$pd" ".claude.workflow/$pd"; }
        done
        for pf in "${preserve_files[@]}"; do
            [ -f "$tmp_dir/_preserve_$pf" ] && mv "$tmp_dir/_preserve_$pf" ".claude.workflow/$pf"
        done
        print_success ".claude.workflow 디렉터리 교체 완료 (사용자 데이터 보존)"
    else
        print_info "클론된 저장소에 .claude.workflow 디렉터리가 없습니다. 스킵합니다."
    fi
    rm -rf "$tmp_dir"; eval "$old_trap"
    print_success "임시 클론 디렉터리 정리 완료"
    find ".claude/" -name '*.sh' -exec chmod +x {} +
    find ".claude.workflow/" -name '*.sh' -exec chmod +x {} + 2>/dev/null
    print_success ".sh 파일 chmod +x 완료"
}

# --- Step 9: 설치 검증 ---
verify_installation() {
    print_step "9" "설치 검증"
    local failed=0
    # (a) python3 버전 검증
    if command -v python3 &>/dev/null; then
        print_success "python3 실행 가능 ($(python3 --version 2>&1))"
        if python3 -c "import sys; sys.exit(0 if (sys.version_info.major, sys.version_info.minor) >= ($REQUIRED_PYTHON_MAJOR, $REQUIRED_PYTHON_MINOR) else 1)" 2>/dev/null; then
            print_success "python3 버전 검증 PASS (>= ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR})"
        else
            local current_ver
            current_ver="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
            print_error "python3 버전 검증 FAIL: 현재 ${current_ver}, 최소 요구 ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
            failed=$((failed + 1))
        fi
    else
        print_error "python3 명령어를 찾을 수 없습니다"; failed=$((failed + 1))
    fi
    # (b) tmux / gh / claude 검증
    _verify_command "tmux" "tmux" || failed=$((failed + 1))
    _verify_command "gh"   "gh CLI" || failed=$((failed + 1))
    if command -v claude &>/dev/null; then print_success "claude 명령어 실행 가능"
    else print_error "claude 명령어를 찾을 수 없습니다"; failed=$((failed + 1)); fi
    # (d) .claude.workflow/kanban/, .claude.workflow/kanban/{open,progress,review,done}/ 디렉터리 존재
    local kanban_ok=true
    for dir in ".claude.workflow/kanban" ".claude.workflow/kanban/open" ".claude.workflow/kanban/progress" ".claude.workflow/kanban/review" ".claude.workflow/kanban/done"; do
        if [ ! -d "$dir" ]; then
            print_error "필수 디렉터리 없음: $dir"; kanban_ok=false; failed=$((failed + 1))
        fi
    done
    [ "$kanban_ok" = true ] && print_success ".claude.workflow/kanban/, .claude.workflow/kanban/{open,progress,review,done}/ 디렉터리 존재 확인"
    # (e) .claude.workflow/.settings 또는 .claude.workflow/.env 파일 존재
    if [ -f ".claude.workflow/.settings" ]; then
        print_success ".claude.workflow/.settings 파일 존재 확인"
    elif [ -f ".claude.workflow/.env" ]; then
        print_success ".claude.workflow/.env 파일 존재 확인 (폴백)"
    else
        print_error ".claude.workflow/.settings 및 .claude.workflow/.env 파일이 모두 없습니다"
        failed=$((failed + 1))
    fi
    # (f) .claude/ 디렉터리 존재
    if [ -d ".claude" ]; then print_success ".claude/ 디렉터리 존재 확인"
    else print_error ".claude/ 디렉터리가 없습니다"; failed=$((failed + 1)); fi
    # (g) aliases 파일 존재 및 shell rc에 source 라인 등록
    local aliases_file="$HOME/.claude.aliases"
    detect_shell_rc
    local shell_rc="$DETECTED_SHELL_RC"
    if [ -f "$aliases_file" ] && grep -q ".claude.aliases" "$shell_rc" 2>/dev/null; then
        print_success "aliases 파일 존재 및 쉘 설정 파일에 source 라인 등록 확인"
    else
        [ ! -f "$aliases_file" ] && print_error "aliases 파일이 없습니다: $aliases_file"
        grep -q ".claude.aliases" "$shell_rc" 2>/dev/null || print_error "쉘 설정 파일에 source 라인이 없습니다: $shell_rc"
        failed=$((failed + 1))
    fi
    # (h) .gitignore 필수 항목 등록 확인
    local gitignore_ok=true
    for entry in "${GITIGNORE_ENTRIES[@]}"; do
        if ! grep -qxF "$entry" ".gitignore" 2>/dev/null; then
            print_error ".gitignore에 미등록: $entry"; gitignore_ok=false; failed=$((failed + 1))
        fi
    done
    [ "$gitignore_ok" = true ] && print_success ".gitignore 필수 항목 모두 등록 확인"
    # (i) 마이그레이션 검증 (마이그레이션이 수행된 경우에만)
    if [ "$_MIGRATION_PERFORMED" = true ]; then
        local mig_warn=0
        # 구 루트 디렉터리 잔류 확인
        for legacy_dir in ".kanban" ".dashboard" ".workflow"; do
            if [ -d "$legacy_dir" ]; then
                print_warning "레거시 디렉터리가 남아있습니다: ${legacy_dir}/ (수동 확인 필요)"
                mig_warn=$((mig_warn + 1))
            fi
        done
        # 구 .claude/ 경로 잔류 확인
        for legacy_path in ".claude/scripts" ".claude/hooks"; do
            if [ -d "$legacy_path" ]; then
                print_warning "레거시 경로가 남아있습니다: ${legacy_path}/ (수동 확인 필요)"
                mig_warn=$((mig_warn + 1))
            fi
        done
        # $HOME/.claude.aliases에 구 경로 패턴 잔류 확인
        local aliases_mig_file="$HOME/.claude.aliases"
        if [ -f "$aliases_mig_file" ] && grep -q '\.claude/scripts/' "$aliases_mig_file" 2>/dev/null; then
            print_warning "\$HOME/.claude.aliases에 구 경로 패턴(.claude/scripts/)이 남아있습니다 (수동 확인 필요)"
            mig_warn=$((mig_warn + 1))
        fi
        if [ "$mig_warn" -eq 0 ]; then
            print_success "마이그레이션 검증 완료 — 레거시 경로 잔류 없음"
        fi
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

# --- main ---
main() {
    trap 'print_error "초기화가 실패했습니다. 위의 에러 메시지를 확인해 주세요."' EXIT
    echo ""
    printf '%s=================================================%s\n' "${GREEN}" "${NC}"
    printf '%s  Claude Code 워크플로우 환경 초기화%s\n' "${GREEN}" "${NC}"
    printf '%s=================================================%s\n' "${GREEN}" "${NC}"
    command -v git  &>/dev/null || { print_error "git이 설치되어 있지 않습니다. git을 먼저 설치해 주세요.";  exit 1; }
    command -v curl &>/dev/null || { print_error "curl이 설치되어 있지 않습니다. curl을 먼저 설치해 주세요."; exit 1; }
    print_success "사전 의존성 확인 완료 (git, curl)"
    validate_templates
    detect_os
    install_claude_code
    install_dependencies
    migrate_legacy_directories
    clone_claude_directory
    cleanup_legacy_claude_paths
    update_legacy_aliases
    create_directories_and_files
    setup_settings_json
    generate_claude_settings
    migrate_legacy_prompt
    setup_shell_aliases
    update_gitignore
    verify_installation
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
