#!/bin/bash
# init-clear.sh - 작업 내역 클리어 스크립트
# 사용법: ./init-clear.sh <list|execute>
#
# 서브커맨드:
#   list    - 삭제 대상 목록 및 크기 출력 (미리보기)
#   execute - 실제 삭제 실행
#
# 삭제 대상:
#   .workflow/  - 워크플로우 서브디렉토리 내용 (registry.json 보존)
#   .prompt/    - 프롬프트 파일 (history.md, prompt.txt 등)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# .workflow 루트에서 보존할 파일 목록 (날짜 디렉토리만 삭제 대상)
# 실제 워크플로우 디렉토리 구조: .workflow/YYYYMMDD-HHMMSS/<workName>/<command>/
# glob 패턴 [0-9]*은 YYYYMMDD-HHMMSS 디렉토리를 매칭하며, rm -rf가 중첩 하위를 재귀 삭제
WORKFLOW_ROOT="${PROJECT_ROOT}/.workflow"

# --- 유틸리티 함수 ---

# 디렉토리/파일 크기를 사람이 읽기 쉬운 형태로 반환
human_size() {
    local bytes="$1"
    if [ "$bytes" -ge 1073741824 ]; then
        echo "$(( bytes / 1073741824 ))G"
    elif [ "$bytes" -ge 1048576 ]; then
        echo "$(( bytes / 1048576 ))M"
    elif [ "$bytes" -ge 1024 ]; then
        echo "$(( bytes / 1024 ))K"
    else
        echo "${bytes}B"
    fi
}

# 디렉토리 내 파일 수 계산 (재귀)
count_files() {
    local dir="$1"
    if [ -d "$dir" ]; then
        find "$dir" -type f 2>/dev/null | wc -l | tr -d ' '
    else
        echo "0"
    fi
}

# 디렉토리 크기 계산 (바이트)
dir_size_bytes() {
    local dir="$1"
    if [ -d "$dir" ] && [ -n "$(ls -A "$dir" 2>/dev/null)" ]; then
        du -sk "$dir" 2>/dev/null | awk '{print $1 * 1024}'
    else
        echo "0"
    fi
}

# --- list 서브커맨드 ---

cmd_list() {
    local total_files=0
    local total_bytes=0
    local has_content=false

    echo "=== 삭제 대상 목록 ==="
    echo ""

    # 1. .workflow 날짜 디렉토리 (YYYYMMDD-* 패턴)
    echo "[.workflow/]"
    if [ -d "$WORKFLOW_ROOT" ]; then
        for target in "$WORKFLOW_ROOT"/[0-9]*; do
            if [ -d "$target" ]; then
                local dirname
                dirname=$(basename "$target")
                local fcount
                fcount=$(count_files "$target")
                local bytes
                bytes=$(dir_size_bytes "$target")
                local hsize
                hsize=$(human_size "$bytes")
                echo "  .workflow/${dirname}/  (${fcount}개 파일, ${hsize})"
                total_files=$(( total_files + fcount ))
                total_bytes=$(( total_bytes + bytes ))
                has_content=true
            fi
        done
    fi

    # 2. .prompt 디렉토리
    echo ""
    echo "[.prompt/]"
    local prompt_dir="${PROJECT_ROOT}/.prompt"
    if [ -d "$prompt_dir" ] && [ -n "$(ls -A "$prompt_dir" 2>/dev/null)" ]; then
        local fcount
        fcount=$(count_files "$prompt_dir")
        local bytes
        bytes=$(dir_size_bytes "$prompt_dir")
        local hsize
        hsize=$(human_size "$bytes")
        echo "  .prompt/  (${fcount}개 파일, ${hsize})"
        # 개별 파일 나열
        for f in "$prompt_dir"/*; do
            if [ -f "$f" ]; then
                local fname
                fname=$(basename "$f")
                local fbytes
                fbytes=$(wc -c < "$f" 2>/dev/null | tr -d ' ' || echo "0")
                local fhsize
                fhsize=$(human_size "$fbytes")
                echo "    - ${fname} (${fhsize})"
            fi
        done
        total_files=$(( total_files + fcount ))
        total_bytes=$(( total_bytes + bytes ))
        has_content=true
    else
        echo "  (비어있음)"
    fi

    # 합계
    echo ""
    echo "---"
    local total_hsize
    total_hsize=$(human_size "$total_bytes")
    echo "합계: ${total_files}개 파일, ${total_hsize}"

    if [ "$has_content" = false ]; then
        echo ""
        echo "삭제할 내용이 없습니다."
    fi
}

# --- execute 서브커맨드 ---

cmd_execute() {
    local deleted_count=0

    echo "=== 작업 내역 삭제 실행 ==="
    echo ""

    # 1. .workflow 날짜 디렉토리 삭제 (YYYYMMDD-* 패턴, 루트 파일 보존)
    echo "[.workflow/]"
    if [ -d "$WORKFLOW_ROOT" ]; then
        for target in "$WORKFLOW_ROOT"/[0-9]*; do
            if [ -d "$target" ]; then
                local dirname
                dirname=$(basename "$target")
                rm -rf "${target:?}"
                echo "  삭제 완료: .workflow/${dirname}/"
                deleted_count=$(( deleted_count + 1 ))
            fi
        done
    fi

    # 2. .prompt 파일 삭제 (history.md 보존)
    echo ""
    echo "[.prompt/]"
    local prompt_dir="${PROJECT_ROOT}/.prompt"
    if [ -d "$prompt_dir" ] && [ -n "$(ls -A "$prompt_dir" 2>/dev/null)" ]; then
        # history.md 임시 백업
        [ -f "${prompt_dir}/history.md" ] && cp "${prompt_dir}/history.md" /tmp/_history_md_backup
        rm -rf "${prompt_dir:?}"/*
        # history.md 복원
        [ -f /tmp/_history_md_backup ] && mv /tmp/_history_md_backup "${prompt_dir}/history.md"
        echo "  삭제 완료: .prompt/* (history.md 보존)"
        deleted_count=$(( deleted_count + 1 ))
    else
        echo "  (비어있음, 스킵)"
    fi

    # 3. .workflow/registry.json 레지스트리 초기화
    echo ""
    echo "[.workflow/registry.json]"
    local registry_file="${PROJECT_ROOT}/.workflow/registry.json"
    if [ -f "$registry_file" ]; then
        # 파일은 보존하되 내용을 빈 레지스트리로 초기화
        echo '{}' > "$registry_file"
        echo "  초기화 완료: .workflow/registry.json ({})"
    else
        # 파일이 없으면 생성
        mkdir -p "$(dirname "$registry_file")"
        echo '{}' > "$registry_file"
        echo "  생성 완료: .workflow/registry.json ({})"
    fi

    echo ""
    echo "---"
    echo "삭제 완료: ${deleted_count}개 디렉토리 정리됨"
    echo ""
    echo "초기화된 파일:"
    echo "  - .workflow/registry.json ({})"
}

# --- 메인 ---

if [ $# -lt 1 ]; then
    echo "사용법: $0 <list|execute>"
    echo ""
    echo "서브커맨드:"
    echo "  list     삭제 대상 목록 및 크기 출력 (미리보기)"
    echo "  execute  실제 삭제 실행"
    exit 1
fi

SUBCOMMAND="$1"
shift

case "$SUBCOMMAND" in
    list)
        cmd_list
        ;;
    execute)
        cmd_execute
        ;;
    *)
        echo "[ERROR] 알 수 없는 서브커맨드: $SUBCOMMAND"
        echo "사용법: $0 <list|execute>"
        exit 1
        ;;
esac
