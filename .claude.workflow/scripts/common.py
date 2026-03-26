#!/usr/bin/env -S python3 -u
"""
common.py - 프로젝트 공통 유틸리티.

프로젝트 루트 경로 해석, ANSI 색상 코드, JSON 원자적 쓰기,
디렉터리 스캔 기반 워크플로우 조회, 환경변수 파싱 등
전역적으로 사용되는 공통 기능을 제공합니다.

주요 함수:
    resolve_project_root: 프로젝트 루트 절대 경로 해석
    load_json_file: JSON 파일 로드 (실패 시 None 반환)
    atomic_write_json: JSON 원자적 쓰기
    scan_active_workflows: 활성 워크플로우 디렉터리 스캔
    resolve_active_workflow: 현재 활성 워크플로우 컨텍스트 반환
    resolve_work_dir: 단축 키로 workDir 경로 조회
    resolve_abs_work_dir: workDir 절대 경로 변환
    read_env: .claude.workflow/.env 환경변수 읽기
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

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


def _detect_worktree_main_root(base: str) -> str:
    """워크트리 내부인지 판별하여 메인 프로젝트 루트 반환.

    git rev-parse --git-common-dir로 .git 공통 디렉터리를 얻고,
    그 부모 디렉터리가 base와 다르면 워크트리 내부로 판정하여
    메인 리포 루트를 반환합니다.

    Args:
        base: 후보 프로젝트 루트 경로 (절대 경로).

    Returns:
        메인 프로젝트 루트 절대 경로. git 실패 또는 워크트리 아니면 base 반환.
    """
    # .claude.workflow/.env가 있으면 이미 메인 리포 루트 — git 호출 불필요
    if os.path.exists(os.path.join(base, ".claude.workflow", ".env")):
        return base

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=base,
        )
        if result.returncode == 0:
            git_common = result.stdout.strip()
            # git-common-dir은 메인 리포의 .git 디렉터리를 가리킴
            main_root = os.path.dirname(git_common)
            if main_root != base:
                return main_root
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return base


def resolve_project_root(start_path: str | None = None) -> str:
    """프로젝트 루트 경로 해석.

    utils -> scripts -> .claude -> project root 순서로 상위 디렉터리를 탐색하여
    프로젝트 루트를 결정합니다. 워크트리 내부에서 호출되더라도 메인 리포의
    프로젝트 루트를 반환합니다.

    Args:
        start_path: 탐색 시작 경로. None이면 이 파일의 위치 기준.

    Returns:
        프로젝트 루트 절대 경로.
    """
    if start_path:
        base = os.path.abspath(start_path)
    else:
        # scripts -> .claude -> project root
        scripts_dir = os.path.dirname(os.path.abspath(__file__))
        base = os.path.normpath(os.path.join(scripts_dir, "..", ".."))
    return _detect_worktree_main_root(base)


def load_json_file(path: str) -> Any | None:
    """JSON 파일 로드. 실패 시 None 반환.

    Args:
        path: JSON 파일 경로.

    Returns:
        파싱된 JSON 데이터. 파일이 없거나 파싱 실패 시 None.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        return None


def atomic_write_json(path: str, data: Any, indent: int = 2) -> None:
    """JSON 원자적 쓰기 (임시 파일 + mv).

    임시 파일에 JSON을 쓰고 원자적으로 대상 경로로 이동합니다.

    Args:
        path: 쓰기 대상 파일 경로.
        data: JSON 직렬화 가능한 데이터.
        indent: JSON 들여쓰기 수준. 기본값 2.

    Raises:
        Exception: 쓰기 실패 시. 임시 파일은 자동 정리.
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


def extract_registry_key(work_dir: str) -> str:
    """workDir 경로에서 YYYYMMDD-HHMMSS 형식의 레지스트리 키 추출.

    중첩 구조: .../<YYYYMMDD-HHMMSS>/<workName>/<command>
    레거시 플랫 구조: .../<YYYYMMDD-HHMMSS>

    Args:
        work_dir: 워크플로우 디렉터리 경로.

    Returns:
        YYYYMMDD-HHMMSS 형식 키. 패턴 미매칭 시 basename 반환.
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


