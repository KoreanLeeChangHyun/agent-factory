#!/usr/bin/env -S python3 -u
"""
kanban.py - 칸반 보드 상태 관리 CLI 스크립트.

XML 티켓 파일(.kanban/active/T-NNN.xml)을 Single Source of Truth(SSoT)로 사용한다.
LLM 호출 없음 (순수 IO).

사용법:
  python3 kanban.py create <title>
  python3 kanban.py move <ticket> <target>
  python3 kanban.py done <ticket>        # active/ -> done/ 이동
  python3 kanban.py delete <ticket>
  python3 kanban.py add-subnumber <ticket> --command <cmd> --goal "<goal>" --target "<target>" [--workdir <path>] [--result "<text>"]
  python3 kanban.py update-title <ticket> <title>
  python3 kanban.py update-subnumber <ticket> --id <N>
  python3 kanban.py archive-subnumber <ticket>

서브커맨드:
  create            새 티켓 XML을 생성한다
  move              티켓 상태를 변경한다
  done              티켓을 Done으로 변경하고 파일을 .kanban/done/으로 이동한다
  delete            티켓 XML 파일을 삭제한다
  add-subnumber     티켓 XML에 새 subnumber 항목을 추가한다
  archive-subnumber active subnumber를 submit에서 history로 이동한다
  update-title      티켓 제목을 갱신한다
  update-subnumber  기존 subnumber의 result 내부 필드를 갱신한다

티켓 번호 형식:
  T-NNN, NNN, #N 형식을 모두 지원하며 내부적으로 T-NNN으로 정규화한다.

상태 전이 규칙:
  Open → Submit → In Progress → Review → Done (정방향, /wf -s N 실행 시 Submit 경유)
  Open → In Progress (직접 전환, 하위 호환)
  모든 상태 → Open (재오픈)
  Submit → In Progress (flow-init 실행 시 자동 전환)
  --force 플래그로 규칙 무시 가능

종료 코드:
  0  성공
  1  에러 (티켓 없음, 잘못된 전이 등)
  2  인자 오류
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, NoReturn

# ─── 경로 상수 ───────────────────────────────────────────────────────────────

_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT: str = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
_SCRIPTS_DIR: str = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


# ─── 로깅 헬퍼 ───────────────────────────────────────────────────────────────

def _resolve_work_dir_for_logging() -> str | None:
    """현재 워크플로우의 abs_work_dir을 환경변수 또는 .context.json에서 해석한다.

    해석 불가 시 None을 반환하여 로깅 실패가 스크립트 실행에 영향을 주지 않도록 한다.
    """
    try:
        # flow_logger가 존재하면 위임
        _flow_dir = os.path.dirname(os.path.abspath(__file__))
        if _flow_dir not in sys.path:
            sys.path.insert(0, _flow_dir)
        from flow_logger import resolve_work_dir_for_logging
        return resolve_work_dir_for_logging()
    except Exception:
        pass
    try:
        # 환경변수 WORKFLOW_WORK_DIR 직접 참조
        work_dir = os.environ.get("WORKFLOW_WORK_DIR", "")
        if work_dir and os.path.isdir(work_dir):
            return work_dir
        # .workflow/ 디렉터리에서 가장 최근 활성 워크플로우 탐색
        workflow_base = os.path.join(_PROJECT_ROOT, ".workflow")
        if not os.path.isdir(workflow_base):
            return None
        import glob as _glob
        context_files = _glob.glob(os.path.join(workflow_base, "*", "*", "*", ".context.json"))
        if not context_files:
            return None
        context_files.sort(key=os.path.getmtime, reverse=True)
        for cf in context_files:
            candidate = os.path.dirname(cf)
            if os.path.isdir(candidate):
                return candidate
    except Exception:
        pass
    return None


def _log(level: str, message: str) -> None:
    """workflow.log에 이벤트를 기록한다. abs_work_dir 해석 실패 시 조용히 건너뛴다."""
    try:
        # flow_logger가 존재하면 위임
        _flow_dir = os.path.dirname(os.path.abspath(__file__))
        if _flow_dir not in sys.path:
            sys.path.insert(0, _flow_dir)
        from flow_logger import append_log, resolve_work_dir_for_logging
        abs_work_dir = resolve_work_dir_for_logging()
        if abs_work_dir:
            append_log(abs_work_dir, level, message)
        return
    except Exception:
        pass
    try:
        abs_work_dir = _resolve_work_dir_for_logging()
        if not abs_work_dir:
            return
        from datetime import timezone, timedelta
        kst = timezone(timedelta(hours=9))
        ts = datetime.now(kst).strftime("%Y-%m-%dT%H:%M:%S")
        log_path = os.path.join(abs_work_dir, "workflow.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {message}\n")
    except Exception:
        pass

# ─── 상수 ───────────────────────────────────────────────────────────────────

# 컬럼 이름 매핑: CLI 인자 → 컬럼명
COLUMN_MAP: dict[str, str] = {
    "open": "Open",
    "submit": "Submit",
    "progress": "In Progress",
    "review": "Review",
    "done": "Done",
}

# 허용 상태 전이 규칙: 현재 상태 → 허용 대상 목록
# Done으로의 이동은 done 서브커맨드(force=True)만 허용.
# move 커맨드로 Done 직접 이동은 불가 (Review → Done도 done 서브커맨드 사용 필요).
ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "Open": ["In Progress", "Submit"],
    "Submit": ["In Progress", "Open"],
    "In Progress": ["Review", "Open"],
    "Review": ["Open", "In Progress"],
    "Done": ["Open"],
}

_KANBAN_DIR: str = os.path.join(_PROJECT_ROOT, ".kanban")
_KANBAN_ACTIVE_DIR: str = os.path.join(_KANBAN_DIR, "active")


# ─── XML 헬퍼 ────────────────────────────────────────────────────────────────


def _create_ticket_xml(ticket_number: str, title: str = "", datetime_str: str = "") -> str:
    """티켓 XML 문자열을 생성하여 반환한다.

    XML은 <metadata>, <submit>, <history> 래퍼 요소로 구분된다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).
        title: 티켓 제목. 빈 문자열 허용.
        datetime_str: 생성 일시 문자열 (YYYY-MM-DD HH:MM:SS 형식). 빈 문자열이면 현재 시간 사용.

    Returns:
        UTF-8 XML 선언을 포함한 티켓 XML 문자열.
    """
    root = ET.Element("ticket")
    # <metadata> 래퍼 요소
    metadata_elem = ET.SubElement(root, "metadata")
    ET.SubElement(metadata_elem, "number").text = ticket_number
    title_sub = ET.SubElement(metadata_elem, "title")
    if title:
        title_sub.text = title
    ET.SubElement(metadata_elem, "datetime").text = datetime_str or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ET.SubElement(metadata_elem, "status").text = "Open"
    ET.SubElement(metadata_elem, "current").text = "0"
    # <submit> 래퍼 요소
    ET.SubElement(root, "submit")
    # <history> 래퍼 요소 (subnumber가 완료되면 여기 아래로 이동)
    ET.SubElement(root, "history")
    ET.indent(root, space="  ")
    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=False)
    # 섹션 주석 삽입: <metadata>, <submit>, <history> 태그 직전에 주석 추가
    # self-closing 태그(<submit />, <history />) 및 일반 태그(<submit>, <history>) 모두 처리
    xml_str = re.sub(r"(<metadata[ />])", r"<!-- metadata -->\n  \1", xml_str)
    xml_str = re.sub(r"(<submit[ />])", r"\n  <!-- submit -->\n  \1", xml_str)
    xml_str = re.sub(r"(<history[ />])", r"\n  <!-- history -->\n  \1", xml_str)
    return xml_str


def _write_ticket_xml(filepath: str, root: ET.Element) -> None:
    """XML Element를 파일에 저장한다.

    <metadata>, <submit>, <history> 래퍼 요소 구조를 유지하고,
    subnumber 요소 사이에 빈 줄을 삽입하여 가독성을 높인다.
    prompt, result 래퍼 태그를 포함한 구조에서도 정상 동작한다.

    Args:
        filepath: 저장할 파일 경로.
        root: 저장할 XML 루트 Element.
    """
    ET.indent(root, space="  ")
    xml_str = ET.tostring(root, encoding="unicode")
    # </subnumber> 다음 <subnumber 앞에 빈 줄 삽입
    xml_str = re.sub(r"(</subnumber>)\s*(<subnumber)", r"\1\n\n      \2", xml_str)
    # prompt 내부 필드 텍스트를 개행+들여쓰기로 래핑하여 가독성 확보 (10자 이상만)
    _PROMPT_FIELD_INLINE_LIMIT = 10

    def _wrap_prompt_field(m: re.Match[str]) -> str:
        indent = m.group(1)
        tag = m.group(2)
        content = m.group(3).strip()
        # \\n 리터럴(2문자)을 실제 개행문자로 변환
        content = content.replace("\\n", "\n")
        # 리스트 패턴 자동 개행: 숫자) 패턴과 대시(-) 패턴 앞에 개행 삽입 (문자열 시작 제외)
        content = re.sub(r"(?<!^)(?<!\n)(?<!\()(\s)(\d{1,2}\))", r"\n\2", content)
        content = re.sub(r"(?<!^)(?<!\n)(\s*)(- )", r"\n\2", content)
        if len(content) < _PROMPT_FIELD_INLINE_LIMIT:
            return f"{indent}<{tag}>{content}</{tag}>"
        inner_indent = indent + "  "
        return f"{indent}<{tag}>\n{inner_indent}{content}\n{indent}</{tag}>"

    xml_str = re.sub(
        r"( *)<(goal|target|constraints|criteria|context)>(.+)</\2>",
        _wrap_prompt_field,
        xml_str,
    )
    # 섹션 주석 삽입: <metadata>, <submit>, <history> 태그 직전에 주석 추가 (없는 경우에만)
    # self-closing 태그(<submit />, <history />) 및 일반 태그(<submit>, <history>) 모두 처리
    if "<!-- metadata -->" not in xml_str:
        xml_str = re.sub(r"(<metadata[ />])", r"<!-- metadata -->\n  \1", xml_str)
    if "<!-- submit -->" not in xml_str:
        xml_str = re.sub(r"(<submit[ />])", r"\n  <!-- submit -->\n  \1", xml_str)
    if "<!-- history -->" not in xml_str:
        xml_str = re.sub(r"(<history[ />])", r"\n  <!-- history -->\n  \1", xml_str)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(xml_str)
        f.write("\n")


def _parse_ticket_xml(filepath: str) -> dict[str, Any]:
    """티켓 XML 파일을 파싱하여 딕셔너리로 반환한다.

    <metadata>, <submit>, <history> 래퍼 요소 기반으로 파싱한다.
    subnumber는 <submit> 및 <history> 래퍼 내부에서 탐색한다.
    subnumber 내부에 <prompt> 래퍼가 있으면 그 안의 필드를 파싱한다.

    Args:
        filepath: 파싱할 티켓 파일 경로.

    Returns:
        파싱된 티켓 정보 딕셔너리:
            - number (str): 티켓 번호
            - status (str): 현재 상태
            - current (int): 현재 subnumber ID
            - title (str): 티켓 제목
            - subnumbers (list[dict]): subnumber 목록

    Raises:
        SystemExit: 파일 읽기 실패 또는 XML 파싱 오류 시.
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        _err(f"티켓 파일 파싱 실패 ({filepath}): {e}")

    def _text(elem: ET.Element, tag: str, default: str = "") -> str:
        """자식 Element의 텍스트를 반환하는 헬퍼."""
        child = elem.find(tag)
        return child.text.strip() if child is not None and child.text else default

    # <metadata> 래퍼에서 number/title/datetime/status 파싱
    metadata_elem = root.find("metadata")
    submit_elem = root.find("submit")
    history_elem = root.find("history")

    if metadata_elem is not None:
        number = _text(metadata_elem, "number")
        status = _text(metadata_elem, "status")
        title = _text(metadata_elem, "title")
    else:
        number = _text(root, "number")
        status = _text(root, "status")
        title = _text(root, "title")

    # <current>는 <metadata> 내부 우선, 없으면 <submit> 폴백, 둘 다 없으면 루트 폴백
    if metadata_elem is not None and metadata_elem.find("current") is not None:
        current = int(_text(metadata_elem, "current", "0"))
    elif submit_elem is not None and submit_elem.find("current") is not None:
        current = int(_text(submit_elem, "current", "0"))
    else:
        current = int(_text(root, "current", "0"))

    # <editing>은 <metadata> 내부에서 파싱. 없으면 false로 폴백
    if metadata_elem is not None:
        editing = _text(metadata_elem, "editing", "false") == "true"
    else:
        editing = False

    # subnumber를 <submit> 및 <history> 래퍼 내부에서 탐색
    subnumbers: list[dict[str, Any]] = []
    sub_sources: list[ET.Element] = []
    if submit_elem is not None:
        sub_sources.append(submit_elem)
    if history_elem is not None:
        sub_sources.append(history_elem)
    if not sub_sources:
        # 래퍼가 없는 경우 루트에서 직접 탐색
        sub_sources.append(root)

    for source in sub_sources:
        for sub in source.findall("subnumber"):
            sub_id = sub.get("id", "")
            sub_data: dict[str, Any] = {"id": int(sub_id) if sub_id.isdigit() else 0}

            # <prompt> 래퍼 내부 필드 파싱
            prompt_elem = sub.find("prompt")
            if prompt_elem is not None:
                for prompt_child in prompt_elem:
                    text = prompt_child.text.strip() if prompt_child.text else ""
                    sub_data[prompt_child.tag] = text

            # <result> 래퍼 내부 필드 파싱
            result_elem = sub.find("result")
            if result_elem is not None and len(result_elem) > 0:
                # 구조화된 result: 하위 요소(workdir, plan, work, report, workflow)를 개별 파싱
                result_data: dict[str, str] = {}
                for result_child in result_elem:
                    text = result_child.text.strip() if result_child.text else ""
                    result_data[result_child.tag] = text
                    # workdir은 subnumber 레벨에도 노출 (하위 호환)
                    if result_child.tag == "workdir":
                        sub_data["workdir"] = text
                    # workflow는 subnumber 레벨에도 노출
                    if result_child.tag == "workflow":
                        sub_data["workflow"] = text
                sub_data["result"] = result_data
            elif result_elem is not None and result_elem.text:
                sub_data["result"] = result_elem.text.strip()

            # subnumber 직하 필드 파싱 (prompt/result 밖의 datetime, command 등)
            for child in sub:
                tag = child.tag
                if tag in ("prompt", "result"):
                    continue  # 이미 위에서 처리
                text = child.text.strip() if child.text else ""
                sub_data[tag] = text

            subnumbers.append(sub_data)

    return {
        "number": number,
        "status": status,
        "current": current,
        "title": title,
        "editing": editing,
        "subnumbers": subnumbers,
    }


