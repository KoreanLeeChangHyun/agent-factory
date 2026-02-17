#!/usr/bin/env bash
#
# validate-kanban.sh
# ==================
# .kanbanboard와 roadmap.md 간의 정합성을 검증하고 프로젝트 완료 여부를 판단한다.
#
# 사용법:
#   validate-kanban.sh <kanbanboard_path> <roadmap_path>
#
# 인자:
#   kanbanboard_path  .kanbanboard 파일 경로
#   roadmap_path      roadmap.md 파일 경로
#
# 정합성 검증 항목:
#   (a) roadmap.md의 마일스톤 ID 목록과 .kanbanboard의 마일스톤 ID 목록 일치 여부
#   (b) 워크플로우 ID 교차 검증 (GAP-V3: roadmap SSOT 기준 ERROR/WARN 분류)
#   (c) 상태 불일치 감지 (roadmap에 없는 WF가 kanbanboard에 존재하는 경우 경고)
#   (d) GAP-V2: roadmap.md 마일스톤 완료 상태 교차 확인 (프로젝트 완료 조건 3)
#
# 프로젝트 완료 판단:
#   .kanbanboard의 Done 컬럼 마일스톤 수와 전체 마일스톤 수 비교
#   + roadmap.md의 모든 마일스톤에 완료 상태가 기록되어 있는지 확인
#   모두 충족 시 "프로젝트 완료" 메시지 출력
#
# 종료 코드:
#   0  정합성 통과 (프로젝트 미완료)
#   1  정합성 불일치
#   2  프로젝트 완료 상태 (정합성도 통과)

set -euo pipefail

