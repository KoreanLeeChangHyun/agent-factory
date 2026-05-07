#!/usr/bin/env -S python3 -u
"""Pre-tool-use dispatcher.

Routes hook logic based on tool_name extracted from stdin JSON.
Uses dispatcher.py utilities for flag-based conditional execution.

라우팅 테이블:
  Write|Edit|MultiEdit|NotebookEdit       -> rules_auto_approve         (HOOK_RULES_AUTO_APPROVE, sync, fast-path)
  Write|Edit|MultiEdit|NotebookEdit|Bash  -> hooks_self_guard          (HOOK_HOOKS_SELF_PROTECT, sync)
  AskUserQuestion                         -> slack_ask                 (HOOK_SLACK_ASK, async)
  Bash                                    -> dangerous_command_guard    (HOOK_DANGEROUS_COMMAND, sync)
  Bash                                    -> direct_path_guard          (HOOK_DIRECT_PATH_GUARD, sync)
  Bash                                    -> main_branch_guard          (HOOK_MAIN_BRANCH_GUARD, sync)
  Bash                                    -> kanban_subcommand_guard    (HOOK_KANBAN_SUBCOMMAND_GUARD, sync)
  Bash                                    -> done_relation_guard        (HOOK_DONE_RELATION_GUARD, sync)
  Bash                                    -> worktree_remove_guard      (HOOK_WORKTREE_REMOVE_GUARD, sync)
  Write|Edit|MultiEdit|NotebookEdit|Bash  -> main_session_guard         (HOOK_MAIN_SESSION_GUARD, sync)
  Write|Edit|MultiEdit|NotebookEdit|Bash  -> readonly_session_guard     (HOOK_READONLY_SESSION_GUARD, sync)
  Write|Edit|MultiEdit|NotebookEdit|Bash  -> worktree_path_guard        (HOOK_WORKTREE_PATH_GUARD, sync)
  Task                                    -> agent_investigation_guard  (HOOK_AGENT_INVESTIGATION_GUARD, sync)
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dispatcher import (
    collect_exit_codes,
    collect_outputs,
    dispatch,
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


def _record_tool_deny_metrics(
    tool_name: str,
    tool_use_id: str,
    reason: str,
    tool_input: object,
) -> None:
    """deny 결정 시 tool.deny 이벤트를 metrics.jsonl에 기록한다.

    hook 자체 동작에 영향을 주지 않기 위해 모든 예외를 조용히 흡수한다.
    work_dir 추출 실패 시 (워크플로우 외부 호출 등) silently skip.

    Args:
        tool_name: 도구 이름 (예: Bash, Edit).
        tool_use_id: 도구 호출 ID (없으면 빈 문자열).
        reason: deny 사유 문자열.
        tool_input: 도구 입력 객체 (직렬화 후 첫 500자를 input_summary에 기록).
    """
    try:
        work_dir = _get_metrics_work_dir()
        if not work_dir:
            return

        # input_summary: tool_input 직렬화 후 최대 500자
        input_summary = ''
        try:
            if tool_input is not None:
                raw = (
                    tool_input
                    if isinstance(tool_input, str)
                    else json.dumps(tool_input, ensure_ascii=False)
                )
                input_summary = raw[:500]
        except Exception:  # noqa: BLE001
            pass

        from flow.metrics import append_event
        append_event(
            work_dir,
            'tool.deny',
            {
                'tool_name': tool_name,
                'tool_use_id': tool_use_id,
                'reason': reason,
                'input_summary': input_summary,
            },
        )
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def main() -> None:
    """Dispatch pre-tool-use hooks based on tool_name.

    Reads JSON from stdin, extracts tool_name, and dispatches
    the appropriate sync or async hook scripts. Exits with the
    first non-zero exit code from synchronous hooks.
    """
    stdin_data = sys.stdin.buffer.read()

    # Parse tool_name from JSON input
    try:
        payload = json.loads(stdin_data)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = payload.get('tool_name', '')

    flags = load_env_flags()
    sync_results = []
    # Other tool_name values (Read, Glob, Grep, WebFetch, etc.) pass through without hook processing

    # --- Write|Edit|MultiEdit|NotebookEdit: rules-auto-approve (sync, fast-path) ---
    # .claude/rules/ 경로 대상 파일 수정 요청을 가드 체인 실행 전에 선제 처리한다.
    # allow 응답이 반환되면 나머지 가드 체인을 스킵하고 즉시 allow 출력 후 종료한다.
    # 이를 통해 hooks_self_guard, main_session_guard 등이 우발적으로 deny하는 것을 방지한다.
    if tool_name in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit'):
        r = dispatch(
            'HOOK_RULES_AUTO_APPROVE',
            scripts_dir('guards', 'rules_auto_approve.py'),
            stdin_data,
            flags=flags,
            capture_output=True,
        )
        if r is not None and r.stdout and b'allow' in r.stdout:
            sys.stdout.buffer.write(r.stdout)
            sys.exit(0)

    # --- Write|Edit|MultiEdit|NotebookEdit|Bash: hooks-self-guard (sync) ---
    if tool_name in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'Bash'):
        r = dispatch(
            'HOOK_HOOKS_SELF_PROTECT',
            scripts_dir('guards', 'hooks_self_guard.py'),
            stdin_data,
            flags=flags,
            capture_output=True,
        )
        sync_results.append(r)

    # --- AskUserQuestion: slack-ask (async, fire-and-forget) ---
    if tool_name == 'AskUserQuestion':
        dispatch_async(
            'HOOK_SLACK_ASK',
            scripts_dir('slack', 'slack_ask.py'),
            stdin_data,
            flags=flags,
        )

    # --- Bash: dangerous-command-guard (sync) ---
    if tool_name == 'Bash':
        r = dispatch(
            'HOOK_DANGEROUS_COMMAND',
            scripts_dir('guards', 'dangerous_command_guard.py'),
            stdin_data,
            flags=flags,
            capture_output=True,
        )
        sync_results.append(r)

    # --- Bash: direct-path-guard (sync) ---
    if tool_name == 'Bash':
        r = dispatch(
            'HOOK_DIRECT_PATH_GUARD',
            scripts_dir('guards', 'direct_path_guard.py'),
            stdin_data,
            flags=flags,
            capture_output=True,
        )
        sync_results.append(r)

    # --- Bash: main-branch-guard (sync) ---
    if tool_name == 'Bash':
        r = dispatch(
            'HOOK_MAIN_BRANCH_GUARD',
            scripts_dir('guards', 'main_branch_guard.py'),
            stdin_data,
            flags=flags,
            capture_output=True,
        )
        sync_results.append(r)

    # --- Bash: kanban-subcommand-guard (sync) ---
    if tool_name == 'Bash':
        r = dispatch(
            'HOOK_KANBAN_SUBCOMMAND_GUARD',
            scripts_dir('guards', 'kanban_subcommand_guard.py'),
            stdin_data,
            flags=flags,
            capture_output=True,
        )
        sync_results.append(r)

    # --- Bash: done-relation-guard (sync) ---
    if tool_name == 'Bash':
        r = dispatch(
            'HOOK_DONE_RELATION_GUARD',
            scripts_dir('guards', 'done_relation_guard.py'),
            stdin_data,
            flags=flags,
            capture_output=True,
        )
        sync_results.append(r)

    # --- Bash: worktree-remove-guard (sync) ---
    if tool_name == 'Bash':
        r = dispatch(
            'HOOK_WORKTREE_REMOVE_GUARD',
            scripts_dir('guards', 'worktree_remove_guard.py'),
            stdin_data,
            flags=flags,
            capture_output=True,
        )
        sync_results.append(r)

    # --- Write|Edit|MultiEdit|NotebookEdit|Bash: main-session-guard (sync) ---
    if tool_name in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'Bash'):
        r = dispatch(
            'HOOK_MAIN_SESSION_GUARD',
            scripts_dir('guards', 'main_session_guard.py'),
            stdin_data,
            flags=flags,
            capture_output=True,
        )
        sync_results.append(r)

    # --- Write|Edit|MultiEdit|NotebookEdit|Bash: readonly-session-guard (sync) ---
    if tool_name in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'Bash'):
        r = dispatch(
            'HOOK_READONLY_SESSION_GUARD',
            scripts_dir('guards', 'readonly_session_guard.py'),
            stdin_data,
            flags=flags,
            capture_output=True,
        )
        sync_results.append(r)

    # --- Write|Edit|MultiEdit|NotebookEdit|Bash: worktree-path-guard (sync) ---
    if tool_name in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'Bash'):
        r = dispatch(
            'HOOK_WORKTREE_PATH_GUARD',
            scripts_dir('guards', 'worktree_path_guard.py'),
            stdin_data,
            flags=flags,
            capture_output=True,
        )
        sync_results.append(r)

    # --- Task: agent-investigation-guard (sync) ---
    if tool_name == 'Task':
        r = dispatch(
            'HOOK_AGENT_INVESTIGATION_GUARD',
            scripts_dir('guards', 'agent_investigation_guard.py'),
            stdin_data,
            flags=flags,
            capture_output=True,
        )
        sync_results.append(r)

    # If any guard emitted a deny JSON, relay the first one and exit 0
    for r in sync_results:
        if r is not None and r.stdout and b'deny' in r.stdout:
            # --- metrics: tool.deny 이벤트 기록 (deny 결정 시에만) ---
            try:
                deny_reason = ''
                try:
                    deny_data = json.loads(r.stdout)
                    hook_out = deny_data.get('hookSpecificOutput', {})
                    deny_reason = hook_out.get('permissionDecisionReason', '')
                except Exception:  # noqa: BLE001
                    pass
                if not deny_reason:
                    deny_reason = 'guard denied'
                tool_use_id_str = payload.get('tool_use_id', '') or ''
                tool_input_val = payload.get('tool_input')
                _record_tool_deny_metrics(
                    tool_name, tool_use_id_str, deny_reason, tool_input_val
                )
            except Exception:  # noqa: BLE001
                pass
            sys.stdout.buffer.write(r.stdout)
            sys.exit(0)

    # No guard blocked: emit allow JSON so Claude Code skips confirm prompt
    allow_payload = {
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'allow',
            'permissionDecisionReason': '모든 가드를 통과하였습니다.',
        }
    }
    print(json.dumps(allow_payload))
    sys.exit(0)


if __name__ == '__main__':
    main()