def _find_history_element(root: ET.Element) -> ET.Element | None:
    """<history> 래퍼 요소를 찾아 반환한다.

    Args:
        root: XML 루트 Element.

    Returns:
        <history> 래퍼 Element. 없으면 None.
    """
    return root.find("history")


def _move_active_to_history(filepath: str) -> bool:
    """<submit> 내 active subnumber를 <history>로 이동한다.

    <submit> 래퍼 내에서 active="true" 속성을 가진 subnumber를 찾아
    active 속성을 제거하고 <history> 래퍼로 이동한 뒤 저장한다.

    Args:
        filepath: 티켓 파일 경로.

    Returns:
        이동 성공 시 True, active subnumber가 없으면 False.
    """
    tree = ET.parse(filepath)
    root = tree.getroot()

    submit_elem = root.find("submit")
    history_elem = root.find("history")

    if submit_elem is None:
        return False

    active_sub = None
    for sub in submit_elem.findall("subnumber"):
        if sub.get("active") == "true":
            active_sub = sub
            break

    if active_sub is None:
        return False

    del active_sub.attrib["active"]
    submit_elem.remove(active_sub)

    if history_elem is not None:
        history_elem.append(active_sub)
    else:
        root.append(active_sub)

    _write_ticket_xml(filepath, root)
    return True


