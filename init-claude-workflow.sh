#!/bin/bash
set -euo pipefail
# ==============================================================================
# init-claude-workflow.sh — 부트스트랩 스크립트
# 원격 저장소를 1회 클론하여 .claude/ + .claude.workflow/ 를 설치한 뒤 build.sh 실행
# 사용법: curl -fsSL https://raw.githubusercontent.com/KoreanLeeChangHyun/claude-workflow/main/init-claude-workflow.sh | bash
# ==============================================================================

REPO_URL="https://github.com/KoreanLeeChangHyun/claude-workflow.git"
GREEN=$'\033[0;32m'; RED=$'\033[0;31m'; YELLOW=$'\033[0;33m'; NC=$'\033[0m'

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
printf '%s  ✓ 클론 완료%s\n' "${GREEN}" "${NC}"

SRC="$tmp_dir/claude-workflow"

# --- git 초기화 + develop 브랜치 ---
if [ ! -d ".git" ]; then
    git init -q
    printf '%s  ✓ git init 완료%s\n' "${GREEN}" "${NC}"
fi
current_branch="$(git branch --show-current 2>/dev/null || true)"
if [ -z "$current_branch" ]; then
    # 초기 커밋이 없는 경우
    git checkout -b develop -q 2>/dev/null || true
    printf '%s  ✓ develop 브랜치 생성%s\n' "${GREEN}" "${NC}"
elif [ "$current_branch" != "develop" ]; then
    if ! git show-ref --verify --quiet refs/heads/develop 2>/dev/null; then
        git branch develop -q
        printf '%s  ✓ develop 브랜치 생성%s\n' "${GREEN}" "${NC}"
    fi
    git checkout develop -q
    printf '%s  ✓ develop 브랜치로 전환%s\n' "${GREEN}" "${NC}"
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
printf '%s  ✓ .claude/ 디렉터리 교체 완료 (프로젝트 데이터 보존)%s\n' "${GREEN}" "${NC}"

# --- .claude.workflow/ 디렉터리 교체 (사용자 데이터 보존) ---
if [ ! -d "$SRC/.claude.workflow" ]; then
    printf '%s  ✗ 클론된 저장소에 .claude.workflow/ 가 없습니다%s\n' "${RED}" "${NC}"; exit 1
fi

preserve_dirs=("kanban" "workflow" "dashboard" "edit")
preserve_files=(".settings" ".env" ".version" ".board.url" "build.url")

if [ -d ".claude.workflow" ]; then
    # 업데이트 설치: 사용자 데이터 백업 후 교체
    for pd in "${preserve_dirs[@]}"; do
        [ -d ".claude.workflow/$pd" ] && cp -r ".claude.workflow/$pd" "$tmp_dir/_preserve_$pd"
    done
    for pf in "${preserve_files[@]}"; do
        [ -f ".claude.workflow/$pf" ] && cp ".claude.workflow/$pf" "$tmp_dir/_preserve_$pf"
    done
    rm -rf ".claude.workflow.new"
    cp -r "$SRC/.claude.workflow" ".claude.workflow.new"
    rm -rf ".claude.workflow"; mv ".claude.workflow.new" ".claude.workflow"
    # 사용자 데이터 복원
    for pd in "${preserve_dirs[@]}"; do
        [ -d "$tmp_dir/_preserve_$pd" ] && { rm -rf ".claude.workflow/$pd"; mv "$tmp_dir/_preserve_$pd" ".claude.workflow/$pd"; }
    done
    for pf in "${preserve_files[@]}"; do
        [ -f "$tmp_dir/_preserve_$pf" ] && mv "$tmp_dir/_preserve_$pf" ".claude.workflow/$pf"
    done
    printf '%s  ✓ .claude.workflow/ 업데이트 완료 (사용자 데이터 보존)%s\n' "${GREEN}" "${NC}"
else
    # 신규 설치: 전체 복사
    cp -r "$SRC/.claude.workflow" ".claude.workflow"
    printf '%s  ✓ .claude.workflow/ 신규 설치 완료%s\n' "${GREEN}" "${NC}"
fi

# .sh 파일 실행 권한 부여
find ".claude/" -name '*.sh' -exec chmod +x {} +
find ".claude.workflow/" -name '*.sh' -exec chmod +x {} + 2>/dev/null || true
printf '%s  ✓ .sh 파일 chmod +x 완료%s\n' "${GREEN}" "${NC}"

# build.sh 실행 (클론 인자 없이)
BUILD_SH=".claude.workflow/build.sh"
if [ ! -f "$BUILD_SH" ]; then
    printf '%s  ✗ build.sh를 찾을 수 없습니다%s\n' "${RED}" "${NC}"; exit 1
fi

printf '%s  → build.sh 실행...%s\n' "${YELLOW}" "${NC}"
echo ""
bash "$BUILD_SH"

# --- Board 서버 기동 ---
BOARD_SERVER=".claude.workflow/board/server.py"
if [ -f "$BOARD_SERVER" ]; then
    printf '%s  → Board 서버 기동 중...%s\n' "${YELLOW}" "${NC}"
    python3 "$BOARD_SERVER" &>/dev/null
    printf '%s  ✓ Board 서버 기동 완료%s\n' "${GREEN}" "${NC}"
fi
