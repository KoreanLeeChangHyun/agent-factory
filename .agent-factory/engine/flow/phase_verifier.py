#!/usr/bin/env -S python3 -u
"""phase verifier.py — VALIDATE step rule-based verification engine.

0 LLM calls LUB IO validation only.
bin/flow-phase-verify

T-452 §1.1 / §2.4 / §10.1 / §10.6 Specified.

VALIDATE Step Charge:
    - WORK BEFORE / REPORT BEFORE.
    - Verify the output quantitative rule base ( 0 LLM calls).
    - Input: work/WXX-*.md, plan. md
    - Output: verifier results + retry-context.json (with shield)

The command-specific verification branch:
    - implement / refactor / build → _verify_implement_like
        (1) All W# ID exists as work/<ID>-*. md
        (2) git diff --name-only head file number ≥ 1
    - research → _verify_research
        (1) All W## Outputs
        (2) report.md or work/RPT-*.md's ## header ≥ 3
        (3) Mermaid block ≥ 1
    - review / analyze → _verify_review
        (1) All W## Outputs
        (2) work/or report.md in "verdict"/"conclusion"/"Decision"/"Verdict" keywords ≥ 1
    - architect → _verify_architect
        (1) All W## Outputs
        (2) Mermaid block ≥ 2
        (3) Section header ≥ 4

LLM call 0 rules base force:
    - 0 API calls for anthropic / claude * SDK / API.
    - All verifications only use file IO + regular + subprocess (git).

CLI:
    python3 phase_verifier.py <registry_key>
    End code: 0 = pass, 1 = failure, 2 = usage error
"""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys

# Determine the project root (using resolve_* helpers in engine/common.py)
_engine_dir: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from common import resolve_project_root, resolve_work_dir  # noqa: E402

# Verifier results standard tuple
# (ok: bool, reason: str, failed_step_ids: list[str])
VerifyResult = tuple[bool, str, list[str]]


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------


def verify_validate_phase(registry_key: str) -> VerifyResult:
    """VALIDATE Step entry point — branching according to the command.

    Payment Terms:
        1. FAQ .agent-factory/runs/<key>/)
        2. Extract command from init-result.json or .context.json.
        3. FAQs plan.md load.
        4. The command quarter 4 dispatch.
        5. FAQs return result (w03 helper calling  write retry context on fail).

    Args:
        registry key: workflow registry key (YYYYMMDD-HMMSS) or work dir path.

    Returns:
        VerifyResult (ok, reason, failed_step_ids):
            - ok: True Shi verifier passing, False failure.
            - reason: 1 line text passing / shielding.
            - failed step ids: List of Warker IDs pointed by verifier when failed.
    """
    # 1. Determine work_dir (absolute path)
    project_root = resolve_project_root()
    rel_work_dir = resolve_work_dir(registry_key, project_root=project_root)
    if os.path.isabs(rel_work_dir):
        work_dir = rel_work_dir
    else:
        work_dir = os.path.join(project_root, rel_work_dir)

    if not os.path.isdir(work_dir):
        return (False, f"work_dir not found: {work_dir}", [])

    # 2. Command extraction
    command = _read_command(work_dir)
    if command is None:
        return (False, "command not found in init-result.json or .context.json", [])

    # 3. Load plan.md
    plan_path = os.path.join(work_dir, "plan.md")
    if not os.path.isfile(plan_path):
        return (False, f"plan.md not found: {plan_path}", [])
    try:
        with open(plan_path, encoding="utf-8") as fh:
            plan_md = fh.read()
    except OSError as exc:
        return (False, f"plan.md read failed: {exc}", [])

    # 4. Dispatch of 4 types of command branches
    cmd_lower = command.strip().lower()
    if cmd_lower in {"implement", "refactor", "build"}:
        return _verify_implement_like(work_dir, plan_md)
    if cmd_lower == "research":
        return _verify_research(work_dir, plan_md)
    if cmd_lower in {"review", "analyze"}:
        return _verify_review(work_dir, plan_md)
    if cmd_lower == "architect":
        return _verify_architect(work_dir, plan_md)

    return (False, f"unknown command: {command}", [])


# ---------------------------------------------------------------------------
# 4 types of branches per command
# ---------------------------------------------------------------------------


