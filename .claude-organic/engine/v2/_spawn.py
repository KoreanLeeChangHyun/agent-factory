"""v2 spawn — claude -p subprocess wrapper.

SPEC.md §8 — Step 마다 1 subprocess. cwd=work_dir, --append-system-prompt,
--session-id, --resume <session_id> 재시도 지원.

본 모듈은 subprocess.run wrapper 만 제공. 재시도 loop 는 _retry.py.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ._common import STEP_TIMEOUT_BY_STEP


CLAUDE_BIN = "claude"


@dataclass
class SpawnResult:
    """claude -p subprocess 결과."""

    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


def session_id_for(ticket_no: str, step: str, phase_id: str | None = None) -> str:
    """SPEC.md §8.2 — session_id 명명 규약.

    예: "wf-T489-PLAN", "wf-T489-WORK-P1".
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
) -> SpawnResult:
    """claude -p subprocess 발사.

    - cwd=work_dir 로 산출물 작성 위치 지정 (SPEC.md §8.4)
    - --append-system-prompt 로 Step 별 system prompt 주입 (10KB 이하)
    - prompt_body 는 stdin 으로 전달 (SDK cap 회피)
    - resume=True 시 --resume 옵션 추가 (재시도)
    """
    effective_timeout = timeout if timeout is not None else STEP_TIMEOUT_BY_STEP.get(step, 600)
    cmd = [CLAUDE_BIN, "-p"]
    if resume:
        cmd += ["--resume", session_id]
    else:
        cmd += ["--session-id", session_id]
    if system_prompt:
        cmd += ["--append-system-prompt", system_prompt]
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
) -> SpawnResult:
    """SPEC.md §6.3 — 같은 session_id 로 이어가기."""
    return spawn_claude(
        prompt_body=prompt_body,
        session_id=session_id,
        system_prompt=system_prompt,
        cwd=cwd,
        step=step,
        resume=True,
        timeout=timeout,
    )
