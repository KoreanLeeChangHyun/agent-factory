#!/usr/bin/env -S python3 -u
"""Git Config 자동 설정 스크립트.

.agent-factory/.settings에서 Git 설정 정보를 읽어 git config를 자동으로 설정합니다.

주요 함수:
    main: Git 설정 적용 진입점

사용법: python3 git_config.py [--global|--local]
  --global  전역 설정 (~/.gitconfig) [기본값]
  --local   로컬 설정 (.git/config)

환경변수 (.agent-factory/.settings에서 로드):
  CLAUDE_CODE_GIT_USER_NAME    - Git user.name (필수)
  CLAUDE_CODE_GIT_USER_EMAIL   - Git user.email (필수)
  CLAUDE_CODE_GITHUB_USERNAME  - GitHub 사용자명 (선택)
  CLAUDE_CODE_SSH_KEY_GITHUB   - GitHub SSH 키 경로 (선택)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ENGINE_DIR = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", ".."))
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from common import read_env
from flow.cli_utils import build_common_epilog

_PROJECT_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", "..", ".."))
_CW_DIR = os.path.join(_PROJECT_ROOT, ".agent-factory")
_ENV_FILE = os.path.join(_CW_DIR, ".settings")


def _git_config_get(scope: str, key: str) -> str:
    """git config 값을 읽어 반환한다.

    Args:
        scope: git config 범위 ('--global' 또는 '--local')
        key: 읽을 설정 키 (예: 'user.name')

    Returns:
        설정 값 문자열. 설정이 없거나 오류 발생 시 '(Not set)' 반환.
    """
    try:
        return subprocess.check_output(
            ["git", "config", scope, key],
            stderr=subprocess.DEVNULL, timeout=5
        ).decode().strip()
    except Exception:
        return "(Not set)"


def _build_parser() -> argparse.ArgumentParser:
    """git_config 전용 ArgumentParser를 생성하여 반환한다.

    --global / --local 은 mutually exclusive group으로 구성되며
    기본값은 --global 이다.

    Returns:
        구성된 ArgumentParser 인스턴스.
    """
    parser = argparse.ArgumentParser(
        prog="flow-gitconfig",
        description=(
            "Read Git configuration information from .agent-factory/.settings"
            "Automatically applies git config."
        ),
        epilog=build_common_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    scope_group = parser.add_mutually_exclusive_group()
    scope_group.add_argument(
        "--global",
        dest="scope",
        action="store_const",
        const="--global",
        help="Applies to global settings (~/.gitconfig) [default]",
    )
    scope_group.add_argument(
        "--local",
        dest="scope",
        action="store_const",
        const="--local",
        help="Applies to local settings (.git/config)",
    )
    return parser


def main() -> None:
    """Git config 자동 설정의 진입점.

    .agent-factory/.settings에서 환경변수를 읽어 git user.name, user.email,
    core.sshCommand를 지정된 범위(global/local)에 적용한다.
    변경 전후 상태를 비교하여 출력한다.

    Raises:
        SystemExit: 설정 파일 부재, 필수 환경변수 누락, 알 수 없는 옵션 지정 시
    """
    # --- Option parsing ---
    parser = _build_parser()
    args = parser.parse_args()

    scope = args.scope if args.scope is not None else "--global"
    scope_label = "global" if scope == "--global" else "local"

    # --- Check .settings file ---
    if not os.path.isfile(_ENV_FILE):
        print(f"[ERROR] Configuration file does not exist: {_ENV_FILE}", file=sys.stderr)
        sys.exit(1)

    # --- Load environment variables ---
    git_user_name = read_env("CLAUDE_CODE_GIT_USER_NAME", env_file=_ENV_FILE)
    git_user_email = read_env("CLAUDE_CODE_GIT_USER_EMAIL", env_file=_ENV_FILE)
    # Currently not in use - expected to be integrated with GitHub API in the future
    _github_username = read_env("CLAUDE_CODE_GITHUB_USERNAME", env_file=_ENV_FILE)
    ssh_key_github = read_env("CLAUDE_CODE_SSH_KEY_GITHUB", env_file=_ENV_FILE)

    # --- Verification of required environment variables ---
    if not git_user_name:
        print("[ERROR] CLAUDE_CODE_GIT_USER_NAME is not set in .settings.", file=sys.stderr)
        sys.exit(1)

    if not git_user_email:
        print("[ERROR] CLAUDE_CODE_GIT_USER_EMAIL is not set in .settings.", file=sys.stderr)
        sys.exit(1)

    # --- Before state collection ---
    before_name = _git_config_get(scope, "user.name")
    before_email = _git_config_get(scope, "user.email")
    before_ssh = _git_config_get(scope, "core.sshCommand")

    # --- Apply settings ---
    print(f"[STATE] GITCONFIG ({scope_label})", flush=True)
    print(f">> user.name={git_user_name}, user.email={git_user_email}", flush=True)
    print(f"[INFO] Git config ({scope_label}) Apply settings...")

    subprocess.run(["git", "config", scope, "user.name", git_user_name], check=True, timeout=5)
    print(f"[OK] user.name = {git_user_name}")

    subprocess.run(["git", "config", scope, "user.email", git_user_email], check=True, timeout=5)
    print(f"[OK] user.email = {git_user_email}")

    # Set SSH key (if file exists)
    if ssh_key_github:
        if os.path.isfile(ssh_key_github):
            ssh_cmd = f'ssh -i "{ssh_key_github}" -o IdentitiesOnly=yes'
            subprocess.run(["git", "config", scope, "core.sshCommand", ssh_cmd], check=True, timeout=5)
            print(f"[OK] core.sshCommand = {ssh_cmd}")
        else:
            print(f"[WARN] SSH key file does not exist: {ssh_key_github} (Skip SSH configuration)")

    # --- After status collection ---
    after_name = _git_config_get(scope, "user.name")
    after_email = _git_config_get(scope, "user.email")
    after_ssh = _git_config_get(scope, "core.sshCommand")

    # --- Before/After comparison output ---
    print()
    print("==========================================")
    print(f"Git Config change results ({scope_label})")
    print("==========================================")
    print(f"{'Set':<20s} {'Before':<30s} {'After':<30s}")
    print(f"{'----':<20s} {'------':<30s} {'-----':<30s}")
    print(f"{'user.name':<20s} {before_name:<30s} {after_name:<30s}")
    print(f"{'user.email':<20s} {before_email:<30s} {after_email:<30s}")
    print(f"{'core.sshCommand':<20s} {before_ssh:<30s} {after_ssh:<30s}")
    print("==========================================")
    print()
    print(f"[OK] Git config ({scope_label}) setup complete")


if __name__ == "__main__":
    main()
