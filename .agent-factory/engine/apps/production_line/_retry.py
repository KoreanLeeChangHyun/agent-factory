"""Production-line retry — rulebase retry prompt template + claude -p --resume loop.

SPEC.md §6 (retry policy) + §3.4 (N_max). LLM call 0 — no retry prompt
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
from ._emitter import step_end, step_start, stdout_chunk
from ._spawn import SpawnResult, spawn_claude, spawn_claude_resume
from ._verify import VerifyResult


VerifyFn = Callable[[], VerifyResult]


def _make_stdout_forwarder(ctx: WorkflowContext) -> Callable[[dict], None]:
    """spawn on_line callback — Forward to board /stdout for each NDJSON line.

    T-495 P1 — claude -p stream-json Send line to endpoint by meaning.
    text is assistant message.content[].text join. Other types are sent as empty strings.
    Only raw is used for frontend branch renders (text_delta / tool_use / result, etc.).
    """

    def _on_line(obj: dict) -> None:
        text = ""
        if obj.get("type") == "assistant":
            msg = obj.get("message") or {}
            for blk in msg.get("content") or []:
                if isinstance(blk, dict) and blk.get("type") == "text":
                    text += str(blk.get("text", ""))
        stdout_chunk(ctx, text, raw=obj)

    return _on_line


def render_retry_prompt(missing: list[str], artifact_path: Path) -> str:
    """SPEC.md §6.2 — driver template fill (templates/retry_prompt.txt). LLM Call"""
    items = "\n".join(f"- {m}" for m in missing) if missing else "- (Missing output)"
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
    """spawn → verify → in case of failure, resume retry up to N_max.

    Returns: (final VerifyResult, last SpawnResult, retry_count).
    Immediate return upon reaching PASS. Last failure result when N_max is exceeded.
    """
    if n_max is None:
        n_max = get_n_max(step)

    step_start(ctx, step, session_id=session_id)
    append_log(
        ctx,
        f"[{step}] spawn start (session={session_id}, n_max={n_max}, "
        f"prompt_chars={len(initial_prompt)})",
    )

    forwarder = _make_stdout_forwarder(ctx)

    spawn_result = spawn_claude(
        prompt_body=initial_prompt,
        session_id=session_id,
        system_prompt=system_prompt,
        cwd=ctx.work_dir,
        step=step,
        on_line=forwarder,
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
            on_line=forwarder,
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
    """SpawnResult verbose log — displays returncode + stdout/stderr length + timeout.

    Requirement ②: Detailed log of workflow script execution.
    The entire stdout/stderr records only the length of metrics.jsonl + workflow.log to avoid bloating.
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
