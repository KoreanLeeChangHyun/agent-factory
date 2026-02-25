#!/bin/bash
set -euo pipefail

# ==============================================================================
# init-claude-workflow.sh
# Claude Code 워크플로우 환경 자동 초기화 스크립트
# 지원: Ubuntu 20.04+, macOS 13.0+
# 의존성: git, curl
# ==============================================================================

# --- 색상 변수 ---
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    YELLOW='\033[0;33m'
    NC='\033[0m' # No Color
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
# Step 1: Claude Code 설치
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
# Step 2: 쉘 aliases 설정
# ==============================================================================
setup_shell_aliases() {
    print_step "2" "쉘 aliases 설정"

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
alias cc='claude --dangerously-skip-permissions "/init:workflow"'
alias ccc='claude --dangerously-skip-permissions --continue'
alias ccv='claude --dangerously-skip-permissions'
alias step-start='bash .claude/scripts/banner/step_start_banner.sh'
alias step-end='bash .claude/scripts/banner/step_end_banner.sh'
alias step-change='bash .claude/scripts/banner/step_change_banner.sh'
alias step-update='.claude/scripts/state/update_state.py'
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
# Step 3: 디렉터리 및 파일 생성
# ==============================================================================
create_directories_and_files() {
    print_step "3" "디렉터리 및 파일 생성"

    # 디렉터리 생성
    local dirs=(".prompt" ".uploads" ".workflow/.history")
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
        ".prompt/error.txt"
        ".prompt/history.md"
        ".prompt/memo.txt"
        ".prompt/prompt.txt"
        ".prompt/querys.txt"
        ".prompt/usage.md"
        ".claude.env"
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

    # registry.json은 {} 초기값으로 생성
    if [ ! -f ".workflow/registry.json" ]; then
        echo '{}' > ".workflow/registry.json"
        print_success "파일 생성: .workflow/registry.json (초기값: {})"
    else
        print_info "파일 이미 존재: .workflow/registry.json"
    fi
}

# ==============================================================================
# Step 4: .gitignore 업데이트
# ==============================================================================
update_gitignore() {
    print_step "4" ".gitignore 업데이트"

    # .gitignore 파일 존재 확인
    if [ ! -f ".gitignore" ]; then
        touch ".gitignore"
        print_success ".gitignore 파일 생성"
    fi

    local entries=(
        ".workflow/"
        ".claude.env*"
        ".uploads/"
        ".prompt/"
        "CLAUDE.md"
        "__pycache__/"
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
# Step 5: .claude 디렉터리 클론
# ==============================================================================
clone_claude_directory() {
    print_step "5" ".claude 디렉터리 클론 (원격 저장소)"

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
# Step 6: 설치 검증
# ==============================================================================
verify_installation() {
    print_step "6" "설치 검증"

    local failed=0

    # 1. claude 명령어 실행 가능 여부
    if command -v claude &>/dev/null; then
        print_success "claude 명령어 실행 가능"
    else
        print_error "claude 명령어를 찾을 수 없습니다"
        failed=$((failed + 1))
    fi

    # 2. 필수 디렉터리 존재 여부
    local required_dirs=(".claude" ".prompt" ".uploads" ".workflow")
    local dirs_ok=true
    for dir in "${required_dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            print_error "필수 디렉터리 없음: $dir"
            dirs_ok=false
            failed=$((failed + 1))
        fi
    done
    if [ "$dirs_ok" = true ]; then
        print_success "필수 디렉터리 모두 존재 (${required_dirs[*]})"
    fi

    # 3. aliases 파일 존재 및 source 라인 등록 여부
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

    # 4. .gitignore 등록 여부
    local gitignore_entries=(".workflow/" ".claude.env*" ".uploads/" ".prompt/" "CLAUDE.md" "__pycache__/")
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

    # Step 1~6 순차 실행
    install_claude_code
    setup_shell_aliases
    create_directories_and_files
    update_gitignore
    clone_claude_directory
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
