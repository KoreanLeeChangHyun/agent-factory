#!/bin/bash
set -euo pipefail
# build.sh — Agent Factory environment auto-initialization script
# Supports: Ubuntu 20.04+, macOS 13.0+ | Dependencies: git, curl, python3, gh | Select: tmux

# --- load constant ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULTS_CONF="${SCRIPT_DIR}/build-assets/defaults.conf"
if [ ! -f "$DEFAULTS_CONF" ]; then
    echo "ERROR: defaults.conf not found: $DEFAULTS_CONF" >&2
    exit 1
fi
# shellcheck source=.agent-factory/build-assets/defaults.conf
source "$DEFAULTS_CONF"

# --- Color variable ---
if [ -t 1 ]; then
    GREEN=$'\033[0;32m'; RED=$'\033[0;31m'; YELLOW=$'\033[0;33m'
    CYAN=$'\033[0;36m'; BOLD_CYAN=$'\033[1;36m'; NC=$'\033[0m'
else
    GREEN=""; RED=""; YELLOW=""; CYAN=""; BOLD_CYAN=""; NC=""
fi

# --- Common output functions ---
# Hierarchy: Header/Structure (GREEN), Success ACK (CYAN — reduce visual noise), Information (YELLOW), Error (RED)
print_success() { printf '%s  ✓ %s%s\n' "${CYAN}"  "$1" "${NC}"; }
print_error()   { printf '%s  ✗ %s%s\n' "${RED}"    "$1" "${NC}"; }
print_warning() { printf '%s  ⚠ %s%s\n' "${YELLOW}" "$1" "${NC}"; }
print_info()    { printf '%s  → %s%s\n' "${YELLOW}"  "$1" "${NC}"; }
print_step()    { printf '\n%s[Step %s]%s %s\n' "${GREEN}" "$1" "${NC}" "$2"; }

# --- Shell Determination Helper ---
# $SHELL returns the login shell. This function determines the configuration file path relative to your login shell.
detect_shell_rc() {
    local _shell_name
    _shell_name="$(basename "$SHELL")"
    case "$_shell_name" in
        zsh)  DETECTED_SHELL_NAME="zsh";  DETECTED_SHELL_RC="$HOME/.zshrc"  ;;
        bash) DETECTED_SHELL_NAME="bash"; DETECTED_SHELL_RC="$HOME/.bashrc" ;;
        *)    DETECTED_SHELL_NAME="$_shell_name"; DETECTED_SHELL_RC="$HOME/.bashrc" ;;
    esac
}

# --- Template verification ---
validate_templates() {
    local missing=()
    for tmpl in "$TMPL_SETTINGS" "$TMPL_CLAUDE_ENV" "$TMPL_CLAUDE_ALIASES"; do
        [ ! -f "$tmpl" ] && missing+=("$tmpl")
    done
    if [ "${#missing[@]}" -gt 0 ]; then
        print_error "Required template file missing: ${missing[*]}"
        print_info "Check the .agent-factory/build-assets/templates/ directory before running build.sh."
        exit 1
    fi
}

# --- Command verification helper ---
_verify_command() {
    local cmd="$1" label="$2"
    if command -v "$cmd" &>/dev/null; then
        print_success "$label executable ($("$cmd" --version 2>/dev/null | head -1 || echo 'version unknown'))"
    else
        print_error "$label command not found"; return 1
    fi
}

# --- OS detection and version verification ---
detect_os() {
    local os_type
    os_type="$(uname -s)"
    case "$os_type" in
        Linux)
            DETECTED_OS="linux"
            [ ! -f /etc/os-release ] && { print_error "This is an unsupported Linux distribution. The /etc/os-release file does not exist."; exit 1; }
            # shellcheck source=/dev/null
            . /etc/os-release
            local version_id="${VERSION_ID:-0}"
            local major_version
            major_version="$(echo "$version_id" | cut -d. -f1)"
            if [ "$major_version" -lt 20 ] 2>/dev/null; then
                print_error "Requires Ubuntu 20.04 or higher. Current version: $version_id"; exit 1
            fi
            print_success "OS detected: Linux (Ubuntu $version_id)"
            ;;
        Darwin)
            DETECTED_OS="macos"
            local macos_version macos_major
            macos_version="$(sw_vers -productVersion 2>/dev/null || echo '0.0')"
            macos_major="$(echo "$macos_version" | cut -d. -f1)"
            if [ "$macos_major" -lt 13 ] 2>/dev/null; then
                print_error "Requires macOS 13.0 (Ventura) or later. Current version: $macos_version"; exit 1
            fi
            print_success "Detect OS: macOS ($macos_version)"
            ;;
        *) print_error "Unsupported OS: $os_type (requires Ubuntu 20.04+ or macOS 13.0+)"; exit 1 ;;
    esac
}