def _verify_implement_like(work_dir: str, plan_md: str) -> VerifyResult:
    """Implement / refactor / build validation.

    Payment Terms:
        (1) All W# ID exists as work/<ID>-*.md.
        (2) git diff --name-only head file number ≥ 1 (worktree standard).
        (3) WORKFLOW WORKTREE=true Head commit number ≥ 1.

    Args:
        work dir: workflow work directory absolute path.
        plan md: plan.md file content.

    Returns:
        VerifyResult (ok, reason, failed_step_ids).
    """
    _, missing_ids = _check_work_files_exist(plan_md, work_dir)
    if missing_ids:
        return (
            False,
            f"implement: missing work files {missing_ids}",
            missing_ids,
        )

    diff_count = _check_git_diff(work_dir)
    if diff_count < 1:
        return (False, "implement: no git diff (0 worktree changes)", [])

    # Or, avoid false-positives by passing ahead >= 1 (normal) cases.
    if _is_worktree_enabled_lazy():
        ahead = _check_commits_ahead(work_dir)
        if ahead == 0:
            return (
                False,
                "implement: worktree commits ahead = 0 (missing worker commit)",
                [],
            )

    return (True, "ok: implement verifier passed", [])


def _verify_research(work_dir: str, plan_md: str) -> VerifyResult:
    """Research validation (light).

    Payment Terms:
        (1) Existence of output.
        (2) report.md or work/RPT-*.md's ## header ≥ 3.
        (3) Mermaid block ≥ 1.

    Args:
        work dir: workflow work directory absolute path.
        plan md: plan.md file content.

    Returns:
        VerifyResult (ok, reason, failed_step_ids).
    """
    _, missing_ids = _check_work_files_exist(plan_md, work_dir)
    if missing_ids:
        return (False, f"research: missing work files {missing_ids}", missing_ids)

    aggregated = _aggregate_md_content(work_dir)
    section_count = _count_sections(aggregated)
    if section_count < 3:
        return (
            False,
            f"research: missing sections (got {section_count}, need 3)",
            [],
        )

    mermaid_count = _count_mermaid_blocks(aggregated)
    if mermaid_count < 1:
        return (False, "research: missing mermaid block", [])

    return (True, "ok: research verifier passed", [])


def _verify_review(work_dir: str, plan_md: str) -> VerifyResult:
    """review / analyze validation (contrast).

    Payment Terms:
        (1) Existence of output.
        (2) "verdict" / "conclusion" / "Decision" / "Verdict" keywords ≥ 1.

    Args:
        work dir: workflow work directory absolute path.
        plan md: plan.md file content.

    Returns:
        VerifyResult (ok, reason, failed_step_ids).
    """
    _, missing_ids = _check_work_files_exist(plan_md, work_dir)
    if missing_ids:
        return (False, f"review: missing work files {missing_ids}", missing_ids)

    aggregated = _aggregate_md_content(work_dir)
    keywords = ("verdict", "conclusion", "Decision", "Verdict")
    if not any(kw in aggregated for kw in keywords):
        return (False, "review: missing verdict section", [])

    return (True, "ok: review verifier passed", [])


def _verify_architect(work_dir: str, plan_md: str) -> VerifyResult:
    """architect verification.

    Payment Terms:
        (1) Existence of output.
        (2) Mermaid block ≥ 2.
        (3) Section header ≥ 4.

    Args:
        work dir: workflow work directory absolute path.
        plan md: plan.md file content.

    Returns:
        VerifyResult (ok, reason, failed_step_ids).
    """
    _, missing_ids = _check_work_files_exist(plan_md, work_dir)
    if missing_ids:
        return (False, f"architect: missing work files {missing_ids}", missing_ids)

    aggregated = _aggregate_md_content(work_dir)
    mermaid_count = _count_mermaid_blocks(aggregated)
    if mermaid_count < 2:
        return (
            False,
            f"architect: insufficient diagrams (got {mermaid_count}, need 2)",
            [],
        )

    section_count = _count_sections(aggregated)
    if section_count < 4:
        return (
            False,
            f"architect: insufficient sections (got {section_count}, need 4)",
            [],
        )

    return (True, "ok: architect verifier passed", [])


# ---------------------------------------------------------------------------
# common helper
# ---------------------------------------------------------------------------


# Extract W## ID from H3 header of plan.md (skill_mapper.py:670 pattern matching)
_W_ID_PATTERN = re.compile(r"^###\s+(W\d+)[:\s]", re.MULTILINE)

