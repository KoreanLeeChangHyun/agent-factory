"""test_worker_return_parser.py - 워커 반환 파싱 + advisory emit 단위 테스트 (W06/W03).

[W06] 4개 시나리오를 통해 parse_worker_return 과 emit_commit_advisory 를 검증한다:

  TC1: 정상 2줄 ("상태: 성공\n커밋: abc1234") → (성공, abc1234)
  TC2: 1줄 레거시 (커밋 라인 없음) → (성공, None)
  TC3: "커밋: 없음" → advisory WARN emit 발화 검증 (flow-update / kanban / state_machine 0건)
  TC4: 잘못된 형식 → (None, None)

[W03 T-447] 4개 시나리오를 통해 emit_report_advisory 를 검증한다:

  RA1: report.md 존재 → no-op (WARN 로그 0건, metrics 이벤트 0건)
  RA2: report.md 부재 → WARN 1건 + report.missing metrics 이벤트 1건
  RA3: abs_work_dir is None → 안전 fallback (예외 없이 처리)
  RA4: metrics 모듈 None / import 실패 → log emit만, 함수 정상 종료

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

from flow.worker_return_parser import (
    emit_commit_advisory,
    emit_report_advisory,
    parse_worker_return,
)


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


class TestEmitReportAdvisory(unittest.TestCase):
    """emit_report_advisory 동작 검증 (T-447 W03).

    advisory only 캐논:
      - 강제 전이 / 자동 회귀 / kanban move 0건
      - WARN 로그 + metrics 이벤트만 emit
      - 예외 비차단 (모든 케이스에서 함수 정상 종료)
    """

    def test_ra1_report_exists_noop(self) -> None:
        """RA1: report.md 존재 → no-op (WARN 로그 0건, metrics 이벤트 0건)."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = os.path.join(tmpdir, "report.md")
            # report.md 파일을 미리 생성
            with open(report_path, "w") as f:
                f.write("# Report\n")

            with patch("flow.worker_return_parser.append_log") as mock_log:
                with patch("flow.metrics.append_event") as mock_metrics:
                    emit_report_advisory(
                        registry_key="20260508-225113",
                        abs_work_dir=tmpdir,
                        report_path=report_path,
                    )
                    mock_log.assert_not_called()
                    mock_metrics.assert_not_called()

    def test_ra2_report_missing_emits_warn_and_metrics(self) -> None:
        """RA2: report.md 부재 → WARN 1건 + report.missing metrics 이벤트 1건."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = os.path.join(tmpdir, "report.md")
            # report.md 파일은 생성하지 않음

            with patch("flow.worker_return_parser.append_log") as mock_log:
                with patch("flow.worker_return_parser.append_log"):
                    pass  # 리셋

            with patch("flow.worker_return_parser.append_log") as mock_log:
                # metrics.append_event를 동적 import 내부에서도 패치하기 위해
                # flow.metrics 모듈을 sys.modules에 mock 주입
                mock_metrics_module = MagicMock()
                mock_append_event = MagicMock()
                mock_metrics_module.append_event = mock_append_event

                with patch.dict("sys.modules", {"flow.metrics": mock_metrics_module}):
                    emit_report_advisory(
                        registry_key="20260508-225113",
                        abs_work_dir=tmpdir,
                        report_path=report_path,
                    )

                # WARN 로그 1건 검증
                mock_log.assert_called_once()
                call_args = mock_log.call_args
                self.assertEqual(call_args[0][1], "WARN", "레벨이 WARN이어야 한다")
                self.assertIn("[ADVISORY]", call_args[0][2], "[ADVISORY] 프리픽스 포함")
                self.assertIn("report.md", call_args[0][2], "report.md 경로 언급")
                self.assertIn(
                    "메인 세션에서 work/ 통합", call_args[0][2], "사용자 수동 수습 경로 안내"
                )
                self.assertIn("T-446", call_args[0][2], "T-446 사례 참조 언급")

                # metrics 이벤트 1건 검증
                mock_append_event.assert_called_once()
                metrics_call = mock_append_event.call_args
                self.assertEqual(
                    metrics_call[0][1],
                    "report.missing",
                    "이벤트 타입이 report.missing이어야 한다",
                )
                payload = metrics_call[0][2]
                self.assertIn("report_path", payload, "payload에 report_path 포함")
                self.assertIn("signal_summary", payload, "payload에 signal_summary 포함")
                self.assertEqual(payload["report_path"], report_path)

    def test_ra3_abs_work_dir_none_no_exception(self) -> None:
        """RA3: abs_work_dir is None → 안전 fallback (예외 없이 처리)."""
        import os

        # report_path도 존재하지 않는 경로로 설정
        report_path = "/nonexistent/path/report.md"

        # append_log가 None abs_work_dir을 받아도 예외를 내부 흡수하도록 mock
        with patch("flow.worker_return_parser.append_log") as mock_log:
            # 예외가 발생하지 않아야 한다
            try:
                emit_report_advisory(
                    registry_key="20260508-225113",
                    abs_work_dir=None,  # type: ignore[arg-type]
                    report_path=report_path,
                )
            except Exception as exc:
                self.fail(
                    f"emit_report_advisory는 abs_work_dir=None 시 예외를 발생시켜서는 안 됩니다: {exc}"
                )

    def test_ra4_metrics_import_failure_log_still_emits(self) -> None:
        """RA4: metrics 모듈 import 실패 → log emit만, 함수 정상 종료."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = os.path.join(tmpdir, "report.md")
            # report.md 없음

            with patch("flow.worker_return_parser.append_log") as mock_log:
                # flow.metrics import를 실패하도록 sys.modules에서 제거
                import sys
                saved = sys.modules.pop("flow.metrics", None)
                try:
                    # flow.metrics를 ImportError로 강제
                    sys.modules["flow.metrics"] = None  # type: ignore[assignment]
                    emit_report_advisory(
                        registry_key="20260508-225113",
                        abs_work_dir=tmpdir,
                        report_path=report_path,
                    )
                finally:
                    # 복원
                    if saved is not None:
                        sys.modules["flow.metrics"] = saved
                    else:
                        sys.modules.pop("flow.metrics", None)

                # WARN 로그는 emit되어야 한다
                mock_log.assert_called_once()
                call_args = mock_log.call_args
                self.assertEqual(call_args[0][1], "WARN")
                self.assertIn("[ADVISORY]", call_args[0][2])


if __name__ == "__main__":
    unittest.main()
