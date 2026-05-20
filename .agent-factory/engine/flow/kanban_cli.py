"""kanban_cli.py - 칸반 보드 서브커맨드 구현 및 CLI 파서 모듈.

서브커맨드별 비즈니스 로직(cmd_* 함수), argparse 파서 구성(build_parser),
서브커맨드 디스패치(dispatch)를 담당하는 비즈니스 계층 모듈이다.
kanban.py에서 분리되었으며, ticket_repository.py와 ticket_state.py에 의존한다.
"""

from __future__ import annotations

import argparse
import os
import re
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
    COLUMN_MAP,
    update_ticket_status,
    validate_transition,
)
from core.validation.prompt_validator import validate as prompt_validate
from constants import QUALITY_THRESHOLD


# ─── Path constant ──────────────────────────────────────────────────────────────────

from common import resolve_project_root

_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT: str = resolve_project_root()

# ─── Merge conflict signal pattern ──────────────────────────────────────────────────────

_CONFLICT_SIGNAL_RE: re.Pattern[str] = re.compile(
    r"(merge\s*conflict|merge\s+conflict|CONFLICT)",
    re.IGNORECASE,
)
"""merge_result.error_message 에서 충돌 신호를 감지하기 위한 정규식.

W05 테스트에서 ``from flow.kanban_cli import _CONFLICT_SIGNAL_RE`` 로 직접 import
가능하도록 모듈 레벨에 노출한다.

매칭 패턴:
- ``병합 충돌`` / ``병합충돌`` (한국어, 공백 선택적)
- ``merge conflict`` / ``Merge Conflict`` 등 (대소문자 무관)
- ``CONFLICT`` (git stdout 접두사 형식)
"""


# ─── Session Helper ──────────────────────────────────────────────────────────────────

import json
import urllib.request

_TMUX_WINDOW_PREFIX: str = "P:"


def _resolve_server_port() -> "int | None":
    """서버 포트를 해석한다.

    _WF_SERVER_PORT 환경변수 또는 .agent-factory/.board.url 파일에서 포트를 추출한다.

    Returns:
        포트 번호(int) 또는 None (해석 불가 시).
    """
    # 1) Environmental variables take precedence
    port_env = os.environ.get("_WF_SERVER_PORT")
    if port_env:
        try:
            return int(port_env)
        except ValueError:
            pass

    # 2) Parse .board.url file: http://127.0.0.1:PORT/board
    board_url_path = os.path.join(_PROJECT_ROOT, ".agent-factory", ".board.url")
    try:
        with open(board_url_path, "r", encoding="utf-8") as f:
            url = f.read().strip()
        # Extract PORT from http://127.0.0.1:PORT/... format
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
        # HTTP API path: Check the session list and kill the ticket_id matching session.
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
            # HTTP errors are unrelated to state transitions, so they are ignored and returned.
            return

    # tmux fallback when port is not interpreted (backwards compatible)
    if not os.environ.get("TMUX"):
        return

    window_name = f"{_TMUX_WINDOW_PREFIX}{ticket_number}"

    try:
        # Check if window exists
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

        # Window index search (prevents the problem of the colon in P:T-NNN being misinterpreted as session:window)
        idx_result = subprocess.run(
            ["tmux", "list-windows", "-F", "#{window_index}\t#{window_name}"],
            capture_output=True,
            text=True,
        )
        target = window_name  # fallback
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
        # Ignore tmux errors as they are independent of state transitions.
        pass


def _cleanup_worktree_on_leave(ticket_number: str) -> None:
    """In Progress에서 이탈할 때 연결된 워크트리를 자동 정리한다.

    워크트리 비활성 환경이거나 해당 티켓의 워크트리가 없으면 조용히 건너뛴다.
    미커밋 변경이 있는 경우 데이터 손실을 막기 위해 정리를 skip 하고
    사용자에게 경로를 명시한다 (T-411: 워커 commit 누락 / finalization 실패 시
    워크트리 자동 삭제로 인한 작업물 영구 손실 차단).
    정리 실패 시 경고만 출력하고 예외를 전파하지 않는다 (상태 전이 차단 금지).

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).
    """
    try:
        from flow.worktree_manager import (
            is_worktree_enabled,
            get_worktree_path,
            has_uncommitted_changes,
            remove_worktree,
        )

        if not is_worktree_enabled():
            return

        wt_path = get_worktree_path(ticket_number)
        if not wt_path:
            return

        if has_uncommitted_changes(wt_path):
            log(
                "WARN",
                f"kanban.py: skip worktree cleanup — preserve uncommitted changes ({ticket_number}, path={wt_path})",
            )
            print(
                f"[WARN] {ticket_number} worktree has uncommitted changes — skip automatic cleanup",
                flush=True,
            )
            print(f"[WARN] Path: {wt_path}", flush=True)
            print(
                "[WARN] Review and manually commit / discard:"
                f"`git -C {wt_path} status`",
                flush=True,
            )
            return

        success = remove_worktree(ticket_number, delete_branch=True)
        if success:
            log("INFO", f"kanban.py: Worktree automatic cleanup completed ({ticket_number})")
        else:
            print(f"[WARN] {ticket_number} work tree cleanup failed (continue)", flush=True)
    except ImportError:
        pass  # Ignored if the worktree module is not installed (backwards compatible)
    except Exception as e:
        print(f"[WARN] Error cleaning worktree {ticket_number} (continue): {e}", flush=True)