# fallback: Direct matching of table ID column (`| W01 |`)
_W_ID_TABLE_PATTERN = re.compile(r"^\s*\|\s*(W\d+)\s*\|", re.MULTILINE)

# Section header (## or ###)
_SECTION_PATTERN = re.compile(r"^#{2,3}\s+", re.MULTILINE)

# Mermaid code block
_MERMAID_PATTERN = re.compile(r"```mermaid\b", re.MULTILINE)


def _check_work_files_exist(
    plan_md_content: str,
    work_dir: str,
) -> tuple[list[str], list[str]]:
    """execute the work/<ID>-*.md exists after the W## ID extraction.

    Extract:
        - Primary: H3 header (`### W01:`) — skill mapper.py:670 patterns.
        - Fallback: Table ID column (`  W01 |`) — plan validator.py compatible.

    RPT header (`### RPT:`) excludes — this verifier only validates the Walker output.

    Args:
        plan md content: plan.md file content.
        work dir: workflow work directory absolute path.

    Returns:
        (existing ids, missing ids): Both lists are sorted.
    """
    ids: set[str] = set()
    for match in _W_ID_PATTERN.finditer(plan_md_content):
        ids.add(match.group(1))
    for match in _W_ID_TABLE_PATTERN.finditer(plan_md_content):
        ids.add(match.group(1))

    work_subdir = os.path.join(work_dir, "work")
    existing: list[str] = []
    missing: list[str] = []

    for wid in sorted(ids):
        pattern = os.path.join(work_subdir, f"{wid}-*.md")
        matches = glob.glob(pattern)
        # In addition to the context slice (work/<ID>-context.md / work/context/<ID>*.md)
        # Verify that there is an actual output file — this verifier has a slice exclusion policy.
        produced = [p for p in matches if not p.endswith("-context.md")]
        if produced:
            existing.append(wid)
        else:
            missing.append(wid)

    return (existing, missing)


def _count_sections(md_content: str) -> int:
    """################################################################################################################################################################################################################################################################

    Args:
        md content: Markdown string.

    Returns:
        More
    """
    return len(_SECTION_PATTERN.findall(md_content))


def _count_mermaid_blocks(md_content: str) -> int:
    """... Count the number of code blocks.

    Args:
        md content: Markdown string.

    Returns:
        Mermaid code block number.
    """
    return len(_MERMAID_PATTERN.findall(md_content))


