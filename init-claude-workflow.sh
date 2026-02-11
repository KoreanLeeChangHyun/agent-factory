#!/bin/bash
# =============================================================================
# init-claude-workflow.sh - Claude Workflow 통합 초기화 스크립트
# =============================================================================
#
# 사용법: ./init-claude-workflow.sh [OPTIONS]
#
# 11단계(Step 0~10) 통합 초기화 스크립트:
#   Step 0:  환경 분석 (OS, 셸, 아키텍처)
#   Step 1:  Claude Code CLI 설치 확인/설치
#   Step 2:  .claude.env 생성
#   Step 3:  필수 도구 확인 (python3, git, rsync)
#   Step 4:  원격 동기화 (.claude/ 디렉토리)
#   Step 5:  프로젝트 디렉토리 구조 생성
#   Step 6:  셸 alias 등록
#   Step 7:  .claude.env 검증
#   Step 8:  .gitignore 패턴 등록
#   Step 9:  StatusLine 설정
#   Step 10: 최종 검증 및 보고
#
# 핵심 원칙:
#   - 멱등성 보장: 재실행해도 동일 결과
#   - 크로스 플랫폼: Linux/macOS 호환
#   - 단계적 폴백: 기존 스크립트 우선, 미존재 시 인라인 폴백
#   - bash 3.2 호환: 연관 배열(declare -A) 사용 금지
# =============================================================================

set -euo pipefail

# =============================================================================
# 버전 및 상수
# =============================================================================

VERSION="1.0.0"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(pwd)"
REMOTE_REPO="https://github.com/KoreanLeeChangHyun/claude-workflow.git"

# =============================================================================
# 컬러 출력 함수
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_step()    { echo -e "${BLUE}[STEP $1]${NC} ${BOLD}$2${NC}"; }
log_info()    { echo -e "  ${CYAN}[INFO]${NC} $1"; }
log_success() { echo -e "  ${GREEN}[OK]${NC} $1"; }
log_warn()    { echo -e "  ${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "  ${RED}[ERROR]${NC} $1"; }
log_skip()    { echo -e "  ${YELLOW}[SKIP]${NC} $1"; }

# =============================================================================
# 진행 상황 추적
# =============================================================================

TOTAL_STEPS=11
CURRENT_STEP=0
RESULTS=()

step_start() {
    CURRENT_STEP=$1
    local desc="$2"
    echo ""
    log_step "$CURRENT_STEP/$((TOTAL_STEPS - 1))" "$desc"
}

step_result() {
    local status="$1"  # OK, WARN, SKIP, FAIL
    local message="$2"
    RESULTS+=("Step $CURRENT_STEP|$status|$message")
}

# =============================================================================
# OS/셸/아키텍처 감지
# =============================================================================

OS_TYPE=""
ARCH=""
SHELL_NAME=""
SHELL_RC=""

detect_platform() {
    case "$(uname -s)" in
        Linux*)   OS_TYPE="linux" ;;
        Darwin*)  OS_TYPE="macos" ;;
        MINGW*|MSYS*|CYGWIN*) OS_TYPE="windows" ;;
        *)        OS_TYPE="unknown" ;;
    esac

    case "$(uname -m)" in
        x86_64|amd64)   ARCH="x64" ;;
        arm64|aarch64)  ARCH="arm64" ;;
        *)              ARCH="unknown" ;;
    esac

    SHELL_NAME=$(basename "${SHELL:-/bin/bash}")
    case "$SHELL_NAME" in
        zsh)  SHELL_RC="$HOME/.zshrc" ;;
        bash)
            if [ -f "$HOME/.bashrc" ]; then
                SHELL_RC="$HOME/.bashrc"
            else
                SHELL_RC="$HOME/.bash_profile"
            fi
            ;;
        *)
            if [ -f "$HOME/.zshrc" ]; then
                SHELL_RC="$HOME/.zshrc"
            elif [ -f "$HOME/.bashrc" ]; then
                SHELL_RC="$HOME/.bashrc"
            else
                SHELL_RC="$HOME/.zshrc"
            fi
            ;;
    esac
}

# =============================================================================
# sed -i 크로스 플랫폼 래퍼
# =============================================================================

portable_sed_i() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "$@"
    else
        sed -i "$@"
    fi
}

# =============================================================================
# 임시 파일 관리
# =============================================================================

TEMP_DIR=""

cleanup() {
    if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
    fi
}
trap cleanup EXIT

# =============================================================================
# retry 유틸리티 (네트워크 작업 재시도)
# =============================================================================

retry() {
    local max_attempts=$1
    local delay=$2
    shift 2
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if "$@"; then
            return 0
        fi
        if [ $attempt -lt $max_attempts ]; then
            log_warn "Attempt $attempt/$max_attempts failed, retrying in ${delay}s..."
            sleep "$delay"
        fi
        attempt=$((attempt + 1))
    done
    return 1
}

# =============================================================================
# 커맨드라인 옵션 파싱
# =============================================================================

DRY_RUN=false
SKIP_SYNC=false
SKIP_INSTALL=false
FORCE=false
VERBOSE=false

