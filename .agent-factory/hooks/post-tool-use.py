#!/usr/bin/env -S python3 -u
"""Post-tool-use dispatcher.

Routes hook logic based on tool_name extracted from stdin JSON.
Uses dispatcher.py utilities for flag-based conditional execution.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dispatcher import (
    dispatch_async,
    load_env_flags,
    scripts_dir,
)

_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'engine')
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)


# ---------------------------------------------------------------------------
# metrics 헬퍼
# ---------------------------------------------------------------------------

def _get_metrics_work_dir() -> str | None:
    """환경변수에서 metrics 기록용 work_dir을 추출한다.

    WORKFLOW_WORK_DIR 또는 _WF_WORK_DIR 우선순위로 조회하며,
    유효한 디렉터리 경로일 때만 반환한다. 해석 불가 시 None.
    """
    for key in ("WORKFLOW_WORK_DIR", "_WF_WORK_DIR"):
        val = os.environ.get(key, "").strip()
        if val and os.path.isdir(val):
            return val
    return None


def _append_metrics_event(event_type: str, payload: dict) -> None:
    """metrics.append_event를 try/except 로 감싸 안전하게 호출한다.

    hook 자체 동작에 영향을 주지 않기 위해 모든 예외를 조용히 흡수한다.
    work_dir 추출 실패 시 (워크플로우 외부 호출 등) silently skip.
    """
    try:
        work_dir = _get_metrics_work_dir()
        if not work_dir:
            return
        from flow.metrics import append_event
        append_event(work_dir, event_type, payload)
    except Exception:  # noqa: BLE001
        pass

from flow.session_identifier import WINDOW_PREFIX_P


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _handle_bash_flow_end(tool_input: dict) -> None:
    """Handle session cleanup when flow-claude end is detected.

    Detects 'flow-claude end' pattern in Bash command input and schedules
    a delayed session kill as a secondary safety net (2nd layer after
    finalization.py Step 5). Uses a 5-second delay (longer than
    finalization.py's 3 seconds) to ensure banner output completes first.

    HTTP API path (primary):
        Uses _WF_SESSION_ID + _WF_SERVER_PORT environment variables to call
        POST /terminal/workflow/kill via a background subprocess with 5s delay.

    TMUX fallback path (legacy):
        When _WF_SESSION_ID or _WF_SERVER_PORT is absent, falls back to the
        original TMUX_PANE-based tmux kill-window approach.

    If any required condition is unmet, cleanup is silently skipped (idempotent).

    Args:
        tool_input: The tool_input dict from the Bash hook payload.
    """
    command: str = tool_input.get('command', '') if isinstance(tool_input, dict) else ''
    # 명령어 시작 위치(줄 시작 또는 ; && || & 뒤)에서만 매칭 —
    # 주석/문자열 리터럴/heredoc 내부의 'flow-claude end' 오탐 방지
    if not re.search(r'(?:^|[;&|]\s*)flow-claude\s+end\b', command):
        return

    session_id: str | None = os.environ.get('_WF_SESSION_ID')
    server_port: str | None = os.environ.get('_WF_SERVER_PORT')

    if session_id and server_port:
        # HTTP API path: 5초 지연 후 POST /terminal/workflow/kill (백그라운드)
        port = server_port
        sid = session_id
        python_cmd = (
            f"import time,urllib.request,json; "
            f"time.sleep(5); "
            f"urllib.request.urlopen("
            f"urllib.request.Request("
            f"'http://127.0.0.1:{port}/terminal/workflow/kill', "
            f"data=json.dumps({{'session_id':'{sid}'}}).encode(), "
            f"headers={{'Content-Type':'application/json'}}, "
            f"method='POST'))"
        )
        subprocess.Popen(
            ['python3', '-c', python_cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return

    # TMUX fallback: _WF_SESSION_ID 또는 _WF_SERVER_PORT 미설정 시 기존 tmux 경로 유지
    tmux_pane: str | None = os.environ.get('TMUX_PANE')
    if not tmux_pane:
        return

    try:
        result = subprocess.run(
            ['tmux', 'display-message', '-t', tmux_pane, '-p', '#W'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        window_name: str = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return

    if not window_name.startswith(f'{WINDOW_PREFIX_P}T-'):
        return

    # TMUX_PANE(%N)을 직접 타겟으로 사용: 콜론 포함 윈도우명의 세션:윈도우 오해석 방지
    pane_target: str = shlex.quote(tmux_pane)
    bash_cmd: str = f'sleep 5 && tmux kill-window -t {pane_target}'

    subprocess.Popen(
        ['bash', '-c', bash_cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def main() -> None:
    """Dispatch post-tool-use hooks based on tool_name and file_path.

    Reads JSON from stdin, extracts tool_name and file_path, and
    dispatches async hooks as fire-and-forget. All hooks in this
    dispatcher are async; exits with 0 unconditionally.
    """
    stdin_data = sys.stdin.buffer.read()

    # Parse tool_name and tool_input from JSON input
    try:
        payload = json.loads(stdin_data)
        if not isinstance(payload, dict):
            sys.exit(0)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = payload.get('tool_name', '')
    tool_input = payload.get('tool_input', {})

    # --- metrics: tool.call 이벤트 기록 (모든 도구 대상) ---
    # 기존 hook 로직과 독립적으로 수행. 실패해도 hook 동작에 영향 없음.
    _record_tool_call_metrics(tool_name, payload)

    # --- Bash: flow-claude end detection (tmux window cleanup, 2nd safety net) ---
    # Must be placed before the file_path guard because Bash tool has no file_path.
    if tool_name == 'Bash':
        _handle_bash_flow_end(tool_input)
        sys.exit(0)

    # T-489 Stage 3-C: workflow_hooks/ 폐기 — v2 driver 는 hook 의존 X.
    # 옛 Task subagent post-hook 분기는 SDK Task 자체 폐기로 dead.
    if tool_name == 'Task':
        sys.exit(0)

    file_path = tool_input.get('file_path', '') if isinstance(tool_input, dict) else ''

    if not file_path:
        sys.exit(0)

    flags = load_env_flags()

    # --- Write|Edit: catalog-sync (async, fire-and-forget) ---
    # Trigger when a SKILL.md file under .claude/skills/ is written or edited
    if tool_name in ('Write', 'Edit'):
        if '.claude/skills/' in file_path and file_path.endswith('/SKILL.md'):
            dispatch_async(
                'HOOK_CATALOG_SYNC',
                scripts_dir('sync', 'catalog_sync.py'),
                stdin_data,
                flags=flags,
            )

    # All hooks are async/fire-and-forget, no exit code aggregation needed
    sys.exit(0)


def _record_tool_call_metrics(tool_name: str, payload: dict) -> None:
    """tool.call 이벤트를 metrics.jsonl에 기록한다.

    tool_name 이 'Task' 인 경우 subagent.spawn / subagent.end 도 함께 기록한다.
    모든 처리는 try/except로 감싸 hook 동작에 영향을 주지 않는다.

    Args:
        tool_name: 도구 이름 (예: Bash, Read, Edit, Task).
        payload: PostToolUse 전체 페이로드 dict.
    """
    try:
        tool_use_id: str = payload.get('tool_use_id', '') or ''
        parent_tool_use_id: str | None = payload.get('parent_tool_use_id') or None
        duration_ms: int | None = payload.get('duration_ms')

        # duration_ms 가 없으면 tool.call 스키마 필수 필드 누락 → 기록 건너뜀
        if duration_ms is None:
            return

        # bytes_in / bytes_out: tool_input/tool_result 직렬화 길이로 추정
        tool_input = payload.get('tool_input')
        tool_result = payload.get('tool_result')
        bytes_in: int | None = None
        bytes_out: int | None = None
        try:
            if tool_input is not None:
                bytes_in = len(json.dumps(tool_input, ensure_ascii=False))
        except Exception:  # noqa: BLE001
            pass
        try:
            if tool_result is not None:
                bytes_out = len(json.dumps(tool_result, ensure_ascii=False))
        except Exception:  # noqa: BLE001
            pass

        tool_call_payload: dict = {
            'tool_name': tool_name,
            'tool_use_id': tool_use_id,
            'duration_ms': int(duration_ms),
            'allowed': True,
        }
        if parent_tool_use_id:
            tool_call_payload['parent_tool_use_id'] = parent_tool_use_id
        if bytes_in is not None:
            tool_call_payload['bytes_in'] = bytes_in
        if bytes_out is not None:
            tool_call_payload['bytes_out'] = bytes_out

        _append_metrics_event('tool.call', tool_call_payload)

        # Task 도구인 경우 subagent.spawn + subagent.end 추가 기록
        if tool_name == 'Task':
            _record_subagent_metrics(tool_use_id, parent_tool_use_id, duration_ms, payload)

    except Exception:  # noqa: BLE001
        pass


def _record_subagent_metrics(
    tool_use_id: str,
    parent_tool_use_id: str | None,
    duration_ms: int,
    payload: dict,
) -> None:
    """Task 도구에 대해 subagent.spawn / subagent.end 이벤트를 기록한다.

    agent_kind 는 tool_input 의 subagent_type 또는 description 앞 단어로 추정한다.
    stdout_tail 은 tool_result 의 마지막 500자.

    Args:
        tool_use_id: Task 도구의 tool_use_id.
        parent_tool_use_id: 부모 tool_use_id (있는 경우).
        duration_ms: 도구 실행 시간(ms).
        payload: PostToolUse 전체 페이로드 dict.
    """
    try:
        tool_input = payload.get('tool_input') or {}
        tool_result = payload.get('tool_result')

        # agent_kind 추정: subagent_type 필드 → description 첫 단어 → 'unknown'
        agent_kind: str = 'unknown'
        if isinstance(tool_input, dict):
            subagent_type = tool_input.get('subagent_type', '')
            if subagent_type and isinstance(subagent_type, str):
                agent_kind = subagent_type.strip()
            else:
                desc = tool_input.get('description', '')
                if desc and isinstance(desc, str):
                    first_word = desc.strip().split()[0] if desc.strip() else 'unknown'
                    agent_kind = first_word[:64]  # 길이 제한

        # subagent.spawn 기록 (호출 시점 — PostToolUse 에서 소급 기록)
        spawn_payload: dict = {
            'agent_kind': agent_kind,
            'parent_tool_use_id': parent_tool_use_id or '',
        }
        # task_index: tool_input 에 명시된 경우
        if isinstance(tool_input, dict) and 'task_index' in tool_input:
            spawn_payload['task_index'] = tool_input['task_index']
        _append_metrics_event('subagent.spawn', spawn_payload)

        # stdout_tail: tool_result 마지막 500자
        stdout_tail = ''
        try:
            if tool_result is not None:
                result_str = (
                    tool_result
                    if isinstance(tool_result, str)
                    else json.dumps(tool_result, ensure_ascii=False)
                )
                stdout_tail = result_str[-500:]
        except Exception:  # noqa: BLE001
            pass

        # outcome 추정: tool_result 에 'error' 문자열 포함 여부
        outcome = 'ok'
        try:
            if tool_result is not None:
                result_str = (
                    tool_result
                    if isinstance(tool_result, str)
                    else json.dumps(tool_result, ensure_ascii=False)
                )
                if 'error' in result_str.lower()[:200]:
                    outcome = 'fail'
        except Exception:  # noqa: BLE001
            pass

        # subagent.end 기록
        end_payload: dict = {
            'agent_kind': agent_kind,
            'tool_use_id': tool_use_id,
            'duration_ms': int(duration_ms),
            'outcome': outcome,
            'stdout_tail': stdout_tail,
        }
        _append_metrics_event('subagent.end', end_payload)

    except Exception:  # noqa: BLE001
        pass


if __name__ == '__main__':
    main()
