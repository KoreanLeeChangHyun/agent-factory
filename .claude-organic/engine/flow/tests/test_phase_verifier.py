"""test_phase_verifier.py - phase_verifier.py 단위 테스트 매트릭스 (T-454 W04).

command 4종 x 통과/실패 + retry-context.json 영속 검증 + flow-phase-verify wrapper subprocess 검증.

테스트 케이스 목록 (13개):
    TestImplementBranch:
        test_implement_pass          - work files 모두 존재 + git diff 1건
        test_implement_missing_file  - W02 산출물 누락
        test_implement_no_diff       - git diff 0건

    TestResearchBranch:
        test_research_pass           - 헤더 3 + mermaid 1
        test_research_few_sections   - 헤더 2 (실패)
        test_research_no_mermaid     - mermaid 0 (실패)

    TestReviewBranch:
        test_review_pass             - verdict 키워드 존재
        test_review_no_verdict       - 키워드 부재 (실패)

    TestArchitectBranch:
        test_architect_pass          - mermaid 2 + 헤더 4
        test_architect_few_diagrams  - mermaid 1 (실패)

    TestRetryContext:
        test_retry_context_written        - 실패 시 retry-context.json 3필드 정확 기록
        test_retry_context_partial_update - 기존 retry_count/prompt_hints 보존, 3필드만 갱신

    TestWrapperExitCode:
        test_wrapper_exit_code            - subprocess flow-phase-verify 호출, 종료 코드 0/1/2 검증

제약:
    - LLM 호출 0건 (rule-based 단위 테스트).
    - tempfile.TemporaryDirectory 로 격리, 외부 git/파일시스템 의존 회피.
    - git diff 관련 검증은 _check_git_diff 함수 자체를 mock 으로 stub.
    - subprocess 호출 시 timeout=10s.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# sys.path: .claude-organic/engine 을 포함시켜 flow 패키지 import 가능하게 한다
_ENGINE_DIR = str(Path(__file__).resolve().parent.parent.parent)
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from flow.phase_verifier import (
    _aggregate_md_content,
    _check_git_diff,
    _check_work_files_exist,
    _count_mermaid_blocks,
    _count_sections,
    _verify_architect,
    _verify_implement_like,
    _verify_research,
    _verify_review,
    _write_retry_context_on_fail,
)

# flow-phase-verify wrapper 절대 경로
_REPO_ROOT = Path(__file__).resolve().parents[4]  # worktree root
WRAPPER_PATH = _REPO_ROOT / ".claude-organic" / "bin" / "flow-phase-verify"


# ---------------------------------------------------------------------------
# 공통 베이스 클래스
# ---------------------------------------------------------------------------


class _BaseCase(unittest.TestCase):
    """임시 work_dir 격리 베이스."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    # --- 픽스처 헬퍼 ---

    def _write_init(self, command: str = "implement") -> None:
        """init-result.json 에 command 필드 기록."""
        (self.work_dir / "init-result.json").write_text(
            json.dumps({"command": command}, ensure_ascii=False),
            encoding="utf-8",
        )

    def _write_plan(self, worker_ids: tuple = ("W01", "W02")) -> str:
        """plan.md 에 H3 W## 헤더 포함 최소 내용 기록 후 내용 반환."""
        plan = "# Plan\n\n## Tasks\n\n"
        for wid in worker_ids:
            plan += "### {}: 작업 설명\n\n".format(wid)
        plan_path = self.work_dir / "plan.md"
        plan_path.write_text(plan, encoding="utf-8")
        return plan

    def _write_work(self, worker_id: str, content: str) -> None:
        """work/<worker_id>-test.md 에 content 기록."""
        wd = self.work_dir / "work"
        wd.mkdir(exist_ok=True)
        (wd / "{}-test.md".format(worker_id)).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# implement 분기 (3개)
# ---------------------------------------------------------------------------


