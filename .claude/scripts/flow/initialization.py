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

출력:
  stdout으로 init-result JSON을 출력한다.
  오케스트레이터는 Bash 실행 결과에서 직접 파싱한다 (Read 불필요).

종료 코드:
  0  성공
  1  prompt.txt 비어있음
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
    if not os.path.isfile(script_path):
        return
    cmd: list[str] = [part.replace("{}", script_path) for part in cmd_template]
    try:
        subprocess.run(cmd, timeout=30, capture_output=True)
    except Exception:
        pass


# ─── Step 1: prompt.txt 읽기 ─────────────────────────────────────────────────


def read_prompt() -> str | None:
    prompt_file: str = os.path.join(_PROJECT_ROOT, ".prompt", "prompt.txt")
    if not os.path.isfile(prompt_file):
        return None
    with open(prompt_file, "r", encoding="utf-8") as f:
        content: str = f.read()
    if not content.strip():
        return None
    return content


# ─── Step 2: 워크플로우 초기화 ───────────────────────────────────────────────


def _create_work_dir(abs_work_dir: str) -> None:
    """워크플로우 디렉터리를 생성한다."""
    os.makedirs(abs_work_dir, exist_ok=True)
    # workflow.log 빈 파일 생성
    try:
        open(os.path.join(abs_work_dir, "workflow.log"), "a").close()
    except Exception:
        pass


def _write_user_prompt(abs_work_dir: str, prompt_content: str) -> None:
    """user_prompt.txt를 작성한다."""
    with open(os.path.join(abs_work_dir, "user_prompt.txt"), "w", encoding="utf-8") as f:
        f.write(prompt_content)


def _copy_uploads(abs_work_dir: str) -> None:
    """.uploads/ 디렉터리의 파일을 <workDir>/files/로 복사 후 원본 삭제."""
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


def _clear_prompt() -> None:
    """prompt.txt를 클리어한다."""
    _prompt_file: str = os.path.join(_PROJECT_ROOT, ".prompt", "prompt.txt")
    if os.path.isfile(_prompt_file):
        with open(_prompt_file, "w", encoding="utf-8") as f:
            pass


def _write_context(abs_work_dir: str, title: str, work_id: str, work_name: str, command: str, ts: str) -> None:
    """.context.json을 작성한다."""
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
    """status.json을 작성한다."""
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


def init_workflow(command: str, title: str, mode: str, prompt_content: str = "") -> dict[str, str]:
    """워크플로우 디렉터리 구조와 메타데이터를 일괄 생성한다."""
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
    _clear_prompt()

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
        if active_count > KEEP_COUNT:
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
    }


# ─── main ────────────────────────────────────────────────────────────────────


def main() -> None:
    """CLI 진입점. 인자 검증 → prompt 읽기 → 워크플로우 초기화."""
    if len(sys.argv) < 3:
        _err(f"사용법: {sys.argv[0]} <command> <title> [mode]", 2)

    command: str = sys.argv[1]
    if len(sys.argv) >= 4:
        mode: str = sys.argv[2]
        title: str = sys.argv[3]
    else:
        mode = "full"
        title = sys.argv[2]

    if command not in VALID_COMMANDS:
        _err(f"Invalid command: '{command}'. Allowed: {', '.join(sorted(VALID_COMMANDS))}", 2)
    if mode not in VALID_MODES:
        _err(f"Invalid mode: '{mode}'. Allowed: {', '.join(sorted(VALID_MODES))}", 2)

    # Step 1: prompt.txt 읽기
    prompt_content: str | None = read_prompt()
    if prompt_content is None:
        prompt_file: str = os.path.join(_PROJECT_ROOT, ".prompt", "prompt.txt")
        _err(f".prompt/prompt.txt에 요청 내용을 작성한 후 다시 실행해주세요. ({prompt_file})", 1)

    # Step 2: 워크플로우 디렉터리/메타데이터/레지스트리 일괄 생성
    try:
        result: dict[str, str] = init_workflow(command, title, mode, prompt_content)
    except Exception as e:
        _err(f"워크플로우 초기화 실패: {e}", 4)

    # init-result.json 저장 (오케스트레이터가 Read로 파싱)
    request: str = prompt_content[:50].replace("\n", " ")
    date: str = result["registryKey"][:8]
    abs_work_dir: str = os.path.join(_PROJECT_ROOT, result["workDir"])

    # Step 3: prompt_validator로 prompt.txt 품질 검증 (하위 호환 — import 실패 시 생략)
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
