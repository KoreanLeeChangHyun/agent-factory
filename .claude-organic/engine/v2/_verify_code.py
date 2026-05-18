"""v2 driver 결정론 코드 검증 — pytest -q / ruff check / mypy.

T-503 신설. SPEC.md §0.1.1 (검증 2축 분리) + §0.1.2 (TDD 강제) + §3.2.1 (산출물 6 영역 — validate/code.json).

LLM 호출 0. driver 결정론.

호출 시기: VALIDATE Step 의 driver 측 sub-단계 (claude -p 로 `validate/report.md` 자연어 평가 받은 후 driver 가 본 모듈 호출).

산출물: `validate/code.json` — `{schema_version, command, tools: [{tool, status, counts, head_diagnostics, duration_ms, ...}], ...}`

룰 (T-503 SPEC §9):
- R-CODE-1: pytest 통과 hard-fail (implement 한정). status ∈ {ok, skip} 이면 PASS, fail 이면 hard-fail.
- R-CODE-2: lint clean advisory FAIL (implement 한정). ruff counts == 0 또는 status == skip 이면 PASS, 위반 시 advisory FAIL.

implement 한정. research/review 는 본 모듈 SKIP — `run(ctx)` 가 `code.json` 안에 `command_skip: true` flag 만 박제 후 return.

graceful SKIP:
- 도구 미설치 (PATH 못 찾음) → status=skip + reason="<tool> not installed"
- 설정 파일 부재 (pytest 의 `pyproject.toml` / `pytest.ini` 부재) → status=skip + reason="no test config"
- 예외 발생 → status=skip + reason="<exception>" (driver 전체 중단 안 함)
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from ._common import WorkflowContext, append_log


SCHEMA_VERSION = 1
HEAD_DIAGNOSTIC_LIMIT = 10           # 결과 JSON 에 박제하는 진단 메시지 최대 개수
DEFAULT_TIMEOUT_SECONDS = 600        # 10 분 — pytest + ruff + mypy 통째


def _has_tool(tool: str) -> bool:
    """PATH 안에 도구 실행 파일이 존재하면 True."""
    return shutil.which(tool) is not None


def _run_subprocess(
    cmd: list[str],
    cwd: Path,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[int, str, str, int]:
    """subprocess.run wrapper — (returncode, stdout, stderr, duration_ms) 반환.

    예외 발생 시 (-1, "", str(exc), 0) 반환 — graceful SKIP 처리.
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
    """pytest / ruff / mypy 를 실행할 cwd 결정. worktree 안의 프로젝트 루트.

    우선순위:
    1. ctx.worktree_path — implement 모드 worktree
    2. ctx.work_dir.parents[2] — 옛 worktree-less 모드 (.claude-organic/runs/<key>/) 의 프로젝트 루트
    3. ctx.work_dir — fallback
    """
    if ctx.worktree_path is not None and Path(ctx.worktree_path).is_dir():
        return Path(ctx.worktree_path)
    # work_dir = <project_root>/.claude-organic/runs/<key>/
    candidate = ctx.work_dir.parent.parent.parent
    if (candidate / ".git").exists() or (candidate / ".claude-organic").is_dir():
        return candidate
    return ctx.work_dir


def _detect_pytest_config(root: Path) -> bool:
    """pytest 설정 존재 여부 — `pyproject.toml` / `pytest.ini` / `setup.cfg` / `tox.ini`."""
    for fname in ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini"):
        if (root / fname).is_file():
            return True
    # 또는 tests/ 디렉터리만 존재해도 OK (pytest -q 가 디스커버리)
    return (root / "tests").is_dir()


def _detect_ruff_config(root: Path) -> bool:
    """ruff 설정 존재 여부 — `pyproject.toml` / `ruff.toml` / `.ruff.toml`.

    ruff 는 설정 없이도 실행 가능하지만, 설정 없이 무차별 실행 시 noise 가 많음.
    설정 있을 때만 진행 — graceful SKIP 도메인.
    """
    for fname in ("ruff.toml", ".ruff.toml"):
        if (root / fname).is_file():
            return True
    # pyproject.toml 안에 [tool.ruff] 섹션 존재 시
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            text = pyproject.read_text(encoding="utf-8")
            if "[tool.ruff" in text:
                return True
        except (OSError, UnicodeDecodeError):
            return False
    return False


