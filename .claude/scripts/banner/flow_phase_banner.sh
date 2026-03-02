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
# | ID | 작업 | 종속성 | Phase | 복잡도 | 서브에이전트 | 스킬 |
rows = []
for line in content.split('\n'):
    line = line.strip()
    if not line.startswith('|') or '---' in line:
        continue
    cols = [c.strip() for c in line.split('|')]
    # cols[0]='', cols[1]=ID, ..., cols[4]=Phase, cols[6]=서브에이전트
    if len(cols) >= 7:
        try:
            if cols[4] == phase:
                rows.append({'id': cols[1], 'agent': cols[6], 'task': cols[2]})
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
