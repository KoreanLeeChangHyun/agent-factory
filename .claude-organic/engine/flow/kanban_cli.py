"""kanban_cli.py - 칸반 보드 서브커맨드 구현 및 CLI 파서 모듈.

서브커맨드별 비즈니스 로직(cmd_* 함수), argparse 파서 구성(build_parser),
서브커맨드 디스패치(dispatch)를 담당하는 비즈니스 계층 모듈이다.
kanban.py에서 분리되었으며, ticket_repository.py와 ticket_state.py에 의존한다.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime

from flow.ticket_repository import (
    add_relation,
    create_ticket_xml,
    find_ticket_file,
    normalize_ticket_number,
    get_max_ticket_number,
    move_ticket_to_status_dir,
    remove_relation,
    update_prompt,
    update_result,
    write_ticket_xml,
    parse_ticket_xml,
    err,
    log,
    KANBAN_DIR,
    KANBAN_TODO_DIR,
    KANBAN_OPEN_DIR,
    KANBAN_PROGRESS_DIR,
    KANBAN_REVIEW_DIR,
    KANBAN_DONE_DIR,
    STATUS_DIR_MAP,
)
from flow.ticket_state import (
    COLUMN_MAP,
    update_ticket_status,
    validate_transition,
)
from flow.prompt_validator import validate as prompt_validate
from constants import QUALITY_THRESHOLD


# ─── 경로 상수 ───────────────────────────────────────────────────────────────

from common import resolve_project_root

_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT: str = resolve_project_root()


# ─── 디버그 슬롯 정책 ─────────────────────────────────────────────────────────
# T-900~T-999 는 디버그/일회성 검증용 예약 영역. 자동 채번에서 제외되며,
# `--debug` 플래그 또는 `--number 9XX` 명시 호출로만 사용한다.
_DEBUG_RANGE_START: int = 900
_DEBUG_RANGE_END: int = 999
_DEBUG_TEMPLATE_PATH: str = os.path.join(
    _PROJECT_ROOT, ".claude-organic", "templates", "debug-ticket.json"
)


def _get_next_debug_slot() -> "str | None":
    """T-900~T-999 영역에서 비어있는 첫 슬롯 번호를 반환한다.

    모든 디버그 슬롯이 사용 중이면 None을 반환한다.

    Returns:
        T-NNN 형식 문자열 또는 None.
    """
    for num in range(_DEBUG_RANGE_START, _DEBUG_RANGE_END + 1):
        candidate = f"T-{num:03d}"
        if find_ticket_file(candidate) is None:
            return candidate
    return None


def _load_debug_template() -> dict:
    """디버그 티켓 템플릿 JSON을 로드한다.

    파일이 없거나 파싱 실패 시 비어있는 dict를 반환하여 호출 측이 폴백할 수 있게 한다.

    Returns:
        템플릿 dict (title_prefix, command, prompt 키 포함 가능).
    """
    try:
        with open(_DEBUG_TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


# ─── 세션 헬퍼 ───────────────────────────────────────────────────────────────

import json
import urllib.request

_TMUX_WINDOW_PREFIX: str = "P:"


def _resolve_server_port() -> "int | None":
    """서버 포트를 해석한다.

    _WF_SERVER_PORT 환경변수 또는 .claude-organic/.board.url 파일에서 포트를 추출한다.

    Returns:
        포트 번호(int) 또는 None (해석 불가 시).
    """
    # 1) 환경변수 우선
    port_env = os.environ.get("_WF_SERVER_PORT")
    if port_env:
        try:
            return int(port_env)
        except ValueError:
            pass

    # 2) .board.url 파일 파싱: http://127.0.0.1:PORT/board
    board_url_path = os.path.join(_PROJECT_ROOT, ".claude-organic", ".board.url")
    try:
        with open(board_url_path, "r", encoding="utf-8") as f:
            url = f.read().strip()
        # http://127.0.0.1:PORT/... 형식에서 PORT 추출
        if "://" in url:
            host_part = url.split("://", 1)[1]  # 127.0.0.1:PORT/...
            host_port = host_part.split("/")[0]  # 127.0.0.1:PORT
            if ":" in host_port:
                return int(host_port.split(":")[1])
    except (OSError, ValueError):
        pass

    return None


def _kill_ticket_session(ticket_number: str) -> None:
    """활성 세션에서 해당 티켓의 워크플로우 세션을 종료한다.

    HTTP API(서버 기동 중)를 통해 세션을 종료하고,
    서버 미기동 시 tmux kill-window 폴백을 사용한다.
    상태 전이 성공 후에만 호출되어야 한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).
    """
    port = _resolve_server_port()

    if port is not None:
        # HTTP API 경로: 세션 목록 조회 후 ticket_id 매칭 세션 kill
        try:
            list_url = f"http://127.0.0.1:{port}/terminal/workflow/list"
            req = urllib.request.Request(list_url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            sessions = data if isinstance(data, list) else data.get("sessions", [])
            session_id = None
            for session in sessions:
                if session.get("ticket_id") == ticket_number or session.get("ticket") == ticket_number:
                    session_id = session.get("session_id") or session.get("id")
                    break

            if session_id:
                kill_url = f"http://127.0.0.1:{port}/terminal/workflow/kill"
                kill_body = json.dumps({"session_id": session_id}).encode("utf-8")
                kill_req = urllib.request.Request(
                    kill_url,
                    data=kill_body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(kill_req, timeout=5) as kill_resp:
                    kill_resp.read()
                log("INFO", f"kanban.py: http kill session_id={session_id} ({ticket_number})")
            else:
                log("INFO", f"kanban.py: no active session found for {ticket_number}")
            return
        except Exception:
            # HTTP 오류는 상태 전이와 무관하므로 무시하고 반환
            return

    # 포트 미해석 시 tmux 폴백 (하위호환)
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


def _cleanup_worktree_on_leave(ticket_number: str) -> None:
    """In Progress에서 이탈할 때 연결된 워크트리를 자동 정리한다.

    워크트리 비활성 환경이거나 해당 티켓의 워크트리가 없으면 조용히 건너뛴다.
    정리 실패 시 경고만 출력하고 예외를 전파하지 않는다 (상태 전이 차단 금지).

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).
    """
    try:
        from flow.worktree_manager import (
            is_worktree_enabled,
            get_worktree_path,
            remove_worktree,
        )

        if not is_worktree_enabled():
            return

        wt_path = get_worktree_path(ticket_number)
        if not wt_path:
            return

        success = remove_worktree(ticket_number, delete_branch=True)
        if success:
            log("INFO", f"kanban.py: worktree 자동 정리 완료 ({ticket_number})")
        else:
            print(f"[WARN] {ticket_number} 워크트리 정리 실패 (계속 진행)", flush=True)
    except ImportError:
        pass  # worktree 모듈 미설치 시 무시 (하위 호환)
    except Exception as e:
        print(f"[WARN] {ticket_number} 워크트리 정리 중 오류 (계속 진행): {e}", flush=True)


# ─── 서브커맨드 구현 ─────────────────────────────────────────────────────────


def cmd_create(
    title: str,
    command: str,
    status: str,
    number: str | None = None,
    debug: bool = False,
) -> None:
    """새 티켓 XML을 생성한다.

    번호 미지정 시 XML 파일명에서 최대 T-NNN 번호를 스캔하여 +1 자동 채번한다.
    번호 명시 시 정규화 후 동일 번호 충돌을 검사하고, 존재하면 에러로 거부한다.
    debug=True 면 T-900~T-999 영역의 빈 슬롯을 자동 배정하고 디버그 템플릿을 적용한다.
    자동 채번은 T-899 까지만 사용한다 (T-900~T-999 는 디버그 전용 예약 영역).
    status 값에 따라 .kanban/todo/ 또는 .kanban/open/ 아래에 T-NNN.xml 파일을 생성한다.

    Args:
        title: 티켓 제목. 빈 문자열 허용.
        command: 워크플로우 커맨드 (implement, review, research 등). 현재 미사용 (하위 호환용).
        status: 초기 상태 키 ("todo" | "open"). COLUMN_MAP을 통해 XML <status> 값으로 변환된다.
        number: 명시적 티켓 번호 (T-NNN, NNN, #N 형식). 미지정 시 자동 채번.
        debug: True 이면 디버그 슬롯 자동 배정 및 템플릿 적용. number 와 동시 사용 불가.
    """
    # status 키를 상태명("To Do" / "Open")으로 변환
    status_label = COLUMN_MAP.get(status)
    if status_label is None or status not in ("todo", "open"):
        err(
            f"잘못된 --status 값: '{status}'. 'todo' 또는 'open' 중 하나를 명시하세요. "
            f"(예: flow-kanban create \"제목\" --command implement --status todo)",
            2,
        )

    # --debug 와 --number 동시 사용 차단
    if debug and number is not None:
        err("--debug 와 --number 는 동시 사용할 수 없습니다. 둘 중 하나만 지정하세요.", 2)

    # --debug 처리: 슬롯 자동 배정 + 템플릿 로드
    debug_template: dict = {}
    if debug:
        slot = _get_next_debug_slot()
        if slot is None:
            err(
                f"디버그 슬롯 소진: T-{_DEBUG_RANGE_START}~T-{_DEBUG_RANGE_END} 모두 사용 중입니다. "
                f"기존 디버그 티켓을 정리한 후 다시 시도하세요.",
                2,
            )
        number = slot
        debug_template = _load_debug_template()
        # 템플릿의 title_prefix / command 적용 (사용자 명시 우선)
        prefix = debug_template.get("title_prefix", "")
        if prefix and not title.startswith(prefix.strip()):
            title = f"{prefix}{title}"
        if not command and debug_template.get("command"):
            command = debug_template["command"]

    # 대상 디렉터리 결정
    target_dir = KANBAN_TODO_DIR if status == "todo" else KANBAN_OPEN_DIR

    if number is not None:
        normalized = normalize_ticket_number(number)
        if normalized is None:
            err(
                f"잘못된 --number 값: '{number}'. T-NNN, NNN, #N 형식 중 하나여야 합니다.",
                2,
            )
        ticket_number = normalized
        existing = find_ticket_file(ticket_number)
        if existing is not None:
            err(
                f"티켓 번호 충돌: {ticket_number} 이미 존재합니다 ({existing}). "
                f"번호는 유니크해야 합니다.",
                2,
            )
    else:
        max_num = get_max_ticket_number()
        new_num = max_num + 1
        # 디버그 영역 진입 차단: 자동 채번이 T-900 에 도달하면 에러로 정책을 알린다.
        if new_num >= _DEBUG_RANGE_START:
            err(
                f"자동 채번이 디버그 영역(T-{_DEBUG_RANGE_START}~T-{_DEBUG_RANGE_END}) 에 도달했습니다. "
                f"--number 로 일반 영역 번호를 명시하거나, 디버그 슬롯을 정리하세요.",
                2,
            )
        ticket_number = f"T-{new_num:03d}"

    # 파일명: T-NNN.xml 고정
    ticket_file = os.path.join(target_dir, f"{ticket_number}.xml")

    os.makedirs(target_dir, exist_ok=True)
    datetime_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    xml_content = create_ticket_xml(ticket_number, title, datetime_str, command=command)

    # XML <status> 태그 값을 status_label로 교체
    # create_ticket_xml 은 기본적으로 "Open"을 기록하므로, status=="todo"인 경우에만 치환.
    if status_label != "Open":
        xml_content = xml_content.replace(
            "<status>Open</status>", f"<status>{status_label}</status>", 1
        )

    try:
        with open(ticket_file, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(xml_content)
            f.write("\n")
    except OSError as e:
        err(f"티켓 파일 생성 실패: {e}")

    # --debug 시 템플릿의 prompt 필드를 즉시 시딩한다 (사용자가 update-prompt 로 갈아끼우기 쉽게 placeholder 제공).
    if debug:
        prompt_defaults = debug_template.get("prompt", {}) or {}
        if prompt_defaults:
            try:
                update_prompt(
                    ticket_file,
                    {k: v for k, v in prompt_defaults.items() if v},
                )
            except Exception as exc:
                # 템플릿 시딩 실패는 티켓 생성 자체를 막지 않는다 (경고만 남긴다).
                print(f"[WARN] 디버그 템플릿 시딩 실패: {exc}", flush=True)

    suffix = f" ({command})" if command else ""
    print(f"{ticket_number}: {title}{suffix} [{status_label}]")
    log("INFO", f"kanban.py: create {ticket_number} title={title!r} status={status_label!r}")


def cmd_move(ticket_number: str, target_key: str, force: bool = False) -> None:
    """티켓 상태를 변경한다.

    허용 상태 전이 규칙을 검증하고, 위반 시 에러를 출력한다.
    --force 플래그가 있으면 규칙을 무시하고 강제 이동한다.

    Args:
        ticket_number: 이동할 티켓 번호 (T-NNN 형식).
        target_key: 대상 컬럼 키 (todo/open/progress/review/done).
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

    # validate_transition 통과 후, 실제 쓰기 전 파일 존재 재검증 (레이스 컨디션 방어)
    if not os.path.isfile(ticket_file):
        # 다른 세션이 이미 파일을 이동했을 수 있음 — 대상 디렉터리에서 재탐색
        refreshed = find_ticket_file(ticket_number)
        if refreshed is None:
            err(f"{ticket_number} 티켓 파일이 이동 중 소실되었습니다 (레이스 컨디션)")
        # 재탐색된 파일로 상태 재확인
        refreshed_data = parse_ticket_xml(refreshed)
        if refreshed_data["status"] == target_section:
            print(f"{ticket_number}은 이미 {target_section} 상태입니다. (다른 세션에서 처리됨)")
            return
        # 다른 상태로 이동된 경우 ticket_file 갱신 후 전이 규칙 재검증
        ticket_file = refreshed
        current_section = refreshed_data["status"]
        validation_error = validate_transition(current_section, target_section, force)
        if validation_error is not None:
            if validation_error == "":
                print(f"{ticket_number}은 이미 {target_section} 상태입니다.")
                return
            err(f"{ticket_number}은 {validation_error}")

    # XML <status> 갱신
    try:
        update_ticket_status(ticket_file, target_section)
    except FileNotFoundError:
        # write_ticket_xml이 파일 소실을 감지 — 재탐색 후 멱등성 확인
        refreshed = find_ticket_file(ticket_number)
        if refreshed is None:
            err(f"{ticket_number} 티켓 파일이 상태 갱신 중 소실되었습니다 (레이스 컨디션)")
        refreshed_data = parse_ticket_xml(refreshed)
        if refreshed_data["status"] == target_section:
            print(f"{ticket_number}은 이미 {target_section} 상태입니다. (다른 세션에서 처리됨)")
            return
        err(f"{ticket_number} 상태 갱신 중 파일 소실 감지. 현재 상태: {refreshed_data['status']}")

    # 상태에 대응하는 디렉터리로 파일 이동
    try:
        new_path = move_ticket_to_status_dir(ticket_file, target_section)
        if new_path != ticket_file:
            src_rel = os.path.relpath(ticket_file, _PROJECT_ROOT)
            dst_rel = os.path.relpath(new_path, _PROJECT_ROOT)
            print(f"파일 이동: {src_rel} → {dst_rel}")
        ticket_file = new_path
    except FileNotFoundError:
        # 이동 중 파일 소실 — 이미 이동된 경우 정상 처리
        refreshed = find_ticket_file(ticket_number)
        if refreshed is not None:
            refreshed_data = parse_ticket_xml(refreshed)
            if refreshed_data["status"] == target_section:
                print(f"{ticket_number}은 이미 {target_section} 상태입니다. (다른 세션에서 처리됨)")
                return
        err(f"{ticket_number} 파일 이동 중 소실 감지")
    except OSError as e:
        err(f"티켓 파일 이동 실패: {e}")

    print(f"{ticket_number}: {current_section} → {target_section}")
    log("INFO", f"kanban.py: move {ticket_number} {current_section} → {target_section}")

    # In Progress에서 이탈 시 워크트리 자동 정리
    # T-370 정합: Review 전이는 worktree 유지 (cmd_done 의 merge_to_develop 가 정리 진입점).
    # In Progress → Open(재작업) / To Do(강등) 전이에서만 자동 정리.
    if current_section == "In Progress" and target_section != "Review":
        _cleanup_worktree_on_leave(ticket_number)

    # Open 전이 시 세션 자동 kill:
    # In Progress에서 Open으로 복귀하면 해당 티켓의 활성 세션을 종료한다.
    # T-399: Submit transient 단계 제거, In Progress 만 검사한다.
    # 상태 전이 성공 후에 실행하므로 전이 실패 시(err() 호출 후 SystemExit) 여기에 도달하지 않는다.
    if target_section == "Open" and current_section == "In Progress":
        _kill_ticket_session(ticket_number)


def cmd_done(ticket_number: str) -> None:
    """티켓을 Done으로 변경하고 파일을 .kanban/done/으로 이동한다.

    worktree가 활성화된 경우, 상태 변경/파일 이동 전에 feature 브랜치를
    develop에 병합한다. 병합 충돌 시 Done 전이를 차단한다.

    XML의 <status>를 Done으로 갱신하고,
    move_ticket_to_status_dir()를 통해 .kanban/done/T-NNN.xml로 이동한다.

    Args:
        ticket_number: 완료할 티켓 번호 (T-NNN 형식).
    """
    # ── worktree 병합 훅 (티켓 상태 변경/파일 이동 전) ──
    import sys as _sys
    try:
        from flow.worktree_manager import is_worktree_enabled, get_worktree_path, merge_to_develop, has_uncommitted_changes
        from flow.branch_strategy import get_feature_branch_for_ticket
        if is_worktree_enabled():
            # C-01: dirty worktree 감지 → 미커밋 변경 존재 시 거부
            _wt_path = get_worktree_path(ticket_number)
            if _wt_path and has_uncommitted_changes(_wt_path):
                _porcelain = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=_wt_path,
                    capture_output=True,
                    text=True,
                )
                print(f"[ERROR] 미커밋 변경이 있는 워크트리입니다. Done 전이를 차단합니다.", flush=True)
                print(f"  미커밋 파일 목록:", flush=True)
                for _line in _porcelain.stdout.strip().splitlines():
                    print(f"    {_line}", flush=True)
                print(f"  flow-merge를 사용하여 정상 경로로 완료하세요.", flush=True)
                _sys.exit(1)
            feat_branch = get_feature_branch_for_ticket(ticket_number)
            if _wt_path or feat_branch:
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

    # XML <status> Done으로 갱신
    update_ticket_status(ticket_file, "Done")

    # 파일을 kanban/done/T-NNN.xml로 이동
    if os.path.isfile(ticket_file):
        try:
            new_path = move_ticket_to_status_dir(ticket_file, "Done")
            if new_path != ticket_file:
                src_rel = os.path.relpath(ticket_file, _PROJECT_ROOT)
                dst_rel = os.path.relpath(new_path, _PROJECT_ROOT)
                print(f"파일 이동: {src_rel} → {dst_rel}")
        except OSError as e:
            err(f"티켓 파일 이동 실패: {e}")

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


