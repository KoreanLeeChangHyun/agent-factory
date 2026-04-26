#!/usr/bin/env -S python3 -u
"""Session-start dispatcher.

SessionStart hook 스크립트를 디스패치한다.
dispatcher.py 유틸리티를 사용하여 플래그 기반 조건부 실행을 수행한다.

워크플로우 세션 전용 프롬프트 주입(inject_prompt.py)을 담당한다.
메인 세션에서는 inject_prompt.py가 아무것도 출력하지 않고 즉시 종료하므로
시스템 프롬프트는 CLAUDE.md + .claude/rules/workflow.md 가 담당한다.

또한 CLAUDE_ENV_FILE 메커니즘을 통해 Bash tool 환경에 .claude-organic/bin
PATH를 주입한다(ensure_bin_path.sh).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dispatcher import (
    collect_exit_codes,
    dispatch,
    load_env_flags,
    scripts_dir,
)


def main() -> None:
    """SessionStart 훅을 디스패치한다.

    stdin(SessionStart JSON 페이로드)을 읽고 다음 두 작업을 수행한다:
    1. CLAUDE_ENV_FILE에 .claude-organic/bin PATH export를 작성하여
       이후 Bash tool 호출 환경에 flow-* 명령어가 resolve되도록 보장한다.
    2. 워크플로우 세션 전용 system-prompt-wf.xml을 stdout에 주입한다.

    HOOK_SESSION_SYSTEM_PROMPT 플래그가 false이면 워크플로우 세션에서도
    프롬프트 주입이 비활성화된다.
    """
    stdin_data = sys.stdin.buffer.read()
    flags = load_env_flags()
    sync_results = []

    # --- Bash tool 환경 PATH 주입 (stdout 없음, CLAUDE_ENV_FILE에 export 작성) ---
    # ensure_bin_path.sh는 CLAUDE_ENV_FILE에 .claude-organic/bin PATH export를 추가한다.
    # Claude Code는 CLAUDE_ENV_FILE의 export 문을 이후 Bash tool 실행 환경에 적용한다.
    # stdout에 아무것도 출력하지 않으므로 system prompt 주입에 영향 없다.
    r = dispatch(
        'HOOK_BIN_PATH_INJECT',
        scripts_dir('session_start', 'ensure_bin_path.sh'),
        stdin_data,
        flags=flags,
        capture_output=True,
    )
    sync_results.append(r)

    # --- 워크플로우 세션 전용 system-prompt-wf.xml 주입 (sync, stdout passthrough) ---
    # inject_prompt.py가 워크플로우 세션 여부를 판별하여 조건부 출력한다.
    # 메인 세션에서는 inject_prompt.py가 아무것도 출력하지 않고 즉시 종료한다.
    r = dispatch(
        'HOOK_SESSION_SYSTEM_PROMPT',
        scripts_dir('flow', 'inject_prompt.py'),
        stdin_data,
        flags=flags,
    )
    sync_results.append(r)

    # --- Memory GC session trigger (fire-and-forget) ---
    # MEMORY_GC_AUTO_TRIGGERS 에 'session' 토큰이 있을 때만 발화. wrapper 가 자체 검사.
    # subprocess.Popen 으로 background 실행 후 즉시 반환 — 세션 시작 지연 없음.
    _trigger_memory_gc_session()

    sys.exit(collect_exit_codes(sync_results))


def _trigger_memory_gc_session() -> None:
    import subprocess
    project_dir = os.environ.get('CLAUDE_PROJECT_DIR') or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    ).rsplit('/.claude-organic', 1)[0]
    gc_bin = os.path.join(project_dir, '.claude-organic', 'bin', 'flow-memory-gc')
    if not os.path.isfile(gc_bin):
        return
    try:
        subprocess.Popen(
            [gc_bin, 'auto', '--trigger', 'session'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        pass


if __name__ == '__main__':
    main()
