"""flow_logger.py - 워크플로우 공통 로깅 유틸리티.

workflow.log 파일에 이벤트를 INFO/WARN/ERROR 레벨로 기록하는
공통 함수를 제공합니다.

로그 포맷:
    [YYYY-MM-DDTHH:MM:SS] [LEVEL] message

예시:
    from flow.flow_logger import append_log, resolve_work_dir_for_logging

    # abs_work_dir을 직접 알고 있는 경우
    append_log("/path/to/workdir", "INFO", "kanban.py: subcommand=list")
    append_log("/path/to/workdir", "WARN", "kanban.py: 티켓 파일 없음")
    append_log("/path/to/workdir", "ERROR", "kanban.py: ERROR 상태 전이 실패")

    # abs_work_dir을 모르는 경우 (워크플로우 외부에서 호출되는 스크립트)
    work_dir = resolve_work_dir_for_logging()
    if work_dir:
        append_log(work_dir, "INFO", "script: start")

주의사항:
    - append_log()는 모든 예외를 조용히 흡수합니다. 로깅 실패가 스크립트
      정상 실행에 영향을 주지 않습니다.
    - resolve_work_dir_for_logging()는 해석 불가 시 None을 반환합니다.
      호출자는 None 반환 시 로깅을 건너뛰어야 합니다.
    - KST (UTC+9) 기준 타임스탬프를 사용합니다.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

# KST (UTC+9)
_KST = timezone(timedelta(hours=9))

# YYYYMMDD-HHMMSS 패턴 (registryKey)
_TS_PATTERN = re.compile(r"^\d{8}-\d{6}$")


def append_log(abs_work_dir: str, level: str, message: str) -> None:
    """워크플로우 로그 파일에 이벤트를 기록한다.

    workflow.log 파일에 KST 타임스탬프와 함께 로그를 추가합니다.
    모든 예외를 조용히 흡수하여 스크립트 실행에 영향을 주지 않습니다.

    Args:
        abs_work_dir: 워크플로우 절대 경로. workflow.log가 위치하는 디렉터리.
        level: 로그 레벨. "INFO", "WARN", "ERROR" 중 하나.
        message: 로그 메시지.

    로그 포맷:
        [YYYY-MM-DDTHH:MM:SS] [LEVEL] message
    """
    try:
        ts = datetime.now(_KST).strftime("%Y-%m-%dT%H:%M:%S")
        log_path = os.path.join(abs_work_dir, "workflow.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {message}\n")
    except Exception:
        pass


def resolve_work_dir_for_logging(
    project_root: Optional[str] = None,
) -> Optional[str]:
    """현재 활성 워크플로우의 abs_work_dir을 해석하여 반환한다.

    다음 순서로 abs_work_dir을 해석합니다:
    1. 환경변수 WORKFLOW_WORK_DIR (직접 지정)
    2. 환경변수 WORKFLOW_REGISTRY_KEY + 디렉터리 스캔
    3. .workflow/ 디렉터리 스캔 (단일 활성 워크플로우 자동 선택)

    해석 불가 시 None을 반환합니다. 호출자는 None 반환 시 로깅을 건너뜁니다.

    Args:
        project_root: 프로젝트 루트 절대 경로. None이면 자동 해석.

    Returns:
        abs_work_dir 절대 경로 문자열. 해석 불가 시 None.
    """
    try:
        if project_root is None:
            project_root = _resolve_project_root()

        # 1. 환경변수 WORKFLOW_WORK_DIR 직접 지정
        env_work_dir = os.environ.get("WORKFLOW_WORK_DIR", "").strip()
        if env_work_dir:
            if os.path.isabs(env_work_dir):
                if os.path.isdir(env_work_dir):
                    return env_work_dir
            else:
                abs_wd = os.path.join(project_root, env_work_dir)
                if os.path.isdir(abs_wd):
                    return abs_wd

        # 2. 환경변수 WORKFLOW_REGISTRY_KEY + 디렉터리 스캔
        registry_key = os.environ.get("WORKFLOW_REGISTRY_KEY", "").strip()
        if registry_key and _TS_PATTERN.match(registry_key):
            resolved = _resolve_work_dir_from_key(registry_key, project_root)
            if resolved:
                return resolved

        # 3. .workflow/ 디렉터리 스캔 (단일 활성 워크플로우 자동 선택)
        resolved = _resolve_from_active_workflows(project_root)
        if resolved:
            return resolved

    except Exception:
        pass

    return None


# =============================================================================
# 내부 헬퍼 함수
# =============================================================================


def _resolve_project_root() -> str:
    """프로젝트 루트 절대 경로를 해석한다.

    이 파일 위치(flow/) -> scripts -> .claude -> project root 순으로
    상위 디렉터리를 탐색합니다. 서브에이전트 워크트리(.claude/worktrees/agent-*)
    에서 실행될 경우 __file__ 기반 4단계 탐색이 워크트리 내부 경로를 반환하므로,
    git-common-dir 기반으로 메인 리포 루트를 재해석합니다.

    Returns:
        프로젝트 루트 절대 경로.
    """
    # flow_logger.py 위치: <project_root>/.claude.workflow/scripts/flow/flow_logger.py
    # 서브에이전트 워크트리 위치:
    #   <main_root>/.claude/worktrees/agent-*/.claude.workflow/scripts/flow/flow_logger.py
    this_file = os.path.abspath(__file__)
    flow_dir = os.path.dirname(this_file)          # .claude.workflow/scripts/flow/
    scripts_dir = os.path.dirname(flow_dir)        # .claude.workflow/scripts/
    claude_dir = os.path.dirname(scripts_dir)      # .claude.workflow/
    candidate = os.path.dirname(claude_dir)        # <candidate>/

    # .claude.workflow/.settings 또는 .env가 있으면 메인 리포 루트 — 즉시 반환
    cw_dir = os.path.join(candidate, ".claude.workflow")
    if os.path.exists(os.path.join(cw_dir, ".settings")) or \
       os.path.exists(os.path.join(cw_dir, ".env")):
        return candidate

    # 워크트리 내부일 수 있음 — git-common-dir로 메인 리포 탐색
    # (dispatcher.py _find_project_root() 와 동일한 패턴)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=candidate,
        )
        if result.returncode == 0:
            git_common = result.stdout.strip()
            # git-common-dir은 메인 리포의 .git 디렉터리를 가리킴
            main_root = os.path.dirname(git_common)
            main_cw_dir = os.path.join(main_root, ".claude.workflow")
            if main_root != candidate and (
                os.path.exists(os.path.join(main_cw_dir, ".settings")) or
                os.path.exists(os.path.join(main_cw_dir, ".env"))
            ):
                return main_root
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return candidate


def _resolve_work_dir_from_key(
    registry_key: str, project_root: str
) -> Optional[str]:
    """registryKey로 abs_work_dir을 디렉터리 스캔으로 해석한다.

    .workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>/ 구조를 순회하여
    status.json이 존재하는 첫 번째 디렉터리를 반환합니다.

    Args:
        registry_key: YYYYMMDD-HHMMSS 형식 레지스트리 키.
        project_root: 프로젝트 루트 절대 경로.

    Returns:
        abs_work_dir 절대 경로. 해석 실패 시 None.
    """
    base_dir = os.path.join(project_root, ".claude.workflow", "workflow", registry_key)
    if not os.path.isdir(base_dir):
        return None

    for work_name in sorted(os.listdir(base_dir)):
        wn_path = os.path.join(base_dir, work_name)
        if not os.path.isdir(wn_path) or work_name.startswith("."):
            continue
        for cmd_name in sorted(os.listdir(wn_path)):
            cmd_path = os.path.join(wn_path, cmd_name)
            if not os.path.isdir(cmd_path):
                continue
            if os.path.exists(os.path.join(cmd_path, "status.json")):
                return cmd_path

    return None


def _resolve_from_active_workflows(project_root: str) -> Optional[str]:
    """활성 워크플로우를 스캔하여 abs_work_dir을 자동 선택한다.

    .workflow/ 디렉터리에서 터미널 상태(DONE/FAILED/STALE/CANCELLED)가 아닌
    워크플로우를 수집합니다. 단일 활성 워크플로우면 즉시 반환합니다.
    복수이면 CLAUDE_SESSION_ID 환경변수로 세션 소유 워크플로우를 먼저 식별하고,
    매칭 실패 시에만 updated_at 기준 최신 항목을 반환합니다.

    Args:
        project_root: 프로젝트 루트 절대 경로.

    Returns:
        abs_work_dir 절대 경로. 활성 워크플로우가 없으면 None.
    """
    workflow_root = os.path.join(project_root, ".claude.workflow", "workflow")
    if not os.path.isdir(workflow_root):
        return None

    _TERMINAL_PHASES = {"DONE", "FAILED", "STALE", "CANCELLED"}

    # (abs_work_dir, updated_at, linked_sessions)
    candidates: list[tuple[str, str, list]] = []

    for entry in sorted(os.listdir(workflow_root)):
        if not _TS_PATTERN.match(entry):
            continue
        entry_path = os.path.join(workflow_root, entry)
        if not os.path.isdir(entry_path):
            continue

        for work_name in sorted(os.listdir(entry_path)):
            wn_path = os.path.join(entry_path, work_name)
            if not os.path.isdir(wn_path) or work_name.startswith("."):
                continue
            for cmd_name in sorted(os.listdir(wn_path)):
                cmd_path = os.path.join(wn_path, cmd_name)
                if not os.path.isdir(cmd_path):
                    continue

                status_file = os.path.join(cmd_path, "status.json")
                if not os.path.exists(status_file):
                    continue

                # status.json에서 phase, updated_at, linked_sessions 읽기
                try:
                    with open(status_file, "r", encoding="utf-8") as f:
                        status = json.load(f)
                except Exception:
                    continue

                if not isinstance(status, dict):
                    continue

                phase = status.get("step") or status.get("phase", "NONE")
                if phase in _TERMINAL_PHASES:
                    continue

                updated_at = status.get("updated_at", "")
                linked_sessions = status.get("linked_sessions", [])
                if not isinstance(linked_sessions, list):
                    linked_sessions = []
                candidates.append((cmd_path, updated_at, linked_sessions))

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0][0]

    # 복수 후보: CLAUDE_SESSION_ID로 세션 소유 워크플로우를 우선 식별한다.
    # statusline.py와 동일한 방식으로 linked_sessions 배열을 검사한다.
    claude_sid = os.environ.get("CLAUDE_SESSION_ID", "").strip()
    if claude_sid:
        session_matches = [
            (cmd_path, updated_at)
            for cmd_path, updated_at, linked in candidates
            if claude_sid in linked
        ]
        if len(session_matches) == 1:
            return session_matches[0][0]
        if len(session_matches) > 1:
            # 같은 세션에 연결된 복수 후보는 updated_at 기준 최신 선택
            session_matches.sort(key=lambda x: x[1], reverse=True)
            return session_matches[0][0]

    # 세션 매칭 실패 시 updated_at 기준 최신 항목으로 폴백
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]
