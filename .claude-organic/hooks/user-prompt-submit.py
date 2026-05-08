#!/usr/bin/env python3
"""UserPromptSubmit dispatcher — 메인 세션 칸반/세션 스냅샷 자동 주입.

UserPromptSubmit hook 진입점 스크립트. 사용자가 프롬프트를 제출할 때마다
칸반 보드 요약 + 활성 세션 목록을 additionalContext로 자동 주입한다.

메인 세션 한정으로 동작한다:
  - 워크트리(워크플로우 워커 세션)에서는 빈 stdout + exit 0 으로 즉시 종료
  - 워크플로우 세션에서 칸반/세션 노이즈 주입을 방지하기 위한 가드

플래그 제어:
  HOOK_USER_PROMPT_KANBAN=true/false (.claude-organic/.settings)
  기본값은 비활성(flags에 미정의 시 is_enabled가 True를 반환하지만,
  dispatch() 내부의 is_enabled 기본값 동작을 따름)

디버그 로그:
  HOOK_USER_PROMPT_DEBUG=true 설정 시 .claude-organic/runs/.user_prompt_hook.log 에 append.
  off-by-default.
"""

from __future__ import annotations

import json
import os
import sys

# ---- 디버그 로거 (off-by-default) ----------------------------------------

def _debug_log(msg: str) -> None:
    """HOOK_USER_PROMPT_DEBUG=true 일 때만 로그를 append한다.

    Args:
        msg: 로그 메시지 (개행 자동 추가).
    """
    if os.environ.get('HOOK_USER_PROMPT_DEBUG', '').lower() not in ('true', '1', 'yes', 'on'):
        return
    try:
        # dispatcher.py의 _find_project_root에 의존하기 전에 독립적으로 탐색
        hooks_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.normpath(os.path.join(hooks_dir, '..', '..'))
        log_path = os.path.join(project_root, '.claude-organic', 'runs', '.user_prompt_hook.log')
        runs_dir = os.path.dirname(log_path)
        if os.path.isdir(runs_dir):
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
    except Exception:
        pass


# ---- dispatcher 임포트 (예외 안전) ----------------------------------------

_dispatcher_loaded = False
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from dispatcher import (
        collect_exit_codes,
        collect_outputs,
        dispatch,
        load_env_flags,
        scripts_dir,
    )
    _dispatcher_loaded = True
except Exception as _e:
    _debug_log(f"[user-prompt-submit] dispatcher import failed: {_e}")


# ---- 메인 세션 가드 --------------------------------------------------------

def _is_main_session(stdin_data: dict) -> bool:
    """현재 세션이 메인 세션인지 판별한다.

    결정 로직 (우선순위 순):

    1. _WF_SESSION_TYPE 환경변수:
       - 값이 "workflow" 이면 → 워크플로우 세션 → False
       - 값이 "main" 이면 → 메인 세션 → True
       - 미정의 또는 "unknown" 이면 → 다음 조건으로 계속

    2. stdin JSON 의 "cwd" 필드:
       - ".claude-organic/worktrees/" 를 포함하면 → 워크트리 세션 → False
       - (CLAUDE_PROJECT_DIR 을 참고하여 절대경로 기반으로 판별)

    3. transcript_path 인근 .context.json 존재 여부 (보조):
       - transcript_path 가 있으면 상위 디렉터리 계층을 탐색하여
         "implement/.context.json" 패턴이 발견되면 → 워크플로우 세션 → False
       - 이 검사는 보조 시그널이며 1, 2번과 결합하여 판단

    4. 보수적 기본값:
       - 위 모든 조건으로 판단 불가 시 → False (빈 출력, 안전 방향)
       - 오판 시 메인 세션에 칸반 미주입 (무해) vs 워크플로우 세션에 노이즈 주입 (해로움)
       - 보수적 방향이 더 안전하므로 False 기본

    session-start.py 와의 차이:
       - session-start.py 는 inject_prompt.py 에 판별 위임 (tmux 기반)
       - 본 스크립트는 stdin JSON cwd + 환경변수로 직접 판별
       - tmux 미사용 환경에서도 동작하도록 설계

    Args:
        stdin_data: stdin에서 파싱한 UserPromptSubmit JSON dict.

    Returns:
        True 이면 메인 세션 (hook 출력 허용).
        False 이면 워크플로우/워크트리/불명 세션 (빈 stdout + exit 0).
    """
    # --- 1. _WF_SESSION_TYPE 환경변수 (가장 신뢰도 높음) ---
    wf_session_type = os.environ.get('_WF_SESSION_TYPE', '').strip().lower()
    if wf_session_type == 'workflow':
        _debug_log('[user-prompt-submit] guard: _WF_SESSION_TYPE=workflow → not main')
        return False
    if wf_session_type == 'main':
        _debug_log('[user-prompt-submit] guard: _WF_SESSION_TYPE=main → main')
        return True

    # --- 2. stdin JSON cwd 필드 — 워크트리 경로 포함 여부 ---
    cwd = stdin_data.get('cwd', '') or ''
    worktree_marker = os.path.join('.claude-organic', 'worktrees') + os.sep
    # 절대경로 정규화 비교 (POSIX + Windows 혼용 방지)
    cwd_norm = cwd.replace('\\', '/')
    if '/.claude-organic/worktrees/' in cwd_norm:
        _debug_log(f'[user-prompt-submit] guard: cwd contains worktrees/ → not main: {cwd!r}')
        return False

    # CLAUDE_PROJECT_DIR 기반 워크트리 절대경로 비교
    project_dir = os.environ.get('CLAUDE_PROJECT_DIR', '')
    if project_dir and cwd:
        worktree_abs = os.path.join(project_dir, '.claude-organic', 'worktrees')
        cwd_abs = os.path.abspath(cwd)
        try:
            if os.path.commonpath([cwd_abs, worktree_abs]) == worktree_abs:
                _debug_log(f'[user-prompt-submit] guard: cwd under CLAUDE_PROJECT_DIR/worktrees → not main: {cwd!r}')
                return False
        except (ValueError, OSError):
            pass

    # --- 3. transcript_path 인근 .context.json 존재 여부 (보조) ---
    transcript_path = stdin_data.get('transcript_path', '') or ''
    if transcript_path:
        # transcript_path 의 상위 디렉터리를 최대 4단계까지 탐색
        # 워크플로우 runs 경로: .claude-organic/runs/YYYYMMDD-HHMMSS/티켓명/implement/.context.json
        check_dir = os.path.dirname(transcript_path)
        for _ in range(5):
            if not check_dir or check_dir == os.path.dirname(check_dir):
                break
            context_json = os.path.join(check_dir, 'implement', '.context.json')
            if os.path.isfile(context_json):
                _debug_log(f'[user-prompt-submit] guard: .context.json found → not main: {context_json!r}')
                return False
            # transcript가 implement/ 안에 있는 경우 직접 확인
            direct_context = os.path.join(check_dir, '.context.json')
            if os.path.isfile(direct_context):
                _debug_log(f'[user-prompt-submit] guard: .context.json found (direct) → not main: {direct_context!r}')
                return False
            check_dir = os.path.dirname(check_dir)

    # --- 4. 보수적 기본값: cwd가 .claude-organic/runs/ 아래이면 워크플로우 세션 ---
    if '/.claude-organic/runs/' in cwd_norm:
        _debug_log(f'[user-prompt-submit] guard: cwd contains /runs/ → not main: {cwd!r}')
        return False

    # --- 5. 판별 불가: 보수적으로 True 반환 (cwd가 일반 경로이면 메인 세션으로 추정) ---
    # 워크트리 + 워크플로우 경로 모두 해당하지 않으면 메인 세션
    _debug_log(f'[user-prompt-submit] guard: no worktree/workflow signals → assuming main: {cwd!r}')
    return True


