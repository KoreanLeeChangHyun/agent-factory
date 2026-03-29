"""ticket_repository.py - 칸반 티켓 XML CRUD 및 파일 탐색 모듈.

XML 티켓 파일(.kanban/{open,progress,review,done}/T-NNN.xml)의 생성, 읽기,
갱신, 삭제를 담당하는 데이터 계층 모듈이다. kanban.py에서 분리되었으며,
순수 IO 작업만 수행한다.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, NoReturn

# ─── 경로 상수 ───────────────────────────────────────────────────────────────

_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR: str = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from common import resolve_project_root

_PROJECT_ROOT: str = resolve_project_root()
KANBAN_DIR: str = os.path.join(_PROJECT_ROOT, ".claude.workflow", "kanban")

# ─── 상태별 디렉터리 상수 ─────────────────────────────────────────────────────
KANBAN_OPEN_DIR: str = os.path.join(KANBAN_DIR, "open")
KANBAN_PROGRESS_DIR: str = os.path.join(KANBAN_DIR, "progress")
KANBAN_REVIEW_DIR: str = os.path.join(KANBAN_DIR, "review")
KANBAN_DONE_DIR: str = os.path.join(KANBAN_DIR, "done")

# 하위 호환: 기존 KANBAN_ACTIVE_DIR를 import하는 코드를 위한 deprecated alias
KANBAN_ACTIVE_DIR: str = KANBAN_OPEN_DIR

# XML <status> 값 -> 디렉터리 경로 매핑
STATUS_DIR_MAP: dict[str, str] = {
    "Open": KANBAN_OPEN_DIR,
    "Submit": KANBAN_PROGRESS_DIR,
    "In Progress": KANBAN_PROGRESS_DIR,
    "Review": KANBAN_REVIEW_DIR,
    "Done": KANBAN_DONE_DIR,
}


# ─── 로깅 헬퍼 ───────────────────────────────────────────────────────────────

def resolve_work_dir_for_logging() -> str | None:
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
        workflow_base = os.path.join(_PROJECT_ROOT, ".claude.workflow", "workflow")
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


def log(level: str, message: str) -> None:
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
        abs_work_dir = resolve_work_dir_for_logging()
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


# ─── 에러 헬퍼 ───────────────────────────────────────────────────────────────

def err(msg: str, code: int = 1) -> NoReturn:
    """에러 메시지를 stderr에 출력하고 종료한다.

    Args:
        msg: 에러 메시지
        code: 종료 코드 (기본값 1)
    """
    log("ERROR", f"kanban.py: ERROR {msg}")
    print(f"에러: {msg}", file=sys.stderr)
    sys.exit(code)


# ─── XML 헬퍼 ────────────────────────────────────────────────────────────────


def create_ticket_xml(ticket_number: str, title: str = "", datetime_str: str = "", command: str = "") -> str:
    """티켓 XML 문자열을 생성하여 반환한다.

    XML은 <metadata>, <prompt>, <result> 요소로 구성되는 flat 구조이다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).
        title: 티켓 제목. 빈 문자열 허용.
        datetime_str: 생성 일시 문자열 (YYYY-MM-DD HH:MM:SS 형식). 빈 문자열이면 현재 시간 사용.
        command: 실행 커맨드 (implement, research 등). 빈 문자열 허용.

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
    if command:
        ET.SubElement(metadata_elem, "command").text = command
    # <prompt /> self-closing 요소
    ET.SubElement(root, "prompt")
    # <result /> self-closing 요소
    ET.SubElement(root, "result")
    ET.indent(root, space="  ")
    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=False)
    # 섹션 주석 삽입: <metadata>, <prompt>, <result> 태그 직전에 주석 추가
    # self-closing 태그(<prompt />, <result />) 및 일반 태그(<prompt>, <result>) 모두 처리
    xml_str = re.sub(r"(<metadata[ />])", r"<!-- metadata -->\n  \1", xml_str)
    xml_str = re.sub(r"(<prompt[ />])", r"\n  <!-- prompt -->\n  \1", xml_str)
    xml_str = re.sub(r"(<result[ />])", r"\n  <!-- result -->\n  \1", xml_str)
    return xml_str


