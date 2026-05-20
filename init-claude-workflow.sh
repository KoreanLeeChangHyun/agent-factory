#!/bin/bash
set -euo pipefail
# ==============================================================================
# init-claude-workflow.sh — 부트스트랩 스크립트
# 원격 저장소를 1회 클론하여 .claude/ + .agent-factory/ 를 설치한 뒤 build.sh 실행
# 사용법: curl -fsSL https://raw.githubusercontent.com/KoreanLeeChangHyun/claude-workflow/main/init-claude-workflow.sh | bash
# ==============================================================================

REPO_URL="https://github.com/KoreanLeeChangHyun/claude-workflow.git"
GREEN=$'\033[0;32m'; RED=$'\033[0;31m'; YELLOW=$'\033[0;33m'; CYAN=$'\033[0;36m'; NC=$'\033[0m'

echo ""
printf '%s=================================================%s\n' "${GREEN}" "${NC}"
printf '%s  Claude Code 워크플로우 부트스트랩%s\n' "${GREEN}" "${NC}"
printf '%s=================================================%s\n' "${GREEN}" "${NC}"

# 사전 의존성 확인
for cmd in git curl python3; do
    command -v "$cmd" &>/dev/null || { printf '%s  ✗ %s가 설치되어 있지 않습니다%s\n' "${RED}" "$cmd" "${NC}"; exit 1; }
done

# 임시 디렉터리에 클론 (1회)
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

printf '%s  → 원격 저장소 클론 중...%s\n' "${YELLOW}" "${NC}"
if ! git clone --depth 1 "$REPO_URL" "$tmp_dir/claude-workflow" 2>/dev/null; then
    printf '%s  ✗ 원격 저장소 클론 실패%s\n' "${RED}" "${NC}"; exit 1
fi
printf '%s  ✓ 클론 완료%s\n' "${CYAN}" "${NC}"

SRC="$tmp_dir/claude-workflow"

# --- git 초기화 + develop 브랜치 ---
if [ ! -d ".git" ]; then
    git init -q
    printf '%s  ✓ git init 완료%s\n' "${CYAN}" "${NC}"
fi
current_branch="$(git branch --show-current 2>/dev/null || true)"
if [ -z "$current_branch" ] || ! git rev-parse HEAD &>/dev/null; then
    # 초기 커밋이 없는 경우 (브랜치명만 있고 실제 ref 없음)
    git checkout -b develop -q 2>/dev/null || true
    printf '%s  ✓ develop 브랜치 생성%s\n' "${CYAN}" "${NC}"
elif [ "$current_branch" != "develop" ]; then
    if ! git show-ref --verify --quiet refs/heads/develop 2>/dev/null; then
        git branch develop -q
        printf '%s  ✓ develop 브랜치 생성%s\n' "${CYAN}" "${NC}"
    fi
    git checkout develop -q
    printf '%s  ✓ develop 브랜치로 전환%s\n' "${CYAN}" "${NC}"
fi

# --- .claude/ 디렉터리 교체 (프로젝트 데이터 보존) ---
if [ ! -d "$SRC/.claude" ]; then
    printf '%s  ✗ 클론된 저장소에 .claude/ 가 없습니다%s\n' "${RED}" "${NC}"; exit 1
fi
[ -L ".claude" ] && { printf '%s  → .claude가 심볼릭 링크입니다. 제거합니다.%s\n' "${YELLOW}" "${NC}"; rm -f ".claude"; }

# 프로젝트 데이터 백업
claude_preserve_dirs=("rules/project")
claude_preserve_files=("settings.json" "settings.local.json")
for cpd in "${claude_preserve_dirs[@]}"; do
    [ -d ".claude/$cpd" ] && { mkdir -p "$tmp_dir/_claude_preserve_$(dirname "$cpd")"; cp -r ".claude/$cpd" "$tmp_dir/_claude_preserve_$cpd"; }
done
for cpf in "${claude_preserve_files[@]}"; do
    [ -f ".claude/$cpf" ] && cp ".claude/$cpf" "$tmp_dir/_claude_preserve_$cpf"
done
# my-* 스킬 백업
if [ -d ".claude/skills" ]; then
    for myskill in .claude/skills/my-*/; do
        [ -d "$myskill" ] && { mkdir -p "$tmp_dir/_claude_preserve_skills"; cp -r "$myskill" "$tmp_dir/_claude_preserve_skills/"; }
    done