usage() {
    cat << USAGE_EOF
Usage: init-claude-workflow.sh [OPTIONS]

Claude Workflow 통합 초기화 스크립트 v${VERSION}
환경 분석 -> CLI 설치 -> 동기화 -> alias 등록 -> 검증 순서로 실행합니다.

Options:
  --dry-run       변경 없이 실행 계획만 출력
  --skip-sync     원격 동기화 건너뜀 (오프라인 모드)
  --skip-install  Claude Code CLI 설치 건너뜀
  --force         이미 존재하는 설정도 재설정
  --verbose       상세 출력
  --version       스크립트 버전 출력
  --help, -h      도움말 출력

Examples:
  ./init-claude-workflow.sh                  # 전체 초기화
  ./init-claude-workflow.sh --dry-run        # 변경 없이 계획만 출력
  ./init-claude-workflow.sh --skip-sync      # 동기화 없이 로컬만 설정
  ./init-claude-workflow.sh --force          # 기존 설정 덮어쓰기
USAGE_EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)      DRY_RUN=true ;;
            --skip-sync)    SKIP_SYNC=true ;;
            --skip-install) SKIP_INSTALL=true ;;
            --force)        FORCE=true ;;
            --verbose)      VERBOSE=true ;;
            --version)      echo "init-claude-workflow.sh v$VERSION"; exit 0 ;;
            --help|-h)      usage; exit 0 ;;
            *)              log_error "Unknown option: $1"; usage; exit 1 ;;
        esac
        shift
    done
}

# =============================================================================
# Step 0: 환경 분석
# =============================================================================

do_step_0() {
    step_start 0 "Environment Analysis"

    detect_platform

    log_info "OS: $OS_TYPE"
    log_info "Architecture: $ARCH"
    log_info "Shell: $SHELL_NAME"
    log_info "Shell RC: $SHELL_RC"
    log_info "Working Directory: $PROJECT_ROOT"

    if [ "$VERBOSE" = true ]; then
        log_info "OSTYPE: ${OSTYPE:-unknown}"
        log_info "HOME: $HOME"
        log_info "PATH (first 3): $(echo "$PATH" | tr ':' '\n' | head -3 | paste -sd ':' -)"
        log_info "Script Dir: $SCRIPT_DIR"
    fi

    if [ "$OS_TYPE" = "windows" ] || [ "$OS_TYPE" = "unknown" ]; then
        log_warn "Unsupported OS: $OS_TYPE. Some features may not work."
        step_result "WARN" "Unsupported OS: $OS_TYPE"
    else
        step_result "OK" "$OS_TYPE/$ARCH/$SHELL_NAME"
    fi
}

# =============================================================================
# Step 1: Claude Code CLI 설치 확인/설치
# =============================================================================

do_step_1() {
    step_start 1 "Claude Code CLI"

    if [ "$SKIP_INSTALL" = true ]; then
        log_skip "Claude Code CLI installation skipped (--skip-install)"
        step_result "SKIP" "Skipped by option"
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY-RUN] Would check/install Claude Code CLI"
        step_result "SKIP" "Dry-run mode"
        return 0
    fi

    if command -v claude >/dev/null 2>&1; then
        local claude_version
        claude_version=$(claude --version 2>/dev/null || echo "unknown")
        log_success "Already installed: $claude_version"
        step_result "OK" "Already installed ($claude_version)"
        return 0
    fi

    # Claude Code CLI 미설치 - 설치 시도
    if ! command -v curl >/dev/null 2>&1; then
        log_warn "curl not found. Cannot install Claude Code CLI automatically."
        log_warn "Install manually: https://claude.ai/install.sh"
        step_result "WARN" "curl not found, manual install required"
        return 0
    fi

    log_info "Installing Claude Code CLI..."
    local install_output
    if install_output=$(curl -fsSL https://claude.ai/install.sh | bash 2>&1); then
        if [ "$VERBOSE" = true ]; then
            log_info "Install output: $install_output"
        fi
        # PATH 갱신 시도
        export PATH="$HOME/.local/bin:$PATH"
        if command -v claude >/dev/null 2>&1; then
            local installed_version
            installed_version=$(claude --version 2>/dev/null || echo "unknown")
            log_success "Installed: $installed_version"
            step_result "OK" "Installed ($installed_version)"
        else
            log_warn "Installation completed but claude not found in PATH"
            log_warn "Try: export PATH=\"\$HOME/.local/bin:\$PATH\""
            step_result "WARN" "Installed but not in PATH"
        fi
    else
        log_warn "Installation failed (exit code: $?)"
        if [ "$VERBOSE" = true ] && [ -n "${install_output:-}" ]; then
            log_info "Output: $install_output"
        fi
        log_warn "Install manually: curl -fsSL https://claude.ai/install.sh | bash"
        step_result "WARN" "Installation failed"
    fi
}

# =============================================================================
# Step 2: .claude.env 생성
# =============================================================================

do_step_2() {
    step_start 2 ".claude.env Setup"

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY-RUN] Would create .claude.env if not exists"
        step_result "SKIP" "Dry-run mode"
        return 0
    fi

    local env_file="$PROJECT_ROOT/.claude.env"

    # .claude.env는 사용자 비밀정보를 포함하므로 --force 여부와 무관하게 보존
    if [ -f "$env_file" ]; then
        if [ "$FORCE" = true ]; then
            log_info "Preserving existing .claude.env (--force does not overwrite secrets)"
        fi
        log_skip ".claude.env already exists"
        step_result "SKIP" "Already exists"
        return 0
    fi

    cat > "$env_file" << 'ENV_EOF'
# ============================================
# Claude Code Environment Variables
# ============================================
#
# This file is used by Claude Code Hook scripts.
# Format: KEY=value (standard .env syntax)
# ============================================

# ============================================
# [OPTIONAL] API Key (if using API key auth)
# ============================================
# ANTHROPIC_API_KEY=your-api-key-here

# ============================================
# [REQUIRED] Git Configuration
# ============================================
# CLAUDE_CODE_GIT_USER_NAME=your-name
# CLAUDE_CODE_GIT_USER_EMAIL=your-email

