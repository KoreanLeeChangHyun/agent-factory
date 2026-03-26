"""env_manager.py - 환경변수 관리 모듈.

.claude.workflow/.settings(.env 폴백) 파일의 환경 변수를 set/unset하는 책임을 담당한다.
HOOK_*, GUARD_* 접두사 및 HOOKS_EDIT_ALLOWED 키만 허용하는
화이트리스트 기반 환경변수 관리를 수행한다.

책임 범위:
    - .claude.workflow/.settings(.env 폴백) 환경변수 설정 (set)
    - .claude.workflow/.settings(.env 폴백) 환경변수 해제 (unset)
    - KEY 화이트리스트 검증
    - 원자적 파일 쓰기
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

# scripts 디렉터리를 sys.path에 추가하여 common, data 패키지 import 허용
_scripts_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from common import resolve_project_root

PROJECT_ROOT: str = resolve_project_root()


def env_manage(action: str, key: str, value: str = "") -> str:
    """.claude.workflow/.settings(.env 폴백) 파일의 환경 변수를 관리한다.

    .settings가 존재하면 해당 파일을 수정하고, 없으면 .env를 수정한다.

    Args:
        action: 수행할 동작. 허용값: 'set', 'unset'.
        key: 환경 변수 키. HOOK_* 또는 GUARD_* 접두사, 또는 HOOKS_EDIT_ALLOWED만 허용.
        value: 설정할 값 (action='set'일 때 필수)

    Returns:
        처리 결과 문자열. 예: 'env -> set HOOK_FOO=bar',
        'env -> unset GUARD_BAR', 'env -> skipped (missing args)', 'env -> failed'.
    """
    if not action or not key:
        print("[WARN] env: action(set|unset)과 KEY 인자가 필요합니다.", file=sys.stderr)
        return "env -> skipped (missing args)"

    if action not in ("set", "unset"):
        print(f"[WARN] env: action은 set 또는 unset만 허용됩니다. got={action}", file=sys.stderr)
        return "env -> skipped (invalid action)"

    if action == "set" and not value:
        print("[WARN] env: set 명령에는 VALUE 인자가 필요합니다.", file=sys.stderr)
        return "env -> skipped (missing value)"

    # KEY 화이트리스트 검증
    if not key.startswith("HOOK_") and not key.startswith("GUARD_") and key != "HOOKS_EDIT_ALLOWED":
        print(f"[WARN] env: 허용되지 않는 KEY입니다: {key} (허용: HOOK_*, GUARD_* 접두사)", file=sys.stderr)
        return "env -> skipped (disallowed key)"

    # .settings 우선, .env 폴백
    cw_dir: str = os.path.join(PROJECT_ROOT, ".claude.workflow")
    settings_path: str = os.path.join(cw_dir, ".settings")
    env_file: str = settings_path if os.path.isfile(settings_path) else os.path.join(cw_dir, ".env")
    if not os.path.isfile(env_file):
        print(f"[WARN] env: 설정 파일을 찾을 수 없습니다: {env_file}", file=sys.stderr)
        return "env -> skipped (file not found)"

    try:
        with open(env_file, "r", encoding="utf-8") as f:
            lines: list[str] = f.readlines()

        label: str = ""

        if action == "set":
            found: bool = False
            new_lines: list[str] = []
            for line in lines:
                stripped: str = line.strip()
                if stripped.startswith(key + "="):
                    new_lines.append(f"{key}={value}\n")
                    found = True
                else:
                    new_lines.append(line)

            if not found:
                if new_lines and not new_lines[-1].endswith("\n"):
                    new_lines[-1] += "\n"
                new_lines.append(f"{key}={value}\n")

            lines = new_lines
            label = f"env -> set {key}={value}"

        elif action == "unset":
            new_lines = []
            i: int = 0
            while i < len(lines):
                stripped = lines[i].strip()
                if stripped.startswith(key + "="):
                    if new_lines and new_lines[-1].strip().startswith("#"):
                        new_lines.pop()
                    i += 1
                    continue
                new_lines.append(lines[i])
                i += 1

            lines = new_lines
            label = f"env -> unset {key}"

        # 원자적 쓰기
        dir_name: str = os.path.dirname(env_file)
        fd: int
        tmp_path: str
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.writelines(lines)
            shutil.move(tmp_path, env_file)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        return label
    except Exception as e:
        print(f"[WARN] env failed: {e}", file=sys.stderr)
        return "env -> failed"
