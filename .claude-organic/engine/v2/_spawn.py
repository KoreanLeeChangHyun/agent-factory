"""v2 spawn — claude -p subprocess wrapper.

SPEC.md §8 — Step 마다 1 subprocess. cwd=work_dir, --append-system-prompt,
--session-id, --resume <session_id> 재시도 지원.

T-495 Phase 2 (driver) — `--output-format stream-json --verbose` 로 갈아끼움 +
subprocess.run → Popen + readline 루프 + line callback. driver 가 NDJSON
line 마다 의미별 endpoint 로 forward 한다.

회귀 fix (Phase 2-A 검토 회귀 4건):
- session_id 는 claude CLI `--session-id <uuid>` 규약상 UUID 필수
- logical_name (`wf-T489-PLAN`) 은 디버그/로그 인용용으로 분리
- --permission-mode 명시 (non-interactive `-p` 모드 권한 차단 회피)
- --add-dir 으로 work_dir 도구 접근 허용 (cwd 보강)
"""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ._common import STEP_TIMEOUT_BY_STEP


CLAUDE_BIN = "claude"
DEFAULT_PERMISSION_MODE = "bypassPermissions"


@dataclass
class SpawnResult:
    """claude -p subprocess 결과.

    Attributes:
        returncode: process returncode (timeout 시 -1)
        stdout: assistant message.content[].text 누적 (호환용 — verify 는 artifact 파일 read)
        stderr: stderr 전체
        timed_out: deadline 초과 여부
        ndjson_lines: 파싱된 NDJSON line dict 목록 (테스트 + 진단용)
        terminal_reason: result.terminal_reason ("completed" 등). 없으면 빈 문자열
    """

    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    ndjson_lines: list[dict[str, Any]] = field(default_factory=list)
    terminal_reason: str = ""


def new_session_uuid() -> str:
    """claude `--session-id <uuid>` 용 UUID4 — 새 세션 1개당 1개 생성."""
    return str(uuid.uuid4())


def logical_session_name(ticket_no: str, step: str, phase_id: str | None = None) -> str:
    """디버그/로그 인용용 logical name. claude 에 전달하지 않음.

    예: "wf-T489-PLAN", "wf-T489-WORK-P1". ctx.session_ids 의 key 로 사용.
    """
    base = f"wf-{ticket_no.replace('-', '')}-{step}"
    if phase_id is not None:
        return f"{base}-{phase_id}"
    return base


def _extract_assistant_text(obj: dict[str, Any]) -> str:
    """assistant NDJSON line 에서 text block 만 join.

    shape (claude -p stream-json 실측):
        {"type":"assistant","message":{"content":[{"type":"text","text":"..."}]}}
    """
    if obj.get("type") != "assistant":
        return ""
    msg = obj.get("message") or {}
    content = msg.get("content") or []
    pieces: list[str] = []
    for blk in content:
        if isinstance(blk, dict) and blk.get("type") == "text":
            pieces.append(str(blk.get("text", "")))
    return "".join(pieces)