def write_ticket_xml(filepath: str, root: ET.Element) -> None:
    """XML Element를 파일에 저장한다.

    <metadata>, <prompt>, <result> flat 구조를 유지하고,
    prompt 내부 필드 텍스트를 가독성 있게 래핑한다.

    Args:
        filepath: 저장할 파일 경로.
        root: 저장할 XML 루트 Element.
    """
    ET.indent(root, space="  ")
    xml_str = ET.tostring(root, encoding="unicode")
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
        # 각 줄의 기존 공백을 strip 후 빈 줄 제거, 재인덴트 (ET.indent 중첩 방지)
        lines = content.split("\n")
        lines = [line.strip() for line in lines if line.strip()]
        indented_content = f"\n{inner_indent}".join(lines)
        return f"{indent}<{tag}>\n{inner_indent}{indented_content}\n{indent}</{tag}>"

    xml_str = re.sub(
        r"( *)<(goal|target|constraints|criteria|context)>(.+)</\2>",
        _wrap_prompt_field,
        xml_str,
        flags=re.DOTALL,
    )
    # 섹션 주석 삽입: <metadata>, <relations>, <prompt>, <result> 태그 직전에 주석 추가 (없는 경우에만)
    # self-closing 태그(<prompt />, <result />) 및 일반 태그(<prompt>, <result>) 모두 처리
    if "<!-- metadata -->" not in xml_str:
        xml_str = re.sub(r"(<metadata[ />])", r"<!-- metadata -->\n  \1", xml_str)
    if "<!-- relations -->" not in xml_str and "<relations" in xml_str:
        xml_str = re.sub(r"(<relations[ />])", r"\n  <!-- relations -->\n  \1", xml_str)
    if "<!-- prompt -->" not in xml_str:
        xml_str = re.sub(r"(<prompt[ />])", r"\n  <!-- prompt -->\n  \1", xml_str)
    if "<!-- result -->" not in xml_str:
        xml_str = re.sub(r"(<result[ />])", r"\n  <!-- result -->\n  \1", xml_str)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(xml_str)
        f.write("\n")


