"""test_worker_return_parser.py - 워커 반환 파싱 + advisory emit 단위 테스트 (W06).

4개 시나리오를 통해 parse_worker_return 과 emit_commit_advisory 를 검증한다:

  TC1: 정상 2줄 ("상태: 성공\n커밋: abc1234") → (성공, abc1234)
  TC2: 1줄 레거시 (커밋 라인 없음) → (성공, None)
  TC3: "커밋: 없음" → advisory WARN emit 발화 검증 (flow-update / kanban / state_machine 0건)
  TC4: 잘못된 형식 → (None, None)

T-425 권고3안 제약:
  - 자동 강제 전이 / kanban move / status FAILED 강제 전이 0건 (mock 검증)
  - advisory emit은 비차단 — 기존 finalization 흐름에 영향 0
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# sys.path: .claude-organic/engine 을 포함시켜 flow 패키지 import 가능하게 한다
_ENGINE_DIR = str(Path(__file__).resolve().parent.parent.parent)
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from flow.worker_return_parser import emit_commit_advisory, parse_worker_return


class TestParseWorkerReturn(unittest.TestCase):
    """parse_worker_return 파싱 로직 검증."""

    def test_tc1_normal_two_line_success(self) -> None:
        """TC1: 정상 2줄 형식 — 상태 성공 + 유효 커밋 SHA."""
        stdout = "상태: 성공\n커밋: abc1234"
        status, commit = parse_worker_return(stdout)
        self.assertEqual(status, "성공", "상태 파싱이 '성공'이어야 한다")
        self.assertEqual(commit, "abc1234", "커밋 SHA가 'abc1234'이어야 한다")

    def test_tc2_legacy_one_line_no_commit(self) -> None:
        """TC2: 1줄 레거시 형식 — 커밋 라인 없음 → commit=None."""
        stdout = "상태: 성공"
        status, commit = parse_worker_return(stdout)
        self.assertEqual(status, "성공", "상태 파싱이 '성공'이어야 한다")
        self.assertIsNone(commit, "커밋 라인 없으면 None이어야 한다")

    def test_tc3_commit_없음_two_line(self) -> None:
        """TC3: '커밋: 없음' — advisory 분기 발화 대상."""
        stdout = "상태: 성공\n커밋: 없음"
        status, commit = parse_worker_return(stdout)
        self.assertEqual(status, "성공")
        self.assertEqual(commit, "없음", "커밋 값이 '없음'이어야 한다")

    def test_tc4_invalid_format_returns_none_none(self) -> None:
        """TC4: 잘못된 형식 — (None, None) 반환."""
        stdout = "error: something went wrong"
        status, commit = parse_worker_return(stdout)
        self.assertIsNone(status, "잘못된 형식은 status=None이어야 한다")
        self.assertIsNone(commit, "잘못된 형식은 commit=None이어야 한다")

    def test_empty_stdout_returns_none_none(self) -> None:
        """빈 stdout → (None, None)."""
        self.assertEqual(parse_worker_return(""), (None, None))
        self.assertEqual(parse_worker_return("   "), (None, None))

    def test_partial_success_two_line(self) -> None:
        """부분성공 + 유효 SHA 40자 형식 파싱."""
        sha40 = "a" * 40
        stdout = f"상태: 부분성공\n커밋: {sha40}"
        status, commit = parse_worker_return(stdout)
        self.assertEqual(status, "부분성공")
        self.assertEqual(commit, sha40)

    def test_failed_status(self) -> None:
        """실패 상태 파싱."""
        stdout = "상태: 실패\n커밋: 없음"
        status, commit = parse_worker_return(stdout)
        self.assertEqual(status, "실패")
        self.assertEqual(commit, "없음")


class TestEmitCommitAdvisory(unittest.TestCase):
    """emit_commit_advisory 동작 + 강제 정책 0건 검증."""

    def test_tc3_없음_emits_warn_log(self) -> None:
        """TC3: commit='없음' → append_log WARN 호출 1회, 강제 전이 0건."""
        with patch("flow.worker_return_parser.append_log") as mock_log:
            emit_commit_advisory(
                registry_key="20260508-161710",
                abs_work_dir="/tmp/fake_workdir",
                status="성공",
                commit="없음",
            )
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            # (abs_work_dir, level, message) 순서
            self.assertEqual(call_args[0][1], "WARN", "레벨이 WARN이어야 한다")
            self.assertIn("[ADVISORY]", call_args[0][2], "메시지에 [ADVISORY] 포함되어야 한다")
            self.assertIn("flow-merge --force", call_args[0][2], "수동 수습 경로가 메시지에 포함되어야 한다")

    def test_commit_none_emits_warn_log(self) -> None:
        """commit=None (레거시 1줄) → WARN emit."""
        with patch("flow.worker_return_parser.append_log") as mock_log:
            emit_commit_advisory(
                registry_key="20260508-161710",
                abs_work_dir="/tmp/fake_workdir",
                status="성공",
                commit=None,
            )
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            self.assertEqual(call_args[0][1], "WARN")
            self.assertIn("N/A", call_args[0][2], "commit=None 시 N/A 표시여야 한다")

    def test_valid_sha_no_emit(self) -> None:
        """유효 SHA → advisory emit 없음 (no-op)."""
        with patch("flow.worker_return_parser.append_log") as mock_log:
            emit_commit_advisory(
                registry_key="20260508-161710",
                abs_work_dir="/tmp/fake_workdir",
                status="성공",
                commit="abc1234",
            )
            mock_log.assert_not_called()

    def test_no_flow_update_kanban_state_machine_calls(self) -> None:
        """강제 정책 0건 검증: flow-update / kanban / state_machine 미호출."""
        # emit_commit_advisory 내부에서 subprocess / kanban_cli / update_state 를
        # 호출하지 않음을 import 차단으로 검증한다.
        forbidden_modules = [
            "flow.kanban_cli",
            "flow.update_state",
            "flow.state_machine",
            "subprocess",
        ]
        # 기존 import를 저장
        saved = {}
        for mod in forbidden_modules:
            saved[mod] = sys.modules.get(mod)

        with patch("flow.worker_return_parser.append_log"):
            # emit 호출 — 내부에서 forbidden_modules를 import하지 않는 한 통과
            emit_commit_advisory(
                registry_key="20260508-161710",
                abs_work_dir="/tmp/fake_workdir",
                status="성공",
                commit="없음",
            )

        # 금지 모듈이 emit_commit_advisory 실행 중 새로 import되지 않았는지 확인
        # (subprocess는 flow_logger 내부에서 사용할 수 있으므로 새로 추가된 경우만 확인)
        # 핵심 확인: kanban_cli / update_state / state_machine 은 emit 경로에 없어야 함
        for mod in ["flow.kanban_cli", "flow.update_state", "flow.state_machine"]:
            # saved[mod]가 None이었는데 emit 후 추가되면 위반
            if saved[mod] is None and sys.modules.get(mod) is not None:
                self.fail(
                    f"emit_commit_advisory가 금지 모듈 {mod}을 import했습니다 "
                    f"(강제 정책 0건 위반)"
                )


if __name__ == "__main__":
    unittest.main()
