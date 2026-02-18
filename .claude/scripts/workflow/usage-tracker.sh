#!/bin/bash
# SubagentStop Hook: 워크플로우 서브에이전트별 토큰 사용량 자동 추적
#
# 동작:
#   SubagentStop 이벤트 발생 시 agent_transcript_path JSONL 파일을 파싱하여
#   마지막 유효 message.usage 라인에서 누적 토큰을 추출하고,
#   활성 워크플로우의 usage.json에 에이전트별로 원자적 기록
#
# 입력 (stdin JSON):
#   agent_type, agent_id, agent_transcript_path
#
# 비차단 원칙: 모든 에러 경로에서 exit 0 (async Hook이므로 실패해도 워크플로우 무영향)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
REGISTRY_FILE="$PROJECT_ROOT/.workflow/registry.json"

# stdin JSON 읽기
INPUT=$(cat)
if [ -z "$INPUT" ]; then
    exit 0
fi

# JSON 필드 추출 (jq 없이 python3 사용)
AGENT_TYPE=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('agent_type',''))" 2>/dev/null) || exit 0
AGENT_ID=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('agent_id',''))" 2>/dev/null) || exit 0
TRANSCRIPT_PATH=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('agent_transcript_path',''))" 2>/dev/null) || exit 0

# 워크플로우 에이전트 필터링 (init, planner, worker, reporter만 처리)
case "$AGENT_TYPE" in
    init|planner|worker|reporter) ;;
    *) exit 0 ;;
esac

# transcript 경로 유효성 확인
if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
    exit 0
fi

# registry.json에서 활성 워크플로우의 workDir 조회
if [ ! -f "$REGISTRY_FILE" ]; then
    exit 0
fi

# Python으로 JSONL 파싱 + usage.json 원자적 기록을 일괄 처리
WF_REGISTRY="$REGISTRY_FILE" \
WF_PROJECT_ROOT="$PROJECT_ROOT" \
WF_AGENT_TYPE="$AGENT_TYPE" \
WF_AGENT_ID="$AGENT_ID" \
WF_TRANSCRIPT_PATH="$TRANSCRIPT_PATH" \
python3 << 'PYEOF'
import json, sys, os, tempfile, shutil

registry_file = os.environ['WF_REGISTRY']
project_root = os.environ['WF_PROJECT_ROOT']
agent_type = os.environ['WF_AGENT_TYPE']
agent_id = os.environ['WF_AGENT_ID']
transcript_path = os.environ['WF_TRANSCRIPT_PATH']

# 1. registry.json에서 활성 워크플로우 찾기 (첫 번째 활성 항목)
try:
    with open(registry_file, 'r', encoding='utf-8') as f:
        registry = json.load(f)
except Exception:
    sys.exit(0)

if not isinstance(registry, dict) or not registry:
    sys.exit(0)

# 활성 워크플로우의 workDir 조회 (첫 번째 항목 사용)
work_dir = None
registry_key = None
for key, entry in registry.items():
    if isinstance(entry, dict) and 'workDir' in entry:
        rel_dir = entry['workDir']
        candidate = os.path.join(project_root, rel_dir) if not rel_dir.startswith('/') else rel_dir
        if os.path.isdir(candidate):
            work_dir = candidate
            registry_key = key
            break

if not work_dir:
    sys.exit(0)

usage_file = os.path.join(work_dir, 'usage.json')

# 2. JSONL 파싱: 마지막 100줄에서 역방향으로 유효 usage 라인 탐색
try:
    # tail -n 100 으로 마지막 100줄만 읽기 (대용량 파일 최적화)
    import subprocess
    result = subprocess.run(
        ['tail', '-n', '100', transcript_path],
        capture_output=True, text=True, timeout=10
    )
    lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
except Exception:
    sys.exit(0)

if not lines or all(not l.strip() for l in lines):
    print(f"[usage-tracker] JSONL file empty or no valid lines: {transcript_path}", file=sys.stderr)
    sys.exit(0)

tokens = None
for line in reversed(lines):
    if not line.strip():
        continue
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        continue

    # isApiErrorMessage 라인 스킵
    if data.get('isApiErrorMessage'):
        continue

    # message.usage 필드 탐색 (primary), 최상위 usage 필드 (fallback)
    usage = None
    msg = data.get('message')
    if isinstance(msg, dict) and 'usage' in msg:
        usage = msg['usage']
    elif 'usage' in data:
        # Anthropic API 응답 형식 변경 대비: 최상위 usage 필드 폴백
        usage = data['usage']

    if isinstance(usage, dict):
        tokens = {
            'input_tokens': usage.get('input_tokens', 0),
            'output_tokens': usage.get('output_tokens', 0),
            'cache_creation_tokens': usage.get('cache_creation_input_tokens', 0),
            'cache_read_tokens': usage.get('cache_read_input_tokens', 0)
        }
        break

if not tokens:
    print(f"[usage-tracker] No valid usage data found in last 100 lines: {transcript_path}", file=sys.stderr)
    sys.exit(0)

# 3. mkdir 기반 POSIX 잠금으로 usage.json 원자적 기록
lock_dir = usage_file + '.lockdir'
max_wait = 5
waited = 0
locked = False

while waited < max_wait:
    try:
        os.makedirs(lock_dir)
        locked = True
        break
    except OSError:
        import time
        time.sleep(1)
        waited += 1

if not locked:
    sys.exit(0)

try:
    # usage.json 읽기 (없으면 빈 구조)
    if os.path.exists(usage_file):
        try:
            with open(usage_file, 'r', encoding='utf-8') as f:
                usage_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            usage_data = {"$schema": "usage-v1", "agents": {}, "totals": {}, "_pending_workers": {}}
    else:
        usage_data = {"$schema": "usage-v1", "agents": {}, "totals": {}, "_pending_workers": {}}

    if 'agents' not in usage_data:
        usage_data['agents'] = {}

    # 에이전트별 기록
    tokens['method'] = 'subagent_transcript'

    if agent_type == 'worker':
        # _pending_workers에서 agent_id로 taskId 조회
        pending = usage_data.get('_pending_workers', {})
        task_id = pending.get(agent_id, None)

        if 'workers' not in usage_data['agents']:
            usage_data['agents']['workers'] = {}

        if task_id:
            usage_data['agents']['workers'][task_id] = tokens
            # 사용된 pending 매핑 제거
            if agent_id in pending:
                del pending[agent_id]
        else:
            # taskId 미확인 시 agent_id를 키로 사용 (폴백)
            print(f"[usage-tracker] WARNING: agent_id '{agent_id}' not found in _pending_workers, using agent_id as key", file=sys.stderr)
            usage_data['agents']['workers'][agent_id] = tokens
    else:
        # init, planner, reporter
        usage_data['agents'][agent_type] = tokens

    # 원자적 쓰기
    dir_name = os.path.dirname(usage_file)
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(usage_data, f, ensure_ascii=False, indent=2)
            f.write('\n')
        shutil.move(tmp_path, usage_file)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
finally:
    # 잠금 해제
    try:
        os.rmdir(lock_dir)
    except OSError:
        pass

PYEOF

exit 0
