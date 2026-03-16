#!/usr/bin/env -S python3 -u
"""
initialization.py - 워크플로우 초기화 스크립트.

오케스트레이터가 command, mode, title을 인자로 전달하면
작업 디렉터리 생성 + 메타데이터 기록을 수행한다.
LLM 호출 없음 (순수 IO).

사용법:
  python3 initialization.py <command> <title> [mode] [#N]

인자:
  command  실행 명령어. implement | review | research
  title    오케스트레이터가 생성한 20자 이내 제목 (단일 인자 시 title로 간주, mode=full 기본값)
  mode     워크플로우 모드. full (유일 지원 모드). 2인자 시 첫 번째가 mode, 두 번째가 title
  #N       티켓 번호 (T-NNN 또는 #NNN 형식, 선택사항)

환경변수:
  TICKET_NUMBER  티켓 번호 (T-NNN 또는 NNN 형식). 미지정 시 .kanban/ 디렉터리에서 자동 선택.

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
from pathlib import Path
from typing import Any, NoReturn

# ─── 경로 상수 ───────────────────────────────────────────────────────────────

_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT: str = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
_SCRIPTS_DIR: str = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from data.constants import C_CLAUDE, C_DIM, C_RESET, KST, KEEP_COUNT, VALID_COMMANDS, VALID_MODES, WORK_NAME_MAX_LEN, parse_chain_command, CHAIN_SEPARATOR


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

    환경변수 TICKET_NUMBER → 커맨드 인자 → .kanban/ 디렉터리 자동 선택 순으로 탐색한다.

    Args:
        ticket_arg: 커맨드 인자에서 추출된 티켓 번호 문자열 (예: '#1', 'T-001', '1'). 없으면 None.

    Returns:
        'T-NNN' 형식 티켓 번호 문자열. 결정 불가능하면 None.
    """
    # 1순위: 환경변수
    env_ticket: str = os.environ.get("TICKET_NUMBER", "").strip()
    if env_ticket:
        normalized_env = _normalize_ticket_number(env_ticket)
        if normalized_env is not None:
            return normalized_env
        _warn(f"TICKET_NUMBER 환경변수 형식이 올바르지 않습니다: '{env_ticket}'. T-NNN 또는 숫자 형식이어야 합니다. 2순위 인자/3순위 자동선택으로 진행합니다.")

    # 2순위: 커맨드 인자
    if ticket_arg:
        normalized = _normalize_ticket_number(ticket_arg)
        if normalized:
            return normalized

    # 3순위: .kanban/ 디렉터리에서 Open 상태 티켓 자동 선택
    return _find_open_ticket_from_kanban()


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


def _find_open_ticket_from_kanban() -> str | None:
    """.kanban/ 디렉터리의 XML 파일을 glob하여 Open 상태 첫 번째 티켓 번호를 반환한다.

    .kanban/*.xml 파일을 알파벳 순으로 탐색하며, <metadata> 내부의
    <status>Open</status>를 포함하는 첫 번째 티켓 번호를 반환한다.

    Returns:
        'T-NNN' 형식 티켓 번호. 없으면 None.
    """
    import glob as _glob
    import xml.etree.ElementTree as _ET

    kanban_dir: str = os.path.join(_PROJECT_ROOT, ".kanban")
    if not os.path.isdir(kanban_dir):
        return None

    xml_files: list[str] = sorted(_glob.glob(os.path.join(kanban_dir, "T-*.xml")))
    for xml_path in xml_files:
        try:
            tree = _ET.parse(xml_path)
            root = tree.getroot()
            # <metadata> 내부의 <status> 탐색
            metadata = root.find("metadata")
            if metadata is None:
                # 구형 구조: 루트 직하 <status> 탐색
                status_el = root.find("status")
            else:
                status_el = metadata.find("status")
            if status_el is not None and (status_el.text or "").strip() == "Open":
                # <metadata>/<number> 탐색
                number_el = (metadata or root).find("number")
                if number_el is not None and number_el.text:
                    normalized = _normalize_ticket_number(number_el.text.strip())
                    if normalized:
                        return normalized
                # 파일명에서 번호 추출 (T-NNN.xml)
                filename = os.path.basename(xml_path)
                m = re.match(r"^(T-\d+)\.xml$", filename, re.IGNORECASE)
                if m:
                    return _normalize_ticket_number(m.group(1))
        except Exception:
            continue
    return None