def _add_subnumber(filepath: str, subnumber_data: dict[str, Any]) -> int:
    """티켓 XML에 새 subnumber를 추가하고 <current>를 갱신한다.

    신규 subnumber는 <submit> 래퍼 내부(<current> 요소 바로 다음)에 삽입한다.
    기존 활성 subnumber는 active 속성을 제거하고 <history> 래퍼로 이동한다.
    프롬프트 5요소는 <prompt> 래퍼 내부에, <command>는 subnumber 직하에 배치한다.
    <result>는 workflow 하위 요소를 갖는 구조화된 래퍼로 생성한다.

    Args:
        filepath: 티켓 파일 경로.
        subnumber_data: 추가할 subnumber 필드 딕셔너리.
            공통 필드: command, datetime
            프롬프트 5요소 (prompt 래퍼 내부): goal, target, context, constraints(선택), criteria(선택)
            결과 필드 (result 래퍼 내부): workflow(선택, W-NNN 형식)

    Returns:
        새로 추가된 subnumber의 ID (정수).

    Raises:
        SystemExit: 파일 읽기/쓰기 실패 시.
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        _err(f"티켓 파일 파싱 실패 ({filepath}): {e}")

    metadata_elem = root.find("metadata")
    submit_elem = root.find("submit")
    history_elem = _find_history_element(root)

    # <current>는 <metadata> 내부 우선, 없으면 <submit> 폴백, 둘 다 없으면 루트 폴백
    if metadata_elem is not None and metadata_elem.find("current") is not None:
        current_elem = metadata_elem.find("current")
    elif submit_elem is not None and submit_elem.find("current") is not None:
        current_elem = submit_elem.find("current")
    else:
        current_elem = root.find("current")
    current_val = int(current_elem.text.strip()) if current_elem is not None and current_elem.text else 0
    new_id = current_val + 1

    # 기존 활성 subnumber를 <history> 래퍼로 이동
    if submit_elem is not None:
        for existing_sub in submit_elem.findall("subnumber"):
            if "active" in existing_sub.attrib:
                del existing_sub.attrib["active"]
                submit_elem.remove(existing_sub)
                if history_elem is not None:
                    history_elem.append(existing_sub)
                else:
                    root.append(existing_sub)

    # 신규 subnumber 요소 생성 (active="true" 설정)
    sub_elem = ET.Element("subnumber")
    sub_elem.set("id", str(new_id))
    sub_elem.set("active", "true")

    # datetime 필드 (없으면 현재 시간)
    dt_str = subnumber_data.get("datetime", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    ET.SubElement(sub_elem, "datetime").text = dt_str

    # command는 subnumber 직하에 배치 (prompt 밖)
    if "command" in subnumber_data:
        ET.SubElement(sub_elem, "command").text = str(subnumber_data["command"])

    # <prompt> 래퍼: goal, target, constraints, criteria, context를 내부에 배치
    prompt_fields = ("goal", "target", "constraints", "criteria", "context")
    has_prompt_fields = any(subnumber_data.get(f) for f in prompt_fields)
    if has_prompt_fields:
        prompt_elem = ET.SubElement(sub_elem, "prompt")
        for field in prompt_fields:
            if subnumber_data.get(field):
                elem = ET.SubElement(prompt_elem, field)
                text = str(subnumber_data[field]).strip().replace("\\n", "\n")
                elem.text = text

    # <result> 래퍼: workflow 하위 요소
    result_fields = ("workflow",)
    has_result_fields = any(subnumber_data.get(f) for f in result_fields)
    if has_result_fields:
        result_elem = ET.SubElement(sub_elem, "result")
        for field in result_fields:
            if subnumber_data.get(field):
                ET.SubElement(result_elem, field).text = str(subnumber_data[field])

    # <submit> 래퍼 내부의 첫 번째 위치에 삽입 (current는 <metadata> 내부로 이동했으므로)
    if submit_elem is not None:
        submit_elem.insert(0, sub_elem)
    else:
        root.append(sub_elem)

    # <current> 갱신
    if current_elem is not None:
        current_elem.text = str(new_id)
    elif metadata_elem is not None:
        ET.SubElement(metadata_elem, "current").text = str(new_id)
    elif submit_elem is not None:
        ET.SubElement(submit_elem, "current").text = str(new_id)
    else:
        ET.SubElement(root, "current").text = str(new_id)

    _write_ticket_xml(filepath, root)
    return new_id


def _update_subnumber(filepath: str, subnumber_id: int, updates: dict[str, Any]) -> None:
    """기존 subnumber의 필드를 갱신한다.

    <submit> 및 <history> 래퍼 내부의 subnumber를 모두 탐색한다.
    <prompt> 래퍼 내부의 하위 요소(goal, target, constraints, criteria, context)를 갱신한다.
    <result> 래퍼 내부의 하위 요소(workflow, registrykey, plan, report, workdir)를 갱신한다.

    Args:
        filepath: 티켓 파일 경로.
        subnumber_id: 갱신할 subnumber ID.
        updates: 갱신할 필드 딕셔너리.
            prompt 내부 필드: goal, target, constraints, criteria, context
            result 내부 필드: workflow, registrykey, plan, report, workdir

    Raises:
        SystemExit: 파일 읽기/쓰기 실패 또는 subnumber를 찾지 못한 경우.
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        _err(f"티켓 파일 파싱 실패 ({filepath}): {e}")

    # <submit> 및 <history> 래퍼 내부의 subnumber를 모두 탐색
    target_sub: ET.Element | None = None
    for wrapper_tag in ("submit", "history"):
        wrapper = root.find(wrapper_tag)
        if wrapper is not None:
            for sub in wrapper.findall("subnumber"):
                if sub.get("id") == str(subnumber_id):
                    target_sub = sub
                    break
        if target_sub is not None:
            break
    # 래퍼가 없는 경우 루트에서 직접 탐색 (하위 호환)
    if target_sub is None:
        for sub in root.findall("subnumber"):
            if sub.get("id") == str(subnumber_id):
                target_sub = sub
                break

    if target_sub is None:
        _err(f"subnumber id={subnumber_id}를 찾을 수 없습니다: {filepath}")

    # prompt / result 래퍼 내부 필드 분류
    prompt_inner_fields = {"goal", "target", "constraints", "criteria", "context"}
    result_inner_fields = {"workflow", "registrykey", "plan", "report", "workdir"}
    prompt_updates: dict[str, str] = {}
    result_updates: dict[str, str] = {}
    other_updates: dict[str, str] = {}

    for field, value in updates.items():
        if field in prompt_inner_fields:
            prompt_updates[field] = str(value)
        elif field in result_inner_fields:
            result_updates[field] = str(value)
        else:
            other_updates[field] = str(value)

    # <prompt> 래퍼 내부 필드 갱신
    if prompt_updates:
        prompt_elem = target_sub.find("prompt")
        if prompt_elem is None:
            prompt_elem = ET.SubElement(target_sub, "prompt")
        for field, value in prompt_updates.items():
            existing = prompt_elem.find(field)
            if existing is not None:
                existing.text = value
            else:
                ET.SubElement(prompt_elem, field).text = value

    # <result> 래퍼 내부 필드 갱신
    if result_updates:
        result_elem = target_sub.find("result")
        if result_elem is None:
            result_elem = ET.SubElement(target_sub, "result")
        for field, value in result_updates.items():
            existing = result_elem.find(field)
            if existing is not None:
                existing.text = value
            else:
                ET.SubElement(result_elem, field).text = value

    # result 래퍼 외부 필드 갱신
    for field, value in other_updates.items():
        existing = target_sub.find(field)
        if existing is not None:
            existing.text = value
        else:
            ET.SubElement(target_sub, field).text = value

    _write_ticket_xml(filepath, root)