# ---- main ------------------------------------------------------------------

def main() -> None:
    """UserPromptSubmit hook 메인 진입점.

    흐름:
      1. stdin 읽기 + JSON 파싱
      2. _is_main_session() 로 메인 세션 여부 확인
         → False 면 즉시 sys.exit(0) (빈 stdout)
      3. dispatcher 로드 여부 확인
         → 미로드 시 sys.exit(0) (빈 stdout, graceful degrade)
      4. dispatch('HOOK_USER_PROMPT_KANBAN', ..., capture_output=True) 호출
      5. collect_outputs([r]) 결과를 sys.stdout.buffer.write 로 통과
      6. collect_exit_codes([r]) 로 종료

    모든 예외 경로에서 빈 stdout + sys.exit(0) 을 보장한다.
    사용자 turn 차단은 절대 발생하지 않는다.
    """
    try:
        # 1. stdin 읽기
        try:
            stdin_raw = sys.stdin.buffer.read()
        except Exception:
            stdin_raw = b''

        try:
            stdin_data: dict = json.loads(stdin_raw) if stdin_raw else {}
        except (json.JSONDecodeError, ValueError):
            stdin_data = {}

        _debug_log(f'[user-prompt-submit] hook_event_name={stdin_data.get("hook_event_name")!r} cwd={stdin_data.get("cwd")!r}')

        # 2. 메인 세션 가드
        if not _is_main_session(stdin_data):
            _debug_log('[user-prompt-submit] not main session → exit 0 (empty stdout)')
            sys.exit(0)

        # 3. dispatcher 로드 확인
        if not _dispatcher_loaded:
            _debug_log('[user-prompt-submit] dispatcher not loaded → exit 0')
            sys.exit(0)

        # 4. 플래그 로드 + dispatch
        flags = load_env_flags()
        target_script = scripts_dir('hook-handlers', 'inject_kanban_context.py')
        _debug_log(f'[user-prompt-submit] dispatching to {target_script!r}')

        r = dispatch(
            'HOOK_USER_PROMPT_KANBAN',
            target_script,
            stdin_raw,
            flags=flags,
            capture_output=True,
        )

        # 5. 출력 통과
        output = collect_outputs([r])
        if output:
            sys.stdout.buffer.write(output)
            sys.stdout.buffer.flush()

        # 6. 종료
        sys.exit(collect_exit_codes([r]))

    except SystemExit:
        raise  # sys.exit() 는 그대로 통과

    except Exception as e:
        _debug_log(f'[user-prompt-submit] unhandled exception: {type(e).__name__}: {e}')
        # 예외 안전장치: 사용자 turn 차단 금지 → 빈 stdout + exit 0
        sys.exit(0)


if __name__ == '__main__':
    main()