# ─── Subcommand implementation ─────────────────────────────────────────────────────────────


def cmd_create(
    title: str,
    command: str,
    status: str,
    number: str | None = None,
) -> None:
    """새 티켓 XML을 생성한다.

    번호 미지정 시 XML 파일명에서 최대 T-NNN 번호를 스캔하여 +1 자동 채번한다.
    번호 명시 시 정규화 후 동일 번호 충돌을 검사하고, 존재하면 에러로 거부한다.
    status 값에 따라 .kanban/todo/ 또는 .kanban/open/ 아래에 T-NNN.xml 파일을 생성한다.

    Args:
        title: 티켓 제목. 빈 문자열 허용.
        command: 워크플로우 커맨드 (implement, review, research 등). 현재 미사용 (하위 호환용).
        status: 초기 상태 키 ("todo" | "open"). COLUMN_MAP을 통해 XML <status> 값으로 변환된다.
        number: 명시적 티켓 번호 (T-NNN, NNN, #N format). Automatic numbering if not specified.
    """
    # Convert status key to status name ("To Do" / "Open")
    status_label = COLUMN_MAP.get(status)
    if status_label is None or status not in ("todo", "open"):
        err(
            f"Invalid --status value: '{status}'. Specify either 'todo' or 'open'."
            f"(Example: flow-kanban create \\"title\\" --command implement --status todo)",
            2,
        )

    # Determine the target directory
    target_dir = KANBAN_TODO_DIR if status == "todo" else KANBAN_OPEN_DIR

    if number is not None:
        normalized = normalize_ticket_number(number)
        if normalized is None:
            err(
                f"Invalid --number value: '{number}'. Must be in one of the following formats: T-NNN, NNN, or #N.",
                2,
            )
        ticket_number = normalized
        existing = find_ticket_file(ticket_number)
        if existing is not None:
            err(
                f"Ticket number conflict: {ticket_number} already exists ({existing})."
                f"The number must be unique.",
                2,
            )
    else:
        # Block automatic granting of debug area (900-999) — Repealed 2026-05-05 (workflow.md number area policy / memory rule).
        # Explicit `--number` calls have no effect as they are processed in the if branch above.
        max_num = get_max_ticket_number(exclude_debug_range=True)
        new_num = max_num + 1
        ticket_number = f"T-{new_num:03d}"

    # File name: T-NNN.xml fixed
    ticket_file = os.path.join(target_dir, f"{ticket_number}.xml")

    os.makedirs(target_dir, exist_ok=True)
    datetime_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    xml_content = create_ticket_xml(ticket_number, title, datetime_str, command=command)

    # Replace XML <status> tag value with status_label
    # create_ticket_xml records “Open” by default, so replace only when status=="todo".
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
        err(f"Failed to create ticket file: {e}")

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
        err(f"Invalid target column: '{target_key}'. Allowed values: {', '.join(COLUMN_MAP.keys())}")

    ticket_file = find_ticket_file(ticket_number)
    if ticket_file is None:
        err(f"Ticket file {ticket_number} not found")

    ticket_data = parse_ticket_xml(ticket_file)
    current_section = ticket_data["status"]

    # Validating state transition rules (using validate_transition)
    validation_error = validate_transition(current_section, target_section, force)
    if validation_error is not None:
        if validation_error == "":
            # Already in the same state
            print(f"{ticket_number} is already in {target_section} state.")
            return
        err(
            f"{ticket_number} is {validation_error}"
        )

    # After passing validate_transition, re-verify file existence before actual writing (race condition defense)
    if not os.path.isfile(ticket_file):
        # Another session may have already moved the file — seek again in the target directory.
        refreshed = find_ticket_file(ticket_number)
        if refreshed is None:
            err(f"{ticket_number} ticket file was lost in transit (race condition)")
        # Recheck status with rediscovered files
        refreshed_data = parse_ticket_xml(refreshed)
        if refreshed_data["status"] == target_section:
            print(f"{ticket_number} is already in {target_section} state. (processed in another session)")
            return
        # If moved to another state, re-validate transition rules after updating ticket_file
        ticket_file = refreshed
        current_section = refreshed_data["status"]
        validation_error = validate_transition(current_section, target_section, force)
        if validation_error is not None:
            if validation_error == "":
                print(f"{ticket_number} is already in {target_section} state.")
                return
            err(f"{ticket_number} is {validation_error}")

    # Update XML <status>
    try:
        update_ticket_status(ticket_file, target_section)
    except FileNotFoundError:
        # write_ticket_xml detects file loss — check for idempotency after re-scanning
        refreshed = find_ticket_file(ticket_number)
        if refreshed is None:
            err(f"{ticket_number} ticket file was lost updating status (race condition)")
        refreshed_data = parse_ticket_xml(refreshed)
        if refreshed_data["status"] == target_section:
            print(f"{ticket_number} is already in {target_section} state. (processed in another session)")
            return
        err(f"File loss detected during {ticket_number} status update. Current status: {refreshed_data['status']}")

    # Move files to the directory corresponding to the state
    try:
        new_path = move_ticket_to_status_dir(ticket_file, target_section)
        if new_path != ticket_file:
            src_rel = os.path.relpath(ticket_file, _PROJECT_ROOT)
            dst_rel = os.path.relpath(new_path, _PROJECT_ROOT)
            print(f"Move file: {src_rel} ​​→ {dst_rel}")
        ticket_file = new_path
    except FileNotFoundError:
        # File loss during movement — handle normally if already moved
        refreshed = find_ticket_file(ticket_number)
        if refreshed is not None:
            refreshed_data = parse_ticket_xml(refreshed)
            if refreshed_data["status"] == target_section:
                print(f"{ticket_number} is already in {target_section} state. (processed in another session)")
                return
        err(f"{ticket_number} file loss detection during movement")
    except OSError as e:
        err(f"Failed to move ticket file: {e}")

    print(f"{ticket_number}: {current_section} → {target_section}")
    log("INFO", f"kanban.py: move {ticket_number} {current_section} → {target_section}")

    # Automatic cleanup of work tree when leaving In Progress
    # Automatic cleanup only in In Progress → Open (rework) / To Do (demotion) transitions.
    if current_section == "In Progress" and target_section != "Review":
        _cleanup_worktree_on_leave(ticket_number)

    # Automatically kill session when transitioning to Open:
    # Returning from In Progress to Open ends the active session for that ticket.
    # Since it is executed after a successful state transition, it does not reach this point if the transition fails (SystemExit after calling err()).
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
    # ── Worktree merge hook (before changing ticket status/moving files) ──
    import sys as _sys
    try:
        from flow.worktree_manager import is_worktree_enabled, get_worktree_path, merge_to_develop, has_uncommitted_changes
        from flow.branch_strategy import get_feature_branch_for_ticket
        if is_worktree_enabled():
            # C-01: Detect dirty worktree → Reject if uncommitted changes exist
            _wt_path = get_worktree_path(ticket_number)
            if _wt_path and has_uncommitted_changes(_wt_path):
                _porcelain = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=_wt_path,
                    capture_output=True,
                    text=True,
                )
                print(f"[ERROR] This is a work tree with uncommitted changes. Done Blocks the transition.", flush=True)
                print(f"List of uncommitted files:", flush=True)
                for _line in _porcelain.stdout.strip().splitlines():
                    print(f"    - {_line.strip()}", flush=True)
                print(f"Complete with the normal path using flow-merge.", flush=True)
                _sys.exit(1)
            feat_branch = get_feature_branch_for_ticket(ticket_number)
            if _wt_path or feat_branch:
                merge_result = merge_to_develop(ticket_number)
                if not merge_result.success:
                    # Collision decision redundancy:
                    # (1) merge_result.conflicts is not empty
                    # (2) Conflict signal pattern included in error_message
                    # (3) There is sentinel "<unknown-conflict>" in conflicts
                    # If any one of the three is satisfied, it is considered a conflict and the Done transition is blocked.
                    _sentinel = "<unknown-conflict>"
                    _has_conflict_files = bool(merge_result.conflicts)
                    _has_signal_in_msg = bool(
                        _CONFLICT_SIGNAL_RE.search(merge_result.error_message or "")
                    )
                    _has_sentinel = _sentinel in (merge_result.conflicts or [])
                    _is_conflict = _has_conflict_files or _has_signal_in_msg or _has_sentinel

                    if _is_conflict:
                        print(f"[ERROR] {ticket_number} merge conflict occurred. Done Blocks the transition.", flush=True)
                        # Output a list of conflicting files — if there is only sentinel or the list is empty, replaced by an instruction message
                        if merge_result.conflicts and not (
                            len(merge_result.conflicts) == 1 and merge_result.conflicts[0] == _sentinel
                        ):
                            print(f"Conflicting files:", flush=True)
                            for cf in merge_result.conflicts:
                                print(f"    - {cf}", flush=True)
                        else:
                            print(
                                f"(List of conflicting files unknown — see error_message)",
                                flush=True,
                            )
                            if merge_result.error_message:
                                print(f"  error_message: {merge_result.error_message}", flush=True)
                        print(f"Please resolve the conflict in the worktree and try again.", flush=True)
                        _sys.exit(1)
                    else:
                        # Conflict pattern check false — Simple failure (e.g. develop checkout failed): print warning and continue
                        print(f"[WARN] Worktree merge failed: {merge_result.error_message}", flush=True)
                else:
                    print(f"{ticket_number}: {merge_result.merged_branch} -> develop merge completed ({merge_result.merge_commit[:8]})", flush=True)
                    log("INFO", f"kanban.py: worktree merge {merge_result.merged_branch} -> develop ({merge_result.merge_commit[:8]})")
                    if merge_result.merge_commit:
                        try:
                            _ticket_file_for_result = find_ticket_file(ticket_number)
                            if _ticket_file_for_result is not None:
                                update_result(_ticket_file_for_result, {"merge_commit": merge_result.merge_commit})
                                log("INFO", f"kanban.py: save result.merge_commit ({merge_result.merge_commit[:8]})")
                        except Exception as _ur_err:
                            print(f"[WARN] result.merge_commit failed to save (continue): {_ur_err}", flush=True)
    except ImportError:
        pass  # Ignored if the worktree module is not installed (backwards compatible)
    except Exception as _wt_err:
        print(f"[WARN] Error processing worktree merge (continued): {_wt_err}", flush=True)

    ticket_file = find_ticket_file(ticket_number)
    if ticket_file is None:
        err(f"Ticket file {ticket_number} not found")

    ticket_data = parse_ticket_xml(ticket_file)
    current_section = ticket_data["status"]

    # XML <status> updated with Done
    update_ticket_status(ticket_file, "Done")

    # Move the file to kanban/done/T-NNN.xml
    if os.path.isfile(ticket_file):
        try:
            new_path = move_ticket_to_status_dir(ticket_file, "Done")
            if new_path != ticket_file:
                src_rel = os.path.relpath(ticket_file, _PROJECT_ROOT)
                dst_rel = os.path.relpath(new_path, _PROJECT_ROOT)
                print(f"Move file: {src_rel} ​​→ {dst_rel}")
        except OSError as e:
            err(f"Failed to move ticket file: {e}")

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
        err(f"Ticket {ticket_number} not found")

    try:
        os.remove(ticket_file)
    except OSError as e:
        err(f"Failed to delete ticket file: {e}")

    print(f"{ticket_number}: deleted")


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
        err(f"Ticket file {ticket_number} not found")

    try:
        tree = ET.parse(ticket_file)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"Failed to parse ticket file ({ticket_file}): {e}")

    # First search for <title> inside the <metadata> wrapper
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

    print(f"{ticket_number}: Title → {title}")


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
        err(f"Ticket file {ticket_number} not found")

    try:
        tree = ET.parse(ticket_file)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"Failed to parse ticket file ({ticket_file}): {e}")

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
        err(f"Ticket file {ticket_number} not found")

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
        err("There are no fields to update.", 2)

    update_prompt(ticket_file, updates)
    print(f"{ticket_number}: prompt updated")

    # ── Quality verification ────────────────────────────────────────────────────────────
    if skip_validation:
        return

    try:
        with open(ticket_file, "r", encoding="utf-8") as f:
            xml_text = f.read()
    except OSError as e:
        _sys.stderr.write(f"[WARN] Failed to reread quality verification file: {e} \n")
        return

    # Flat structure: directly extract text inside <prompt> tag
    try:
        from core.validation.prompt_validator import extract_active_prompt
        prompt_text = extract_active_prompt(xml_text)
    except Exception:
        # Skip verification if extract_active_prompt fails
        return

    validation_result = prompt_validate(prompt_text)
    quality_score = validation_result["quality_score"]

    if quality_score < QUALITY_THRESHOLD:
        _sys.stderr.write(
            f"[ERROR] Quality verification failed (score={quality_score:.4f} < threshold={QUALITY_THRESHOLD}) \n"
        )
        if validation_result["missing_tags"]:
            _sys.stderr.write(
                f"Missing tags: {', '.join(validation_result['missing_tags'])} \n"
            )
        if validation_result["empty_tags"]:
            _sys.stderr.write(
                f"Empty tags: {', '.join(validation_result['empty_tags'])} \n"
            )
        if validation_result["feedback"]:
            _sys.stderr.write("Feedback: \n")
            for fb in validation_result["feedback"]:
                _sys.stderr.write(f"    - {fb}\n")
        _sys.exit(1)


