"""test_worker_return_parser.py - Worker return parsing + advisory emit unit test (W06/W03).

[W06] Verify parse_worker_return and emit_commit_advisory through four scenarios:

  TC1: OK 2 lines ("Status: Success \n Commit: abc1234") → (Success, abc1234)
  TC2: 1-line legacy (no commit line) → (success, None)
  TC3: "Commit: None" → advisory WARN emit ignition verification (flow-update / kanban / state_machine 0 cases)
  TC4: Invalid format → (None, None)

[W03 T-447] Verify emit_report_advisory through four scenarios:

  RA1: report.md exists → no-op (0 WARN logs, 0 metrics events)
  RA2: Absence of report.md → 1 WARN + 1 report.missing metrics event
  RA3: abs_work_dir is None → safety fallback (processed without exception)
  RA4: metrics module None / import failure → log emit only, function terminates normally

Limitations of T-425 Recommendation 3:
  - Automatic forced transfer / kanban move / status FAILED forced transfer 0 cases (mock verification)
  - Advisory emit is non-blocking — has 0 impact on existing finalization flow
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# sys.path: Enable flow package import by including .agent-factory/engine
_ENGINE_DIR = str(Path(__file__).resolve().parents[3] / "engine")
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from flow.worker_return_parser import (
    emit_commit_advisory,
    emit_report_advisory,
    parse_worker_return,
)


class TestParseWorkerReturn(unittest.TestCase):
    """parse_worker_return Verification of parsing logic."""

    def test_tc1_normal_two_line_success(self) -> None:
        """TC1: Normal 2-line format — status success + valid commit SHA."""
        stdout = "Status: Success \n Commit: abc1234"
        status, commit = parse_worker_return(stdout)
        self.assertEqual(status, "success", "Status parsing should be 'success'")
        self.assertEqual(commit, "abc1234", "Commit SHA must be 'abc1234'")

    def test_tc2_legacy_one_line_no_commit(self) -> None:
        """TC2: 1-line legacy format — no commit line → commit=None."""
        stdout = "Status: Success"
        status, commit = parse_worker_return(stdout)
        self.assertEqual(status, "success", "Status parsing should be 'success'")
        self.assertIsNone(commit, "If there is no commit line, it should be None")

    def test_tc3_commit_없음_two_line(self) -> None:
        """TC3: 'Commit: None' — Advisory branch fire target."""
        stdout = "Status: Success \n Commit: None"
        status, commit = parse_worker_return(stdout)
        self.assertEqual(status, "success")
        self.assertEqual(commit, "doesn't exist", "Commit value must be 'None'")

    def test_tc4_invalid_format_returns_none_none(self) -> None:
        """TC4: Bad format — returning (None, None)."""
        stdout = "error: something went wrong"
        status, commit = parse_worker_return(stdout)
        self.assertIsNone(status, "Invalid format should be status=None")
        self.assertIsNone(commit, "Invalid format should be commit=None")

    def test_empty_stdout_returns_none_none(self) -> None:
        """Empty stdout → (None, None)."""
        self.assertEqual(parse_worker_return(""), (None, None))
        self.assertEqual(parse_worker_return("   "), (None, None))

    def test_partial_success_two_line(self) -> None:
        """Partial success + parsing valid SHA 40 character format."""
        sha40 = "a" * 40
        stdout = f"Status: Partial Success \n Commit: {sha40}"
        status, commit = parse_worker_return(stdout)
        self.assertEqual(status, "Partial success")
        self.assertEqual(commit, sha40)

    def test_failed_status(self) -> None:
        """Parsing failure status."""
        stdout = "Status: Failed \n Commit: None"
        status, commit = parse_worker_return(stdout)
        self.assertEqual(status, "failure")
        self.assertEqual(commit, "doesn't exist")


class TestEmitCommitAdvisory(unittest.TestCase):
    """emit_commit_advisory action + 0 enforced policy verifications."""

    def test_tc3_없음_emits_warn_log(self) -> None:
        """TC3: commit='none' → 1 append_log WARN call, 0 forced transitions."""
        with patch("flow.worker_return_parser.append_log") as mock_log:
            emit_commit_advisory(
                registry_key="20260508-161710",
                abs_work_dir="/tmp/fake_workdir",
                status="success",
                commit="doesn't exist",
            )
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            # (abs_work_dir, level, message) order
            self.assertEqual(call_args[0][1], "WARN", "The level must be WARN")
            self.assertIn("[ADVISORY]", call_args[0][2], "[ADVISORY] must be included in the message")
            self.assertIn("flow-merge --force", call_args[0][2], "A manual recovery path should be included in the message.")

    def test_commit_none_emits_warn_log(self) -> None:
        """commit=None (legacy 1 line) → WARN emit."""
        with patch("flow.worker_return_parser.append_log") as mock_log:
            emit_commit_advisory(
                registry_key="20260508-161710",
                abs_work_dir="/tmp/fake_workdir",
                status="success",
                commit=None,
            )
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            self.assertEqual(call_args[0][1], "WARN")
            self.assertIn("N/A", call_args[0][2], "When commit=None, it should display N/A")

    def test_valid_sha_no_emit(self) -> None:
        """Valid SHA → No advisory emit (no-op)."""
        with patch("flow.worker_return_parser.append_log") as mock_log:
            emit_commit_advisory(
                registry_key="20260508-161710",
                abs_work_dir="/tmp/fake_workdir",
                status="success",
                commit="abc1234",
            )
            mock_log.assert_not_called()

    def test_no_flow_update_kanban_state_machine_calls(self) -> None:
        """0 enforced policies verified: flow-update / kanban / state_machine not called."""
        # Inside emit_commit_advisory, subprocess / kanban_cli / update_state
        # Verify that it is not called by blocking import.
        forbidden_modules = [
            "flow.kanban_cli",
            "flow.update_state",
            "flow.state_machine",
            "subprocess",
        ]
        # Save existing import
        saved = {}
        for mod in forbidden_modules:
            saved[mod] = sys.modules.get(mod)

        with patch("flow.worker_return_parser.append_log"):
            # emit call — passes unless you import forbidden_modules inside
            emit_commit_advisory(
                registry_key="20260508-161710",
                abs_work_dir="/tmp/fake_workdir",
                status="success",
                commit="doesn't exist",
            )

        # Ensure that prohibited modules are not newly imported during emit_commit_advisory execution
        # (subprocess can be used inside flow_logger, so only check if it is newly added)
        # Key check: kanban_cli / update_state / state_machine should not be in emit path
        for mod in ["flow.kanban_cli", "flow.update_state", "flow.state_machine"]:
            # If saved[mod] was None and added after emit, it is a violation.
            if saved[mod] is None and sys.modules.get(mod) is not None:
                self.fail(
                    f"emit_commit_advisory imported prohibit module {mod}"
                    f"(0 enforced policy violations)"
                )


class TestEmitReportAdvisory(unittest.TestCase):
    """Verification of emit_report_advisory operation (T-447 W03).

    Advisory only Canon:
      - Forced transition / auto regression / kanban move 0 cases
      - Only emit WARN log + metrics events
      - Non-blocking exceptions (normal termination of function in all cases)
    """

    def test_ra1_report_exists_noop(self) -> None:
        """RA1: report.md exists → no-op (0 WARN logs, 0 metrics events)."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = os.path.join(tmpdir, "report.md")
            # Create report.md file in advance
            with open(report_path, "w") as f:
                f.write("# Report\n")

            with patch("flow.worker_return_parser.append_log") as mock_log:
                with patch("engine.core.metrics.append_event") as mock_metrics:
                    emit_report_advisory(
                        registry_key="20260508-225113",
                        abs_work_dir=tmpdir,
                        report_path=report_path,
                    )
                    mock_log.assert_not_called()
                    mock_metrics.assert_not_called()

    def test_ra2_report_missing_emits_warn_and_metrics(self) -> None:
        """RA2: Absence of report.md → 1 WARN + 1 report.missing metrics event."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = os.path.join(tmpdir, "report.md")
            # The report.md file is not created.

            with patch("flow.worker_return_parser.append_log") as mock_log:
                with patch("flow.worker_return_parser.append_log"):
                    pass  # reset

            with patch("flow.worker_return_parser.append_log") as mock_log:
                # To patch metrics.append_event also inside dynamic import:
                # Mock injection of engine.core.metrics module into sys.modules
                mock_metrics_module = MagicMock()
                mock_append_event = MagicMock()
                mock_metrics_module.append_event = mock_append_event

                with patch.dict("sys.modules", {"engine.core.metrics": mock_metrics_module}):
                    emit_report_advisory(
                        registry_key="20260508-225113",
                        abs_work_dir=tmpdir,
                        report_path=report_path,
                    )

                # Verification of 1 WARN log
                mock_log.assert_called_once()
                call_args = mock_log.call_args
                self.assertEqual(call_args[0][1], "WARN", "The level must be WARN")
                self.assertIn("[ADVISORY]", call_args[0][2], "[ADVISORY] Includes prefix")
                self.assertIn("report.md", call_args[0][2], "Mention report.md path")
                self.assertIn(
                    "work/ integration in main session", call_args[0][2], "User manual training path guidance"
                )
                # Verification of 1 metrics event
                mock_append_event.assert_called_once()
                metrics_call = mock_append_event.call_args
                self.assertEqual(
                    metrics_call[0][1],
                    "report.missing",
                    "Event type must be report.missing",
                )
                payload = metrics_call[0][2]
                self.assertIn("report_path", payload, "Include report_path in payload")
                self.assertIn("signal_summary", payload, "Include signal_summary in payload")
                self.assertEqual(payload["report_path"], report_path)

    def test_ra3_abs_work_dir_none_no_exception(self) -> None:
        """RA3: abs_work_dir is None → safe fallback (handled without exception)."""
        import os

        # report_path is also set to a path that does not exist.
        report_path = "/nonexistent/path/report.md"

        # Mock to internally absorb exceptions even if append_log receives None abs_work_dir
        with patch("flow.worker_return_parser.append_log") as mock_log:
            # No exceptions should occur
            try:
                emit_report_advisory(
                    registry_key="20260508-225113",
                    abs_work_dir=None,  # type: ignore[arg-type]
                    report_path=report_path,
                )
            except Exception as exc:
                self.fail(
                    f"emit_report_advisory must not raise an exception when abs_work_dir=None: {exc}"
                )

    def test_ra4_metrics_import_failure_log_still_emits(self) -> None:
        """RA4: Metrics module import failure → Only log emit, function terminates normally."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = os.path.join(tmpdir, "report.md")
            # no report.md

            with patch("flow.worker_return_parser.append_log") as mock_log:
                # Remove engine.core.metrics from sys.modules to make import fail
                import sys
                saved = sys.modules.pop("engine.core.metrics", None)
                try:
                    # Force engine.core.metrics to ImportError
                    sys.modules["engine.core.metrics"] = None  # type: ignore[assignment]
                    emit_report_advisory(
                        registry_key="20260508-225113",
                        abs_work_dir=tmpdir,
                        report_path=report_path,
                    )
                finally:
                    # restore
                    if saved is not None:
                        sys.modules["engine.core.metrics"] = saved
                    else:
                        sys.modules.pop("engine.core.metrics", None)

                # WARN logs must be emitted
                mock_log.assert_called_once()
                call_args = mock_log.call_args
                self.assertEqual(call_args[0][1], "WARN")
                self.assertIn("[ADVISORY]", call_args[0][2])


if __name__ == "__main__":
    unittest.main()
