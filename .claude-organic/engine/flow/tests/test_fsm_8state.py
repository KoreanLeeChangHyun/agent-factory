"""test_fsm_8state.py - T-453 FSM 8-state extension unit tests.

4 verification axes:
  Axis 1: workflow_phase field read/write behavior
  Axis 2: VALIDATE / FAIL entry and exit (multi key transitions)
  Axis 3: light / single / full mode regression = 0
  Axis 4: INIT phase_verify outcomes via _phase_verify_init()
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# sys.path: .claude-organic/engine directory
_ENGINE_DIR = str(Path(__file__).resolve().parent.parent.parent)
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from constants import FSM_TRANSITIONS
from flow.state_machine import update_status
from flow.update_state import _read_current_step
from flow.initialization import _phase_verify_init


def _write_status_json(path: str, data: dict) -> None:
    """Write a status.json dict to the given path (atomic-safe for tests)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _make_status_dir() -> str:
    """Create a temp directory with an empty work-dir structure and return its path."""
    d = tempfile.mkdtemp(prefix="wf_test_fsm8_")
    return d


# =============================================================================
# Axis 1: workflow_phase field read/write
# =============================================================================

class TestWorkflowPhaseReadWrite(unittest.TestCase):
    """Axis 1: status.json write uses workflow_phase as single key (T-459);
    read fallback priority: workflow_phase > step > phase > 'NONE'."""

    def setUp(self) -> None:
        self.workdir = _make_status_dir()
        self.status_file = os.path.join(self.workdir, "status.json")

    def tearDown(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)

    def _write_and_transition(self, initial_phase: str, to_step: str, mode: str = "multi") -> None:
        """Helper: write status.json with given phase, then call update_status."""
        _write_status_json(self.status_file, {
            "workflow_phase": initial_phase,
            "step": initial_phase,
            "mode": mode,
            "transitions": [],
        })
        update_status(self.workdir, self.status_file, initial_phase, to_step)

    def test_write_creates_workflow_phase_key(self) -> None:
        """After update_status, status.json must have workflow_phase as single key (T-459).
        step key is no longer written by update_status (1-cycle compat removed)."""
        self._write_and_transition("PLAN", "WORK", mode="multi")
        with open(self.status_file, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("workflow_phase", data, "workflow_phase key must exist after write")
        self.assertEqual(data["workflow_phase"], "WORK")
        # T-459: step write removed. Legacy step key may remain from prior status.json
        # (read fallback still supports step for pre-T-459 files — see test_read_fallback_step_when_no_workflow_phase)

    def test_read_fallback_workflow_phase_priority(self) -> None:
        """workflow_phase takes priority over step when both present."""
        _write_status_json(self.status_file, {
            "workflow_phase": "VALIDATE",
            "step": "WORK",
        })
        result = _read_current_step(self.status_file)
        self.assertEqual(result, "VALIDATE", "workflow_phase must win over step")

    def test_read_fallback_step_when_no_workflow_phase(self) -> None:
        """step used when workflow_phase absent (1-cycle compat)."""
        _write_status_json(self.status_file, {"step": "PLAN"})
        result = _read_current_step(self.status_file)
        self.assertEqual(result, "PLAN")

    def test_read_fallback_phase_legacy(self) -> None:
        """phase used when both workflow_phase and step absent (legacy compat)."""
        _write_status_json(self.status_file, {"phase": "INIT"})
        result = _read_current_step(self.status_file)
        self.assertEqual(result, "INIT")

    def test_read_fallback_none_when_empty_dict(self) -> None:
        """Empty dict yields 'NONE'."""
        _write_status_json(self.status_file, {})
        result = _read_current_step(self.status_file)
        self.assertEqual(result, "NONE")

    def test_read_fallback_none_when_file_missing(self) -> None:
        """Missing file yields 'NONE'."""
        result = _read_current_step(os.path.join(self.workdir, "nonexistent.json"))
        self.assertEqual(result, "NONE")


# =============================================================================
# Axis 2: VALIDATE / FAIL entry and exit (multi mode)
# =============================================================================

class TestMultiModeTransitions(unittest.TestCase):
    """Axis 2: multi mode FSM transitions involving VALIDATE and FAILED."""

    def setUp(self) -> None:
        self.workdir = _make_status_dir()
        self.status_file = os.path.join(self.workdir, "status.json")

    def tearDown(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)

    def _do_transition(self, from_step: str, to_step: str, mode: str = "multi") -> str:
        _write_status_json(self.status_file, {
            "workflow_phase": from_step,
            "step": from_step,
            "mode": mode,
            "transitions": [],
        })
        return update_status(self.workdir, self.status_file, from_step, to_step)

    def test_work_to_validate(self) -> None:
        """WORK -> VALIDATE passes in multi mode."""
        result = self._do_transition("WORK", "VALIDATE")
        self.assertNotIn("blocked", result, f"WORK->VALIDATE should pass, got: {result}")
        with open(self.status_file, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["workflow_phase"], "VALIDATE")

    def test_validate_to_report(self) -> None:
        """VALIDATE -> REPORT passes in multi mode."""
        result = self._do_transition("VALIDATE", "REPORT")
        self.assertNotIn("blocked", result, f"VALIDATE->REPORT should pass, got: {result}")

    def test_validate_to_work_retry(self) -> None:
        """VALIDATE -> WORK (retry) passes in multi mode."""
        result = self._do_transition("VALIDATE", "WORK")
        self.assertNotIn("blocked", result, f"VALIDATE->WORK retry should pass, got: {result}")

    def test_work_to_failed(self) -> None:
        """WORK -> FAILED passes in multi mode (FAIL alias)."""
        result = self._do_transition("WORK", "FAILED")
        self.assertNotIn("blocked", result, f"WORK->FAILED should pass, got: {result}")

    def test_validate_to_failed(self) -> None:
        """VALIDATE -> FAILED passes in multi mode."""
        result = self._do_transition("VALIDATE", "FAILED")
        self.assertNotIn("blocked", result, f"VALIDATE->FAILED should pass, got: {result}")

    def test_light_mode_rejects_validate(self) -> None:
        """light mode must NOT allow WORK -> VALIDATE (regression guard)."""
        result = self._do_transition("WORK", "VALIDATE", mode="light")
        self.assertIn("blocked", result,
                      f"light mode WORK->VALIDATE must be blocked, got: {result}")

    def test_work_to_report_blocked_in_multi(self) -> None:
        """WORK -> REPORT direct must be blocked in multi mode (VALIDATE required)."""
        result = self._do_transition("WORK", "REPORT")
        self.assertIn("blocked", result,
                      f"WORK->REPORT direct must be blocked in multi mode, got: {result}")


# =============================================================================
# Axis 3: light / full mode regression = 0
# =============================================================================

# Snapshot of FSM_TRANSITIONS before T-453 (W02 baseline, from W02 report).
# multi key is new; full and light must remain exactly as before.
_EXPECTED_FULL = {
    "INIT": ["PLAN", "STALE", "FAILED", "CANCELLED"],
    "NONE": ["PLAN", "STALE", "FAILED", "CANCELLED"],
    "PLAN": ["WORK", "STALE", "FAILED", "CANCELLED"],
    "WORK": ["REPORT", "STALE", "FAILED", "CANCELLED"],
    "REPORT": ["DONE", "STALE", "FAILED", "CANCELLED"],
}

_EXPECTED_LIGHT = {
    "INIT": ["WORK", "STALE", "FAILED", "CANCELLED"],
    "NONE": ["WORK", "STALE", "FAILED", "CANCELLED"],
    "WORK": ["DONE", "STALE", "FAILED", "CANCELLED"],
}


class TestModeRegressionZero(unittest.TestCase):
    """Axis 3: light and full FSM tables must be unchanged by T-453."""

    def test_light_dict_unchanged(self) -> None:
        """FSM_TRANSITIONS['light'] must match pre-T-453 snapshot exactly."""
        self.assertEqual(
            FSM_TRANSITIONS["light"],
            _EXPECTED_LIGHT,
            "light mode FSM table changed — regression detected",
        )

    def test_full_dict_preserved(self) -> None:
        """FSM_TRANSITIONS['full'] must match pre-T-453 snapshot exactly."""
        self.assertEqual(
            FSM_TRANSITIONS["full"],
            _EXPECTED_FULL,
            "full mode FSM table changed — regression detected",
        )

    def test_multi_key_exists(self) -> None:
        """FSM_TRANSITIONS must have 'multi' key after T-453."""
        self.assertIn("multi", FSM_TRANSITIONS)

    def test_multi_work_does_not_include_report_direct(self) -> None:
        """multi.WORK must NOT include REPORT (VALIDATE required path)."""
        self.assertNotIn(
            "REPORT",
            FSM_TRANSITIONS["multi"].get("WORK", []),
            "REPORT must not be directly reachable from WORK in multi mode",
        )

    def test_multi_validate_includes_work_retry(self) -> None:
        """multi.VALIDATE must include WORK for retry path."""
        self.assertIn(
            "WORK",
            FSM_TRANSITIONS["multi"].get("VALIDATE", []),
        )

    def test_full_work_includes_report_direct(self) -> None:
        """full.WORK must still include REPORT directly (no VALIDATE step)."""
        self.assertIn(
            "REPORT",
            FSM_TRANSITIONS["full"].get("WORK", []),
        )


# =============================================================================
# Axis 4: _phase_verify_init outcomes
# =============================================================================

class TestPhaseVerifyInit(unittest.TestCase):
    """Axis 4: _phase_verify_init() 5 outcome cases."""

    def setUp(self) -> None:
        # temp root acting as _PROJECT_ROOT for the function
        self.project_root = tempfile.mkdtemp(prefix="wf_test_pvi_root_")
        self.registry_key = "20260509-999999"
        # abs_work_dir is the workflow run directory (contains .context.json)
        self.abs_work_dir = os.path.join(
            self.project_root, ".claude-organic", "runs", self.registry_key
        )
        os.makedirs(self.abs_work_dir, exist_ok=True)
        # create .context.json in abs_work_dir
        ctx_path = os.path.join(self.abs_work_dir, ".context.json")
        with open(ctx_path, "w", encoding="utf-8") as f:
            json.dump({"registryKey": self.registry_key}, f)
        # tickets directory for ticket XML tests
        self.tickets_dir = os.path.join(
            self.project_root, ".claude-organic", "tickets", "todo"
        )
        os.makedirs(self.tickets_dir, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.project_root, ignore_errors=True)

    def _call(self, ticket_number=None, abs_work_dir=None, registry_key=None):
        """Call _phase_verify_init with patched _PROJECT_ROOT."""
        import flow.initialization as _init_mod
        original_root = _init_mod._PROJECT_ROOT
        _init_mod._PROJECT_ROOT = self.project_root
        try:
            return _phase_verify_init(
                abs_work_dir or self.abs_work_dir,
                registry_key or self.registry_key,
                ticket_number=ticket_number,
            )
        finally:
            _init_mod._PROJECT_ROOT = original_root

    def test_all_pass_no_ticket(self) -> None:
        """All axes pass with ticket_number=None -> (True, 'ok')."""
        ok, reason = self._call(ticket_number=None)
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_context_json_missing(self) -> None:
        """Missing .context.json -> (False, '.context.json missing: ...')."""
        bad_dir = tempfile.mkdtemp(prefix="wf_test_pvi_nocontext_")
        try:
            ok, reason = self._call(abs_work_dir=bad_dir)
            self.assertFalse(ok)
            self.assertIn(".context.json missing", reason)
            self.assertIn(bad_dir, reason)
        finally:
            shutil.rmtree(bad_dir, ignore_errors=True)

    def test_runs_dir_missing(self) -> None:
        """Missing runs/<registry_key>/ -> (False, 'runs dir missing: ...')."""
        missing_key = "20260509-000001"
        ok, reason = self._call(registry_key=missing_key)
        self.assertFalse(ok)
        self.assertIn("runs dir missing", reason)
        self.assertIn(missing_key, reason)

    def test_ticket_number_none_skips_axis3(self) -> None:
        """ticket_number=None skips axis 3 and returns (True, 'ok')."""
        # Even if tickets dir is empty, should pass when ticket_number is None
        ok, reason = self._call(ticket_number=None)
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_ticket_xml_parse_error(self) -> None:
        """Broken ticket XML -> (False, 'ticket XML parse error: ...')."""
        ticket_path = os.path.join(self.tickets_dir, "T-999.xml")
        with open(ticket_path, "w", encoding="utf-8") as f:
            f.write("<broken><unclosed>")
        ok, reason = self._call(ticket_number="T-999")
        self.assertFalse(ok)
        self.assertIn("ticket XML parse error", reason)

    def test_ticket_xml_not_found(self) -> None:
        """Ticket XML not found -> (False, 'ticket XML not found for ...')."""
        ok, reason = self._call(ticket_number="T-888")
        self.assertFalse(ok)
        self.assertIn("ticket XML not found for", reason)
        self.assertIn("T-888", reason)

    def test_all_pass_with_valid_ticket(self) -> None:
        """Valid ticket XML + all dirs present -> (True, 'ok')."""
        ticket_path = os.path.join(self.tickets_dir, "T-777.xml")
        with open(ticket_path, "w", encoding="utf-8") as f:
            f.write("<ticket><number>T-777</number></ticket>")
        ok, reason = self._call(ticket_number="T-777")
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")


if __name__ == "__main__":
    unittest.main()
