#!/usr/bin/env python3
"""
wf-history sync/status Python 코어 스크립트.

.workflow/ 디렉토리를 스캔하여 history.md와 비교하고,
누락 항목을 추가하거나 상태 변경 항목을 업데이트한다.

사용법:
    python3 history-sync-core.py sync --workflow-dir <path> --target <path> [--dry-run] [--all]
    python3 history-sync-core.py status --workflow-dir <path> --target <path> [--all]
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

MARKER_LINE = "<!-- 새 항목은 이 줄 아래에 추가됩니다 -->"

HEADER_LINE = "| 날짜 | 작업ID | 제목 & 내용 | 명령어 | 상태 | 계획서 | 질의 | 이미지 | 보고서 |"
SEPARATOR_LINE = "|------|--------|------------|--------|------|--------|------|--------|--------|"

TIMESTAMP_PATTERN = re.compile(r"^\d{8}-\d{6}$")

# status.json phase -> 표시 상태 매핑
PHASE_STATUS_MAP = {
    "COMPLETED": "완료",
    "REPORT": "완료",
    "STALE": "완료",
    "WORK": "진행중",
    "PLAN": "중단",
    "INIT": "중단",
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


def extract_status_from_json(status_file: str) -> tuple[str, str | None]:
    """status.json에서 phase와 created_at을 추출."""
    try:
        with open(status_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        phase = data.get("phase", "UNKNOWN")
        created_at = data.get("created_at")
        return phase, created_at
    except (json.JSONDecodeError, IOError, KeyError):
        return "UNKNOWN", None


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


def scan_workflow_directory(workflow_dir: str, include_all: bool = False) -> list[dict]:
    """
    .workflow/ 디렉토리를 스캔하여 각 작업의 메타정보를 추출.

    디렉토리 구조: .workflow/<YYYYMMDD-HHMMSS>/<workName>/<command>/
    """
    entries = []

    if not os.path.isdir(workflow_dir):
        return entries

    for dir_name in os.listdir(workflow_dir):
        dir_path = os.path.join(workflow_dir, dir_name)

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

            for command in os.listdir(work_path):
                cmd_path = os.path.join(work_path, command)
                if not os.path.isdir(cmd_path):
                    continue

                status_file = os.path.join(cmd_path, "status.json")
                plan_file = os.path.join(cmd_path, "plan.md")
                prompt_file = os.path.join(cmd_path, "user_prompt.txt")
                report_file = os.path.join(cmd_path, "report.md")
                files_dir = os.path.join(cmd_path, "files")

                # status.json에서 메타 정보 추출
                phase = "UNKNOWN"
                created_at = None
                if os.path.exists(status_file):
                    phase, created_at = extract_status_from_json(status_file)

                # include_all=False 시 INIT/PLAN 중단 작업 제외하지 않음
                # (기본적으로 모든 항목을 포함하되, include_all은 이미 기본 동작)
                # 기획 변경: include_all=False 시에도 모든 항목 포함
                # -> research 보고서에서는 --all 옵션으로 중단 작업 포함이지만
                #    W01에서 이미 모든 항목 포함하여 마이그레이션 완료.
                #    따라서 기본 동작도 모든 항목 포함으로 통일.

                status_text = PHASE_STATUS_MAP.get(phase, "불명")

                # 날짜/시간 추출
                date_str, time_str = parse_timestamp_from_dir(dir_name)

                # 요약 추출 (plan.md 우선, user_prompt.txt 폴백)
                summary = ""
                if os.path.exists(plan_file):
                    summary = extract_summary_from_plan(plan_file)
                if not summary and os.path.exists(prompt_file):
                    summary = extract_summary_from_prompt(prompt_file)

                # 제목: work_name (하이픈을 공백으로 변환하지 않고 그대로 사용)
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

                entries.append({
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
                    # 상대 경로 구성용
                    "work_name": work_name,
                    "rel_base": f"../.workflow/{dir_name}/{work_name}/{command}",
                })

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

    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")

        # 마커 라인 감지
        if MARKER_LINE in stripped:
            marker_idx = i
            header_lines.append(line)
            continue

        # 테이블 헤더/구분선 감지
        if "| 날짜" in stripped and "작업ID" in stripped:
            in_table = True
            table_header_seen = True
            header_lines.append(line)
            continue

        if table_header_seen and stripped.startswith("|---"):
            header_lines.append(line)
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

    # 기존 행을 work_id -> row 딕셔너리로 변환
    existing_rows = {}
    for row in data_rows:
        wid = extract_work_id_from_row(row)
        if wid:
            existing_rows[wid] = row

    # 비교: 누락 항목 및 상태 변경 항목 탐지
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

    if not new_entries and not updated_entries:
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

    # 기존 행 업데이트
    for row in data_rows:
        wid = extract_work_id_from_row(row)
        if wid in updated_row_map:
            final_rows.append(updated_row_map[wid])
        else:
            final_rows.append(row)

    # 신규 행을 날짜순으로 삽입 (전체를 합친 후 재정렬)
    all_rows = final_rows + new_rows

    # 작업ID(역순)로 정렬
    def sort_key(row):
        wid = extract_work_id_from_row(row)
        return wid if wid else ""

    all_rows.sort(key=sort_key, reverse=True)

    # history.md 파일 재구성
    output_lines = []

    # 제목
    output_lines.append("# 워크플로우 실행 이력\n")
    output_lines.append("\n")
    output_lines.append(f"{MARKER_LINE}\n")
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
    status_counts = {}
    for entry in scanned:
        s = entry["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    # 출력
    print("=== wf-history status ===")
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
    parser = argparse.ArgumentParser(description="wf-history sync/status core")
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