def _check_git_diff(work_dir: str) -> int:
    """git diff --name-only HEAD

    In the work tree isolated environment, find the git parent of work dir and call git -C.
    subprocess failed / git Uninstalled / Returns 0 when 5 seconds timeout

    Args:
        work dir: workflow work directory absolute path.

    Returns:
        Number of changed files (line count).
    """
    git_root = _find_git_root(work_dir)
    if git_root is None:
        return 0

    try:
        result = subprocess.run(
            ["git", "-C", git_root, "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 0

    if result.returncode != 0:
        return 0

    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    return len(lines)


def _check_commits_ahead(work_dir: str) -> int:
    """development.. Returns the number of commits between HEAD.

    Walker Commit Signal for missing turnover. Worktree Insulating Environment
    `git diff --name-only HEAD` is for development, even if the work tree changes more than 1
    If you do not have a real commit, the change is missing at the time of your stay.

    Returns:
        ≥ 1: Normal (commit existence)
        0: Commit Missing Signal — Caller Should Block
        -1: Cannot be checked (brand/base migration, subprocess failure, 5 seconds timeout) —
            (false-positive)

    Args:
        work dir: workflow work directory absolute path.
    """
    git_root = _find_git_root(work_dir)
    if git_root is None:
        return -1
    try:
        proc = subprocess.run(
            ["git", "-C", git_root, "rev-list", "--count", "develop..HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return -1
    if proc.returncode != 0:
        return -1
    try:
        return int(proc.stdout.strip())
    except ValueError:
        return -1


def _is_worktree_enabled_lazy() -> bool:
    """call worktree manager.is worktree enabled as a delay import.

    Worktree manager at the top of the phase verifier module to preserve modular independence
    not import directly, but only lazy import at the point of call. False
    fallback does not affect existing verification flow.

    Returns:
        WORKFLOW WORKTREE=true and true.
    """
    try:
        from .worktree_manager import is_worktree_enabled

        return is_worktree_enabled()
    except Exception:
        return False


def _aggregate_md_content(work_dir: str) -> str:
    """work/W*.md + work/RPT-*.md + report.md

    Used as input of section/mermaid counting helper.

    Args:
        work dir: workflow work directory absolute path.

    Returns:
        A string that joins all markdown content.
    """
    chunks: list[str] = []
    work_subdir = os.path.join(work_dir, "work")

    patterns = [
        os.path.join(work_subdir, "W*.md"),
        os.path.join(work_subdir, "RPT-*.md"),
    ]
    seen: set[str] = set()
    for pattern in patterns:
        for path in sorted(glob.glob(pattern)):
            if path in seen:
                continue
            seen.add(path)
            # Excluding context slices
            if path.endswith("-context.md"):
                continue
            try:
                with open(path, encoding="utf-8") as fh:
                    chunks.append(fh.read())
            except OSError:
                continue

    report_path = os.path.join(work_dir, "report.md")
    if os.path.isfile(report_path):
        try:
            with open(report_path, encoding="utf-8") as fh:
                chunks.append(fh.read())
        except OSError:
            pass

    return "\n".join(chunks)


# ---------------------------------------------------------------------------
# internal utility
# ---------------------------------------------------------------------------


def _read_command(work_dir: str) -> str | None:
    """init-result.json or .context.json

    Tag:
        1. init-result.json
        2. .context.json

    Args:
        work dir: workflow work directory absolute path.

    Returns:
        command string or None (unless or parsing failed).
    """
    candidates = [
        os.path.join(work_dir, "init-result.json"),
        os.path.join(work_dir, ".context.json"),
    ]
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        cmd = data.get("command")
        if isinstance(cmd, str) and cmd.strip():
            return cmd
    return None


def _find_git_root(start_dir: str) -> str | None:
    """From start dir, go up and find .git directory.

    Args:
        start dir: navigation start directory absolute path.

    Returns:
        git root absolute path or None.
    """
    current = os.path.abspath(start_dir)
    while True:
        if os.path.isdir(os.path.join(current, ".git")) or os.path.isfile(
            os.path.join(current, ".git")
        ):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


# ---------------------------------------------------------------------------
# Perpetuating results (W03 scope)
# ---------------------------------------------------------------------------


def _write_retry_context_on_fail(
    work_dir: str,
    failure_reason: str,
    failed_steps: list[str],
) -> None:
    """retry-context.json

    Tag:
        - last failure phase: Fixed "VALIDATE"
        - last_failure_reason: failure_reason.
        - failed_work_steps: failed_steps.

    The rest 2 field (retry count, prompt hints) is updated by T-455 sentinel/handler.
    If you have an existing file, please update the part with read-modify-write, and we'll update it.

    Args:
        work dir: workflow work directory absolute path.
        failure reason: confirmation validate phase return reason message.
        failed steps: List of Warker IDs with verifier.
    """
    retry_path = os.path.join(work_dir, "retry-context.json")

    # Read existing file (if present)
    existing: dict = {}
    if os.path.isfile(retry_path):
        try:
            with open(retry_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if not isinstance(existing, dict):
                existing = {}
        except (OSError, json.JSONDecodeError):
            existing = {}

    # Only 3 fields of this ticket are updated, the rest are preserved.
    existing["last_failure_phase"] = "VALIDATE"
    existing["last_failure_reason"] = failure_reason
    existing["failed_work_steps"] = list(failed_steps)

    # write
    with open(retry_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point — call flow-phase-verify wrapper.

    Usage:
        python3 phase_verifier.py <registry_key>

    Tag:
        0 = Pass (verifier ok=True).
        1 = failed (verifier ok=False).
        2 = Usage error (unlimited/multiple).

    Args:
        argv: command line argument list (None-side sys.argv[1:] use).

    Returns:
        Skip to content
    """
    if argv is None:
        argv = sys.argv[1:]
    if len(argv) != 1:
        print("usage: phase_verifier.py <registry_key>", file=sys.stderr)
        return 2

    registry_key = argv[0]
    ok, reason, failed = verify_validate_phase(registry_key)
    if ok:
        print(f"OK: {reason}")
        return 0

    failed_str = ",".join(failed) if failed else "-"
    print(f"FAIL: {reason} (failed={failed_str})")
    work_dir = os.path.join(".agent-factory", "runs", registry_key)
    try:
        _write_retry_context_on_fail(work_dir, reason, failed)
    except OSError as exc:
        print(f"[WARN] Failed to write retry-context.json: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