def cmd_update_result(
    ticket_number: str,
    registrykey: str = "",
    workdir: str = "",
    plan: str = "",
    report: str = "",
    merge_commit: str = "",
) -> None:
    """티켓 XML의 <result> 하위 요소를 갱신한다.

    Args:
        ticket_number: 티켓 번호 (T-NNN 형식).
        registrykey: 워크플로우 registryKey (YYYYMMDD-HHMMSS 형식).
        workdir: 워크플로우 산출물 디렉터리 상대 경로.
        plan: plan.md 상대 경로.
        report: report.md 상대 경로.
        merge_commit: feature -> develop 머지 커밋 SHA (40자 hex).

    Raises:
        SystemExit: 티켓 파일을 찾을 수 없거나 쓰기 실패 시.
    """
    ticket_file = find_ticket_file(ticket_number)
    if ticket_file is None:
        err(f"Ticket file {ticket_number} not found")

    updates: dict[str, str] = {}
    if registrykey:
        updates["registrykey"] = registrykey
    if workdir:
        updates["workdir"] = workdir
    if plan:
        updates["plan"] = plan
    if report:
        updates["report"] = report
    if merge_commit:
        updates["merge_commit"] = merge_commit

    if not updates:
        err("There are no fields to update.", 2)

    update_result(ticket_file, updates)
    print(f"{ticket_number}: result updated")


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
        err(f"Ticket {ticket_number} not found")

    ticket_data = parse_ticket_xml(ticket_file)

    number: str = ticket_data.get("number", ticket_number)
    title: str = ticket_data.get("title", "")
    status: str = ticket_data.get("status", "")
    command: str = ticket_data.get("command", "")
    prompt_data: dict = ticket_data.get("prompt", {}) or {}
    result_data: dict | None = ticket_data.get("result")
    relations: list = ticket_data.get("relations", [])

    # ── Header and metadata output ───────────────────────────────────────────────
    print(f"## {number}: {title}")
    print()
    print("### Metadata")
    print(f"- Number: {number}")
    print(f"- Title: {title}")
    print(f"- Status: {status}")
    if command:
        print(f"- Command: {command}")

    # ── Output relationship information ──────────────────────────────────────────────────────────
    if relations:
        print()
        print("### Relations")
        for rel in relations:
            rel_type: str = rel.get("type", "")
            rel_ticket: str = rel.get("ticket", "")
            print(f"- {rel_type}: {rel_ticket}")

    # ── Prompt output ───────────────────────────────────────────────────────────
    has_prompt = any(prompt_data.get(k) for k in ("goal", "target", "constraints", "criteria", "context"))
    if not has_prompt:
        print()
        print("(no prompt)")
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

    # ── Output result information ────────────────────────────────────────────────────────
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


