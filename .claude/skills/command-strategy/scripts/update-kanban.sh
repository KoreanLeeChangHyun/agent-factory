#!/usr/bin/env bash
#
# update-kanban.sh
# ================
# 워크플로우 완료 시 .kanbanboard 파일을 갱신한다.
#
# 사용법:
#   update-kanban.sh <kanbanboard_path> <workflow_id> <status>
#
# 인자:
#   kanbanboard_path  .kanbanboard 파일 경로
#   workflow_id       완료된 워크플로우 ID (예: WF-1)
#   status            새 상태 (completed | failed)
#
# 동작:
#   1. 워크플로우 체크박스를 [ ] -> [x] 로 전환 (completed인 경우)
#   2. 마일스톤 상태 카운터(N/M 완료) 자동 갱신
#   3. 모든 워크플로우 완료 시 마일스톤을 In Progress -> Done 컬럼으로 이동
#   4. frontmatter의 updated 날짜 갱신
#
# 종료 코드:
#   0  정상 완료
#   1  인자 오류 또는 파일 없음
#   2  워크플로우 ID를 찾을 수 없음

set -euo pipefail

# --- 인자 검증 ---
if [[ $# -ne 3 ]]; then
    echo "error: 인자 3개 필요 (kanbanboard_path, workflow_id, status)" >&2
    echo "사용법: update-kanban.sh <kanbanboard_path> <workflow_id> <status>" >&2
    exit 1
fi

KANBAN_PATH="$1"
WORKFLOW_ID="$2"
STATUS="$3"

if [[ ! -f "$KANBAN_PATH" ]]; then
    echo "error: 파일을 찾을 수 없음: $KANBAN_PATH" >&2
    exit 1
fi

if [[ "$STATUS" != "completed" && "$STATUS" != "failed" ]]; then
    echo "error: status는 'completed' 또는 'failed'만 허용 (입력: $STATUS)" >&2
    exit 1
fi

# 워크플로우 ID가 파일에 존재하는지 확인
if ! grep -q "\[.\] ${WORKFLOW_ID}:" "$KANBAN_PATH" 2>/dev/null; then
    echo "error: 워크플로우 ID를 찾을 수 없음: $WORKFLOW_ID" >&2
    exit 2
fi

TODAY=$(date +%Y-%m-%d)

# --- 1단계: 워크플로우 체크박스 전환 ---
if [[ "$STATUS" == "completed" ]]; then
    sed -i "s/\[ \] ${WORKFLOW_ID}:/[x] ${WORKFLOW_ID}:/" "$KANBAN_PATH"
fi

# --- 2단계: frontmatter updated 날짜 갱신 ---
sed -i "s/^updated: .*/updated: ${TODAY}/" "$KANBAN_PATH"

# --- 3단계: 마일스톤 상태 카운터 갱신 + 완료 마일스톤 Done 이동 ---
TEMP_FILE=$(mktemp)
trap "rm -f '$TEMP_FILE'" EXIT

awk -v today="$TODAY" '
BEGIN {
    current_column = ""
    in_ms_block = 0
    ms_block = ""
    wf_total = 0
    wf_checked = 0
    in_wf_section = 0
    done_count = 0
    done_section_printed = 0
}

/^## Planned/ { current_column = "planned" }
/^## In Progress/ { current_column = "inprogress" }

/^## Done/ {
    current_column = "done"
    if (in_ms_block) {
        flush_milestone()
    }
    print
    done_section_printed = 1
    for (i = 1; i <= done_count; i++) {
        printf "\n%s", done_blocks[i]
    }
    next
}

/^### .+: .+/ {
    if (in_ms_block) {
        flush_milestone()
    }
    in_ms_block = 1
    in_wf_section = 0
    ms_block = $0 "\n"
    ms_column = current_column
    wf_total = 0
    wf_checked = 0
    next
}

/^## / {
    if (in_ms_block) {
        flush_milestone()
    }
    print
    next
}

in_ms_block {
    # "- **워크플로우**:" 헤더 감지 -> 워크플로우 섹션 시작
    if ($0 ~ /^- \*\*워크플로우\*\*/) {
        in_wf_section = 1
        ms_block = ms_block $0 "\n"
        next
    }

    # "- **상태**:" 감지 -> 카운터 교체, 워크플로우 섹션 종료
    if ($0 ~ /^- \*\*상태\*\*:/) {
        in_wf_section = 0
        ms_block = ms_block "STATUS_PLACEHOLDER\nCOMPLETION_DATE_PLACEHOLDER\n"
        next
    }

    # 다른 "- **XXX**" 항목 감지 -> 워크플로우 섹션 종료
    if ($0 ~ /^- \*\*.+\*\*/) {
        in_wf_section = 0
    }

    # 워크플로우 섹션 내의 체크박스만 카운트
    if (in_wf_section && $0 ~ /^  - \[.\] .+/) {
        wf_total++
        if ($0 ~ /^  - \[x\] .+/) {
            wf_checked++
        }
    }

    ms_block = ms_block $0 "\n"
    next
}

{ print }

END {
    if (in_ms_block) {
        flush_milestone()
    }
    if (!done_section_printed && done_count > 0) {
        for (i = 1; i <= done_count; i++) {
            printf "\n%s", done_blocks[i]
        }
    }
}

function flush_milestone() {
    status_line = "- **상태**: " wf_checked "/" wf_total " 완료"
    gsub(/STATUS_PLACEHOLDER/, status_line, ms_block)

    if (ms_column == "inprogress" && wf_total > 0 && wf_checked == wf_total) {
        # 완료일 추가
        gsub(/COMPLETION_DATE_PLACEHOLDER/, "- **완료일**: " today, ms_block)
        done_count++
        done_blocks[done_count] = ms_block
    } else {
        # 미완료 시 완료일 플레이스홀더 제거 (빈 줄 포함)
        gsub(/COMPLETION_DATE_PLACEHOLDER\n/, "", ms_block)
        printf "%s", ms_block
    }

    in_ms_block = 0
    in_wf_section = 0
    ms_block = ""
    wf_total = 0
    wf_checked = 0
}
' "$KANBAN_PATH" > "$TEMP_FILE"

cp "$TEMP_FILE" "$KANBAN_PATH"

# 연속 빈 줄을 최대 1개로 축소
sed -i '/^$/N;/^\n$/d' "$KANBAN_PATH"

echo "ok: ${WORKFLOW_ID} -> ${STATUS}"