def spawn_claude(
    *,
    prompt_body: str,
    session_id: str,
    system_prompt: str,
    cwd: Path,
    step: str,
    resume: bool = False,
    timeout: int | None = None,
    permission_mode: str = DEFAULT_PERMISSION_MODE,
    add_dirs: tuple[Path, ...] = (),
    on_line: Callable[[dict[str, Any]], None] | None = None,
) -> SpawnResult:
    """claude -p subprocess 발사 (stream-json 모드).

    - cwd=work_dir 로 산출물 작성 위치 지정 (SPEC.md §8.4)
    - --output-format stream-json --verbose (T-495 P1)
    - --append-system-prompt 로 Step 별 system prompt 주입 (10KB 이하)
    - --session-id <uuid> 또는 --resume <uuid>
    - --permission-mode <mode> 명시 (default: bypassPermissions)
    - --add-dir <path> 으로 도구 접근 허용 디렉터리 추가
    - prompt_body 는 stdin 으로 전달
    - on_line(obj) 콜백 — NDJSON line 마다 호출 (None 이면 skip)
      콜백 예외는 silent 흡수 — driver 흐름 영향 0
    """
    effective_timeout = timeout if timeout is not None else STEP_TIMEOUT_BY_STEP.get(step, 600)
    cmd = [CLAUDE_BIN, "-p", "--output-format", "stream-json", "--verbose"]
    if resume:
        cmd += ["--resume", session_id]
    else:
        cmd += ["--session-id", session_id]
    if system_prompt:
        cmd += ["--append-system-prompt", system_prompt]
    cmd += ["--permission-mode", permission_mode]
    for d in (cwd, *add_dirs):
        cmd += ["--add-dir", str(d)]

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(cwd),
            text=True,
            bufsize=1,  # line-buffered
        )
    except (FileNotFoundError, OSError) as exc:
        return SpawnResult(
            returncode=-1,
            stdout="",
            stderr=f"spawn failed: {exc}",
            timed_out=False,
        )

    # prompt 를 stdin 으로 전달 + close (claude 가 EOF 읽고 종료 흐름 시작)
    try:
        if proc.stdin is not None:
            proc.stdin.write(prompt_body)
            proc.stdin.close()
    except (BrokenPipeError, OSError):
        pass

    text_buf: list[str] = []
    ndjson_lines: list[dict[str, Any]] = []
    terminal_reason = ""
    timed_out = False

    deadline = time.monotonic() + effective_timeout

    assert proc.stdout is not None
    try:
        for raw_line in proc.stdout:
            if time.monotonic() > deadline:
                timed_out = True
                break
            line = raw_line.rstrip("\n")
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # stream-json 외 노이즈 line 은 무시 (테스트 모드에서는 발생 가능)
                continue
            if not isinstance(obj, dict):
                continue
            ndjson_lines.append(obj)
            text_chunk = _extract_assistant_text(obj)
            if text_chunk:
                text_buf.append(text_chunk)
            if obj.get("type") == "result":
                tr = obj.get("terminal_reason")
                if isinstance(tr, str):
                    terminal_reason = tr
            if on_line is not None:
                try:
                    on_line(obj)
                except Exception:
                    pass  # silent — driver 흐름 영향 0
    except (OSError, ValueError):
        pass

    # 회귀 ③ 차단 — readline 루프 종료 후 completion 처리.
    # 정상 EOF 면 wait() 즉시 returncode 확보. timeout 이면 kill.
    if timed_out:
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        returncode = -1
    else:
        try:
            returncode = proc.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
                proc.wait(timeout=2)
            except (subprocess.TimeoutExpired, OSError):
                pass
            timed_out = True
            returncode = -1

    try:
        stderr_text = proc.stderr.read() if proc.stderr is not None else ""
    except (OSError, ValueError):
        stderr_text = ""
    try:
        if proc.stdout is not None:
            proc.stdout.close()
        if proc.stderr is not None:
            proc.stderr.close()
    except OSError:
        pass

    stdout_text = "".join(text_buf)
    return SpawnResult(
        returncode=returncode,
        stdout=stdout_text,
        stderr=stderr_text or "",
        timed_out=timed_out,
        ndjson_lines=ndjson_lines,
        terminal_reason=terminal_reason,
    )


def spawn_claude_resume(
    *,
    prompt_body: str,
    session_id: str,
    system_prompt: str,
    cwd: Path,
    step: str,
    timeout: int | None = None,
    permission_mode: str = DEFAULT_PERMISSION_MODE,
    add_dirs: tuple[Path, ...] = (),
    on_line: Callable[[dict[str, Any]], None] | None = None,
) -> SpawnResult:
    """SPEC.md §6.3 — 같은 session_id (UUID) 로 이어가기."""
    return spawn_claude(
        prompt_body=prompt_body,
        session_id=session_id,
        system_prompt=system_prompt,
        cwd=cwd,
        step=step,
        resume=True,
        timeout=timeout,
        permission_mode=permission_mode,
        add_dirs=add_dirs,
        on_line=on_line,
    )