def cmd_update_prompt(
    ticket_number: str,
    command: str = "",
    goal: str = "",
    target: str = "",
    constraints: str = "",
    criteria: str = "",
    context: str = "",
    skip_validation: bool = False,
) -> None:
    """티켓 XML의 <prompt> 및 <metadata>/<command>를 갱신한다.

    갱신 후 품질 검증을 수행하여 QUALITY_THRESHOLD 미만이면 에러를 출력한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).
        command: 워크플로우 커맨드 (implement, review, research 등).
        goal: 작업 목표.
        target: 대상.
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

    updates: dict[str, str] = {}
    if command:
        updates["command"] = command
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

    update_prompt(ticket_file, updates)
    print(f"{ticket_number}: prompt 갱신됨")

    # ── 품질 검증 ──────────────────────────────────────────────────────────
    if skip_validation:
        return

    try:
        with open(ticket_file, "r", encoding="utf-8") as f:
            xml_text = f.read()
    except OSError as e:
        _sys.stderr.write(f"[WARN] 품질 검증용 파일 재읽기 실패: {e}\n")
        return

    # flat 구조: <prompt> 태그 내부 텍스트를 직접 추출
    try:
        from flow.prompt_validator import extract_active_prompt
        prompt_text = extract_active_prompt(xml_text)
    except Exception:
        # extract_active_prompt 실패 시 검증 건너뜀
        return

    validation_result = prompt_validate(prompt_text)
    quality_score = validation_result["quality_score"]

    if quality_score < QUALITY_THRESHOLD:
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


def cmd_update_result(
    ticket_number: str,
    registrykey: str = "",
    workdir: str = "",
    plan: str = "",
    report: str = "",
) -> None:
    """티켓 XML의 <result> 하위 요소를 갱신한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).
        registrykey: 워크플로우 registryKey (YYYYMMDD-HHMMSS 형식).
        workdir: 워크플로우 산출물 디렉터리 상대 경로.
        plan: plan.md 상대 경로.
        report: report.md 상대 경로.

    Raises:
        SystemExit: 티켓 파일을 찾을 수 없거나 쓰기 실패 시.
    """
    ticket_file = find_ticket_file(ticket_number)
    if ticket_file is None:
        err(f"{ticket_number} 티켓 파일을 찾을 수 없습니다")

    updates: dict[str, str] = {}
    if registrykey:
        updates["registrykey"] = registrykey
    if workdir:
        updates["workdir"] = workdir
    if plan:
        updates["plan"] = plan
    if report:
        updates["report"] = report

    if not updates:
        err("갱신할 필드가 없습니다.", 2)

    update_result(ticket_file, updates)
    print(f"{ticket_number}: result 갱신됨")


def cmd_show(ticket_number: str) -> None:
    """특정 티켓의 상세 정보를 구조화된 텍스트로 출력한다.

    메타데이터, 관계 정보, 프롬프트(goal/target/constraints/criteria/context)
    및 result 정보를 순서대로 출력한다.

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
    command: str = ticket_data.get("command", "")
    prompt_data: dict = ticket_data.get("prompt", {}) or {}
    result_data: dict | None = ticket_data.get("result")
    relations: list = ticket_data.get("relations", [])

    # ── 헤더 및 메타데이터 출력 ──────────────────────────────────────────────
    print(f"## {number}: {title}")
    print()
    print("### Metadata")
    print(f"- Number: {number}")
    print(f"- Title: {title}")
    print(f"- Status: {status}")
    if command:
        print(f"- Command: {command}")

    # ── 관계 정보 출력 ────────────────────────────────────────────────────────
    if relations:
        print()
        print("### Relations")
        for rel in relations:
            rel_type: str = rel.get("type", "")
            rel_ticket: str = rel.get("ticket", "")
            print(f"- {rel_type}: {rel_ticket}")

    # ── 프롬프트 출력 ────────────────────────────────────────────────────────
    has_prompt = any(prompt_data.get(k) for k in ("goal", "target", "constraints", "criteria", "context"))
    if not has_prompt:
        print()
        print("(프롬프트 없음)")
    else:
        print()
        print("### Prompt")

        goal: str = prompt_data.get("goal", "")
        if goal:
            print(f"- Goal: {goal.strip()}")

        target: str = prompt_data.get("target", "")
        if target:
            print(f"- Target: {target.strip()}")

        constraints: str = prompt_data.get("constraints", "")
        if constraints:
            print(f"- Constraints: {constraints.strip()}")

        criteria: str = prompt_data.get("criteria", "")
        if criteria:
            print(f"- Criteria: {criteria.strip()}")

        context: str = prompt_data.get("context", "")
        if context:
            print(f"- Context: {context.strip()}")

    # ── result 정보 출력 ─────────────────────────────────────────────────────
    print()
    print("### Result")

    if result_data and isinstance(result_data, dict):
        has_content = any(result_data.get(k) for k in ("registrykey", "workdir", "plan", "report"))
        if has_content:
            print("- Has Result: Yes")
            registrykey: str = result_data.get("registrykey", "")
            if registrykey:
                print(f"- RegistryKey: {registrykey}")
            workdir: str = result_data.get("workdir", "")
            if workdir:
                print(f"- Workdir: {workdir}")
            plan: str = result_data.get("plan", "")
            if plan:
                print(f"- Plan: {plan}")
            report: str = result_data.get("report", "")
            if report:
                print(f"- Report: {report}")
        else:
            print("- Has Result: No")
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

    .kanban/todo/, .kanban/open/, .kanban/progress/, .kanban/review/ 디렉터리를 각각 스캔하여
    To Do/Open/In Progress/Review 칼럼에 직접 매핑하고, .kanban/done/ 디렉터리의
    티켓을 Done 칼럼에 그룹핑하여 출력한다.
    Done 칼럼은 최근 10건만 표시하고 총 건수를 함께 출력한다.
    각 칼럼에 티켓이 없으면 "(없음)"을 출력한다.

    출력 포맷:
        ## Kanban Board

        ### To Do
        | Ticket | Title | Command |
        ...

        ### Done (총 N건, 최근 10건 표시)
        | Ticket | Title |
        ...
    """
    # ── 칼럼 정의 ────────────────────────────────────────────────────────────
    COLUMNS = ["To Do", "Open", "In Progress", "Review", "Done"]
    grouped: dict[str, list[dict]] = {col: [] for col in COLUMNS}

    # ── 상태별 디렉터리 스캔 (디렉터리가 SSoT) ────────────────────────────────
    # 디렉터리 -> 칼럼 매핑: todo/ -> To Do, open/ -> Open, progress/ -> In Progress, review/ -> Review
    _DIR_COLUMN_MAP = [
        (KANBAN_TODO_DIR, "To Do"),
        (KANBAN_OPEN_DIR, "Open"),
        (KANBAN_PROGRESS_DIR, "In Progress"),
        (KANBAN_REVIEW_DIR, "Review"),
    ]
    for scan_dir, column in _DIR_COLUMN_MAP:
        if not os.path.isdir(scan_dir):
            continue
        for fname in os.listdir(scan_dir):
            if not (fname.startswith("T-") and fname.endswith(".xml")):
                continue
            fpath = os.path.join(scan_dir, fname)
            try:
                ticket_data = parse_ticket_xml(fpath)
            except SystemExit:
                log("WARN", f"kanban.py: board - parse_ticket_xml 실패: {fname}")
                continue

            grouped[column].append({
                "number": ticket_data.get("number", ""),
                "title": ticket_data.get("title", ""),
                "command": ticket_data.get("command", ""),
            })

    # ── done 디렉터리 스캔 ───────────────────────────────────────────────────
    if os.path.isdir(KANBAN_DONE_DIR):
        for fname in os.listdir(KANBAN_DONE_DIR):
            if not (fname.startswith("T-") and fname.endswith(".xml")):
                continue
            fpath = os.path.join(KANBAN_DONE_DIR, fname)
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

    for col in COLUMNS[:-1]:  # To Do, Open, In Progress, Review
        grouped[col].sort(key=_ticket_sort_key)

    # Done은 번호 내림차순(최신 먼저), 최근 10건만 표시
    grouped["Done"].sort(key=_ticket_sort_key, reverse=True)
    done_total = len(grouped["Done"])
    grouped["Done"] = grouped["Done"][:10]

    # ── 출력 ─────────────────────────────────────────────────────────────────
    print("## Kanban Board")

    for col in COLUMNS[:-1]:  # To Do, Open, In Progress, Review
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


# 상태 키 -> (디렉터리, 표시 상태명) 매핑
_STATUS_SCAN_MAP: dict[str, tuple[str, str]] = {
    "todo": (KANBAN_TODO_DIR, "To Do"),
    "open": (KANBAN_OPEN_DIR, "Open"),
    "progress": (KANBAN_PROGRESS_DIR, "In Progress"),
    "review": (KANBAN_REVIEW_DIR, "Review"),
    "done": (KANBAN_DONE_DIR, "Done"),
}


def cmd_list(status_filter: str = "") -> None:
    """칸반 티켓 목록을 한 줄 요약 형식으로 출력한다.

    --status 옵션으로 특정 상태만 필터링할 수 있다.
    미지정 시 To Do/Done을 제외한 open/progress/review 전체를 출력한다.
    (To Do는 백로그 성격이므로 기본 노출에서 제외, 명시 요청 시에만 출력한다.)

    출력 포맷: T-NNN  [상태]  제목 (번호 오름차순)

    Args:
        status_filter: 상태 필터 키 (todo/open/progress/review/done).
            빈 문자열이면 To Do/Done 제외 전체.
    """
    if status_filter:
        scan_targets = [_STATUS_SCAN_MAP[status_filter]]
    else:
        # 기본: open + progress + review (todo, done 제외)
        # - todo: 백로그 성격이므로 기본 노출 제외 (--status todo 명시 시만 노출)
        # - done: 완료 티켓은 기본 노출 제외
        scan_targets = [
            _STATUS_SCAN_MAP["open"],
            _STATUS_SCAN_MAP["progress"],
            _STATUS_SCAN_MAP["review"],
        ]

    tickets: list[dict[str, str]] = []
    for scan_dir, status_label in scan_targets:
        if not os.path.isdir(scan_dir):
            continue
        for fname in os.listdir(scan_dir):
            if not (fname.startswith("T-") and fname.endswith(".xml")):
                continue
            fpath = os.path.join(scan_dir, fname)
            try:
                ticket_data = parse_ticket_xml(fpath)
            except SystemExit:
                continue
            tickets.append({
                "number": ticket_data.get("number", ""),
                "title": ticket_data.get("title", ""),
                "status": status_label,
            })

    # 번호 기준 오름차순 정렬 (T-NNN → NNN 숫자 변환)
    def _sort_key(t: dict[str, str]) -> int:
        num_str = t.get("number", "T-0").lstrip("T-")
        return int(num_str) if num_str.isdigit() else 0

    tickets.sort(key=_sort_key)

    if not tickets:
        print("(티켓 없음)")
        return

    for t in tickets:
        print(f"{t['number']}  [{t['status']}]  {t['title']}")


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
    create_parser.add_argument(
        "--status",
        required=True,
        choices=["todo", "open"],
        metavar="{todo,open}",
        help=(
            "초기 상태 (필수). 'todo'=백로그·미래에 할 일, 'open'=지금 집중 대상. "
            "예: flow-kanban create \"제목\" --command implement --status todo"
        ),
    )
    create_parser.add_argument(
        "--number",
        default=None,
        help=(
            "티켓 번호 명시 (T-NNN, NNN, #N 형식). 미지정 시 자동 채번 (T-899 까지). "
            "동일 번호 존재 시 에러. T-900~T-999 는 디버그 예약 영역."
        ),
    )
    create_parser.add_argument(
        "--debug",
        action="store_true",
        help=(
            "디버그 티켓 생성. T-900~T-999 영역의 빈 슬롯을 자동 배정하고 "
            ".claude-organic/templates/debug-ticket.json 템플릿을 적용한다. "
            "--number 와 동시 사용 불가."
        ),
    )

    # move 서브커맨드
    move_parser = subparsers.add_parser("move", help="티켓을 지정 컬럼으로 이동한다")
    move_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")
    move_parser.add_argument(
        "target",
        choices=list(COLUMN_MAP.keys()),
        help="대상 컬럼 (todo/open/progress/review/done)",
    )
    move_parser.add_argument("--force", action="store_true", help="상태 전이 규칙 무시하고 강제 이동")

    # done 서브커맨드
    done_parser = subparsers.add_parser("done", help="티켓을 Done으로 이동하고 파일을 .kanban/done/으로 이동한다")
    done_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")

    # delete 서브커맨드
    delete_parser = subparsers.add_parser("delete", help="티켓을 삭제한다")
    delete_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")

    # update-prompt 서브커맨드
    update_prompt_parser = subparsers.add_parser("update-prompt", help="티켓의 prompt 및 command를 갱신한다")
    update_prompt_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")
    update_prompt_parser.add_argument("--command", default="", help="워크플로우 커맨드 (implement, review, research 등)")
    update_prompt_parser.add_argument("--goal", default="", help="작업 목표")
    update_prompt_parser.add_argument("--target", default="", help="대상")
    update_prompt_parser.add_argument("--constraints", default="", help="제약사항 (선택, 프롬프트 5요소)")
    update_prompt_parser.add_argument("--criteria", default="", help="완료 기준 (선택, 프롬프트 5요소)")
    update_prompt_parser.add_argument("--context", default="", help="맥락 정보 (선택, 프롬프트 5요소)")
    update_prompt_parser.add_argument("--skip-validation", action="store_true", default=False, help="품질 검증을 우회한다 (긴급 시 사용)")

    # update-result 서브커맨드
    update_result_parser = subparsers.add_parser("update-result", help="티켓의 result 정보를 갱신한다")
    update_result_parser.add_argument("ticket", help="티켓 번호 (T-NNN, NNN, #N 형식)")
    update_result_parser.add_argument("--registrykey", default="", help="워크플로우 registryKey (YYYYMMDD-HHMMSS 형식)")
    update_result_parser.add_argument("--workdir", default="", help="워크플로우 산출물 디렉터리 상대 경로")
    update_result_parser.add_argument("--plan", default="", help="plan.md 상대 경로")
    update_result_parser.add_argument("--report", default="", help="report.md 상대 경로")

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

    # list 서브커맨드
    list_parser = subparsers.add_parser("list", help="칸반 티켓 목록을 조회한다")
    list_parser.add_argument(
        "--status",
        choices=["todo", "open", "progress", "review", "done"],
        default="",
        help="상태 필터 (미지정 시 To Do/Done 제외 전체)",
    )

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
        cmd_create(args.title, args.command, args.status, args.number, debug=args.debug)

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

    elif args.subcommand == "update-prompt":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_update_prompt(
            ticket,
            command=args.command,
            goal=args.goal,
            target=args.target,
            constraints=args.constraints,
            criteria=args.criteria,
            context=args.context,
            skip_validation=args.skip_validation,
        )

    elif args.subcommand == "update-result":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_update_result(
            ticket,
            registrykey=args.registrykey,
            workdir=args.workdir,
            plan=args.plan,
            report=args.report,
        )

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

    elif args.subcommand == "list":
        cmd_list(status_filter=args.status)

    elif args.subcommand == "show":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"잘못된 티켓 번호 형식: '{args.ticket}'. T-NNN, NNN, #N 형식을 사용하세요.", 2)
        cmd_show(ticket)

    else:
        err(f"알 수 없는 서브커맨드: '{args.subcommand}'", 2)