def parse_ticket_xml(filepath: str) -> dict[str, Any]:
    """티켓 XML 파일을 파싱하여 딕셔너리로 반환한다.

    flat 구조(<metadata>, <prompt>, <result>)를 기본으로 파싱한다.
    done 디렉터리의 레거시 티켓(<submit>/<subnumber> 또는 <history>/<subnumber> 구조)은 폴백 로직으로 처리한다.

    Args:
        filepath: 파싱할 티켓 파일 경로.

    Returns:
        파싱된 티켓 정보 딕셔너리:
            - number (str): 티켓 번호
            - status (str): 현재 상태
            - title (str): 티켓 제목
            - command (str): 실행 커맨드
            - prompt (dict): goal, target, constraints, criteria, context
            - result (dict | None): registrykey, workdir, plan, report (미실행 시 None)
            - relations (list[dict]): 관계 목록

    Raises:
        SystemExit: 파일 읽기 실패 또는 XML 파싱 오류 시.
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"티켓 파일 파싱 실패 ({filepath}): {e}")

    def _text(elem: ET.Element, tag: str, default: str = "") -> str:
        """자식 Element의 텍스트를 반환하는 헬퍼."""
        child = elem.find(tag)
        return child.text.strip() if child is not None and child.text else default

    # <metadata> 래퍼에서 number/title/datetime/status/command 파싱
    metadata_elem = root.find("metadata")

    if metadata_elem is not None:
        number = _text(metadata_elem, "number")
        status = _text(metadata_elem, "status")
        title = _text(metadata_elem, "title")
        command = _text(metadata_elem, "command")
    else:
        number = _text(root, "number")
        status = _text(root, "status")
        title = _text(root, "title")
        command = _text(root, "command")

    # done 디렉터리 레거시 폴백: <submit>/<subnumber> 또는 <history>/<subnumber> 구조가 감지되면 기존 로직으로 파싱
    submit_elem = root.find("submit")
    history_elem = root.find("history")
    has_legacy_structure = (
        (submit_elem is not None and submit_elem.find("subnumber") is not None) or
        (history_elem is not None and history_elem.find("subnumber") is not None)
    )
    if has_legacy_structure:
        return _parse_legacy_ticket(filepath, root, number, status, title, _text)

    # flat 구조: <prompt> 루트 직하에서 5요소 파싱
    prompt_fields = ("goal", "target", "constraints", "criteria", "context")
    prompt_data: dict[str, str] = {}
    prompt_elem = root.find("prompt")
    if prompt_elem is not None:
        for field in prompt_fields:
            prompt_data[field] = _text(prompt_elem, field)
    else:
        for field in prompt_fields:
            prompt_data[field] = ""

    # flat 구조: <result> 루트 직하에서 하위 요소 파싱
    result_fields = ("registrykey", "workdir", "plan", "report")
    result_data: dict[str, str] | None = None
    result_elem = root.find("result")
    if result_elem is not None and len(result_elem) > 0:
        result_data = {}
        for field in result_fields:
            result_data[field] = _text(result_elem, field)

    # <relations> 요소 파싱 (하위 호환: 없으면 빈 리스트)
    relations = _parse_relations(root)

    return {
        "number": number,
        "status": status,
        "title": title,
        "command": command,
        "prompt": prompt_data,
        "result": result_data,
        "relations": relations,
    }


def _parse_relations(root: ET.Element) -> list[dict[str, str]]:
    """<relations> 요소를 파싱하여 관계 리스트를 반환한다."""
    relations: list[dict[str, str]] = []
    relations_elem = root.find("relations")
    if relations_elem is not None:
        for rel in relations_elem.findall("relation"):
            rel_type = rel.get("type", "")
            rel_ticket = rel.get("ticket", "")
            if rel_type and rel_ticket:
                relations.append({"type": rel_type, "ticket": rel_ticket})
    return relations


def _parse_legacy_ticket(
    filepath: str,
    root: ET.Element,
    number: str,
    status: str,
    title: str,
    _text: Any,
) -> dict[str, Any]:
    """레거시 <submit>/<subnumber> 구조를 파싱하여 새 flat 형식으로 반환한다.

    done 디렉터리의 기존 티켓과의 하위 호환을 위해 사용된다.
    """
    submit_elem = root.find("submit")
    history_elem = root.find("history")

    # command와 prompt는 가장 최근(가장 큰 id) subnumber에서 추출
    all_subs: list[ET.Element] = []
    if submit_elem is not None:
        all_subs.extend(submit_elem.findall("subnumber"))
    if history_elem is not None:
        all_subs.extend(history_elem.findall("subnumber"))
    if not all_subs:
        all_subs.extend(root.findall("subnumber"))

    # ID 기준 내림차순 정렬하여 최근 subnumber 우선
    all_subs.sort(key=lambda s: int(s.get("id", "0")) if s.get("id", "0").isdigit() else 0, reverse=True)

    command = ""
    prompt_data: dict[str, str] = {"goal": "", "target": "", "constraints": "", "criteria": "", "context": ""}
    result_data: dict[str, str] | None = None

    if all_subs:
        latest = all_subs[0]
        # command: subnumber 직하
        cmd_elem = latest.find("command")
        if cmd_elem is not None and cmd_elem.text:
            command = cmd_elem.text.strip()

        # prompt: subnumber 내부 <prompt> 래퍼
        prompt_elem = latest.find("prompt")
        if prompt_elem is not None:
            for field in ("goal", "target", "constraints", "criteria", "context"):
                child = prompt_elem.find(field)
                if child is not None and child.text:
                    prompt_data[field] = child.text.strip()

        # result: subnumber 내부 <result> 래퍼
        result_elem = latest.find("result")
        if result_elem is not None and len(result_elem) > 0:
            result_data = {}
            for result_child in result_elem:
                text = result_child.text.strip() if result_child.text else ""
                result_data[result_child.tag] = text

    # <relations> 요소 파싱
    relations = _parse_relations(root)

    return {
        "number": number,
        "status": status,
        "title": title,
        "command": command,
        "prompt": prompt_data,
        "result": result_data,
        "relations": relations,
    }


# ─── prompt/result 갱신 ──────────────────────────────────────────────────────


def update_prompt(filepath: str, updates: dict[str, str]) -> None:
    """티켓 XML의 <prompt> 하위 요소와 <metadata>/<command>를 갱신한다.

    self-closing <prompt /> 태그를 내용 있는 <prompt> 태그로 자동 변환한다.

    Args:
        filepath: 티켓 파일 경로.
        updates: 갱신할 필드 딕셔너리.
            - command: <metadata>/<command> 갱신
            - goal, target, constraints, criteria, context: <prompt> 하위 요소 갱신
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"티켓 파일 파싱 실패 ({filepath}): {e}")

    # <metadata>/<command> 갱신
    if "command" in updates:
        metadata_elem = root.find("metadata")
        if metadata_elem is not None:
            cmd_elem = metadata_elem.find("command")
            if cmd_elem is not None:
                cmd_elem.text = updates["command"]
            else:
                ET.SubElement(metadata_elem, "command").text = updates["command"]

    # <prompt> 하위 요소 갱신
    prompt_fields = ("goal", "target", "constraints", "criteria", "context")
    prompt_updates = {k: v for k, v in updates.items() if k in prompt_fields}

    if prompt_updates:
        prompt_elem = root.find("prompt")
        if prompt_elem is None:
            # <prompt> 요소가 없으면 생성 (metadata 뒤에 삽입)
            prompt_elem = ET.Element("prompt")
            insert_idx = 0
            for i, child in enumerate(root):
                if child.tag in ("metadata", "relations"):
                    insert_idx = i + 1
            root.insert(insert_idx, prompt_elem)

        for field, value in prompt_updates.items():
            # \\n 리터럴을 실제 개행으로 변환
            text = str(value).strip().replace("\\n", "\n")
            existing = prompt_elem.find(field)
            if existing is not None:
                existing.text = text
            else:
                ET.SubElement(prompt_elem, field).text = text

    write_ticket_xml(filepath, root)