def _find_ticket_file(kanban_dir: Path, ticket_number: str) -> Path | None:
    """kanban 디렉터리에서 티켓 파일을 정확 매칭으로 탐색한다.

    루트 파일(T-NNN.xml)을 먼저 탐색하고, 없으면 done 서브디렉터리도 탐색한다.

    Args:
        kanban_dir: .kanban 디렉터리 절대 경로
        ticket_number: 'T-NNN' 형식 티켓 번호

    Returns:
        찾은 티켓 파일의 Path 객체. 없으면 None.
    """
    # 루트 탐색: .kanban/T-NNN.xml
    candidate: Path = kanban_dir / f"{ticket_number}.xml"
    if candidate.is_file():
        return candidate
    # done 상태 탐색: .kanban/done/T-NNN.xml
    done_candidate: Path = kanban_dir / "done" / f"{ticket_number}.xml"
    if done_candidate.is_file():
        return done_candidate
    return None


def read_prompt(ticket_arg: str | None = None) -> tuple[str | None, str | None]:
    """티켓 파일 내용을 읽어 반환한다.

    티켓 번호를 결정한 후 .kanban/T-NNN.xml 파일을 정확 매칭으로 탐색하여 읽는다.
    파일이 없거나 내용이 비어있으면 None을 반환한다.

    XML 구조 호환성 주석:
        이 함수는 티켓 파일 전체를 문자열로 읽어 반환하며 XML을 파싱하지 않는다.
        따라서 새 XML 구조(<metadata>/<submit>/<history> 래퍼 요소, <prompt> 래퍼,
        <result> 구조화)에서도 동작에 영향이 없다. 반환된 content는 user_prompt.txt에
        그대로 기록되며, prompt_validator.py의 validate() 함수로 전달되어 태그 기반
        검증에 사용된다.

    Args:
        ticket_arg: 커맨드 인자에서 추출된 티켓 번호 (예: '#1'). 없으면 None.

    Returns:
        (티켓 파일 내용 문자열, 티켓 번호 문자열) 튜플.
        파일 없음 또는 빈 내용이면 (None, None).
    """
    ticket_number: str | None = _resolve_ticket_number(ticket_arg)
    if ticket_number is None:
        return None, None

    kanban_dir: Path = Path(_PROJECT_ROOT) / ".kanban"
    ticket_path: Path | None = _find_ticket_file(kanban_dir, ticket_number)
    if ticket_path is None:
        return None, None
    with open(ticket_path, "r", encoding="utf-8") as f:
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


