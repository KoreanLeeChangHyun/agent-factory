"""Compatibility helpers for legacy kanban done sub-branches."""

from __future__ import annotations

import os
import re
import subprocess
import sys

from engine.apps.board_api.kanban_done_re import (
    _DONE_MERGE_OK_RE,
    _classify_done_failure,
)


def handle_kanban_done_force(handler, ticket: str, force_dirty: bool, project_root: str, flow_kanban: str) -> None:
    open_xml = os.path.join(project_root, ".agent-factory", "tickets", "open", f"{ticket}.xml")
    if not os.path.isfile(open_xml):
        handler._send_error(400, f"{ticket} is not in Open column (force done requires Open status)")
        return

    wt_path: str | None = None
    try:
        engine_dir = os.path.join(project_root, ".agent-factory", "engine")
        if engine_dir not in sys.path:
            sys.path.insert(0, engine_dir)
        from flow import worktree_manager  # noqa: WPS433

        wt_path = worktree_manager.get_worktree_path(ticket, repo_path=project_root)
        if wt_path and worktree_manager.has_uncommitted_changes(wt_path) and not force_dirty:
            handler._send_json_with_status(409, {
                "ok": False,
                "error_kind": "dirty_worktree",
                "conflicts": [],
                "dirty_files": handler._get_dirty_files(wt_path),
                "message": (
                    f"There are uncommitted changes in the {ticket} worktree."
                    "Retry with force_dirty=true or cancel."
                ),
                "ticket": ticket,
            })
            return
    except ImportError:
        wt_path = None

    try:
        result = subprocess.run(
            [flow_kanban, "move", ticket, "done", "--force"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        handler._send_error(504, "flow-kanban move timed out (30s)")
        return
    except FileNotFoundError:
        handler._send_error(500, f"flow-kanban not found: {flow_kanban}")
        return

    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        handler._send_json_with_status(409, {
            "ok": False,
            "error_kind": "other",
            "conflicts": [],
            "dirty_files": [],
            "message": stderr or "flow-kanban move done --force failed",
            "ticket": ticket,
        })
        return

    worktree_removed = False
    if wt_path:
        try:
            engine_dir = os.path.join(project_root, ".agent-factory", "engine")
            if engine_dir not in sys.path:
                sys.path.insert(0, engine_dir)
            from flow import worktree_manager as _wm  # noqa: WPS433

            worktree_removed = _wm.remove_worktree(ticket, delete_branch=True, repo_path=project_root)
        except ImportError:
            pass

    handler._send_json({
        "ok": True,
        "ticket": ticket,
        "force": True,
        "worktree_removed": worktree_removed,
        "stdout": (result.stdout or "").strip(),
    })


def handle_kanban_done_review(handler, ticket: str, project_root: str, flow_kanban: str) -> None:
    review_xml = os.path.join(project_root, ".agent-factory", "tickets", "review", f"{ticket}.xml")
    if not os.path.isfile(review_xml):
        handler._send_error(400, f"{ticket} is not in Review column (current state check failed)")
        return

    try:
        result = subprocess.run(
            [flow_kanban, "done", ticket],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        handler._send_error(504, "flow-kanban done timed out (120s)")
        return
    except FileNotFoundError:
        handler._send_error(500, f"flow-kanban not found: {flow_kanban}")
        return

    stdout = result.stdout or ""
    if result.returncode == 0:
        merge_commit = ""
        merged_branch = ""
        for line in stdout.splitlines():
            match = _DONE_MERGE_OK_RE.search(line)
            if match:
                merged_branch = match.group(1).strip()
                merge_commit = match.group(2).strip()
                break

        if not merge_commit:
            done_transition_re = re.compile(rf"^{re.escape(ticket)}:\s+\S+\s+→\s+Done\b")
            if any(done_transition_re.match(line) for line in stdout.splitlines()):
                handler._send_json({
                    "ok": True,
                    "ticket": ticket,
                    "merge_commit": "",
                    "merged_branch": "",
                    "merge_skipped": True,
                    "stdout": stdout.strip(),
                })
                return

            failure = _classify_done_failure(stdout, result.stderr or "")
            if failure["error_kind"] == "merge_conflict":
                handler._send_json_with_status(409, {
                    "ok": False,
                    "error_kind": "merge_conflict",
                    "conflicts": failure["conflicts"],
                    "dirty_files": failure["dirty_files"],
                    "message": failure["message"],
                    "ticket": ticket,
                })
            else:
                handler._send_json_with_status(409, {
                    "ok": False,
                    "error_kind": "other",
                    "conflicts": [],
                    "dirty_files": [],
                    "message": "merge_commit missing — backend response format error",
                    "ticket": ticket,
                })
            return

        handler._send_json({
            "ok": True,
            "ticket": ticket,
            "merge_commit": merge_commit,
            "merged_branch": merged_branch,
            "stdout": stdout.strip(),
        })
        return

    failure = _classify_done_failure(stdout, result.stderr or "")
    handler._send_json_with_status(409, {
        "ok": False,
        "error_kind": failure["error_kind"],
        "conflicts": failure["conflicts"],
        "dirty_files": failure["dirty_files"],
        "message": failure["message"],
        "ticket": ticket,
    })


def check_derived_blocked(ticket: str, kanban_base: str, kanban_all_dirs: tuple) -> list[str]:
    import xml.etree.ElementTree as ET

    not_done: list[str] = []
    for dir_name in kanban_all_dirs:
        dir_path = os.path.join(kanban_base, dir_name)
        if not os.path.isdir(dir_path):
            continue
        try:
            entries = [entry for entry in os.scandir(dir_path) if entry.is_file() and entry.name.endswith(".xml")]
        except OSError:
            continue
        for entry in entries:
            try:
                tree = ET.parse(entry.path)
                for rel in tree.findall(".//relations/relation"):
                    if rel.get("type") != "derived-from" or rel.get("ticket") != ticket:
                        continue
                    num_el = tree.find(".//metadata/number")
                    status_el = tree.find(".//metadata/status")
                    num = (num_el.text or "").strip() if num_el is not None else ""
                    status = (status_el.text or "").strip() if status_el is not None else ""
                    if status != "Done" and num:
                        not_done.append(f"{num}({status or '?'})")
            except Exception:
                continue
    return not_done


__all__ = [
    "handle_kanban_done_force",
    "handle_kanban_done_review",
    "check_derived_blocked",
]