# ─── Relationship Bidirectional Mapping ───────────────────────────────────────────────────────────
# For each relationship option (type to write to source, reverse type to write to destination)
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
        err(f"Target ticket {target_ticket} file not found")

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
        err(f"Ticket file {ticket_number} not found")

    options = {"depends_on": depends_on, "derived_from": derived_from, "blocks": blocks}
    applied = []

    for option_name, target in options.items():
        if not target:
            continue
        normalized = normalize_ticket_number(target)
        if normalized is None:
            err(f"Invalid ticket number format: '{target}'. Use the format T-NNN, NNN, #N.", 2)
        _apply_relation(source_file, ticket_number, normalized, option_name)
        forward_type = _RELATION_PAIRS[option_name][0]
        applied.append(f"{forward_type} {normalized}")

    for desc in applied:
        print(f"{ticket_number}: {desc} relationship added")
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
        err(f"Ticket file {ticket_number} not found")

    options = {"depends_on": depends_on, "derived_from": derived_from, "blocks": blocks}
    removed = []

    for option_name, target in options.items():
        if not target:
            continue
        normalized = normalize_ticket_number(target)
        if normalized is None:
            err(f"Invalid ticket number format: '{target}'. Use the format T-NNN, NNN, #N.", 2)
        _apply_relation(source_file, ticket_number, normalized, option_name, remove=True)
        forward_type = _RELATION_PAIRS[option_name][0]
        removed.append(f"{forward_type} {normalized}")

    for desc in removed:
        print(f"{ticket_number}: {desc} relationship removed")
    log("INFO", f"kanban.py: unlink {ticket_number} {', '.join(removed)}")