class TestImplementBranch(_BaseCase):
    """_verify_implement_like 검증."""

    def test_implement_pass(self) -> None:
        """work files 모두 존재 + git diff 1건 -> ok."""
        plan_md = self._write_plan(("W01", "W02"))
        self._write_work("W01", "# work1\n")
        self._write_work("W02", "# work2\n")

        with mock.patch("flow.phase_verifier._check_git_diff", return_value=1):
            ok, reason, failed = _verify_implement_like(str(self.work_dir), plan_md)

        self.assertTrue(ok, msg="reason={}, failed={}".format(reason, failed))
        self.assertEqual(failed, [])
        self.assertIn("implement verifier passed", reason)

    def test_implement_missing_file(self) -> None:
        """W02 산출물 누락 -> 실패."""
        plan_md = self._write_plan(("W01", "W02"))
        self._write_work("W01", "# work1\n")
        # W02 의도적 누락

        ok, reason, failed = _verify_implement_like(str(self.work_dir), plan_md)

        self.assertFalse(ok, msg="산출물 누락이면 실패여야 한다")
        self.assertIn("missing work files", reason)
        self.assertIn("W02", failed)

    def test_implement_no_diff(self) -> None:
        """git diff 0건 -> 실패."""
        plan_md = self._write_plan(("W01",))
        self._write_work("W01", "# work1\n")

        with mock.patch("flow.phase_verifier._check_git_diff", return_value=0):
            ok, reason, failed = _verify_implement_like(str(self.work_dir), plan_md)

        self.assertFalse(ok, msg="git diff 0건이면 실패여야 한다")
        self.assertIn("no git diff", reason)


# ---------------------------------------------------------------------------
# research 분기 (3개)
# ---------------------------------------------------------------------------


class TestResearchBranch(_BaseCase):
    """_verify_research 검증."""

    def test_research_pass(self) -> None:
        """헤더 3 + mermaid 1 -> ok."""
        plan_md = self._write_plan(("W01",))
        content = (
            "## 섹션1\n\n내용\n\n"
            "## 섹션2\n\n내용\n\n"
            "## 섹션3\n\n```mermaid\ngraph LR\n  A-->B\n```\n"
        )
        self._write_work("W01", content)

        ok, reason, failed = _verify_research(str(self.work_dir), plan_md)

        self.assertTrue(ok, msg="reason={}, failed={}".format(reason, failed))
        self.assertIn("research verifier passed", reason)

    def test_research_few_sections(self) -> None:
        """헤더 2 (need 3) -> 실패."""
        plan_md = self._write_plan(("W01",))
        content = (
            "## 섹션1\n\n내용\n\n"
            "## 섹션2\n\n```mermaid\ngraph LR\n  A-->B\n```\n"
        )
        self._write_work("W01", content)

        ok, reason, failed = _verify_research(str(self.work_dir), plan_md)

        self.assertFalse(ok, msg="헤더 2개면 실패여야 한다")
        self.assertIn("missing sections", reason)
        self.assertIn("need 3", reason)

    def test_research_no_mermaid(self) -> None:
        """mermaid 0개 (헤더는 충족) -> 실패."""
        plan_md = self._write_plan(("W01",))
        content = (
            "## 섹션1\n\n내용\n\n"
            "## 섹션2\n\n내용\n\n"
            "## 섹션3\n\n내용 (mermaid 없음)\n"
        )
        self._write_work("W01", content)

        ok, reason, failed = _verify_research(str(self.work_dir), plan_md)

        self.assertFalse(ok, msg="mermaid 0개면 실패여야 한다")
        self.assertIn("missing mermaid block", reason)


# ---------------------------------------------------------------------------
# review 분기 (2개)
# ---------------------------------------------------------------------------


class TestReviewBranch(_BaseCase):
    """_verify_review 검증."""

    def test_review_pass(self) -> None:
        """verdict 키워드 'Verdict' 존재 -> ok."""
        plan_md = self._write_plan(("W01",))
        self._write_work("W01", "# 리뷰 보고서\n\n## Verdict\n\n코드 품질 양호.\n")

        ok, reason, failed = _verify_review(str(self.work_dir), plan_md)

        self.assertTrue(ok, msg="reason={}, failed={}".format(reason, failed))
        self.assertIn("review verifier passed", reason)

    def test_review_no_verdict(self) -> None:
        """verdict 키워드 부재 -> 실패."""
        plan_md = self._write_plan(("W01",))
        self._write_work("W01", "# 리뷰 보고서\n\n## 분석\n\n코드 품질 분석 내용만 있음.\n")

        ok, reason, failed = _verify_review(str(self.work_dir), plan_md)

        self.assertFalse(ok, msg="verdict 키워드 부재면 실패여야 한다")
        self.assertIn("missing verdict section", reason)


# ---------------------------------------------------------------------------
# architect 분기 (2개)
# ---------------------------------------------------------------------------


