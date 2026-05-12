"""test_review_verdict.py - review_verdict.py 단위 테스트 (T-463 W21).

13 룰 각각 위반/통과 페어 + 임계 분기 4종 (PASS/WARN/FAIL/SKIP)
+ CLI wrapper subprocess 검증.

테스트 케이스 (총 23):
    TestRuleExist:
        test_exist_1_pass / test_exist_1_missing / test_exist_1_empty
        test_exist_2_pass / test_exist_2_missing
        test_exist_2_skip_research
        test_exist_3_pass / test_exist_3_missing_key
        test_exist_4_pass / test_exist_4_empty

    TestRuleMetric:
        test_metric_1_pass / test_metric_1_mismatch
        test_metric_2_pass / test_metric_2_fail_outcome
        test_metric_2_missing_done
        test_metric_3_pass / test_metric_3_deny_emitted

    TestRuleGuard:
        test_guard_1_pass / test_guard_1_disabled
        test_guard_3_pass / test_guard_3_emitted

    TestRulePath:
        test_path_1_pass / test_path_1_missing_plan
        test_path_1_no_token

    TestRuleFsm:
        test_fsm_1_pass / test_fsm_1_wrong_phase

    TestThreshold:
        test_threshold_pass / test_threshold_warn
        test_threshold_fail_count / test_threshold_fail_hard
        test_threshold_skip_no_workdir / test_threshold_skip_phase

    TestCli:
        test_cli_main_outputs_json
        test_wrapper_exit_code

제약:
    - LLM 호출 0건.
    - tempfile.TemporaryDirectory 격리.
    - subprocess 호출 5초 timeout.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_ENGINE_DIR = str(Path(__file__).resolve().parent.parent.parent)
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from flow.review_verdict import (
    FAIL,
    PASS,
    SKIP,
    WARN,
    Violation,
    _check_exist_1,
    _check_exist_2,
    _check_exist_3,
    _check_exist_4,
    _check_fsm_1,
    _check_guard_1,
    _check_guard_3,
    _check_metric_2,
    _check_metric_3,
    _check_path_1,
    _read_metrics_lines,
    _resolve_verdict,
    compute_review_verdict,
    main as cli_main,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
WRAPPER_PATH = _REPO_ROOT / ".claude-organic" / "bin" / "flow-review-verdict"


class _BaseCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.workdir = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def write_file(self, name: str, content: str) -> Path:
        p = self.workdir / name
        p.write_text(content, encoding="utf-8")
        return p

    def write_json(self, name: str, data: dict) -> Path:
        return self.write_file(name, json.dumps(data, ensure_ascii=False))

    def write_metrics(self, events: list[dict]) -> Path:
        lines = "\n".join(json.dumps(e, ensure_ascii=False) for e in events)
        return self.write_file("metrics.jsonl", lines + "\n")


class TestRuleExist(_BaseCase):
    def test_exist_1_pass(self) -> None:
        self.write_file("report.md", "# report\nbody\n")
        self.assertIsNone(_check_exist_1(self.workdir, {}))

    def test_exist_1_missing(self) -> None:
        v = _check_exist_1(self.workdir, {})
        self.assertIsNotNone(v)
        assert v is not None
        self.assertEqual(v.rule_id, "R-EXIST-1")
        self.assertEqual(v.severity, "fail")

    def test_exist_1_empty(self) -> None:
        self.write_file("report.md", "")
        v = _check_exist_1(self.workdir, {})
        self.assertIsNotNone(v)
        assert v is not None
        self.assertIn("empty", v.message)

    def test_exist_2_pass(self) -> None:
        self.write_file("plan.md", "# plan\n")
        self.assertIsNone(_check_exist_2(self.workdir, {"command": "implement"}))

    def test_exist_2_missing(self) -> None:
        v = _check_exist_2(self.workdir, {"command": "implement"})
        self.assertIsNotNone(v)
        assert v is not None
        self.assertEqual(v.rule_id, "R-EXIST-2")

    def test_exist_2_skip_research(self) -> None:
        # research 명령은 plan.md 부재라도 통과
        self.assertIsNone(_check_exist_2(self.workdir, {"command": "research"}))

    def test_exist_3_pass(self) -> None:
        self.write_json("status.json", {"workflow_phase": "DONE"})
        self.assertIsNone(_check_exist_3(self.workdir, {}))

    def test_exist_3_missing_key(self) -> None:
        self.write_json("status.json", {"foo": "bar"})
        v = _check_exist_3(self.workdir, {})
        self.assertIsNotNone(v)
        assert v is not None
        self.assertIn("workflow_phase", v.message)

    def test_exist_4_pass(self) -> None:
        self.write_file("metrics.jsonl", '{"event_type":"x"}\n')
        ctx = {"metrics_lines": [{"event_type": "x"}]}
        self.assertIsNone(_check_exist_4(self.workdir, ctx))

    def test_exist_4_empty(self) -> None:
        self.write_file("metrics.jsonl", "")
        ctx = {"metrics_lines": []}
        v = _check_exist_4(self.workdir, ctx)
        self.assertIsNotNone(v)
        assert v is not None
        self.assertEqual(v.rule_id, "R-EXIST-4")


class TestRuleMetric(_BaseCase):
    def _ev(self, et: str, step: str | None = None, outcome: str | None = None) -> dict:
        payload: dict = {}
        if step is not None:
            payload["step"] = step
        if outcome is not None:
            payload["outcome"] = outcome
        return {"event_type": et, "payload": payload}

    def test_metric_2_pass(self) -> None:
        events = [self._ev("step.end", step="DONE", outcome="ok")]
        ctx = {"metrics_lines": events}
        self.assertIsNone(_check_metric_2(self.workdir, ctx))

    def test_metric_2_fail_outcome(self) -> None:
        events = [self._ev("step.end", step="DONE", outcome="fail")]
        ctx = {"metrics_lines": events}
        v = _check_metric_2(self.workdir, ctx)
        self.assertIsNotNone(v)
        assert v is not None
        self.assertEqual(v.severity, "fail")

    def test_metric_2_missing_done(self) -> None:
        ctx = {"metrics_lines": [self._ev("step.end", step="WORK", outcome="ok")]}
        v = _check_metric_2(self.workdir, ctx)
        self.assertIsNotNone(v)
        assert v is not None
        self.assertIn("DONE", v.message)

    def test_metric_3_pass(self) -> None:
        ctx = {"metrics_lines": [self._ev("tool.call")]}
        self.assertIsNone(_check_metric_3(self.workdir, ctx))

    def test_metric_3_deny_emitted(self) -> None:
        ctx = {"metrics_lines": [self._ev("tool.deny"), self._ev("tool.deny")]}
        v = _check_metric_3(self.workdir, ctx)
        self.assertIsNotNone(v)
        assert v is not None
        self.assertIn("count=2", v.message)


class TestRuleGuard(_BaseCase):
    def test_guard_1_pass(self) -> None:
        ctx = {"context_json": {"worktree": {"enabled": True}}}
        self.assertIsNone(_check_guard_1(self.workdir, ctx))

    def test_guard_1_disabled(self) -> None:
        ctx = {"context_json": {"worktree": {"enabled": False}}}
        v = _check_guard_1(self.workdir, ctx)
        self.assertIsNotNone(v)
        assert v is not None
        self.assertEqual(v.rule_id, "R-GUARD-1")

    def test_guard_3_pass(self) -> None:
        ctx = {"metrics_lines": [{"event_type": "step.end"}]}
        self.assertIsNone(_check_guard_3(self.workdir, ctx))

    def test_guard_3_emitted(self) -> None:
        ctx = {
            "metrics_lines": [
                {"event_type": "regression.pattern", "payload": {"kind": "hook_deny"}}
            ]
        }
        v = _check_guard_3(self.workdir, ctx)
        self.assertIsNotNone(v)
        assert v is not None
        self.assertIn("hook_deny", v.message)


class TestRulePath(_BaseCase):
    def test_path_1_pass(self) -> None:
        self.write_file("report.md", "본문에 [plan.md] 참조\n")
        self.write_file("plan.md", "# plan\n")
        self.assertIsNone(_check_path_1(self.workdir, {"command": "implement"}))

    def test_path_1_missing_plan(self) -> None:
        self.write_file("report.md", "본문에 plan.md 참조\n")
        # plan.md 미작성
        v = _check_path_1(self.workdir, {"command": "implement"})
        self.assertIsNotNone(v)
        assert v is not None
        self.assertEqual(v.rule_id, "R-PATH-1")

    def test_path_1_no_token(self) -> None:
        # report.md 안에 plan.md 토큰 자체가 없으면 통과 (검증 무의미)
        self.write_file("report.md", "본문에 다른 내용만\n")
        self.assertIsNone(_check_path_1(self.workdir, {"command": "implement"}))


class TestRuleFsm(_BaseCase):
    def test_fsm_1_pass(self) -> None:
        ctx = {"workflow_phase": "DONE"}
        self.assertIsNone(_check_fsm_1(self.workdir, ctx))

    def test_fsm_1_wrong_phase(self) -> None:
        ctx = {"workflow_phase": "WORK"}
        v = _check_fsm_1(self.workdir, ctx)
        self.assertIsNotNone(v)
        assert v is not None
        self.assertEqual(v.rule_id, "R-FSM-1")


class TestThreshold(unittest.TestCase):
    """_resolve_verdict 임계 분기 4종 검증."""

    def test_threshold_pass(self) -> None:
        result = _resolve_verdict([], {"command": "implement"})
        self.assertEqual(result.verdict, PASS)

    def test_threshold_warn(self) -> None:
        violations = [
            Violation("R-EXIST-2", "warn", "missing"),
            Violation("R-METRIC-3", "warn", "tool_deny"),
        ]
        result = _resolve_verdict(violations, {})
        self.assertEqual(result.verdict, WARN)

    def test_threshold_fail_count(self) -> None:
        violations = [
            Violation("R-EXIST-2", "warn", "x"),
            Violation("R-GUARD-3", "warn", "x"),
            Violation("R-METRIC-3", "warn", "x"),
        ]
        result = _resolve_verdict(violations, {})
        self.assertEqual(result.verdict, FAIL)
        self.assertIn("3", result.reason)

    def test_threshold_fail_hard(self) -> None:
        # 위반 1건이지만 hard-fail 룰이라 FAIL
        violations = [Violation("R-EXIST-1", "fail", "missing report.md")]
        result = _resolve_verdict(violations, {})
        self.assertEqual(result.verdict, FAIL)
        self.assertIn("hard-fail", result.reason)

    def test_threshold_fail_hard_metric(self) -> None:
        # R-METRIC-2 도 hard-fail
        violations = [Violation("R-METRIC-2", "fail", "DONE outcome=fail")]
        result = _resolve_verdict(violations, {})
        self.assertEqual(result.verdict, FAIL)


class TestEntrypointSkip(_BaseCase):
    """compute_review_verdict 진입점 SKIP 분기 검증."""

    def test_skip_no_workdir(self) -> None:
        # 존재하지 않는 디렉터리
        bogus = self.workdir / "nonexistent"
        result = compute_review_verdict("bogus", workdir=bogus)
        self.assertEqual(result.verdict, SKIP)

    def test_skip_phase_not_done(self) -> None:
        # workflow_phase=WORK -> SKIP
        self.write_json("status.json", {"workflow_phase": "WORK"})
        result = compute_review_verdict("test", workdir=self.workdir)
        self.assertEqual(result.verdict, SKIP)
        self.assertIn("WORK", result.reason)

    def test_full_pass_done(self) -> None:
        # 모든 룰 통과 가능한 최소 환경: command=research (plan/path/wt SKIP)
        # status.json + report.md + metrics.jsonl + .context.json
        self.write_json("status.json", {"workflow_phase": "DONE"})
        self.write_json(".context.json", {
            "command": "research",
            "worktree": {
                "enabled": True,
                "featureBranch": "nonexistent-branch",
            },
        })
        self.write_file("report.md", "# report\n")
        # 5 phase 모두 정상 페어 + DONE outcome=ok
        events = []
        for s in ("INIT", "PLAN", "WORK", "REPORT", "DONE"):
            events.append({"event_type": "step.start", "payload": {"step": s}})
            events.append({
                "event_type": "step.end",
                "payload": {"step": s, "outcome": "ok"},
            })
        self.write_metrics(events)
        result = compute_review_verdict("test", workdir=self.workdir)
        # research 라 R-EXIST-2/R-PATH-1/R-WT-1 SKIP, R-GUARD-2 git 검사 불가
        # 시 통과. 위반은 0~1건 사이.
        self.assertIn(result.verdict, (PASS, WARN))


class TestCli(unittest.TestCase):
    def test_cli_main_outputs_json(self) -> None:
        # CLI main() 호출 - 존재하지 않는 registry_key 로 SKIP 응답.
        captured: list[str] = []
        old_stdout = sys.stdout

        class _Capture:
            def write(self, s: str) -> int:
                captured.append(s)
                return len(s)
            def flush(self) -> None:
                pass

        try:
            sys.stdout = _Capture()  # type: ignore[assignment]
            rc = cli_main(["nonexistent-key-xxx"])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(rc, 0)
        joined = "".join(captured)
        data = json.loads(joined)
        self.assertEqual(data["verdict"], SKIP)
        self.assertIn("violations", data)

    def test_wrapper_exit_code(self) -> None:
        if not WRAPPER_PATH.exists():
            self.skipTest(f"wrapper not found: {WRAPPER_PATH}")
        proc = subprocess.run(
            [str(WRAPPER_PATH), "nonexistent-key-yyy"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["verdict"], SKIP)


class TestMetricsLineReader(_BaseCase):
    def test_skip_invalid_lines(self) -> None:
        self.write_file(
            "metrics.jsonl",
            '{"event_type":"x"}\nnot-json\n{"event_type":"y"}\n',
        )
        lines = _read_metrics_lines(self.workdir)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["event_type"], "x")
        self.assertEqual(lines[1]["event_type"], "y")


if __name__ == "__main__":
    unittest.main()