# ============================================
# [REQUIRED] SSH Key
# ============================================
# CLAUDE_CODE_SSH_KEY_GITHUB=~/.ssh/id_ed25519

# ============================================
# [OPTIONAL] Slack Webhook
# ============================================
# SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/yyy/zzz
ENV_EOF

    chmod 600 "$env_file"
    log_success "Created .claude.env (template)"
    step_result "OK" "Created (template)"
}

# =============================================================================
# Step 3: 필수 도구 확인
# =============================================================================

do_step_3() {
    step_start 3 "Required Tools Check"

    local missing_required=()
    local missing_optional=()

    # 개별 도구 확인 함수 (반복 로직 추출)
    _check_tool() {
        local tool_name="$1"
        local required="$2"
        local version_cmd="$3"

        if command -v "$tool_name" >/dev/null 2>&1; then
            local ver
            ver=$(eval "$version_cmd" 2>/dev/null || echo "available")
            log_success "$tool_name: $ver"
            return 0
        else
            if [ "$required" = "required" ]; then
                missing_required+=("$tool_name")
                log_error "$tool_name: NOT FOUND"
            else
                missing_optional+=("$tool_name")
            fi
            return 1
        fi
    }

    # 필수 도구
    _check_tool "python3" "required" "python3 --version 2>&1 | awk '{print \$2}'"
    _check_tool "git" "required" "git --version 2>&1 | awk '{print \$3}'"
    _check_tool "rsync" "required" "rsync --version 2>&1 | awk 'NR==1{print \$3}'"

    # 선택 도구
    _check_tool "curl" "optional" "curl --version 2>&1 | awk 'NR==1{print \$2}'" || \
        log_warn "curl: NOT FOUND (fallback sync unavailable)"
    _check_tool "jq" "optional" "jq --version 2>&1" || \
        log_warn "jq: NOT FOUND (python3 will be used instead)"

    # 필수 도구 미설치 시 FATAL
    if [ ${#missing_required[@]} -gt 0 ]; then
        echo ""
        log_error "Required tools missing:"
        for tool in "${missing_required[@]}"; do
            case "$tool" in
                python3)
                    log_error "  - python3: Install with 'sudo apt install python3' (Ubuntu) or 'brew install python3' (macOS)"
                    ;;
                git)
                    log_error "  - git: Install with 'sudo apt install git' (Ubuntu) or 'xcode-select --install' (macOS)"
                    ;;
                rsync)
                    log_error "  - rsync: Install with 'sudo apt install rsync' (Ubuntu) or 'brew install rsync' (macOS)"
                    ;;
            esac
        done
        echo ""
        log_error "Please install the missing tools and re-run this script."
        step_result "FAIL" "Missing: ${missing_required[*]}"
        exit 1
    fi

    if [ ${#missing_optional[@]} -gt 0 ]; then
        step_result "WARN" "Optional missing: ${missing_optional[*]}"
    else
        step_result "OK" "All tools available"
    fi
}

# =============================================================================
# Step 4: 원격 동기화 (.claude/ 디렉토리)
# =============================================================================

do_step_4() {
    step_start 4 "Remote Sync (.claude/)"

    if [ "$SKIP_SYNC" = true ]; then
        log_skip "Remote sync skipped (--skip-sync)"
        if [ -d "$PROJECT_ROOT/.claude" ]; then
            step_result "SKIP" "Skipped, local .claude/ exists"
        else
            log_warn ".claude/ directory does not exist. Some features will not work."
            step_result "WARN" "Skipped, no local .claude/"
        fi
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY-RUN] Would sync .claude/ from $REMOTE_REPO"
        step_result "SKIP" "Dry-run mode"
        return 0
    fi

    local init_sync_sh="$PROJECT_ROOT/.claude/hooks/init/init-sync.sh"
    local env_file="$PROJECT_ROOT/.claude.env"

    # init-sync.sh 존재 시 직접 호출
    if [ -f "$init_sync_sh" ]; then
        log_info "Using existing init-sync.sh..."
        if bash "$init_sync_sh" 2>&1 | { [ "$VERBOSE" = true ] && cat || cat >/dev/null; }; then
            log_success "Sync completed via init-sync.sh"
            step_result "OK" "Synced (init-sync.sh)"
            return 0
        else
            log_warn "init-sync.sh failed, trying inline sync..."
        fi
    fi

    # 인라인 동기화 (최초 설치 또는 init-sync.sh 실패 시)
    log_info "Running inline sync..."

    TEMP_DIR=$(mktemp -d "/tmp/claude-workflow-sync-XXXXXX")
    local clone_dir="$TEMP_DIR/clone"
    local backup_dir="$TEMP_DIR/backup"

    # 보존 대상 파일 백업 함수 (DRY: 반복 로직 추출)
    _backup_file() {
        local src="$1"
        local dest_name="$2"
        if [ -f "$src" ]; then
            mkdir -p "$backup_dir"
            cp "$src" "$backup_dir/$dest_name"
            [ "$VERBOSE" = true ] && log_info "Backed up: $dest_name"
        fi
    }

    # .claude.env 이중 보호 백업 (rsync 범위 외부이나 안전장치)
    _backup_file "$env_file" ".claude.env"

    # settings.local.json 백업 (rsync exclude 대상이나 이중 보호)
    _backup_file "$PROJECT_ROOT/.claude/settings.local.json" "settings.local.json"

    # git clone 시도 (retry 3회, timeout 30초)
    log_info "Cloning from $REMOTE_REPO (shallow)..."
    local clone_success=false
    local clone_output=""
    if clone_output=$(retry 3 2 timeout 30 git clone --depth 1 "$REMOTE_REPO" "$clone_dir" 2>&1); then
        clone_success=true
        [ "$VERBOSE" = true ] && log_info "Clone output: $clone_output"
    else
        [ "$VERBOSE" = true ] && [ -n "$clone_output" ] && log_info "Clone output: $clone_output"
    fi

    if [ "$clone_success" = false ]; then
        # 단계적 폴백: 로컬 .claude/ 존재 여부로 분기
        if [ -d "$PROJECT_ROOT/.claude" ]; then
            log_warn "Network sync failed. Using existing local .claude/ directory."
            step_result "WARN" "Network failed, local preserved"
            return 0
        else
            log_error "Network sync failed and no local .claude/ directory exists."
            log_error "Please check your internet connection and try again."
            step_result "FAIL" "Network failed, no local .claude/"
            exit 1
        fi
    fi

    # 원격에 .claude 디렉토리가 있는지 확인
    if [ ! -d "$clone_dir/.claude" ]; then
        log_error "Remote repository does not contain .claude/ directory."
        step_result "FAIL" "No .claude/ in remote"
        exit 1
    fi

    # rsync 동기화 (--delete로 원격 기준 최종 상태 보장)
    log_info "Syncing .claude/ via rsync --delete..."
    local rsync_output=""
    if rsync_output=$(rsync -a --delete \
        --exclude='settings.local.json' \
        --exclude='__pycache__/' \
        "$clone_dir/.claude/" "$PROJECT_ROOT/.claude/" 2>&1); then
        log_success "rsync sync completed"
        [ "$VERBOSE" = true ] && [ -n "$rsync_output" ] && log_info "rsync output: $rsync_output"
    else
        log_error "rsync failed."
        [ "$VERBOSE" = true ] && [ -n "$rsync_output" ] && log_info "rsync output: $rsync_output"
        if [ -d "$PROJECT_ROOT/.claude" ]; then
            log_warn "Keeping existing .claude/ directory."
            step_result "WARN" "rsync failed, local preserved"
            return 0
        else
            step_result "FAIL" "rsync failed, no local .claude/"
            exit 1
        fi
    fi

    # 보존 파일 복원 함수 (DRY: 반복 로직 추출)
    _restore_file() {
        local backup_name="$1"
        local dest="$2"
        if [ -f "$backup_dir/$backup_name" ]; then
            cp "$backup_dir/$backup_name" "$dest"
            [ "$VERBOSE" = true ] && log_info "Restored: $backup_name"
        fi
    }

    # settings.local.json 복원
    _restore_file "settings.local.json" "$PROJECT_ROOT/.claude/settings.local.json"

    # .claude.env 복원 (이중 보호)
    _restore_file ".claude.env" "$env_file"

    step_result "OK" "Synced from remote"
}