def cmd_board() -> None:
    """칸반 보드 전체 현황을 마크다운 테이블 형식으로 출력한다.

    .kanban/todo/, .kanban/open/, .kanban/progress/, .kanban/review/ 디렉터리를 각각 스캔하여
    To Do/Open/In Progress/Review 칼럼에 직접 매핑하고, .kanban/done/ 디렉터리의
    티켓을 Done 칼럼에 그룹핑하여 출력한다.
    Done 칼럼은 최근 10건만 표시하고 총 건수를 함께 출력한다.
    각 칼럼에 티켓이 없으면 "(doesn't exist)"을 출력한다.

    출력 포맷:
        ## Kanban Board

        ### To Do
        | Ticket | Title | Command |
        ...

        ### Done (N total, display the most recent 10)
        | Ticket | Title |
        ...
    """
    # ── Column definition ─────────────────────────────────────────────────────────────────
    COLUMNS = ["To Do", "Open", "In Progress", "Review", "Done"]
    grouped: dict[str, list[dict]] = {col: [] for col in COLUMNS}

    # ── Directory scan by status (directory is SSoT) ─────────────────────────────────
    # Directory -> Column Mapping: todo/ -> To Do, open/ -> Open, progress/ -> In Progress, review/ -> Review
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
                log("WARN", f"kanban.py: board - parse_ticket_xml failed: {fname}")
                continue

            grouped[column].append({
                "number": ticket_data.get("number", ""),
                "title": ticket_data.get("title", ""),
                "command": ticket_data.get("command", ""),
            })

    # ── done Directory scan ───────────────────────────────────────────────────────
    if os.path.isdir(KANBAN_DONE_DIR):
        for fname in os.listdir(KANBAN_DONE_DIR):
            if not (fname.startswith("T-") and fname.endswith(".xml")):
                continue
            fpath = os.path.join(KANBAN_DONE_DIR, fname)
            try:
                ticket_data = parse_ticket_xml(fpath)
            except SystemExit:
                log("WARN", f"kanban.py: board - parse_ticket_xml failed: {fname}")
                continue

            grouped["Done"].append({
                "number": ticket_data.get("number", ""),
                "title": ticket_data.get("title", ""),
                "command": "",
            })

    # ── Sort by number (T-NNN → NNN number ascending) ───────────────────────────
    def _ticket_sort_key(t: dict) -> int:
        num_str = t.get("number", "T-0").lstrip("T-")
        return int(num_str) if num_str.isdigit() else 0

    for col in COLUMNS[:-1]:  # To Do, Open, In Progress, Review
        grouped[col].sort(key=_ticket_sort_key)

    # Done displays only the 10 most recent items in descending number order (newest first).
    grouped["Done"].sort(key=_ticket_sort_key, reverse=True)
    done_total = len(grouped["Done"])
    grouped["Done"] = grouped["Done"][:10]

    # ── Output ────────────────────────────────────────────────────────────────────
    print("## Kanban Board")

    for col in COLUMNS[:-1]:  # To Do, Open, In Progress, Review
        print(f"\n### {col}")
        tickets = grouped[col]
        if not tickets:
            print("(doesn't exist)")
        else:
            print("| Ticket | Title | Command |")
            print("|--------|-------|---------|")
            for t in tickets:
                number = t["number"]
                title = t["title"]
                command = t["command"]
                print(f"| {number}  | {title} | {command} |")

    # Done column
    print(f"\n ### Done (Total {done_total}, showing the most recent 10)")
    tickets = grouped["Done"]
    if not tickets:
        print("(doesn't exist)")
    else:
        print("| Ticket | Title |")
        print("|--------|-------|")
        for t in tickets:
            number = t["number"]
            title = t["title"]
            print(f"| {number}  | {title} |")


