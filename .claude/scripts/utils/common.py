#!/usr/bin/env -S python3 -u
"""
common.py - 프로젝트 공통 유틸리티

프로젝트 루트 경로 해석, ANSI 색상 코드, JSON 원자적 쓰기,
registry.json 조회 등 전역적으로 사용되는 공통 기능을 제공합니다.

제공 함수/상수:
    resolve_project_root()          - 프로젝트 루트 경로 해석
    atomic_write_json(path, data)   - JSON 원자적 쓰기 (tmpfile + mv)
    resolve_work_dir(input_key)     - registry.json에서 YYYYMMDD-HHMMSS 키로 workDir 조회
    extract_registry_key(work_dir)  - workDir 경로에서 YYYYMMDD-HHMMSS 키 추출
    load_json_file(path)            - JSON 파일 로드 (실패 시 None)
    C_* 상수                        - ANSI 색상 코드
    PHASE_COLORS                    - phase별 색상 매핑
    colorize_phase(phase)           - phase 이름을 ANSI 색상으로 감싸서 반환
"""

import json
import os
import shutil
import sys
import tempfile

# -- sys.path 보장: 이 모듈이 직접 실행될 때를 위해 scripts/ 디렉터리 추가 --
_utils_dir = os.path.dirname(os.path.abspath(__file__))
_scripts_dir = os.path.dirname(_utils_dir)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

# =============================================================================
# 상수를 data.constants에서 import (re-export하여 하위 호환성 보장)
# =============================================================================
from data.constants import (  # noqa: E402
    C_RED,
    C_BLUE,
    C_GREEN,
    C_PURPLE,
    C_YELLOW,
    C_CYAN,
    C_GRAY,
    C_BOLD,
    C_DIM,
    C_RESET,
    PHASE_COLORS,
    TS_PATTERN,
)


def colorize_phase(phase):
    """
    phase 이름을 ANSI 색상으로 감싸서 반환.

    Args:
        phase: phase 이름 (INIT, PLAN, WORK, REPORT 등)

    Returns:
        str: 색상이 적용된 phase 문자열
    """
    color = PHASE_COLORS.get(phase, "")
    if color:
        return f"{color}{phase}{C_RESET}"
    return phase


def resolve_project_root(start_path=None):
    """
    프로젝트 루트 경로 해석.

    utils -> scripts -> .claude -> project root 순서로 상위 디렉터리를 탐색하여
    프로젝트 루트를 결정합니다.

    Args:
        start_path: 탐색 시작 경로 (None이면 이 파일의 위치 기준)

    Returns:
        str: 프로젝트 루트 절대 경로
    """
    if start_path:
        base = os.path.abspath(start_path)
    else:
        # utils -> scripts -> .claude -> project root
        utils_dir = os.path.dirname(os.path.abspath(__file__))
        base = os.path.normpath(os.path.join(utils_dir, "..", "..", ".."))
    return base


def load_json_file(path):
    """
    JSON 파일 로드. 실패 시 None 반환.

    Args:
        path: JSON 파일 경로

    Returns:
        파싱된 JSON 데이터 또는 None
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        return None


def atomic_write_json(path, data, indent=2):
    """
    JSON 원자적 쓰기 (임시 파일 + mv).

    Args:
        path: 쓰기 대상 파일 경로
        data: JSON 직렬화 가능한 데이터
        indent: JSON 들여쓰기 (기본 2)

    Raises:
        Exception: 쓰기 실패 시 (임시 파일은 자동 정리)
    """
    dir_name = os.path.dirname(path)
    os.makedirs(dir_name, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
            f.write("\n")
        shutil.move(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def extract_registry_key(work_dir):
    """
    workDir 경로에서 YYYYMMDD-HHMMSS 형식의 레지스트리 키 추출.

    중첩 구조: .../<YYYYMMDD-HHMMSS>/<workName>/<command>
    레거시 플랫 구조: .../<YYYYMMDD-HHMMSS>

    Args:
        work_dir: 워크플로우 디렉터리 경로

    Returns:
        str: YYYYMMDD-HHMMSS 형식 키
    """
    basename = os.path.basename(work_dir)
    if TS_PATTERN.match(basename):
        return basename

    # 중첩 구조: basename=<command>, parent=<workName>, grandparent=<YYYYMMDD-HHMMSS>
    grandparent = os.path.basename(os.path.dirname(os.path.dirname(work_dir)))
    if TS_PATTERN.match(grandparent):
        return grandparent

    # 폴백: 경로에서 YYYYMMDD-HHMMSS 패턴 탐색
    parts = work_dir.replace(os.sep, "/").split("/")
    for part in parts:
        if TS_PATTERN.match(part):
            return part

    # 최후 폴백
    return basename


def resolve_work_dir(input_key, project_root=None):
    """
    registry.json에서 YYYYMMDD-HHMMSS 단축 형식 키로 workDir 조회.

    YYYYMMDD-HHMMSS 패턴이 아닌 입력은 그대로 반환.

    Args:
        input_key: 워크플로우 키 또는 경로
        project_root: 프로젝트 루트 경로 (None이면 자동 해석)

    Returns:
        str: 해석된 workDir 경로 (상대 경로)
    """
    if not TS_PATTERN.match(input_key):
        return input_key

    if project_root is None:
        project_root = resolve_project_root()

    registry_file = os.path.join(project_root, ".workflow", "registry.json")
    registry = load_json_file(registry_file)

    if isinstance(registry, dict) and input_key in registry:
        entry = registry[input_key]
        if isinstance(entry, dict) and "workDir" in entry:
            return entry["workDir"]

    # 레거시 폴백
    fallback = f".workflow/{input_key}"
    print(
        f"[WARN] registry lookup failed for {input_key}, falling back to {fallback}",
        file=sys.stderr,
    )
    return fallback


def resolve_abs_work_dir(work_dir, project_root=None):
    """
    workDir를 절대 경로로 변환.

    YYYYMMDD-HHMMSS 단축 형식이면 registry에서 조회 후 절대 경로로 변환.
    상대 경로이면 project_root 기준으로 절대 경로 구성.

    Args:
        work_dir: 워크플로우 디렉터리 (단축/상대/절대)
        project_root: 프로젝트 루트 경로 (None이면 자동 해석)

    Returns:
        str: 절대 경로
    """
    if project_root is None:
        project_root = resolve_project_root()

    # 단축 형식 해석
    if TS_PATTERN.match(work_dir):
        work_dir = resolve_work_dir(work_dir, project_root)

    # 절대 경로 구성
    if os.path.isabs(work_dir):
        return work_dir
    return os.path.join(project_root, work_dir)