# =============================================================================
# Step 5: 프로젝트 디렉토리 구조 생성
# =============================================================================

do_step_5() {
    step_start 5 "Project Directory Setup"

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY-RUN] Would create .workflow/, .prompt/ directories"
        step_result "SKIP" "Dry-run mode"
        return 0
    fi

    local init_project_sh="$PROJECT_ROOT/.claude/hooks/init/init-project.sh"

    if [ -f "$init_project_sh" ] && [ "$FORCE" = false ]; then
        log_info "Using init-project.sh setup-dirs..."
        local setup_output=""
        if setup_output=$(bash "$init_project_sh" setup-dirs 2>&1); then
            log_success "Directories created via init-project.sh"
            [ "$VERBOSE" = true ] && [ -n "$setup_output" ] && log_info "Output: $setup_output"
            step_result "OK" "Created (init-project.sh)"
            return 0
        else
            log_warn "init-project.sh setup-dirs failed, using inline fallback..."
            [ "$VERBOSE" = true ] && [ -n "$setup_output" ] && log_info "Output: $setup_output"
        fi
    fi

    # 인라인 폴백: 디렉토리 및 파일 생성 (DRY: 헬퍼 함수 활용)
    local created=0

    # 디렉토리 생성 헬퍼
    _ensure_dir() {
        local dir_path="$1"
        if [ ! -d "$dir_path" ]; then
            mkdir -p "$dir_path"
            created=$((created + 1))
            [ "$VERBOSE" = true ] && log_info "Created dir: $dir_path"
        fi
    }

    # 파일 생성 헬퍼 (빈 파일)
    _ensure_file() {
        local file_path="$1"
        if [ ! -f "$file_path" ]; then
            touch "$file_path"
            created=$((created + 1))
            [ "$VERBOSE" = true ] && log_info "Created file: $file_path"
        fi
    }

    # 디렉토리 생성
    _ensure_dir "$PROJECT_ROOT/.workflow"
    _ensure_dir "$PROJECT_ROOT/.prompt"

    # .workflow 파일 생성
    if [ ! -f "$PROJECT_ROOT/.workflow/registry.json" ]; then
        echo '{}' > "$PROJECT_ROOT/.workflow/registry.json"
        created=$((created + 1))
    fi

    if [ ! -f "$PROJECT_ROOT/.prompt/history.md" ]; then
        cat > "$PROJECT_ROOT/.prompt/history.md" << 'HIST_EOF'
# Work History

