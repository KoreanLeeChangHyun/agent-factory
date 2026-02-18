#!/usr/bin/env python3
"""
git_config.py - Git Config 자동 설정 스크립트

.claude.env에서 Git 설정 정보를 읽어 git config를 자동으로 설정합니다.

사용법: python3 git_config.py [--global|--local]
  --global  전역 설정 (~/.gitconfig) [기본값]
  --local   로컬 설정 (.git/config)

환경변수 (.claude.env에서 로드):
  CLAUDE_CODE_GIT_USER_NAME    - Git user.name (필수)
  CLAUDE_CODE_GIT_USER_EMAIL   - Git user.email (필수)
  CLAUDE_CODE_GITHUB_USERNAME  - GitHub 사용자명 (선택)
  CLAUDE_CODE_SSH_KEY_GITHUB   - GitHub SSH 키 경로 (선택)
"""

import os
import subprocess
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
sys.path.insert(0, _SCRIPTS_DIR)

from _utils.env_utils import read_env

_PROJECT_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
_ENV_FILE = os.path.join(_PROJECT_ROOT, ".claude.env")


def _git_config_get(scope, key):
    """git config 값을 읽기."""
    try:
        return subprocess.check_output(
            ["git", "config", scope, key],
            stderr=subprocess.DEVNULL, timeout=5
        ).decode().strip()
    except Exception:
        return "(미설정)"


def main():
    # --- 옵션 파싱 ---
    scope = "--global"
    if len(sys.argv) >= 2:
        if sys.argv[1] == "--global":
            scope = "--global"
        elif sys.argv[1] == "--local":
            scope = "--local"
        else:
            print(f"[ERROR] 알 수 없는 옵션: {sys.argv[1]}", file=sys.stderr)
            print(f"사용법: {sys.argv[0]} [--global|--local]")
            sys.exit(1)

    scope_label = "global" if scope == "--global" else "local"

    # --- .claude.env 파일 확인 ---
    if not os.path.isfile(_ENV_FILE):
        print(f"[ERROR] .claude.env 파일이 존재하지 않습니다: {_ENV_FILE}", file=sys.stderr)
        sys.exit(1)

    # --- 환경변수 로드 ---
    git_user_name = read_env("CLAUDE_CODE_GIT_USER_NAME", env_file=_ENV_FILE)
    git_user_email = read_env("CLAUDE_CODE_GIT_USER_EMAIL", env_file=_ENV_FILE)
    # 현재 미사용 - 향후 GitHub API 연동 예정
    _github_username = read_env("CLAUDE_CODE_GITHUB_USERNAME", env_file=_ENV_FILE)
    ssh_key_github = read_env("CLAUDE_CODE_SSH_KEY_GITHUB", env_file=_ENV_FILE)

    # --- 필수 환경변수 검증 ---
    if not git_user_name:
        print("[ERROR] CLAUDE_CODE_GIT_USER_NAME이 .claude.env에 설정되지 않았습니다.", file=sys.stderr)
        sys.exit(1)

    if not git_user_email:
        print("[ERROR] CLAUDE_CODE_GIT_USER_EMAIL이 .claude.env에 설정되지 않았습니다.", file=sys.stderr)
        sys.exit(1)

    # --- Before 상태 수집 ---
    before_name = _git_config_get(scope, "user.name")
    before_email = _git_config_get(scope, "user.email")
    before_ssh = _git_config_get(scope, "core.sshCommand")

    # --- 설정 적용 ---
    print(f"[INFO] Git config ({scope_label}) 설정을 적용합니다...")

    subprocess.run(["git", "config", scope, "user.name", git_user_name], check=True, timeout=5)
    print(f"[OK] user.name = {git_user_name}")

    subprocess.run(["git", "config", scope, "user.email", git_user_email], check=True, timeout=5)
    print(f"[OK] user.email = {git_user_email}")

    # SSH 키 설정 (파일 존재 시)
    if ssh_key_github:
        if os.path.isfile(ssh_key_github):
            ssh_cmd = f'ssh -i "{ssh_key_github}" -o IdentitiesOnly=yes'
            subprocess.run(["git", "config", scope, "core.sshCommand", ssh_cmd], check=True, timeout=5)
            print(f"[OK] core.sshCommand = {ssh_cmd}")
        else:
            print(f"[WARN] SSH 키 파일이 존재하지 않습니다: {ssh_key_github} (SSH 설정 스킵)")

    # --- After 상태 수집 ---
    after_name = _git_config_get(scope, "user.name")
    after_email = _git_config_get(scope, "user.email")
    after_ssh = _git_config_get(scope, "core.sshCommand")

    # --- Before/After 비교 출력 ---
    print()
    print("==========================================")
    print(f" Git Config 변경 결과 ({scope_label})")
    print("==========================================")
    print(f"{'설정':<20s} {'Before':<30s} {'After':<30s}")
    print(f"{'----':<20s} {'------':<30s} {'-----':<30s}")
    print(f"{'user.name':<20s} {before_name:<30s} {after_name:<30s}")
    print(f"{'user.email':<20s} {before_email:<30s} {after_email:<30s}")
    print(f"{'core.sshCommand':<20s} {before_ssh:<30s} {after_ssh:<30s}")
    print("==========================================")
    print()
    print(f"[OK] Git config ({scope_label}) 설정 완료")


if __name__ == "__main__":
    main()
