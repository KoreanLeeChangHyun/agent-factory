"""test_kanban_done_handler.py - _handle_kanban_done 강화 (T-907) 단위 테스트.

검증 범위:
  T6: _classify_done_failure — stdout 에 '[WARN] worktree 병합 실패: 병합 충돌 발생: ...'
      포함 시 error_kind='merge_conflict' + conflicts 리스트에 충돌 파일명 반영

kanban_done_re.py (T-499) 는 Board API 앱 경계의 compatibility export 이므로
모듈 import 로 _classify_done_failure 를 추출한다.
"""

from __future__ import annotations

import unittest


def _load_classify_done_failure():
    """Board API 앱 경계의 _classify_done_failure 를 추출한다."""
    from engine.apps.board_api.kanban_done_re import _classify_done_failure

    return _classify_done_failure


# 모듈 로드 시점에 함수를 추출한다 (테스트 메서드마다 재실행 방지)
_classify_done_failure = _load_classify_done_failure()


# ─── T6: _classify_done_failure — WARN 충돌 패턴 분류 ────────────────────────


class TestClassifyDoneHandlesEmptyHashWithWarnConflict(unittest.TestCase):
    """stdout 에 '[WARN] worktree 병합 실패: 병합 충돌 발생: <파일>' 포함 시
    error_kind='merge_conflict' + conflicts 에 파일명이 반영된다.
    """

    def test_classify_done_handles_warn_conflict_pattern(self) -> None:
        """[WARN] 충돌 패턴 → error_kind='merge_conflict' + conflicts 포함."""
        stdout = (
            "[WARN] worktree 병합 실패: 병합 충돌 발생: generic.py\n"
            "  - generic.py\n"
        )
        result = _classify_done_failure(stdout, "")

        self.assertEqual(result["error_kind"], "merge_conflict")
        self.assertIn("generic.py", result["conflicts"])

    def test_classify_done_empty_stdout_is_other(self) -> None:
        """stdout 이 빈 문자열이면 error_kind='other' 를 반환한다."""
        result = _classify_done_failure("", "")

        self.assertEqual(result["error_kind"], "other")
        self.assertEqual(result["conflicts"], [])

    def test_classify_done_error_header_is_merge_conflict(self) -> None:
        """'[ERROR]' 헤더 라인이 있으면 error_kind='merge_conflict' 를 반환한다."""
        stdout = (
            "[ERROR] T-907 병합 충돌 발생. Done 전이를 차단합니다.\n"
            "  충돌 파일:\n"
            "    - work.py\n"
        )
        result = _classify_done_failure(stdout, "")

        self.assertEqual(result["error_kind"], "merge_conflict")
        self.assertIn("work.py", result["conflicts"])

    def test_classify_done_dirty_worktree_pattern(self) -> None:
        """미커밋 파일 목록 패턴 → error_kind='dirty_worktree' + dirty_files 포함."""
        stdout = (
            "[ERROR] 미커밋 변경이 있는 워크트리입니다. Done 전이를 차단합니다.\n"
            "  미커밋 파일 목록:\n"
            "    - dirty.py\n"
        )
        result = _classify_done_failure(stdout, "")

        self.assertEqual(result["error_kind"], "dirty_worktree")
        self.assertIn("dirty.py", result["dirty_files"])

    def test_classify_done_uses_stderr_as_message_fallback(self) -> None:
        """stdout 이 비어있으면 stderr 를 message 로 사용한다."""
        result = _classify_done_failure("", "fatal: merge failed")

        self.assertEqual(result["message"], "fatal: merge failed")


if __name__ == "__main__":
    unittest.main()
