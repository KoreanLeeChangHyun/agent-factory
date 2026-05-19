"""test_kanban_done_handler.py - _handle_kanban_done 강화 (T-907) 단위 테스트.

검증 범위:
  T6: _classify_done_failure — stdout 에 '[WARN] worktree 병합 실패: 병합 충돌 발생: ...'
      포함 시 error_kind='merge_conflict' + conflicts 리스트에 충돌 파일명 반영

_kanban_done_re.py (T-499) 는 패키지 상대 import 없는 standalone 모듈이라 파일 전체를
exec 로 격리 실행해 _classify_done_failure 를 추출한다.
"""

from __future__ import annotations

import unittest
from pathlib import Path

# _kanban_done_re.py 경로 계산: tests/ → engine/ → .claude-organic/ → board/server/handlers/
_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_KANBAN_DONE_RE_PY = (
    _WORKTREE_ROOT / ".claude-organic" / "board" / "server" / "handlers" / "_kanban_done_re.py"
)


def _load_classify_done_failure():
    """_kanban_done_re.py 의 _classify_done_failure 를 격리 추출한다.

    본 모듈은 ``re`` 만 import 하는 standalone 모듈이라 파일 전체를 exec 로
    그대로 실행해도 안전하다.
    """
    src = _KANBAN_DONE_RE_PY.read_text(encoding="utf-8")
    ns: dict = {}
    exec(src, ns)  # noqa: S102
    return ns["_classify_done_failure"]


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
