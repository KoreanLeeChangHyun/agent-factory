#!/usr/bin/env python3
"""ensure_bin_path.sh - Claude Code Bash tool 환경에 .agent-factory/bin PATH를 주입한다.

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
    """CLAUDE_ENV_FILE에 .agent-factory/bin PATH export를 작성한다.

    CLAUDE_PROJECT_DIR 환경변수를 사용하여 bin 디렉터리 경로를 결정한다.
    CLAUDE_ENV_FILE이 설정되지 않았거나 bin 디렉터리가 없으면 조용히 종료한다.
    """
    env_file = os.environ.get('CLAUDE_ENV_FILE', '')
    if not env_file:
        sys.exit(0)

    project_dir = os.environ.get('CLAUDE_PROJECT_DIR', '')
    if not project_dir:
        # If CLAUDE_PROJECT_DIR does not exist, it is inferred based on the hooks directory.
        # ensure_bin_path.sh is located in .agent-factory/engine/apps/hooks/
        # So ../../../../ = project root
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.normpath(os.path.join(script_dir, '..', '..', '..', '..'))

    bin_dir = os.path.join(project_dir, '.agent-factory', 'bin')
    if not os.path.isdir(bin_dir):
        # Do nothing if there is no bin directory
        sys.exit(0)

    # Add PATH export to CLAUDE_ENV_FILE
    # Avoid adding duplicates if the path is already included
    current_path = os.environ.get('PATH', '')
    if bin_dir in current_path.split(':'):
        # Already included in PATH (based on current process environment)
        sys.exit(0)

    export_line = f'export PATH="{bin_dir}:$PATH"\n'

    try:
        # Skip if the file already exists and contains its path
        existing = ''
        if os.path.isfile(env_file):
            with open(env_file, 'r', encoding='utf-8') as f:
                existing = f.read()
        if bin_dir in existing:
            sys.exit(0)

        with open(env_file, 'a', encoding='utf-8') as f:
            f.write(export_line)
    except OSError:
        # Quietly exits when file writing fails
        pass

    sys.exit(0)


if __name__ == '__main__':
    main()