def update_result(filepath: str, updates: dict[str, str]) -> None:
    """티켓 XML의 <result> 하위 요소를 갱신한다.

    self-closing <result /> 태그를 내용 있는 <result> 태그로 자동 변환한다.

    Args:
        filepath: 티켓 파일 경로.
        updates: 갱신할 필드 딕셔너리.
            - registrykey, workdir, plan, report: <result> 하위 요소 갱신
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"티켓 파일 파싱 실패 ({filepath}): {e}")

    result_fields = ("registrykey", "workdir", "plan", "report")
    result_updates = {k: v for k, v in updates.items() if k in result_fields}

    if result_updates:
        result_elem = root.find("result")
        if result_elem is None:
            # <result> 요소가 없으면 생성 (루트 마지막에 추가)
            result_elem = ET.SubElement(root, "result")

        for field, value in result_updates.items():
            existing = result_elem.find(field)
            if existing is not None:
                existing.text = str(value)
            else:
                ET.SubElement(result_elem, field).text = str(value)

    write_ticket_xml(filepath, root)


# ─── relations 관련 ─────────────────────────────────────────────────────────


def add_relation(filepath: str, relation_type: str, target_ticket: str) -> None:
    """티켓 XML에 관계(relation) 요소를 추가한다.

    <relations> 요소가 없으면 <metadata> 뒤, <prompt> 앞에 새로 생성한다.
    동일한 type+ticket 조합이 이미 존재하면 중복 추가하지 않는다.

    Args:
        filepath: 티켓 파일 경로.
        relation_type: 관계 유형 (depends-on, derived-from, blocks).
        target_ticket: 대상 티켓 번호 (T-NNN 형식).
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"티켓 파일 파싱 실패 ({filepath}): {e}")

    relations_elem = root.find("relations")

    # 중복 검사
    if relations_elem is not None:
        for rel in relations_elem.findall("relation"):
            if rel.get("type") == relation_type and rel.get("ticket") == target_ticket:
                return  # 이미 존재하면 스킵

    # <relations> 요소가 없으면 생성
    if relations_elem is None:
        relations_elem = ET.Element("relations")
        # <metadata> 뒤, <prompt> 앞에 삽입
        insert_idx = 0
        for i, child in enumerate(root):
            if child.tag == "metadata":
                insert_idx = i + 1
                break
        root.insert(insert_idx, relations_elem)

    # <relation type="..." ticket="..."/> 추가
    rel_elem = ET.SubElement(relations_elem, "relation")
    rel_elem.set("type", relation_type)
    rel_elem.set("ticket", target_ticket)

    write_ticket_xml(filepath, root)


