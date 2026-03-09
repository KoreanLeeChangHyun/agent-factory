#!/usr/bin/env -S python3 -u
"""
initialization.py - 워크플로우 초기화 스크립트.

오케스트레이터가 command, mode, title을 인자로 전달하면
작업 디렉터리 생성 + 메타데이터 기록을 수행한다.
LLM 호출 없음 (순수 IO).

사용법:
  python3 initialization.py <command> <mode> <title>

인자:
  command  실행 명령어. implement | review | research
  mode     워크플로우 모드. full (유일 지원 모드)
  title    오케스트레이터가 생성한 20자 이내 제목

환경변수:
  TICKET_NUMBER  티켓 번호 (T-NNN 또는 NNN 형식). 미지정 시 board.md에서 자동 선택.

출력:
  stdout으로 init-result JSON을 출력한다.
  오케스트레이터는 Bash 실행 결과에서 직접 파싱한다 (Read 불필요).

종료 코드:
  0  성공
  1  티켓 파일 없음 또는 비어있음
  2  인자 오류
  4  워크플로우 초기화 실패

생성 파일:
  <workDir>/user_prompt.txt   사용자 원문 요청 보존
  <workDir>/.context.json     작업 메타데이터 (title, workId, command 등)
  <workDir>/status.json       FSM 상태 (phase: NONE, mode, transitions)
  <workDir>/files/            .uploads/ 에서 복사된 첨부 파일 (있을 경우)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime
from typing import Any, NoReturn

# ─── 경로 상수 ───────────────────────────────────────────────────────────────

_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT: str = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
_SCRIPTS_DIR: str = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from data.constants import C_CLAUDE, C_DIM, C_RESET, KST, KEEP_COUNT, VALID_COMMANDS, VALID_MODES, WORK_NAME_MAX_LEN


# ─── 유틸리티 ────────────────────────────────────────────────────────────────


def _append_log(abs_work_dir: str, level: str, message: str) -> None:
    """워크플로우 로그에 이벤트를 기록한다."""
    try:
        from datetime import datetime, timezone, timedelta
        kst = timezone(timedelta(hours=9))
        ts = datetime.now(kst).strftime("%Y-%m-%dT%H:%M:%S")
        log_path = os.path.join(abs_work_dir, "workflow.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {message}\n")
    except Exception:
        pass


def _err(msg: str, code: int = 1) -> NoReturn:
    print("FAIL", flush=True)
    print(f"에러: {msg}", file=sys.stderr)
    sys.exit(code)


def _warn(msg: str) -> None:
    print(f"[WARN] {msg}", file=sys.stderr)


def _sanitize_work_name(title: str) -> str:
    """제목을 파일시스템 안전한 디렉터리명으로 변환한다."""
    name: str = re.sub(r"\s+", "-", title.strip())
    name = re.sub(r"[!@#%^&*()/:;<>?|~\"'`\\${}[\]]", "", name)
    name = re.sub(r"\.", "-", name)
    name = re.sub(r"-{2,}", "-", name)
    name = name.strip("-")
    return name[:WORK_NAME_MAX_LEN]


def _atomic_write_json(path: str, data: dict[str, Any]) -> None:
    """JSON 데이터를 원자적으로 파일에 기록한다.

    임시 파일에 먼저 쓴 후 최종 경로로 이동하여 파일 시스템 원자성을 보장한다.

    Args:
        path: 기록할 파일의 절대 경로
        data: JSON 직렬화할 딕셔너리 데이터
    """
    dir_name: str = os.path.dirname(path)
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        shutil.move(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _run_optional_script(script_path: str, cmd_template: list[str]) -> None:
    """스크립트 파일이 존재하는 경우에만 실행한다 (비차단).

    스크립트가 없거나 실패해도 예외를 전파하지 않는다.

    Args:
        script_path: 실행할 스크립트 절대 경로
        cmd_template: 명령어 템플릿 리스트. '{}'는 script_path로 치환됨
    """
    if not os.path.isfile(script_path):
        return
    cmd: list[str] = [part.replace("{}", script_path) for part in cmd_template]
    try:
        subprocess.run(cmd, timeout=30, capture_output=True)
    except Exception:
        pass


# ─── Step 1: 티켓 파일 읽기 ──────────────────────────────────────────────────


def _resolve_ticket_number(ticket_arg: str | None = None) -> str | None:
    """티켓 번호를 결정한다.

    환경변수 TICKET_NUMBER → 커맨드 인자 → board.md 자동 선택 순으로 탐색한다.

    Args:
        ticket_arg: 커맨드 인자에서 추출된 티켓 번호 문자열 (예: '#1', 'T-001', '1'). 없으면 None.

    Returns:
        'T-NNN' 형식 티켓 번호 문자열. 결정 불가능하면 None.
    """
    # 1순위: 환경변수
    env_ticket: str = os.environ.get("TICKET_NUMBER", "").strip()
    if env_ticket:
        return _normalize_ticket_number(env_ticket)

    # 2순위: 커맨드 인자
    if ticket_arg:
        normalized = _normalize_ticket_number(ticket_arg)
        if normalized:
            return normalized

    # 3순위: board.md에서 Open 상태 티켓 자동 선택
    return _find_open_ticket_from_board()


def _normalize_ticket_number(raw: str) -> str | None:
    """티켓 번호 문자열을 'T-NNN' 형식으로 정규화한다.

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