# --- Python minimum version verification ---
check_python_version() {
    local current_version
    current_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    if python3 -c "import sys; sys.exit(0 if (sys.version_info.major, sys.version_info.minor) >= ($REQUIRED_PYTHON_MAJOR, $REQUIRED_PYTHON_MINOR) else 1)" 2>/dev/null; then
        return 0
    fi
    print_error "Python version below: Current $current_version, minimum required ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
    print_info "Upgrade to Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR} or higher:"
    case "${DETECTED_OS:-linux}" in
        macos) print_info "  brew install python@${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}" ;;
        linux)
            print_info "  sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt-get update"
            print_info "  sudo apt-get install python${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
            ;;
        *) print_info "Install Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}+ from https://www.python.org/downloads/" ;;
    esac
    exit 1
}

# --- Register gh CLI APT repository (Linux only) ---
_register_gh_apt_repo() {
    print_info "Register the GitHub CLI official APT repository..."
    if ! command -v curl &>/dev/null; then
        print_error "Registration of gh APT repository failed due to lack of curl. Install curl first."; return 1
    fi
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
            | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg 2>/dev/null \
    && sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
            | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && sudo apt-get update -qq
}

# --- Install python3 automatically (tmux is optional) ---
install_dependencies() {
    print_step "2" "Check dependency installation (python3, gh)"
    local missing_deps=()
    if ! command -v python3 &>/dev/null; then missing_deps+=("python3"); else check_python_version; fi
    command -v gh   &>/dev/null || missing_deps+=("gh")
    # tmux is optional — not required as it is only used in the TMUX_PANE fallback path
    if ! command -v tmux &>/dev/null; then
        print_warning "tmux is not installed (optional). The tmux fallback path is disabled."
    fi
    if [ "${#missing_deps[@]}" -eq 0 ]; then
        print_success "Dependencies already installed (python3, gh)"; return 0
    fi
    print_info "Missing dependencies: ${missing_deps[*]}"
    case "${DETECTED_OS:-linux}" in
        linux)
            sudo apt-get update -qq || { print_error "apt-get update failed"; return 1; }
            if printf '%s\n' "${missing_deps[@]}" | grep -qx 'gh'; then
                if _register_gh_apt_repo; then
                    print_success "GitHub CLI APT repository registration completed"
                else
                    print_error "GitHub CLI APT repository registration failed. Install gh manually: https://cli.github.com"
                    local filtered=()
                    for dep in "${missing_deps[@]}"; do [ -n "$dep" ] && [ "$dep" != "gh" ] && filtered+=("$dep"); done
                    missing_deps=("${filtered[@]}")
                fi
            fi
            [ "${#missing_deps[@]}" -gt 0 ] && { sudo apt-get install -y "${missing_deps[@]}" || { print_error "Package installation failed: ${missing_deps[*]}"; return 1; }; }
            ;;
        macos)
            command -v brew &>/dev/null || { print_error "Homebrew is not installed. Please install it from https://brew.sh first."; return 1; }
            brew install "${missing_deps[@]}" || { print_error "brew install failed: ${missing_deps[*]}"; return 1; }
            ;;
        *) print_error "Unknown OS does not support silent installation."; return 1 ;;
    esac
    local still_missing=()
    for dep in "${missing_deps[@]}"; do command -v "$dep" &>/dev/null || still_missing+=("$dep"); done
    if [ "${#still_missing[@]}" -gt 0 ]; then
        print_error "Even after installing, the following dependencies are not found: ${still_missing[*]}"; return 1
    fi
    print_success "Dependencies installed (${missing_deps[*]})"
}

