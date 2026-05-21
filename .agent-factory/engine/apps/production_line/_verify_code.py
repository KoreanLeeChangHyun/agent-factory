"""Production-line deterministic code verification — pytest -q / ruff check / mypy.

T-503 newly established. SPEC.md §0.1.1 (validation 2 axes separation) + §0.1.2 (TDD enforcement) + §3.2.1 (output 6 areas — validate/code.json).

LLM calls 0. driver determinism.

When to call: Driver side sub-step of VALIDATE Step (call the module seen by the driver after receiving natural language evaluation of `validate/report.md` with claude -p).

Output: `validate/code.json` — `{schema_version, command, tools: [{tool, status, counts, head_diagnostics, duration_ms, ...}], ...}`

Rules (T-503 SPEC §9):
- R-CODE-1: pytest passed hard-fail (implementation only). If status ∈ {ok, skip}, PASS, if fail, hard-fail.
- R-CODE-2: lint clean advisory FAIL (implementation only). PASS if ruff counts == 0 or status == skip, advisory FAIL in case of violation.

implement limited. Research/review is this module SKIP — `run(ctx)` returns after stuffing only the `command_skip: true` flag in `code.json`.

graceful SKIP:
- Tool not installed (PATH not found) → status=skip + reason="<tool> not installed"
- Absence of configuration file (absence of `pyproject.toml` / `pytest.ini` of pytest) → status=skip + reason="no test config"
- Exception occurs → status=skip + reason="<exception>" (does not stop the entire driver)
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from engine.core.validation import code_checks

from ._common import WorkflowContext, append_log


SCHEMA_VERSION = code_checks.SCHEMA_VERSION
HEAD_DIAGNOSTIC_LIMIT = code_checks.HEAD_DIAGNOSTIC_LIMIT
DEFAULT_TIMEOUT_SECONDS = code_checks.DEFAULT_TIMEOUT_SECONDS


def _has_tool(tool: str) -> bool:
    """True if the tool executable file exists in PATH."""
    return shutil.which(tool) is not None


def _run_subprocess(
    cmd: list[str],
    cwd: Path,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[int, str, str, int]:
    """subprocess.run wrapper — returns (returncode, stdout, stderr, duration_ms).

    When an exception occurs, return (-1, "", str(exc), 0) — graceful SKIP processing.
    """
    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        return result.returncode, result.stdout, result.stderr, duration_ms
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        return -1, "", f"TimeoutExpired: {exc}", duration_ms
    except (OSError, ValueError) as exc:
        return -1, "", f"{type(exc).__name__}: {exc}", 0


def _resolve_work_root(ctx: WorkflowContext) -> Path:
    """Determine which cwd to run pytest / ruff / mypy on. Project root in the worktree.

    Priority:
    1. ctx.worktree_path — implement mode worktree
    2. ctx.work_dir.parents[2] — Project root in old worktree-less mode (.agent-factory/runs/<key>/)
    3. ctx.work_dir — fallback
    """
    if ctx.worktree_path is not None and Path(ctx.worktree_path).is_dir():
        return Path(ctx.worktree_path)
    # work_dir = <project_root>/.agent-factory/runs/<key>/
    candidate = ctx.work_dir.parent.parent.parent
    if (candidate / ".git").exists() or (candidate / ".agent-factory").is_dir():
        return candidate
    return ctx.work_dir


def _detect_pytest_config(root: Path) -> bool:
    """Existence of pytest settings — `pyproject.toml` / `pytest.ini` / `setup.cfg` / `tox.ini`."""
    return code_checks.detect_pytest_config(root)


def _detect_ruff_config(root: Path) -> bool:
    """Existence of ruff setting — `pyproject.toml` / `ruff.toml` / `.ruff.toml`.

    ruff can be run without configuration, but there is a lot of noise when run indiscriminately without configuration.
    Proceed only when set up — graceful SKIP domain.
    """
    return code_checks.detect_ruff_config(root)


def _detect_mypy_config(root: Path) -> bool:
    """Existence of mypy configuration — `pyproject.toml` / `mypy.ini` / `setup.cfg`."""
    return code_checks.detect_mypy_config(root)


# -------- pytest --------


def _run_pytest(root: Path) -> dict[str, Any]:
    """Run `pytest -q` subprocess → result dict.

    status: ok | fail | skip
    counts: {"passed": N, "failed": N, "errors": N, "skipped": N}
    head_diagnostics: List of failed node IDs (HEAD_DIAGNOSTIC_LIMIT)
    """
    if not _has_tool("pytest"):
        return {
            "tool": "pytest",
            "status": "skip",
            "reason": "pytest not installed",
            "counts": {},
            "head_diagnostics": [],
            "duration_ms": 0,
        }
    if not _detect_pytest_config(root):
        return {
            "tool": "pytest",
            "status": "skip",
            "reason": "no pytest config / tests/ dir",
            "counts": {},
            "head_diagnostics": [],
            "duration_ms": 0,
        }
    rc, stdout, stderr, dur = _run_subprocess(
        ["pytest", "-q", "--tb=no", "--no-header"],
        cwd=root,
    )
    # pytest exit code: 0=all pass, 1=fail, 2=interrupted, 3=internal, 4=usage, 5=no tests
    if rc == 0:
        status = "ok"
    elif rc == 5:
        status = "skip"  # no tests collected
    else:
        status = "fail"
    counts = _parse_pytest_summary(stdout + "\n" + stderr)
    head_diag = _parse_pytest_failed_nodes(stdout + "\n" + stderr)[:HEAD_DIAGNOSTIC_LIMIT]
    return {
        "tool": "pytest",
        "status": status,
        "rc": rc,
        "counts": counts,
        "head_diagnostics": head_diag,
        "duration_ms": dur,
    }


def _parse_pytest_summary(text: str) -> dict[str, int]:
    """Parse the last summary line of pytest -q (`N passed, M failed in X.XXs`).

    Example: "5 passed, 1 failed in 0.34s" → {"passed": 5, "failed": 1}
    """
    return code_checks.parse_pytest_summary(text)


def _parse_pytest_failed_nodes(text: str) -> list[str]:
    """Extract failed node ID from pytest -q output (`FAILED tests/test_x.py::test_y`)."""
    return code_checks.parse_pytest_failed_nodes(text)


# -------- ruff --------


def _run_ruff(root: Path) -> dict[str, Any]:
    """`ruff check .` Subprocess execution → result dict.

    status: ok | fail | skip
    counts: {"diagnostics": N}
    head_diagnostics: first HEAD_DIAGNOSTIC_LIMIT line
    """
    if not _has_tool("ruff"):
        return {
            "tool": "ruff",
            "status": "skip",
            "reason": "ruff not installed",
            "counts": {},
            "head_diagnostics": [],
            "duration_ms": 0,
        }
    if not _detect_ruff_config(root):
        return {
            "tool": "ruff",
            "status": "skip",
            "reason": "no ruff config",
            "counts": {},
            "head_diagnostics": [],
            "duration_ms": 0,
        }
    rc, stdout, stderr, dur = _run_subprocess(
        ["ruff", "check", "."],
        cwd=root,
    )
    # ruff exit code: 0=clean, 1=violations found, 2=error
    if rc == 0:
        status = "ok"
    elif rc == 1:
        status = "fail"
    else:
        status = "skip"  # internal error → graceful skip
    head_diag = [line for line in stdout.splitlines() if line.strip()][:HEAD_DIAGNOSTIC_LIMIT]
    diag_count = sum(1 for line in stdout.splitlines() if line.strip())
    return {
        "tool": "ruff",
        "status": status,
        "rc": rc,
        "counts": {"diagnostics": diag_count},
        "head_diagnostics": head_diag,
        "duration_ms": dur,
    }


# -------- mypy --------


def _run_mypy(root: Path) -> dict[str, Any]:
    """Execute `mypy <root>` subprocess → result dict.

    status: ok | fail | skip
    counts: {"errors": N}
    """
    if not _has_tool("mypy"):
        return {
            "tool": "mypy",
            "status": "skip",
            "reason": "mypy not installed",
            "counts": {},
            "head_diagnostics": [],
            "duration_ms": 0,
        }
    if not _detect_mypy_config(root):
        return {
            "tool": "mypy",
            "status": "skip",
            "reason": "no mypy config",
            "counts": {},
            "head_diagnostics": [],
            "duration_ms": 0,
        }
    rc, stdout, stderr, dur = _run_subprocess(
        ["mypy", "--no-error-summary", "."],
        cwd=root,
    )
    # mypy exit code: 0=clean, 1=type errors, 2=usage
    if rc == 0:
        status = "ok"
    elif rc == 1:
        status = "fail"
    else:
        status = "skip"
    head_diag = [line for line in stdout.splitlines() if ": error:" in line][
        :HEAD_DIAGNOSTIC_LIMIT
    ]
    err_count = sum(1 for line in stdout.splitlines() if ": error:" in line)
    return {
        "tool": "mypy",
        "status": status,
        "rc": rc,
        "counts": {"errors": err_count},
        "head_diagnostics": head_diag,
        "duration_ms": dur,
    }


# -------- Integration entrypoint --------


def run(ctx: WorkflowContext) -> Path:
    """driver deterministic code verification entrypoint.

    When to call: Call the function seen by the driver within the VALIDATE Step (with claude -p)
    validate/report.md after receiving natural language evaluation).

    movement:
      1. ctx.command != "implement" → Immediately SKIP + `validate/code.json` stuffed
      2. Sequential execution of pytest -q / ruff check / mypy
      3. Accumulate each tool result dict in the `tools` list
      4. JSON serialization with `ctx.validate_code_json_path()`
      5. Append trace 1 line to driver workflow.log

    Returns: Path of the calculated `validate/code.json`.
    """
    code_json_path = ctx.validate_code_json_path()
    code_json_path.parent.mkdir(parents=True, exist_ok=True)

    if ctx.command != "implement":
        payload = {
            "schema_version": SCHEMA_VERSION,
            "command": ctx.command,
            "command_skip": True,
            "skip_reason": f"command={ctx.command} (implement only)",
            "tools": [],
        }
        code_json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        append_log(
            ctx,
            f"[VERIFY-CODE] command={ctx.command} SKIP — code.json stuffed empty",
        )
        return code_json_path

    root = _resolve_work_root(ctx)
    tools_results: list[dict[str, Any]] = []
    try:
        tools_results.append(_run_pytest(root))
        tools_results.append(_run_ruff(root))
        tools_results.append(_run_mypy(root))
    except Exception as exc:  # noqa: BLE001 — graceful SKIP boundary
        # Attempting to raise an exception graceful SKIP — does not completely stop the driver.
        tools_results.append(
            {
                "tool": "internal",
                "status": "skip",
                "reason": f"unhandled exception: {type(exc).__name__}: {exc}",
                "counts": {},
                "head_diagnostics": [],
                "duration_ms": 0,
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "command": ctx.command,
        "command_skip": False,
        "work_root": str(root),
        "tools": tools_results,
    }
    code_json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary_parts = [f"{t['tool']}={t['status']}" for t in tools_results]
    append_log(
        ctx,
        f"[VERIFY-CODE] {len(tools_results)} tools: {' '.join(summary_parts)}",
    )
    return code_json_path


def read_code_json(ctx: WorkflowContext) -> dict[str, Any]:
    """`validate/code.json` reader — R-CODE rule input in `_validate.py`.

    If not present, `{}` is returned (R-CODE rule skips processing).
    """
    return code_checks.read_code_json(ctx)


def tool_result(code_payload: dict[str, Any], tool: str) -> dict[str, Any] | None:
    """Extract specific tool results from the `tools` list in `code.json`.

    For evaluation of R-CODE-1 (pytest) + R-CODE-2 (ruff) in `_validate.py`.
    None if not found.
    """
    return code_checks.tool_result(code_payload, tool)
