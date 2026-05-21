"""Compatibility surface for legacy kanban board API imports.

The active implementation is ``ConveyorHandlerMixin``. This module preserves
older test/UI imports and method names while the frontend and contracts migrate.
"""

from __future__ import annotations

import os
import subprocess

from engine.apps.board_api.conveyor import ConveyorHandlerMixin, _emit_launch_event
from engine.apps.board_api.handler_common import _TICKET_RE
from engine.apps.board_api.kanban_done_helpers import (
    handle_kanban_done_force,
    handle_kanban_done_review,
)
from engine.apps.board_api.kanban_done_re import (
    _UNDO_ERROR_RE,
    _UNDO_STRATEGY_RESET,
    _UNDO_STRATEGY_REVERT,
    _UNDO_WORKTREE_RE,
)
from board.server.support.common import api_endpoint


class KanbanHandlerMixin(ConveyorHandlerMixin):
    """Legacy kanban method names backed by conveyor-era code."""

    _handle_kanban_branch_active = ConveyorHandlerMixin._handle_conveyor_branch_active
    _handle_kanban_workflow_entries = ConveyorHandlerMixin._handle_conveyor_workflow_entries
    _handle_kanban_workflow_detail = ConveyorHandlerMixin._handle_conveyor_workflow_detail
    _handle_kanban_workrequest = ConveyorHandlerMixin._handle_conveyor_workrequest
    _handle_kanban_done_verdict = ConveyorHandlerMixin._handle_conveyor_complete_verdict
    _handle_kanban_review_verdict = ConveyorHandlerMixin._handle_conveyor_verifying_verdict

    def _handle_kanban_branch_active(self) -> None:
        self._handle_conveyor_branch_active()

    def _handle_kanban_move(self) -> None:
        self._handle_conveyor_move()

    def _handle_kanban_submit(self) -> None:
        self._handle_conveyor_submit()

    def _handle_kanban_delete(self) -> None:
        self._handle_conveyor_delete()

    def _handle_kanban_branch_toggle(self) -> None:
        self._handle_conveyor_branch_toggle()

    def _resolve_audit_workdir(self, ticket: str, project_root: str) -> str | None:
        import glob as _glob
        import json as _json
        import xml.etree.ElementTree as ET

        tickets_root = os.path.join(project_root, ".agent-factory", "tickets")
        for dir_name in ("todo", "open", "progress", "review", "done"):
            xml_path = os.path.join(tickets_root, dir_name, f"{ticket}.xml")
            if not os.path.isfile(xml_path):
                continue
            try:
                root_el = ET.parse(xml_path).getroot()
                wd_el = root_el.find(".//result/workdir")
                if wd_el is not None and wd_el.text and wd_el.text.strip():
                    workdir = wd_el.text.strip()
                    if not os.path.isabs(workdir):
                        workdir = os.path.join(project_root, workdir)
                    return workdir
            except Exception:
                pass

        runs_root = os.path.join(project_root, ".agent-factory", "runs")
        if not os.path.isdir(runs_root):
            return None
        try:
            run_dirs = [
                d for d in _glob.glob(os.path.join(runs_root, "*"))
                if os.path.isdir(d) and not os.path.basename(d).startswith("_")
            ]
            run_dirs.sort(key=lambda d: os.path.getmtime(d), reverse=True)
        except Exception:
            return None

        for run_dir in run_dirs:
            status_path = os.path.join(run_dir, "status.json")
            if not os.path.isfile(status_path):
                continue
            try:
                with open(status_path, encoding="utf-8") as f:
                    status = _json.load(f)
                if status.get("ticket_number") == ticket:
                    return run_dir
            except Exception:
                pass
        return None

    @staticmethod
    def _compute_combined_verdict(tier1, tier2) -> str:
        return ConveyorHandlerMixin._compute_combined_verdict(tier1, tier2)

    @api_endpoint("K", "audit_verdict")
    def _handle_kanban_audit_verdict(self) -> None:
        from urllib.parse import parse_qs, urlparse
        import json as _json

        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        ticket = (qs.get("ticket", [None])[0] or "").strip()
        if not ticket or not _TICKET_RE.match(ticket):
            self._send_error(400, 'Missing or invalid "ticket" query param (T-NNN required)')
            return

        none_response = {"tier1": None, "tier2": None, "combined": "NONE"}
        project_root = os.getcwd()
        work_dir = self._resolve_audit_workdir(ticket, project_root)
        if not work_dir:
            self._send_json(none_response)
            return

        verdict_path = os.path.join(work_dir, "audit-verdict.json")
        if not os.path.isfile(verdict_path):
            self._send_json(none_response)
            return
        try:
            with open(verdict_path, encoding="utf-8") as f:
                data = _json.load(f)
        except Exception:
            self._send_json(none_response)
            return

        tier1 = data.get("tier1")
        tier2 = data.get("tier2")
        self._send_json({
            "ticket": ticket,
            "tier1": tier1,
            "tier2": tier2,
            "combined": self._compute_combined_verdict(tier1, tier2),
        })

    @api_endpoint("K", "done")
    def _handle_kanban_done(self) -> None:
        data = self._read_json_body() or {}
        ticket = (data.get("ticket") or "").strip()
        force = bool(data.get("force", False))
        force_dirty = bool(data.get("force_dirty", False))
        if not ticket or not _TICKET_RE.match(ticket):
            self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
            return

        project_root = os.getcwd()
        flow_kanban = os.path.join(project_root, ".agent-factory", "bin", "flow-kanban")
        if force:
            handle_kanban_done_force(self, ticket, force_dirty, project_root, flow_kanban)
        else:
            handle_kanban_done_review(self, ticket, project_root, flow_kanban)

    @api_endpoint("KANBAN", "undo_done")
    def _handle_kanban_undo_done(self) -> None:
        data = self._read_json_body() or {}
        ticket = (data.get("ticket") or "").strip()
        force = bool(data.get("force", False))
        if not ticket or not _TICKET_RE.match(ticket):
            self._send_error(400, 'Missing or invalid "ticket" (T-NNN required)')
            return

        project_root = os.getcwd()
        done_xml = os.path.join(project_root, ".agent-factory", "tickets", "done", f"{ticket}.xml")
        if not os.path.isfile(done_xml):
            self._send_error(400, f"{ticket} is not in Done column (undo-done targets Done tickets only)")
            return

        cmd_args = [os.path.join(project_root, ".agent-factory", "bin", "flow-undo-done"), ticket]
        if force:
            cmd_args.append("--force")
        try:
            result = subprocess.run(
                cmd_args,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired:
            self._send_error(504, "flow-undo-done timed out (180s)")
            return
        except FileNotFoundError:
            self._send_error(500, f"flow-undo-done not found: {cmd_args[0]}")
            return

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        strategy = ""
        worktree_path = ""
        branch = ""
        error_message = ""
        for line in stdout.replace("\\n", "\n").splitlines() + stderr.replace("\\n", "\n").splitlines():
            if not strategy and _UNDO_STRATEGY_RESET.search(line):
                strategy = "reset"
            elif not strategy and _UNDO_STRATEGY_REVERT.search(line):
                strategy = "revert"
            wt_match = _UNDO_WORKTREE_RE.search(line)
            if wt_match:
                worktree_path = wt_match.group(1).strip()
                branch = wt_match.group(2).strip()
            err_match = _UNDO_ERROR_RE.search(line)
            if err_match and not error_message:
                error_message = err_match.group(1).strip()

        if result.returncode == 0:
            kind = "reset_ok" if strategy == "reset" else "revert_ok" if strategy == "revert" else "unknown_ok"
            self._send_json({
                "ok": True,
                "kind": kind,
                "ticket": ticket,
                "strategy": strategy,
                "branch": branch,
                "worktree_path": worktree_path,
                "message": f'{ticket} rollback completed (strategy: {strategy or "?"})',
                "stdout": stdout.strip(),
            })
            return

        if not error_message:
            for line in reversed(stderr.splitlines()):
                if line.strip():
                    error_message = line.strip()
                    break
        if not error_message:
            error_message = f"flow-undo-done exited with code {result.returncode}"
        self._send_json_with_status(409, {
            "ok": False,
            "kind": "error",
            "ticket": ticket,
            "error": error_message,
            "message": error_message,
            "stdout": stdout.strip(),
            "stderr": stderr.strip(),
        })


__all__ = ["KanbanHandlerMixin", "_emit_launch_event"]
