"""v2 spawn — claude -p subprocess wrapper.

SPEC.md §8 — Step 마다 1 subprocess. cwd=work_dir, --append-system-prompt,
--session-id, --resume <session_id> 재시도 지원.

본 모듈은 subprocess.run wrapper 만 제공. 재시도 loop 는 _retry.py.

회귀 fix (Phase 2-A 검토 회귀 4건):
- session_id 는 claude CLI `--session-id <uuid>` 규약상 UUID 필수
- logical_name (`wf-T489-PLAN`) 은 디버그/로그 인용용으로 분리
- --permission-mode 명시 (non-interactive `-p` 모드 권한 차단 회피)
- --add-dir 으로 work_dir 도구 접근 허용 (cwd 보강)
"""

from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from ._common import STEP_TIMEOUT_BY_STEP


CLAUDE_BIN = "claude"
DEFAULT_PERMISSION_MODE = "bypassPermissions"


@dataclass
class SpawnResult:
    """claude -p subprocess 결과."""

    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


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
) -> SpawnResult:
    """claude -p subprocess 발사.

    - cwd=work_dir 로 산출물 작성 위치 지정 (SPEC.md §8.4)
    - --append-system-prompt 로 Step 별 system prompt 주입 (10KB 이하)
    - --session-id <uuid> 또는 --resume <uuid>
    - --permission-mode <mode> 명시 (default: bypassPermissions)
    - --add-dir <path> 으로 도구 접근 허용 디렉터리 추가
    - prompt_body 는 stdin 으로 전달
    """
    effective_timeout = timeout if timeout is not None else STEP_TIMEOUT_BY_STEP.get(step, 600)
    cmd = [CLAUDE_BIN, "-p"]
    if resume:
        cmd += ["--resume", session_id]
    else:
        cmd += ["--session-id", session_id]
    if system_prompt:
        cmd += ["--append-system-prompt", system_prompt]
    cmd += ["--permission-mode", permission_mode]
    # cwd 자체도 명시적으로 추가 — claude 가 cwd 외 경로 접근 허용
    for d in (cwd, *add_dirs):
        cmd += ["--add-dir", str(d)]
    try:
        result = subprocess.run(
            cmd,
            input=prompt_body,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            check=False,
        )
        return SpawnResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=False,
        )
    except subprocess.TimeoutExpired as exc:
        return SpawnResult(
            returncode=-1,
            stdout=exc.stdout.decode("utf-8", errors="replace") if exc.stdout else "",
            stderr=exc.stderr.decode("utf-8", errors="replace") if exc.stderr else "",
            timed_out=True,
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
    )
