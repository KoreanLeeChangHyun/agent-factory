"""test conveyor complete handler.py -  handle conveyor complete (T-907) unit test.

Payment Terms:
  T6:  classify complete failure — stdout failed to merge '[WARN] worktree: merge conflict: ...'
      error kind='merge conflict' + reflect the conflict filename in the conflicts list

conveyor complete re.py (T-499) is compatibility export of Board API app boundaries
classify complete failure
"""

from __future__ import annotations

import unittest


def _load_classify_complete_failure():
    """classify complete failure"""
    from engine.apps.board_api.conveyor_complete_re import _classify_complete_failure

    return _classify_complete_failure


# Extracts the function at the time of the module load (anti-reacting for testing methods)
_classify_complete_failure = _load_classify_complete_failure()


# ──────────────────────────────────────────────


class TestClassifyCompleteHandlesEmptyHashWithWarnConflict(unittest.TestCase):
    """stdout to '[WARN] worktree merge failed: merge conflict occurred: <file>
    error kind='merge conflict' + conflicts
    """

    def test_classify_complete_handles_warn_conflict_pattern(self) -> None:
        """[WARN] conflict pattern → error kind='merge conflict' + conflicts included."""
        stdout = (
            "[WARN] worktree merge failed: merging conflict occur: generic.py\\n"
            "  - generic.py\n"
        )
        result = _classify_complete_failure(stdout, "")

        self.assertEqual(result["error_kind"], "merge_conflict")
        self.assertIn("generic.py", result["conflicts"])

    def test_classify_complete_empty_stdout_is_other(self) -> None:
        """return error kind='other' if stdout is empty string."""
        result = _classify_complete_failure("", "")

        self.assertEqual(result["error_kind"], "other")
        self.assertEqual(result["conflicts"], [])

    def test_classify_complete_error_header_is_merge_conflict(self) -> None:
        """return the error kind='merge conflict' if the '[ERROR]' header line."""
        stdout = (
            "[ERROR] T-907 merging collision. Complete Blocks All. \\n"
            "Crash file:\\n"
            "    - work.py\n"
        )
        result = _classify_complete_failure(stdout, "")

        self.assertEqual(result["error_kind"], "merge_conflict")
        self.assertIn("work.py", result["conflicts"])

    def test_classify_complete_dirty_worktree_pattern(self) -> None:
        """list of mitigation files → error kind='dirty worktree' + dirty files included."""
        stdout = (
            "[ERROR] It is a work tree that changes the MIT. Complete Blocks All. \\n"
            "Micommit File List:\\n"
            "    - dirty.py\n"
        )
        result = _classify_complete_failure(stdout, "")

        self.assertEqual(result["error_kind"], "dirty_worktree")
        self.assertIn("dirty.py", result["dirty_files"])

    def test_classify_complete_uses_stderr_as_message_fallback(self) -> None:
        """if stdout is empty, use stderr to message."""
        result = _classify_complete_failure("", "fatal: merge failed")

        self.assertEqual(result["message"], "fatal: merge failed")


if __name__ == "__main__":
    unittest.main()
