"""v2 retry — 룰베이스 재시도 prompt 템플릿 + claude -p --resume loop.

SPEC.md §6 (재시도 정책) + §3.4 (N_max). LLM 호출 0 — 재시도 prompt 도
template fill.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ._common import (
    WorkflowContext,
    append_log,
    get_n_max,
    load_template,
)
from ._emitter import step_end, step_start
from ._spawn import SpawnResult, spawn_claude, spawn_claude_resume
from ._verify import VerifyResult


VerifyFn = Callable[[], VerifyResult]


def render_retry_prompt(missing: list[str], artifact_path: Path) -> str:
    """SPEC.md §6.2 — driver template fill (templates/retry_prompt.txt). LLM 호출 X."""
    items = "\n".join(f"- {m}" for m in missing) if missing else "- (산출물 누락)"
    return load_template("retry_prompt.txt").format(
        missing_items=items,
        artifact_path=str(artifact_path),
    )


def spawn_with_retry(
    ctx: WorkflowContext,
    *,
    step: str,
    initial_prompt: str,
    system_prompt: str,
    session_id: str,
    verify: VerifyFn,
    artifact_path: Path,
    n_max: int | None = None,
) -> tuple[VerifyResult, SpawnResult | None, int]:
    """spawn → verify → 실패 시 resume 재시도 N_max 까지.

    Returns: (final VerifyResult, last SpawnResult, retry_count).
    PASS 도달 시 즉시 반환. N_max 초과 시 마지막 실패 결과.
    """
    if n_max is None:
        n_max = get_n_max(step)

    step_start(ctx, step, session_id=session_id)
    append_log(
        ctx,
        f"[{step}] spawn start (session={session_id}, n_max={n_max}, "
        f"prompt_chars={len(initial_prompt)})",
    )

    spawn_result = spawn_claude(
        prompt_body=initial_prompt,
        session_id=session_id,
        system_prompt=system_prompt,
        cwd=ctx.work_dir,
        step=step,
    )
    _log_spawn_result(ctx, step, spawn_result, attempt=0)
    verify_result = verify()
    retry_count = 0

    while not verify_result.ok and retry_count < n_max:
        retry_count += 1
        retry_prompt = render_retry_prompt(verify_result.missing, artifact_path)
        append_log(
            ctx,
            f"[{step}] retry {retry_count}/{n_max} — missing: {verify_result.missing}",
        )
        spawn_result = spawn_claude_resume(
            prompt_body=retry_prompt,
            session_id=session_id,
            system_prompt=system_prompt,
            cwd=ctx.work_dir,
            step=step,
        )
        _log_spawn_result(ctx, step, spawn_result, attempt=retry_count)
        verify_result = verify()

    outcome = "ok" if verify_result.ok else "fail"
    step_end(ctx, step, outcome=outcome, retry_count=retry_count)
    append_log(
        ctx,
        f"[{step}] spawn end (outcome={outcome}, retry={retry_count}, "
        f"timed_out={spawn_result.timed_out if spawn_result else False})",
    )
    return verify_result, spawn_result, retry_count


def _log_spawn_result(
    ctx: WorkflowContext,
    step: str,
    result: SpawnResult,
    *,
    attempt: int,
) -> None:
    """SpawnResult 상세 로그 — returncode + stdout/stderr 길이 + timeout 표시.

    요구사항 ②: 워크플로우 스크립트 실행 상세 로그 기록.
    stdout/stderr 전체는 metrics.jsonl + workflow.log 비대화 회피 위해 길이만 기록.
    """
    suffix = "" if attempt == 0 else f" attempt={attempt}"
    if result.timed_out:
        append_log(
            ctx,
            f"[{step}] spawn result{suffix} TIMEOUT (stdout={len(result.stdout)}, "
            f"stderr={len(result.stderr)})",
        )
        return
    stderr_tail = result.stderr.rstrip().splitlines()[-1] if result.stderr.strip() else ""
    append_log(
        ctx,
        f"[{step}] spawn result{suffix} rc={result.returncode} "
        f"stdout={len(result.stdout)} stderr={len(result.stderr)}"
        + (f" stderr_tail={stderr_tail!r}" if stderr_tail else ""),
    )
