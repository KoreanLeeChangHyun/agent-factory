"""worker_return_parser.py - Parse worker return 2-line format + emit advisory warning.

Parse the 2-line format returned by workers (worker-sonnet / worker-opus / explorer series),
When a commit is missed, an [ADVISORY] warning is recorded in workflow.log.

Return format (2-line convention):
    Status: Success | Partial success | failure
    commit: <7-40 character SHA> | doesn't exist

Legacy one-line format (no commit lines):
    Status: Success | Partial success | failure

Design principles:
    - Automatic forced transition / kanban move / finalization step skip MUST NOT
    - Advisory emit is a non-blocking / no-op branch — 0 impact on existing finalization flow
    - Only emits a warning log when "commit: none" or a commit line is not provided.
    - Fully preserved user manual recovery path:
        flow-merge --force / Board UI 1-click commit / /wf -e rework
"""

from __future__ import annotations

import re
from typing import Optional

from flow.flow_logger import append_log


# Commit line regular expression: "Commit: <SHA (7 to 40 hex characters)>" or "commit: none"
_COMMIT_LINE_RE = re.compile(r"^Commit:\s*([0-9a-f]{7,40}|None)\s*$", re.IGNORECASE)

# Status line regular expression: "Status: Success | Partial success | failure"
_STATUS_LINE_RE = re.compile(r"^Status:\s*(Success|Partial Success|Failure|Failed)\s*$")


def parse_worker_return(stdout: str) -> tuple[Optional[str], Optional[str]]:
    """The worker returns a (status, commit) tuple by parsing stdout.

    Two-line format (standard):
        Status: Success → ("success", None) or ("success", "abc1234")
        Commit: abc1234 → commit parsing

    One-line legacy format (no commit line):
        Status: Success → ("success", None)

    Incorrect format (status line not recognized):
                                    → (None, None)

    Args:
        stdout: The entire stdout string returned by the worker.

    Returns:
        (status, commit) tuple.
          - status: "success" | "Partial success" | "failure" | None (if parsing fails)
          - commit: 7~40 characters hex SHA | "doesn't exist" | None (if there is no commit line or parsing fails)
    """
    if not stdout:
        return (None, None)

    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        return (None, None)

    # Parsing the first status line
    status_match = _STATUS_LINE_RE.match(lines[0])
    if not status_match:
        return (None, None)

    status_map = {
        "Success": "success",
        "Partial Success": "Partial success",
        "Failure": "failure",
        "Failed": "failure",
    }
    status: str = status_map[status_match.group(1)]

    # Parse the second commit line (if none, legacy 1-line format)
    if len(lines) < 2:
        return (status, None)

    commit_match = _COMMIT_LINE_RE.match(lines[1])
    if not commit_match:
        # If there is a second line but it is not in commit format → considered legacy
        return (status, None)

    commit: str = commit_match.group(1)
    if commit.lower() == "none":
        commit = "doesn't exist"
    return (status, commit)


def emit_commit_advisory(
    registry_key: str,
    abs_work_dir: str,
    status: str,
    commit: Optional[str],
) -> None:
    """When a commit is missed, an [ADVISORY] warning is recorded in workflow.log.

    A warning is emitted only if commit == "doesn't exist" or commit is None.
    If the commit is a valid SHA, no action is performed.

    The warning message only guides the user through a manual recovery path.
    Forced state transition / kanban move / finalization step skip, etc.
    MUST NOT perform any auto-enforcement policy.

    User Manual Recovery Path (Completely Preserved):
        - flow-merge --force <T-NNN>
        - Board UI 1-click commit
        - /wf -e rework

    Args:
        registry_key: Workflow identifier (YYYYMMDD-HHMMSS).
        abs_work_dir: Absolute path where workflow.log is located.
        status: Worker return status ("success" | "Partial success" | "failure").
        commit: Parsed commit value. If it is a valid SHA, skip emit.
    """
    # No need for advisory if SHA is valid — no-op
    if commit is not None and commit != "doesn't exist":
        return

    commit_repr = commit if commit is not None else "N/A"
    message = (
        f"[ADVISORY] worker returned commit={commit_repr}; "
        f"status={status}; "
        f"User manual training path guidance"
        f"(flow-merge --force / Board 1 click / /wf -e)"
    )
    # Non-blocking: append_log silently absorbs all exceptions
    append_log(abs_work_dir, "WARN", message)


def emit_report_advisory(
    registry_key: str,
    abs_work_dir: str,
    report_path: str,
) -> None:
    """After completing the REPORT step, verify the existence of the report.md disk (advisory only).

    T-447: Reporter agent says 'Subagents should return findings as text, not write'
    If the Write tool is blocked by the 'report files' SDK policy, report.md will be written to disk.
    Advisory to detect regressions where a workflow is reported as completed normally without being created.

    A WARN log is emitted only when the report.md file does not exist on disk.
    If the file exists, no action is performed (no-op).

    Design principles:
        advisory only — MUST NOT force transfer/autoregress/autoblock.
        T-411 finalize AND guard discard example citation: Automatic coercion is not the verification itself.
        problem. This function emits only WARN log + metrics events.
        The introduction of automatically enforced policies without the user's explicit consent is absolutely prohibited.

    User Manual Recovery Path (Completely Preserved):
        - Report.md can be created by integrating work/ in the main session
        - Board UI 1-click commit
        - /wf -e rework

    Args:
        registry_key: Workflow registry key (e.g. 20260508-191559).
        abs_work_dir: Absolute path to the workflow work directory. workflow.log location.
        report_path: Absolute path to the report.md file.
    """
    import os

    # No need for advisory if file exists — no-op
    if os.path.isfile(report_path):
        return

    message = (
        f"[ADVISORY] reporter returned without report.md (path={report_path})\n"
        f"- Possibility that the SDK blocked the write of the subagent \n"
        f"- User manual repair: report.md can be created by work/ integration in main session"
    )
    # Non-blocking: append_log silently absorbs all exceptions
    append_log(abs_work_dir, "WARN", message)

    # metrics events emit (try/except non-blocking protection)
    try:
        from engine.core.metrics import append_event  # noqa: PLC0415

        payload = {
            "report_path": report_path,
            "signal_summary": "reporter returned without report.md disk write",
        }
        append_event(abs_work_dir, "report.missing", payload)
    except Exception:
        # Metrics emit failure is absorbed so as not to break the advisory itself
        pass
