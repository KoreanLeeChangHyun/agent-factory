#!/usr/bin/env -S python3 -u
"""
history sync/status Python 코어 스크립트.

.workflow/ 및 .workflow/.history/ 디렉토리를 스캔하여 history.md와 비교하고,
누락 항목을 추가하거나 상태 변경 항목을 업데이트한다.

사용법:
    python3 .claude/scripts/workflow/history-sync-core.py sync --workflow-dir <path> --target <path> [--dry-run] [--all]
    python3 .claude/scripts/workflow/history-sync-core.py status --workflow-dir <path> --target <path> [--all]
"""

import argparse
import json
import os
import re
import sys
import tempfile
import shutil
from datetime import datetime
from pathlib import Path


# ============================================================
# 상수
# ============================================================

HEADER_LINE = "| 날짜 | 작업ID | 제목 & 내용 | 명령어 | 상태 | 계획서 | 질의 | 이미지 | 보고서 |"
SEPARATOR_LINE = "|------|--------|------------|--------|------|--------|------|--------|--------|"

TIMESTAMP_PATTERN = re.compile(r"^\d{8}-\d{6}$")

# status.json phase -> 표시 상태 매핑
PHASE_STATUS_MAP = {
    "COMPLETED": "완료",
    "REPORT": "진행중",
    "STALE": "중단",
    "WORK": "진행중",
    "PLAN": "진행중",
    "INIT": "진행중",
    "CANCELLED": "중단",
    "FAILED": "실패",
    "UNKNOWN": "불명",
    "NONE": "불명",
}


# ============================================================
# 헬퍼 함수
# ============================================================

def parse_timestamp_from_dir(dir_name: str) -> tuple[str, str]:
    """YYYYMMDD-HHMMSS 형식에서 날짜와 시간을 추출."""
    date_part = dir_name[:8]
    time_part = dir_name[9:15]
    formatted_date = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
    formatted_time = f"{time_part[:2]}:{time_part[2:4]}"
    return formatted_date, formatted_time


