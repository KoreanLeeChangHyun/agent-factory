#!/usr/bin/env -S python3 -u
"""reload_prompt.py - 수정 피드백을 워크플로우에 반영하는 스크립트.

현재 워크플로우의 티켓 파일(.kanban/T-NNN.xml)에서 피드백을 읽어
user_prompt.txt에 append한다.

티켓 파일은 환경변수 TICKET_NUMBER, .context.json의 ticketNumber 필드,
또는 .kanban/ 디렉터리의 XML 파일 직접 스캔에서 순서대로 탐색한다.

사용법:
  python3 reload_prompt.py <workDir>

인자:
  workDir - 작업 디렉터리 상대 경로

환경변수:
  TICKET_NUMBER  티켓 번호 (T-NNN 또는 NNN 형식)

수행 작업 (순서대로):
  1. .kanban/T-NNN.xml 읽기 (티켓 미발견 또는 비어있으면 경고 후 종료)
  2. <workDir>/user_prompt.txt에 구분선 + 피드백 append

출력 (stdout):
  피드백 내용 전문
"""

from __future__ import annotations

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

from data.constants import KST
from flow.flow_logger import append_log

_KST = KST


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

    루트 파일(T-NNN.xml)을 먼저 탐색하고, 없으면 done 서브디렉터리도 탐색한다.

    Args:
        kanban_dir: .kanban 디렉터리 절대 경로
        ticket_number: 'T-NNN' 형식 티켓 번호

    Returns:
        찾은 티켓 파일의 절대 경로 문자열. 없으면 None.
    """
    candidate: Path = kanban_dir / f"{ticket_number}.xml"
    if candidate.is_file():
        return str(candidate)
    # done 서브디렉터리 탐색
    done_candidate: Path = kanban_dir / "done" / f"{ticket_number}.xml"
    if done_candidate.is_file():
        return str(done_candidate)
    return None


def _resolve_ticket_file(abs_work_dir: str) -> str | None:
    """현재 워크플로우에 연결된 티켓 파일 경로를 결정한다.

    탐색 우선순위:
      1. 환경변수 TICKET_NUMBER
      2. .context.json의 ticketNumber 필드
      3. .kanban/ 디렉터리 XML 파일 직접 스캔 (In Progress 상태 첫 번째 티켓)

    Args:
        abs_work_dir: 현재 워크플로우 디렉터리 절대 경로

    Returns:
        .kanban/T-NNN.xml 절대 경로. 결정 불가능하면 None.
    """
    kanban_dir: Path = Path(_PROJECT_ROOT) / ".kanban"

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

    # 3순위: .kanban/ 디렉터리 XML 직접 스캔 (In Progress 상태 첫 번째 티켓)
    try:
        import glob as _glob
        import xml.etree.ElementTree as _ET

        xml_files: list[str] = sorted(_glob.glob(str(kanban_dir / "T-*.xml")))
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
      1. .kanban/T-NNN.xml 읽기 (티켓 미발견 또는 비어있으면 경고 후 종료)
      2. <workDir>/user_prompt.txt에 구분선 + 피드백 append

    XML 구조 호환성 주석:
        티켓 파일(.kanban/T-NNN.xml) 전체를 문자열로 읽어 user_prompt.txt에
        append하므로, 새 XML 구조(<metadata>/<submit>/<history> 래퍼 요소, <prompt>
        래퍼, <result> 구조화)에서도 동작에 영향이 없다. XML 내부 구조를 파싱하거나
        특정 태그를 추출하지 않으므로 코드 변경이 불필요하다.

    Raises:
        SystemExit: 인자 누락(1), workDir 미존재(1), 정상 완료(0).
    """
    # --- 인자 확인 ---
    if len(sys.argv) < 2:
        print(f"[ERROR] 사용법: {sys.argv[0]} <workDir>", file=sys.stderr)
        sys.exit(1)

    work_dir = sys.argv[1]
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
        append_log(abs_work_dir, "WARN", "reload_prompt: 티켓 파일을 찾을 수 없거나 비어있습니다 (.kanban/T-NNN.xml)")
        print("FAIL", flush=True)
        print("[WARN] 티켓 파일을 찾을 수 없거나 비어있습니다 (.kanban/T-NNN.xml)", flush=True)
        sys.exit(0)

    # --- Step 2: user_prompt.txt에 피드백 append ---
    kst_date = datetime.now(_KST).strftime("%Y-%m-%d %H:%M")
    user_prompt_file = os.path.join(abs_work_dir, "user_prompt.txt")

    with open(user_prompt_file, "a", encoding="utf-8") as f:
        f.write(f"\n\n--- (수정 피드백, {kst_date}) ---\n\n")
        f.write(feedback)

    append_log(abs_work_dir, "INFO", "reload_prompt: complete")
    print(feedback, end="", flush=True)


if __name__ == "__main__":
    main()
