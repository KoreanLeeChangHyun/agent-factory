#!/usr/bin/env -S python3 -u
"""
env_utils.py - .claude.env 공통 파싱 유틸리티

.claude.env 파일에서 KEY=value 형식의 환경변수를 읽고 쓰는 공통 함수를 제공합니다.
기존 env-utils.sh의 Python 1:1 포팅.

제공 함수:
    read_env(key, default, env_file)  - .claude.env에서 값 읽기 (따옴표 제거, 경로 확장 포함)
    set_env(key, value, env_file)     - .claude.env에 KEY=value 추가/갱신

사전 조건:
    - env_file 인자 또는 ENV_FILE 환경변수가 .claude.env 경로를 가리켜야 함
    - env_file이 지정되지 않으면 기본값을 반환
"""

import os
import tempfile
import shutil

# 기본 ENV_FILE 경로 (호출자가 명시적으로 설정하지 않으면 환경변수에서 읽음)
_DEFAULT_ENV_FILE = os.environ.get("ENV_FILE", "")


def _resolve_env_file(env_file=None):
    """env_file 경로를 해석. None이면 환경변수 또는 프로젝트 루트에서 추론."""
    if env_file:
        return env_file
    if _DEFAULT_ENV_FILE:
        return _DEFAULT_ENV_FILE
    # 프로젝트 루트 추론: _utils -> scripts -> .claude -> project root
    utils_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(utils_dir, "..", "..", ".."))
    return os.path.join(project_root, ".claude.env")


def read_env(key, default="", env_file=None):
    """
    .claude.env에서 환경변수 읽기.

    - 중복 키 방어: 첫 번째 매칭만 사용
    - 따옴표 제거: 앞뒤 큰따옴표/작은따옴표 제거
    - $HOME 확장: $HOME을 실제 홈 디렉토리로 치환
    - ~ 확장: 선두 ~를 실제 홈 디렉토리로 치환

    Args:
        key: 환경변수 키 이름
        default: 키가 없을 때 반환할 기본값
        env_file: .claude.env 파일 경로 (None이면 자동 해석)

    Returns:
        str: 환경변수 값 또는 기본값
    """
    resolved = _resolve_env_file(env_file)
    if not resolved or not os.path.isfile(resolved):
        return default

    prefix = f"{key}="
    try:
        with open(resolved, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith(prefix):
                    value = stripped[len(prefix):]
                    # 따옴표 제거 (앞뒤 큰따옴표 또는 작은따옴표)
                    if len(value) >= 2:
                        if (value[0] == '"' and value[-1] == '"') or \
                           (value[0] == "'" and value[-1] == "'"):
                            value = value[1:-1]
                    # $HOME 확장
                    home = os.environ.get("HOME", "")
                    if home:
                        value = value.replace("$HOME", home)
                        # ~ 확장 (선두 ~ 만)
                        if value.startswith("~"):
                            value = home + value[1:]
                    return value
    except (IOError, OSError):
        pass

    return default


def set_env(key, value, env_file=None):
    """
    .claude.env에 KEY=value 추가/갱신.

    - 파일이 없으면 헤더와 함께 생성
    - 기존 키가 있으면 업데이트 (임시 파일 + mv 방식)
    - 새 키이면 파일 끝에 추가

    Args:
        key: 환경변수 키 이름
        value: 설정할 값
        env_file: .claude.env 파일 경로 (None이면 자동 해석)
    """
    resolved = _resolve_env_file(env_file)
    if not resolved:
        return

    if not os.path.isfile(resolved):
        # 파일이 없으면 헤더와 함께 생성
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(
                "# ============================================\n"
                "# Claude Code 환경 변수\n"
                "# ============================================\n"
                "#\n"
                "# 이 파일은 Claude Code Hook 스크립트에서 사용하는 환경 변수를 정의합니다.\n"
                "# 형식: KEY=value (표준 .env 문법)\n"
                "# ============================================\n"
                "\n"
            )

    prefix = f"{key}="
    try:
        with open(resolved, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (IOError, OSError):
        lines = []

    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(prefix):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        # 마지막 줄에 줄바꿈이 없으면 추가
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"{key}={value}\n")

    # 원자적 쓰기: 임시 파일 + mv
    dir_name = os.path.dirname(resolved)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        shutil.move(tmp_path, resolved)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
