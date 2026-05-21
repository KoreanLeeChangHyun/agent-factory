"""conveyor_cli.py - Conveyor board subcommand implementation and CLI parser module.

Business logic for each subcommand (cmd_* functions), argparse parser configuration (build_parser),
This is a business layer module responsible for subcommand dispatch.
It is separated from conveyor.py and depends on work_request_repository.py.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime

from flow.work_request_repository import (
    add_relation,
    create_work_request_xml,
    find_work_request_file,
    normalize_work_request_number,
    get_max_work_request_number,
    move_work_request_to_status_dir,
    remove_relation,
    update_prompt,
    update_result,
    write_work_request_xml,
    parse_work_request_xml,
    err,
    log,
    CONVEYOR_DIR,
    CONVEYOR_DRAFT_DIR,
    CONVEYOR_ACCEPTED_DIR,
    CONVEYOR_EXECUTING_DIR,
    CONVEYOR_VERIFYING_DIR,
    CONVEYOR_COMPLETE_DIR,
    STATUS_DIR_MAP,
    COLUMN_MAP,
    update_work_request_status,
    validate_transition,
)
from core.validation.prompt_validator import validate as prompt_validate
from constants import QUALITY_THRESHOLD


# ─── Path constant ──────────────────────────────────────────────────────────────────

from common import resolve_project_root

_SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT: str = resolve_project_root()

# ─── Merge conflict signal pattern ──────────────────────────────────────────────────────

_CONFLICT_SIGNAL_RE: re.Pattern[str] = re.compile(
    r"(merge\s*conflict|merge\s+conflict|CONFLICT)",
    re.IGNORECASE,
)
"""Regular expression to detect conflict signals in merge_result.error_message.

In the W05 test, import directly with ``from flow.conveyor_cli import _CONFLICT_SIGNAL_RE``
If possible, expose it at the module level.