def _detect_mypy_config(root: Path) -> bool:
    """mypy 설정 존재 여부 — `pyproject.toml` / `mypy.ini` / `setup.cfg`."""
    for fname in ("mypy.ini", ".mypy.ini"):
        if (root / fname).is_file():
            return True
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            text = pyproject.read_text(encoding="utf-8")
            if "[tool.mypy" in text:
                return True
        except (OSError, UnicodeDecodeError):
            return False
    return False


# -------- pytest --------


def _run_pytest(root: Path) -> dict[str, Any]:
    """`pytest -q` subprocess 실행 → result dict.

    status: ok | fail | skip
    counts: {"passed": N, "failed": N, "errors": N, "skipped": N}
    head_diagnostics: 실패 노드 ID 목록 (HEAD_DIAGNOSTIC_LIMIT)
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
    """pytest -q 의 마지막 summary 라인 (`N passed, M failed in X.XXs`) parse.

    예: "5 passed, 1 failed in 0.34s" → {"passed": 5, "failed": 1}
    """
    keywords = ("passed", "failed", "errors", "skipped", "xfailed", "xpassed")
    counts: dict[str, int] = {}
    for line in text.splitlines()[-20:]:
        tokens = line.replace(",", " ").split()
        for i, tok in enumerate(tokens):
            if tok.isdigit() and i + 1 < len(tokens) and tokens[i + 1] in keywords:
                counts[tokens[i + 1]] = int(tok)
    return counts


def _parse_pytest_failed_nodes(text: str) -> list[str]:
    """pytest -q 출력에서 실패 노드 ID 추출 (`FAILED tests/test_x.py::test_y`)."""
    nodes: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("FAILED "):
            nodes.append(s[7:].split(" - ")[0].strip())
        elif s.startswith("ERROR "):
            nodes.append(s[6:].split(" - ")[0].strip())
    return nodes


# -------- ruff --------


def _run_ruff(root: Path) -> dict[str, Any]:
    """`ruff check .` subprocess 실행 → result dict.

    status: ok | fail | skip
    counts: {"diagnostics": N}
    head_diagnostics: 첫 HEAD_DIAGNOSTIC_LIMIT 줄
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
    """`mypy <root>` subprocess 실행 → result dict.

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


# -------- 통합 entrypoint --------


def run(ctx: WorkflowContext) -> Path:
    """driver 결정론 코드 검증 entrypoint.

    호출 시기: VALIDATE Step 안에서 driver 가 본 함수 호출 (claude -p 로
    validate/report.md 자연어 평가 받은 후).

    동작:
      1. ctx.command != "implement" → 즉시 SKIP + `validate/code.json` 박제
      2. pytest -q / ruff check / mypy 순차 실행
      3. 각 도구 결과 dict 를 `tools` list 에 누적
      4. `ctx.validate_code_json_path()` 에 JSON 직렬화
      5. driver workflow.log 에 trace 1 줄 append

    Returns: 산출된 `validate/code.json` 의 Path.
    """
    code_json_path = ctx.validate_code_json_path()
    code_json_path.parent.mkdir(parents=True, exist_ok=True)

    if ctx.command != "implement":
        payload = {
            "schema_version": SCHEMA_VERSION,
            "command": ctx.command,
            "command_skip": True,
            "skip_reason": f"command={ctx.command} (implement 한정)",
            "tools": [],
        }
        code_json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        append_log(
            ctx,
            f"[VERIFY-CODE] command={ctx.command} SKIP — code.json 빈 박제",
        )
        return code_json_path

    root = _resolve_work_root(ctx)
    tools_results: list[dict[str, Any]] = []
    try:
        tools_results.append(_run_pytest(root))
        tools_results.append(_run_ruff(root))
        tools_results.append(_run_mypy(root))
    except Exception as exc:  # noqa: BLE001 — graceful SKIP boundary
        # 예외 발생 시도 graceful SKIP — driver 전체 중단 안 함.
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
    """`validate/code.json` reader — `_validate.py` 의 R-CODE 룰 입력.

    미존재 시 `{}` 반환 (R-CODE 룰이 SKIP 처리).
    """
    path = ctx.validate_code_json_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def tool_result(code_payload: dict[str, Any], tool: str) -> dict[str, Any] | None:
    """`code.json` 의 `tools` list 에서 특정 도구 결과 추출.

    `_validate.py` 의 R-CODE-1 (pytest) + R-CODE-2 (ruff) 평가용.
    미발견 시 None.
    """
    tools = code_payload.get("tools", [])
    for entry in tools:
        if isinstance(entry, dict) and entry.get("tool") == tool:
            return entry
    return None
