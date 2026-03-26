"""ticket_repository.py - 칸반 티켓 XML CRUD 및 파일 탐색 모듈.

XML 티켓 파일(.kanban/active/T-NNN.xml)의 생성, 읽기, 갱신, 삭제를
담당하는 데이터 계층 모듈이다. kanban.py에서 분리되었으며, 순수 IO 작업만
수행한다.
"""

from __future__ import annotations

import os
import re
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
KANBAN_ACTIVE_DIR: str = os.path.join(KANBAN_DIR, "active")


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


def create_ticket_xml(ticket_number: str, title: str = "", datetime_str: str = "") -> str:
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


def write_ticket_xml(filepath: str, root: ET.Element) -> None:
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
    if "<!-- relations -->" not in xml_str and "<relations" in xml_str:
        xml_str = re.sub(r"(<relations[ />])", r"\n  <!-- relations -->\n  \1", xml_str)
    if "<!-- history -->" not in xml_str:
        xml_str = re.sub(r"(<history[ />])", r"\n  <!-- history -->\n  \1", xml_str)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(xml_str)
        f.write("\n")


def parse_ticket_xml(filepath: str) -> dict[str, Any]:
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
        err(f"티켓 파일 파싱 실패 ({filepath}): {e}")

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

    # <relations> 요소 파싱 (하위 호환: 없으면 빈 리스트)
    relations: list[dict[str, str]] = []
    relations_elem = root.find("relations")
    if relations_elem is not None:
        for rel in relations_elem.findall("relation"):
            rel_type = rel.get("type", "")
            rel_ticket = rel.get("ticket", "")
            if rel_type and rel_ticket:
                relations.append({"type": rel_type, "ticket": rel_ticket})

    return {
        "number": number,
        "status": status,
        "current": current,
        "title": title,
        "editing": editing,
        "subnumbers": subnumbers,
        "relations": relations,
    }


# ─── 히스토리 관련 ────────────────────────────────────────────────────────────


def find_history_element(root: ET.Element) -> ET.Element | None:
    """<history> 래퍼 요소를 찾아 반환한다.

    Args:
        root: XML 루트 Element.

    Returns:
        <history> 래퍼 Element. 없으면 None.
    """
    return root.find("history")


def move_active_to_history(filepath: str) -> bool:
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

    write_ticket_xml(filepath, root)
    return True


# ─── subnumber 관련 ──────────────────────────────────────────────────────────


def add_subnumber(filepath: str, subnumber_data: dict[str, Any]) -> int:
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
        err(f"티켓 파일 파싱 실패 ({filepath}): {e}")

    metadata_elem = root.find("metadata")
    submit_elem = root.find("submit")
    history_elem = find_history_element(root)

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

    write_ticket_xml(filepath, root)
    return new_id


def rollback_subnumber(filepath: str, subnumber_id: int) -> None:
    """add_subnumber()의 역연산: 지정 subnumber를 제거하고 current를 복원한다.

    <submit> 내에서 subnumber_id를 가진 <subnumber> 요소를 제거하고,
    <current>를 subnumber_id - 1로 복원한다.
    직전 subnumber(id == subnumber_id - 1)가 <history>에 존재하면
    <submit>으로 이동하고 active="true"를 복원한다.

    Args:
        filepath: 티켓 파일 경로.
        subnumber_id: 롤백할 subnumber ID.

    Raises:
        SystemExit: 파일 읽기/쓰기 실패 또는 subnumber를 찾지 못한 경우.
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"티켓 파일 파싱 실패 ({filepath}): {e}")

    metadata_elem = root.find("metadata")
    submit_elem = root.find("submit")
    history_elem = find_history_element(root)

    # <submit> 내에서 대상 subnumber 탐색
    target_sub: ET.Element | None = None
    if submit_elem is not None:
        for sub in submit_elem.findall("subnumber"):
            if sub.get("id") == str(subnumber_id):
                target_sub = sub
                break

    if target_sub is None:
        err(f"subnumber id={subnumber_id}를 <submit>에서 찾을 수 없습니다: {filepath}")

    # 대상 subnumber 제거
    if submit_elem is not None:
        submit_elem.remove(target_sub)

    # <current> 값을 subnumber_id - 1로 복원
    prev_id = subnumber_id - 1
    if metadata_elem is not None and metadata_elem.find("current") is not None:
        current_elem = metadata_elem.find("current")
    elif submit_elem is not None and submit_elem.find("current") is not None:
        current_elem = submit_elem.find("current")
    else:
        current_elem = root.find("current")

    if current_elem is not None:
        current_elem.text = str(prev_id)

    # 직전 subnumber(id == prev_id)가 <history>에 존재하면 <submit>으로 복원
    if prev_id >= 1 and history_elem is not None:
        prev_sub: ET.Element | None = None
        for sub in history_elem.findall("subnumber"):
            if sub.get("id") == str(prev_id):
                prev_sub = sub
                break

        if prev_sub is not None and prev_sub.get("active") != "true":
            history_elem.remove(prev_sub)
            prev_sub.set("active", "true")
            if submit_elem is not None:
                submit_elem.insert(0, prev_sub)
            else:
                root.append(prev_sub)

    write_ticket_xml(filepath, root)


def update_subnumber(filepath: str, subnumber_id: int, updates: dict[str, Any]) -> None:
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
        err(f"티켓 파일 파싱 실패 ({filepath}): {e}")

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
        err(f"subnumber id={subnumber_id}를 찾을 수 없습니다: {filepath}")

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

    write_ticket_xml(filepath, root)


# ─── relations 관련 ─────────────────────────────────────────────────────────


def add_relation(filepath: str, relation_type: str, target_ticket: str) -> None:
    """티켓 XML에 관계(relation) 요소를 추가한다.

    <relations> 요소가 없으면 <metadata> 뒤, <submit> 앞에 새로 생성한다.
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
        # <metadata> 뒤, <submit> 앞에 삽입
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

    탐색 순서: .kanban/active/T-NNN.xml -> .kanban/done/T-NNN.xml -> .kanban/T-NNN.xml (루트 폴백)

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).

    Returns:
        발견된 파일 절대 경로 문자열. 미발견 시 None.
    """
    active_path = os.path.join(KANBAN_ACTIVE_DIR, f"{ticket_number}.xml")
    if os.path.isfile(active_path):
        return active_path
    done_path = os.path.join(KANBAN_DIR, "done", f"{ticket_number}.xml")
    if os.path.isfile(done_path):
        return done_path
    # 루트 폴백: 마이그레이션 미완료 시 안전장치
    root_path = os.path.join(KANBAN_DIR, f"{ticket_number}.xml")
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

        # subnumber의 result에서 report 경로 추출 (가장 최근 subnumber 우선)
        report_path_str = ""
        for sub in reversed(pred_data.get("subnumbers", [])):
            result = sub.get("result")
            if isinstance(result, dict) and result.get("report"):
                report_path_str = result["report"]
                break

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
    """Scan .kanban/active/ and .kanban/done/ XML filenames to find max T-NNN number.

    루트 폴백: .kanban/ 루트도 스캔하여 마이그레이션 미완료 시 채번 충돌을 방지한다.

    Returns:
        현재 최대 티켓 번호 정수. 티켓이 없으면 0.
    """
    max_num = 0
    for d in [KANBAN_ACTIVE_DIR, os.path.join(KANBAN_DIR, "done"), KANBAN_DIR]:
        if not os.path.isdir(d):
            continue
        for fname in os.listdir(d):
            m = re.match(r"^T-(\d+)\.xml$", fname)
            if m:
                num = int(m.group(1))
                if num > max_num:
                    max_num = num
    return max_num
