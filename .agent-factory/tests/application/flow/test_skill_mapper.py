#!/usr/bin/env python3
"""Regression tests for skill_mapper.parse_plan_tasks().

Tests 4 input format variants and the T-378 smoke regression scenario.

Test cases:
  (a) test_parse_table_w_prefix       — P0: table with W-prefix IDs
  (b) test_parse_heading_w_prefix     — P2: ### W01: heading
  (c) test_parse_heading_task_xy      — P3: ### Task 1.1: heading (auto-numbered W01)
  (d) test_parse_heading_t_prefix_normalized — P4: ### T1: heading -> W01 normalization
  (e) test_t378_smoke_regression
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest

# Ensure the engine package is importable when the file is run directly.
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_AGENT_FACTORY_ROOT = os.path.normpath(os.path.join(_TEST_DIR, "..", "..", ".."))
_ENGINE_DIR = os.path.join(_AGENT_FACTORY_ROOT, "engine")
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from flow.skill_mapper import parse_plan_tasks  # noqa: E402


def _write_tmp(content: str) -> str:
    """Write content to a NamedTemporaryFile and return the file path."""
    tf = tempfile.NamedTemporaryFile(
        suffix=".md", mode="w", encoding="utf-8", delete=False
    )
    tf.write(content)
    tf.close()
    return tf.name


class TestParsePlanTasks(unittest.TestCase):
    """Regression tests for parse_plan_tasks() covering P0/P2/P3/P4 fallback paths."""

    def setUp(self):
        self._tmp_files: list[str] = []

    def tearDown(self):
        for path in self._tmp_files:
            try:
                os.unlink(path)
            except OSError:
                pass

    def _tmp(self, content: str) -> str:
        path = _write_tmp(content)
        self._tmp_files.append(path)
        return path

    # ── (a) P0: Markdown table with W-prefix task IDs ────────────────────────

    def test_parse_table_w_prefix(self):
        """P0: table `| W01 | ... |` should be parsed directly."""
        content = """\
## Task List

| ID | Work | Skills |
|----|------|------|
| W01 | Paseo P4 Poly bag added | convention-python |
| W02 | Document-markdown |
"""
        path = self._tmp(content)
        tasks, p4_triggered = parse_plan_tasks(path)

        self.assertFalse(p4_triggered, "P0 path must not set p4_triggered")
        self.assertEqual(len(tasks), 2)

        self.assertEqual(tasks[0]["taskId"], "W01")
        self.assertEqual(tasks[0]["description"], "Add P4 Poly bag")
        self.assertIn("convention-python", tasks[0]["skills"])

        self.assertEqual(tasks[1]["taskId"], "W02")
        self.assertEqual(tasks[1]["description"], "Skip to content")
        self.assertIn("document-markdown", tasks[1]["skills"])

    # ── (b) P2: ### W01: heading fallback ────────────────────────────────────

    def test_parse_heading_w_prefix(self):
        """P2: ### W01: heading (no table) should be parsed via heading fallback."""
        content = """\
## Task List

################################################################################################################################################################################################################################################################

### W02: Fix Guide
"""
        path = self._tmp(content)
        tasks, p4_triggered = parse_plan_tasks(path)

        self.assertFalse(p4_triggered, "P2 path must not set p4_triggered")
        self.assertEqual(len(tasks), 2)

        self.assertEqual(tasks[0]["taskId"], "W01")
        self.assertEqual(tasks[0]["description"], "Add P4 Poly bag")
        self.assertEqual(tasks[0]["skills"], [])

        self.assertEqual(tasks[1]["taskId"], "W02")
        self.assertEqual(tasks[1]["description"], "Skip to content")
        self.assertEqual(tasks[1]["skills"], [])

    # ── (c) P3: ### Task X.Y heading fallback ────────────────────────────────

    def test_parse_heading_task_xy(self):
        """P3: ### Task 1.1: heading should auto-number as W01."""
        content = """\
## Task List

### Task 1.1: Add P4 Poly Bag

## Task 1.2: Fix Guide
"""
        path = self._tmp(content)
        tasks, p4_triggered = parse_plan_tasks(path)

        self.assertFalse(p4_triggered, "P3 path must not set p4_triggered")
        self.assertEqual(len(tasks), 2)

        self.assertEqual(tasks[0]["taskId"], "W01")
        self.assertEqual(tasks[0]["description"], "Add P4 Poly bag")
        self.assertEqual(tasks[0]["skills"], [])

        self.assertEqual(tasks[1]["taskId"], "W02")
        self.assertEqual(tasks[1]["description"], "Skip to content")
        self.assertEqual(tasks[1]["skills"], [])

    # ── (d) P4: ### T# heading normalization ─────────────────────────────────

    def test_parse_heading_t_prefix_normalized(self):
        """P4: ### T1: heading must be normalized to W01 and set p4_triggered."""
        content = """\
## Task List

### T1: Add P4 Poly Bag

## T2: Fix Guide
"""
        path = self._tmp(content)
        # Capture stderr to verify WARN log is emitted
        captured = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured
        try:
            tasks, p4_triggered = parse_plan_tasks(path)
        finally:
            sys.stderr = old_stderr

        stderr_output = captured.getvalue()

        self.assertTrue(p4_triggered, "P4 path must set p4_triggered=True")
        self.assertEqual(len(tasks), 2)

        self.assertEqual(tasks[0]["taskId"], "W01")
        self.assertEqual(tasks[0]["description"], "Add P4 Poly bag")
        self.assertEqual(tasks[0]["skills"], [])

        self.assertEqual(tasks[1]["taskId"], "W02")
        self.assertEqual(tasks[1]["description"], "Skip to content")
        self.assertEqual(tasks[1]["skills"], [])

        # WARN log must appear in stderr
        self.assertIn("WARN", stderr_output)
        self.assertIn("T#", stderr_output)


    def test_t378_smoke_regression(self):
        """T-378: five-task plan.md using ### T1~T5 headings must parse to W01~W05.

        Regression: parse_plan_tasks() previously returned [] for this format,
        producing an empty skill-map.md.
        """
        content = """\

## Task List

### T1: First Work

First task body

### T2: Second Work

The second job body

### T3: Third Operation

The third task body

## T4: The Fourth Job

The third task body

### T5: The fifth work

The fifth task body
"""
        path = self._tmp(content)
        captured = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured
        try:
            tasks, p4_triggered = parse_plan_tasks(path)
        finally:
            sys.stderr = old_stderr

        # Must parse all 5 tasks (regression: previously returned [])
        self.assertEqual(len(tasks), 5, "T-378 regression: expected 5 tasks")

        # All taskIds must be W01~W05 (zero-padded)
        expected_ids = [f"W{i:02d}" for i in range(1, 6)]
        actual_ids = [t["taskId"] for t in tasks]
        self.assertEqual(actual_ids, expected_ids)

        # All skills must be empty list (no skills column in T# format)
        for task in tasks:
            self.assertEqual(task["skills"], [])

        # p4_triggered must be True
        self.assertTrue(p4_triggered)


if __name__ == "__main__":
    unittest.main(verbosity=2)