def scan_active_workflows(
    project_root: str | None = None,
    include_terminal: bool = False,
) -> dict[str, dict[str, str]]:
    """.claude.workflow/workflow/ 디렉터리를 스캔하여 워크플로우 목록을 반환.

    .claude.workflow/workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>/ 구조를 순회하며
    각 워크플로우의 status.json과 .context.json을 읽어 dict 형태로 반환.
    동일 entry에 복수 워크플로우가 있을 경우 updated_at 최신순으로 결정적 선택.

    Args:
        project_root: 프로젝트 루트 경로. None이면 자동 해석.
        include_terminal: True이면 DONE/FAILED/STALE/CANCELLED도 포함.

    Returns:
        registryKey를 키로 하는 딕셔너리.
        각 값은 {"title", "step", "workDir", "command"} 형식.
        활성 워크플로우가 없으면 빈 딕셔너리.
    """
    if project_root is None:
        project_root = resolve_project_root()

    from data.constants import TERMINAL_PHASES

    workflow_root = os.path.join(project_root, ".claude.workflow", "workflow")
    if not os.path.isdir(workflow_root):
        return {}

    result: dict[str, dict[str, str]] = {}
    for entry in os.listdir(workflow_root):
        if not TS_PATTERN.match(entry):
            continue
        entry_path = os.path.join(workflow_root, entry)
        if not os.path.isdir(entry_path):
            continue

        # 중첩 구조: .claude.workflow/workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>/
        # 동일 entry에 복수 워크플로우가 있을 경우 updated_at 최신순으로 결정적 선택
        candidates: list[dict[str, str]] = []
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

                rel_work_dir = os.path.join(".claude.workflow", "workflow", entry, work_name, cmd_name)
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


def _get_workflow_updated_at(project_root: str, entry: dict[str, str]) -> str:
    """워크플로우 status.json에서 updated_at 읽기.

    Args:
        project_root: 프로젝트 루트 절대 경로.
        entry: workDir 키를 포함하는 워크플로우 엔트리 딕셔너리.

    Returns:
        updated_at 문자열. status.json이 없거나 키가 없으면 빈 문자열.
    """
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


def _select_by_most_recent(
    candidates: list[tuple[str, dict[str, str]]],
    project_root: str,
) -> tuple[str | None, dict[str, str] | None]:
    """updated_at 기준 가장 최근 워크플로우 선택.

    Args:
        candidates: (registryKey, entry) 튜플 목록.
        project_root: 프로젝트 루트 절대 경로.

    Returns:
        (registryKey, entry) 튜플. 후보가 없으면 (None, None).
    """
    with_time: list[tuple[str, dict[str, str], str]] = []
    for key, entry in candidates:
        updated_at = _get_workflow_updated_at(project_root, entry)
        with_time.append((key, entry, updated_at))
    if not with_time:
        return None, None
    with_time.sort(key=lambda x: x[2], reverse=True)
    return with_time[0][0], with_time[0][1]


def resolve_active_workflow(project_root: str | None = None) -> dict[str, str] | None:
    """디렉터리 스캔으로 활성 워크플로우를 식별하여 컨텍스트 반환.

    단일 워크플로우이면 즉시 선택, 복수이면 PLAN 단계 우선,
    동일 조건이면 updated_at 최신순으로 선택.

    Args:
        project_root: 프로젝트 루트 경로. None이면 자동 해석.

    Returns:
        활성 워크플로우 컨텍스트 딕셔너리 {"title", "workId", "workName",
        "command", "agent", "step"}. 활성 워크플로우가 없으면 None.
    """
    if project_root is None:
        project_root = resolve_project_root()

    registry = scan_active_workflows(project_root=project_root)

    if not isinstance(registry, dict) or not registry:
        return None

    entries = [(k, v) for k, v in registry.items() if isinstance(v, dict)]
    if not entries:
        return None

    selected_entry: dict[str, str] | None = None

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


def resolve_work_dir(input_key: str, project_root: str | None = None) -> str:
    """YYYYMMDD-HHMMSS 단축 형식 키로 workDir 디렉터리 스캔 조회.

    YYYYMMDD-HHMMSS 패턴이 아닌 입력은 그대로 반환.

    Args:
        input_key: 워크플로우 키(YYYYMMDD-HHMMSS) 또는 경로.
        project_root: 프로젝트 루트 경로. None이면 자동 해석.

    Returns:
        해석된 workDir 상대 경로. 스캔 실패 시 ".claude.workflow/workflow/<input_key>" 폴백.
    """
    if not TS_PATTERN.match(input_key):
        return input_key

    if project_root is None:
        project_root = resolve_project_root()

    # 디렉터리 스캔으로 workDir 조회
    base_dir = os.path.join(project_root, ".claude.workflow", "workflow", input_key)
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
                    return os.path.join(".claude.workflow", "workflow", input_key, work_name, cmd_name)

    # 폴백
    fallback = f".claude.workflow/workflow/{input_key}"
    print(
        f"[WARN] directory scan failed for {input_key}, falling back to {fallback}",
        file=sys.stderr,
    )
    return fallback