| Date | WorkID | Title | Command | Status | Report |
|------|--------|-------|---------|--------|--------|
<!-- New entries are added below this line -->
HIST_EOF
        created=$((created + 1))
    fi

    # .prompt 파일 생성
    for f in prompt.txt memo.txt querys.txt; do
        _ensure_file "$PROJECT_ROOT/.prompt/$f"
    done

    if [ $created -gt 0 ]; then
        log_success "Created $created items (inline)"
        step_result "OK" "Created $created items"
    else
        log_skip "All directories already exist"
        step_result "SKIP" "Already exists"
    fi
}

# =============================================================================
# Step 6: 셸 alias 등록
# =============================================================================

do_step_6() {
    step_start 6 "Shell Alias Setup"

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY-RUN] Would register cc/ccc aliases and wf-* aliases"
        step_result "SKIP" "Dry-run mode"
        return 0
    fi

    local init_claude_sh="$PROJECT_ROOT/.claude/hooks/init/init-claude.sh"
    local init_project_sh="$PROJECT_ROOT/.claude/hooks/init/init-project.sh"
    local cc_ok=false
    local wf_ok=false

    # 기존 스크립트 호출 + 인라인 폴백 (DRY: 공통 패턴 추출)
    _try_script_or_fallback() {
        local label="$1"
        local script="$2"
        local subcmd="$3"
        local fallback_fn="$4"

        if [ -f "$script" ]; then
            local output=""
            if output=$(bash "$script" "$subcmd" 2>&1); then
                log_success "$label registered via $(basename "$script")"
                [ "$VERBOSE" = true ] && [ -n "$output" ] && log_info "Output: $output"
                return 0
            else
                log_warn "$(basename "$script") $subcmd failed, using inline fallback..."
                [ "$VERBOSE" = true ] && [ -n "$output" ] && log_info "Output: $output"
            fi
        fi
        "$fallback_fn"
    }

    # 6a: Claude Code alias (cc/ccc)
    log_info "6a: Claude Code aliases (cc/ccc)..."
    _try_script_or_fallback "cc/ccc aliases" "$init_claude_sh" "setup-alias" "_inline_setup_cc_alias" && cc_ok=true || cc_ok=true

    # 6b: Workflow alias (wf-*)
    log_info "6b: Workflow aliases (wf-*)..."
    _try_script_or_fallback "wf-* aliases" "$init_project_sh" "setup-wf-alias" "_inline_setup_wf_alias" && wf_ok=true || wf_ok=true

    step_result "OK" "Aliases registered (cc/ccc + wf-*)"
}

# 인라인 cc/ccc alias 등록 (delete+append 방식)
_inline_setup_cc_alias() {
    local rc_file="$SHELL_RC"

    if [ ! -f "$rc_file" ]; then
        touch "$rc_file"
    fi

    local block_begin="# >>> Claude Code aliases"
    local block_end="# <<< Claude Code aliases"

    # 기존 블록 삭제 (블록 마커 방식)
    if grep -qF "$block_begin" "$rc_file" 2>/dev/null; then
        portable_sed_i "/$block_begin/,/$block_end/d" "$rc_file"
    fi

    # 레거시 패턴 삭제 (블록 마커 없는 이전 형식 호환)
    local legacy_patterns=("^alias cc=" "^alias ccc=")
    for pattern in "${legacy_patterns[@]}"; do
        if grep -q "$pattern" "$rc_file" 2>/dev/null; then
            portable_sed_i "/${pattern}/d" "$rc_file"
        fi
    done

    # 새 블록 추가
    {
        echo ""
        echo "$block_begin"
        echo 'export PATH="$HOME/.local/bin:$PATH"'
        echo "alias cc='claude --dangerously-skip-permissions \"/init:workflow\"'"
        echo "alias ccc='claude --dangerously-skip-permissions --continue'"
        echo "$block_end"
    } >> "$rc_file"

    log_success "cc/ccc aliases registered (inline)"
}

# 인라인 wf-* alias 등록 (alias + wrapper 스크립트)
_inline_setup_wf_alias() {
    local rc_file="$SHELL_RC"
    local bin_dir="$HOME/.local/bin"

    if [ ! -f "$rc_file" ]; then
        touch "$rc_file"
    fi

    mkdir -p "$bin_dir"

    # alias 정의 (name:command 형식, bash 3.2 호환 - 연관 배열 미사용)
    local alias_defs=(
        "Workflow:bash .claude/hooks/workflow/banner.sh"
        "wf-state:bash .claude/hooks/workflow/update-state.sh"
        "wf-init:bash .claude/hooks/init/init-workflow.sh"
        "wf-claude:bash .claude/hooks/init/init-claude.sh"
        "wf-project:bash .claude/hooks/init/init-project.sh"
        "wf-clear:bash .claude/hooks/init/init-clear.sh"
        "wf-sync:bash .claude/hooks/init/init-sync.sh"
        "wf-git-config:bash .claude/hooks/init/git-config.sh"
        "wf-slack:bash .claude/hooks/slack/slack.sh"
        "wf-info:bash .claude/hooks/workflow/info.sh"
        "wf-commands:bash .claude/hooks/workflow/commands.sh"
    )

    # 헤더 주석 추가 (없으면)
    if ! grep -qF "# Workflow shortcut aliases" "$rc_file" 2>/dev/null; then
        {
            echo ""
            echo "# Workflow shortcut aliases (for Claude Code Bash tool)"
        } >> "$rc_file"
    fi

    local alias_count=0
    local wrapper_count=0

    for entry in "${alias_defs[@]}"; do
        local name="${entry%%:*}"
        local cmd="${entry#*:}"

        # alias 추가 (중복 체크)
        if ! grep -q "^alias ${name}=" "$rc_file" 2>/dev/null; then
            echo "alias ${name}='${cmd}'" >> "$rc_file"
            alias_count=$((alias_count + 1))
        fi

        # wrapper 스크립트 생성 (항상 덮어쓰기 - 멱등)
        cat > "${bin_dir}/${name}" << WRAPPER_EOF
#!/bin/bash
# Auto-generated by init-claude-workflow.sh
# Wrapper for non-interactive bash environments
# Equivalent to: alias ${name}='${cmd}'
exec ${cmd} "\$@"
WRAPPER_EOF
        chmod +x "${bin_dir}/${name}"
        wrapper_count=$((wrapper_count + 1))
    done

    log_success "wf-* aliases registered (inline, ${alias_count} new aliases + ${wrapper_count} wrappers)"
}