# --- 인자 검증 ---
if [[ $# -ne 2 ]]; then
    echo "error: 인자 2개 필요 (kanbanboard_path, roadmap_path)" >&2
    echo "사용법: validate-kanban.sh <kanbanboard_path> <roadmap_path>" >&2
    exit 1
fi

KANBAN_PATH="$1"
ROADMAP_PATH="$2"

if [[ ! -f "$KANBAN_PATH" ]]; then
    echo "error: 파일을 찾을 수 없음: $KANBAN_PATH" >&2
    exit 1
fi

if [[ ! -f "$ROADMAP_PATH" ]]; then
    echo "error: 파일을 찾을 수 없음: $ROADMAP_PATH" >&2
    exit 1
fi

# --- 마일스톤 ID 추출 ---

# roadmap.md에서 마일스톤 ID 추출
# 패턴: "### MS-N:" 또는 "## MS-N:" 형태의 마일스톤 헤더
extract_roadmap_milestone_ids() {
    grep -oP '^#{2,3}\s+\K(MS-[0-9]+)(?=:)' "$ROADMAP_PATH" | sort -u
}

# .kanbanboard에서 마일스톤 ID 추출
# 패턴: "### MS-N:" 형태의 마일스톤 카드 헤더
extract_kanban_milestone_ids() {
    grep -oP '^###\s+\K(MS-[0-9]+)(?=:)' "$KANBAN_PATH" | sort -u
}

# --- 워크플로우 ID 추출 ---

# roadmap.md에서 워크플로우 ID 추출
# 패턴: "WF-N" 형태 (테이블 또는 목록에서)
extract_roadmap_workflow_ids() {
    grep -oP '\bWF-[0-9]+\b' "$ROADMAP_PATH" | sort -u
}

# .kanbanboard에서 워크플로우 ID 추출
# 패턴: "- [ ] WF-N:" 또는 "- [x] WF-N:" 형태의 체크박스 항목
extract_kanban_workflow_ids() {
    grep -oP '^\s*- \[.\]\s+\K(WF-[0-9]+)(?=:)' "$KANBAN_PATH" | sort -u
}

# --- Done 컬럼 분석 ---

# .kanbanboard에서 Done 컬럼의 마일스톤 수 계산
count_done_milestones() {
    awk '
    BEGIN { in_done = 0; count = 0 }
    /^## Done/ { in_done = 1; next }
    /^## / { if (in_done) in_done = 0 }
    in_done && /^### MS-[0-9]+:/ { count++ }
    END { print count }
    ' "$KANBAN_PATH"
}

# .kanbanboard에서 전체 마일스톤 수 계산
count_total_milestones() {
    grep -cP '^### MS-[0-9]+:' "$KANBAN_PATH" || echo "0"
}

# --- GAP-V2: roadmap.md 마일스톤 완료 상태 교차 확인 ---

# .kanbanboard Done 컬럼의 마일스톤 ID 목록 추출
extract_done_milestone_ids() {
    awk '
    BEGIN { in_done = 0 }
    /^## Done/ { in_done = 1; next }
    /^## / { if (in_done) in_done = 0 }
    in_done && /^### (MS-[0-9]+):/ { print $2 }
    ' "$KANBAN_PATH" | sed 's/:$//' | sort -u
}

# roadmap.md에서 완료 상태가 기록된 마일스톤 ID 목록 추출
# 패턴: "### MS-N:" 또는 "## MS-N:" 헤더 이후 "- **상태**: 완료" 가 존재하는 마일스톤
extract_roadmap_completed_milestone_ids() {
    awk '
    /^##/ && /MS-[0-9]+:/ {
        if (ms_id != "" && completed) print ms_id
        match($0, /MS-[0-9]+/)
        ms_id = substr($0, RSTART, RLENGTH)
        completed = 0
    }
    /^- \*\*상태\*\*: 완료/ { completed = 1 }
    END { if (ms_id != "" && completed) print ms_id }
    ' "$ROADMAP_PATH" | sort -u
}

# --- 검증 실행 ---

HAS_ERROR=0
WARNINGS=()
ERRORS=()

# 임시 파일
ROADMAP_MS=$(mktemp)
KANBAN_MS=$(mktemp)
ROADMAP_WF=$(mktemp)
KANBAN_WF=$(mktemp)
trap "rm -f '$ROADMAP_MS' '$KANBAN_MS' '$ROADMAP_WF' '$KANBAN_WF'" EXIT

extract_roadmap_milestone_ids > "$ROADMAP_MS"
extract_kanban_milestone_ids > "$KANBAN_MS"
extract_roadmap_workflow_ids > "$ROADMAP_WF"
extract_kanban_workflow_ids > "$KANBAN_WF"

# (a) 마일스톤 ID 일치 여부 검증
ONLY_IN_ROADMAP=$(comm -23 "$ROADMAP_MS" "$KANBAN_MS")
ONLY_IN_KANBAN=$(comm -13 "$ROADMAP_MS" "$KANBAN_MS")

if [[ -n "$ONLY_IN_ROADMAP" ]]; then
    HAS_ERROR=1
    while IFS= read -r ms_id; do
        ERRORS+=("마일스톤 불일치: ${ms_id}가 roadmap에 있으나 kanbanboard에 없음")
    done <<< "$ONLY_IN_ROADMAP"
fi

if [[ -n "$ONLY_IN_KANBAN" ]]; then
    HAS_ERROR=1
    while IFS= read -r ms_id; do
        ERRORS+=("마일스톤 불일치: ${ms_id}가 kanbanboard에 있으나 roadmap에 없음")
    done <<< "$ONLY_IN_KANBAN"
fi

# (b) 워크플로우 ID 교차 검증
WF_ONLY_IN_ROADMAP=$(comm -23 "$ROADMAP_WF" "$KANBAN_WF")
WF_ONLY_IN_KANBAN=$(comm -13 "$ROADMAP_WF" "$KANBAN_WF")

# GAP-V3: roadmap이 SSOT이므로 roadmap에만 있는 WF는 kanban 누락(ERROR),
#          kanban에만 있는 WF는 독자 추가(WARN)
if [[ -n "$WF_ONLY_IN_ROADMAP" ]]; then
    HAS_ERROR=1
    while IFS= read -r wf_id; do
        ERRORS+=("워크플로우 누락: ${wf_id}가 roadmap에 있으나 kanbanboard에 없음")
    done <<< "$WF_ONLY_IN_ROADMAP"
fi

# (c) 상태 불일치 감지 - roadmap에 없는 WF가 kanbanboard에 존재 (경고)
if [[ -n "$WF_ONLY_IN_KANBAN" ]]; then
    while IFS= read -r wf_id; do
        WARNINGS+=("상태 불일치: ${wf_id}가 kanbanboard에 있으나 roadmap에 없음")
    done <<< "$WF_ONLY_IN_KANBAN"
fi

# --- 결과 출력 ---

# 에러 출력
for err in "${ERRORS[@]+"${ERRORS[@]}"}"; do
    echo "error: $err" >&2
done

# 경고 출력
for warn in "${WARNINGS[@]+"${WARNINGS[@]}"}"; do
    echo "warn: $warn" >&2
done

# 정합성 불일치 시 종료
if [[ $HAS_ERROR -ne 0 ]]; then
    echo "result: 정합성 불일치 (에러 ${#ERRORS[@]}건, 경고 ${#WARNINGS[@]}건)"
    exit 1
fi

# --- GAP-V2: roadmap.md 마일스톤 완료 상태 교차 확인 ---
# kanban Done 컬럼의 마일스톤이 roadmap.md에도 완료 상태로 기록되어 있는지 검증
# (프로젝트 완료 조건 3: roadmap.md의 모든 마일스톤에 완료 상태가 기록되어 있다)

DONE_MS_IDS=$(mktemp)
ROADMAP_COMPLETED_MS_IDS=$(mktemp)
trap "rm -f '$ROADMAP_MS' '$KANBAN_MS' '$ROADMAP_WF' '$KANBAN_WF' '$DONE_MS_IDS' '$ROADMAP_COMPLETED_MS_IDS'" EXIT

extract_done_milestone_ids > "$DONE_MS_IDS"
extract_roadmap_completed_milestone_ids > "$ROADMAP_COMPLETED_MS_IDS"

# kanban Done에 있지만 roadmap에 완료 상태가 미기록된 마일스톤
DONE_BUT_NOT_IN_ROADMAP=$(comm -23 "$DONE_MS_IDS" "$ROADMAP_COMPLETED_MS_IDS")
if [[ -n "$DONE_BUT_NOT_IN_ROADMAP" ]]; then
    while IFS= read -r ms_id; do
        WARNINGS+=("완료 상태 미기록: ${ms_id}가 kanbanboard Done에 있으나 roadmap.md에 완료 상태가 기록되지 않음")
    done <<< "$DONE_BUT_NOT_IN_ROADMAP"
fi

# --- 프로젝트 완료 판단 ---

TOTAL_MS=$(count_total_milestones)
DONE_MS=$(count_done_milestones)

echo "정합성 통과 (마일스톤: ${DONE_MS}/${TOTAL_MS} 완료)"

# 경고가 있으면 출력
if [[ ${#WARNINGS[@]} -gt 0 ]]; then
    echo "경고 ${#WARNINGS[@]}건 (상세 내용은 stderr 참조)"
fi

if [[ "$TOTAL_MS" -gt 0 && "$DONE_MS" -eq "$TOTAL_MS" ]]; then
    # 프로젝트 완료 조건 3 검증: roadmap.md의 모든 마일스톤에 완료 상태가 기록되어 있는가
    ROADMAP_COMPLETED_COUNT=$(wc -l < "$ROADMAP_COMPLETED_MS_IDS" | tr -d ' ')
    if [[ "$ROADMAP_COMPLETED_COUNT" -lt "$TOTAL_MS" ]]; then
        echo "warn: 프로젝트 완료 조건 미충족 - roadmap.md에 완료 상태 미기록 마일스톤 존재 (${ROADMAP_COMPLETED_COUNT}/${TOTAL_MS})" >&2
        echo "프로젝트 미완료: kanban은 모두 Done이나 roadmap.md 완료 상태 미기록 (${ROADMAP_COMPLETED_COUNT}/${TOTAL_MS})"
        exit 0
    fi
    echo "프로젝트 완료: 모든 마일스톤(${TOTAL_MS}개)이 Done 상태이며 roadmap.md에 완료 기록됨."
    exit 2
fi

exit 0
