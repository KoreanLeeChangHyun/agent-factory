#!/usr/bin/env -S python3 -u
"""히스토리 동기화 및 상태 확인 명령어.

.agent-factory/runs/ 및 .agent-factory/runs/.history/ 디렉토리를 스캔하여 .agent-factory/board/data/.history.md와 비교하고,
누락 항목을 추가하거나 상태 변경 항목을 업데이트한다.

디렉터리 구조:
    신규 구조: .agent-factory/runs/<YYYYMMDD-HHMMSS>/
                 status.json, plan.md, work/, report.md, .context.json 직속
    구 구조 (fallback): .agent-factory/runs/<YYYYMMDD-HHMMSS>/<workName>/<command>/

주요 함수:
    parse_timestamp_from_dir: 디렉터리명에서 날짜/시간 추출
    extract_status_from_json: status.json에서 단계 및 타임스탬프 추출
    is_stale: WORK/PLAN 단계의 스테일 여부 판정
    scan_workflow_directory: 워크플로우 디렉터리 스캔
    cmd_sync: sync 서브커맨드 실행
    cmd_status: status 서브커맨드 실행
    cmd_archive: archive 서브커맨드 실행

사용법:
    python3 .agent-factory/engine/sync/history_sync.py sync [--workflow-dir <path>] [--target <path>] [--dry-run] [--all]
    python3 .agent-factory/engine/sync/history_sync.py status [--workflow-dir <path>] [--target <path>] [--all]
    python3 .agent-factory/engine/sync/history_sync.py archive [registryKey]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Optional

_agent_factory_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
)
if _agent_factory_dir not in sys.path:
    sys.path.insert(0, _agent_factory_dir)

try:
    from engine.common import (
        resolve_project_root,
    )
except ImportError:
    def resolve_project_root() -> str:
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from engine.constants import STALE_TTL_SECONDS, KEEP_COUNT

# ============================================================
# Constant (Phase-state mapping)
# ============================================================

from engine.constants import HEADER_LINE, SEPARATOR_LINE, STEP_STATUS_MAP

TIMESTAMP_PATTERN = re.compile(r"^\d{8}-\d{6}$")
EXPECTED_CELL_COUNT = 12
ORPHAN_STATUS = "deleted"


# ============================================================
# helper function
# ============================================================

def _escape_pipe(text: str) -> str:
    """마크다운 테이블 셀 내 파이프 문자를 HTML 엔티티로 이스케이프.

    Args:
        text: 이스케이프할 문자열

    Returns:
        파이프 문자(|)가 &#String replaced with 124;
    """
    return text.replace("|", "&#124;")


def parse_timestamp_from_dir(dir_name: str) -> tuple[str, str]:
    """YYYYMMDD-HHMMSS 형식에서 날짜와 시간을 추출.

    Args:
        dir_name: YYYYMMDD-HHMMSS 형식의 디렉터리 이름

    Returns:
        tuple: (formatted_date, formatted_time)
            - formatted_date: YYYY-MM-DD 형식
            - formatted_time: HH:MM 형식
    """
    date_part = dir_name[:8]
    time_part = dir_name[9:15]
    formatted_date = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
    formatted_time = f"{time_part[:2]}:{time_part[2:4]}"
    return formatted_date, formatted_time


def extract_status_from_json(status_file: str) -> tuple[str, Optional[str], Optional[str]]:
    """status.json에서 step(phase), created_at, updated_at을 추출.

    Args:
        status_file: status.json 파일 경로

    Returns:
        tuple: (step, created_at, updated_at)
            - step: 현재 단계 문자열. 파싱 실패 시 "UNKNOWN"
            - created_at: ISO 8601 생성 타임스탬프. 없으면 None
            - updated_at: ISO 8601 갱신 타임스탬프. 없으면 None
    """
    try:
        with open(status_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        step = data.get("step") or data.get("phase", "UNKNOWN")
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        return step, created_at, updated_at
    except (json.JSONDecodeError, IOError, KeyError):
        return "UNKNOWN", None, None


def is_stale(step: str, updated_at: Optional[str]) -> bool:
    """WORK 또는 PLAN 단계에서 updated_at 기준 30분 이상 경과하면 스테일로 판정.

    Args:
        step: 현재 워크플로우 단계 (WORK, PLAN, INIT, REPORT 등)
        updated_at: ISO 8601 형식의 마지막 갱신 타임스탬프. None이면 False 반환.

    Returns:
        스테일 여부. STALE_TTL_SECONDS 초 이상 경과하면 True.
    """
    if step not in ("WORK", "PLAN", "INIT", "REPORT"):
        return False
    if not updated_at:
        return False
    try:
        # ISO 8601 format parsing (including time zone)
        updated_dt = datetime.fromisoformat(updated_at)
        now = datetime.now(updated_dt.tzinfo)
        elapsed = (now - updated_dt).total_seconds()
        return elapsed > STALE_TTL_SECONDS
    except (ValueError, TypeError):
        return False


def extract_summary_from_plan(plan_file: str, max_len: int = 60) -> str:
    """plan.md에서 '## Task Summary' 섹션의 첫 문장을 추출.

    Args:
        plan_file: plan.md 파일 경로
        max_len: 반환할 최대 문자 수. 초과하면 잘라낸다.

    Returns:
        추출된 요약 문자열. 추출 실패 시 빈 문자열.
    """
    try:
        with open(plan_file, "r", encoding="utf-8") as f:
            content = f.read()
        # "## Task Summary" 헤더 찾기
        match = re.search(r"##\s*Task\s*Summary\s* \n +(.+)", content)
        if match:
            summary = match.group(1).strip()
            if len(summary) > max_len:
                summary = summary[:max_len]
            return summary
    except (IOError, UnicodeDecodeError):
        pass
    return ""


def extract_summary_from_prompt(prompt_file: str, max_len: int = 60) -> str:
    """user_prompt.txt의 첫 줄을 요약으로 추출.

    Args:
        prompt_file: user_prompt.txt 파일 경로
        max_len: 반환할 최대 문자 수. 초과하면 잘라낸다.

    Returns:
        추출된 첫 줄 문자열. 추출 실패 시 빈 문자열.
    """
    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
        if len(first_line) > max_len:
            first_line = first_line[:max_len]
        return first_line
    except (IOError, UnicodeDecodeError):
        return ""


def extract_summary_from_file(summary_file: str, max_len: int = 60) -> str:
    """summary.txt의 첫 줄을 읽어 max_len 이내로 잘라 반환.

    Args:
        summary_file: summary.txt 파일 경로
        max_len: 반환할 최대 문자 수. 초과하면 잘라낸다.

    Returns:
        추출된 첫 줄 문자열. 파일이 비어있거나 읽기 실패 시 빈 문자열.
    """
    try:
        with open(summary_file, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
        if not first_line:
            return ""
        if len(first_line) > max_len:
            first_line = first_line[:max_len]
        return first_line
    except (IOError, UnicodeDecodeError):
        return ""


def extract_title_from_context(context_file: str) -> str:
    """.context.json에서 title 필드를 읽어 반환. JSON 파싱 실패 시 빈 문자열 반환.

    Args:
        context_file: .context.json 파일 경로

    Returns:
        title 필드 값. 파싱 실패 또는 title 없으면 빈 문자열.
    """
    try:
        with open(context_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        title = data.get("title", "")
        if isinstance(title, str) and title.strip():
            return title.strip()
    except (json.JSONDecodeError, IOError, KeyError):
        pass
    return ""


def ensure_entry_data(cmd_path: str) -> None:
    """단일 워크플로우 디렉터리의 필수 파일을 검증하고, 누락 시 자동 생성한다.

    대상 디렉터리: <YYYYMMDD-HHMMSS>/<workName>/<command>/

    검증 대상 파일:
        - summary.txt: 1줄 텍스트 요약 파일

    자동 생성 규칙 (summary.txt):
        다음 우선순위로 요약 텍스트를 추출하여 summary.txt를 생성한다.
        (a) plan.md의 '## Task Summary' 섹션 첫 문장
        (b) user_prompt.txt의 첫 줄
        (c) .context.json의 'title' 필드
        모든 소스에서 추출 실패 시 생성하지 않는다.

    Args:
        cmd_path: <command> 레벨 디렉터리 절대 경로
    """
    summary_file = os.path.join(cmd_path, "summary.txt")
    if os.path.exists(summary_file):
        return

    summary = ""

    # (a) plan.md의 '## Task Summary' 섹션 첫 문장
    plan_file = os.path.join(cmd_path, "plan.md")
    if not summary and os.path.exists(plan_file):
        summary = extract_summary_from_plan(plan_file)

    # (b) First line of user_prompt.txt
    prompt_file = os.path.join(cmd_path, "user_prompt.txt")
    if not summary and os.path.exists(prompt_file):
        summary = extract_summary_from_prompt(prompt_file)

    # (c) 'title' field in .context.json
    context_file = os.path.join(cmd_path, ".context.json")
    if not summary and os.path.exists(context_file):
        try:
            with open(context_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            title = data.get("title", "")
            if isinstance(title, str) and title.strip():
                summary = title.strip()
                if len(summary) > 60:
                    summary = summary[:60]
        except (json.JSONDecodeError, IOError, KeyError):
            pass

    if summary:
        try:
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(summary + "\n")
        except IOError:
            pass


def _build_entry(
    dir_name: str,
    work_name: str,
    command: str,
    cmd_path: str,
    work_path: str,
    rel_prefix: str,
) -> dict[str, object]:
    """단일 엔트리의 메타정보를 수집하여 dict로 반환하는 내부 헬퍼.

    Args:
        dir_name: YYYYMMDD-HHMMSS 형식의 타임스탬프 디렉터리 이름
        work_name: 작업 이름 (workName 서브디렉터리 이름)
        command: 커맨드 이름 (implement, review 등)
        cmd_path: <command> 레벨 디렉터리 절대 경로
        work_path: <workName> 레벨 디렉터리 절대 경로
        rel_prefix: history.md에서의 상대 경로 접두사

    Returns:
        엔트리 메타정보 딕셔너리 (work_id, title, summary, command, step, status,
        date, time, has_plan, has_prompt, has_files, files_count, has_report,
        has_work, work_name, rel_base 포함)
    """
    ensure_entry_data(cmd_path)

    # Configure file path
    status_file = os.path.join(cmd_path, "status.json")
    plan_file = os.path.join(cmd_path, "plan.md")
    prompt_file = os.path.join(cmd_path, "user_prompt.txt")
    report_file = os.path.join(cmd_path, "report.md")
    files_dir = os.path.join(cmd_path, "files")

    # Extract meta information from status.json
    # Priority: <command>/status.json > <workName>/status.json
    step = "UNKNOWN"
    created_at = None
    updated_at = None
    if os.path.exists(status_file):
        step, created_at, updated_at = extract_status_from_json(status_file)
    else:
        # fallback: status.json at workName level
        work_status_file = os.path.join(work_path, "status.json")
        if os.path.exists(work_status_file):
            step, created_at, updated_at = extract_status_from_json(work_status_file)

    # T1: 스테일 감지 - WORK/PLAN 단계에서 2시간 이상 경과 시 "interruption"
    if is_stale(step, updated_at):
        status_text = "interruption"
    else:
        status_text = STEP_STATUS_MAP.get(step, "unknown")

    # Date/Time Extraction
    date_str, time_str = parse_timestamp_from_dir(dir_name)

    # Extract summary (summary.txt first, plan.md second best, user_prompt.txt fallback)
    summary = ""
    summary_file = os.path.join(cmd_path, "summary.txt")
    if os.path.exists(summary_file):
        summary = extract_summary_from_file(summary_file)
    if not summary and os.path.exists(plan_file):
        summary = extract_summary_from_plan(plan_file)
    if not summary and os.path.exists(prompt_file):
        summary = extract_summary_from_prompt(prompt_file)

    # Title: title field in .context.json takes precedence, if not, fallback to work_name
    context_file = os.path.join(cmd_path, ".context.json")
    title = ""
    if os.path.exists(context_file):
        title = extract_title_from_context(context_file)
    if not title:
        title = work_name

    # Existence of each file/directory
    has_plan = os.path.exists(plan_file)
    has_prompt = os.path.exists(prompt_file)
    has_files = os.path.isdir(files_dir) and len(os.listdir(files_dir)) > 0
    has_report = os.path.exists(report_file)
    has_work = os.path.isdir(os.path.join(cmd_path, "work"))

    # Number of image files (files directory)
    files_count = 0
    if has_files:
        files_count = len(os.listdir(files_dir))

    return {
        "work_id": dir_name,
        "title": title,
        "summary": summary,
        "command": command,
        "step": step,
        "status": status_text,
        "date": date_str,
        "time": time_str,
        "has_plan": has_plan,
        "has_prompt": has_prompt,
        "has_files": has_files,
        "files_count": files_count,
        "has_report": has_report,
        "has_work": has_work,
        "work_name": work_name,
        "rel_base": f"{rel_prefix}/{dir_name}/{work_name}/{command}",
    }


def _scan_entries_in_dir(base_dir: str, rel_prefix: str) -> list[dict[str, object]]:
    """단일 디렉토리를 스캔하여 워크플로우 엔트리 목록을 반환.

    T-448 이후 신규 폴드 구조를 우선 탐색하고, 구 구조는 fallback으로 처리한다.

    신규 구조 (우선): base_dir/<YYYYMMDD-HHMMSS>/status.json 직속
        → entry 1건 생성 (work_name/command는 .context.json에서 읽음)
    구 구조 (fallback): base_dir/<YYYYMMDD-HHMMSS>/<workName>/<command>/
        command 서브디렉토리가 없고 workName에 직접 파일이 있으면 command="unknown"으로 폴백.

    Args:
        base_dir: 스캔할 기본 디렉터리 절대 경로
        rel_prefix: history.md에서의 상대 경로 접두사
            (예: "../workflow" 또는 "../workflow/.history")

    Returns:
        발견된 워크플로우 엔트리 딕셔너리 목록
    """
    entries: list[dict[str, object]] = []

    if not os.path.isdir(base_dir):
        return entries

    for dir_name in os.listdir(base_dir):
        dir_path = os.path.join(base_dir, dir_name)

        # Check for YYYYMMDD-HHMMSS pattern
        if not TIMESTAMP_PATTERN.match(dir_name):
            continue
        if not os.path.isdir(dir_path):
            continue

        new_status_file = os.path.join(dir_path, "status.json")
        if os.path.isfile(new_status_file):
            # New structure: extract work_name/command from .context.json
            context_file = os.path.join(dir_path, ".context.json")
            work_name = dir_name  # Fallback: use dir_name
            command = "unknown"
            if os.path.exists(context_file):
                try:
                    with open(context_file, "r", encoding="utf-8") as _f:
                        ctx = json.load(_f)
                    if isinstance(ctx.get("workName"), str) and ctx["workName"]:
                        work_name = ctx["workName"]
                    if isinstance(ctx.get("command"), str) and ctx["command"]:
                        command = ctx["command"]
                except Exception:
                    pass
            entry = _build_entry(dir_name, work_name, command,
                                 dir_path, dir_path, rel_prefix)
            # New structure: rel_base is {rel_prefix}/{dir_name} (no intermediate directories)
            entry["rel_base"] = f"{rel_prefix}/{dir_name}"
            entries.append(entry)
            continue

        # Sphere structure fallback: Nested structure navigation <YYYYMMDD-HHMMSS>/<workName>/<command>/
        for work_name in os.listdir(dir_path):
            work_path = os.path.join(dir_path, work_name)
            if not os.path.isdir(work_path):
                continue

            # command subdirectory navigation
            has_command_subdir = False
            for command in os.listdir(work_path):
                cmd_path = os.path.join(work_path, command)
                if not os.path.isdir(cmd_path):
                    continue

                has_command_subdir = True
                entry = _build_entry(dir_name, work_name, command,
                                     cmd_path, work_path, rel_prefix)
                entries.append(entry)

            # T2: Fallback if there is no command directory and a file exists directly in workName.
            if not has_command_subdir:
                work_status = os.path.join(work_path, "status.json")
                work_prompt = os.path.join(work_path, "user_prompt.txt")
                if os.path.exists(work_status) or os.path.exists(work_prompt):
                    entry = _build_entry(dir_name, work_name, "unknown",
                                         work_path, work_path, rel_prefix)
                    entries.append(entry)

    return entries


def scan_workflow_directory(workflow_dir: str, include_all: bool = False) -> list[dict[str, object]]:
    """.agent-factory/runs/ 및 .agent-factory/runs/.history/ 디렉토리를 스캔하여 각 작업의 메타정보를 추출.

    디렉터리 구조:
        신규 구조: .agent-factory/runs/<YYYYMMDD-HHMMSS>/status.json 직속
        구 구조 (fallback): .agent-factory/runs/<YYYYMMDD-HHMMSS>/<workName>/<command>/
    .history/ 하위도 동일 구조로 탐색하며, rel_base를 ../workflow/.history/...로 구성.

    workflow/ 엔트리가 .history/ 엔트리보다 우선한다 (같은 work_id인 경우).

    Args:
        workflow_dir: .agent-factory/runs/ 디렉터리 절대 경로
        include_all: True이면 중단된 작업도 포함. 현재 미사용.

    Returns:
        발견된 워크플로우 엔트리 딕셔너리 목록 (날짜 역순 정렬)
    """
    # Scan .agent-factory/runs/ (priority)
    entries = _scan_entries_in_dir(workflow_dir, "../workflow")

    # Already collected work_id set (priority protected)
    seen_ids = {e["work_id"] for e in entries}

    # Scan .agent-factory/runs/.history/
    history_dir = os.path.join(workflow_dir, ".history")
    history_entries = _scan_entries_in_dir(history_dir, "../workflow/.history")

    # Add only items not in workflow/
    for entry in history_entries:
        if entry["work_id"] not in seen_ids:
            entries.append(entry)
            seen_ids.add(entry["work_id"])

    # Sort by reverse date (newest)
    entries.sort(key=lambda x: x["work_id"], reverse=True)
    return entries


def format_row(entry: dict[str, object]) -> str:
    """10컬럼 테이블 행을 생성.

    Args:
        entry: _build_entry()가 반환한 워크플로우 엔트리 딕셔너리

    Returns:
        마크다운 테이블 행 문자열 (| 구분자 포함)
    """
    # Date cell: YYYY-MM-DD<br><sub>HH:MM</sub>
    date_cell = f"{entry['date']}<br><sub>{entry['time']}</sub>"

    # Title & Content Cell: Title<br><sub>Summary</sub>
    if entry["summary"]:
        title_cell = f"{_escape_pipe(str(entry['title']))}<br><sub>{_escape_pipe(str(entry['summary']))}</sub>"
    else:
        title_cell = _escape_pipe(str(entry["title"]))

    # query link
    if entry["has_prompt"]:
        prompt_cell = f"[Query]({entry['rel_base']}/user_prompt.txt)"
    else:
        prompt_cell = "-"

    # file link
    if entry["has_files"]:
        files_cell = f"[file({entry['files_count']})]({entry['rel_base']}/files/)"
    else:
        files_cell = "-"

    # plan link
    if entry["has_plan"]:
        plan_cell = f"[plan]({entry['rel_base']}/plan.md)"
    else:
        plan_cell = "-"

    # work link
    if entry["has_work"]:
        work_cell = f"[work]({entry['rel_base']}/work/)"
    else:
        work_cell = "-"

    # reporting link
    if entry["has_report"]:
        report_cell = f"[report]({entry['rel_base']}/report.md)"
    else:
        report_cell = "-"

    return f"| {date_cell} | {entry['work_id']} | {title_cell} | {entry['command']} | {entry['status']} | {prompt_cell} | {files_cell} | {plan_cell} | {work_cell} | {report_cell} |"


# ============================================================
# Parsing history.md
# ============================================================

def parse_history_md(filepath: str) -> tuple[list[str], set[str], int, list[str]]:
    """history.md를 파싱하여 구성 요소를 반환.

    Args:
        filepath: history.md 파일 경로. 파일이 없으면 빈 결과를 반환.

    Returns:
        tuple: (header_lines, existing_ids, marker_idx, data_rows)
            - header_lines: 마커까지의 헤더 부분 (마커 포함)
            - existing_ids: 기존 작업ID Set
            - marker_idx: 마커 라인의 인덱스 (-1이면 없음)
            - data_rows: 데이터 행 목록 (테이블 헤더/구분선 제외)
    """
    if not os.path.exists(filepath):
        return [], set(), -1, []

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    header_lines: list[str] = []
    data_rows: list[str] = []
    existing_ids: set[str] = set()
    marker_idx = -1
    in_table = False
    table_header_seen = False
    header_separator_seen = False

    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")

        # Table header/separator line detection
        if "| date" in stripped and "Job ID" in stripped:
            in_table = True
            table_header_seen = True
            header_lines.append(line)
            continue

        if table_header_seen and stripped.startswith("|---"):
            if not header_separator_seen:
                # First separator line immediately after the table header -> part of the header
                header_lines.append(line)
                header_separator_seen = True
            # Ignore middle separators between data rows (do not add them to data_rows)
            continue

        # data row
        if in_table and stripped.startswith("|"):
            data_rows.append(stripped)
            # Extract task ID (2nd cell)
            cells = stripped.split("|")
            if len(cells) >= 3:
                work_id = cells[2].strip()
                if TIMESTAMP_PATTERN.match(work_id):
                    existing_ids.add(work_id)
        elif not in_table:
            header_lines.append(line)

    return header_lines, existing_ids, marker_idx, data_rows


def extract_status_from_row(row: str) -> str:
    """기존 데이터 행에서 상태 셀 값을 추출.

    Args:
        row: 마크다운 테이블 데이터 행 문자열

    Returns:
        상태 셀 값 문자열. 셀 수가 부족하면 빈 문자열.
    """
    cells = row.split("|")
    if len(cells) >= 6:
        return cells[5].strip()
    return ""


def replace_status_in_row(row: str, new_status: str) -> str:
    """기존 데이터 행의 상태 셀 값을 교체.

    Args:
        row: 마크다운 테이블 데이터 행 문자열
        new_status: 교체할 새 상태 값

    Returns:
        상태 셀이 교체된 행 문자열. 셀 수가 부족하면 원본 행 반환.
    """
    cells = row.split("|")
    if len(cells) >= 6:
        cells[5] = f" {new_status} "
        return "|".join(cells)
    return row


def extract_work_id_from_row(row: str) -> str:
    """기존 데이터 행에서 작업ID를 추출.

    Args:
        row: 마크다운 테이블 데이터 행 문자열

    Returns:
        작업ID 문자열. 셀 수가 부족하면 빈 문자열.
    """
    cells = row.split("|")
    if len(cells) >= 3:
        return cells[2].strip()
    return ""


# ============================================================
# sync command
# ============================================================

def cmd_sync(args: argparse.Namespace) -> int:
    """sync 서브커맨드 실행.

    .agent-factory/runs/ 디렉터리를 스캔하여 history.md와 비교하고 누락/변경 항목을 동기화한다.

    Args:
        args: argparse.Namespace. workflow_dir, target, dry_run, all 속성 포함.

    Returns:
        종료 코드. 0: 성공, 1: 실패
    """
    print("[STATE] HISTORY sync", flush=True)
    print(">> Start sync...", flush=True)

    workflow_dir = args.workflow_dir
    target = args.target
    dry_run = args.dry_run
    include_all = args.all

    # Convert relative path to absolute path based on PROJECT_ROOT
    if not os.path.isabs(target):
        target = os.path.join(PROJECT_ROOT, target)
    if not os.path.isabs(workflow_dir):
        workflow_dir = os.path.join(PROJECT_ROOT, workflow_dir)

    # Scan .agent-factory/runs/
    scanned = scan_workflow_directory(workflow_dir, include_all)
    if not scanned:
        print("[INFO] There are no tasks in the .agent-factory/runs/ directory.")
        return 0

    # Parsing history.md
    header_lines, existing_ids, marker_idx, data_rows = parse_history_md(target)

    # Organize scanned data into work_id -> entry map
    # (workflow/ is already prioritized in scan_workflow_directory)
    scanned_map: dict[str, dict[str, object]] = {}
    for entry in scanned:
        scanned_map.setdefault(entry["work_id"], entry)

    # Convert existing rows to work_id -> row dictionary
    # Original rows are also preserved for legacy format detection
    existing_rows: dict[str, str] = {}
    original_rows: dict[str, str] = {}
    for row in data_rows:
        wid = extract_work_id_from_row(row)
        if wid:
            if wid in scanned_map:
                existing_rows[wid] = format_row(scanned_map[wid])
            else:
                existing_rows[wid] = row
            original_rows.setdefault(wid, row)

    # Comparison: Detecting missing items and state change/legacy format items
    new_entries: list[dict[str, object]] = []
    updated_entries: list[dict[str, object]] = []

    for entry in scanned:
        wid = entry["work_id"]
        if wid not in existing_ids:
            new_entries.append(entry)
        else:
            # Check status change
            old_row = original_rows.get(wid, "")
            old_status = extract_status_from_row(old_row)
            new_status = entry["status"]
            if old_status != new_status:
                updated_entries.append(entry)
            else:
                # Detect legacy format rows (less than 9 columns): O(1) dict lookup
                orig_row = original_rows.get(wid, "")
                if orig_row and len(orig_row.split("|")) < EXPECTED_CELL_COUNT:
                    updated_entries.append(entry)

    # Check for existence of duplicate rows
    wid_counts: dict[str, int] = {}
    for row in data_rows:
        wid = extract_work_id_from_row(row)
        if wid:
            wid_counts[wid] = wid_counts.get(wid, 0) + 1
    has_duplicates = any(c > 1 for c in wid_counts.values())

    # Check for legacy format row existence (cell count less than 10)
    has_legacy = any(
        len(row.split("|")) < EXPECTED_CELL_COUNT
        for row in data_rows
        if extract_work_id_from_row(row)
    )

    # T3: Orphan entry detection - entries in history.md but no directory in filesystem
    orphan_wids: set[str] = set()
    for row in data_rows:
        wid = extract_work_id_from_row(row)
        if wid and wid not in scanned_map:
            old_status = extract_status_from_row(row)
            if old_status != ORPHAN_STATUS:
                orphan_wids.add(wid)

    if not new_entries and not updated_entries and not has_duplicates and not has_legacy and not orphan_wids:
        print("[INFO] history.md is up to date. No changes.")
        return 0

    # dry-run mode
    if dry_run:
        print("[DRY-RUN] Scheduled changes:")
        print(f"New addition: {len(new_entries)} entries")
        for e in new_entries:
            print(f"    + {e['work_id']} | {e['title']} | {e['command']} | {e['status']}")
        print(f"Status update: {len(updated_entries)} entries")
        for e in updated_entries:
            old_row = original_rows.get(str(e["work_id"]), "")
            old_status = extract_status_from_row(old_row)
            print(f"    ~ {e['work_id']} | {old_status} -> {e['status']}")
        if orphan_wids:
            print(f"Orphan entries (marked deleted): {len(orphan_wids)} occurrences")
            for wid in sorted(orphan_wids, reverse=True):
                print(f"! {wid} | deleted")
        return 0

    # actual renewal
    # 1. Apply a state change on an existing row
    updated_row_map: dict[str, str] = {}
    for entry in updated_entries:
        updated_row_map[str(entry["work_id"])] = format_row(entry)

    # 2. Reorganize entire data (update existing rows + add new rows)
    final_rows: list[str] = []

    # Create new row
    new_rows = [format_row(e) for e in new_entries]

    # Update existing row (regenerate with format_row if scanned data exists)
    for row in data_rows:
        wid = extract_work_id_from_row(row)
        if wid in updated_row_map:
            final_rows.append(updated_row_map[wid])
        elif wid in scanned_map:
            # Regeneration with scanned data (resolving legacy formats/missing links)
            final_rows.append(format_row(scanned_map[wid]))
        elif wid in orphan_wids:
            # T3: 고아 엔트리 - 상태를 "deleted"으로 변경
            final_rows.append(replace_status_in_row(row, ORPHAN_STATUS))
        else:
            final_rows.append(row)

    # Insert new rows by date (merge and reorder everything)
    # Filter out middle separator rows so they are not included in the final output
    all_rows = [r for r in (final_rows + new_rows) if not r.strip().startswith("|---")]

    # Sort by task ID (reverse order)
    def sort_key(row: str) -> str:
        """Returns the task ID of the row as the sort key."""
        wid = extract_work_id_from_row(row)
        return wid if wid else ""

    all_rows.sort(key=sort_key, reverse=True)

    # Remove duplicate rows by work_id (keep only first row after sorting)
    seen_wids: set[str] = set()
    deduped_rows: list[str] = []
    for row in all_rows:
        wid = extract_work_id_from_row(row)
        if wid and wid in seen_wids:
            continue
        if wid:
            seen_wids.add(wid)
        deduped_rows.append(row)
    all_rows = deduped_rows

    # Reorganize the history.md file
    output_lines: list[str] = []

    # title
    output_lines.append("# Workflow execution history \n")
    output_lines.append("\n")
    output_lines.append(f"{HEADER_LINE}\n")
    output_lines.append(f"{SEPARATOR_LINE}\n")

    for row in all_rows:
        output_lines.append(f"{row}\n")

    # Atomic Write
    target_dir = os.path.dirname(target)
    os.makedirs(target_dir, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=target_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(output_lines)
        shutil.move(tmp_path, target)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    # Summary of Results
    print(f"[SYNC] Done:")
    print(f"New addition: {len(new_entries)} entries")
    for e in new_entries:
        print(f"    + {e['work_id']} | {e['title']} | {e['command']} | {e['status']}")
    if updated_entries:
        print(f"Status update: {len(updated_entries)} entries")
        for e in updated_entries:
            old_row = original_rows.get(str(e["work_id"]), "")
            old_status = extract_status_from_row(old_row)
            print(f"    ~ {e['work_id']} | {old_status} -> {e['status']}")
    if orphan_wids:
        print(f"Orphan entries (marked deleted): {len(orphan_wids)} occurrences")
        for wid in sorted(orphan_wids, reverse=True):
            print(f"! {wid} | deleted")
    print(f"Total number of rows: {len(all_rows)}")

    print(">> [OK] sync completed", flush=True)
    return 0


# ============================================================
# status command
# ============================================================

def cmd_status(args: argparse.Namespace) -> int:
    """status 서브커맨드 실행.

    .agent-factory/runs/ 디렉터리와 history.md를 비교하여 동기화 상태 요약을 출력한다.

    Args:
        args: argparse.Namespace. workflow_dir, target, all 속성 포함.

    Returns:
        종료 코드. 항상 0.
    """
    workflow_dir = args.workflow_dir
    target = args.target
    include_all = args.all

    # Convert relative path to absolute path based on PROJECT_ROOT
    if not os.path.isabs(target):
        target = os.path.join(PROJECT_ROOT, target)
    if not os.path.isabs(workflow_dir):
        workflow_dir = os.path.join(PROJECT_ROOT, workflow_dir)

    # Scan .agent-factory/runs/
    scanned = scan_workflow_directory(workflow_dir, include_all)

    # Parsing history.md
    _, existing_ids, _, data_rows = parse_history_md(target)

    # Count missing items
    scanned_ids = {e["work_id"] for e in scanned}
    missing_ids = scanned_ids - existing_ids
    extra_ids = existing_ids - scanned_ids

    # Classification by status
    status_counts: dict[str, int] = {}
    for entry in scanned:
        s = str(entry["status"])
        status_counts[s] = status_counts.get(s, 0) + 1

    # output of power
    print("[STATE] HISTORY status", flush=True)
    print(f">> workflow: {len(scanned)} rows, history: {len(data_rows)} rows, missing: {len(missing_ids)} rows", flush=True)
    print("=== history-sync status ===")
    print(f"Number of workflow/ directories: {len(scanned)}")
    print(f"history.md row count: {len(data_rows)} rows")
    print(f"Missing items: {len(missing_ids)}")
    if extra_ids:
        print(f"Exists only in history.md: {len(extra_ids)} items")
    print()
    print("Classification by status:")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"{status}: {count} cases")

    if missing_ids:
        print()
        print("List of missing items:")
        for entry in scanned:
            if entry["work_id"] in missing_ids:
                print(f"    - {entry['work_id']} | {entry['title']} | {entry['command']} | {entry['status']}")

    return 0


# ============================================================
# archive command
# ============================================================

def _update_ticket_workdir_after_archive(moved_key: str, workflow_dir: str, history_dir: str) -> None:
    """archive 후 이동된 registryKey를 보유한 티켓 XML의 경로 필드를 .history/ 반영 경로로 갱신.

    tickets 전체 디렉터리(open/progress/review/done)를 스캔하여 <result>/<registrykey>가
    moved_key와 일치하는 티켓 XML을 찾고, <workdir>/<plan>/<report> 경로 텍스트를
    .agent-factory/runs/.history/{key}/... 형태로 갱신한다.

    Args:
        moved_key: .history/로 이동된 워크플로우 키 (YYYYMMDD-HHMMSS 형식)
        workflow_dir: .agent-factory/runs/ 디렉터리 절대 경로
        history_dir: .agent-factory/runs/.history/ 디렉터리 절대 경로

    Returns:
        None. 실패 시 [WARN] 경고를 출력하고 비차단 처리한다.
    """
    # workflow_dir = .../PROJECT/.agent-factory/workflow
    # workflow_dir parent = .../PROJECT/.agent-factory
    cw_dir = os.path.dirname(workflow_dir)
    tickets_dir = os.path.join(cw_dir, "tickets")

    status_dirs = ["open", "progress", "review", "done"]

    # Path update function: .agent-factory/runs/{key}/... -> .agent-factory/runs/.history/{key}/...
    def _rewrite_path(text: str) -> str:
        """Change workflow/{key}/ to workflow/.history/{key}/に置換."""
        if not text:
            return text
        old_prefix = f".agent-factory/runs/{moved_key}/"
        new_prefix = f".agent-factory/runs/.history/{moved_key}/"
        if old_prefix in text:
            return text.replace(old_prefix, new_prefix)
        return text

    for status in status_dirs:
        status_dir = os.path.join(tickets_dir, status)
        if not os.path.isdir(status_dir):
            continue
        for fname in os.listdir(status_dir):
            if not fname.endswith(".xml"):
                continue
            xml_path = os.path.join(status_dir, fname)
            ticket_number = fname[:-4]  # T-NNN
            try:
                tree = ET.parse(xml_path)
                root = tree.getroot()
                result_el = root.find("result")
                if result_el is None:
                    continue
                rk_el = result_el.find("registrykey")
                if rk_el is None or (rk_el.text or "").strip() != moved_key:
                    continue

                # registrykey match — update path workdir/plan/report
                updated = False
                for tag in ("workdir", "plan", "report"):
                    el = result_el.find(tag)
                    if el is not None and el.text:
                        new_text = _rewrite_path(el.text.strip())
                        if new_text != el.text.strip():
                            el.text = new_text
                            updated = True

                if updated:
                    tree.write(xml_path, encoding="unicode", xml_declaration=False)
                    new_workdir = (result_el.find("workdir") or result_el).text or ""
                    print(
                        f"[OK] ticket {ticket_number}: workdir updated to .history/"
                    )
            except Exception as exc:
                print(
                    f"[WARN] ticket {ticket_number}: XML workdir update failed — {exc}",
                    file=sys.stderr,
                )


def _detect_active_workflow_keys(workflow_dir: str) -> set[str]:
    """활성 워크플로우(완료 상태가 아닌)의 디렉터리 이름 집합을 반환.

    T-448 이후 신규 폴드 구조를 우선 탐색하고, 구 구조는 fallback으로 처리한다.
    신규 구조: dir_path/status.json 직속
    구 구조 fallback: dir_path/<workName>/<command>/status.json

    Args:
        workflow_dir: .agent-factory/runs/ 디렉터리 절대 경로

    Returns:
        완료되지 않은(DONE/FAILED/CANCELLED 아닌) 워크플로우 디렉터리 이름 집합
    """
    active_keys: set[str] = set()
    terminal_phases = {"DONE", "FAILED", "CANCELLED"}

    if not os.path.isdir(workflow_dir):
        return active_keys

    for dir_name in os.listdir(workflow_dir):
        dir_path = os.path.join(workflow_dir, dir_name)
        if not os.path.isdir(dir_path) or not re.match(r"^[0-9]", dir_name):
            continue

        # New fold structure priority: check dir_path/status.json directly
        new_status_file = os.path.join(dir_path, "status.json")
        if os.path.exists(new_status_file):
            phase, _, _ = extract_status_from_json(new_status_file)
            if phase not in terminal_phases:
                active_keys.add(dir_name)
            continue

        # Phrase structure fallback: workName subdirectory navigation
        for work_name in os.listdir(dir_path):
            work_path = os.path.join(dir_path, work_name)
            if not os.path.isdir(work_path):
                continue

            # command subdirectory navigation
            for command in os.listdir(work_path):
                cmd_path = os.path.join(work_path, command)
                if not os.path.isdir(cmd_path):
                    continue
                status_file = os.path.join(cmd_path, "status.json")
                if os.path.exists(status_file):
                    phase, _, _ = extract_status_from_json(status_file)
                    if phase not in terminal_phases:
                        active_keys.add(dir_name)
                        break
            else:
                continue
            break

    return active_keys


def cmd_archive(args: argparse.Namespace) -> int:
    """archive 서브커맨드 실행. 오래된 워크플로우 디렉토리를 .history/로 이동.

    KEEP_COUNT개를 초과하는 오래된 디렉터리를 .agent-factory/runs/.history/로 이동한다.
    registry_key가 지정되면 해당 키는 보존하고, 없으면 활성 워크플로우를 자동 감지하여 제외한다.

    Args:
        args: argparse.Namespace. registry_key 속성 포함 (None 가능).

    Returns:
        종료 코드. 0: 성공, 1: 일부 실패
    """
    print("[STATE] HISTORY archive", flush=True)
    current_key = getattr(args, 'registry_key', None)
    workflow_dir = os.path.join(PROJECT_ROOT, ".agent-factory", "runs")
    history_dir = os.path.join(workflow_dir, ".history")

    if not os.path.isdir(workflow_dir):
        print(">> No workflow directory — skipped", flush=True)
        return 0

    # [0-9]* Sort pattern directory in reverse order.
    dirs: list[str] = []
    for name in sorted(os.listdir(workflow_dir), reverse=True):
        full_path = os.path.join(workflow_dir, name)
        if os.path.isdir(full_path) and re.match(r"^[0-9]", name):
            dirs.append(name)

    if not dirs:
        print(">>No archive destination", flush=True)
        return 0

    # If registry_key is None, active workflows are automatically detected and excluded.
    if current_key:
        filtered = [d for d in dirs if d != current_key]
        if len(filtered) < KEEP_COUNT - 1:
            print(">> Less than retention quantity — skipped", flush=True)
            return 0

        # Create .history/ directory
        os.makedirs(history_dir, exist_ok=True)

        moved = 0
        failed = 0
        for target in filtered[KEEP_COUNT - 1:]:
            src = os.path.join(workflow_dir, target)
            dst = os.path.join(history_dir, target)
            try:
                shutil.move(src, dst)
                moved += 1
                print(f"[OK] archived: {target}")
                _update_ticket_workdir_after_archive(target, workflow_dir, history_dir)
            except Exception:
                failed += 1
                print(f"[WARN] archive failed: {target} (skipping)", file=sys.stderr)
    else:
        active_keys = _detect_active_workflow_keys(workflow_dir)
        filtered = [d for d in dirs if d not in active_keys]
        keep = max(0, KEEP_COUNT - len(active_keys))
        if len(filtered) < keep:
            print(">> Less than retention quantity — skipped", flush=True)
            return 0

        # Create .history/ directory
        os.makedirs(history_dir, exist_ok=True)

        moved = 0
        failed = 0
        for target in filtered[keep:]:
            src = os.path.join(workflow_dir, target)
            dst = os.path.join(history_dir, target)
            try:
                shutil.move(src, dst)
                moved += 1
                print(f"[OK] archived: {target}")
                _update_ticket_workdir_after_archive(target, workflow_dir, history_dir)
            except Exception:
                failed += 1
                print(f"[WARN] archive failed: {target} (skipping)", file=sys.stderr)

    if moved > 0:
        print(f">> {moved} directories archived", flush=True)
    else:
        print(">>No change", flush=True)

    if failed > 0:
        print(f"[WARN] {failed} directories failed to archive", file=sys.stderr)
        return 1

    return 0


# ============================================================
# main
# ============================================================

PROJECT_ROOT = resolve_project_root()


def main() -> int:
    """CLI 진입점. 서브커맨드(sync/status/archive)를 파싱하여 실행한다.

    Returns:
        종료 코드. 0: 성공, 1: 실패
    """
    parser = argparse.ArgumentParser(description="history sync/status core")
    subparsers = parser.add_subparsers(dest="subcmd", required=True)

    # sync subcommand
    sync_parser = subparsers.add_parser("sync", help="sync history.md")
    sync_parser.add_argument("--workflow-dir", default=os.path.join(PROJECT_ROOT, ".agent-factory", "runs"), help=".workflow directory path")
    sync_parser.add_argument("--target", default=os.path.join(PROJECT_ROOT, ".agent-factory", "board", "data", ".history.md"), help=".history.md file path")
    sync_parser.add_argument("--dry-run", action="store_true", help="Only preview changes")
    sync_parser.add_argument("--all", action="store_true", help="Includes interrupt operations")

    # status subcommand
    status_parser = subparsers.add_parser("status", help="Sync status summary")
    status_parser.add_argument("--workflow-dir", default=os.path.join(PROJECT_ROOT, ".agent-factory", "runs"), help=".workflow directory path")
    status_parser.add_argument("--target", default=os.path.join(PROJECT_ROOT, ".agent-factory", "board", "data", ".history.md"), help=".history.md file path")
    status_parser.add_argument("--all", action="store_true", help="Includes interrupt operations")

    # archive subcommand
    archive_parser = subparsers.add_parser("archive", help="Archive old workflows to .history/")
    archive_parser.add_argument("registry_key", nargs='?', default=None, help="registryKey of the current workflow (if omitted, active workflow will be automatically detected)")

    args = parser.parse_args()

    if args.subcmd == "sync":
        try:
            return cmd_sync(args)
        except Exception as e:
            print(f"[FAIL] sync failed: {e}", file=sys.stderr)
            return 1
    elif args.subcmd == "status":
        return cmd_status(args)
    elif args.subcmd == "archive":
        try:
            return cmd_archive(args)
        except Exception as e:
            print(f"[FAIL] archive failed: {e}", file=sys.stderr)
            return 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
