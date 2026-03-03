#!/usr/bin/env -S python3 -u
"""
common.py - 프로젝트 공통 유틸리티

프로젝트 루트 경로 해석, ANSI 색상 코드, JSON 원자적 쓰기,
디렉터리 스캔 기반 워크플로우 조회, 환경변수 파싱 등
전역적으로 사용되는 공통 기능을 제공합니다.
"""

import json
import os
import shutil
import sys
import tempfile

# -- sys.path 보장: 이 모듈이 직접 실행될 때를 위해 scripts/ 디렉터리 추가 --
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
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
    C_CLAUDE,
    C_BOLD,
    C_DIM,
    C_RESET,
    STEP_COLORS,
    PHASE_COLORS,  # 하위 호환 re-export
    TS_PATTERN,
)


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
        # scripts -> .claude -> project root
        scripts_dir = os.path.dirname(os.path.abspath(__file__))
        base = os.path.normpath(os.path.join(scripts_dir, "..", ".."))
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


def scan_active_workflows(project_root=None, include_terminal=False):
    """
    .workflow/ 디렉터리를 스캔하여 워크플로우 목록을 반환.

    .workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>/ 구조를 순회하며
    각 워크플로우의 status.json과 .context.json을 읽어 dict 형태로 반환.

    Args:
        project_root: 프로젝트 루트 경로 (None이면 자동 해석)
        include_terminal: True이면 DONE/FAILED/STALE/CANCELLED도 포함

    Returns:
        dict: {registryKey: {"title", "step", "workDir", "command"}}
    """
    if project_root is None:
        project_root = resolve_project_root()

    from data.constants import TERMINAL_PHASES

    workflow_root = os.path.join(project_root, ".workflow")
    if not os.path.isdir(workflow_root):
        return {}

    result = {}
    for entry in os.listdir(workflow_root):
        if not TS_PATTERN.match(entry):
            continue
        entry_path = os.path.join(workflow_root, entry)
        if not os.path.isdir(entry_path):
            continue

        # 중첩 구조: .workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>/
        # 동일 entry에 복수 워크플로우가 있을 경우 updated_at 최신순으로 결정적 선택
        candidates = []
        for work_name in sorted(os.listdir(entry_path)):
            wn_path = os.path.join(entry_path, work_name)
            if not os.path.isdir(wn_path) or work_name.startswith("."):
                continue
            for cmd_name in sorted(os.listdir(wn_path)):
                cmd_path = os.path.join(wn_path, cmd_name)
                if not os.path.isdir(cmd_path):
                    continue

                status_file = os.path.join(cmd_path, "status.json")
                context_file = os.path.join(cmd_path, ".context.json")

                status = load_json_file(status_file)
                phase = (status.get("step") or status.get("phase", "NONE")) if isinstance(status, dict) else "NONE"

                if not include_terminal and phase in TERMINAL_PHASES:
                    continue

                ctx = load_json_file(context_file)
                title = ctx.get("title", "") if isinstance(ctx, dict) else ""
                command = ctx.get("command", "") if isinstance(ctx, dict) else ""
                updated_at = status.get("updated_at", "") if isinstance(status, dict) else ""

                rel_work_dir = os.path.join(".workflow", entry, work_name, cmd_name)
                candidates.append({
                    "title": title,
                    "step": phase,
                    "workDir": rel_work_dir,
                    "command": command,
                    "updated_at": updated_at,
                })

        if candidates:
            # updated_at 기준 최신 항목 선택 (결정적 동작 보장)
            best = max(candidates, key=lambda c: c["updated_at"])
            result[entry] = {
                "title": best["title"],
                "step": best["step"],
                "workDir": best["workDir"],
                "command": best["command"],
            }

    return result


def _get_workflow_updated_at(project_root, entry):
    """워크플로우 status.json에서 updated_at 읽기."""
    work_dir = entry.get("workDir", "")
    abs_wd = (
        os.path.join(project_root, work_dir)
        if not os.path.isabs(work_dir)
        else work_dir
    )
    status = load_json_file(os.path.join(abs_wd, "status.json"))
    if status:
        return status.get("updated_at", "")
    return ""


def _select_by_most_recent(candidates, project_root):
    """updated_at 기준 가장 최근 워크플로우 선택."""
    with_time = []
    for key, entry in candidates:
        updated_at = _get_workflow_updated_at(project_root, entry)
        with_time.append((key, entry, updated_at))
    if not with_time:
        return None, None
    with_time.sort(key=lambda x: x[2], reverse=True)
    return with_time[0][0], with_time[0][1]