fi

rm -rf ".claude.new"
if ! cp -r "$SRC/.claude" ".claude.new"; then
    printf '%s  ✗ .claude 디렉터리 복사 실패%s\n' "${RED}" "${NC}"; exit 1
fi
rm -rf ".claude"; mv ".claude.new" ".claude"

# 프로젝트 데이터 복원
for cpd in "${claude_preserve_dirs[@]}"; do
    [ -d "$tmp_dir/_claude_preserve_$cpd" ] && { mkdir -p ".claude/$(dirname "$cpd")"; cp -r "$tmp_dir/_claude_preserve_$cpd" ".claude/$cpd"; }
done
for cpf in "${claude_preserve_files[@]}"; do
    [ -f "$tmp_dir/_claude_preserve_$cpf" ] && cp "$tmp_dir/_claude_preserve_$cpf" ".claude/$cpf"
done
if [ -d "$tmp_dir/_claude_preserve_skills" ]; then
    for myskill in "$tmp_dir/_claude_preserve_skills"/my-*/; do
        [ -d "$myskill" ] && cp -r "$myskill" ".claude/skills/"
    done
fi
printf '%s  ✓ .claude/ 디렉터리 교체 완료 (프로젝트 데이터 보존)%s\n' "${CYAN}" "${NC}"

# --- .agent-factory/ 디렉터리 교체 (사용자 데이터 보존) ---
if [ ! -d "$SRC/.agent-factory" ]; then
    printf '%s  ✗ 클론된 저장소에 .agent-factory/ 가 없습니다%s\n' "${RED}" "${NC}"; exit 1
fi

RUNTIME_DIR=".agent-factory"
OLD_RUNTIME_DIR=".claude-organic"

# M2 one-time migration: older installs used .claude-organic as the runtime
# root. Preserve user data by moving it to the canonical .agent-factory root
# before the normal update path runs. Application code must not search both
# roots; this bootstrap branch is the only compatibility layer.
if [ ! -d "$RUNTIME_DIR" ] && [ -d "$OLD_RUNTIME_DIR" ]; then
    mv "$OLD_RUNTIME_DIR" "$RUNTIME_DIR"
    printf '%s  ✓ 기존 .claude-organic/ 사용자 데이터를 .agent-factory/ 로 이전%s\n' "${CYAN}" "${NC}"
fi

preserve_dirs=("tickets" "runs" "roadmap" "memo" "worktrees" "board/data" "logs" "staging")
preserve_files=(".settings" ".env" ".version" ".board.url" "build.url" ".last-session-id")

if [ -d "$RUNTIME_DIR" ]; then
    # 업데이트 설치: 사용자 데이터 백업 후 교체
    for pd in "${preserve_dirs[@]}"; do
        [ -d "$RUNTIME_DIR/$pd" ] && { mkdir -p "$tmp_dir/_preserve_$(dirname "$pd")"; cp -r "$RUNTIME_DIR/$pd" "$tmp_dir/_preserve_$pd"; }
    done
    for pf in "${preserve_files[@]}"; do
        [ -f "$RUNTIME_DIR/$pf" ] && cp "$RUNTIME_DIR/$pf" "$tmp_dir/_preserve_$pf"
    done
    rm -rf ".agent-factory.new"
    cp -r "$SRC/.agent-factory" ".agent-factory.new"
    rm -rf "$RUNTIME_DIR"; mv ".agent-factory.new" "$RUNTIME_DIR"
    # 사용자 데이터 복원
    for pd in "${preserve_dirs[@]}"; do
        [ -d "$tmp_dir/_preserve_$pd" ] && { rm -rf "$RUNTIME_DIR/$pd"; mkdir -p "$RUNTIME_DIR/$(dirname "$pd")"; mv "$tmp_dir/_preserve_$pd" "$RUNTIME_DIR/$pd"; }
    done
    for pf in "${preserve_files[@]}"; do
        [ -f "$tmp_dir/_preserve_$pf" ] && mv "$tmp_dir/_preserve_$pf" "$RUNTIME_DIR/$pf"
    done
    printf '%s  ✓ .agent-factory/ 업데이트 완료 (사용자 데이터 보존)%s\n' "${CYAN}" "${NC}"
