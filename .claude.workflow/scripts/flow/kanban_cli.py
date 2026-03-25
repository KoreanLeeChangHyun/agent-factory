"""kanban_cli.py - 칸반 보드 서브커맨드 구현 및 CLI 파서 모듈.

서브커맨드별 비즈니스 로직(cmd_* 함수), argparse 파서 구성(build_parser),
서브커맨드 디스패치(dispatch)를 담당하는 비즈니스 계층 모듈이다.
kanban.py에서 분리되었으며, ticket_repository.py와 ticket_state.py에 의존한다.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

from flow.ticket_repository import (
    add_relation,
    create_ticket_xml,
    find_ticket_file,
    normalize_ticket_number,
    get_max_ticket_number,
    add_subnumber,
    rollback_subnumber,
    update_subnumber,
    move_active_to_history,
    remove_relation,
    write_ticket_xml,
    parse_ticket_xml,
    err,
    log,
    KANBAN_DIR,
    KANBAN_ACTIVE_DIR,
)
from flow.ticket_state import (
    COLUMN_MAP,
    update_ticket_status,
    validate_transition,
)
from flow.prompt_validator import validate as prompt_validate, extract_active_prompt
from data.constants import QUALITY_THRESHOLD


# ─── 경로 상수 ───────────────────────────────────────────────────────────────

_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT: str = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))


# ─── tmux 헬퍼 ───────────────────────────────────────────────────────────────

_TMUX_WINDOW_PREFIX: str = "P:"


def _tmux_kill_ticket_window(ticket_number: str) -> None:
    """tmux 세션에서 해당 티켓의 P:T-NNN 윈도우를 종료한다.

    비tmux 환경($TMUX 미설정) 또는 윈도우 미존재 시 조용히 건너뛴다.
    상태 전이 성공 후에만 호출되어야 한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식). 윈도우명 P:T-NNN으로 변환됨.
    """
    # 비tmux 환경 방어: $TMUX 환경변수 미설정 시 건너뜀
    if not os.environ.get("TMUX"):
        return

    window_name = f"{_TMUX_WINDOW_PREFIX}{ticket_number}"

    try:
        # 윈도우 존재 여부 확인
        list_result = subprocess.run(
            ["tmux", "list-windows", "-F", "#W"],
            capture_output=True,
            text=True,
        )
        if list_result.returncode != 0:
            return
        existing_windows = list_result.stdout.strip().splitlines()
        if window_name not in existing_windows:
            return

        # 윈도우 인덱스 조회 (P:T-NNN의 콜론이 세션:윈도우로 오해석되는 문제 방지)
        idx_result = subprocess.run(
            ["tmux", "list-windows", "-F", "#{window_index}\t#{window_name}"],
            capture_output=True,
            text=True,
        )
        target = window_name  # 폴백
        if idx_result.returncode == 0:
            for line in idx_result.stdout.strip().splitlines():
                parts = line.split("\t", 1)
                if len(parts) == 2 and parts[1] == window_name:
                    target = parts[0]
                    break

        subprocess.run(
            ["tmux", "kill-window", "-t", target],
            capture_output=True,
        )
        log("INFO", f"kanban.py: tmux kill-window {window_name}")
    except Exception:
        # tmux 오류는 상태 전이와 무관하므로 무시
        pass


# ─── 서브커맨드 구현 ─────────────────────────────────────────────────────────


def cmd_create(title: str, command: str) -> None:
    """새 티켓 XML을 생성한다.

    XML 파일명에서 최대 T-NNN 번호를 스캔하여 +1 채번 후,
    .kanban/active/T-NNN.xml 파일을 생성한다.

    Args:
        title: 티켓 제목. 빈 문자열 허용.
        command: 워크플로우 커맨드 (implement, review, research 등). 현재 미사용 (하위 호환용).
    """
    max_num = get_max_ticket_number()
    new_num = max_num + 1
    ticket_number = f"T-{new_num:03d}"

    # 파일명: T-NNN.xml 고정
    ticket_file = os.path.join(KANBAN_ACTIVE_DIR, f"{ticket_number}.xml")

    os.makedirs(KANBAN_ACTIVE_DIR, exist_ok=True)
    datetime_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    xml_content = create_ticket_xml(ticket_number, title, datetime_str)
    try:
        with open(ticket_file, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(xml_content)
            f.write("\n")
    except OSError as e:
        err(f"티켓 파일 생성 실패: {e}")

    suffix = f" ({command})" if command else ""
    print(f"{ticket_number}: {title}{suffix}")
    log("INFO", f"kanban.py: create {ticket_number} title={title!r}")


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
        err(f"잘못된 대상 컬럼: '{target_key}'. 허용값: {', '.join(COLUMN_MAP.keys())}")

    ticket_file = find_ticket_file(ticket_number)
    if ticket_file is None:
        err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

    ticket_data = parse_ticket_xml(ticket_file)
    current_section = ticket_data["status"]

    # 상태 전이 규칙 검증 (validate_transition 사용)
    validation_error = validate_transition(current_section, target_section, force)
    if validation_error is not None:
        if validation_error == "":
            # 이미 같은 상태
            print(f"{ticket_number}은 이미 {target_section} 상태입니다.")
            return
        err(
            f"{ticket_number}은 {validation_error}"
        )

    # XML <status> 갱신
    update_ticket_status(ticket_file, target_section)

    print(f"{ticket_number}: {current_section} → {target_section}")
    log("INFO", f"kanban.py: move {ticket_number} {current_section} → {target_section}")

    # Open 전이 시 tmux 윈도우 자동 kill:
    # Submit 또는 In Progress에서 Open으로 복귀하면 해당 티켓의 P:T-NNN 윈도우를 종료한다.
    # 상태 전이 성공 후에 실행하므로 전이 실패 시(err() 호출 후 SystemExit) 여기에 도달하지 않는다.
    if target_section == "Open" and current_section in ("Submit", "In Progress"):
        _tmux_kill_ticket_window(ticket_number)


def cmd_done(ticket_number: str) -> None:
    """티켓을 Done으로 변경하고 파일을 .kanban/done/으로 이동한다.

    worktree가 활성화된 경우, 상태 변경/파일 이동 전에 feature 브랜치를
    develop에 병합한다. 병합 충돌 시 Done 전이를 차단한다.

    XML의 <status>를 Done으로 갱신하고,
    .kanban/active/T-NNN.xml를 .kanban/done/T-NNN.xml로 이동한다.

    Args:
        ticket_number: 완료할 티켓 번호 (T-NNN 형식).
    """
    # ── worktree 병합 훅 (티켓 상태 변경/파일 이동 전) ──
    import sys as _sys
    try:
        from flow.worktree_manager import is_worktree_enabled, get_worktree_path, merge_to_develop
        from flow.branch_strategy import get_feature_branch_for_ticket
        if is_worktree_enabled():
            wt_path = get_worktree_path(ticket_number)
            feat_branch = get_feature_branch_for_ticket(ticket_number)
            if wt_path or feat_branch:
                merge_result = merge_to_develop(ticket_number)
                if not merge_result.success:
                    if merge_result.conflicts:
                        print(f"[ERROR] {ticket_number} 병합 충돌 발생. Done 전이를 차단합니다.", flush=True)
                        print(f"  충돌 파일:", flush=True)
                        for cf in merge_result.conflicts:
                            print(f"    - {cf}", flush=True)
                        print(f"  worktree에서 충돌을 해결한 후 다시 시도하세요.", flush=True)
                        _sys.exit(1)
                    else:
                        # 충돌 외 실패: 경고 출력 후 계속 진행
                        print(f"[WARN] worktree 병합 실패: {merge_result.error_message}", flush=True)
                else:
                    print(f"{ticket_number}: {merge_result.merged_branch} -> develop 병합 완료 ({merge_result.merge_commit[:8]})", flush=True)
                    log("INFO", f"kanban.py: worktree merge {merge_result.merged_branch} -> develop ({merge_result.merge_commit[:8]})")
    except ImportError:
        pass  # worktree 모듈 미설치 시 무시 (하위 호환)
    except Exception as _wt_err:
        print(f"[WARN] worktree 병합 처리 중 오류 (계속 진행): {_wt_err}", flush=True)

    ticket_file = find_ticket_file(ticket_number)
    if ticket_file is None:
        err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

    ticket_data = parse_ticket_xml(ticket_file)
    current_section = ticket_data["status"]

    # active subnumber를 history로 이동 (있는 경우)
    move_active_to_history(ticket_file)

    # XML <status> Done으로 갱신
    update_ticket_status(ticket_file, "Done")

    # 파일을 kanban/done/T-NNN.xml로 이동
    done_dir = os.path.join(KANBAN_DIR, "done")
    dst_filename = f"{ticket_number}.xml"
    dst_file = os.path.join(done_dir, dst_filename)

    if os.path.isfile(ticket_file):
        os.makedirs(done_dir, exist_ok=True)
        try:
            shutil.move(ticket_file, dst_file)
        except OSError as e:
            err(f"티켓 파일 이동 실패: {e}")
        src_rel = os.path.relpath(ticket_file, _PROJECT_ROOT)
        print(f"파일 이동: {src_rel} → kanban/done/{dst_filename}")

    print(f"{ticket_number}: {current_section} → Done")
    log("INFO", f"kanban.py: done {ticket_number} {current_section} → Done")


def cmd_delete(ticket_number: str) -> None:
    """티켓 XML 파일을 삭제한다.

    Done과 달리 히스토리를 보존하지 않고 파일을 삭제한다.

    Args:
        ticket_number: 삭제할 티켓 번호 (T-NNN 형식).

    Raises:
        SystemExit: 티켓을 찾을 수 없는 경우.
    """
    ticket_file = find_ticket_file(ticket_number)
    if ticket_file is None:
        err(f"{ticket_number} 티켓을 찾을 수 없습니다")

    try:
        os.remove(ticket_file)
    except OSError as e:
        err(f"티켓 파일 삭제 실패: {e}")

    print(f"{ticket_number}: 삭제됨")


def cmd_update_title(ticket_number: str, title: str) -> None:
    """티켓 XML의 <title> 요소를 갱신한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).
        title: 새 제목 문자열.

    Raises:
        SystemExit: 티켓 파일을 찾을 수 없거나 쓰기 실패 시.
    """
    ticket_file = find_ticket_file(ticket_number)
    if ticket_file is None:
        err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

    try:
        tree = ET.parse(ticket_file)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"티켓 파일 파싱 실패 ({ticket_file}): {e}")

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

    write_ticket_xml(ticket_file, root)

    print(f"{ticket_number}: 제목 → {title}")


def cmd_set_editing(ticket_number: str, value: bool) -> None:
    """티켓 XML의 <metadata> 내부에 <editing> 요소를 생성(없으면) 또는 갱신한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).
        value: True이면 "true", False이면 "false"로 설정.

    Raises:
        SystemExit: 티켓 파일을 찾을 수 없거나 쓰기 실패 시.
    """
    ticket_file = find_ticket_file(ticket_number)
    if ticket_file is None:
        err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

    try:
        tree = ET.parse(ticket_file)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"티켓 파일 파싱 실패 ({ticket_file}): {e}")

    metadata_elem = root.find("metadata")
    if metadata_elem is None:
        metadata_elem = ET.SubElement(root, "metadata")

    editing_elem = metadata_elem.find("editing")
    if editing_elem is None:
        editing_elem = ET.SubElement(metadata_elem, "editing")
    editing_elem.text = "true" if value else "false"

    write_ticket_xml(ticket_file, root)

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
    skip_validation: bool = False,
) -> None:
    """티켓 XML에 새 subnumber 항목을 추가한다.

    추가 후 품질 검증을 수행하여 QUALITY_THRESHOLD 미만이면 롤백한다.

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
        skip_validation: True이면 품질 검증을 건너뛴다 (긴급 시 사용).

    Raises:
        SystemExit: 티켓 파일을 찾을 수 없거나, 품질 검증 실패 시.
    """
    import sys as _sys

    ticket_file = find_ticket_file(ticket_number)
    if ticket_file is None:
        err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

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

    new_id = add_subnumber(ticket_file, subnumber_data)
    print(f"{ticket_number}: subnumber id={new_id} 추가됨")

    # ── 품질 검증 ──────────────────────────────────────────────────────────
    if skip_validation:
        return

    try:
        with open(ticket_file, "r", encoding="utf-8") as f:
            xml_text = f.read()
    except OSError as e:
        _sys.stderr.write(f"[WARN] 품질 검증용 파일 재읽기 실패: {e}\n")
        return

    prompt_text = extract_active_prompt(xml_text)
    validation_result = prompt_validate(prompt_text)
    quality_score = validation_result["quality_score"]

    if quality_score < QUALITY_THRESHOLD:
        # 품질 미달: 롤백 후 에러 종료
        rollback_subnumber(ticket_file, new_id)
        _sys.stderr.write(
            f"[ERROR] 품질 검증 실패 (score={quality_score:.4f} < threshold={QUALITY_THRESHOLD})\n"
        )
        if validation_result["missing_tags"]:
            _sys.stderr.write(
                f"  누락 태그: {', '.join(validation_result['missing_tags'])}\n"
            )
        if validation_result["empty_tags"]:
            _sys.stderr.write(
                f"  빈 태그: {', '.join(validation_result['empty_tags'])}\n"
            )
        if validation_result["feedback"]:
            _sys.stderr.write("  피드백:\n")
            for fb in validation_result["feedback"]:
                _sys.stderr.write(f"    - {fb}\n")
        _sys.exit(1)


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
    ticket_file = find_ticket_file(ticket_number)
    if ticket_file is None:
        err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

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
        err("갱신할 필드가 없습니다.", 2)

    update_subnumber(ticket_file, subnumber_id, updates)
    print(f"{ticket_number}: subnumber id={subnumber_id} 갱신됨")


def cmd_show(ticket_number: str) -> None:
    """특정 티켓의 상세 정보를 구조화된 텍스트로 출력한다.

    메타데이터, 관계 정보, 활성 subnumber의 프롬프트(goal/target/constraints/
    criteria/context) 및 result 유무를 순서대로 출력한다.

    Args:
        ticket_number: 조회할 티켓 번호 (T-NNN 형식).

    Raises:
        SystemExit: 티켓 파일을 찾을 수 없는 경우.
    """
    ticket_file = find_ticket_file(ticket_number)
    if ticket_file is None:
        err(f"{ticket_number} 티켓을 찾을 수 없습니다")

    ticket_data = parse_ticket_xml(ticket_file)

    number: str = ticket_data.get("number", ticket_number)
    title: str = ticket_data.get("title", "")
    status: str = ticket_data.get("status", "")
    current: int = ticket_data.get("current", 0)
    subnumbers: list = ticket_data.get("subnumbers", [])
    relations: list = ticket_data.get("relations", [])

    # ── 헤더 및 메타데이터 출력 ──────────────────────────────────────────────
    print(f"## {number}: {title}")
    print()
    print("### Metadata")
    print(f"- Number: {number}")
    print(f"- Title: {title}")
    print(f"- Status: {status}")
    print(f"- Current: {current}")

    # ── 관계 정보 출력 ────────────────────────────────────────────────────────
    if relations:
        print()
        print("### Relations")
        for rel in relations:
            rel_type: str = rel.get("type", "")
            rel_ticket: str = rel.get("ticket", "")
            print(f"- {rel_type}: {rel_ticket}")

    # ── 활성 subnumber 탐색 ──────────────────────────────────────────────────
    active_sub: dict | None = None
    if current > 0:
        for sub in subnumbers:
            if sub.get("id") == current:
                active_sub = sub
                break

    if active_sub is None:
        print()
        print("(활성 프롬프트 없음)")
        return

    # ── 활성 프롬프트 출력 ───────────────────────────────────────────────────
    print()
    print(f"### Active Prompt (subnumber {current})")

    command: str = active_sub.get("command", "")
    if command:
        print(f"- Command: {command}")

    goal: str = active_sub.get("goal", "")
    if goal:
        print(f"- Goal: {goal.strip()}")

    target: str = active_sub.get("target", "")
    if target:
        print(f"- Target: {target.strip()}")

    constraints: str = active_sub.get("constraints", "")
    if constraints:
        print(f"- Constraints: {constraints.strip()}")

    criteria: str = active_sub.get("criteria", "")
    if criteria:
        print(f"- Criteria: {criteria.strip()}")

    context: str = active_sub.get("context", "")
    if context:
        print(f"- Context: {context.strip()}")

    # ── result 정보 출력 ─────────────────────────────────────────────────────
    print()
    print("### Result")

    result = active_sub.get("result")
    if result:
        print("- Has Result: Yes")
        if isinstance(result, dict):
            workdir: str = result.get("workdir", "")
            if workdir:
                print(f"- Workdir: {workdir}")
            report: str = result.get("report", "")
            if report:
                print(f"- Report: {report}")
        else:
            print(f"- Detail: {result}")
    else:
        print("- Has Result: No")


# ─── 관계 양방향 매핑 ────────────────────────────────────────────────────────
# 각 관계 옵션에 대해 (원본에 기록할 타입, 대상에 기록할 역방향 타입)
_RELATION_PAIRS: dict[str, tuple[str, str]] = {
    "depends_on": ("depends-on", "blocks"),
    "derived_from": ("derived-from", "blocks"),
    "blocks": ("blocks", "depends-on"),
}


def _apply_relation(
    source_file: str,
    source_ticket: str,
    target_ticket: str,
    option_name: str,
    *,
    remove: bool = False,
) -> None:
    """단일 관계 옵션에 대해 양방향 관계를 기록하거나 제거한다.

    Args:
        source_file: 원본 티켓 파일 경로.
        source_ticket: 원본 티켓 번호 (T-NNN).
        target_ticket: 대상 티켓 번호 (T-NNN).
        option_name: 관계 옵션 이름 (depends_on, derived_from, blocks).
        remove: True이면 관계를 제거한다.
    """
    target_file = find_ticket_file(target_ticket)
    if target_file is None:
        err(f"대상 티켓 {target_ticket} 파일을 찾을 수 없습니다")

    forward_type, reverse_type = _RELATION_PAIRS[option_name]
    fn = remove_relation if remove else add_relation

    fn(source_file, forward_type, target_ticket)
    fn(target_file, reverse_type, source_ticket)


def cmd_link(
    ticket_number: str,
    depends_on: str = "",
    derived_from: str = "",
    blocks: str = "",
) -> None:
    """티켓 간 관계를 양방향으로 기록한다.

    각 관계 옵션에 대해 원본 티켓과 대상 티켓 양쪽에 관계를 추가한다.
    - --depends-on T-MMM: 원본에 depends-on T-MMM + T-MMM에 blocks T-NNN
    - --derived-from T-MMM: 원본에 derived-from T-MMM + T-MMM에 blocks T-NNN
    - --blocks T-MMM: 원본에 blocks T-MMM + T-MMM에 depends-on T-NNN

    Args:
        ticket_number: 원본 티켓 번호 (T-NNN 형식).
        depends_on: 의존 대상 티켓 번호.
        derived_from: 파생 원본 티켓 번호.
        blocks: 차단 대상 티켓 번호.
    """
    source_file = find_ticket_file(ticket_number)
    if source_file is None:
        err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

    options = {"depends_on": depends_on, "derived_from": derived_from, "blocks": blocks}
    applied = []

    for option_name, target in options.items():
        if not target:
            continue
        normalized = normalize_ticket_number(target)
        if normalized is None:
            err(f"잘못된 티켓 번호 형식: '{target}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        _apply_relation(source_file, ticket_number, normalized, option_name)
        forward_type = _RELATION_PAIRS[option_name][0]
        applied.append(f"{forward_type} {normalized}")

    for desc in applied:
        print(f"{ticket_number}: {desc} 관계 추가됨")
    log("INFO", f"kanban.py: link {ticket_number} {', '.join(applied)}")


def cmd_unlink(
    ticket_number: str,
    depends_on: str = "",
    derived_from: str = "",
    blocks: str = "",
) -> None:
    """티켓 간 관계를 양방향으로 제거한다.

    cmd_link의 역방향으로 양쪽 XML에서 관계를 제거한다.

    Args:
        ticket_number: 원본 티켓 번호 (T-NNN 형식).
        depends_on: 의존 대상 티켓 번호.
        derived_from: 파생 원본 티켓 번호.
        blocks: 차단 대상 티켓 번호.
    """
    source_file = find_ticket_file(ticket_number)
    if source_file is None:
        err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

    options = {"depends_on": depends_on, "derived_from": derived_from, "blocks": blocks}
    removed = []

    for option_name, target in options.items():
        if not target:
            continue
        normalized = normalize_ticket_number(target)
        if normalized is None:
            err(f"잘못된 티켓 번호 형식: '{target}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        _apply_relation(source_file, ticket_number, normalized, option_name, remove=True)
        forward_type = _RELATION_PAIRS[option_name][0]
        removed.append(f"{forward_type} {normalized}")

    for desc in removed:
        print(f"{ticket_number}: {desc} 관계 제거됨")
    log("INFO", f"kanban.py: unlink {ticket_number} {', '.join(removed)}")


def cmd_board() -> None:
    """칸반 보드 전체 현황을 마크다운 테이블 형식으로 출력한다.

    .kanban/active/ 디렉터리의 티켓을 status 기준으로 Open/In Progress/Review 칼럼에,
    .kanban/done/ 디렉터리의 티켓을 Done 칼럼에 그룹핑하여 출력한다.
    Done 칼럼은 최근 10건만 표시하고 총 건수를 함께 출력한다.
    각 칼럼에 티켓이 없으면 "(없음)"을 출력한다.

    출력 포맷:
        ## Kanban Board

        ### Open
        | Ticket | Title | Command |
        ...

        ### Done (총 N건, 최근 10건 표시)
        | Ticket | Title |
        ...
    """
    # ── 칼럼 정의 ────────────────────────────────────────────────────────────
    COLUMNS = ["Open", "In Progress", "Review", "Done"]
    grouped: dict[str, list[dict]] = {col: [] for col in COLUMNS}

    # ── active 디렉터리 스캔 ──────────────────────────────────────────────────
    if os.path.isdir(KANBAN_ACTIVE_DIR):
        for fname in os.listdir(KANBAN_ACTIVE_DIR):
            if not (fname.startswith("T-") and fname.endswith(".xml")):
                continue
            fpath = os.path.join(KANBAN_ACTIVE_DIR, fname)
            try:
                ticket_data = parse_ticket_xml(fpath)
            except SystemExit:
                log("WARN", f"kanban.py: board - parse_ticket_xml 실패: {fname}")
                continue

            status = ticket_data.get("status", "Open")
            column = status if status in COLUMNS else "Open"

            # 활성 subnumber 탐색: current 값과 id가 일치하는 subnumber
            current_id = ticket_data.get("current", 0)
            active_command = ""
            for sub in ticket_data.get("subnumbers", []):
                if sub.get("id") == current_id:
                    active_command = sub.get("command", "")
                    break

            grouped[column].append({
                "number": ticket_data.get("number", ""),
                "title": ticket_data.get("title", ""),
                "command": active_command,
            })

    # ── done 디렉터리 스캔 ───────────────────────────────────────────────────
    done_dir = os.path.join(KANBAN_DIR, "done")
    if os.path.isdir(done_dir):
        for fname in os.listdir(done_dir):
            if not (fname.startswith("T-") and fname.endswith(".xml")):
                continue
            fpath = os.path.join(done_dir, fname)
            try:
                ticket_data = parse_ticket_xml(fpath)
            except SystemExit:
                log("WARN", f"kanban.py: board - parse_ticket_xml 실패: {fname}")
                continue

            grouped["Done"].append({
                "number": ticket_data.get("number", ""),
                "title": ticket_data.get("title", ""),
                "command": "",
            })

    # ── 번호 기준 정렬 (T-NNN → NNN 숫자 오름차순) ──────────────────────────
    def _ticket_sort_key(t: dict) -> int:
        num_str = t.get("number", "T-0").lstrip("T-")
        return int(num_str) if num_str.isdigit() else 0

    for col in COLUMNS[:-1]:  # Open, In Progress, Review
        grouped[col].sort(key=_ticket_sort_key)

    # Done은 번호 내림차순(최신 먼저), 최근 10건만 표시
    grouped["Done"].sort(key=_ticket_sort_key, reverse=True)
    done_total = len(grouped["Done"])
    grouped["Done"] = grouped["Done"][:10]

    # ── 출력 ─────────────────────────────────────────────────────────────────
    print("## Kanban Board")

    for col in COLUMNS[:-1]:  # Open, In Progress, Review
        print(f"\n### {col}")
        tickets = grouped[col]
        if not tickets:
            print("(없음)")
        else:
            print("| Ticket | Title | Command |")
            print("|--------|-------|---------|")
            for t in tickets:
                number = t["number"]
                title = t["title"]
                command = t["command"]
                print(f"| {number}  | {title} | {command} |")

    # Done 칼럼
    print(f"\n### Done (총 {done_total}건, 최근 10건 표시)")
    tickets = grouped["Done"]
    if not tickets:
        print("(없음)")
    else:
        print("| Ticket | Title |")
        print("|--------|-------|")
        for t in tickets:
            number = t["number"]
            title = t["title"]
            print(f"| {number}  | {title} |")


# ─── argparse 설정 ───────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
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
    add_sub_parser.add_argument("--workdir", default="", help=".claude.workflow/workflow/ 산출물 경로 (선택)")
    add_sub_parser.add_argument("--result", default="", help="실행 결과 요약 (선택)")
    add_sub_parser.add_argument("--skip-validation", action="store_true", default=False, help="품질 검증을 우회한다 (긴급 시 사용)")

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

    # link 서브커맨드
    link_parser = subparsers.add_parser("link", help="티켓 간 관계를 양방향으로 기록한다")
    link_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")
    link_parser.add_argument("--depends-on", dest="depends_on", default="", help="의존 대상 티켓 번호")
    link_parser.add_argument("--derived-from", dest="derived_from", default="", help="파생 원본 티켓 번호")
    link_parser.add_argument("--blocks", default="", help="차단 대상 티켓 번호")

    # unlink 서브커맨드
    unlink_parser = subparsers.add_parser("unlink", help="티켓 간 관계를 양방향으로 제거한다")
    unlink_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")
    unlink_parser.add_argument("--depends-on", dest="depends_on", default="", help="의존 대상 티켓 번호")
    unlink_parser.add_argument("--derived-from", dest="derived_from", default="", help="파생 원본 티켓 번호")
    unlink_parser.add_argument("--blocks", default="", help="차단 대상 티켓 번호")

    # board 서브커맨드
    subparsers.add_parser("board", help="칸반 보드 전체 현황을 조회한다")

    # show 서브커맨드
    show_parser = subparsers.add_parser("show", help="특정 티켓의 상세 정보를 조회한다")
    show_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")

    return parser


# ─── 디스패치 ───────────────────────────────────────────────────────────────


def dispatch(args: argparse.Namespace) -> None:
    """파싱된 CLI 인자를 해당 서브커맨드 핸들러로 디스패치한다.

    main()의 서브커맨드별 분기 로직을 독립 함수로 추출한 것이다.
    티켓 번호 정규화 및 유효성 검증을 포함한다.

    Args:
        args: argparse.parse_args()의 반환값.

    Raises:
        SystemExit: 잘못된 티켓 번호 또는 서브커맨드 실행 오류 시.
    """
    if args.subcommand == "create":
        cmd_create(args.title, args.command)

    elif args.subcommand == "move":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_move(ticket, args.target, force=args.force)

    elif args.subcommand == "done":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_done(ticket)

    elif args.subcommand == "delete":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_delete(ticket)

    elif args.subcommand == "add-subnumber":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
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
            skip_validation=args.skip_validation,
        )

    elif args.subcommand == "archive-subnumber":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        ticket_file = find_ticket_file(ticket)
        if ticket_file is None:
            err(f"{ticket} 티켓 파일을 찾을 수 없습니다")
        moved = move_active_to_history(ticket_file)
        if moved:
            print(f"{ticket}: active subnumber를 history로 이동했습니다")
        else:
            err(f"{ticket}: active subnumber가 없습니다")

    elif args.subcommand == "set-editing":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_set_editing(ticket, args.on)

    elif args.subcommand in ("update-title", "update"):
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        title = args.title or getattr(args, "title_flag", "") or ""
        if not title:
            err("제목을 지정해야 합니다. 예: flow-kanban update-title T-001 \"새 제목\"", 2)
        cmd_update_title(ticket, title)

    elif args.subcommand == "update-subnumber":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
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

    elif args.subcommand == "link":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        if not args.depends_on and not args.derived_from and not args.blocks:
            err("--depends-on, --derived-from, --blocks 중 최소 1개를 지정해야 합니다.", 2)
        cmd_link(
            ticket,
            depends_on=args.depends_on,
            derived_from=args.derived_from,
            blocks=args.blocks,
        )

    elif args.subcommand == "unlink":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        if not args.depends_on and not args.derived_from and not args.blocks:
            err("--depends-on, --derived-from, --blocks 중 최소 1개를 지정해야 합니다.", 2)
        cmd_unlink(
            ticket,
            depends_on=args.depends_on,
            derived_from=args.derived_from,
            blocks=args.blocks,
        )

    elif args.subcommand == "board":
        cmd_board()

    elif args.subcommand == "show":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_show(ticket)

    else:
        err(f"알 수 없는 서브커맨드: '{args.subcommand}'", 2)
