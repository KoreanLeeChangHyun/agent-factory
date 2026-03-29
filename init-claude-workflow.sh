#!/bin/bash
set -euo pipefail
# ==============================================================================
# init-claude-workflow.sh — 부트스트랩 스크립트
# 원격 저장소를 클론하여 .claude/ + .claude.workflow/ 를 설치한 뒤 build.sh 실행
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

# 임시 디렉터리에 클론
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

printf '%s  → 원격 저장소 클론 중...%s\n' "${YELLOW}" "${NC}"
if ! git clone --depth 1 "$REPO_URL" "$tmp_dir/claude-workflow" 2>/dev/null; then
    printf '%s  ✗ 원격 저장소 클론 실패%s\n' "${RED}" "${NC}"; exit 1
fi
printf '%s  ✓ 클론 완료%s\n' "${GREEN}" "${NC}"

SRC="$tmp_dir/claude-workflow"

# .claude.workflow/ 가 없으면 클론에서 복사 (build.sh + init/ 포함)
if [ ! -d ".claude.workflow" ]; then
    if [ -d "$SRC/.claude.workflow" ]; then
        cp -r "$SRC/.claude.workflow" ".claude.workflow"
        printf '%s  ✓ .claude.workflow/ 디렉터리 설치 완료%s\n' "${GREEN}" "${NC}"
    else
        printf '%s  ✗ 클론된 저장소에 .claude.workflow/ 가 없습니다%s\n' "${RED}" "${NC}"; exit 1
    fi
else
    # init/ 디렉터리만 갱신 (build.sh 실행에 필요)
    if [ -d "$SRC/.claude.workflow/init" ]; then
        rm -rf ".claude.workflow/init"
        cp -r "$SRC/.claude.workflow/init" ".claude.workflow/init"
    fi
    # build.sh 갱신
    if [ -f "$SRC/.claude.workflow/build.sh" ]; then
        cp "$SRC/.claude.workflow/build.sh" ".claude.workflow/build.sh"
    fi
    printf '%s  ✓ .claude.workflow/init + build.sh 갱신 완료%s\n' "${GREEN}" "${NC}"

    # 구 버전 디렉터리 감지 (마이그레이션 필요 여부 안내)
    _legacy_detected=0
    for _legacy_dir in ".kanban" ".dashboard" ".workflow"; do
        [ -d "$_legacy_dir" ] && _legacy_detected=1 && break
    done
    if [ "$_legacy_detected" -eq 1 ]; then
        printf '%s  ⚠ 마이그레이션이 필요한 이전 버전이 감지되었습니다 (.kanban/.dashboard/.workflow)%s\n' "${YELLOW}" "${NC}"
        printf '%s    build.sh가 자동으로 마이그레이션을 수행합니다.%s\n' "${YELLOW}" "${NC}"
    fi
fi

# build.sh 실행
BUILD_SH=".claude.workflow/build.sh"
if [ ! -f "$BUILD_SH" ]; then
    printf '%s  ✗ build.sh를 찾을 수 없습니다%s\n' "${RED}" "${NC}"; exit 1
fi

chmod +x "$BUILD_SH"
printf '%s  → build.sh 실행...%s\n' "${YELLOW}" "${NC}"
echo ""
bash "$BUILD_SH"
