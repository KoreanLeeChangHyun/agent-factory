#!/usr/bin/env bash
# flow_phase_banner.sh - WORK Phase 서브배너 출력
#
# 사용법:
#   flow-phase <registryKey> <N>
#
# 예시:
#   flow-phase 20260301-061849 0
#   flow-phase 20260301-061849 1
#
# status.json의 running 태스크를 자동으로 읽어 표시합니다.
# Phase 0은 "skill-mapper"로 고정 표시됩니다.

set -euo pipefail

# ─── 공통 색상/유틸리티 로드 ───
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../data/colors.sh"

# ─── 인자 파싱 ───
REGISTRY_KEY="${1:-}"
PHASE="${2:-}"

if [[ -z "$REGISTRY_KEY" || -z "$PHASE" ]]; then
    echo "사용법: flow-phase <registryKey> <N>" >&2
    exit 0
fi

COLOR=$(get_color "WORK")

# ─── workflow.log 이벤트 기록 ───
_log_event() {
    local REGISTRY_KEY="$1" LEVEL="$2" MESSAGE="$3"
    REGISTRY_KEY="$REGISTRY_KEY" SCRIPT_DIR="$SCRIPT_DIR" LEVEL="$LEVEL" MESSAGE="$MESSAGE" python3 -c "
import os, sys
sys.path.insert(0, os.path.normpath(os.path.join(os.environ['SCRIPT_DIR'], '..')))
from common import resolve_abs_work_dir, resolve_project_root
from datetime import datetime, timezone, timedelta
try:
    root = resolve_project_root()
    wd = resolve_abs_work_dir(os.environ['REGISTRY_KEY'], root)
    kst = timezone(timedelta(hours=9))
    ts = datetime.now(kst).strftime('%Y-%m-%dT%H:%M:%S')
    log_path = os.path.join(wd, 'workflow.log')
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] [{os.environ[\"LEVEL\"]}] {os.environ[\"MESSAGE\"]}\n')
except Exception:
    pass
" 2>/dev/null || true
}

# ─── plan.md에서 Phase 정보 파싱 ───
if [[ "$PHASE" == "0" ]]; then
    EXEC_MODE="sequential"
    AGENTS="skill-mapper"
    TASKS=""
else
    read -r EXEC_MODE AGENTS TASKS < <(REGISTRY_KEY="$REGISTRY_KEY" PHASE="$PHASE" SCRIPT_DIR="$SCRIPT_DIR" python3 -c "
import os, re, sys
sys.path.insert(0, os.path.normpath(os.path.join(os.environ['SCRIPT_DIR'], '..')))
from common import resolve_abs_work_dir, resolve_project_root

root = resolve_project_root()
wd = resolve_abs_work_dir(os.environ['REGISTRY_KEY'], root)
phase = os.environ['PHASE']

plan_file = os.path.join(wd, 'plan.md')
try:
    with open(plan_file, 'r') as f:
        content = f.read()
except FileNotFoundError:
    print('sequential  ')
    sys.exit(0)

# 작업 목록 테이블에서 현재 Phase에 해당하는 행 파싱
# 헤더 행에서 컬럼 인덱스를 동적으로 추출
rows = []
header_cols = None
phase_idx = None
agent_idx = None
id_idx = None
task_idx = None
for line in content.split('\n'):
    line = line.strip()
    if not line.startswith('|'):
        continue
    if '---' in line:
        continue
    cols = [c.strip() for c in line.split('|')]
    if header_cols is None:
        # 첫 번째 데이터 행을 헤더로 인식
        header_lower = [c.lower() for c in cols]
        for i, h in enumerate(header_lower):
            if 'phase' in h:
                phase_idx = i
            if '서브에이전트' in h or 'agent' in h:
                agent_idx = i
            if h in ('id', '| id'):
                id_idx = i
            if '작업' in h or 'task' in h:
                task_idx = i
        # 헤더 행에 ID 컬럼이 있으면 헤더로 확정
        if phase_idx is not None:
            header_cols = cols
            continue
    if header_cols is not None and phase_idx is not None:
        try:
            if len(cols) > max(filter(lambda x: x is not None, [phase_idx, agent_idx or 0, id_idx or 0, task_idx or 0])):
                row_phase = cols[phase_idx] if phase_idx is not None else ''
                row_agent = cols[agent_idx] if agent_idx is not None else ''
                row_id = cols[id_idx] if id_idx is not None else cols[1] if len(cols) > 1 else ''
                row_task = cols[task_idx] if task_idx is not None else cols[2] if len(cols) > 2 else ''
                if row_phase == phase:
                    rows.append({'id': row_id, 'agent': row_agent, 'task': row_task})
        except (IndexError, ValueError):
            pass

if not rows:
    print('sequential  ')
    sys.exit(0)

exec_mode = 'parallel' if len(rows) > 1 else 'sequential'
agents = sorted(set(r['agent'] for r in rows if r['agent'] and r['agent'] != '-'))
task_ids = [r['id'] for r in rows]
print(f\"{exec_mode} {','.join(agents) if agents else '-'} {','.join(task_ids)}\")
" 2>/dev/null || echo "sequential  ")
fi

# ─── 출력 ───
if [[ "$EXEC_MODE" == "parallel" ]]; then
    MODE_LABEL="${C_CYAN}parallel${C_RESET}"
else
    MODE_LABEL="${C_DIM}sequential${C_RESET}"
fi

echo -e "${C_CLAUDE}║ STATE:${C_RESET} ${C_GREEN}Phase${C_RESET} ${COLOR}${C_BOLD}${PHASE}${C_RESET}  ${MODE_LABEL}"
if [[ -n "$AGENTS" && "$AGENTS" != "-" ]]; then
    if [[ -n "$TASKS" ]]; then
        echo -e "${C_CLAUDE}║${C_RESET} ${C_CLAUDE}>>${C_RESET} ${AGENTS}  ${C_DIM}[${TASKS}]${C_RESET}"
    else
        echo -e "${C_CLAUDE}║${C_RESET} ${C_CLAUDE}>>${C_RESET} ${AGENTS}"
    fi
else
    echo -e "${C_CLAUDE}║${C_RESET} ${C_CLAUDE}>>${C_RESET} ${C_DIM}Phase ${PHASE}${C_RESET}"
fi
_log_event "$REGISTRY_KEY" "INFO" "PHASE_START: ${PHASE} mode=${EXEC_MODE} agents=${AGENTS:-none} tasks=${TASKS:-none}" || true