def _find_open_ticket_from_board() -> str | None:
    """board.md의 Open 섹션에서 첫 번째 미완료 티켓 번호를 반환한다.

    board.md 파일의 '## Open' 섹션을 파싱하여 '- [ ] T-NNN:' 패턴의
    첫 번째 항목을 찾는다. Open 섹션이 없거나 티켓이 없으면 None을 반환한다.

    Returns:
        'T-NNN' 형식 티켓 번호. 없으면 None.
    """
    board_path: str = os.path.join(_PROJECT_ROOT, ".kanban", "board.md")
    if not os.path.isfile(board_path):
        return None
    try:
        with open(board_path, "r", encoding="utf-8") as f:
            content: str = f.read()
    except OSError:
        return None

    in_open_section: bool = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_open_section = stripped == "## Open"
            continue
        if in_open_section:
            match = re.match(r"^-\s+\[\s*\]\s+(T-\d+)\s*:", stripped)
            if match:
                return _normalize_ticket_number(match.group(1))
    return None


def read_prompt(ticket_arg: str | None = None) -> tuple[str | None, str | None]:
    """티켓 파일 내용을 읽어 반환한다.

    티켓 번호를 결정한 후 .kanban/T-NNN.txt 파일을 읽는다.
    파일이 없거나 내용이 비어있으면 None을 반환한다.

    Args:
        ticket_arg: 커맨드 인자에서 추출된 티켓 번호 (예: '#1'). 없으면 None.

    Returns:
        (티켓 파일 내용 문자열, 티켓 번호 문자열) 튜플.
        파일 없음 또는 빈 내용이면 (None, None).
    """
    ticket_number: str | None = _resolve_ticket_number(ticket_arg)
    if ticket_number is None:
        return None, None

    ticket_file: str = os.path.join(_PROJECT_ROOT, ".kanban", f"{ticket_number}.txt")
    if not os.path.isfile(ticket_file):
        return None, None
    with open(ticket_file, "r", encoding="utf-8") as f:
        content: str = f.read()
    if not content.strip():
        return None, None
    return content, ticket_number


# ─── Step 2: 워크플로우 초기화 ───────────────────────────────────────────────


def _create_work_dir(abs_work_dir: str) -> None:
    """워크플로우 디렉터리를 생성한다.

    디렉터리가 이미 존재해도 오류 없이 진행한다.
    빈 workflow.log 파일을 함께 생성한다.

    Args:
        abs_work_dir: 생성할 작업 디렉터리 절대 경로
    """
    os.makedirs(abs_work_dir, exist_ok=True)
    # workflow.log 빈 파일 생성
    try:
        open(os.path.join(abs_work_dir, "workflow.log"), "a").close()
    except Exception:
        pass


def _write_user_prompt(abs_work_dir: str, prompt_content: str) -> None:
    """user_prompt.txt를 작업 디렉터리에 작성한다.

    Args:
        abs_work_dir: 작업 디렉터리 절대 경로
        prompt_content: 사용자 원문 프롬프트 내용
    """
    with open(os.path.join(abs_work_dir, "user_prompt.txt"), "w", encoding="utf-8") as f:
        f.write(prompt_content)