# =============================================================================
# Step 7: .claude.env 검증
# =============================================================================

do_step_7() {
    step_start 7 ".claude.env Verification"

    local env_file="$PROJECT_ROOT/.claude.env"

    # .claude.env 존재 확인 (Step 2에서 생성되었어야 하나 안전장치)
    if [ ! -f "$env_file" ]; then
        log_warn ".claude.env not found. Creating..."
        touch "$env_file"
        chmod 600 "$env_file"
    fi

    # 읽기/쓰기 권한 확인
    if [ ! -r "$env_file" ]; then
        log_warn ".claude.env is not readable"
        step_result "WARN" "Not readable"
        return 0
    fi

    if [ ! -w "$env_file" ]; then
        log_warn ".claude.env is not writable"
        step_result "WARN" "Not writable"
        return 0
    fi

    log_success ".claude.env exists with correct permissions"

    # 환경변수 설정 여부 확인 헬퍼 (DRY: grep 패턴 반복 제거)
    _check_env_var() {
        local key="$1"
        local desc="$2"
        local required="$3"  # required | optional
        if grep -q "^${key}=.\+" "$env_file" 2>/dev/null; then
            local val=""
            [ "$VERBOSE" = true ] && val=" ($(grep "^${key}=" "$env_file" | head -1 | cut -d= -f2-))"
            log_success "${key}: configured${val}"
            return 0
        else
            if [ "$required" = "required" ]; then
                log_info "${key}: not set (${desc})"
            else
                log_info "${key}: not configured (${desc}, optional)"
            fi
            return 1
        fi
    }

    # 필수 환경변수 확인
    local unset_count=0
    _check_env_var "CLAUDE_CODE_GIT_USER_NAME" "Git user name" "required" || unset_count=$((unset_count + 1))
    _check_env_var "CLAUDE_CODE_GIT_USER_EMAIL" "Git user email" "required" || unset_count=$((unset_count + 1))
    _check_env_var "CLAUDE_CODE_SSH_KEY_GITHUB" "SSH key path" "required" || unset_count=$((unset_count + 1))

    # 선택 환경변수 (Slack - 3가지 키 중 하나라도 설정되면 OK)
    local slack_configured=false
    for slack_key in SLACK_WEBHOOK_URL CLAUDE_CODE_SLACK_WEBHOOK_URL CLAUDE_CODE_SLACK_BOT_TOKEN; do
        if grep -q "^${slack_key}=.\+" "$env_file" 2>/dev/null; then
            slack_configured=true
            break
        fi
    done
    if [ "$slack_configured" = true ]; then
        log_success "Slack: configured"
    else
        log_info "Slack: not configured (optional)"
    fi

    if [ $unset_count -gt 0 ]; then
        step_result "WARN" "${unset_count} required vars not set"
    else
        step_result "OK" "All required vars configured"
    fi
}

# =============================================================================
# Step 8: .gitignore 패턴 등록
# =============================================================================

do_step_8() {
    step_start 8 ".gitignore Patterns"

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY-RUN] Would add patterns to .gitignore"
        step_result "SKIP" "Dry-run mode"
        return 0
    fi

    local init_project_sh="$PROJECT_ROOT/.claude/hooks/init/init-project.sh"

    # 기존 스크립트 호출 (FORCE=false 시, VERBOSE 지원)
    if [ -f "$init_project_sh" ] && [ "$FORCE" = false ]; then
        log_info "Using init-project.sh setup-gitignore..."
        local setup_output=""
        if setup_output=$(bash "$init_project_sh" setup-gitignore 2>&1); then
            log_success ".gitignore updated via init-project.sh"
            [ "$VERBOSE" = true ] && [ -n "$setup_output" ] && log_info "Output: $setup_output"
            step_result "OK" "Updated (init-project.sh)"
            return 0
        else
            log_warn "init-project.sh setup-gitignore failed, using inline fallback..."
            [ "$VERBOSE" = true ] && [ -n "$setup_output" ] && log_info "Output: $setup_output"
        fi
    fi

    # 인라인 폴백: 패턴 중복 체크 후 append (DRY: 헬퍼 함수 활용)
    local gitignore="$PROJECT_ROOT/.gitignore"

    if [ ! -f "$gitignore" ]; then
        touch "$gitignore"
    fi

    local patterns=(".workflow/" ".claude.env" ".claude.env*" ".prompt/" "CLAUDE.md")
    local added=0
    local skipped=0

    _add_gitignore_pattern() {
        local pattern="$1"
        if grep -qxF "$pattern" "$gitignore" 2>/dev/null; then
            skipped=$((skipped + 1))
            [ "$VERBOSE" = true ] && log_info "Pattern exists: $pattern"
        else
            echo "$pattern" >> "$gitignore"
            added=$((added + 1))
            [ "$VERBOSE" = true ] && log_info "Added pattern: $pattern"
        fi
    }

    for pattern in "${patterns[@]}"; do
        _add_gitignore_pattern "$pattern"
    done

    if [ $added -gt 0 ]; then
        log_success "Added $added patterns to .gitignore ($skipped already existed)"
        step_result "OK" "Added $added patterns"
    else
        log_skip "All ${#patterns[@]} patterns already in .gitignore"
        step_result "SKIP" "All patterns exist"
    fi
}

