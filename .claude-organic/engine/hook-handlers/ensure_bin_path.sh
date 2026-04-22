#!/usr/bin/env python3
"""ensure_bin_path.sh - Claude Code Bash tool 환경에 .claude-organic/bin PATH를 주입한다.

SessionStart hook에서 호출되며, CLAUDE_ENV_FILE에 PATH export 문을 작성한다.
Claude Code는 CLAUDE_ENV_FILE의 export 문을 이후 Bash tool 실행 환경에 적용한다.

stdout: 없음 (SessionStart hook stdout은 system prompt로 주입되므로 아무것도 출력하지 않는다)
stderr: 디버그 로그 (필요 시)
exit code: 0 (항상 성공)
"""

from __future__ import annotations

import os
import sys


def main() -> None:
    """CLAUDE_ENV_FILE에 .claude-organic/bin PATH export를 작성한다.

    CLAUDE_PROJECT_DIR 환경변수를 사용하여 bin 디렉터리 경로를 결정한다.
    CLAUDE_ENV_FILE이 설정되지 않았거나 bin 디렉터리가 없으면 조용히 종료한다.
    """
    env_file = os.environ.get('CLAUDE_ENV_FILE', '')
    if not env_file:
        sys.exit(0)

    project_dir = os.environ.get('CLAUDE_PROJECT_DIR', '')
    if not project_dir:
        # CLAUDE_PROJECT_DIR이 없으면 hooks 디렉터리 기준으로 추론
        # ensure_bin_path.sh는 .claude-organic/engine/hook-handlers/ 에 위치
        # 따라서 ../../../../ = project root
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.normpath(os.path.join(script_dir, '..', '..', '..'))

    bin_dir = os.path.join(project_dir, '.claude-organic', 'bin')
    if not os.path.isdir(bin_dir):
        # bin 디렉터리가 없으면 아무것도 하지 않음
        sys.exit(0)

    # CLAUDE_ENV_FILE에 PATH export 추가
    # 이미 해당 경로가 포함되어 있으면 중복 추가 방지
    current_path = os.environ.get('PATH', '')
    if bin_dir in current_path.split(':'):
        # 이미 PATH에 포함됨 (현재 프로세스 환경 기준)
        sys.exit(0)

    export_line = f'export PATH="{bin_dir}:$PATH"\n'

    try:
        # 파일이 이미 있고 해당 경로가 포함되어 있으면 스킵
        existing = ''
        if os.path.isfile(env_file):
            with open(env_file, 'r', encoding='utf-8') as f:
                existing = f.read()
        if bin_dir in existing:
            sys.exit(0)

        with open(env_file, 'a', encoding='utf-8') as f:
            f.write(export_line)
    except OSError:
        # 파일 쓰기 실패 시 조용히 종료
        pass

    sys.exit(0)


if __name__ == '__main__':
    main()