class TestArchitectBranch(_BaseCase):
    """_verify_architect 검증."""

    def test_architect_pass(self) -> None:
        """mermaid 2 + 헤더 4 -> ok."""
        plan_md = self._write_plan(("W01",))
        content = (
            "## 개요\n\n내용\n\n"
            "## 컴포넌트\n\n```mermaid\ngraph LR\n  A-->B\n```\n\n"
            "## 데이터 흐름\n\n```mermaid\nsequenceDiagram\n  A->>B: req\n```\n\n"
            "## 결론\n\n내용\n"
        )
        self._write_work("W01", content)

        ok, reason, failed = _verify_architect(str(self.work_dir), plan_md)

        self.assertTrue(ok, msg="reason={}, failed={}".format(reason, failed))
        self.assertIn("architect verifier passed", reason)

    def test_architect_few_diagrams(self) -> None:
        """mermaid 1 (need 2) -> 실패."""
        plan_md = self._write_plan(("W01",))
        content = (
            "## 개요\n\n내용\n\n"
            "## 컴포넌트\n\n```mermaid\ngraph LR\n  A-->B\n```\n\n"
            "## 데이터 흐름\n\n내용 (mermaid 없음)\n\n"
            "## 결론\n\n내용\n"
        )
        self._write_work("W01", content)

        ok, reason, failed = _verify_architect(str(self.work_dir), plan_md)

        self.assertFalse(ok, msg="mermaid 1개면 실패여야 한다")
        self.assertIn("insufficient diagrams", reason)
        self.assertIn("need 2", reason)


# ---------------------------------------------------------------------------
# retry-context.json 영속 검증 (2개)
# ---------------------------------------------------------------------------


class TestRetryContext(_BaseCase):
    """_write_retry_context_on_fail 검증."""

    def test_retry_context_written(self) -> None:
        """실패 시 retry-context.json 에 3필드 정확 기록."""
        _write_retry_context_on_fail(
            str(self.work_dir),
            failure_reason="implement: no git diff (워크트리 변경 0건)",
            failed_steps=["W01", "W02"],
        )

        retry_path = self.work_dir / "retry-context.json"
        self.assertTrue(retry_path.exists(), "retry-context.json 이 생성되어야 한다")

        data = json.loads(retry_path.read_text(encoding="utf-8"))
        self.assertEqual(data["last_failure_phase"], "VALIDATE")
        self.assertEqual(
            data["last_failure_reason"],
            "implement: no git diff (워크트리 변경 0건)",
        )
        self.assertEqual(data["failed_work_steps"], ["W01", "W02"])

    def test_retry_context_partial_update(self) -> None:
        """기존 retry_count / prompt_hints 보존, 3필드만 갱신 (read-modify-write)."""
        retry_path = self.work_dir / "retry-context.json"
        existing = {
            "last_failure_phase": "VALIDATE",
            "last_failure_reason": "old reason",
            "failed_work_steps": ["W99"],
            "retry_count": {"VALIDATE": 2},
            "prompt_hints": ["hint_a", "hint_b"],
        }
        retry_path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        _write_retry_context_on_fail(
            str(self.work_dir),
            failure_reason="research: missing mermaid block",
            failed_steps=["W03"],
        )

        data = json.loads(retry_path.read_text(encoding="utf-8"))
        # 3필드 갱신 확인
        self.assertEqual(data["last_failure_phase"], "VALIDATE")
        self.assertEqual(data["last_failure_reason"], "research: missing mermaid block")
        self.assertEqual(data["failed_work_steps"], ["W03"])
        # T-455 scope 필드 보존 확인
        self.assertEqual(data["retry_count"], {"VALIDATE": 2})
        self.assertEqual(data["prompt_hints"], ["hint_a", "hint_b"])


# ---------------------------------------------------------------------------
# wrapper subprocess 검증 (1개, 3가지 시나리오)
# ---------------------------------------------------------------------------