# =============================================================================
# Step 9: StatusLine 설정
# =============================================================================

do_step_9() {
    step_start 9 "StatusLine Setup"

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY-RUN] Would configure StatusLine"
        step_result "SKIP" "Dry-run mode"
        return 0
    fi

    local init_claude_sh="$PROJECT_ROOT/.claude/hooks/init/init-claude.sh"

    # 기존 스크립트 호출 (FORCE=false 시, VERBOSE 지원)
    if [ -f "$init_claude_sh" ] && [ "$FORCE" = false ]; then
        log_info "Using init-claude.sh setup-statusline..."
        local setup_output=""
        if setup_output=$(bash "$init_claude_sh" setup-statusline 2>&1); then
            log_success "StatusLine configured via init-claude.sh"
            [ "$VERBOSE" = true ] && [ -n "$setup_output" ] && log_info "Output: $setup_output"
            step_result "OK" "Configured (init-claude.sh)"
            return 0
        else
            log_warn "init-claude.sh setup-statusline failed, using inline fallback..."
            [ "$VERBOSE" = true ] && [ -n "$setup_output" ] && log_info "Output: $setup_output"
        fi
    fi

    # 인라인 폴백
    mkdir -p "$HOME/.claude"

    local global_settings="$HOME/.claude/settings.json"
    local statusline_script="$HOME/.claude/statusline.sh"
    local settings_updated=false
    local script_created=false

    # settings.json 설정 (python3로 안전한 JSON 병합)
    if [ ! -f "$global_settings" ]; then
        cat > "$global_settings" << 'SETTINGS_EOF'
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh",
    "padding": 0
  }
}
SETTINGS_EOF
        settings_updated=true
        [ "$VERBOSE" = true ] && log_info "Created new settings.json"
    else
        if ! grep -q '"statusLine"' "$global_settings" 2>/dev/null; then
            if command -v python3 >/dev/null 2>&1; then
                # python3 인라인 스크립트 - sys.argv로 경로 전달 (쉘 변수 주입 방지)
                if python3 -c '
import json, sys
settings_path = sys.argv[1]
with open(settings_path, "r") as f:
    data = json.load(f)
data["statusLine"] = {
    "type": "command",
    "command": "~/.claude/statusline.sh",
    "padding": 0
}
with open(settings_path, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
' "$global_settings" 2>/dev/null; then
                    settings_updated=true
                    [ "$VERBOSE" = true ] && log_info "Merged statusLine into existing settings.json"
                else
                    log_warn "Failed to merge statusLine into settings.json"
                fi
            else
                log_warn "python3 not available, cannot merge statusLine into settings.json"
            fi
        else
            [ "$VERBOSE" = true ] && log_info "statusLine already present in settings.json"
        fi
    fi

    # statusline.sh 스크립트 생성 (--force 시 덮어쓰기)
    if [ ! -f "$statusline_script" ] || [ "$FORCE" = true ]; then
        cat > "$statusline_script" << 'STATUSLINE_EOF'
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
        chmod +x "$statusline_script"
        script_created=true
        [ "$VERBOSE" = true ] && log_info "Created statusline.sh script"
    fi

    if [ "$settings_updated" = true ] || [ "$script_created" = true ]; then
        log_success "StatusLine configured (inline)"
        step_result "OK" "Configured (inline)"
    else
        log_skip "StatusLine already configured"
        step_result "SKIP" "Already configured"
    fi
}

# =============================================================================
# Step 10: 최종 검증 및 보고
# =============================================================================