def _move_ticket_to_in_progress(ticket_number: str, abs_work_dir: str = "") -> None:
    """kanban.py를 호출하여 티켓을 Open → In Progress 상태로 이동한다.

    kanban.py move 서브커맨드를 subprocess로 실행한다.
    실패 시 경고만 출력하고 계속 진행한다.

    Args:
        ticket_number: 이동할 티켓 번호 (예: 'T-001')
        abs_work_dir: 워크플로우 로그 기록용 절대 경로. 비어있으면 로그 기록 생략.
    """
    kanban_py_path: str = os.path.join(_SCRIPT_DIR, "kanban.py")
    if not os.path.isfile(kanban_py_path):
        _warn(f"kanban.py를 찾을 수 없습니다: {kanban_py_path}")
        return

    try:
        result = subprocess.run(
            ["python3", kanban_py_path, "move", ticket_number, "progress"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            combined = "\n".join(filter(None, [stdout, stderr]))
            _warn(f"kanban.py move 실패 (exit {result.returncode}): {combined}")
            if abs_work_dir:
                _append_log(abs_work_dir, "WARN", f"kanban.py move 실패 (exit {result.returncode}): {combined}")
    except subprocess.TimeoutExpired:
        _warn("kanban.py move: 타임아웃")
    except Exception as e:
        _warn(f"kanban.py move 실행 실패: {e}")


def _update_ticket_title(ticket_number: str, title: str, abs_work_dir: str = "") -> None:
    """kanban.py를 호출하여 티켓 제목을 갱신한다.

    kanban.py update-title 서브커맨드를 subprocess로 실행한다.
    실패 시 경고만 출력하고 계속 진행한다.

    Args:
        ticket_number: 티켓 번호 (예: 'T-001')
        title: 갱신할 제목 문자열
        abs_work_dir: 워크플로우 로그 기록용 절대 경로. 비어있으면 로그 기록 생략.
    """
    kanban_py_path: str = os.path.join(_SCRIPT_DIR, "kanban.py")
    if not os.path.isfile(kanban_py_path):
        _warn(f"kanban.py를 찾을 수 없습니다: {kanban_py_path}")
        return

    try:
        result = subprocess.run(
            ["python3", kanban_py_path, "update-title", ticket_number, title],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            combined = "\n".join(filter(None, [stdout, stderr]))
            _warn(f"kanban.py update-title 실패 (exit {result.returncode}): {combined}")
            if abs_work_dir:
                _append_log(abs_work_dir, "WARN", f"kanban.py update-title 실패 (exit {result.returncode}): {combined}")
    except subprocess.TimeoutExpired:
        _warn("kanban.py update-title: 타임아웃")
    except Exception as e:
        _warn(f"kanban.py update-title 실행 실패: {e}")


def _write_context(
    abs_work_dir: str,
    title: str,
    work_id: str,
    work_name: str,
    command: str,
    ts: str,
    chain_command: str = "",
    registry_key: str = "",
    ticket_number: str = "",
) -> None:
    """.context.json을 작업 디렉터리에 작성한다.

    command 필드는 finalization.py의 체인 추적에 사용되며 전체 체인 문자열을 저장한다.
    chainCommand 필드는 원본 체인 문자열의 명시적 보존용이며, command와 동일한 값을 중복 저장한다.
    이 이중 저장은 의도적 설계로, command 필드가 단일 command와 체인 command를 겸용하는 반면
    chainCommand는 체인 존재 여부를 빈 문자열/비빈 문자열로 즉시 판별할 수 있는 편의 필드이다.

    registryKey와 ticketNumber 필드는 board.js가 워크플로우↔티켓 양방향 연결에 사용한다.

    Args:
        abs_work_dir: 작업 디렉터리 절대 경로
        title: 워크플로우 제목 (20자 이내)
        work_id: 시간 기반 워크 ID (HHMMSS 형식)
        work_name: 파일시스템 안전 작업명
        command: 실행 명령어 (implement | review | research). 체인의 경우 전체 체인 문자열.
        ts: ISO 8601 형식 타임스탬프 문자열
        chain_command: 전체 체인 문자열 (예: "research>implement>review"). 단일 command 시 빈 문자열.
        registry_key: YYYYMMDD-HHMMSS 형식 전체 registryKey. board.js 양방향 연결용.
        ticket_number: 연결된 티켓 번호 (예: 'T-001'). board.js 양방향 연결용.
    """
    context: dict[str, Any] = {
        "title": title,
        "workId": work_id,
        "workName": work_name,
        "command": command,
        "agent": "orchestrator",
        "created_at": ts,
    }
    if chain_command:
        context["chainCommand"] = chain_command
    if registry_key:
        context["registryKey"] = registry_key
    if ticket_number:
        context["ticketNumber"] = ticket_number
    _atomic_write_json(
        os.path.join(abs_work_dir, ".context.json"),
        context,
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
    status_data: dict[str, Any] = {
        "step": "NONE",
        "mode": mode,
        "session_id": str(uuid.uuid4())[:8],
        "linked_sessions": [claude_sid] if claude_sid else [],
        "created_at": ts,
        "updated_at": ts,
        "transitions": [],
    }
    _atomic_write_json(
        os.path.join(abs_work_dir, "status.json"),
        status_data,
    )


def init_workflow(
    command: str,
    title: str,
    mode: str,
    prompt_content: str = "",
    ticket_number: str | None = None,
    chain_command: str = "",
) -> dict[str, str]:
    """워크플로우 디렉터리 구조와 메타데이터를 일괄 생성한다.

    registryKey 기반의 작업 디렉터리를 생성하고, .context.json / status.json /
    user_prompt.txt 파일을 원자적으로 기록한다. 충돌 방지, 좀비 정리,
    아카이빙 후처리까지 포함한다.

    Args:
        command: 실행 명령어 (implement | review | research). 체인의 경우 첫 세그먼트.
        title: 워크플로우 제목 (20자 이내)
        mode: 워크플로우 모드 (full)
        prompt_content: 사용자 원문 프롬프트 내용 (기본값 빈 문자열)
        ticket_number: 연결된 티켓 번호 (예: 'T-001'). 있으면 티켓 상태를 갱신한다.
        chain_command: 전체 체인 문자열 (예: "research>implement>review"). 단일 command 시 빈 문자열.

    Returns:
        초기화 결과 딕셔너리:
            workDir (str): 프로젝트 루트 상대 작업 경로
            registryKey (str): YYYYMMDD-HHMMSS 형식 식별자
            workId (str): HHMMSS 형식 작업 ID
            workName (str): 파일시스템 안전 작업명
            promptContent (str): 전달받은 프롬프트 내용
            ticketNumber (str): 연결된 티켓 번호 (없으면 빈 문자열)
            chainCommand (str): 전체 체인 문자열 (없으면 빈 문자열)
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
        else:
            _err("registryKey 충돌이 99회를 초과했습니다. 중복 워크플로우를 정리하세요.", 4)

    _create_work_dir(abs_work_dir)
    _write_user_prompt(abs_work_dir, prompt_content)
    _copy_uploads(abs_work_dir)

    # 티켓이 있으면 제목 갱신 + Open → In Progress 이동
    if ticket_number:
        _update_ticket_title(ticket_number, title, abs_work_dir)
        _move_ticket_to_in_progress(ticket_number, abs_work_dir)

    _append_log(abs_work_dir, "INFO", f"Workflow initialized: {command}/{work_name}")

    ts: str = now.strftime("%Y-%m-%dT%H:%M:%S+09:00")

    # .context.json의 command 필드: 체인이 있으면 전체 체인 문자열 저장 (finalization.py 체인 추적용)
    context_command: str = chain_command if chain_command else command
    _write_context(
        abs_work_dir,
        title,
        work_id,
        work_name,
        context_command,
        ts,
        chain_command,
        registry_key=registry_key,
        ticket_number=ticket_number or "",
    )
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
        "chainCommand": chain_command,
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

    # 체인 command 처리: ">" 구분자가 있으면 체인으로 파싱, 첫 세그먼트를 실행 command로 사용
    chain_command: str = ""
    effective_command: str = command
    if CHAIN_SEPARATOR in command:
        segments: list[str] = []  # 정적 분석 possibly unbound 해소용 사전 초기화
        try:
            segments = parse_chain_command(command)
        except ValueError as e:
            _err(f"체인 command 파싱 오류: {e}", 2)
        chain_command = command  # 전체 체인 문자열 보존 (finalization.py 체인 추적용)
        effective_command = segments[0]  # 첫 세그먼트만 현재 실행에 사용
    else:
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
            _err(f".kanban/ 디렉터리가 없거나 Open 상태 티켓이 없습니다. 먼저 /wf -o 로 티켓을 생성하세요. ({kanban_dir})", 1)

    # Step 2: 워크플로우 디렉터리/메타데이터/레지스트리 일괄 생성
    try:
        result: dict[str, str] = init_workflow(effective_command, title, mode, prompt_content, ticket_number, chain_command)
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
            import importlib.util as _ilu  # 내부 API 호출 (CLI 미사용)
            _spec = _ilu.spec_from_file_location("prompt_validator", _validator_path)
            if _spec and _spec.loader:
                _mod = _ilu.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)  # type: ignore[attr-defined]
                # 활성 subnumber의 <prompt> 섹션만 추출 (하위 호환: 함수 없으면 전체 XML 전달)
                _active_prompt: str = (
                    _mod.extract_active_prompt(prompt_content)
                    if hasattr(_mod, "extract_active_prompt")
                    else prompt_content
                )
                _raw: dict[str, Any] = _mod.validate(_active_prompt)
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
        "command": effective_command,
        "mode": mode,
        "ticketNumber": result.get("ticketNumber", ""),
    }
    if chain_command:
        init_result["chainCommand"] = chain_command
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