Matching pattern:
- ``Merge Conflict`` / ``Merge Conflict`` (Korean, space optional)
- ``merge conflict`` / ``Merge Conflict``, etc. (case irrelevant)
- ``CONFLICT`` (git stdout prefix format)
"""


# ─── Session Helper ──────────────────────────────────────────────────────────────────

import json
import urllib.request

_TMUX_WINDOW_PREFIX: str = "P:"


def _resolve_server_port() -> "int | None":
    """Resolve the server port.

    Extract the port from the _WF_SERVER_PORT environment variable or the .agent-factory/.board.url file.

    Returns:
        Port number (int) or None (if not interpretable).
    """
    # 1) Environmental variables take precedence
    port_env = os.environ.get("_WF_SERVER_PORT")
    if port_env:
        try:
            return int(port_env)
        except ValueError:
            pass

    # 2) Parse .board.url file: http://127.0.0.1:PORT/board
    board_url_path = os.path.join(_PROJECT_ROOT, ".agent-factory", ".board.url")
    try:
        with open(board_url_path, "r", encoding="utf-8") as f:
            url = f.read().strip()
        # Extract PORT from http://127.0.0.1:PORT/... format
        if "://" in url:
            host_part = url.split("://", 1)[1]  # 127.0.0.1:PORT/...
            host_port = host_part.split("/")[0]  # 127.0.0.1:PORT
            if ":" in host_port:
                return int(host_port.split(":")[1])
    except (OSError, ValueError):
        pass

    return None


def _kill_work_request_session(work_request_number: str) -> None:
    """Terminates the workflow session for the work_request in the active session.

    Terminate the session via HTTP API (server running),
    When the server is not started, tmux kill-window fallback is used.
    It should be called only after a successful state transition.

    Args:
        work_request_number: WorkRequest number (WR-NNN format).
    """
    port = _resolve_server_port()

    if port is not None:
        # HTTP API path: Check the session list and kill the WorkRequest matching session.
        try:
            list_url = f"http://127.0.0.1:{port}/terminal/workflow/list"
            req = urllib.request.Request(list_url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            sessions = data if isinstance(data, list) else data.get("sessions", [])
            session_id = None
            for session in sessions:
                if session.get("work_request") == work_request_number:
                    session_id = session.get("session_id") or session.get("id")
                    break

            if session_id:
                kill_url = f"http://127.0.0.1:{port}/terminal/workflow/kill"
                kill_body = json.dumps({"session_id": session_id}).encode("utf-8")
                kill_req = urllib.request.Request(
                    kill_url,
                    data=kill_body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(kill_req, timeout=5) as kill_resp:
                    kill_resp.read()
                log("INFO", f"conveyor.py: http kill session_id={session_id} ({work_request_number})")
            else:
                log("INFO", f"conveyor.py: no active session found for {work_request_number}")
            return
        except Exception:
            # HTTP errors are unrelated to state transitions, so they are ignored and returned.
            return

    # tmux fallback when port is not interpreted (backwards compatible)
    if not os.environ.get("TMUX"):
        return

    window_name = f"{_TMUX_WINDOW_PREFIX}{work_request_number}"

    try:
        # Check if window exists
        list_result = subprocess.run(
            ["tmux", "list-windows", "-F", "#W"],
            capture_output=True,
            text=True,
        )
        if list_result.returncode != 0:
            return
        existing_windows = list_result.stdout.strip().splitlines()
        if window_name not in existing_windows:
            return

        # Window index search (prevents the problem of the colon in P:WR-NNN being misinterpreted as session:window)
        idx_result = subprocess.run(
            ["tmux", "list-windows", "-F", "#{window_index}\t#{window_name}"],
            capture_output=True,
            text=True,
        )
        target = window_name  # fallback
        if idx_result.returncode == 0:
            for line in idx_result.stdout.strip().splitlines():
                parts = line.split("\t", 1)
                if len(parts) == 2 and parts[1] == window_name:
                    target = parts[0]
                    break

        subprocess.run(
            ["tmux", "kill-window", "-t", target],
            capture_output=True,
        )
        log("INFO", f"conveyor.py: tmux kill-window {window_name}")
    except Exception:
        # Ignore tmux errors as they are independent of state transitions.
        pass


def _cleanup_worktree_on_leave(work_request_number: str) -> None:
    """When leaving Executing, the connected work tree is automatically cleaned up.

    If the work tree is in an inactive environment or there is no work tree for the work_request, it is quietly skipped.
    If there are uncommitted changes, skip cleanup to prevent data loss.
    Specifies the path to the user (WR-411: When worker commit is missing / finalization fails
    Prevent permanent loss of work due to automatic deletion of the work tree).
    If cleanup fails, only a warning is issued and no exceptions are propagated (no blocking of state transitions).

    Args:
        work_request_number: WorkRequest number (WR-NNN format).
    """
    try:
        from flow.worktree_manager import (
            is_worktree_enabled,
            get_worktree_path,
            has_uncommitted_changes,
            remove_worktree,
        )

        if not is_worktree_enabled():
            return

        wt_path = get_worktree_path(work_request_number)
        if not wt_path:
            return

        if has_uncommitted_changes(wt_path):
            log(
                "WARN",
                f"conveyor.py: skip worktree cleanup — preserve uncommitted changes ({work_request_number}, path={wt_path})",
            )
            print(
                f"[WARN] {work_request_number} worktree has uncommitted changes — skip automatic cleanup",
                flush=True,
            )
            print(f"[WARN] Path: {wt_path}", flush=True)
            print(
                "[WARN] Inspect and manually commit / discard:"
                f"`git -C {wt_path} status`",
                flush=True,
            )
            return

        success = remove_worktree(work_request_number, delete_branch=True)
        if success:
            log("INFO", f"conveyor.py: Worktree automatic cleanup completed ({work_request_number})")
        else:
            print(f"[WARN] {work_request_number} work tree cleanup failed (continue)", flush=True)
    except ImportError:
        pass  # Ignored if the worktree module is not installed (backwards compatible)
    except Exception as e:
        print(f"[WARN] Error cleaning worktree {work_request_number} (continue): {e}", flush=True)


# ─── Subcommand implementation ─────────────────────────────────────────────────────────────


def cmd_create(
    title: str,
    command: str,
    status: str,
    number: str | None = None,
) -> None:
    """Create a new WorkRequest XML.

    If the number is not specified, the maximum WR-NNN number is scanned from the XML file name and automatically numbered +1.
    When specifying a number, after normalization, identical number collisions are checked and, if present, are rejected as an error.
    Depending on the status value, a WR-NNN.xml file is created under work-requests/draft/ or work-requests/accepted/.

    Args:
        title: WorkRequest title. Allows empty strings.
        command: Workflow command (implement, review, research, etc.).
        status: initial status key ("draft" | "accepted"). Converted to XML <status> value through COLUMN_MAP.
        number: Explicit work_request number (WR-NNN, NNN, #N format). Automatic numbering if not specified.
    """
    # Convert status key to status name ("Draft" / "Accepted")
    status_label = COLUMN_MAP.get(status)
    if status_label is None or status not in ("draft", "accepted"):
        err(
            f"Invalid --status value: '{status}'. Specify either 'draft' or 'accepted'."
            f"(Example: flow-conveyor create \"title\" --command implement --status draft)",
            2,
        )

    # Determine the target directory
    target_dir = CONVEYOR_DRAFT_DIR if status == "draft" else CONVEYOR_ACCEPTED_DIR

    if number is not None:
        normalized = normalize_work_request_number(number)
        if normalized is None:
            err(
                f"Invalid --number value: '{number}'. Must be in one of the following formats: WR-NNN, NNN, or #N.",
                2,
            )
        work_request_number = normalized
        existing = find_work_request_file(work_request_number)
        if existing is not None:
            err(
                f"WorkRequest number conflict: {work_request_number} already exists ({existing})."
                f"The number must be unique.",
                2,
            )
    else:
        # Block automatic granting of debug area (900-999) — Repealed 2026-05-05 (workflow.md number area policy / memory rule).
        # Explicit `--number` calls have no effect as they are processed in the if branch above.
        max_num = get_max_work_request_number(exclude_debug_range=True)
        new_num = max_num + 1
        work_request_number = f"WR-{new_num:03d}"

    # File name: WR-NNN.xml fixed
    work_request_file = os.path.join(target_dir, f"{work_request_number}.xml")

    os.makedirs(target_dir, exist_ok=True)
    datetime_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    xml_content = create_work_request_xml(work_request_number, title, datetime_str, command=command)

    # Replace XML <status> tag value with status_label
    # create_work_request_xml records “Accepted” by default, so replace only when status=="draft".
    if status_label != "Accepted":
        xml_content = xml_content.replace(
            "<status>Accepted</status>", f"<status>{status_label}</status>", 1
        )

    try:
        with open(work_request_file, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(xml_content)
            f.write("\n")
    except OSError as e:
        err(f"Failed to create work_request file: {e}")

    suffix = f" ({command})" if command else ""
    print(f"{work_request_number}: {title}{suffix} [{status_label}]")
    log("INFO", f"conveyor.py: create {work_request_number} title={title!r} status={status_label!r}")


def cmd_move(work_request_number: str, target_key: str, force: bool = False) -> None:
    """Change work_request status.

    Verifies the allowable state transition rules and outputs an error if violated.
    If the --force flag is present, the rule is ignored and the movement is forced.

    Args:
        work_request_number: WorkRequest number to move to (WR-NNN format).
        target_key: Target column key (draft/accepted/executing/verifying/complete).
        force: Whether to force movement.

    Raises:
        SystemExit: When there is no work_request or a transition rule is violated.
    """
    target_section = COLUMN_MAP.get(target_key)
    if target_section is None:
        err(f"Invalid target column: '{target_key}'. Allowed values: {', '.join(COLUMN_MAP.keys())}")

    work_request_file = find_work_request_file(work_request_number)
    if work_request_file is None:
        err(f"WorkRequest file {work_request_number} not found")

    work_request_data = parse_work_request_xml(work_request_file)
    current_section = work_request_data["status"]

    # Validating state transition rules (using validate_transition)
    validation_error = validate_transition(current_section, target_section, force)
    if validation_error is not None:
        if validation_error == "":
            # Already in the same state
            print(f"{work_request_number} is already in {target_section} state.")
            return
        err(
            f"{work_request_number} is {validation_error}"
        )

    # After passing validate_transition, re-verify file existence before actual writing (race condition defense)
    if not os.path.isfile(work_request_file):
        # Another session may have already moved the file — seek again in the target directory.
        refreshed = find_work_request_file(work_request_number)
        if refreshed is None:
            err(f"{work_request_number} work_request file was lost in transit (race condition)")
        # Recheck status with rediscovered files
        refreshed_data = parse_work_request_xml(refreshed)
        if refreshed_data["status"] == target_section:
            print(f"{work_request_number} is already in {target_section} state. (processed in another session)")
            return
        # If moved to another state, re-validate transition rules after updating work_request_file
        work_request_file = refreshed
        current_section = refreshed_data["status"]
        validation_error = validate_transition(current_section, target_section, force)
        if validation_error is not None:
            if validation_error == "":
                print(f"{work_request_number} is already in {target_section} state.")
                return
            err(f"{work_request_number} is {validation_error}")

    # Update XML <status>
    try:
        update_work_request_status(work_request_file, target_section)
    except FileNotFoundError:
        # write_work_request_xml detects file loss — check for idempotency after re-scanning
        refreshed = find_work_request_file(work_request_number)
        if refreshed is None:
            err(f"{work_request_number} work_request file was lost updating status (race condition)")
        refreshed_data = parse_work_request_xml(refreshed)
        if refreshed_data["status"] == target_section:
            print(f"{work_request_number} is already in {target_section} state. (processed in another session)")
            return
        err(f"File loss detected during {work_request_number} status update. Current status: {refreshed_data['status']}")

    # Move files to the directory corresponding to the state
    try:
        new_path = move_work_request_to_status_dir(work_request_file, target_section)
        if new_path != work_request_file:
            src_rel = os.path.relpath(work_request_file, _PROJECT_ROOT)
            dst_rel = os.path.relpath(new_path, _PROJECT_ROOT)
            print(f"Move file: {src_rel} ​​→ {dst_rel}")
        work_request_file = new_path
    except FileNotFoundError:
        # File loss during movement — handle normally if already moved
        refreshed = find_work_request_file(work_request_number)
        if refreshed is not None:
            refreshed_data = parse_work_request_xml(refreshed)
            if refreshed_data["status"] == target_section:
                print(f"{work_request_number} is already in {target_section} state. (processed in another session)")
                return
        err(f"{work_request_number} file loss detection during movement")
    except OSError as e:
        err(f"Failed to move work_request file: {e}")

    print(f"{work_request_number}: {current_section} → {target_section}")
    log("INFO", f"conveyor.py: move {work_request_number} {current_section} → {target_section}")

    # Automatic cleanup of work tree when leaving Executing.
    # Executing -> Verifying keeps the workflow worktree available for inspection.
    if current_section == "Executing" and target_section != "Verifying":
        _cleanup_worktree_on_leave(work_request_number)

    # Automatically kill session when transitioning to Accepted:
    # Returning from Executing to Accepted ends the active session for that WorkRequest.
    # Since it is executed after a successful state transition, it does not reach this point if the transition fails (SystemExit after calling err()).
    if target_section == "Accepted" and current_section == "Executing":
        _kill_work_request_session(work_request_number)


def cmd_complete(work_request_number: str) -> None:
    """Change the work_request to Complete and move the file to work-requests/complete/.

    If worktree is enabled, create a feature branch before changing state/moving files.
    Merge into develop. In case of merge conflict, the Complete transition is blocked.

    Update <status> in XML to Complete,
    Move to work-requests/complete/WR-NNN.xml through move_work_request_to_status_dir().

    Args:
        work_request_number: WorkRequest number to complete (WR-NNN format).
    """
    # ── Worktree merge hook (before changing work_request status/moving files) ──
    import sys as _sys
    try:
        from flow.worktree_manager import is_worktree_enabled, get_worktree_path, merge_to_develop, has_uncommitted_changes
        from flow.branch_strategy import get_feature_branch_for_ticket
        if is_worktree_enabled():
            # C-01: Detect dirty worktree → Reject if uncommitted changes exist
            _wt_path = get_worktree_path(work_request_number)
            if _wt_path and has_uncommitted_changes(_wt_path):
                _porcelain = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=_wt_path,
                    capture_output=True,
                    text=True,
                )
                print(f"[ERROR] This is a work tree with uncommitted changes. Complete Blocks the transition.", flush=True)
                print(f"List of uncommitted files:", flush=True)
                for _line in _porcelain.stdout.strip().splitlines():
                    print(f"    - {_line.strip()}", flush=True)
                print(f"Complete with the normal path using flow-merge.", flush=True)
                _sys.exit(1)
            feat_branch = get_feature_branch_for_ticket(work_request_number)
            if _wt_path or feat_branch:
                merge_result = merge_to_develop(work_request_number)
                if not merge_result.success:
                    # Collision decision redundancy:
                    # (1) merge_result.conflicts is not empty
                    # (2) Conflict signal pattern included in error_message
                    # (3) There is sentinel "<unknown-conflict>" in conflicts
                    # If any one of the three is satisfied, it is considered a conflict and the Complete transition is blocked.
                    _sentinel = "<unknown-conflict>"
                    _has_conflict_files = bool(merge_result.conflicts)
                    _has_signal_in_msg = bool(
                        _CONFLICT_SIGNAL_RE.search(merge_result.error_message or "")
                    )
                    _has_sentinel = _sentinel in (merge_result.conflicts or [])
                    _is_conflict = _has_conflict_files or _has_signal_in_msg or _has_sentinel

                    if _is_conflict:
                        print(f"[ERROR] {work_request_number} merge conflict occurred. Complete Blocks the transition.", flush=True)
                        # Output a list of conflicting files — if there is only sentinel or the list is empty, replaced by an instruction message
                        if merge_result.conflicts and not (
                            len(merge_result.conflicts) == 1 and merge_result.conflicts[0] == _sentinel
                        ):
                            print(f"Conflicting files:", flush=True)
                            for cf in merge_result.conflicts:
                                print(f"    - {cf}", flush=True)
                        else:
                            print(
                                f"(List of conflicting files unknown — see error_message)",
                                flush=True,
                            )
                            if merge_result.error_message:
                                print(f"  error_message: {merge_result.error_message}", flush=True)
                        print(f"Please resolve the conflict in the worktree and try again.", flush=True)
                        _sys.exit(1)
                    else:
                        # Conflict pattern check false — Simple failure (e.g. develop checkout failed): print warning and continue
                        print(f"[WARN] Worktree merge failed: {merge_result.error_message}", flush=True)
                else:
                    print(f"{work_request_number}: {merge_result.merged_branch} -> develop merge completed ({merge_result.merge_commit[:8]})", flush=True)
                    log("INFO", f"conveyor.py: worktree merge {merge_result.merged_branch} -> develop ({merge_result.merge_commit[:8]})")
                    if merge_result.merge_commit:
                        try:
                            _work_request_file_for_result = find_work_request_file(work_request_number)
                            if _work_request_file_for_result is not None:
                                update_result(_work_request_file_for_result, {"merge_commit": merge_result.merge_commit})
                                log("INFO", f"conveyor.py: save result.merge_commit ({merge_result.merge_commit[:8]})")
                        except Exception as _ur_err:
                            print(f"[WARN] result.merge_commit failed to save (continue): {_ur_err}", flush=True)
    except ImportError:
        pass  # Ignored if the worktree module is not installed (backwards compatible)
    except Exception as _wt_err:
        print(f"[WARN] Error processing worktree merge (continued): {_wt_err}", flush=True)

    work_request_file = find_work_request_file(work_request_number)
    if work_request_file is None:
        err(f"WorkRequest file {work_request_number} not found")

    work_request_data = parse_work_request_xml(work_request_file)
    current_section = work_request_data["status"]

    # XML <status> updated with Complete
    update_work_request_status(work_request_file, "Complete")

    # Move the file to conveyor/complete/WR-NNN.xml
    if os.path.isfile(work_request_file):
        try:
            new_path = move_work_request_to_status_dir(work_request_file, "Complete")
            if new_path != work_request_file:
                src_rel = os.path.relpath(work_request_file, _PROJECT_ROOT)
                dst_rel = os.path.relpath(new_path, _PROJECT_ROOT)
                print(f"Move file: {src_rel} ​​→ {dst_rel}")
        except OSError as e:
            err(f"Failed to move work_request file: {e}")

    print(f"{work_request_number}: {current_section} → Complete")
    log("INFO", f"conveyor.py: complete {work_request_number} {current_section} → Complete")


def cmd_delete(work_request_number: str) -> None:
    """Delete the work_request XML file.

    Unlike Complete, it deletes the file without preserving the history.

    Args:
        work_request_number: WorkRequest number to delete (WR-NNN format).

    Raises:
        SystemExit: If work_request not found.
    """
    work_request_file = find_work_request_file(work_request_number)
    if work_request_file is None:
        err(f"WorkRequest {work_request_number} not found")

    try:
        os.remove(work_request_file)
    except OSError as e:
        err(f"Failed to delete work_request file: {e}")

    print(f"{work_request_number}: deleted")


def cmd_update_title(work_request_number: str, title: str) -> None:
    """Updates the <title> element of the work_request XML.

    Args:
        work_request_number: WorkRequest number (WR-NNN format).
        title: New title string.

    Raises:
        SystemExit: When work_request file cannot be found or write fails.
    """
    work_request_file = find_work_request_file(work_request_number)
    if work_request_file is None:
        err(f"WorkRequest file {work_request_number} not found")

    try:
        tree = ET.parse(work_request_file)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"Failed to parse work_request file ({work_request_file}): {e}")

    # First search for <title> inside the <metadata> wrapper
    metadata_elem = root.find("metadata")
    if metadata_elem is not None:
        title_elem = metadata_elem.find("title")
        if title_elem is not None:
            title_elem.text = title
        else:
            ET.SubElement(metadata_elem, "title").text = title
    else:
        title_elem = root.find("title")
        if title_elem is not None:
            title_elem.text = title
        else:
            ET.SubElement(root, "title").text = title

    write_work_request_xml(work_request_file, root)

    print(f"{work_request_number}: Title → {title}")


def cmd_set_editing(work_request_number: str, value: bool) -> None:
    """Creates (if not present) or updates the <editing> element within the <metadata> of the work_request XML.

    Args:
        work_request_number: WorkRequest number (WR-NNN format).
        value: Set to “true” if True, “false” if False.

    Raises:
        SystemExit: When work_request file cannot be found or write fails.
    """
    work_request_file = find_work_request_file(work_request_number)
    if work_request_file is None:
        err(f"WorkRequest file {work_request_number} not found")

    try:
        tree = ET.parse(work_request_file)
        root = tree.getroot()
    except (OSError, ET.ParseError) as e:
        err(f"Failed to parse work_request file ({work_request_file}): {e}")

    metadata_elem = root.find("metadata")
    if metadata_elem is None:
        metadata_elem = ET.SubElement(root, "metadata")

    editing_elem = metadata_elem.find("editing")
    if editing_elem is None:
        editing_elem = ET.SubElement(metadata_elem, "editing")
    editing_elem.text = "true" if value else "false"

    write_work_request_xml(work_request_file, root)

    flag_str = "--on" if value else "--off"
    print(f"{work_request_number}: editing → {editing_elem.text} ({flag_str})")


def cmd_update_prompt(
    work_request_number: str,
    command: str = "",
    goal: str = "",
    target: str = "",
    constraints: str = "",
    criteria: str = "",
    context: str = "",
    skip_validation: bool = False,
) -> None:
    """Update <prompt> and <metadata>/<command> in work_request XML.

    After updating, quality verification is performed and an error is output if it is less than QUALITY_THRESHOLD.

    Args:
        work_request_number: WorkRequest number (WR-NNN format).
        command: Workflow command (implement, review, research, etc.).
        goal: The task goal.
        target: target.
        constraints: Constraints (optional, prompt 5 elements).
        criteria: Completion criteria (optional, prompt 5 elements).
        context: Context information (optional, prompt 5 elements).
        skip_validation: If True, quality verification is skipped (used in emergency cases).

    Raises:
        SystemExit: When the work_request file cannot be found or quality verification fails.
    """
    import sys as _sys

    work_request_file = find_work_request_file(work_request_number)
    if work_request_file is None:
        err(f"WorkRequest file {work_request_number} not found")

    updates: dict[str, str] = {}
    if command:
        updates["command"] = command
    if goal:
        updates["goal"] = goal
    if target:
        updates["target"] = target
    if constraints:
        updates["constraints"] = constraints
    if criteria:
        updates["criteria"] = criteria
    if context:
        updates["context"] = context

    if not updates:
        err("There are no fields to update.", 2)

    update_prompt(work_request_file, updates)
    print(f"{work_request_number}: prompt updated")

    # ── Quality verification ────────────────────────────────────────────────────────────
    if skip_validation:
        return

    try:
        with open(work_request_file, "r", encoding="utf-8") as f:
            xml_text = f.read()
    except OSError as e:
        _sys.stderr.write(f"[WARN] Failed to reread quality verification file: {e} \n")
        return

    # Flat structure: directly extract text inside <prompt> tag
    try:
        from core.validation.prompt_validator import extract_active_prompt
        prompt_text = extract_active_prompt(xml_text)
    except Exception:
        # Skip verification if extract_active_prompt fails
        return

    validation_result = prompt_validate(prompt_text)
    quality_score = validation_result["quality_score"]

    if quality_score < QUALITY_THRESHOLD:
        _sys.stderr.write(
            f"[ERROR] Quality verification failed (score={quality_score:.4f} < threshold={QUALITY_THRESHOLD}) \n"
        )
        if validation_result["missing_tags"]:
            _sys.stderr.write(
                f"Missing tags: {', '.join(validation_result['missing_tags'])} \n"
            )
        if validation_result["empty_tags"]:
            _sys.stderr.write(
                f"Empty tags: {', '.join(validation_result['empty_tags'])} \n"
            )
        if validation_result["feedback"]:
            _sys.stderr.write("Feedback: \n")
            for fb in validation_result["feedback"]:
                _sys.stderr.write(f"    - {fb}\n")
        _sys.exit(1)


def cmd_update_result(
    work_request_number: str,
    registrykey: str = "",
    workdir: str = "",
    plan: str = "",
    report: str = "",
    merge_commit: str = "",
) -> None:
    """Updates the <result> sub-element of work_request XML.

    Args:
        work_request_number: WorkRequest number (WR-NNN format).
        registrykey: Workflow registryKey (in YYYYMMDD-HHMMSS format).
        workdir: Relative path to the workflow output directory.
        plan: plan.md relative path.
        report: report.md relative path.
        merge_commit: feature -> develop Merge commit SHA (40 characters hex).

    Raises:
        SystemExit: When work_request file cannot be found or write fails.
    """
    work_request_file = find_work_request_file(work_request_number)
    if work_request_file is None:
        err(f"WorkRequest file {work_request_number} not found")

    updates: dict[str, str] = {}
    if registrykey:
        updates["registrykey"] = registrykey
    if workdir:
        updates["workdir"] = workdir
    if plan:
        updates["plan"] = plan
    if report:
        updates["report"] = report
    if merge_commit:
        updates["merge_commit"] = merge_commit

    if not updates:
        err("There are no fields to update.", 2)

    update_result(work_request_file, updates)
    print(f"{work_request_number}: result updated")


def cmd_show(work_request_number: str) -> None:
    """Outputs detailed information about a specific work_request as structured text.

    Metadata, relationship information, prompts (goal/target/constraints/criteria/context)
    and result information are output in order.

    Args:
        work_request_number: WorkRequest number to search (WR-NNN format).

    Raises:
        SystemExit: If the work_request file cannot be found.
    """
    work_request_file = find_work_request_file(work_request_number)
    if work_request_file is None:
        err(f"WorkRequest {work_request_number} not found")

    work_request_data = parse_work_request_xml(work_request_file)

    number: str = work_request_data.get("number", work_request_number)
    title: str = work_request_data.get("title", "")
    status: str = work_request_data.get("status", "")
    command: str = work_request_data.get("command", "")
    prompt_data: dict = work_request_data.get("prompt", {}) or {}
    result_data: dict | None = work_request_data.get("result")
    relations: list = work_request_data.get("relations", [])

    # ── Header and metadata output ───────────────────────────────────────────────
    print(f"## {number}: {title}")
    print()
    print("### Metadata")
    print(f"- Number: {number}")
    print(f"- Title: {title}")
    print(f"- Status: {status}")
    if command:
        print(f"- Command: {command}")

    # ── Output relationship information ──────────────────────────────────────────────────────────
    if relations:
        print()
        print("### Relations")
        for rel in relations:
            rel_type: str = rel.get("type", "")
            rel_work_request: str = rel.get("work_request", "")
            print(f"- {rel_type}: {rel_work_request}")

    # ── Prompt output ───────────────────────────────────────────────────────────
    has_prompt = any(prompt_data.get(k) for k in ("goal", "target", "constraints", "criteria", "context"))
    if not has_prompt:
        print()
        print("(no prompt)")
    else:
        print()
        print("### Prompt")

        goal: str = prompt_data.get("goal", "")
        if goal:
            print(f"- Goal: {goal.strip()}")

        target: str = prompt_data.get("target", "")
        if target:
            print(f"- Target: {target.strip()}")

        constraints: str = prompt_data.get("constraints", "")
        if constraints:
            print(f"- Constraints: {constraints.strip()}")

        criteria: str = prompt_data.get("criteria", "")
        if criteria:
            print(f"- Criteria: {criteria.strip()}")

        context: str = prompt_data.get("context", "")
        if context:
            print(f"- Context: {context.strip()}")

    # ── Output result information ────────────────────────────────────────────────────────
    print()
    print("### Result")

    if result_data and isinstance(result_data, dict):
        has_content = any(result_data.get(k) for k in ("registrykey", "workdir", "plan", "report"))
        if has_content:
            print("- Has Result: Yes")
            registrykey: str = result_data.get("registrykey", "")
            if registrykey:
                print(f"- RegistryKey: {registrykey}")
            workdir: str = result_data.get("workdir", "")
            if workdir:
                print(f"- Workdir: {workdir}")
            plan: str = result_data.get("plan", "")
            if plan:
                print(f"- Plan: {plan}")
            report: str = result_data.get("report", "")
            if report:
                print(f"- Report: {report}")
        else:
            print("- Has Result: No")
    else:
        print("- Has Result: No")


# ─── Relationship Bidirectional Mapping ───────────────────────────────────────────────────────────
# For each relationship option (type to write to source, reverse type to write to destination)
_RELATION_PAIRS: dict[str, tuple[str, str]] = {
    "depends_on": ("depends-on", "blocks"),
    "derived_from": ("derived-from", "blocks"),
    "blocks": ("blocks", "depends-on"),
}


def _apply_relation(
    source_file: str,
    source_work_request: str,
    target_work_request: str,
    option_name: str,
    *,
    remove: bool = False,
) -> None:
    """Record or remove bidirectional relationships for the single relationship option.

    Args:
        source_file: Original work_request file path.
        source_work_request: Original work_request number (WR-NNN).
        target_work_request: Target work_request number (WR-NNN).
        option_name: Relationship option name (depends_on, derived_from, blocks).
        remove: If True, the relationship is removed.
    """
    target_file = find_work_request_file(target_work_request)
    if target_file is None:
        err(f"Target work_request {target_work_request} file not found")

    forward_type, reverse_type = _RELATION_PAIRS[option_name]
    fn = remove_relation if remove else add_relation

    fn(source_file, forward_type, target_work_request)
    fn(target_file, reverse_type, source_work_request)


def cmd_link(
    work_request_number: str,
    depends_on: str = "",
    derived_from: str = "",
    blocks: str = "",
) -> None:
    """Records relationships between work_requests in both directions.

    For each relationship option, a relationship is added to both the source work_request and the target work_request.
    - --depends-on WR-MMM: depends-on WR-MMM on original + blocks WR-NNN on WR-MMM
    - --derived-from WR-MMM: derived-from WR-MMM to original + blocks WR-NNN to WR-MMM
    - --blocks WR-MMM: blocks WR-MMM on original + depends-on WR-NNN on WR-MMM

    Args:
        work_request_number: Original work_request number (WR-NNN format).
        depends_on: Depending on work_request number.
        derived_from: Derived original work_request number.
        blocks: WorkRequest number to block.
    """
    source_file = find_work_request_file(work_request_number)
    if source_file is None:
        err(f"WorkRequest file {work_request_number} not found")

    options = {"depends_on": depends_on, "derived_from": derived_from, "blocks": blocks}
    applied = []

    for option_name, target in options.items():
        if not target:
            continue
        normalized = normalize_work_request_number(target)
        if normalized is None:
            err(f"Invalid work_request number format: '{target}'. Use the format WR-NNN, NNN, #N.", 2)
        _apply_relation(source_file, work_request_number, normalized, option_name)
        forward_type = _RELATION_PAIRS[option_name][0]
        applied.append(f"{forward_type} {normalized}")

    for desc in applied:
        print(f"{work_request_number}: {desc} relationship added")
    log("INFO", f"conveyor.py: link {work_request_number} {', '.join(applied)}")


def cmd_unlink(
    work_request_number: str,
    depends_on: str = "",
    derived_from: str = "",
    blocks: str = "",
) -> None:
    """Remove relationships between work_requests in both directions.

    Remove the relationship from both XML in the reverse direction of cmd_link.

    Args:
        work_request_number: Original work_request number (WR-NNN format).
        depends_on: Depending on work_request number.
        derived_from: Derived original work_request number.
        blocks: WorkRequest number to block.
    """
    source_file = find_work_request_file(work_request_number)
    if source_file is None:
        err(f"WorkRequest file {work_request_number} not found")

    options = {"depends_on": depends_on, "derived_from": derived_from, "blocks": blocks}
    removed = []

    for option_name, target in options.items():
        if not target:
            continue
        normalized = normalize_work_request_number(target)
        if normalized is None:
            err(f"Invalid work_request number format: '{target}'. Use the format WR-NNN, NNN, #N.", 2)
        _apply_relation(source_file, work_request_number, normalized, option_name, remove=True)
        forward_type = _RELATION_PAIRS[option_name][0]
        removed.append(f"{forward_type} {normalized}")

    for desc in removed:
        print(f"{work_request_number}: {desc} relationship removed")
    log("INFO", f"conveyor.py: unlink {work_request_number} {', '.join(removed)}")


def cmd_board() -> None:
    """The entire Conveyor board status is output in Markdown table format.

    Scan the .conveyor/draft/, .conveyor/accepted/, .conveyor/executing/, and .conveyor/verifying/ directories respectively.
    Map directly to the Draft/Accepted/Executing/Verifying columns and in the work-requests/complete/ directory.
    WorkRequests are grouped and printed in the Complete column.
    The Complete column displays only the most recent 10 cases and also outputs the total number of cases.
    If there is no work_request in each column, "(doesn't exist)" is output.

    Output Format:
        ## Conveyor Board

        ### Draft
        | WorkRequest | Title | Command |
        ...

        ### Complete (N total, display the most recent 10)
        | WorkRequest | Title |
        ...
    """
    # ── Column definition ─────────────────────────────────────────────────────────────────
    COLUMNS = ["Draft", "Accepted", "Executing", "Verifying", "Complete"]
    grouped: dict[str, list[dict]] = {col: [] for col in COLUMNS}

    # ── Directory scan by status (directory is SSoT) ─────────────────────────────────
    # Directory -> Column Mapping: draft/accepted/executing/verifying.
    _DIR_COLUMN_MAP = [
        (CONVEYOR_DRAFT_DIR, "Draft"),
        (CONVEYOR_ACCEPTED_DIR, "Accepted"),
        (CONVEYOR_EXECUTING_DIR, "Executing"),
        (CONVEYOR_VERIFYING_DIR, "Verifying"),
    ]
    for scan_dir, column in _DIR_COLUMN_MAP:
        if not os.path.isdir(scan_dir):
            continue
        for fname in os.listdir(scan_dir):
            if not (fname.startswith("WR-") and fname.endswith(".xml")):
                continue
            fpath = os.path.join(scan_dir, fname)
            try:
                work_request_data = parse_work_request_xml(fpath)
            except SystemExit:
                log("WARN", f"conveyor.py: board - parse_work_request_xml failed: {fname}")
                continue

            grouped[column].append({
                "number": work_request_data.get("number", ""),
                "title": work_request_data.get("title", ""),
                "command": work_request_data.get("command", ""),
            })

    # ── complete Directory scan ───────────────────────────────────────────────────────
    if os.path.isdir(CONVEYOR_COMPLETE_DIR):
        for fname in os.listdir(CONVEYOR_COMPLETE_DIR):
            if not (fname.startswith("WR-") and fname.endswith(".xml")):
                continue
            fpath = os.path.join(CONVEYOR_COMPLETE_DIR, fname)
            try:
                work_request_data = parse_work_request_xml(fpath)
            except SystemExit:
                log("WARN", f"conveyor.py: board - parse_work_request_xml failed: {fname}")
                continue

            grouped["Complete"].append({
                "number": work_request_data.get("number", ""),
                "title": work_request_data.get("title", ""),
                "command": "",
            })

    # ── Sort by number (WR-NNN → NNN number ascending) ───────────────────────────
    def _work_request_sort_key(t: dict) -> int:
        num_str = t.get("number", "WR-0").removeprefix("WR-")
        return int(num_str) if num_str.isdigit() else 0

    for col in COLUMNS[:-1]:
        grouped[col].sort(key=_work_request_sort_key)

    # Complete displays only the 10 most recent items in descending number order (newest first).
    grouped["Complete"].sort(key=_work_request_sort_key, reverse=True)
    done_total = len(grouped["Complete"])
    grouped["Complete"] = grouped["Complete"][:10]

    # ── Output ────────────────────────────────────────────────────────────────────
    print("## Conveyor Board")

    for col in COLUMNS[:-1]:
        print(f"\n### {col}")
        work_requests = grouped[col]
        if not work_requests:
            print("(doesn't exist)")
        else:
            print("| WorkRequest | Title | Command |")
            print("|--------|-------|---------|")
            for t in work_requests:
                number = t["number"]
                title = t["title"]
                command = t["command"]
                print(f"| {number}  | {title} | {command} |")

    # Complete column
    print(f"\n ### Complete (Total {done_total}, showing the most recent 10)")
    work_requests = grouped["Complete"]
    if not work_requests:
        print("(doesn't exist)")
    else:
        print("| WorkRequest | Title |")
        print("|--------|-------|")
        for t in work_requests:
            number = t["number"]
            title = t["title"]
            print(f"| {number}  | {title} |")


# State key -> (directory, display state name) mapping
_STATUS_SCAN_MAP: dict[str, tuple[str, str]] = {
    "draft": (CONVEYOR_DRAFT_DIR, "Draft"),
    "accepted": (CONVEYOR_ACCEPTED_DIR, "Accepted"),
    "executing": (CONVEYOR_EXECUTING_DIR, "Executing"),
    "verifying": (CONVEYOR_VERIFYING_DIR, "Verifying"),
    "complete": (CONVEYOR_COMPLETE_DIR, "Complete"),
}


def cmd_list(status_filter: str = "") -> None:
    """Prints the list of Conveyor work_requests in a one-line summary format.

    You can filter only specific statuses with the --status option.
    If not specified, Accepted, Executing, and Verifying are output.
    Draft is excluded from basic exposure and is output only when explicitly requested.

    Output Format: WR-NNN [Status] Title (number ascending)

    Args:
        status_filter: Status filter key (draft/accepted/executing/verifying/complete).
            If the string is empty, Accepted/Executing/Verifying.
    """
    if status_filter:
        scan_targets = [_STATUS_SCAN_MAP[status_filter]]
    else:
        # Default: accepted + executing + verifying (excluding draft, complete)
        # - draft: Excluding default exposure due to backlog nature (exposed only when --status draft is specified)
        # - complete: Completed work_requests exclude basic exposure
        scan_targets = [
            _STATUS_SCAN_MAP["accepted"],
            _STATUS_SCAN_MAP["executing"],
            _STATUS_SCAN_MAP["verifying"],
        ]

    work_requests: list[dict[str, str]] = []
    for scan_dir, status_label in scan_targets:
        if not os.path.isdir(scan_dir):
            continue
        for fname in os.listdir(scan_dir):
            if not (fname.startswith("WR-") and fname.endswith(".xml")):
                continue
            fpath = os.path.join(scan_dir, fname)
            try:
                work_request_data = parse_work_request_xml(fpath)
            except SystemExit:
                continue
            work_requests.append({
                "number": work_request_data.get("number", ""),
                "title": work_request_data.get("title", ""),
                "status": status_label,
            })

    # Sort in ascending order by number (WR-NNN → NNN number conversion)
    def _sort_key(t: dict[str, str]) -> int:
        num_str = t.get("number", "WR-0").removeprefix("WR-")
        return int(num_str) if num_str.isdigit() else 0

    work_requests.sort(key=_sort_key)

    if not work_requests:
        print("(no work_requests)")
        return

    for t in work_requests:
        print(f"{t['number']}  [{t['status']}]  {t['title']}")


# ─── argparse settings ──────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Constructs and returns an argparse-based CLI parser.

    Returns:
        A configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="conveyor.py",
        description="Conveyor Board Status Management CLI",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # create subcommand
    create_parser = subparsers.add_parser("create", help="Create a new work_request")
    create_parser.add_argument("title", help="work_request title")
    create_parser.add_argument("--command", default="", help="Workflow commands (implement, review, research, etc.)")
    create_parser.add_argument(
        "--status",
        required=True,
        choices=["draft", "accepted"],
        metavar="{draft,accepted}",
        help=(
            "Initial state (required). 'draft'=backlog·things to do in the future, 'accepted'=target of focus now."
            "Example: flow-conveyor create \"title\" --command implement --status draft"
        ),
    )
    create_parser.add_argument(
        "--number",
        default=None,
        help=(
            "Specify work_request number (in the format WR-NNN, NNN, #N). Automatic numbering if not specified."
            "Error when the same number exists."
        ),
    )

    # move subcommand
    move_parser = subparsers.add_parser("move", help="Move the work_request to the specified column")
    move_parser.add_argument("work_request", help="WorkRequest number (WR-NNN, NNN, #N format)")
    move_parser.add_argument(
        "target",
        choices=list(COLUMN_MAP.keys()),
        help="Target column (draft/accepted/executing/verifying/complete)",
    )
    move_parser.add_argument("--force", action="store_true", help="Ignore state transition rules and force movement")

    # complete subcommand
    complete_parser = subparsers.add_parser("complete", help="Move the work_request to Complete and the file to work-requests/complete/")
    complete_parser.add_argument("work_request", help="WorkRequest number (WR-NNN, NNN, #N format)")

    # delete subcommand
    delete_parser = subparsers.add_parser("delete", help="Delete the work_request")
    delete_parser.add_argument("work_request", help="WorkRequest number (WR-NNN, NNN, #N format)")

    # update-prompt subcommand
    update_prompt_parser = subparsers.add_parser("update-prompt", help="Update work_request prompt and command")
    update_prompt_parser.add_argument("work_request", help="WorkRequest number (WR-NNN, NNN, #N format)")
    update_prompt_parser.add_argument("--command", default="", help="Workflow commands (implement, review, research, etc.)")
    update_prompt_parser.add_argument("--goal", default="", help="work goal")
    update_prompt_parser.add_argument("--target", default="", help="Target")
    update_prompt_parser.add_argument("--constraints", default="", help="Constraints (optional, prompt 5 elements)")
    update_prompt_parser.add_argument("--criteria", default="", help="Completion criteria (optional, prompt 5 elements)")
    update_prompt_parser.add_argument("--context", default="", help="Contextual information (optional, prompt 5 elements)")
    update_prompt_parser.add_argument("--skip-validation", action="store_true", default=False, help="Bypass quality verification (for emergency use)")

    # update-result subcommand
    update_result_parser = subparsers.add_parser("update-result", help="Update the result information of the work_request")
    update_result_parser.add_argument("work_request", help="WorkRequest number (WR-NNN, NNN, #N format)")
    update_result_parser.add_argument("--registrykey", default="", help="Workflow registryKey (YYYYMMDD-HHMMSS format)")
    update_result_parser.add_argument("--workdir", default="", help="Workflow output directory relative path")
    update_result_parser.add_argument("--plan", default="", help="plan.md relative path")
    update_result_parser.add_argument("--report", default="", help="report.md relative path")
    update_result_parser.add_argument("--merge-commit", dest="merge_commit", default="", help="feature -> develop merge commit SHA")

    # set-editing subcommand
    set_editing_parser = subparsers.add_parser("set-editing", help="Set the <editing> flag in the work_request XML.")
    set_editing_parser.add_argument("work_request", help="WorkRequest number (WR-NNN, NNN, #N format)")
    set_editing_group = set_editing_parser.add_mutually_exclusive_group(required=True)
    set_editing_group.add_argument("--on", action="store_true", help="Set state to editing")
    set_editing_group.add_argument("--off", action="store_true", help="Turn off editing state")

    # update-title subcommand (update is an alias for update-title)
    update_title_parser = subparsers.add_parser("update-title", help="Update work_request title")
    update_title_parser.add_argument("work_request", help="WorkRequest number (WR-NNN, NNN, #N format)")
    update_title_parser.add_argument("title", nargs="?", default="", help="new title")
    update_title_parser.add_argument("--title", dest="title_flag", default="", help="New title (format --title)")
    update_alias = subparsers.add_parser("update", help="alias for update-title")
    update_alias.add_argument("work_request", help="WorkRequest number (WR-NNN, NNN, #N format)")
    update_alias.add_argument("title", nargs="?", default="", help="new title")
    update_alias.add_argument("--title", dest="title_flag", default="", help="New title (format --title)")

    # link subcommand
    link_parser = subparsers.add_parser("link", help="Records relationships between work_requests in both directions")
    link_parser.add_argument("work_request", help="WorkRequest number (WR-NNN, NNN, #N format)")
    link_parser.add_argument("--depends-on", dest="depends_on", default="", help="Depends on work_request number")
    link_parser.add_argument("--derived-from", dest="derived_from", default="", help="Derived original work_request number")
    link_parser.add_argument("--blocks", default="", help="WorkRequest number to block")

    # unlink subcommand
    unlink_parser = subparsers.add_parser("unlink", help="Remove relationships between work_requests in both directions")
    unlink_parser.add_argument("work_request", help="WorkRequest number (WR-NNN, NNN, #N format)")
    unlink_parser.add_argument("--depends-on", dest="depends_on", default="", help="Depends on work_request number")
    unlink_parser.add_argument("--derived-from", dest="derived_from", default="", help="Derived original work_request number")
    unlink_parser.add_argument("--blocks", default="", help="WorkRequest number to block")

    # board subcommand
    subparsers.add_parser("board", help="Check the overall status of the Conveyor board")

    # list subcommand
    list_parser = subparsers.add_parser("list", help="View Conveyor work_request list")
    list_parser.add_argument(
        "--status",
        choices=["draft", "accepted", "executing", "verifying", "complete"],
        default="",
        help="Status filter (Accepted/Executing/Verifying if not specified)",
    )

    # show subcommand
    show_parser = subparsers.add_parser("show", help="View detailed information on a specific work_request")
    show_parser.add_argument("work_request", help="WorkRequest number (WR-NNN, NNN, #N format)")

    return parser


# ─── Dispatch ──────────────────────────────────────────────────────────────────


def dispatch(args: argparse.Namespace) -> None:
    """Dispatch the parsed CLI argument to the corresponding subcommand handler.

    The branching logic for each subcommand of main() is extracted as an independent function.
    Includes work_request number normalization and validation.

    Args:
        args: Return value of argparse.parse_args().

    Raises:
        SystemExit: In case of incorrect work_request number or subcommand execution error.
    """
    if args.subcommand == "create":
        cmd_create(args.title, args.command, args.status, args.number)

    elif args.subcommand == "move":
        work_request = normalize_work_request_number(args.work_request)
        if work_request is None:
            err(f"Invalid work_request number format: '{args.work_request}'. Use the format WR-NNN, NNN, #N.", 2)
        cmd_move(work_request, args.target, force=args.force)

    elif args.subcommand == "complete":
        work_request = normalize_work_request_number(args.work_request)
        if work_request is None:
            err(f"Invalid work_request number format: '{args.work_request}'. Use the format WR-NNN, NNN, #N.", 2)
        cmd_complete(work_request)

    elif args.subcommand == "delete":
        work_request = normalize_work_request_number(args.work_request)
        if work_request is None:
            err(f"Invalid work_request number format: '{args.work_request}'. Use the format WR-NNN, NNN, #N.", 2)
        cmd_delete(work_request)

    elif args.subcommand == "update-prompt":
        work_request = normalize_work_request_number(args.work_request)
        if work_request is None:
            err(f"Invalid work_request number format: '{args.work_request}'. Use the format WR-NNN, NNN, #N.", 2)
        cmd_update_prompt(
            work_request,
            command=args.command,
            goal=args.goal,
            target=args.target,
            constraints=args.constraints,
            criteria=args.criteria,
            context=args.context,
            skip_validation=args.skip_validation,
        )

    elif args.subcommand == "update-result":
        work_request = normalize_work_request_number(args.work_request)
        if work_request is None:
            err(f"Invalid work_request number format: '{args.work_request}'. Use the format WR-NNN, NNN, #N.", 2)
        cmd_update_result(
            work_request,
            registrykey=args.registrykey,
            workdir=args.workdir,
            plan=args.plan,
            report=args.report,
            merge_commit=args.merge_commit,
        )

    elif args.subcommand == "set-editing":
        work_request = normalize_work_request_number(args.work_request)
        if work_request is None:
            err(f"Invalid work_request number format: '{args.work_request}'. Use the format WR-NNN, NNN, #N.", 2)
        cmd_set_editing(work_request, args.on)

    elif args.subcommand in ("update-title", "update"):
        work_request = normalize_work_request_number(args.work_request)
        if work_request is None:
            err(f"Invalid work_request number format: '{args.work_request}'. Use the format WR-NNN, NNN, #N.", 2)
        title = args.title or getattr(args, "title_flag", "") or ""
        if not title:
            err("You must specify a title. Example: flow-conveyor update-title WR-001 \"New title\"", 2)
        cmd_update_title(work_request, title)

    elif args.subcommand == "link":
        work_request = normalize_work_request_number(args.work_request)
        if work_request is None:
            err(f"Invalid work_request number format: '{args.work_request}'. Use the format WR-NNN, NNN, #N.", 2)
        if not args.depends_on and not args.derived_from and not args.blocks:
            err("At least one of --depends-on, --derived-from, and --blocks must be specified.", 2)
        cmd_link(
            work_request,
            depends_on=args.depends_on,
            derived_from=args.derived_from,
            blocks=args.blocks,
        )

    elif args.subcommand == "unlink":
        work_request = normalize_work_request_number(args.work_request)
        if work_request is None:
            err(f"Invalid work_request number format: '{args.work_request}'. Use the format WR-NNN, NNN, #N.", 2)
        if not args.depends_on and not args.derived_from and not args.blocks:
            err("At least one of --depends-on, --derived-from, and --blocks must be specified.", 2)
        cmd_unlink(
            work_request,
            depends_on=args.depends_on,
            derived_from=args.derived_from,
            blocks=args.blocks,
        )

    elif args.subcommand == "board":
        cmd_board()

    elif args.subcommand == "list":
        cmd_list(status_filter=args.status)

    elif args.subcommand == "show":
        work_request = normalize_work_request_number(args.work_request)
        if work_request is None:
            err(f"Invalid work_request number format: '{args.work_request}'. Use the format WR-NNN, NNN, #N.", 2)
        cmd_show(work_request)

    else:
        err(f"Unknown subcommand: '{args.subcommand}'", 2)