def resolve_abs_work_dir(work_dir: str, project_root: str | None = None) -> str:
    """workDir를 절대 경로로 변환.

    YYYYMMDD-HHMMSS 단축 형식이면 디렉터리 스캔으로 조회 후 절대 경로로 변환.
    상대 경로이면 project_root 기준으로 절대 경로 구성.

    Args:
        work_dir: 워크플로우 디렉터리 경로. 단축/상대/절대 형식 모두 허용.
        project_root: 프로젝트 루트 경로. None이면 자동 해석.

    Returns:
        절대 경로 문자열.
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
# 환경변수 파싱 (.claude.workflow/.env)
# =============================================================================

_DEFAULT_ENV_FILE = os.environ.get("ENV_FILE", "")


def _resolve_env_file(env_file: str | None = None) -> str:
    """env_file 경로를 해석.

    None이면 환경변수 또는 프로젝트 루트에서 추론합니다.

    Args:
        env_file: .claude.workflow/.env 파일 경로. None이면 자동 해석.

    Returns:
        해석된 env_file 절대 경로 문자열.
    """
    if env_file:
        return env_file
    if _DEFAULT_ENV_FILE:
        return _DEFAULT_ENV_FILE
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(scripts_dir, "..", ".."))
    return os.path.join(project_root, ".claude.workflow", ".env")


def read_env(key: str, default: str = "", env_file: str | None = None) -> str:
    """.claude.workflow/.env에서 환경변수 읽기.

    중복 키 방어(첫 번째 매칭), 따옴표 제거, $HOME/~ 확장 포함.

    Args:
        key: 환경변수 키 이름.
        default: 키가 없을 때 반환할 기본값.
        env_file: .claude.workflow/.env 파일 경로. None이면 자동 해석.

    Returns:
        환경변수 값. 파일이 없거나 키가 없으면 default 반환.
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


# =============================================================================
# 파일시스템 잠금 (mkdir 기반 POSIX lock)
# =============================================================================


def acquire_lock(lock_dir: str, max_wait: int = 2, stale_timeout: int = 300) -> bool:
    """mkdir 기반 POSIX 잠금 획득. stale lock 감지 및 orphan lock 회수 포함.

    디렉터리 생성으로 잠금을 획득하며, PID 파일로 소유자를 기록한다.
    프로세스가 종료되었거나 stale_timeout 초 초과 시 stale lock을 제거하고 재시도한다.
    pid 파일이 없는 orphan lock은 즉시 회수하여 영구 교착을 방지한다.

    Args:
        lock_dir: 잠금 디렉터리 경로.
        max_wait: 최대 대기 초. 기본값 2.
        stale_timeout: stale lock 판정 임계값(초). 잠금 생성 후 이 시간을 초과하면
            stale lock으로 간주하여 회수한다. 기본값 300(5분). max_wait와 독립적으로
            동작하므로 장시간 merge도 정상 잠금으로 유지된다.

    Returns:
        잠금 획득 성공 여부.
    """
    waited = 0
    while True:
        try:
            os.makedirs(lock_dir)
            try:
                with open(os.path.join(lock_dir, "pid"), "w") as f:
                    f.write(f"{os.getpid()} {time.time()}")
            except OSError:
                pass
            return True
        except OSError:
            pid_file = os.path.join(lock_dir, "pid")
            if not os.path.isfile(pid_file):
                # pid 파일 없는 orphan lock: 즉시 회수 후 재시도
                try:
                    shutil.rmtree(lock_dir)
                except OSError:
                    pass
                continue
            if os.path.isfile(pid_file):
                try:
                    with open(pid_file, "r") as f:
                        pid_content = f.read().strip()
                    parts = pid_content.split()
                    lock_pid = int(parts[0])
                    lock_ts = float(parts[1]) if len(parts) > 1 else 0
                    os.kill(lock_pid, 0)
                    if lock_ts and (time.time() - lock_ts) > stale_timeout:
                        try:
                            with open(pid_file, "r") as f:
                                recheck = f.read().strip()
                            if recheck == pid_content:
                                shutil.rmtree(lock_dir)
                                waited += 1
                                continue
                        except OSError:
                            pass
                except (ValueError, ProcessLookupError, OSError):
                    try:
                        with open(pid_file, "r") as f:
                            recheck = f.read().strip()
                        if recheck == pid_content:
                            shutil.rmtree(lock_dir)
                    except OSError:
                        pass
                    waited += 1
                    continue
                except PermissionError:
                    pass
            waited += 1
            if waited >= max_wait:
                return False
            time.sleep(1)


def release_lock(lock_dir: str) -> None:
    """잠금을 해제한다.

    PID 파일 삭제 후 잠금 디렉터리를 제거한다.
    파일시스템 오류는 무시한다.

    Args:
        lock_dir: 해제할 잠금 디렉터리 경로.
    """
    try:
        pid_file = os.path.join(lock_dir, "pid")
        if os.path.exists(pid_file):
            os.unlink(pid_file)
    except OSError:
        pass
    try:
        os.rmdir(lock_dir)
    except OSError:
        pass
