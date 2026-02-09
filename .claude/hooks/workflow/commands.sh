#!/bin/bash
# commands.sh - 사용 가능한 cc:* 명령어 목록을 동적 스캔하여 출력
#
# 사용법:
#   wf-commands
#   bash .claude/hooks/workflow/commands.sh
#
# .claude/commands/cc/*.md 파일의 frontmatter description을 파싱하여
# 컬러 테이블 형식으로 터미널에 출력합니다.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
COMMANDS_DIR="${PROJECT_ROOT}/.claude/commands/cc"

# --- 색상 코드 ---
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
GRAY='\033[0;90m'

# --- 명령어 디렉토리 확인 ---
if [ ! -d "$COMMANDS_DIR" ]; then
    echo -e "${YELLOW}[WARN] 명령어 디렉토리가 존재하지 않습니다: ${COMMANDS_DIR}${RESET}"
    exit 1
fi

# --- 명령어 파일 스캔 ---
md_files=()
while IFS= read -r -d '' f; do
    md_files+=("$f")
done < <(find "$COMMANDS_DIR" -maxdepth 1 -name '*.md' -type f -print0 | sort -z)

if [ ${#md_files[@]} -eq 0 ]; then
    echo -e "${YELLOW}[WARN] 명령어 파일이 없습니다: ${COMMANDS_DIR}/*.md${RESET}"
    exit 0
fi

# --- 명령어 정보 수집 ---
# 배열: "명령어이름|설명" 형식
entries=()
max_name_len=0

for md_file in "${md_files[@]}"; do
    filename="$(basename "$md_file" .md)"
    cmd_name="cc:${filename}"

    # frontmatter에서 description 추출
    description=""
    if head -1 "$md_file" | grep -q '^---$'; then
        description=$(sed -n '2,/^---$/p' "$md_file" | grep '^description:' | sed 's/^description:[[:space:]]*//' | head -1)
    fi

    [ -z "$description" ] && description="(설명 없음)"

    entries+=("${cmd_name}|${description}")

    name_len=${#cmd_name}
    if [ "$name_len" -gt "$max_name_len" ]; then
        max_name_len=$name_len
    fi
done

# 패딩 계산 (최소 열 너비)
col_width=$((max_name_len + 4))
[ "$col_width" -lt 20 ] && col_width=20

# 구분선
separator_width=$((col_width + 50))
separator=$(printf '%.0s─' $(seq 1 $separator_width))

# --- 테이블 출력 ---
echo ""
echo -e "  ${BOLD}사용 가능한 명령어${RESET}  ${DIM}(${#entries[@]}개)${RESET}"
echo -e "  ${DIM}${separator}${RESET}"

# 헤더
printf "  ${BOLD}${CYAN}%-${col_width}s${RESET} ${BOLD}%s${RESET}\n" "명령어" "설명"
echo -e "  ${DIM}${separator}${RESET}"

# 본문
for entry in "${entries[@]}"; do
    cmd_name="${entry%%|*}"
    description="${entry#*|}"
    printf "  ${GREEN}%-${col_width}s${RESET} %s\n" "$cmd_name" "$description"
done

echo -e "  ${DIM}${separator}${RESET}"
echo -e "  ${DIM}실행: /cc:<명령어> <요청내용>${RESET}"
echo ""
