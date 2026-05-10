"""T-477: /api/kanban/audit/verdict endpoint + _compute_combined_verdict helper unit tests.

Test cases:
  (a) audit-verdict.json absent         -> combined=NONE
  (b) tier2.overall=FAIL                -> combined=FAIL
  (c) tier1=null + tier2.overall=PASS   -> combined=PASS
  (d) hard_gate_failed exposed in tier2
  (e) both None                         -> combined=NONE
  (f) tier2.overall=WARN                -> combined=WARN
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

# sys.path setup
# board package is at <worktree>/.claude-organic/board
# For 'import board.server...' to work, .claude-organic must be in sys.path
_WORKTREE_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_CLAUDE_ORGANIC = os.path.normpath(os.path.join(_WORKTREE_ROOT, ".claude-organic"))
for _p in (_WORKTREE_ROOT, _CLAUDE_ORGANIC):
    if _p not in sys.path:
        sys.path.insert(0, _p)


class TestComputeCombinedVerdict(unittest.TestCase):
    def setUp(self):
        from board.server.handlers.kanban import KanbanHandlerMixin
        self.fn = KanbanHandlerMixin._compute_combined_verdict

    def test_both_none_returns_none(self):
        self.assertEqual(self.fn(None, None), "NONE")

    def test_fail_beats_pass(self):
        self.assertEqual(self.fn({"overall": "FAIL"}, {"overall": "PASS"}), "FAIL")

    def test_fail_beats_warn(self):
        self.assertEqual(self.fn({"overall": "WARN"}, {"overall": "FAIL"}), "FAIL")

    def test_warn_beats_pass(self):
        self.assertEqual(self.fn({"overall": "PASS"}, {"overall": "WARN"}), "WARN")

    def test_both_pass_returns_pass(self):
        self.assertEqual(self.fn({"overall": "PASS"}, {"overall": "PASS"}), "PASS")

    def test_tier1_none_tier2_pass_returns_pass(self):
        self.assertEqual(self.fn(None, {"overall": "PASS"}), "PASS")

    def test_tier2_none_tier1_pass_returns_pass(self):
        self.assertEqual(self.fn({"overall": "PASS"}, None), "PASS")

    def test_tier2_none_tier1_fail(self):
        self.assertEqual(self.fn({"overall": "FAIL"}, None), "FAIL")

    def test_warn_with_none(self):
        self.assertEqual(self.fn(None, {"overall": "WARN"}), "WARN")

    def test_case_insensitive(self):
        self.assertEqual(self.fn({"overall": "fail"}, None), "FAIL")
        self.assertEqual(self.fn({"overall": "warn"}, {"overall": "PASS"}), "WARN")

    def test_inconclusive_with_none_returns_none(self):
        self.assertEqual(self.fn(None, {"overall": "INCONCLUSIVE"}), "NONE")


def _make_mock_handler(path: str):
    from board.server.handlers.kanban import KanbanHandlerMixin

    class FakeHandler(KanbanHandlerMixin):
        def __init__(self):
            self.path = path
            self._sent_json = None
            self._sent_error = None

        def _send_json(self, data):
            self._sent_json = data

        def _send_error(self, code, msg):
            self._sent_error = (code, msg)

    return FakeHandler()


class TestAuditVerdictEndpoint(unittest.TestCase):
    def test_missing_ticket_param_sends_400(self):
        h = _make_mock_handler("/api/kanban/audit/verdict")
        h._handle_kanban_audit_verdict()
        self.assertIsNotNone(h._sent_error)
        self.assertEqual(h._sent_error[0], 400)

    def test_verdict_file_absent_returns_none_combined(self):
        h = _make_mock_handler("/api/kanban/audit/verdict?ticket=T-001")
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(h, "_resolve_audit_workdir", return_value=tmpdir):
                with patch("os.getcwd", return_value=tmpdir):
                    h._handle_kanban_audit_verdict()
        self.assertIsNotNone(h._sent_json)
        self.assertEqual(h._sent_json["combined"], "NONE")
        self.assertIsNone(h._sent_json["tier1"])
        self.assertIsNone(h._sent_json["tier2"])

    def test_tier2_fail_returns_fail(self):
        h = _make_mock_handler("/api/kanban/audit/verdict?ticket=T-002")
        verdict_data = {
            "tier1": None,
            "tier2": {"overall": "FAIL", "hard_gate_failed": ["AT-06", "AT-09"], "items": []},
            "combined": "FAIL",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "audit-verdict.json"), "w") as f:
                json.dump(verdict_data, f)
            with patch.object(h, "_resolve_audit_workdir", return_value=tmpdir):
                with patch("os.getcwd", return_value=tmpdir):
                    h._handle_kanban_audit_verdict()
        self.assertEqual(h._sent_json["combined"], "FAIL")

    def test_tier1_null_tier2_pass_returns_pass(self):
        h = _make_mock_handler("/api/kanban/audit/verdict?ticket=T-003")
        verdict_data = {
            "tier1": None,
            "tier2": {"overall": "PASS", "hard_gate_failed": [], "items": []},
            "combined": "PASS",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "audit-verdict.json"), "w") as f:
                json.dump(verdict_data, f)
            with patch.object(h, "_resolve_audit_workdir", return_value=tmpdir):
                with patch("os.getcwd", return_value=tmpdir):
                    h._handle_kanban_audit_verdict()
        self.assertEqual(h._sent_json["combined"], "PASS")
        self.assertIsNone(h._sent_json["tier1"])

    def test_hard_gate_failed_exposed(self):
        h = _make_mock_handler("/api/kanban/audit/verdict?ticket=T-004")
        verdict_data = {
            "tier1": None,
            "tier2": {"overall": "FAIL", "hard_gate_failed": ["AT-06", "AT-09"], "items": []},
            "combined": "FAIL",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "audit-verdict.json"), "w") as f:
                json.dump(verdict_data, f)
            with patch.object(h, "_resolve_audit_workdir", return_value=tmpdir):
                with patch("os.getcwd", return_value=tmpdir):
                    h._handle_kanban_audit_verdict()
        self.assertIn("AT-06", h._sent_json["tier2"]["hard_gate_failed"])
        self.assertIn("AT-09", h._sent_json["tier2"]["hard_gate_failed"])

    def test_workdir_not_found_returns_none(self):
        h = _make_mock_handler("/api/kanban/audit/verdict?ticket=T-005")
        with patch.object(h, "_resolve_audit_workdir", return_value=None):
            with patch("os.getcwd", return_value="/fake"):
                h._handle_kanban_audit_verdict()
        self.assertEqual(h._sent_json["combined"], "NONE")


class TestResolveAuditWorkdir(unittest.TestCase):
    def _make_handler(self):
        from board.server.handlers.kanban import KanbanHandlerMixin

        class FakeHandler(KanbanHandlerMixin):
            def _send_json(self, d): pass
            def _send_error(self, c, m): pass

        return FakeHandler()

    def test_xml_workdir_field_resolved(self):
        h = self._make_handler()
        with tempfile.TemporaryDirectory() as project_root:
            tickets_dir = os.path.join(project_root, ".claude-organic", "tickets", "review")
            os.makedirs(tickets_dir)
            runs_dir = os.path.join(project_root, ".claude-organic", "runs", "20260510-120000")
            os.makedirs(runs_dir)
            xml_content = (
                "<ticket><result>"
                "<workdir>.claude-organic/runs/20260510-120000/</workdir>"
                "</result></ticket>"
            )
            with open(os.path.join(tickets_dir, "T-010.xml"), "w") as f:
                f.write(xml_content)
            result = h._resolve_audit_workdir("T-010", project_root)
        self.assertIsNotNone(result)
        self.assertIn("20260510-120000", result)

    def test_missing_ticket_returns_none(self):
        h = self._make_handler()
        with tempfile.TemporaryDirectory() as project_root:
            result = h._resolve_audit_workdir("T-999", project_root)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