class TestWrapperExitCode(unittest.TestCase):
    """flow-phase-verify wrapper subprocess 종료 코드 검증."""

    def test_wrapper_exit_code(self) -> None:
        """subprocess 로 flow-phase-verify 호출, 종료 코드 2/1/0 검증."""
        # --- 종료 코드 2: 인자 없음 ---
        result_no_args = subprocess.run(
            [str(WRAPPER_PATH)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(
            result_no_args.returncode,
            2,
            msg="인자 없음 시 exit=2 기대. stderr={!r}".format(result_no_args.stderr),
        )
        self.assertIn(
            "usage:",
            result_no_args.stderr,
            msg="usage 메시지가 stderr 에 출력되어야 한다",
        )

        # --- 종료 코드 1: 존재하지 않는 registry_key ---
        result_nonexist = subprocess.run(
            [str(WRAPPER_PATH), "nonexistent-key-99999999"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(
            result_nonexist.returncode,
            1,
            msg="nonexistent key 시 exit=1 기대. stdout={!r}".format(result_nonexist.stdout),
        )
        self.assertIn(
            "FAIL",
            result_nonexist.stdout,
            msg="FAIL 메시지가 stdout 에 출력되어야 한다",
        )

        # --- 종료 코드 0: research 통과 시나리오 ---
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_key = "test-wrapper-00000000"
            work_dir = Path(tmpdir) / ".claude-organic" / "runs" / registry_key
            work_dir.mkdir(parents=True)

            (work_dir / "init-result.json").write_text(
                json.dumps({"command": "research"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (work_dir / "plan.md").write_text(
                "# Plan\n\n### W01: 작업\n\n", encoding="utf-8"
            )
            work_subdir = work_dir / "work"
            work_subdir.mkdir()
            (work_subdir / "W01-test.md").write_text(
                "## 섹션1\n\n내용\n\n## 섹션2\n\n내용\n\n"
                "## 섹션3\n\n```mermaid\ngraph LR\n  A-->B\n```\n",
                encoding="utf-8",
            )

            # verify_validate_phase 는 절대 경로 registry_key 를 지원한다.
            # (resolve_work_dir 이 isabs 체크 후 그대로 반환)
            result_pass = subprocess.run(
                [str(WRAPPER_PATH), str(work_dir)],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=tmpdir,
            )
            self.assertEqual(
                result_pass.returncode,
                0,
                msg="통과 시나리오 exit=0 기대. stdout={!r}, stderr={!r}".format(
                    result_pass.stdout, result_pass.stderr
                ),
            )
            self.assertIn(
                "OK",
                result_pass.stdout,
                msg="OK 메시지가 stdout 에 출력되어야 한다",
            )


# ---------------------------------------------------------------------------
# 헬퍼 함수 단위 검증 (추가 커버리지)
# ---------------------------------------------------------------------------


class TestHelpers(unittest.TestCase):
    """_count_sections / _count_mermaid_blocks / _check_work_files_exist 헬퍼 검증."""

    def test_count_sections(self) -> None:
        """## 헤더와 ### 헤더를 모두 카운트한다."""
        md = "## 섹션1\n### 서브섹션\n## 섹션2\n"
        self.assertEqual(_count_sections(md), 3)

    def test_count_mermaid_blocks(self) -> None:
        """mermaid 코드 블록 2개 카운트."""
        md = "```mermaid\ngraph LR\n  A-->B\n```\n\n```mermaid\nsequenceDiagram\n  A->>B: r\n```\n"
        self.assertEqual(_count_mermaid_blocks(md), 2)

    def test_count_mermaid_blocks_zero(self) -> None:
        """mermaid 없는 경우 0 반환."""
        self.assertEqual(_count_mermaid_blocks("## 섹션\n\n내용\n"), 0)

    def test_check_work_files_exist_all_present(self) -> None:
        """W01, W02 모두 존재 시 missing 없음."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            (work_dir / "work").mkdir()
            (work_dir / "work" / "W01-result.md").write_text("# w1", encoding="utf-8")
            (work_dir / "work" / "W02-result.md").write_text("# w2", encoding="utf-8")
            plan_md = "### W01: 작업\n\n### W02: 작업\n\n"
            existing, missing = _check_work_files_exist(plan_md, str(work_dir))
            self.assertEqual(sorted(existing), ["W01", "W02"])
            self.assertEqual(missing, [])

    def test_check_work_files_exist_context_excluded(self) -> None:
        """-context.md 파일은 산출물로 인정하지 않는다."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            (work_dir / "work").mkdir()
            # context 파일만 있고 실제 산출물 없음
            (work_dir / "work" / "W01-context.md").write_text("ctx", encoding="utf-8")
            plan_md = "### W01: 작업\n\n"
            existing, missing = _check_work_files_exist(plan_md, str(work_dir))
            self.assertEqual(existing, [])
            self.assertEqual(missing, ["W01"])


if __name__ == "__main__":
    unittest.main()