def _copy_uploads(abs_work_dir: str) -> None:
    """.uploads/ 디렉터리의 파일을 <workDir>/files/로 복사 후 원본 삭제.

    .uploads/ 디렉터리가 없거나 비어있으면 아무것도 하지 않는다.

    Args:
        abs_work_dir: 복사 대상 작업 디렉터리 절대 경로
    """
    uploads_dir: str = os.path.join(_PROJECT_ROOT, ".uploads")
    if not os.path.isdir(uploads_dir) or not os.listdir(uploads_dir):
        return
    files_dir: str = os.path.join(abs_work_dir, "files")
    os.makedirs(files_dir, exist_ok=True)
    for item in os.listdir(uploads_dir):
        src: str = os.path.join(uploads_dir, item)
        dst: str = os.path.join(files_dir, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    for item in os.listdir(uploads_dir):
        item_path: str = os.path.join(uploads_dir, item)
        if os.path.isdir(item_path):
            shutil.rmtree(item_path)
        else:
            os.unlink(item_path)


def _move_ticket_to_in_progress(ticket_number: str) -> None:
    """board.md에서 해당 티켓을 Open → In Progress 섹션으로 이동한다.

    board.md의 Open 섹션에서 해당 티켓 항목을 제거하고,
    In Progress 섹션에 추가한다.
    파일 조작 실패 시 경고만 출력하고 계속 진행한다.

    Args:
        ticket_number: 이동할 티켓 번호 (예: 'T-001')
    """
    board_path: str = os.path.join(_PROJECT_ROOT, ".kanban", "board.md")
    if not os.path.isfile(board_path):
        _warn(f"board.md를 찾을 수 없습니다: {board_path}")
        return

    try:
        with open(board_path, "r", encoding="utf-8") as f:
            lines: list[str] = f.readlines()
    except OSError as e:
        _warn(f"board.md 읽기 실패: {e}")
        return

    # Open 섹션에서 해당 티켓 항목 추출
    ticket_pattern = re.compile(rf"^-\s+\[\s*\]\s+{re.escape(ticket_number)}\s*:")
    ticket_line: str | None = None
    new_lines: list[str] = []
    in_open_section: bool = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            in_open_section = stripped == "## Open"
        if in_open_section and ticket_pattern.match(stripped):
            ticket_line = line.rstrip("\n")
            continue  # Open 섹션에서 제거
        new_lines.append(line)

    if ticket_line is None:
        _warn(f"{ticket_number}을 board.md Open 섹션에서 찾을 수 없습니다.")
        return

    # In Progress 섹션에 추가
    in_progress_idx: int = -1
    for i, line in enumerate(new_lines):
        if line.strip() == "## In Progress":
            in_progress_idx = i
            break

    if in_progress_idx == -1:
        _warn("board.md에 '## In Progress' 섹션이 없습니다.")
        return

    # In Progress 헤더 다음 줄 (빈 줄 또는 주석 줄 이후)에 삽입
    insert_idx: int = in_progress_idx + 1
    # 빈 줄 / 주석 줄 건너뛰기
    while insert_idx < len(new_lines):
        stripped = new_lines[insert_idx].strip()
        if stripped == "" or stripped.startswith("<!--"):
            insert_idx += 1
        else:
            break

    new_lines.insert(insert_idx, ticket_line + "\n")

    try:
        with open(board_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except OSError as e:
        _warn(f"board.md 쓰기 실패: {e}")


def _write_context(abs_work_dir: str, title: str, work_id: str, work_name: str, command: str, ts: str) -> None:
    """.context.json을 작업 디렉터리에 작성한다.

    Args:
        abs_work_dir: 작업 디렉터리 절대 경로
        title: 워크플로우 제목 (20자 이내)
        work_id: 시간 기반 워크 ID (HHMMSS 형식)
        work_name: 파일시스템 안전 작업명
        command: 실행 명령어 (implement | review | research)
        ts: ISO 8601 형식 타임스탬프 문자열
    """
    _atomic_write_json(
        os.path.join(abs_work_dir, ".context.json"),
        {
            "title": title,
            "workId": work_id,
            "workName": work_name,
            "command": command,
            "agent": "orchestrator",
            "created_at": ts,
        },
    )


def _write_status(abs_work_dir: str, mode: str, ts: str) -> None:
    """status.json을 작업 디렉터리에 작성한다.

    FSM 초기 상태(NONE)와 현재 세션 ID를 포함한 상태 파일을 생성한다.

    Args:
        abs_work_dir: 작업 디렉터리 절대 경로
        mode: 워크플로우 모드 (full 등)
        ts: ISO 8601 형식 타임스탬프 문자열
    """
    claude_sid: str = os.environ.get("CLAUDE_SESSION_ID", "")
    _atomic_write_json(
        os.path.join(abs_work_dir, "status.json"),
        {
            "step": "NONE",
            "mode": mode,
            "session_id": str(uuid.uuid4())[:8],
            "linked_sessions": [claude_sid] if claude_sid else [],
            "created_at": ts,
            "updated_at": ts,
            "transitions": [],
        },
    )


def init_workflow(
    command: str,
    title: str,
    mode: str,
    prompt_content: str = "",
    ticket_number: str | None = None,
) -> dict[str, str]:
    """워크플로우 디렉터리 구조와 메타데이터를 일괄 생성한다.

    registryKey 기반의 작업 디렉터리를 생성하고, .context.json / status.json /
    user_prompt.txt 파일을 원자적으로 기록한다. 충돌 방지, 좀비 정리,
    아카이빙 후처리까지 포함한다.

    Args:
        command: 실행 명령어 (implement | review | research)
        title: 워크플로우 제목 (20자 이내)
        mode: 워크플로우 모드 (full)
        prompt_content: 사용자 원문 프롬프트 내용 (기본값 빈 문자열)
        ticket_number: 연결된 티켓 번호 (예: 'T-001'). 있으면 board.md를 갱신한다.

    Returns:
        초기화 결과 딕셔너리:
            workDir (str): 프로젝트 루트 상대 작업 경로
            registryKey (str): YYYYMMDD-HHMMSS 형식 식별자
            workId (str): HHMMSS 형식 작업 ID
            workName (str): 파일시스템 안전 작업명
            promptContent (str): 전달받은 프롬프트 내용
            ticketNumber (str): 연결된 티켓 번호 (없으면 빈 문자열)
    """
    now: datetime = datetime.now(KST)
    registry_key: str = now.strftime("%Y%m%d-%H%M%S")
    work_id: str = registry_key.split("-")[1]

    work_name: str = _sanitize_work_name(title)
    if not work_name:
        _err(f"Title produced empty workName after sanitization: '{title}'", 4)

    work_dir: str = f".workflow/{registry_key}/{work_name}/{command}"
    abs_work_dir: str = os.path.join(_PROJECT_ROOT, work_dir)

    # registryKey 충돌 방지: 동일 디렉터리가 이미 존재하면 suffix 추가
    if os.path.exists(abs_work_dir):
        for suffix in range(1, 100):
            candidate_key: str = f"{registry_key}-{suffix}"
            candidate_dir: str = f".workflow/{candidate_key}/{work_name}/{command}"
            candidate_abs: str = os.path.join(_PROJECT_ROOT, candidate_dir)
            if not os.path.exists(candidate_abs):
                registry_key = candidate_key
                work_id = registry_key.split("-")[1]
                work_dir = candidate_dir
                abs_work_dir = candidate_abs
                break

    _create_work_dir(abs_work_dir)
    _write_user_prompt(abs_work_dir, prompt_content)
    _copy_uploads(abs_work_dir)

    # 티켓이 있으면 board.md에서 Open → In Progress 이동
    if ticket_number:
        _move_ticket_to_in_progress(ticket_number)

    _append_log(abs_work_dir, "INFO", f"Workflow initialized: {command}/{work_name}")

    ts: str = now.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    _write_context(abs_work_dir, title, work_id, work_name, command, ts)
    _write_status(abs_work_dir, mode, ts)

    # 좀비 워크플로우 정리
    _run_optional_script(
        os.path.join(_SCRIPTS_DIR, "flow", "garbage_collect.py"),
        ["python3", "{}", _PROJECT_ROOT],
    )

    # KEEP_COUNT 초과 시 아카이빙
    workflow_root: str = os.path.join(_PROJECT_ROOT, ".workflow")
    if os.path.isdir(workflow_root):
        active_count: int = sum(
            1 for e in os.listdir(workflow_root)
            if e[0].isdigit() and e != registry_key
            and os.path.isdir(os.path.join(workflow_root, e))
        )
        if active_count >= KEEP_COUNT - 1:
            _run_optional_script(
                os.path.join(_SCRIPTS_DIR, "sync", "history_sync.py"),
                ["python3", "{}", "archive", registry_key],
            )

    return {
        "workDir": work_dir,
        "registryKey": registry_key,
        "workId": work_id,
        "workName": work_name,
        "promptContent": prompt_content,
        "ticketNumber": ticket_number or "",
    }


# ─── main ────────────────────────────────────────────────────────────────────


def main() -> None:
    """CLI 진입점. 인자 검증 → 티켓 파일 읽기 → 워크플로우 초기화."""
    if len(sys.argv) < 3:
        _err(f"사용법: {sys.argv[0]} <command> <title> [mode] [#N]", 2)

    command: str = sys.argv[1]
    # 인자에서 #N 패턴 티켓 번호 추출
    ticket_arg: str | None = None
    remaining_args: list[str] = []
    for arg in sys.argv[2:]:
        if re.match(r"^#\d+$", arg) or re.match(r"^T-\d+$", arg, re.IGNORECASE):
            ticket_arg = arg
        else:
            remaining_args.append(arg)

    if len(remaining_args) >= 2:
        mode: str = remaining_args[0]
        title: str = remaining_args[1]
    elif len(remaining_args) >= 1:
        mode = "full"
        title = remaining_args[0]
    else:
        _err(f"사용법: {sys.argv[0]} <command> <title> [mode] [#N]", 2)

    if command not in VALID_COMMANDS:
        _err(f"Invalid command: '{command}'. Allowed: {', '.join(sorted(VALID_COMMANDS))}", 2)
    if mode not in VALID_MODES:
        _err(f"Invalid mode: '{mode}'. Allowed: {', '.join(sorted(VALID_MODES))}", 2)

    # Step 1: 티켓 파일 읽기
    prompt_content: str | None
    ticket_number: str | None
    prompt_content, ticket_number = read_prompt(ticket_arg)
    if prompt_content is None:
        kanban_dir: str = os.path.join(_PROJECT_ROOT, ".kanban")
        if ticket_arg or os.environ.get("TICKET_NUMBER"):
            _err(f"지정한 티켓 파일을 찾을 수 없거나 비어있습니다. .kanban/ 디렉터리를 확인하세요. ({kanban_dir})", 1)
        else:
            _err(f".kanban/board.md에 Open 상태 티켓이 없거나 .kanban/ 디렉터리가 없습니다. ({kanban_dir})", 1)

    # Step 2: 워크플로우 디렉터리/메타데이터/레지스트리 일괄 생성
    try:
        result: dict[str, str] = init_workflow(command, title, mode, prompt_content, ticket_number)
    except Exception as e:
        _err(f"워크플로우 초기화 실패: {e}", 4)

    # init-result.json 저장 (오케스트레이터가 Read로 파싱)
    request: str = prompt_content[:50].replace("\n", " ")
    date: str = result["registryKey"][:8]
    abs_work_dir: str = os.path.join(_PROJECT_ROOT, result["workDir"])

    # Step 3: prompt_validator로 티켓 파일 품질 검증 (하위 호환 — import 실패 시 생략)
    prompt_quality: dict[str, Any] | None = None
    try:
        _validator_path: str = os.path.join(_SCRIPT_DIR, "prompt_validator.py")
        if os.path.isfile(_validator_path):
            import importlib.util as _ilu
            _spec = _ilu.spec_from_file_location("prompt_validator", _validator_path)
            if _spec and _spec.loader:
                _mod = _ilu.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)  # type: ignore[attr-defined]
                _raw: dict[str, Any] = _mod.validate(prompt_content)
                prompt_quality = {
                    "quality_score": _raw.get("quality_score", 0.0),
                    "has_tags": _raw.get("has_tags", False),
                    "missing_tags": _raw.get("missing_tags", []),
                    "feedback": _raw.get("feedback", []),
                }
    except Exception as _pv_err:
        _warn(f"prompt_validator import 실패 (품질 검증 생략): {_pv_err}")

    init_result: dict[str, Any] = {
        "request": request,
        "workDir": result["workDir"],
        "workId": result["workId"],
        "registryKey": result["registryKey"],
        "date": date,
        "title": title,
        "workName": result["workName"],
        "command": command,
        "mode": mode,
        "ticketNumber": result.get("ticketNumber", ""),
    }
    if prompt_quality is not None:
        init_result["prompt_quality"] = prompt_quality

    _atomic_write_json(
        os.path.join(abs_work_dir, "init-result.json"),
        init_result,
    )

    print(f"{C_CLAUDE}║ INIT:{C_RESET} {title}", flush=True)
    print(f"{C_CLAUDE}║{C_RESET} {C_DIM}{result['workDir']}{C_RESET}", flush=True)


if __name__ == "__main__":
    main()