do_step_10() {
    step_start 10 "Final Verification"

    local ok_count=0
    local warn_count=0
    local fail_count=0
    local total_count=0
    local check_results=()

    # 검증 함수 (OK/WARN/FAIL 별도 카운트)
    _check() {
        local name="$1"
        local status="$2"
        local detail="$3"
        total_count=$((total_count + 1))
        case "$status" in
            OK)   ok_count=$((ok_count + 1)) ;;
            WARN) warn_count=$((warn_count + 1)) ;;
            FAIL) fail_count=$((fail_count + 1)) ;;
        esac
        check_results+=("$name|$status|$detail")
    }

    # 디렉토리/파일 존재 검증 헬퍼 (DRY: 반복 패턴 추출)
    _check_exists() {
        local name="$1"
        local path="$2"
        local type="$3"  # dir | file
        if [ "$type" = "dir" ] && [ -d "$path" ]; then
            _check "$name" "OK" "Exists"
        elif [ "$type" = "file" ] && [ -f "$path" ]; then
            _check "$name" "OK" "Exists"
        else
            _check "$name" "FAIL" "Missing"
        fi
    }

    # 1. Claude Code CLI
    if command -v claude >/dev/null 2>&1; then
        local ver
        ver=$(claude --version 2>/dev/null || echo "?")
        _check "Claude Code CLI" "OK" "$ver"
    else
        _check "Claude Code CLI" "WARN" "Not installed"
    fi

    # 2. 필수 도구
    for tool in python3 git rsync; do
        if command -v "$tool" >/dev/null 2>&1; then
            _check "$tool" "OK" "Available"
        else
            _check "$tool" "FAIL" "Not found"
        fi
    done

    # 3~6. 디렉토리/파일 존재 확인 (헬퍼 사용)
    _check_exists ".claude/ directory" "$PROJECT_ROOT/.claude" "dir"
    _check_exists ".claude.env" "$PROJECT_ROOT/.claude.env" "file"
    _check_exists ".workflow/ directory" "$PROJECT_ROOT/.workflow" "dir"
    _check_exists ".prompt/ directory" "$PROJECT_ROOT/.prompt" "dir"

    # 7. Shell aliases (cc/ccc)
    if [ -f "$SHELL_RC" ] && grep -q "^alias cc=" "$SHELL_RC" 2>/dev/null; then
        _check "Shell aliases (cc/ccc)" "OK" "$SHELL_RC"
    else
        _check "Shell aliases (cc/ccc)" "WARN" "Not found in $SHELL_RC"
    fi

    # 8. Workflow aliases (파일 한 번 읽어서 카운트 - DRY: grep 반복 제거)
    local wf_alias_count=0
    if [ -f "$SHELL_RC" ]; then
        local rc_content
        rc_content=$(cat "$SHELL_RC" 2>/dev/null || true)
        for name in Workflow wf-state wf-init wf-claude wf-project wf-clear wf-sync wf-git-config wf-slack wf-info wf-commands; do
            if echo "$rc_content" | grep -q "^alias ${name}="; then
                wf_alias_count=$((wf_alias_count + 1))
            fi
        done
    fi
    if [ $wf_alias_count -ge 11 ]; then
        _check "Workflow aliases (11)" "OK" "${wf_alias_count}/11 in $SHELL_RC"
    else
        _check "Workflow aliases (11)" "WARN" "${wf_alias_count}/11 in $SHELL_RC"
    fi

    # 9. .gitignore patterns (파일 한 번 읽어서 카운트)
    if [ -f "$PROJECT_ROOT/.gitignore" ]; then
        local gi_content gi_count=0
        gi_content=$(cat "$PROJECT_ROOT/.gitignore" 2>/dev/null || true)
        for p in ".workflow/" ".claude.env" ".prompt/"; do
            if echo "$gi_content" | grep -qF "$p"; then
                gi_count=$((gi_count + 1))
            fi
        done
        if [ $gi_count -ge 3 ]; then
            _check ".gitignore patterns" "OK" "${gi_count} patterns"
        else
            _check ".gitignore patterns" "WARN" "${gi_count}/3 patterns"
        fi
    else
        _check ".gitignore patterns" "WARN" "No .gitignore"
    fi

    # 10. StatusLine
    if [ -f "$HOME/.claude/settings.json" ] && grep -q '"statusLine"' "$HOME/.claude/settings.json" 2>/dev/null; then
        _check "StatusLine" "OK" "~/.claude/settings.json"
    else
        _check "StatusLine" "WARN" "Not configured"
    fi

    # 결과 테이블 출력
    echo ""
    echo "  =================================================="
    echo "    init-claude-workflow.sh - Setup Report"
    echo "  =================================================="
    echo ""
    printf "  %-30s %-10s %s\n" "Component" "Status" "Details"
    echo "  --------------------------------------------------"

    for entry in "${check_results[@]}"; do
        local name status detail
        name="${entry%%|*}"
        local rest="${entry#*|}"
        status="${rest%%|*}"
        detail="${rest#*|}"

        local status_display
        case "$status" in
            OK)   status_display="${GREEN}[OK]${NC}" ;;
            WARN) status_display="${YELLOW}[WARN]${NC}" ;;
            FAIL) status_display="${RED}[FAIL]${NC}" ;;
            SKIP) status_display="${YELLOW}[SKIP]${NC}" ;;
            *)    status_display="[$status]" ;;
        esac

        printf "  %-30s " "$name"
        echo -e "${status_display}      ${detail}"
    done

    echo ""
    echo "  --------------------------------------------------"
    local result_summary="${ok_count}/${total_count} OK"
    [ $warn_count -gt 0 ] && result_summary="${result_summary}, ${warn_count} WARN"
    [ $fail_count -gt 0 ] && result_summary="${result_summary}, ${fail_count} FAIL"
    echo -e "  Result: ${BOLD}${result_summary}${NC}"

    # VERBOSE 모드: 이전 Step 결과 요약 표시
    if [ "$VERBOSE" = true ] && [ ${#RESULTS[@]} -gt 0 ]; then
        echo ""
        echo "  Step Results (from execution):"
        for r in "${RESULTS[@]}"; do
            echo "    $r"
        done
    fi

    echo ""
    echo "  Next steps:"
    echo "    1. Run 'source $SHELL_RC' to apply aliases"
    echo "    2. Run 'claude' to authenticate (if first time)"
    echo "    3. Edit '.claude.env' to configure environment variables"
    echo "    4. Run 'cc' to start Claude Code with workflow"
    echo "  =================================================="

    step_result "OK" "${result_summary}"
}

# =============================================================================
# main 함수
# =============================================================================

main() {
    parse_args "$@"

    echo ""
    echo -e "${BOLD}init-claude-workflow.sh v${VERSION}${NC}"
    echo "========================================"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN MODE] No changes will be made.${NC}"
    fi

    do_step_0
    do_step_1
    do_step_2
    do_step_3
    do_step_4
    do_step_5
    do_step_6
    do_step_7
    do_step_8
    do_step_9
    do_step_10

    echo ""
    echo -e "${GREEN}${BOLD}Setup complete!${NC}"
    echo ""
}

main "$@"