def resolve_active_workflow(project_root=None):
    """
    디렉터리 스캔으로 활성 워크플로우를 식별하여 컨텍스트 반환.

    단일 워크플로우이면 즉시 선택, 복수이면 PLAN 단계 우선,
    동일 조건이면 updated_at 최신순으로 선택.

    Args:
        project_root: 프로젝트 루트 경로 (None이면 자동 해석)

    Returns:
        dict or None: {title, workId, workName, command, agent, step}
    """
    if project_root is None:
        project_root = resolve_project_root()

    registry = scan_active_workflows(project_root=project_root)

    if not isinstance(registry, dict) or not registry:
        return None

    entries = [(k, v) for k, v in registry.items() if isinstance(v, dict)]
    if not entries:
        return None

    selected_entry = None

    if len(entries) == 1:
        _, selected_entry = entries[0]
    else:
        plan_entries = [
            (k, v) for k, v in entries if v.get("step", "") == "PLAN"
        ]
        if len(plan_entries) == 1:
            _, selected_entry = plan_entries[0]
        elif len(plan_entries) > 1:
            _, selected_entry = _select_by_most_recent(plan_entries, project_root)
        else:
            _, selected_entry = _select_by_most_recent(entries, project_root)

    if not selected_entry:
        return None

    # .context.json 로드
    work_dir = selected_entry.get("workDir", "")
    abs_work_dir = (
        os.path.join(project_root, work_dir)
        if not os.path.isabs(work_dir)
        else work_dir
    )
    ctx = load_json_file(os.path.join(abs_work_dir, ".context.json"))
    if not ctx:
        return None

    title = ctx.get("title", "")
    work_id = ctx.get("workId", "")
    work_name = ctx.get("workName", "") or ctx.get("title", "")
    command = ctx.get("command", "")
    agent = ctx.get("agent", "")

    if not (title and work_id and command):
        return None

    # status.json에서 step 읽기
    status = load_json_file(os.path.join(abs_work_dir, "status.json"))
    phase = (status.get("step") or status.get("phase", "")) if status else ""

    return {
        "title": title,
        "workId": work_id,
        "workName": work_name,
        "command": command,
        "agent": agent,
        "step": phase,
    }


def resolve_work_dir(input_key, project_root=None):
    """
    YYYYMMDD-HHMMSS 단축 형식 키로 workDir 디렉터리 스캔 조회.

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

    # 디렉터리 스캔으로 workDir 조회
    base_dir = os.path.join(project_root, ".workflow", input_key)
    if os.path.isdir(base_dir):
        for work_name in sorted(os.listdir(base_dir)):
            wn_path = os.path.join(base_dir, work_name)
            if not os.path.isdir(wn_path) or work_name.startswith("."):
                continue
            for cmd_name in sorted(os.listdir(wn_path)):
                cmd_path = os.path.join(wn_path, cmd_name)
                if not os.path.isdir(cmd_path):
                    continue
                if os.path.exists(os.path.join(cmd_path, "status.json")):
                    return os.path.join(".workflow", input_key, work_name, cmd_name)

    # 폴백
    fallback = f".workflow/{input_key}"
    print(
        f"[WARN] directory scan failed for {input_key}, falling back to {fallback}",
        file=sys.stderr,
    )
    return fallback


def resolve_abs_work_dir(work_dir, project_root=None):
    """
    workDir를 절대 경로로 변환.

    YYYYMMDD-HHMMSS 단축 형식이면 디렉터리 스캔으로 조회 후 절대 경로로 변환.
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


# =============================================================================
# 환경변수 파싱 (.claude.env)
# =============================================================================

_DEFAULT_ENV_FILE = os.environ.get("ENV_FILE", "")


def _resolve_env_file(env_file=None):
    """env_file 경로를 해석. None이면 환경변수 또는 프로젝트 루트에서 추론."""
    if env_file:
        return env_file
    if _DEFAULT_ENV_FILE:
        return _DEFAULT_ENV_FILE
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(scripts_dir, "..", ".."))
    return os.path.join(project_root, ".claude.env")


def read_env(key, default="", env_file=None):
    """
    .claude.env에서 환경변수 읽기.

    중복 키 방어(첫 번째 매칭), 따옴표 제거, $HOME/~ 확장 포함.

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
                    if len(value) >= 2:
                        if (value[0] == '"' and value[-1] == '"') or \
                           (value[0] == "'" and value[-1] == "'"):
                            value = value[1:-1]
                    home = os.environ.get("HOME", "")
                    if home:
                        value = value.replace("$HOME", home)
                        if value.startswith("~"):
                            value = home + value[1:]
                    return value
    except (IOError, OSError):
        pass

    return default