# --- Step 1: Install Claude Code ---
install_claude_code() {
    print_step "1" "Verify Claude Code installation"
    if command -v claude &>/dev/null; then
        print_success "Claude Code is already installed ($(claude --version 2>/dev/null || echo 'version unknown'))"
        return 0
    fi
    print_info "Claude Code is not installed. Installation begins..."
    command -v curl &>/dev/null || { print_error "curl is not installed. Please install curl first."; return 1; }
    local install_script
    install_script="$(mktemp)"
    if ! curl -fsSL -o "$install_script" https://claude.ai/install.sh; then
        print_error "Claude Code installation script download failed"
        rm -f "$install_script"; return 1
    fi
    if bash "$install_script"; then
        print_success "Claude Code installation complete"
    else
        print_error "Claude Code installation failed"
        rm -f "$install_script"; return 1
    fi
    rm -f "$install_script"
}

# --- Step 6: Set shell aliases ---
setup_shell_aliases() {
    print_step "6" "Set shell aliases"
    local aliases_file="$HOME/.claude.aliases"
    detect_shell_rc
    local shell_name="$DETECTED_SHELL_NAME" shell_rc="$DETECTED_SHELL_RC"
    if [ "$shell_name" != "zsh" ] && [ "$shell_name" != "bash" ]; then
        print_info "Detected shell: $shell_name (replace with your bash configuration)"
    fi
    # Grant permission to execute wrapper script
    if ls "$SCRIPT_DIR/bin/flow-"* &>/dev/null 2>&1; then
        chmod +x "$SCRIPT_DIR/bin/flow-"*
        print_success "Completed granting permission to execute wrapper script ($SCRIPT_DIR/bin/flow-*)"
    else
        print_info "No wrapper script ($SCRIPT_DIR/bin/flow-*). skip chmod"
    fi
    # Always overwrite the template (completely switch to bin/wrapper PATH method)
    cp "$TMPL_CLAUDE_ALIASES" "$aliases_file"
    print_success ".claude.aliases setup complete ($aliases_file)"
    local source_line="# Agent Factory aliases"
    local source_cmd="[ -f \"$aliases_file\" ] && source \"$aliases_file\""
    [ ! -f "$shell_rc" ] && touch "$shell_rc"
    if grep -q ".claude.aliases" "$shell_rc" 2>/dev/null; then
        print_success "The source line is already registered in the shell configuration file ($shell_rc)"
    else
        { echo ""; echo "$source_line"; echo "$source_cmd"; } >> "$shell_rc"
        print_success "Completed adding source line to shell configuration file ($shell_rc)"
    fi
}

# --- Step 3: Create directories and files ---
create_directories_and_files() {
    print_step "3" "Create directories and files"
    for dir in "${INIT_DIRS[@]}"; do
        if [ ! -d "$dir" ]; then mkdir -p "$dir"; print_success "Create directory: $dir"
        else print_info "Directory already exists: $dir"; fi
    done
    for file in "${INIT_FILES[@]}"; do
        if [ ! -f "$file" ]; then touch "$file"; print_success "Create file: $file"
        else print_info "File already exists: $file"; fi
    done
    local skill_state_file=".claude/skills/skill-state.json"
    if [ -f "$skill_state_file" ]; then
        print_info "File already exists: $skill_state_file"
    elif [ -d ".claude/skills" ]; then
        python3 -c "import json; f=open('$skill_state_file','w'); json.dump({'version':1,'skills':{}},f,indent=2); f.write('\n'); f.close()"
        print_success "Create file: $skill_state_file"
    else
        print_info "The .claude/skills/ directory does not exist. Skip creating skill-state.json."
    fi
}