def remove_relation(filepath: str, relation_type: str, target_ticket: str) -> None:
    """티켓 XML에서 관계(relation) 요소를 제거한다.

    해당 type+ticket 조합의 relation 요소를 제거하고,
    <relations>가 비면 요소 자체도 제거한다.

    Args:
        filepath: 티켓 파일 경로.
        relation_type: 관계 유형 (depends-on, derived-from, blocks).
        target_ticket: 대상 티켓 번호 (T-NNN 형식).
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"티켓 파일 파싱 실패 ({filepath}): {e}")

    relations_elem = root.find("relations")
    if relations_elem is None:
        return  # relations 요소가 없으면 무시

    # 매칭되는 relation 제거
    for rel in relations_elem.findall("relation"):
        if rel.get("type") == relation_type and rel.get("ticket") == target_ticket:
            relations_elem.remove(rel)

    # <relations>가 비면 요소 자체 제거
    if len(relations_elem) == 0:
        root.remove(relations_elem)

    write_ticket_xml(filepath, root)


# ─── 유틸리티 ────────────────────────────────────────────────────────────────


def find_ticket_file(ticket_number: str) -> str | None:
    """T-NNN.xml 정확 매칭으로 티켓 파일 경로를 탐색하여 반환한다.

    탐색 순서: open/ -> progress/ -> review/ -> done/ -> active/(폴백) -> kanban/(루트 폴백)

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).

    Returns:
        발견된 파일 절대 경로 문자열. 미발견 시 None.
    """
    filename = f"{ticket_number}.xml"
    # 상태별 디렉터리 순회
    for status_dir in [KANBAN_OPEN_DIR, KANBAN_PROGRESS_DIR, KANBAN_REVIEW_DIR, KANBAN_DONE_DIR]:
        candidate = os.path.join(status_dir, filename)
        if os.path.isfile(candidate):
            return candidate
    # 폴백: 마이그레이션 미완료 시 active/ 또는 kanban/ 루트
    active_path = os.path.join(KANBAN_DIR, "active", filename)
    if os.path.isfile(active_path):
        return active_path
    root_path = os.path.join(KANBAN_DIR, filename)
    if os.path.isfile(root_path):
        return root_path
    return None


def normalize_ticket_number(raw: str) -> str | None:
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


def extract_report_summary(report_path: str) -> str:
    """report.md에서 핵심 섹션을 추출하여 요약 문자열을 반환한다.

    "## 최종 판정" 또는 "## 판정" 섹션과 "## 이슈" 또는 "## 발견 사항" 섹션을 추출한다.
    위 섹션이 없으면 report.md 첫 50줄을 fallback으로 사용한다.
    토큰 절감을 위해 최대 2000자로 제한한다.

    Args:
        report_path: report.md 파일 절대 경로.

    Returns:
        추출된 요약 문자열. 파일 읽기 실패 시 빈 문자열.
    """
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return ""

    if not content.strip():
        return ""

    lines = content.split("\n")

    # 섹션 추출 헬퍼: ## 헤더 시작부터 다음 ## 헤더 직전까지
    def _extract_section(header_patterns: list[str]) -> str:
        for pattern in header_patterns:
            for i, line in enumerate(lines):
                if line.strip().lower().startswith(f"## {pattern.lower()}"):
                    section_lines = [lines[i]]
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip().startswith("## "):
                            break
                        section_lines.append(lines[j])
                    return "\n".join(section_lines).strip()
        return ""

    verdict = _extract_section(["최종 판정", "판정"])
    issues = _extract_section(["이슈", "발견 사항"])

    summary_parts = [p for p in [verdict, issues] if p]

    if summary_parts:
        summary = "\n\n".join(summary_parts)
    else:
        # fallback: 첫 50줄
        summary = "\n".join(lines[:50]).strip()

    # 2000자 제한
    if len(summary) > 2000:
        summary = summary[:2000] + "..."

    return summary


def get_predecessor_reports(ticket_number: str) -> list[dict[str, str]]:
    """선행 티켓의 report 요약을 추출하여 반환한다.

    티켓 XML에서 depends-on 및 derived-from 관계를 찾고,
    각 선행 티켓이 Done 상태이고 report 파일이 존재하면 요약을 추출한다.

    Args:
        ticket_number: 현재 티켓 번호 (T-NNN 형식).

    Returns:
        선행 티켓 report 정보 리스트. 각 항목은
        {"ticket": "T-NNN", "type": "depends-on", "summary": "..."} 형태.
        선행 티켓이 없거나 조건 미충족 시 빈 리스트.
    """
    ticket_file = find_ticket_file(ticket_number)
    if not ticket_file:
        return []

    try:
        ticket_data = parse_ticket_xml(ticket_file)
    except SystemExit:
        return []

    relations = ticket_data.get("relations", [])
    predecessor_types = {"depends-on", "derived-from"}
    results: list[dict[str, str]] = []

    for rel in relations:
        rel_type = rel.get("type", "")
        rel_ticket = rel.get("ticket", "")
        if rel_type not in predecessor_types or not rel_ticket:
            continue

        # 선행 티켓 파일 찾기
        pred_file = find_ticket_file(rel_ticket)
        if not pred_file:
            continue

        try:
            pred_data = parse_ticket_xml(pred_file)
        except SystemExit:
            continue

        # Done이 아니면 스킵
        if pred_data.get("status", "") != "Done":
            continue

        # result dict에서 report 경로 직접 추출
        report_path_str = ""
        result = pred_data.get("result")
        if isinstance(result, dict) and result.get("report"):
            report_path_str = result["report"]

        if not report_path_str:
            continue

        # 상대 경로를 절대 경로로 변환
        abs_report_path = os.path.join(_PROJECT_ROOT, report_path_str)
        if not os.path.isfile(abs_report_path):
            continue

        summary = extract_report_summary(abs_report_path)
        if summary:
            results.append({
                "ticket": rel_ticket,
                "type": rel_type,
                "summary": summary,
            })

    return results


def get_max_ticket_number() -> int:
    """Scan .kanban/{open,progress,review,done}/ XML filenames to find max T-NNN number.

    루트 폴백: .kanban/ 루트도 스캔하여 마이그레이션 미완료 시 채번 충돌을 방지한다.

    Returns:
        현재 최대 티켓 번호 정수. 티켓이 없으면 0.
    """
    max_num = 0
    for d in [KANBAN_OPEN_DIR, KANBAN_PROGRESS_DIR, KANBAN_REVIEW_DIR, KANBAN_DONE_DIR, KANBAN_DIR]:
        if not os.path.isdir(d):
            continue
        for fname in os.listdir(d):
            m = re.match(r"^T-(\d+)\.xml$", fname)
            if m:
                num = int(m.group(1))
                if num > max_num:
                    max_num = num
    return max_num


def move_ticket_to_status_dir(filepath: str, target_status: str) -> str:
    """티켓 파일을 대상 상태에 해당하는 디렉터리로 이동한다.

    STATUS_DIR_MAP에서 대상 디렉터리를 조회하고, 현재 파일이 이미 해당
    디렉터리에 있으면 이동을 스킵한다 (Submit <-> In Progress 전이 시).

    Args:
        filepath: 이동할 티켓 파일의 절대 경로.
        target_status: 대상 상태 문자열 (Open, Submit, In Progress, Review, Done).

    Returns:
        이동 후 새 파일 경로. 스킵된 경우 원래 경로 반환.

    Raises:
        ValueError: STATUS_DIR_MAP에 없는 상태 문자열인 경우.
        OSError: 파일 이동 실패 시.
    """
    target_dir = STATUS_DIR_MAP.get(target_status)
    if target_dir is None:
        raise ValueError(f"알 수 없는 상태: '{target_status}'. 허용값: {', '.join(STATUS_DIR_MAP.keys())}")

    current_dir = os.path.dirname(filepath)
    if os.path.normpath(current_dir) == os.path.normpath(target_dir):
        # 같은 디렉터리 — 이동 불필요 (Submit <-> In Progress 등)
        return filepath

    os.makedirs(target_dir, exist_ok=True)
    filename = os.path.basename(filepath)
    new_path = os.path.join(target_dir, filename)
    shutil.move(filepath, new_path)
    return new_path