def _update_ticket_status(filepath: str, new_status: str) -> None:
    """티켓 XML의 <status> 요소를 갱신한다.

    <metadata> 래퍼 내부의 <status> 요소를 우선 탐색한다.

    Args:
        filepath: 티켓 파일 경로.
        new_status: 새 상태 문자열 (예: 'Open', 'In Progress', 'Review', 'Done').

    Raises:
        SystemExit: 파일 읽기/쓰기 실패 시.
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        _err(f"티켓 파일 파싱 실패 ({filepath}): {e}")

    # <metadata> 래퍼 내부의 <status> 우선 탐색
    metadata_elem = root.find("metadata")
    if metadata_elem is not None:
        status_elem = metadata_elem.find("status")
        if status_elem is not None:
            status_elem.text = new_status
        else:
            ET.SubElement(metadata_elem, "status").text = new_status
    else:
        status_elem = root.find("status")
        if status_elem is not None:
            status_elem.text = new_status
        else:
            ET.SubElement(root, "status").text = new_status

    _write_ticket_xml(filepath, root)


# ─── 유틸리티 ────────────────────────────────────────────────────────────────


def _find_ticket_file(ticket_number: str) -> str | None:
    """T-NNN.xml 정확 매칭으로 티켓 파일 경로를 탐색하여 반환한다.

    탐색 순서: .kanban/active/T-NNN.xml -> .kanban/done/T-NNN.xml -> .kanban/T-NNN.xml (루트 폴백)

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).

    Returns:
        발견된 파일 절대 경로 문자열. 미발견 시 None.
    """
    active_path = os.path.join(_KANBAN_ACTIVE_DIR, f"{ticket_number}.xml")
    if os.path.isfile(active_path):
        return active_path
    done_path = os.path.join(_KANBAN_DIR, "done", f"{ticket_number}.xml")
    if os.path.isfile(done_path):
        return done_path
    # 루트 폴백: 마이그레이션 미완료 시 안전장치
    root_path = os.path.join(_KANBAN_DIR, f"{ticket_number}.xml")
    if os.path.isfile(root_path):
        return root_path
    return None


def _err(msg: str, code: int = 1) -> NoReturn:
    """에러 메시지를 stderr에 출력하고 종료한다.

    Args:
        msg: 에러 메시지
        code: 종료 코드 (기본값 1)
    """
    _log("ERROR", f"kanban.py: ERROR {msg}")
    print(f"에러: {msg}", file=sys.stderr)
    sys.exit(code)


def _normalize_ticket_number(raw: str) -> str | None:
    """티켓 번호 문자열을 'T-NNN' 형식으로 정규화한다.

    T-NNN, NNN, #N 형식을 모두 지원한다.

    Args:
        raw: 원본 티켓 번호 문자열 (예: '#1', 'T-001', '001', '1')

    Returns:
        정규화된 'T-NNN' 형식 문자열. 변환 불가능하면 None.
    """
    raw = raw.strip().lstrip("#")
    # 이미 T-NNN 형식
    if re.match(r"^T-\d+$", raw, re.IGNORECASE):
        parts = raw.split("-")
        num = int(parts[1])
        return f"T-{num:03d}"
    # 순수 숫자
    if re.match(r"^\d+$", raw):
        return f"T-{int(raw):03d}"
    return None


def _get_max_ticket_number() -> int:
    """Scan .kanban/active/ and .kanban/done/ XML filenames to find max T-NNN number.

    루트 폴백: .kanban/ 루트도 스캔하여 마이그레이션 미완료 시 채번 충돌을 방지한다.

    Returns:
        현재 최대 티켓 번호 정수. 티켓이 없으면 0.
    """
    max_num = 0
    for d in [_KANBAN_ACTIVE_DIR, os.path.join(_KANBAN_DIR, "done"), _KANBAN_DIR]:
        if not os.path.isdir(d):
            continue
        for fname in os.listdir(d):
            m = re.match(r"^T-(\d+)\.xml$", fname)
            if m:
                num = int(m.group(1))
                if num > max_num:
                    max_num = num
    return max_num


# ─── 서브커맨드 구현 ─────────────────────────────────────────────────────────


def cmd_create(title: str, command: str) -> None:
    """새 티켓 XML을 생성한다.

    XML 파일명에서 최대 T-NNN 번호를 스캔하여 +1 채번 후,
    .kanban/active/T-NNN.xml 파일을 생성한다.

    Args:
        title: 티켓 제목. 빈 문자열 허용.
        command: 워크플로우 커맨드 (implement, review, research 등). 현재 미사용 (하위 호환용).
    """
    max_num = _get_max_ticket_number()
    new_num = max_num + 1
    ticket_number = f"T-{new_num:03d}"

    # 파일명: T-NNN.xml 고정
    ticket_file = os.path.join(_KANBAN_ACTIVE_DIR, f"{ticket_number}.xml")

    os.makedirs(_KANBAN_ACTIVE_DIR, exist_ok=True)
    datetime_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    xml_content = _create_ticket_xml(ticket_number, title, datetime_str)
    try:
        with open(ticket_file, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(xml_content)
            f.write("\n")
    except OSError as e:
        _err(f"티켓 파일 생성 실패: {e}")

    suffix = f" ({command})" if command else ""
    print(f"{ticket_number}: {title}{suffix}")
    _log("INFO", f"kanban.py: create {ticket_number} title={title!r}")


def cmd_move(ticket_number: str, target_key: str, force: bool = False) -> None:
    """티켓 상태를 변경한다.

    허용 상태 전이 규칙을 검증하고, 위반 시 에러를 출력한다.
    --force 플래그가 있으면 규칙을 무시하고 강제 이동한다.

    Args:
        ticket_number: 이동할 티켓 번호 (T-NNN 형식).
        target_key: 대상 컬럼 키 (open/progress/review/done).
        force: 강제 이동 여부.

    Raises:
        SystemExit: 티켓이 없거나 전이 규칙 위반 시.
    """
    target_section = COLUMN_MAP.get(target_key)
    if target_section is None:
        _err(f"잘못된 대상 컬럼: '{target_key}'. 허용값: {', '.join(COLUMN_MAP.keys())}")

    ticket_file = _find_ticket_file(ticket_number)
    if ticket_file is None:
        _err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

    ticket_data = _parse_ticket_xml(ticket_file)
    current_section = ticket_data["status"]

    # 이미 같은 상태이면 무시
    if current_section == target_section:
        print(f"{ticket_number}은 이미 {target_section} 상태입니다.")
        return

    # 상태 전이 규칙 검증
    allowed = ALLOWED_TRANSITIONS.get(current_section, [])
    if target_section not in allowed and not force:
        _err(
            f"{ticket_number}은 현재 {current_section}이므로 {target_section}으로 이동할 수 없습니다. "
            f"--force 플래그로 강제 이동 가능"
        )

    # XML <status> 갱신
    _update_ticket_status(ticket_file, target_section)

    print(f"{ticket_number}: {current_section} → {target_section}")
    _log("INFO", f"kanban.py: move {ticket_number} {current_section} → {target_section}")


def cmd_done(ticket_number: str) -> None:
    """티켓을 Done으로 변경하고 파일을 .kanban/done/으로 이동한다.

    XML의 <status>를 Done으로 갱신하고,
    .kanban/active/T-NNN.xml를 .kanban/done/T-NNN.xml로 이동한다.

    Args:
        ticket_number: 완료할 티켓 번호 (T-NNN 형식).
    """
    ticket_file = _find_ticket_file(ticket_number)
    if ticket_file is None:
        _err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

    ticket_data = _parse_ticket_xml(ticket_file)
    current_section = ticket_data["status"]

    # active subnumber를 history로 이동 (있는 경우)
    _move_active_to_history(ticket_file)

    # XML <status> Done으로 갱신
    _update_ticket_status(ticket_file, "Done")

    # 파일을 .kanban/done/T-NNN.xml로 이동
    done_dir = os.path.join(_KANBAN_DIR, "done")
    dst_filename = f"{ticket_number}.xml"
    dst_file = os.path.join(done_dir, dst_filename)

    if os.path.isfile(ticket_file):
        os.makedirs(done_dir, exist_ok=True)
        try:
            shutil.move(ticket_file, dst_file)
        except OSError as e:
            _err(f"티켓 파일 이동 실패: {e}")
        src_rel = os.path.relpath(ticket_file, _PROJECT_ROOT)
        print(f"파일 이동: {src_rel} → .kanban/done/{dst_filename}")

    print(f"{ticket_number}: {current_section} → Done")
    _log("INFO", f"kanban.py: done {ticket_number} {current_section} → Done")


def cmd_delete(ticket_number: str) -> None:
    """티켓 XML 파일을 삭제한다.

    Done과 달리 히스토리를 보존하지 않고 파일을 삭제한다.

    Args:
        ticket_number: 삭제할 티켓 번호 (T-NNN 형식).

    Raises:
        SystemExit: 티켓을 찾을 수 없는 경우.
    """
    ticket_file = _find_ticket_file(ticket_number)
    if ticket_file is None:
        _err(f"{ticket_number} 티켓을 찾을 수 없습니다")

    try:
        os.remove(ticket_file)
    except OSError as e:
        _err(f"티켓 파일 삭제 실패: {e}")

    print(f"{ticket_number}: 삭제됨")


def cmd_update_title(ticket_number: str, title: str) -> None:
    """티켓 XML의 <title> 요소를 갱신한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).
        title: 새 제목 문자열.

    Raises:
        SystemExit: 티켓 파일을 찾을 수 없거나 쓰기 실패 시.
    """
    ticket_file = _find_ticket_file(ticket_number)
    if ticket_file is None:
        _err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

    try:
        tree = ET.parse(ticket_file)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        _err(f"티켓 파일 파싱 실패 ({ticket_file}): {e}")

    # <metadata> 래퍼 내부의 <title> 우선 탐색
    metadata_elem = root.find("metadata")
    if metadata_elem is not None:
        title_elem = metadata_elem.find("title")
        if title_elem is not None:
            title_elem.text = title
        else:
            ET.SubElement(metadata_elem, "title").text = title
    else:
        title_elem = root.find("title")
        if title_elem is not None:
            title_elem.text = title
        else:
            ET.SubElement(root, "title").text = title

    _write_ticket_xml(ticket_file, root)

    print(f"{ticket_number}: 제목 → {title}")


def cmd_set_editing(ticket_number: str, value: bool) -> None:
    """티켓 XML의 <metadata> 내부에 <editing> 요소를 생성(없으면) 또는 갱신한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).
        value: True이면 "true", False이면 "false"로 설정.

    Raises:
        SystemExit: 티켓 파일을 찾을 수 없거나 쓰기 실패 시.
    """
    ticket_file = _find_ticket_file(ticket_number)
    if ticket_file is None:
        _err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

    try:
        tree = ET.parse(ticket_file)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        _err(f"티켓 파일 파싱 실패 ({ticket_file}): {e}")

    metadata_elem = root.find("metadata")
    if metadata_elem is None:
        metadata_elem = ET.SubElement(root, "metadata")

    editing_elem = metadata_elem.find("editing")
    if editing_elem is None:
        editing_elem = ET.SubElement(metadata_elem, "editing")
    editing_elem.text = "true" if value else "false"

    _write_ticket_xml(ticket_file, root)

    flag_str = "--on" if value else "--off"
    print(f"{ticket_number}: editing → {editing_elem.text} ({flag_str})")


def cmd_add_subnumber(
    ticket_number: str,
    command: str,
    goal: str,
    target: str,
    workdir: str = "",
    result: str = "",
    constraints: str = "",
    criteria: str = "",
    context: str = "",
) -> None:
    """티켓 XML에 새 subnumber 항목을 추가한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).
        command: 워크플로우 커맨드 (implement, review, research 등).
        goal: 해당 사이클 목표.
        target: 대상.
        workdir: .workflow/ 산출물 경로 (선택).
        result: 실행 결과 요약 (선택).
        constraints: 제약사항 (선택, 프롬프트 5요소).
        criteria: 완료 기준 (선택, 프롬프트 5요소).
        context: 맥락 정보 (선택, 프롬프트 5요소).

    Raises:
        SystemExit: 티켓 파일을 찾을 수 없거나 쓰기 실패 시.
    """
    ticket_file = _find_ticket_file(ticket_number)
    if ticket_file is None:
        _err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

    subnumber_data: dict[str, Any] = {
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "command": command,
        "goal": goal.replace("\\n", "\n"),
        "target": target.replace("\\n", "\n"),
    }
    if constraints:
        subnumber_data["constraints"] = constraints.replace("\\n", "\n")
    if criteria:
        subnumber_data["criteria"] = criteria.replace("\\n", "\n")
    if context:
        subnumber_data["context"] = context.replace("\\n", "\n")
    if workdir:
        subnumber_data["workdir"] = workdir
    if result:
        subnumber_data["result"] = result

    new_id = _add_subnumber(ticket_file, subnumber_data)
    print(f"{ticket_number}: subnumber id={new_id} 추가됨")


def cmd_update_subnumber(
    ticket_number: str,
    subnumber_id: int,
    registrykey: str = "",
    plan: str = "",
    report: str = "",
    workdir: str = "",
    goal: str = "",
    target: str = "",
    constraints: str = "",
    criteria: str = "",
    context: str = "",
) -> None:
    """기존 subnumber의 prompt / result 내부 필드를 갱신한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).
        subnumber_id: 갱신할 subnumber ID.
        registrykey: 워크플로우 registryKey (YYYYMMDD-HHMMSS 형식).
        plan: plan.md 상대 경로.
        report: report.md 상대 경로.
        workdir: 워크플로우 산출물 디렉터리 상대 경로.
        goal: 작업 목표.
        target: 작업 대상.
        constraints: 제약 조건.
        criteria: 완료 기준.
        context: 추가 컨텍스트.

    Raises:
        SystemExit: 티켓 파일을 찾을 수 없거나 쓰기 실패 시.
    """
    ticket_file = _find_ticket_file(ticket_number)
    if ticket_file is None:
        _err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

    updates: dict[str, Any] = {}
    if registrykey:
        updates["registrykey"] = registrykey
    if plan:
        updates["plan"] = plan
    if report:
        updates["report"] = report
    if workdir:
        updates["workdir"] = workdir
    if goal:
        updates["goal"] = goal
    if target:
        updates["target"] = target
    if constraints:
        updates["constraints"] = constraints
    if criteria:
        updates["criteria"] = criteria
    if context:
        updates["context"] = context

    if not updates:
        _err("갱신할 필드가 없습니다.", 2)

    _update_subnumber(ticket_file, subnumber_id, updates)
    print(f"{ticket_number}: subnumber id={subnumber_id} 갱신됨")


# ─── argparse 설정 ───────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    """argparse 기반 CLI 파서를 구성하여 반환한다.

    Returns:
        구성된 ArgumentParser 인스턴스.
    """
    parser = argparse.ArgumentParser(
        prog="kanban.py",
        description="칸반 보드 상태 관리 CLI",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # create 서브커맨드
    create_parser = subparsers.add_parser("create", help="새 티켓을 생성한다")
    create_parser.add_argument("title", help="티켓 제목")
    create_parser.add_argument("--command", default="", help="워크플로우 커맨드 (implement, review, research 등)")

    # move 서브커맨드
    move_parser = subparsers.add_parser("move", help="티켓을 지정 컬럼으로 이동한다")
    move_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")
    move_parser.add_argument(
        "target",
        choices=list(COLUMN_MAP.keys()),
        help="대상 컬럼 (open/progress/review/done)",
    )
    move_parser.add_argument("--force", action="store_true", help="상태 전이 규칙 무시하고 강제 이동")

    # done 서브커맨드
    done_parser = subparsers.add_parser("done", help="티켓을 Done으로 이동하고 파일을 .kanban/done/으로 이동한다")
    done_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")

    # delete 서브커맨드
    delete_parser = subparsers.add_parser("delete", help="티켓을 삭제한다")
    delete_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")

    # add-subnumber 서브커맨드
    add_sub_parser = subparsers.add_parser("add-subnumber", help="티켓 XML에 새 subnumber 항목을 추가한다")
    add_sub_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")
    add_sub_parser.add_argument("--command", required=True, help="워크플로우 커맨드 (implement, review, research 등)")
    add_sub_parser.add_argument("--goal", required=True, help="해당 사이클 목표")
    add_sub_parser.add_argument("--target", required=True, help="대상")
    add_sub_parser.add_argument("--constraints", default="", help="제약사항 (선택, 프롬프트 5요소)")
    add_sub_parser.add_argument("--criteria", default="", help="완료 기준 (선택, 프롬프트 5요소)")
    add_sub_parser.add_argument("--context", default="", help="맥락 정보 (선택, 프롬프트 5요소)")
    add_sub_parser.add_argument("--workdir", default="", help=".workflow/ 산출물 경로 (선택)")
    add_sub_parser.add_argument("--result", default="", help="실행 결과 요약 (선택)")

    # archive-subnumber 서브커맨드
    archive_sub_parser = subparsers.add_parser("archive-subnumber", help="active subnumber를 submit에서 history로 이동한다")
    archive_sub_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")

    # set-editing 서브커맨드
    set_editing_parser = subparsers.add_parser("set-editing", help="티켓 XML의 <editing> 플래그를 설정한다")
    set_editing_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")
    set_editing_group = set_editing_parser.add_mutually_exclusive_group(required=True)
    set_editing_group.add_argument("--on", action="store_true", help="편집 중 상태로 설정")
    set_editing_group.add_argument("--off", action="store_true", help="편집 중 상태 해제")

    # update-title 서브커맨드 (update는 update-title의 alias)
    update_title_parser = subparsers.add_parser("update-title", help="티켓 제목을 갱신한다")
    update_title_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")
    update_title_parser.add_argument("title", nargs="?", default="", help="새 제목")
    update_title_parser.add_argument("--title", dest="title_flag", default="", help="새 제목 (--title 형식)")
    update_alias = subparsers.add_parser("update", help="update-title의 alias")
    update_alias.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")
    update_alias.add_argument("title", nargs="?", default="", help="새 제목")
    update_alias.add_argument("--title", dest="title_flag", default="", help="새 제목 (--title 형식)")

    # update-subnumber 서브커맨드
    update_sub_parser = subparsers.add_parser("update-subnumber", help="기존 subnumber의 prompt / result 내부 필드를 갱신한다")
    update_sub_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")
    update_sub_parser.add_argument("--id", dest="subnumber_id", required=True, type=int, help="갱신할 subnumber ID")
    update_sub_parser.add_argument("--registrykey", default="", help="워크플로우 registryKey (YYYYMMDD-HHMMSS 형식)")
    update_sub_parser.add_argument("--plan", default="", help="plan.md 상대 경로")
    update_sub_parser.add_argument("--report", default="", help="report.md 상대 경로")
    update_sub_parser.add_argument("--workdir", default="", help="워크플로우 산출물 디렉터리 상대 경로")
    update_sub_parser.add_argument("--goal", default="", help="작업 목표")
    update_sub_parser.add_argument("--target", default="", help="작업 대상")
    update_sub_parser.add_argument("--constraints", default="", help="제약 조건")
    update_sub_parser.add_argument("--criteria", default="", help="완료 기준")
    update_sub_parser.add_argument("--context", default="", help="추가 컨텍스트")

    return parser


# ─── main ────────────────────────────────────────────────────────────────────


def main() -> None:
    """CLI 진입점. 서브커맨드를 파싱하여 해당 핸들러를 호출한다."""
    parser = _build_parser()
    args = parser.parse_args()

    _log("INFO", f"kanban.py: subcommand={args.subcommand}")

    if args.subcommand == "create":
        cmd_create(args.title, args.command)

    elif args.subcommand == "move":
        ticket = _normalize_ticket_number(args.ticket)
        if ticket is None:
            _err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_move(ticket, args.target, force=args.force)

    elif args.subcommand == "done":
        ticket = _normalize_ticket_number(args.ticket)
        if ticket is None:
            _err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_done(ticket)

    elif args.subcommand == "delete":
        ticket = _normalize_ticket_number(args.ticket)
        if ticket is None:
            _err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_delete(ticket)

    elif args.subcommand == "add-subnumber":
        ticket = _normalize_ticket_number(args.ticket)
        if ticket is None:
            _err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_add_subnumber(
            ticket,
            command=args.command,
            goal=args.goal,
            target=args.target,
            workdir=args.workdir,
            result=args.result,
            constraints=args.constraints,
            criteria=args.criteria,
            context=args.context,
        )

    elif args.subcommand == "archive-subnumber":
        ticket = _normalize_ticket_number(args.ticket)
        if ticket is None:
            _err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        ticket_file = _find_ticket_file(ticket)
        if ticket_file is None:
            _err(f"{ticket} 티켓 파일을 찾을 수 없습니다")
        moved = _move_active_to_history(ticket_file)
        if moved:
            print(f"{ticket}: active subnumber를 history로 이동했습니다")
        else:
            _err(f"{ticket}: active subnumber가 없습니다")

    elif args.subcommand == "set-editing":
        ticket = _normalize_ticket_number(args.ticket)
        if ticket is None:
            _err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_set_editing(ticket, args.on)

    elif args.subcommand in ("update-title", "update"):
        ticket = _normalize_ticket_number(args.ticket)
        if ticket is None:
            _err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        title = args.title or getattr(args, "title_flag", "") or ""
        if not title:
            _err("제목을 지정해야 합니다. 예: flow-kanban update-title T-001 \"새 제목\"", 2)
        cmd_update_title(ticket, title)

    elif args.subcommand == "update-subnumber":
        ticket = _normalize_ticket_number(args.ticket)
        if ticket is None:
            _err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_update_subnumber(
            ticket,
            subnumber_id=args.subnumber_id,
            registrykey=args.registrykey,
            plan=args.plan,
            report=args.report,
            workdir=args.workdir,
            goal=args.goal,
            target=args.target,
            constraints=args.constraints,
            criteria=args.criteria,
            context=args.context,
        )


if __name__ == "__main__":
    main()