# --- Merge Helper: JSON Top-Level Key Unit Merge ---
# Usage: _merge_json_keys <existing file> <template file>
# Existing values ​​take precedence, adding only new top-level keys that exist only in the template.
# Handled inline in python3. Preserve existing files in case of error.
_merge_json_keys() {
    local existing_file="$1" tmpl_file="$2"
    [ ! -f "$existing_file" ] || [ ! -f "$tmpl_file" ] && return 1

    local tmp_result
    tmp_result="$(mktemp)" || return 1

    local py_output
    py_output="$(python3 - "$existing_file" "$tmpl_file" "$tmp_result" <<'PYEOF'
import json, sys

existing_path, tmpl_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

try:
    with open(existing_path, 'r') as f:
        existing = json.load(f)
except Exception as e:
    print(f"ERROR: existing file JSON parsing failed:   FIELD 0  ", file=sys.stderr)
    sys.exit(1)

try:
    with open(tmpl_path, 'r') as f:
        tmpl = json.load(f)
except Exception as e:
    print(f"ERROR: template file JSON parsing failed:   FIELD 0  ", file=sys.stderr)
    sys.exit(1)

# Matches the hook command path with the old directory name to the new path.
# If you compare and merge only the keys, the stale command in the existing settings.json remains as is.
# Hooks call files that do not exist and are blocked with ENOENT.
# Preserve other keys/values ​​added by the user and replace only the command field with a pattern.
_PATH_FIXES = [
    (".claude.workflow/scripts/", ".agent-factory/engine/"),
    (".claude.workflow/", ".agent-factory/"),
    (
        "python3 -u $CLAUDE_PROJECT_DIR/.agent-factory/engine/sync/history_sync.py",
        "$CLAUDE_PROJECT_DIR/.agent-factory/bin/flow-history",
    ),
    (
        "$CLAUDE_PROJECT_DIR/.agent-factory/engine/statusline.py",
        "$CLAUDE_PROJECT_DIR/.agent-factory/engine/apps/hooks/statusline.py",
    ),
]

stale_fixed = []

def _fix_stale_paths(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "command" and isinstance(v, str):
                new = v
                for old, new_seg in _PATH_FIXES:
                    new = new.replace(old, new_seg)
                if new != v:
                    obj[k] = new
                    stale_fixed.append(f"{path}/{k}")
            else:
                _fix_stale_paths(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _fix_stale_paths(item, f"{path}[{i}]")

_fix_stale_paths(existing)

added_keys = []
for key, value in tmpl.items():
    if key not in existing:
        existing[key] = value
        added_keys.append(key)

with open(out_path, 'w') as f:
    json.dump(existing, f, indent=2, ensure_ascii=False)
    f.write('\n')

if added_keys:
    print(f"ADDED:{','.join(added_keys)}")
if stale_fixed:
    print(f"FIXED:{len(stale_fixed)}")
if not added_keys and not stale_fixed:
    print("NOCHANGE")
PYEOF
)"

    local py_exit=$?
    if [ "$py_exit" -ne 0 ]; then
        rm -f "$tmp_result"
        print_error "JSON merge failed. Keep existing files."
        return 1
    fi

    # Revalidation
    if ! python3 -c 'import json, sys; json.load(open(sys.argv[1]))' "$tmp_result" 2>/dev/null; then
        rm -f "$tmp_result"
        print_error "Merge result JSON validation failed. Keep existing files."
        return 1
    fi

    mv "$tmp_result" "$existing_file" || { rm -f "$tmp_result"; return 1; }

    local fixed_count=""
    if echo "$py_output" | grep -q "^FIXED:"; then
        fixed_count="$(echo "$py_output" | grep "^FIXED:" | sed 's/^FIXED://')"
    fi
    if echo "$py_output" | grep -q "^ADDED:"; then
        local added_keys_str
        added_keys_str="$(echo "$py_output" | grep "^ADDED:" | sed 's/^ADDED://')"
        if [ -n "$fixed_count" ]; then
            print_success "settings.json merge: New key [${added_keys_str}] + stale path ${fixed_count} cases merged"
        else
            print_success "settings.json merge completed: Add new keys [${added_keys_str}]"
        fi
    elif [ -n "$fixed_count" ]; then
        print_success "settings.json stale path ${fixed_count} consistent (.claude.workflow/ → .agent-factory/)"
    else
        print_info "settings.json is already up to date (no new keys)"
    fi
    return 0
}

# --- Step 4: Create .claude/settings.json ---
setup_settings_json() {
    print_step "4" "Create .claude/settings.json"
    local settings_file=".claude/settings.json"
    [ -f "$settings_file" ] && { _merge_json_keys "$settings_file" "$TMPL_SETTINGS"; return 0; }
    [ ! -d ".claude" ] && { print_info "The .claude/ directory does not exist. Skip creating settings.json."; return 0; }
    cp "$TMPL_SETTINGS" "$settings_file"
    if python3 -c 'import json, sys; json.load(open(sys.argv[1]))' "$settings_file" 2>/dev/null; then
        print_success ".claude/settings.json creation completed (JSON validation passed)"
    else
        print_error ".claude/settings.json JSON validation failed. Please check the file."; return 1
    fi
}

# --- Merge Helper: KEY=VALUE key-wise merge ---
# Usage: _merge_kv_settings <existing file> <template file>
# Preserve existing KEY, add new KEY (including the previous comment block) that exists only in the template.
# Guaranteed idempotence: Skip if the same KEY already exists. Preserve existing files in case of error.
_merge_kv_settings() {
    local existing_file="$1" tmpl_file="$2"
    [ ! -f "$existing_file" ] || [ ! -f "$tmpl_file" ] && return 1

    local rename_pair old_key new_key tmp_rename
    local rename_pairs=(
        "AGENT_FACTORY_LLM_PROVIDER LLM_PROVIDER"
        "AGENT_FACTORY_SLACK_BOT_TOKEN SLACK_BOT_TOKEN"
        "AGENT_FACTORY_SLACK_CHANNEL_ID SLACK_CHANNEL_ID"
        "AGENT_FACTORY_SLACK_API_URL SLACK_API_URL"
        "AGENT_FACTORY_GIT_USER_NAME GIT_USER_NAME"
        "AGENT_FACTORY_GIT_USER_EMAIL GIT_USER_EMAIL"
        "AGENT_FACTORY_GITHUB_USERNAME GITHUB_USERNAME"
        "AGENT_FACTORY_SSH_KEY_GITHUB SSH_KEY_GITHUB"
        "AGENT_FACTORY_WORKFLOW_KEEP_COUNT WORKFLOW_KEEP_COUNT"
        "AGENT_FACTORY_CHAIN_MAX_RETRY CHAIN_MAX_RETRY"
        "AGENT_FACTORY_QUALITY_THRESHOLD QUALITY_THRESHOLD"
        "AGENT_FACTORY_ERROR_THRESHOLD ERROR_THRESHOLD"
        "AGENT_FACTORY_STALE_TTL_MINUTES STALE_TTL_MINUTES"
        "AGENT_FACTORY_ZOMBIE_TTL_HOURS ZOMBIE_TTL_HOURS"
        "AGENT_FACTORY_REPORT_TTL_HOURS REPORT_TTL_HOURS"
        "AGENT_FACTORY_WORK_NAME_MAX_LEN WORK_NAME_MAX_LEN"
        "AGENT_FACTORY_BANNER_WIDTH BANNER_WIDTH"
        "AGENT_FACTORY_REPO_URL REPO_URL"
        "AGENT_FACTORY_REQUIRED_PYTHON_MAJOR REQUIRED_PYTHON_MAJOR"
        "AGENT_FACTORY_REQUIRED_PYTHON_MINOR REQUIRED_PYTHON_MINOR"
        "CLAUDE_CODE_SLACK_BOT_TOKEN SLACK_BOT_TOKEN"
        "CLAUDE_CODE_SLACK_CHANNEL_ID SLACK_CHANNEL_ID"
        "CLAUDE_SLACK_API_URL SLACK_API_URL"
        "CLAUDE_CODE_GIT_USER_NAME GIT_USER_NAME"
        "CLAUDE_CODE_GIT_USER_EMAIL GIT_USER_EMAIL"
        "CLAUDE_CODE_GITHUB_USERNAME GITHUB_USERNAME"
        "CLAUDE_CODE_SSH_KEY_GITHUB SSH_KEY_GITHUB"
        "CLAUDE_WORKFLOW_KEEP_COUNT WORKFLOW_KEEP_COUNT"
        "CLAUDE_CHAIN_MAX_RETRY CHAIN_MAX_RETRY"
        "CLAUDE_QUALITY_THRESHOLD QUALITY_THRESHOLD"
        "CLAUDE_ERROR_THRESHOLD ERROR_THRESHOLD"
        "CLAUDE_STALE_TTL_MINUTES STALE_TTL_MINUTES"
        "CLAUDE_ZOMBIE_TTL_HOURS ZOMBIE_TTL_HOURS"
        "CLAUDE_REPORT_TTL_HOURS REPORT_TTL_HOURS"
        "CLAUDE_WORK_NAME_MAX_LEN WORK_NAME_MAX_LEN"
        "CLAUDE_BANNER_WIDTH BANNER_WIDTH"
        "CLAUDE_REPO_URL REPO_URL"
        "CLAUDE_REQUIRED_PYTHON_MAJOR REQUIRED_PYTHON_MAJOR"
        "CLAUDE_REQUIRED_PYTHON_MINOR REQUIRED_PYTHON_MINOR"
    )
    for rename_pair in "${rename_pairs[@]}"; do
        old_key="${rename_pair%% *}"
        new_key="${rename_pair##* }"
        if grep -q "^${old_key}=" "$existing_file" 2>/dev/null && ! grep -q "^${new_key}=" "$existing_file" 2>/dev/null; then
            tmp_rename="$(mktemp)" || return 1
            sed "s/^${old_key}=/${new_key}=/" "$existing_file" > "$tmp_rename" || { rm -f "$tmp_rename"; return 1; }
            mv "$tmp_rename" "$existing_file" || { rm -f "$tmp_rename"; return 1; }
        elif grep -q "^${old_key}=" "$existing_file" 2>/dev/null && grep -q "^${new_key}=" "$existing_file" 2>/dev/null; then
            tmp_rename="$(mktemp)" || return 1
            sed "/^${old_key}=/d" "$existing_file" > "$tmp_rename" || { rm -f "$tmp_rename"; return 1; }
            mv "$tmp_rename" "$existing_file" || { rm -f "$tmp_rename"; return 1; }
        fi
    done

    # Extract KEY list from existing file (start with uppercase letter + underscore)
    local existing_keys
    existing_keys="$(sed -n 's/^\([A-Z_][A-Z0-9_]*\)=.*/\1/p' "$existing_file" 2>/dev/null)"

    local tmp_append
    tmp_append="$(mktemp)" || return 1

    # Template traversal: Extract new KEY block (previous comment + KEY=VALUE)
    local pending_comments=()
    local added_count=0
    local line

    while IFS= read -r line || [ -n "$line" ]; do
        # KEY=VALUE line detection
        if echo "$line" | grep -qE '^[A-Z_][A-Z0-9_]+='; then
            local key
            key="$(echo "$line" | sed -n 's/^\([A-Z_][A-Z0-9_]*\)=.*/\1/p')"
            if echo "$existing_keys" | grep -qx "$key"; then
                # Existing → Skip, initialize accumulated annotations
                pending_comments=()
            else
                # New KEY → Previous comment block + KEY=VALUE line added
                for cmt in "${pending_comments[@]}"; do
                    echo "$cmt" >> "$tmp_append"
                done
                echo "$line" >> "$tmp_append"
                added_count=$((added_count + 1))
                pending_comments=()
            fi
            continue
        fi

        # Comments or blank lines: stacked for next KEY
        if echo "$line" | grep -q '^#' || [ -z "$line" ]; then
            pending_comments+=("$line")
        else
            # Other lines (export, etc.): matching the entire line
            if grep -qF "$line" "$existing_file" 2>/dev/null; then
                pending_comments=()
            else
                for cmt in "${pending_comments[@]}"; do
                    echo "$cmt" >> "$tmp_append"
                done
                echo "$line" >> "$tmp_append"
                added_count=$((added_count + 1))
                pending_comments=()
            fi
        fi
    done < "$tmpl_file"

    # Append to existing files only when new items are present
    if [ "$added_count" -gt 0 ]; then
        local tmp_result
        tmp_result="$(mktemp)" || { rm -f "$tmp_append"; return 1; }
        cat "$existing_file" > "$tmp_result"
        echo "" >> "$tmp_result"
        echo "# === Merge added ($(date +%Y%m%d)) ===" >> "$tmp_result"
        cat "$tmp_append" >> "$tmp_result"
        mv "$tmp_result" "$existing_file" || { rm -f "$tmp_result" "$tmp_append"; return 1; }
        print_success ".settings merge completed: ${added_count} new KEY added"
    else
        print_info ".settings is already up to date (no new KEY)"
    fi
    rm -f "$tmp_append"
    return 0
}

# --- Step 5: Create .agent-factory/.settings ---
generate_claude_settings() {
    print_step "5" "Create .agent-factory/.settings"
    local settings_file=".agent-factory/.settings"
    local env_file=".agent-factory/.env"
    # If .settings already exists, merge (just add new KEY)
    if [ -f "$settings_file" ]; then
        _merge_kv_settings "$settings_file" "$TMPL_CLAUDE_ENV"; return 0
    fi
    # If .settings does not exist and .env exists, copy .env to create .settings
    if [ -f "$env_file" ]; then
        cp "$env_file" "$settings_file"
        print_success ".agent-factory/.settings created (copied from .env) ($settings_file)"
        return 0
    fi
    # If neither exists, create one from a template
    cp "$TMPL_CLAUDE_ENV" "$settings_file"
    print_success ".agent-factory/.settings template creation completed ($settings_file)"
}

# --- Step 7: Update .gitignore ---
update_gitignore() {
    print_step "7" ".gitignore update"
    [ ! -f ".gitignore" ] && { touch ".gitignore"; print_success "Create .gitignore file"; }
    local added=0
    for entry in "${GITIGNORE_ENTRIES[@]}"; do
        if ! grep -qxF "$entry" ".gitignore" 2>/dev/null; then
            echo "$entry" >> ".gitignore"; print_success "Add to .gitignore: $entry"; added=$((added + 1))
        fi
    done
    if [ "$added" -eq 0 ]; then print_info "All required entries are already registered in .gitignore"
    else print_success "Completed adding ${added} items to .gitignore"; fi
}

# --- Step 8: Verify installation ---
verify_installation() {
    print_step "8" "Installation Verification"
    local failed=0
    # (a) python3 version verification
    if command -v python3 &>/dev/null; then
        print_success "python3 executable ($(python3 --version 2>&1))"
        if python3 -c "import sys; sys.exit(0 if (sys.version_info.major, sys.version_info.minor) >= ($REQUIRED_PYTHON_MAJOR, $REQUIRED_PYTHON_MINOR) else 1)" 2>/dev/null; then
            print_success "python3 version verification PASS (>= ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR})"
        else
            local current_ver
            current_ver="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
            print_error "python3 version verification FAIL: current ${current_ver}, minimum required ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
            failed=$((failed + 1))
        fi
    else
        print_error "python3 command not found"; failed=$((failed + 1))
    fi
    # (b) gh/claude verification (tmux is optional — don't fail without it)
    if command -v tmux &>/dev/null; then
        print_success "tmux executable (optional, $(tmux -V 2>/dev/null || echo 'version unknown'))"
    else
        print_warning "tmux command not found (optional — only tmux fallback path is disabled)"
    fi
    _verify_command "gh"   "gh CLI" || failed=$((failed + 1))
    if command -v claude &>/dev/null; then print_success "Claude command can be executed"
    else print_error "claude command not found"; failed=$((failed + 1)); fi
    # (d) .agent-factory/tickets/, .agent-factory/tickets/{todo,open,progress,review,done}/ directories exist
    local tickets_ok=true
    for dir in ".agent-factory/tickets" ".agent-factory/tickets/todo" ".agent-factory/tickets/open" ".agent-factory/tickets/progress" ".agent-factory/tickets/review" ".agent-factory/tickets/done"; do
        if [ ! -d "$dir" ]; then
            print_error "No required directory: $dir"; tickets_ok=false; failed=$((failed + 1))
        fi
    done
    [ "$tickets_ok" = true ] && print_success "Check the existence of .agent-factory/tickets/, .agent-factory/tickets/{todo,open,progress,review,done}/ directories"
    # (e) Existence of .agent-factory/.settings or .agent-factory/.env files
    if [ -f ".agent-factory/.settings" ]; then
        print_success "Check existence of .agent-factory/.settings file"
    elif [ -f ".agent-factory/.env" ]; then
        print_success "Check for existence of .agent-factory/.env file (fallback)"
    else
        print_error "Both .agent-factory/.settings and .agent-factory/.env files are missing"
        failed=$((failed + 1))
    fi
    # (f) .claude/ directory exists
    if [ -d ".claude" ]; then print_success "Verify existence of .claude/ directory"
    else print_error ".claude/ directory does not exist"; failed=$((failed + 1)); fi
    # (g) Existence of aliases file and registration of source line in shell rc
    local aliases_file="$HOME/.claude.aliases"
    detect_shell_rc
    local shell_rc="$DETECTED_SHELL_RC"
    if [ -f "$aliases_file" ] && grep -q ".claude.aliases" "$shell_rc" 2>/dev/null; then
        print_success "Check the existence of the aliases file and the registration of the source line in the shell configuration file."
    else
        [ ! -f "$aliases_file" ] && print_error "No aliases file: $aliases_file"
        grep -q ".claude.aliases" "$shell_rc" 2>/dev/null || print_error "Missing source line in shell configuration file: $shell_rc"
        failed=$((failed + 1))
    fi
    # (h) Confirm registration of .gitignore required items
    local gitignore_ok=true
    for entry in "${GITIGNORE_ENTRIES[@]}"; do
        if ! grep -qxF "$entry" ".gitignore" 2>/dev/null; then
            print_error "Not registered in .gitignore: $entry"; gitignore_ok=false; failed=$((failed + 1))
        fi
    done
    [ "$gitignore_ok" = true ] && print_success "Confirm registration of all .gitignore required items"
    # Summary of Results
    echo ""
    if [ "$failed" -eq 0 ]; then
        printf '%s  ========================================%s\n' "${GREEN}" "${NC}"
        printf '%s Passed all verification items!%s\\n' "${GREEN}" "${NC}"
        printf '%s  ========================================%s\n' "${GREEN}" "${NC}"
    else
        printf '%s  ========================================%s\n' "${YELLOW}" "${NC}"
        printf '%s Warning: Problems found in %s verification items%s\\n' "${YELLOW}" "${failed}" "${NC}"
        printf '%s  ========================================%s\n' "${YELLOW}" "${NC}"
    fi
}

# --- Create Board URL ---
# It uses the same MD5 hash-based port determination formula as resolve_port() in server.py.
# Conflict sequential search (is_port_in_use) only uses the first deterministic port because the server is not running.
generate_board_url() {
    local project_root
    project_root="$(pwd)"
    local url_file="${SCRIPT_DIR}/.board.url"
    local port
    port="$(python3 -c "
import hashlib
project_root = '$project_root'
PORT_RANGE_START = 9900
range_size = 100
hash_bytes = hashlib.md5(project_root.encode()).digest()
hash_int = int.from_bytes(hash_bytes[:4], byteorder='big')
port = PORT_RANGE_START + (hash_int % range_size)
print(port)
")"
    local base="http://127.0.0.1:${port}"
    printf '%s/index.html\n%s/terminal.html' "${base}" "${base}" > "${url_file}"
    print_success "Board URL creation completed"
    printf '    %s%s/index.html%s\n'    "${BOLD_CYAN}" "${base}" "${NC}"
    printf '    %s%s/terminal.html%s\n' "${BOLD_CYAN}" "${base}" "${NC}"
}

# --- main ---
main() {
    trap 'print_error "Initialization failed. Please check the error message above."' EXIT
    echo ""
    printf '%s=================================================%s\n' "${GREEN}" "${NC}"
    printf '%s Initialize Agent Factory environment%s\\n' "${GREEN}" "${NC}"
    printf '%s=================================================%s\n' "${GREEN}" "${NC}"
    command -v git  &>/dev/null || { print_error "git is not installed. Please install git first.";  exit 1; }
    command -v curl &>/dev/null || { print_error "curl is not installed. Please install curl first."; exit 1; }
    print_success "Pre-dependency check completed (git, curl)"
    validate_templates
    detect_os
    install_claude_code
    install_dependencies
    create_directories_and_files
    setup_settings_json
    generate_claude_settings
    setup_shell_aliases
    update_gitignore
    verify_installation
    generate_board_url
    trap - EXIT
    detect_shell_rc
    local url_file="${SCRIPT_DIR}/.board.url"
    echo ""
    printf '%s=================================================%s\n' "${GREEN}" "${NC}"
    printf '%s Initialization completed!%s\\n' "${GREEN}" "${NC}"
    printf '%s Open a new terminal or run '\''source %s'\''%s\n' "${GREEN}" "${DETECTED_SHELL_RC}" "${NC}"
    if [ -f "${url_file}" ]; then
        while IFS= read -r _board_line; do
            [ -z "${_board_line}" ] && continue
            printf '  Board:  %s%s%s\n' "${BOLD_CYAN}" "${_board_line}" "${NC}"
        done < "${url_file}"
    fi
    printf '%s=================================================%s\n' "${GREEN}" "${NC}"
    echo ""
}

main "$@"