# State key -> (directory, display state name) mapping
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
        # Default: open + progress + review (excluding todo, done)
        # - todo: Excluding default exposure due to backlog nature (exposed only when --status todo is specified)
        # - done: Completed tickets exclude basic exposure
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

    # Sort in ascending order by number (T-NNN → NNN number conversion)
    def _sort_key(t: dict[str, str]) -> int:
        num_str = t.get("number", "T-0").lstrip("T-")
        return int(num_str) if num_str.isdigit() else 0

    tickets.sort(key=_sort_key)

    if not tickets:
        print("(no tickets)")
        return

    for t in tickets:
        print(f"{t['number']}  [{t['status']}]  {t['title']}")


# ─── argparse settings ──────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """argparse 기반 CLI 파서를 구성하여 반환한다.

    Returns:
        구성된 ArgumentParser 인스턴스.
    """
    parser = argparse.ArgumentParser(
        prog="kanban.py",
        description="Kanban Board Status Management CLI",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # create subcommand
    create_parser = subparsers.add_parser("create", help="Create a new ticket")
    create_parser.add_argument("title", help="ticket title")
    create_parser.add_argument("--command", default="", help="Workflow commands (implement, review, research, etc.)")
    create_parser.add_argument(
        "--status",
        required=True,
        choices=["todo", "open"],
        metavar="{todo,open}",
        help=(
            "Initial state (required). 'todo'=backlog·things to do in the future, 'open'=target of focus now."
            "Example: flow-kanban create \\"title\\" --command implement --status todo"
        ),
    )
    create_parser.add_argument(
        "--number",
        default=None,
        help=(
            "Specify ticket number (in the format T-NNN, NNN, #N). Automatic numbering if not specified."
            "Error when the same number exists."
        ),
    )

    # move subcommand
    move_parser = subparsers.add_parser("move", help="Move the ticket to the specified column")
    move_parser.add_argument("ticket", help="Ticket number (T-NNN, NNN, #N format)")
    move_parser.add_argument(
        "target",
        choices=list(COLUMN_MAP.keys()),
        help="Target column (todo/open/progress/review/done)",
    )
    move_parser.add_argument("--force", action="store_true", help="Ignore state transition rules and force movement")

    # done subcommand
    done_parser = subparsers.add_parser("done", help="Move the ticket to Done and the file to .kanban/done/")
    done_parser.add_argument("ticket", help="Ticket number (T-NNN, NNN, #N format)")

    # delete subcommand
    delete_parser = subparsers.add_parser("delete", help="Delete the ticket")
    delete_parser.add_argument("ticket", help="Ticket number (T-NNN, NNN, #N format)")

    # update-prompt subcommand
    update_prompt_parser = subparsers.add_parser("update-prompt", help="Update ticket prompt and command")
    update_prompt_parser.add_argument("ticket", help="Ticket number (T-NNN, NNN, #N format)")
    update_prompt_parser.add_argument("--command", default="", help="Workflow commands (implement, review, research, etc.)")
    update_prompt_parser.add_argument("--goal", default="", help="work goal")
    update_prompt_parser.add_argument("--target", default="", help="Target")
    update_prompt_parser.add_argument("--constraints", default="", help="Constraints (optional, prompt 5 elements)")
    update_prompt_parser.add_argument("--criteria", default="", help="Completion criteria (optional, prompt 5 elements)")
    update_prompt_parser.add_argument("--context", default="", help="Contextual information (optional, prompt 5 elements)")
    update_prompt_parser.add_argument("--skip-validation", action="store_true", default=False, help="Bypass quality verification (for emergency use)")

    # update-result subcommand
    update_result_parser = subparsers.add_parser("update-result", help="Update the result information of the ticket")
    update_result_parser.add_argument("ticket", help="Ticket number (T-NNN, NNN, #N format)")
    update_result_parser.add_argument("--registrykey", default="", help="Workflow registryKey (YYYYMMDD-HHMMSS format)")
    update_result_parser.add_argument("--workdir", default="", help="Workflow output directory relative path")
    update_result_parser.add_argument("--plan", default="", help="plan.md relative path")
    update_result_parser.add_argument("--report", default="", help="report.md relative path")
    update_result_parser.add_argument("--merge-commit", dest="merge_commit", default="", help="feature -> develop merge commit SHA")

    # set-editing subcommand
    set_editing_parser = subparsers.add_parser("set-editing", help="Set the <editing> flag in the ticket XML.")
    set_editing_parser.add_argument("ticket", help="Ticket number (T-NNN, NNN, #N format)")
    set_editing_group = set_editing_parser.add_mutually_exclusive_group(required=True)
    set_editing_group.add_argument("--on", action="store_true", help="Set state to editing")
    set_editing_group.add_argument("--off", action="store_true", help="Turn off editing state")

    # update-title subcommand (update is an alias for update-title)
    update_title_parser = subparsers.add_parser("update-title", help="Update ticket title")
    update_title_parser.add_argument("ticket", help="Ticket number (T-NNN, NNN, #N format)")
    update_title_parser.add_argument("title", nargs="?", default="", help="new title")
    update_title_parser.add_argument("--title", dest="title_flag", default="", help="New title (format --title)")
    update_alias = subparsers.add_parser("update", help="alias for update-title")
    update_alias.add_argument("ticket", help="Ticket number (T-NNN, NNN, #N format)")
    update_alias.add_argument("title", nargs="?", default="", help="new title")
    update_alias.add_argument("--title", dest="title_flag", default="", help="New title (format --title)")

    # link subcommand
    link_parser = subparsers.add_parser("link", help="Records relationships between tickets in both directions")
    link_parser.add_argument("ticket", help="Ticket number (T-NNN, NNN, #N format)")
    link_parser.add_argument("--depends-on", dest="depends_on", default="", help="Depends on ticket number")
    link_parser.add_argument("--derived-from", dest="derived_from", default="", help="Derived original ticket number")
    link_parser.add_argument("--blocks", default="", help="Ticket number to block")

    # unlink subcommand
    unlink_parser = subparsers.add_parser("unlink", help="Remove relationships between tickets in both directions")
    unlink_parser.add_argument("ticket", help="Ticket number (T-NNN, NNN, #N format)")
    unlink_parser.add_argument("--depends-on", dest="depends_on", default="", help="Depends on ticket number")
    unlink_parser.add_argument("--derived-from", dest="derived_from", default="", help="Derived original ticket number")
    unlink_parser.add_argument("--blocks", default="", help="Ticket number to block")

    # board subcommand
    subparsers.add_parser("board", help="Check the overall status of the Kanban board")

    # list subcommand
    list_parser = subparsers.add_parser("list", help="View Kanban ticket list")
    list_parser.add_argument(
        "--status",
        choices=["todo", "open", "progress", "review", "done"],
        default="",
        help="Status filter (all except To Do/Done if not specified)",
    )

    # show subcommand
    show_parser = subparsers.add_parser("show", help="View detailed information on a specific ticket")
    show_parser.add_argument("ticket", help="Ticket number (T-NNN, NNN, #N format)")

    return parser


# ─── Dispatch ──────────────────────────────────────────────────────────────────


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
        cmd_create(args.title, args.command, args.status, args.number)

    elif args.subcommand == "move":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"Invalid ticket number format: '{args.ticket}'. Use the format T-NNN, NNN, #N.", 2)
        cmd_move(ticket, args.target, force=args.force)

    elif args.subcommand == "done":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"Invalid ticket number format: '{args.ticket}'. Use the format T-NNN, NNN, #N.", 2)
        cmd_done(ticket)

    elif args.subcommand == "delete":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"Invalid ticket number format: '{args.ticket}'. Use the format T-NNN, NNN, #N.", 2)
        cmd_delete(ticket)

    elif args.subcommand == "update-prompt":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"Invalid ticket number format: '{args.ticket}'. Use the format T-NNN, NNN, #N.", 2)
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
            err(f"Invalid ticket number format: '{args.ticket}'. Use the format T-NNN, NNN, #N.", 2)
        cmd_update_result(
            ticket,
            registrykey=args.registrykey,
            workdir=args.workdir,
            plan=args.plan,
            report=args.report,
            merge_commit=args.merge_commit,
        )

    elif args.subcommand == "set-editing":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"Invalid ticket number format: '{args.ticket}'. Use the format T-NNN, NNN, #N.", 2)
        cmd_set_editing(ticket, args.on)

    elif args.subcommand in ("update-title", "update"):
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"Invalid ticket number format: '{args.ticket}'. Use the format T-NNN, NNN, #N.", 2)
        title = args.title or getattr(args, "title_flag", "") or ""
        if not title:
            err("You must specify a title. Example: flow-kanban update-title T-001 \\"New title\\"", 2)
        cmd_update_title(ticket, title)

    elif args.subcommand == "link":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"Invalid ticket number format: '{args.ticket}'. Use the format T-NNN, NNN, #N.", 2)
        if not args.depends_on and not args.derived_from and not args.blocks:
            err("At least one of --depends-on, --derived-from, and --blocks must be specified.", 2)
        cmd_link(
            ticket,
            depends_on=args.depends_on,
            derived_from=args.derived_from,
            blocks=args.blocks,
        )

    elif args.subcommand == "unlink":
        ticket = normalize_ticket_number(args.ticket)
        if ticket is None:
            err(f"Invalid ticket number format: '{args.ticket}'. Use the format T-NNN, NNN, #N.", 2)
        if not args.depends_on and not args.derived_from and not args.blocks:
            err("At least one of --depends-on, --derived-from, and --blocks must be specified.", 2)
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
            err(f"Invalid ticket number format: '{args.ticket}'. Use the format T-NNN, NNN, #N.", 2)
        cmd_show(ticket)

    else:
        err(f"Unknown subcommand: '{args.subcommand}'", 2)
