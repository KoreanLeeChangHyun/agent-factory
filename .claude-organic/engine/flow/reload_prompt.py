#!/usr/bin/env -S python3 -u
"""reload_prompt.py - 수정 피드백을 워크플로우에 반영하는 스크립트.

현재 워크플로우의 티켓 파일(kanban/open/ 또는 kanban/progress/ 등 상태별 디렉터리)에서 피드백을 읽어
user_prompt.txt에 append한다.

티켓 파일은 환경변수 TICKET_NUMBER, .context.json의 ticketNumber 필드,
또는 kanban/open/, kanban/progress/, kanban/review/ 디렉터리의 XML 파일 직접 스캔에서 순서대로 탐색한다.

사용법:
  flow-reload <workDir>
  flow-reload <registryKey>
  flow-reload --help

인자:
  workDir    - 작업 디렉터리 상대 경로
  registryKey - YYYYMMDD-HHMMSS 형식의 레지스트리 키 (workDir 자동 해석)

환경변수:
  TICKET_NUMBER  티켓 번호 (T-NNN 또는 NNN 형식)

수행 작업 (순서대로):
  1. kanban/open/ 등 상태별 디렉터리에서 T-NNN.xml 읽기 (티켓 미발견 또는 비어있으면 경고 후 종료)
  2. <workDir>/user_prompt.txt에 구분선 + 피드백 append

출력 (stdout):
  피드백 내용 전문
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
_SCRIPTS_DIR = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from constants import KST
from flow.cli_utils import build_common_epilog
from flow.flow_logger import append_log

_KST = KST
_REGISTRY_KEY_PATTERN = re.compile(r"^\d{8}-\d{6}$")


def _resolve_workdir_from_registry(registry_key: str) -> tuple[str | None, list[str]]:
    """registryKey로부터 workDir 절대 경로를 자동 해석한다.

    탐색 순서:
      1. .claude-organic/runs/<registry_key>/ 하위 디렉터리 스캔
      2. 1차 탐색 실패(디렉터리 미존재) 시 .claude-organic/runs/.history/<registry_key>/ 하위 스캔

    Args:
        registry_key: 'YYYYMMDD-HHMMSS' 형식의 레지스트리 키

    Returns:
        (resolved_path, candidates) 튜플.
        - 유일한 경로 발견 시: (절대경로, [절대경로])
        - 복수 경로 발견 시: (None, [경로1, 경로2, ...])
        - 디렉터리 미존재 시: (None, [])
    """
    def _scan_registry_dir(registry_dir: str) -> list[str]:
        """registry_dir 하위 workDir 후보 목록을 반환한다."""
        if not os.path.isdir(registry_dir):
            return []
        result: list[str] = []
        for work_name in os.listdir(registry_dir):
            work_path = os.path.join(registry_dir, work_name)
            if not os.path.isdir(work_path):
                continue
            for command in os.listdir(work_path):
                cmd_path = os.path.join(work_path, command)
                if os.path.isdir(cmd_path):
                    result.append(cmd_path)
        return result

    workflow_base = os.path.join(_PROJECT_ROOT, ".claude-organic", "runs")

    # 1차 탐색: 활성 workflow 디렉터리
    registry_dir = os.path.join(workflow_base, registry_key)
    candidates = _scan_registry_dir(registry_dir)

    # 2차 탐색: .history/ 아카이브 디렉터리
    if not candidates:
        history_registry_dir = os.path.join(workflow_base, ".history", registry_key)
        candidates = _scan_registry_dir(history_registry_dir)

    if len(candidates) == 1:
        return candidates[0], candidates
    return None, candidates


def _normalize_ticket_number(raw: str) -> str | None:
    """티켓 번호 문자열을 'T-NNN' 형식으로 정규화한다.

    Args:
        raw: 원본 티켓 번호 문자열 (예: 'T-001', '001', '1')

    Returns:
        정규화된 'T-NNN' 형식 문자열. 변환 불가능하면 None.
    """
    raw = raw.strip().lstrip("#")
    if re.match(r"^T-\d+$", raw, re.IGNORECASE):
        parts = raw.split("-")
        return f"T-{int(parts[1]):03d}"
    if re.match(r"^\d+$", raw):
        return f"T-{int(raw):03d}"
    return None


def _find_ticket_file_by_number(kanban_dir: Path, ticket_number: str) -> str | None:
    """kanban 디렉터리에서 티켓 번호에 해당하는 파일을 정확 매칭으로 탐색한다.

    open/ -> progress/ -> review/ -> done/ -> active/ (폴백) -> 루트 (폴백) 순으로 탐색한다.

    Args:
        kanban_dir: .kanban 디렉터리 절대 경로
        ticket_number: 'T-NNN' 형식 티켓 번호

    Returns:
        찾은 티켓 파일의 절대 경로 문자열. 없으면 None.
    """
    # 1순위: .kanban/open/T-NNN.xml
    open_candidate: Path = kanban_dir / "open" / f"{ticket_number}.xml"
    if open_candidate.is_file():
        return str(open_candidate)
    # 2순위: .kanban/progress/T-NNN.xml
    progress_candidate: Path = kanban_dir / "progress" / f"{ticket_number}.xml"
    if progress_candidate.is_file():
        return str(progress_candidate)
    # 3순위: .kanban/review/T-NNN.xml
    review_candidate: Path = kanban_dir / "review" / f"{ticket_number}.xml"
    if review_candidate.is_file():
        return str(review_candidate)
    # 4순위: .kanban/done/T-NNN.xml
    done_candidate: Path = kanban_dir / "done" / f"{ticket_number}.xml"
    if done_candidate.is_file():
        return str(done_candidate)
    # 5순위 (하위 호환 폴백): .kanban/active/T-NNN.xml
    active_candidate: Path = kanban_dir / "active" / f"{ticket_number}.xml"
    if active_candidate.is_file():
        return str(active_candidate)
    # 6순위 (하위 호환 폴백): .kanban/T-NNN.xml
    root_candidate: Path = kanban_dir / f"{ticket_number}.xml"
    if root_candidate.is_file():
        return str(root_candidate)
    return None


def _resolve_ticket_file(abs_work_dir: str) -> str | None:
    """현재 워크플로우에 연결된 티켓 파일 경로를 결정한다.

    탐색 우선순위:
      1. 환경변수 TICKET_NUMBER
      2. .context.json의 ticketNumber 필드
      3. kanban/progress/ 디렉터리 XML 파일 직접 스캔 (In Progress 상태 첫 번째 티켓)
         + kanban/open/, kanban/review/ 및 active/ (하위 호환 폴백) 스캔

    Args:
        abs_work_dir: 현재 워크플로우 디렉터리 절대 경로

    Returns:
        티켓 파일 절대 경로. 결정 불가능하면 None.
    """
    kanban_dir: Path = Path(_PROJECT_ROOT) / ".claude-organic" / "tickets"

    # 1순위: 환경변수
    env_ticket = os.environ.get("TICKET_NUMBER", "").strip()
    if env_ticket:
        normalized = _normalize_ticket_number(env_ticket)
        if normalized:
            return _find_ticket_file_by_number(kanban_dir, normalized)

    # 2순위: .context.json ticketNumber
    context_path = os.path.join(abs_work_dir, ".context.json")
    if os.path.isfile(context_path):
        try:
            with open(context_path, "r", encoding="utf-8") as f:
                context = json.load(f)
            ticket_num = context.get("ticketNumber", "").strip()
            if ticket_num:
                normalized = _normalize_ticket_number(ticket_num)
                if normalized:
                    return _find_ticket_file_by_number(kanban_dir, normalized)
        except Exception:
            pass

    # 3순위: 상태별 디렉터리 XML 직접 스캔 (In Progress 상태 첫 번째 티켓)
    # progress/ 디렉터리를 우선 탐색하고, open/, review/ 및 active/ (하위 호환 폴백), 루트도 스캔
    try:
        import glob as _glob
        import xml.etree.ElementTree as _ET

        progress_dir = kanban_dir / "progress"
        open_dir = kanban_dir / "open"
        review_dir = kanban_dir / "review"
        active_dir = kanban_dir / "active"
        scan_dirs: list[Path] = [progress_dir, open_dir, review_dir, active_dir, kanban_dir]
        for scan_dir in scan_dirs:
            xml_files: list[str] = sorted(_glob.glob(str(scan_dir / "T-*.xml")))
            for xml_path in xml_files:
                try:
                    tree = _ET.parse(xml_path)
                    root = tree.getroot()
                    # <metadata> 내부의 <status> 탐색
                    metadata = root.find("metadata")
                    if metadata is None:
                        status_el = root.find("status")
                    else:
                        status_el = metadata.find("status")
                    if status_el is not None and (status_el.text or "").strip() == "In Progress":
                        # <metadata>/<number> 탐색
                        number_el = (metadata or root).find("number")
                        if number_el is not None and number_el.text:
                            normalized = _normalize_ticket_number(number_el.text.strip())
                            if normalized:
                                ticket_path = _find_ticket_file_by_number(kanban_dir, normalized)
                                if ticket_path:
                                    return ticket_path
                        # 파일명에서 번호 추출 (T-NNN.xml)
                        filename = os.path.basename(xml_path)
                        m = re.match(r"^(T-\d+)\.xml$", filename, re.IGNORECASE)
                        if m:
                            normalized = _normalize_ticket_number(m.group(1))
                            if normalized:
                                ticket_path = _find_ticket_file_by_number(kanban_dir, normalized)
                                if ticket_path:
                                    return ticket_path
                except Exception:
                    continue
    except Exception:
        pass

    return None


def main() -> None:
    """CLI 진입점. workDir 인자를 받아 티켓 피드백 반영 작업을 수행한다.

    수행 작업:
      1. kanban/open/ 등 상태별 디렉터리에서 T-NNN.xml 읽기 (티켓 미발견 또는 비어있으면 경고 후 종료)
      2. <workDir>/user_prompt.txt에 구분선 + 피드백 append

    XML 구조 호환성 주석:
        티켓 파일(kanban/open/ 또는 kanban/progress/ 등 상태별 디렉터리의 T-NNN.xml) 전체를
        문자열로 읽어 user_prompt.txt에 append하므로, 새 XML 구조(<metadata>/<submit>/<history>
        래퍼 요소, <prompt> 래퍼, <result> 구조화)에서도 동작에 영향이 없다. XML 내부 구조를
        파싱하거나 특정 태그를 추출하지 않으므로 코드 변경이 불필요하다.

    Raises:
        SystemExit: 인자 누락·형식 오류(2, argparse 처리), workDir 미존재(1), 정상 완료(0).
    """
    # --- 인자 파싱 ---
    parser = argparse.ArgumentParser(
        prog="flow-reload",
        description="수정 피드백을 워크플로우에 반영하는 스크립트.",
        epilog=build_common_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "work_dir",
        metavar="workDir",
        help=(
            "작업 디렉터리 상대 경로 또는 registryKey (YYYYMMDD-HHMMSS 형식).\n"
            "registryKey 형식으로 전달하면 하위 workDir을 자동 해석합니다.\n"
            "예: .claude-organic/runs/YYYYMMDD-HHMMSS/workName/command\n"
            "    20260403-011117"
        ),
    )
    args = parser.parse_args()

    work_dir = args.work_dir

    # registryKey 형식 판별 및 자동 해석
    if _REGISTRY_KEY_PATTERN.match(work_dir):
        registry_key = work_dir
        resolved, candidates = _resolve_workdir_from_registry(registry_key)
        if resolved is None:
            if not candidates:
                print(
                    f"[ERROR] registryKey '{registry_key}'에 해당하는 워크플로우 디렉터리를 찾을 수 없습니다",
                    file=sys.stderr,
                )
            else:
                paths_str = "\n  - ".join(candidates)
                print(
                    f"[ERROR] registryKey '{registry_key}' 하위에 복수 작업 경로가 존재합니다."
                    f" 전체 경로를 지정하세요:\n  - {paths_str}",
                    file=sys.stderr,
                )
            sys.exit(1)
        abs_work_dir = resolved
    else:
        abs_work_dir = os.path.join(_PROJECT_ROOT, work_dir)

    if not os.path.isdir(abs_work_dir):
        print(f"[ERROR] workDir not found: {work_dir}", file=sys.stderr)
        sys.exit(1)

    append_log(abs_work_dir, "INFO", f"reload_prompt: start workDir={work_dir}")

    ticket_file = _resolve_ticket_file(abs_work_dir)

    # --- Step 1: 티켓 파일 읽기 ---
    feedback = ""
    if ticket_file and os.path.isfile(ticket_file):
        with open(ticket_file, "r", encoding="utf-8") as f:
            feedback = f.read()

    if not feedback:
        append_log(abs_work_dir, "WARN", "reload_prompt: 티켓 파일을 찾을 수 없거나 비어있습니다 (kanban/open/ 또는 kanban/progress/ 등)")
        print("[STATE] RELOAD [WARN]", flush=True)
        print(">> 티켓 파일 미발견", flush=True)
        print("FAIL", flush=True)
        sys.exit(0)

    # --- Step 1.5: work/*.md 파일 수집 ---
    work_context = ""
    work_dir_path = abs_work_dir + "/work/"
    if os.path.isdir(work_dir_path):
        md_files = sorted(glob.glob(work_dir_path + "*.md"))
        # skill-map.md 제외 (부수 산출물)
        md_files = [f for f in md_files if os.path.basename(f) != "skill-map.md"]
        # 최대 5개 제한 (알파벳순 = 작업 순서, 마지막 5개 선택)
        if len(md_files) > 5:
            md_files = md_files[-5:]
        parts: list[str] = []
        for md_path in md_files:
            fname = os.path.basename(md_path)
            try:
                with open(md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                parts.append(f"--- work/{fname} ---\n\n{content}")
            except Exception:
                continue
        if parts:
            work_context = "\n\n".join(parts)

    # --- Step 2: user_prompt.txt에 피드백 append ---
    kst_date = datetime.now(_KST).strftime("%Y-%m-%d %H:%M")
    user_prompt_file = os.path.join(abs_work_dir, "user_prompt.txt")

    with open(user_prompt_file, "a", encoding="utf-8") as f:
        f.write(f"\n\n--- (수정 피드백, {kst_date}) ---\n\n")
        f.write(feedback)
        if work_context:
            f.write("\n\n--- (작업 내역 컨텍스트) ---\n\n")
            f.write(work_context)

    append_log(abs_work_dir, "INFO", "reload_prompt: complete")
    print("[STATE] RELOAD", flush=True)
    print(">> 피드백 적용 완료", flush=True)
    print(feedback, end="", flush=True)


if __name__ == "__main__":
    main()