def extract_status_from_json(status_file: str) -> tuple[str, str | None, str | None]:
    """status.json에서 phase, created_at, updated_at을 추출."""
    try:
        with open(status_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        phase = data.get("phase", "UNKNOWN")
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        return phase, created_at, updated_at
    except (json.JSONDecodeError, IOError, KeyError):
        return "UNKNOWN", None, None


# 스테일 판정 TTL (초)
STALE_TTL_SECONDS = 30 * 60  # 30분


def is_stale(phase: str, updated_at: str | None) -> bool:
    """WORK 또는 PLAN 단계에서 updated_at 기준 30분 이상 경과하면 스테일로 판정."""
    if phase not in ("WORK", "PLAN", "INIT"):
        return False
    if not updated_at:
        return False
    try:
        # ISO 8601 형식 파싱 (타임존 포함)
        updated_dt = datetime.fromisoformat(updated_at)
        now = datetime.now(updated_dt.tzinfo)
        elapsed = (now - updated_dt).total_seconds()
        return elapsed > STALE_TTL_SECONDS
    except (ValueError, TypeError):
        return False


def extract_summary_from_plan(plan_file: str, max_len: int = 60) -> str:
    """plan.md에서 '## 작업 요약' 섹션의 첫 문장을 추출."""
    try:
        with open(plan_file, "r", encoding="utf-8") as f:
            content = f.read()
        # "## 작업 요약" 헤더 찾기
        match = re.search(r"##\s*작업\s*요약\s*\n+(.+)", content)
        if match:
            summary = match.group(1).strip()
            if len(summary) > max_len:
                summary = summary[:max_len]
            return summary
    except (IOError, UnicodeDecodeError):
        pass
    return ""


def extract_summary_from_prompt(prompt_file: str, max_len: int = 60) -> str:
    """user_prompt.txt의 첫 줄을 요약으로 추출."""
    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
        if len(first_line) > max_len:
            first_line = first_line[:max_len]
        return first_line
    except (IOError, UnicodeDecodeError):
        return ""


def extract_summary_from_file(summary_file: str, max_len: int = 60) -> str:
    """summary.txt의 첫 줄을 읽어 max_len 이내로 잘라 반환."""
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
    """.context.json에서 title 필드를 읽어 반환. JSON 파싱 실패 시 빈 문자열 반환."""
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
    """
    단일 워크플로우 디렉터리의 필수 파일을 검증하고, 누락 시 자동 생성한다.

    대상 디렉터리: <YYYYMMDD-HHMMSS>/<workName>/<command>/

    검증 대상 파일:
        - summary.txt: 1줄 텍스트 요약 파일

    자동 생성 규칙 (summary.txt):
        다음 우선순위로 요약 텍스트를 추출하여 summary.txt를 생성한다.
        (a) plan.md의 '## 작업 요약' 섹션 첫 문장
        (b) user_prompt.txt의 첫 줄
        (c) .context.json의 'title' 필드
        모든 소스에서 추출 실패 시 생성하지 않는다.
    """
    summary_file = os.path.join(cmd_path, "summary.txt")
    if os.path.exists(summary_file):
        return

    summary = ""

    # (a) plan.md의 '## 작업 요약' 섹션 첫 문장
    plan_file = os.path.join(cmd_path, "plan.md")
    if not summary and os.path.exists(plan_file):
        summary = extract_summary_from_plan(plan_file)

    # (b) user_prompt.txt의 첫 줄
    prompt_file = os.path.join(cmd_path, "user_prompt.txt")
    if not summary and os.path.exists(prompt_file):
        summary = extract_summary_from_prompt(prompt_file)

    # (c) .context.json의 'title' 필드
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


def _build_entry(dir_name: str, work_name: str, command: str,
                  cmd_path: str, work_path: str, rel_prefix: str) -> dict:
    """단일 엔트리의 메타정보를 수집하여 dict로 반환하는 내부 헬퍼."""
    ensure_entry_data(cmd_path)

    # 파일 경로 구성
    status_file = os.path.join(cmd_path, "status.json")
    plan_file = os.path.join(cmd_path, "plan.md")
    prompt_file = os.path.join(cmd_path, "user_prompt.txt")
    report_file = os.path.join(cmd_path, "report.md")
    files_dir = os.path.join(cmd_path, "files")

    # status.json에서 메타 정보 추출
    # 우선순위: <command>/status.json > <workName>/status.json
    phase = "UNKNOWN"
    created_at = None
    updated_at = None
    if os.path.exists(status_file):
        phase, created_at, updated_at = extract_status_from_json(status_file)
    else:
        # fallback: workName 레벨의 status.json
        work_status_file = os.path.join(work_path, "status.json")
        if os.path.exists(work_status_file):
            phase, created_at, updated_at = extract_status_from_json(work_status_file)

    # T1: 스테일 감지 - WORK/PLAN 단계에서 2시간 이상 경과 시 "중단"
    if is_stale(phase, updated_at):
        status_text = "중단"
    else:
        status_text = PHASE_STATUS_MAP.get(phase, "불명")

    # 날짜/시간 추출
    date_str, time_str = parse_timestamp_from_dir(dir_name)

    # 요약 추출 (summary.txt 최우선, plan.md 차선, user_prompt.txt 폴백)
    summary = ""
    summary_file = os.path.join(cmd_path, "summary.txt")
    if os.path.exists(summary_file):
        summary = extract_summary_from_file(summary_file)
    if not summary and os.path.exists(plan_file):
        summary = extract_summary_from_plan(plan_file)
    if not summary and os.path.exists(prompt_file):
        summary = extract_summary_from_prompt(prompt_file)

    # 제목: .context.json의 title 필드 우선, 없으면 work_name 폴백
    context_file = os.path.join(cmd_path, ".context.json")
    title = ""
    if os.path.exists(context_file):
        title = extract_title_from_context(context_file)
    if not title:
        title = work_name

    # 각 파일/디렉토리 존재 여부
    has_plan = os.path.exists(plan_file)
    has_prompt = os.path.exists(prompt_file)
    has_files = os.path.isdir(files_dir) and len(os.listdir(files_dir)) > 0
    has_report = os.path.exists(report_file)

    # 이미지 파일 개수 (files 디렉토리)
    files_count = 0
    if has_files:
        files_count = len(os.listdir(files_dir))

    return {
        "work_id": dir_name,
        "title": title,
        "summary": summary,
        "command": command,
        "phase": phase,
        "status": status_text,
        "date": date_str,
        "time": time_str,
        "has_plan": has_plan,
        "has_prompt": has_prompt,
        "has_files": has_files,
        "files_count": files_count,
        "has_report": has_report,
        "work_name": work_name,
        "rel_base": f"{rel_prefix}/{dir_name}/{work_name}/{command}",
    }


def _scan_entries_in_dir(base_dir: str, rel_prefix: str) -> list[dict]:
    """
    단일 디렉토리를 스캔하여 워크플로우 엔트리 목록을 반환.

    디렉토리 구조: base_dir/<YYYYMMDD-HHMMSS>/<workName>/<command>/
    command 서브디렉토리가 없고 workName에 직접 파일이 있으면 command="unknown"으로 폴백.
    rel_prefix: history.md에서의 상대 경로 접두사 (예: "../.workflow" 또는 "../.workflow/.history")
    """
    entries = []

    if not os.path.isdir(base_dir):
        return entries

    for dir_name in os.listdir(base_dir):
        dir_path = os.path.join(base_dir, dir_name)

        # YYYYMMDD-HHMMSS 패턴 확인
        if not TIMESTAMP_PATTERN.match(dir_name):
            continue
        if not os.path.isdir(dir_path):
            continue

        # 중첩 구조 탐색: <YYYYMMDD-HHMMSS>/<workName>/<command>/
        for work_name in os.listdir(dir_path):
            work_path = os.path.join(dir_path, work_name)
            if not os.path.isdir(work_path):
                continue

            # command 서브디렉토리 탐색
            has_command_subdir = False
            for command in os.listdir(work_path):
                cmd_path = os.path.join(work_path, command)
                if not os.path.isdir(cmd_path):
                    continue

                has_command_subdir = True
                entry = _build_entry(dir_name, work_name, command,
                                     cmd_path, work_path, rel_prefix)
                entries.append(entry)

            # T2: command 디렉토리가 없고, workName에 직접 파일이 존재하는 경우 폴백
            if not has_command_subdir:
                work_status = os.path.join(work_path, "status.json")
                work_prompt = os.path.join(work_path, "user_prompt.txt")
                if os.path.exists(work_status) or os.path.exists(work_prompt):
                    entry = _build_entry(dir_name, work_name, "unknown",
                                         work_path, work_path, rel_prefix)
                    entries.append(entry)

    return entries


def scan_workflow_directory(workflow_dir: str, include_all: bool = False) -> list[dict]:
    """
    .workflow/ 및 .workflow/.history/ 디렉토리를 스캔하여 각 작업의 메타정보를 추출.

    디렉토리 구조: .workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>/
    .history/ 하위도 동일 구조로 탐색하며, rel_base를 ../.workflow/.history/...로 구성.

    .workflow/ 엔트리가 .history/ 엔트리보다 우선한다 (같은 work_id인 경우).
    """
    # .workflow/ 스캔 (우선)
    entries = _scan_entries_in_dir(workflow_dir, "../.workflow")

    # 이미 수집된 work_id 셋 (우선순위 보호)
    seen_ids = {e["work_id"] for e in entries}

    # .workflow/.history/ 스캔
    history_dir = os.path.join(workflow_dir, ".history")
    history_entries = _scan_entries_in_dir(history_dir, "../.workflow/.history")

    # .workflow/에 없는 항목만 추가
    for entry in history_entries:
        if entry["work_id"] not in seen_ids:
            entries.append(entry)
            seen_ids.add(entry["work_id"])

    # 날짜 역순 정렬 (최신순)
    entries.sort(key=lambda x: x["work_id"], reverse=True)
    return entries


def format_row(entry: dict) -> str:
    """9컬럼 테이블 행을 생성."""
    # 날짜 셀: YYYY-MM-DD<br><sub>HH:MM</sub>
    date_cell = f"{entry['date']}<br><sub>{entry['time']}</sub>"

    # 제목 & 내용 셀: 제목<br><sub>요약</sub>
    if entry["summary"]:
        title_cell = f"{entry['title']}<br><sub>{entry['summary']}</sub>"
    else:
        title_cell = entry["title"]

    # 계획서 링크
    if entry["has_plan"]:
        plan_cell = f"[계획서]({entry['rel_base']}/plan.md)"
    else:
        plan_cell = "-"

    # 질의 링크
    if entry["has_prompt"]:
        prompt_cell = f"[질의]({entry['rel_base']}/user_prompt.txt)"
    else:
        prompt_cell = "-"

    # 이미지 링크
    if entry["has_files"]:
        files_cell = f"[이미지({entry['files_count']})]({entry['rel_base']}/files/)"
    else:
        files_cell = "-"

    # 보고서 링크
    if entry["has_report"]:
        report_cell = f"[보고서]({entry['rel_base']}/report.md)"
    else:
        report_cell = "-"

    return f"| {date_cell} | {entry['work_id']} | {title_cell} | {entry['command']} | {entry['status']} | {plan_cell} | {prompt_cell} | {files_cell} | {report_cell} |"


# ============================================================
# history.md 파싱
# ============================================================

def parse_history_md(filepath: str) -> tuple[list[str], set[str], int, list[str]]:
    """
    history.md를 파싱하여 구성 요소를 반환.

    Returns:
        - header_lines: 마커까지의 헤더 부분 (마커 포함)
        - existing_ids: 기존 작업ID Set
        - marker_idx: 마커 라인의 인덱스 (-1이면 없음)
        - data_rows: 데이터 행 목록 (테이블 헤더/구분선 제외)
    """
    if not os.path.exists(filepath):
        return [], set(), -1, []

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    header_lines = []
    data_rows = []
    existing_ids = set()
    marker_idx = -1
    in_table = False
    table_header_seen = False
    header_separator_seen = False

    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")

        # 테이블 헤더/구분선 감지
        if "| 날짜" in stripped and "작업ID" in stripped:
            in_table = True
            table_header_seen = True
            header_lines.append(line)
            continue

        if table_header_seen and stripped.startswith("|---"):
            if not header_separator_seen:
                # 테이블 헤더 직후 첫 구분선 -> 헤더의 일부
                header_lines.append(line)
                header_separator_seen = True
            # 데이터 행 사이의 중간 구분선은 무시 (data_rows에 추가하지 않음)
            continue

        # 데이터 행
        if in_table and stripped.startswith("|"):
            data_rows.append(stripped)
            # 작업ID 추출 (2번째 셀)
            cells = stripped.split("|")
            if len(cells) >= 3:
                work_id = cells[2].strip()
                if TIMESTAMP_PATTERN.match(work_id):
                    existing_ids.add(work_id)
        elif not in_table:
            header_lines.append(line)

    return header_lines, existing_ids, marker_idx, data_rows


def extract_status_from_row(row: str) -> str:
    """기존 데이터 행에서 상태 셀 값을 추출."""
    cells = row.split("|")
    if len(cells) >= 6:
        return cells[5].strip()
    return ""


def replace_status_in_row(row: str, new_status: str) -> str:
    """기존 데이터 행의 상태 셀 값을 교체."""
    cells = row.split("|")
    if len(cells) >= 6:
        cells[5] = f" {new_status} "
        return "|".join(cells)
    return row


def extract_work_id_from_row(row: str) -> str:
    """기존 데이터 행에서 작업ID를 추출."""
    cells = row.split("|")
    if len(cells) >= 3:
        return cells[2].strip()
    return ""


# ============================================================
# sync 명령어
# ============================================================

def cmd_sync(args: argparse.Namespace) -> int:
    """sync 서브커맨드 실행."""
    workflow_dir = args.workflow_dir
    target = args.target
    dry_run = args.dry_run
    include_all = args.all

    # .workflow/ 스캔
    scanned = scan_workflow_directory(workflow_dir, include_all)
    if not scanned:
        print("[INFO] .workflow/ 디렉토리에 작업이 없습니다.")
        return 0

    # history.md 파싱
    header_lines, existing_ids, marker_idx, data_rows = parse_history_md(target)

    # scanned 데이터를 work_id -> entry 맵으로 구성
    # (scan_workflow_directory에서 이미 .workflow/ 우선 처리됨)
    scanned_map = {}
    for entry in scanned:
        scanned_map.setdefault(entry["work_id"], entry)

    # 기존 행을 work_id -> row 딕셔너리로 변환
    # 레거시 형식 감지를 위해 원본 행도 보존
    existing_rows = {}
    original_rows = {}
    for row in data_rows:
        wid = extract_work_id_from_row(row)
        if wid:
            if wid in scanned_map:
                existing_rows[wid] = format_row(scanned_map[wid])
            else:
                existing_rows[wid] = row
            original_rows.setdefault(wid, row)

    # 비교: 누락 항목 및 상태 변경/레거시 형식 항목 탐지
    new_entries = []
    updated_entries = []

    for entry in scanned:
        wid = entry["work_id"]
        if wid not in existing_ids:
            new_entries.append(entry)
        else:
            # 상태 변경 확인
            old_row = existing_rows.get(wid, "")
            old_status = extract_status_from_row(old_row)
            new_status = entry["status"]
            if old_status != new_status:
                updated_entries.append(entry)
            else:
                # 레거시 형식 행(9컬럼 미만) 탐지: O(1) dict lookup
                orig_row = original_rows.get(wid, "")
                if orig_row and len(orig_row.split("|")) < 10:
                    updated_entries.append(entry)

    # 중복 행 존재 여부 확인
    wid_counts: dict[str, int] = {}
    for row in data_rows:
        wid = extract_work_id_from_row(row)
        if wid:
            wid_counts[wid] = wid_counts.get(wid, 0) + 1
    has_duplicates = any(c > 1 for c in wid_counts.values())

    # 레거시 형식 행 존재 여부 확인 (셀 수 10 미만)
    has_legacy = any(
        len(row.split("|")) < 10
        for row in data_rows
        if extract_work_id_from_row(row)
    )

    # T3: 고아 엔트리 감지 - history.md에는 있으나 파일시스템에 디렉토리가 없는 엔트리
    orphan_wids: set[str] = set()
    for row in data_rows:
        wid = extract_work_id_from_row(row)
        if wid and wid not in scanned_map:
            old_status = extract_status_from_row(row)
            if old_status != "삭제됨":
                orphan_wids.add(wid)

    if not new_entries and not updated_entries and not has_duplicates and not has_legacy and not orphan_wids:
        print("[INFO] history.md는 최신 상태입니다. 변경 사항 없음.")
        return 0

    # dry-run 모드
    if dry_run:
        print("[DRY-RUN] 변경 예정 사항:")
        print(f"  신규 추가: {len(new_entries)}건")
        for e in new_entries:
            print(f"    + {e['work_id']} | {e['title']} | {e['command']} | {e['status']}")
        print(f"  상태 업데이트: {len(updated_entries)}건")
        for e in updated_entries:
            old_row = existing_rows.get(e["work_id"], "")
            old_status = extract_status_from_row(old_row)
            print(f"    ~ {e['work_id']} | {old_status} -> {e['status']}")
        if orphan_wids:
            print(f"  고아 엔트리(삭제됨 표시): {len(orphan_wids)}건")
            for wid in sorted(orphan_wids, reverse=True):
                print(f"    ! {wid} | 삭제됨")
        return 0

    # 실제 갱신
    # 1. 기존 행에서 상태 변경 적용
    updated_row_map = {}
    for entry in updated_entries:
        updated_row_map[entry["work_id"]] = format_row(entry)

    # 2. 전체 데이터 재구성 (기존 행 업데이트 + 신규 행 추가)
    final_rows = []

    # 신규 행 생성
    new_rows = [format_row(e) for e in new_entries]

    # 기존 행 업데이트 (scanned 데이터가 있으면 format_row로 재생성)
    for row in data_rows:
        wid = extract_work_id_from_row(row)
        if wid in updated_row_map:
            final_rows.append(updated_row_map[wid])
        elif wid in scanned_map:
            # scanned 데이터로 재생성 (레거시 형식/누락 링크 해소)
            final_rows.append(format_row(scanned_map[wid]))
        elif wid in orphan_wids:
            # T3: 고아 엔트리 - 상태를 "삭제됨"으로 변경
            final_rows.append(replace_status_in_row(row, "삭제됨"))
        else:
            final_rows.append(row)

    # 신규 행을 날짜순으로 삽입 (전체를 합친 후 재정렬)
    # 중간 구분선 행을 필터링하여 최종 출력에 포함시키지 않음
    all_rows = [r for r in (final_rows + new_rows) if not r.strip().startswith("|---")]

    # 작업ID(역순)로 정렬
    def sort_key(row):
        wid = extract_work_id_from_row(row)
        return wid if wid else ""

    all_rows.sort(key=sort_key, reverse=True)

    # work_id 기준 중복 행 제거 (정렬 후 첫 번째 행만 유지)
    seen_wids: set[str] = set()
    deduped_rows = []
    for row in all_rows:
        wid = extract_work_id_from_row(row)
        if wid and wid in seen_wids:
            continue
        if wid:
            seen_wids.add(wid)
        deduped_rows.append(row)
    all_rows = deduped_rows

    # history.md 파일 재구성
    output_lines = []

    # 제목
    output_lines.append("# 워크플로우 실행 이력\n")
    output_lines.append("\n")
    output_lines.append(f"{HEADER_LINE}\n")
    output_lines.append(f"{SEPARATOR_LINE}\n")

    for row in all_rows:
        output_lines.append(f"{row}\n")

    # 원자적 쓰기
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

    # 결과 요약
    print(f"[SYNC] 완료:")
    print(f"  신규 추가: {len(new_entries)}건")
    for e in new_entries:
        print(f"    + {e['work_id']} | {e['title']} | {e['command']} | {e['status']}")
    if updated_entries:
        print(f"  상태 업데이트: {len(updated_entries)}건")
        for e in updated_entries:
            old_row = existing_rows.get(e["work_id"], "")
            old_status = extract_status_from_row(old_row)
            print(f"    ~ {e['work_id']} | {old_status} -> {e['status']}")
    if orphan_wids:
        print(f"  고아 엔트리(삭제됨 표시): {len(orphan_wids)}건")
        for wid in sorted(orphan_wids, reverse=True):
            print(f"    ! {wid} | 삭제됨")
    print(f"  총 행 수: {len(all_rows)}건")

    return 0


# ============================================================
# status 명령어
# ============================================================

def cmd_status(args: argparse.Namespace) -> int:
    """status 서브커맨드 실행."""
    workflow_dir = args.workflow_dir
    target = args.target
    include_all = args.all

    # .workflow/ 스캔
    scanned = scan_workflow_directory(workflow_dir, include_all)

    # history.md 파싱
    _, existing_ids, _, data_rows = parse_history_md(target)

    # 누락 항목 계산
    scanned_ids = {e["work_id"] for e in scanned}
    missing_ids = scanned_ids - existing_ids
    extra_ids = existing_ids - scanned_ids

    # 상태별 분류
    status_counts: dict[str, int] = {}
    for entry in scanned:
        s = entry["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    # 출력
    print("=== history-sync status ===")
    print(f"  .workflow/ 디렉토리 수: {len(scanned)}개")
    print(f"  history.md 행 수:       {len(data_rows)}행")
    print(f"  누락 항목:              {len(missing_ids)}건")
    if extra_ids:
        print(f"  history.md에만 존재:    {len(extra_ids)}건")
    print()
    print("  상태별 분류:")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"    {status}: {count}건")

    if missing_ids:
        print()
        print("  누락 항목 목록:")
        for entry in scanned:
            if entry["work_id"] in missing_ids:
                print(f"    - {entry['work_id']} | {entry['title']} | {entry['command']} | {entry['status']}")

    return 0


# ============================================================
# main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="history sync/status core")
    subparsers = parser.add_subparsers(dest="subcmd", required=True)

    # sync 서브커맨드
    sync_parser = subparsers.add_parser("sync", help="history.md 동기화")
    sync_parser.add_argument("--workflow-dir", required=True, help=".workflow 디렉토리 경로")
    sync_parser.add_argument("--target", required=True, help="history.md 파일 경로")
    sync_parser.add_argument("--dry-run", action="store_true", help="변경 미리보기만 수행")
    sync_parser.add_argument("--all", action="store_true", help="중단 작업 포함")

    # status 서브커맨드
    status_parser = subparsers.add_parser("status", help="동기화 상태 요약")
    status_parser.add_argument("--workflow-dir", required=True, help=".workflow 디렉토리 경로")
    status_parser.add_argument("--target", required=True, help="history.md 파일 경로")
    status_parser.add_argument("--all", action="store_true", help="중단 작업 포함")

    args = parser.parse_args()

    if args.subcmd == "sync":
        return cmd_sync(args)
    elif args.subcmd == "status":
        return cmd_status(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