else
    # 신규 설치: 전체 복사
    cp -r "$SRC/.agent-factory" "$RUNTIME_DIR"
    printf '%s  ✓ .agent-factory/ 신규 설치 완료%s\n' "${CYAN}" "${NC}"
fi

# 실행 권한 부여 — .sh 파일 + bin wrapper (확장자 없는 flow-* 실행 파일)
find ".claude/" -name '*.sh' -exec chmod +x {} +
find ".agent-factory/" -name '*.sh' -exec chmod +x {} + 2>/dev/null || true
[ -d ".agent-factory/bin" ] && find ".agent-factory/bin" -type f -exec chmod +x {} +
printf '%s  ✓ chmod +x 완료 (.sh + bin wrapper)%s\n' "${CYAN}" "${NC}"

# --- .gitignore 자동 등록 ---
# .claude/ + .agent-factory/ 는 워크플로우 런타임 디렉터리이므로 외부 프로젝트
# 의 git tracking 에서 제외한다. 본 저장소(또는 fork)에서는 이미 tracking
# 중이므로 안전하게 skip.
if git ls-files --error-unmatch .claude > /dev/null 2>&1 || \
   git ls-files --error-unmatch .agent-factory > /dev/null 2>&1; then
    printf '%s  → .claude/·.agent-factory/ 이미 tracking 중 — .gitignore 갱신 skip%s\n' "${YELLOW}" "${NC}"
else
    GITIGNORE=".gitignore"
    touch "$GITIGNORE"
    changed=0
    for entry in ".claude/" ".agent-factory/"; do
        if ! grep -qxF "$entry" "$GITIGNORE"; then
            [ -s "$GITIGNORE" ] && [ "$(tail -c1 "$GITIGNORE")" != $'\n' ] && echo "" >> "$GITIGNORE"
            echo "$entry" >> "$GITIGNORE"
            changed=1
        fi
    done
    if [ "$changed" = 1 ]; then
        printf '%s  ✓ .gitignore 갱신 (.claude/, .agent-factory/)%s\n' "${CYAN}" "${NC}"
    else
        printf '%s  ✓ .gitignore 이미 등록됨%s\n' "${CYAN}" "${NC}"
    fi
fi

# build.sh 실행 (클론 인자 없이)
BUILD_SH=".agent-factory/build.sh"
if [ ! -f "$BUILD_SH" ]; then
    printf '%s  ✗ build.sh를 찾을 수 없습니다%s\n' "${RED}" "${NC}"; exit 1
fi

printf '%s  → build.sh 실행...%s\n' "${YELLOW}" "${NC}"
echo ""
bash "$BUILD_SH"

# --- Board 서버 기동 (백그라운드 데몬) ---
BOARD_SERVER=".agent-factory/board/server.py"
if [ -f "$BOARD_SERVER" ]; then
    # 기존 좀비 board 서버 감지 → 종료
    # 서버 자체에 중복 실행 방지 로직이 있어, 좀비가 살아있으면 새 인스턴스가
    # LISTEN 충돌로 즉시 die → 옛 코드/옛 webroot 가 그대로 유지되는 회귀 차단.
    if [ -f ".agent-factory/.board.url" ] && command -v lsof &>/dev/null; then
        OLD_PORT="$(head -1 .agent-factory/.board.url | sed -E 's|.*:([0-9]+)/.*|\1|')"
        if [ -n "$OLD_PORT" ]; then
            OLD_PID="$(lsof -tiTCP:"$OLD_PORT" -sTCP:LISTEN 2>/dev/null | head -1)"
            if [ -n "$OLD_PID" ]; then
                kill "$OLD_PID" 2>/dev/null && sleep 1
                printf '%s  → 기존 board 서버(PID %s) 종료 후 재기동%s\n' "${YELLOW}" "${OLD_PID}" "${NC}"
            fi
        fi
    fi
    printf '%s  → Board 서버 기동 중...%s\n' "${YELLOW}" "${NC}"
    nohup python3 "$BOARD_SERVER" >/dev/null 2>&1 &
    disown
    printf '%s  ✓ Board 서버 기동 완료 (백그라운드)%s\n' "${CYAN}" "${NC}"
fi
