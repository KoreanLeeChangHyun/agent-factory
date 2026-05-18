"""test_verify_code.py — T-503 신설 driver 결정론 코드 검증 단위 테스트.

대상:
  - `run(ctx)` — implement / research-skip / 도구 미설치 / 설정 부재 분기
  - `_run_pytest` / `_run_ruff` / `_run_mypy` — subprocess 호출 결과 parse
  - `_parse_pytest_summary` / `_parse_pytest_failed_nodes` — pytest 출력 파싱
  - `read_code_json` / `tool_result` — 헬퍼
  - JSON 스키마 회귀

graceful SKIP 검증 우선 — pytest/ruff/mypy 가 실제로 PATH 에 없는 환경에서도
테스트가 통과해야 한다. PATH 의존성은 monkeypatch 로 회피.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.v2 import _verify_code
from engine.v2._common import WorkflowContext


def _make_ctx(tmp_path: Path, command: str = "implement") -> WorkflowContext:
    (tmp_path / "work").mkdir(exist_ok=True)
    return WorkflowContext(
        ticket_no="T-503",
        registry_key="20260518-000000",
        work_dir=tmp_path,
        command=command,
        mode="multi",
        current_step="VALIDATE",
        worktree_path=tmp_path,  # tmp_path 를 워크트리로 사용
    )


# -------- run(ctx) 분기 --------


def test_run_research_skip(tmp_path: Path) -> None:
    """command=research → 즉시 SKIP. code.json 의 command_skip=True 박제."""
    ctx = _make_ctx(tmp_path, command="research")
    out = _verify_code.run(ctx)
    assert out == ctx.validate_code_json_path()
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["command"] == "research"
    assert payload["command_skip"] is True
    assert payload["tools"] == []


def test_run_review_skip(tmp_path: Path) -> None:
    """command=review → 즉시 SKIP."""
    ctx = _make_ctx(tmp_path, command="review")
    out = _verify_code.run(ctx)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["command_skip"] is True


def test_run_implement_no_tools_graceful(tmp_path: Path, monkeypatch) -> None:
    """implement 이지만 pytest/ruff/mypy 모두 미설치 — graceful SKIP. driver 중단 없음."""
    # 모든 도구 미설치 시뮬레이션
    monkeypatch.setattr(_verify_code.shutil, "which", lambda _tool: None)
    ctx = _make_ctx(tmp_path, command="implement")
    out = _verify_code.run(ctx)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["command_skip"] is False
    assert payload["command"] == "implement"
    assert len(payload["tools"]) == 3
    for entry in payload["tools"]:
        assert entry["status"] == "skip"
        assert "not installed" in entry.get("reason", "")


def test_run_implement_no_config(tmp_path: Path, monkeypatch) -> None:
    """implement + 도구 설치되었지만 config 부재 — graceful SKIP."""
    monkeypatch.setattr(_verify_code.shutil, "which", lambda _tool: "/usr/bin/" + _tool)
    # tmp_path 안에 pyproject.toml / pytest.ini / tests/ 모두 없음.
    ctx = _make_ctx(tmp_path, command="implement")
    out = _verify_code.run(ctx)
    payload = json.loads(out.read_text(encoding="utf-8"))
    for entry in payload["tools"]:
        # config 부재 또는 (호출 가능하지만 fail) — 어느 쪽이든 driver 중단 없음
        assert entry["status"] in ("skip", "ok", "fail")


def test_run_creates_validate_dir(tmp_path: Path) -> None:
    """validate/ 디렉터리가 없어도 run(ctx) 가 자동 mkdir."""
    ctx = _make_ctx(tmp_path, command="research")
    assert not ctx.validate_dir().exists()
    _verify_code.run(ctx)
    assert ctx.validate_dir().is_dir()


# -------- _has_tool --------


def test_has_tool_existing(monkeypatch) -> None:
    monkeypatch.setattr(_verify_code.shutil, "which", lambda _: "/usr/bin/foo")
    assert _verify_code._has_tool("foo") is True


def test_has_tool_missing(monkeypatch) -> None:
    monkeypatch.setattr(_verify_code.shutil, "which", lambda _: None)
    assert _verify_code._has_tool("nonexistent") is False


# -------- config detection --------


def test_detect_pytest_config_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.pytest]", encoding="utf-8")
    assert _verify_code._detect_pytest_config(tmp_path) is True


def test_detect_pytest_config_tests_dir(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    assert _verify_code._detect_pytest_config(tmp_path) is True


def test_detect_pytest_config_missing(tmp_path: Path) -> None:
    assert _verify_code._detect_pytest_config(tmp_path) is False


def test_detect_ruff_config_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.ruff]\nline-length = 100\n", encoding="utf-8"
    )
    assert _verify_code._detect_ruff_config(tmp_path) is True


def test_detect_ruff_config_dedicated(tmp_path: Path) -> None:
    (tmp_path / "ruff.toml").write_text("line-length = 100", encoding="utf-8")
    assert _verify_code._detect_ruff_config(tmp_path) is True


def test_detect_ruff_config_missing(tmp_path: Path) -> None:
    assert _verify_code._detect_ruff_config(tmp_path) is False


def test_detect_mypy_config_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.mypy]\nstrict = true\n", encoding="utf-8"
    )
    assert _verify_code._detect_mypy_config(tmp_path) is True


def test_detect_mypy_config_missing(tmp_path: Path) -> None:
    assert _verify_code._detect_mypy_config(tmp_path) is False


# -------- pytest 결과 parse --------


def test_parse_pytest_summary_passed_failed() -> None:
    text = """test session starts
......
5 passed, 1 failed in 0.34s
"""
    counts = _verify_code._parse_pytest_summary(text)
    assert counts.get("passed") == 5
    assert counts.get("failed") == 1


def test_parse_pytest_failed_nodes() -> None:
    text = """
FAILED tests/test_x.py::test_y - assert 1 == 2
FAILED tests/test_z.py::test_w - TypeError
ERROR tests/test_q.py - collection error
"""
    nodes = _verify_code._parse_pytest_failed_nodes(text)
    assert "tests/test_x.py::test_y" in nodes
    assert "tests/test_z.py::test_w" in nodes
    assert "tests/test_q.py" in nodes


def test_parse_pytest_failed_nodes_empty() -> None:
    text = "test session starts\n......\n5 passed in 0.1s\n"
    assert _verify_code._parse_pytest_failed_nodes(text) == []


# -------- _run_pytest 도구 미설치 graceful SKIP --------


def test_run_pytest_no_tool_skip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(_verify_code.shutil, "which", lambda _: None)
    result = _verify_code._run_pytest(tmp_path)
    assert result["tool"] == "pytest"
    assert result["status"] == "skip"
    assert "not installed" in result["reason"]


def test_run_pytest_no_config_skip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(_verify_code.shutil, "which", lambda _: "/usr/bin/pytest")
    result = _verify_code._run_pytest(tmp_path)
    assert result["tool"] == "pytest"
    assert result["status"] == "skip"
    assert "no pytest config" in result["reason"]


def test_run_pytest_ok_mocked(tmp_path: Path, monkeypatch) -> None:
    """pytest 호출이 returncode=0 stdout='5 passed in 0.1s' 인 경우 → status=ok."""
    monkeypatch.setattr(_verify_code.shutil, "which", lambda _: "/usr/bin/pytest")
    (tmp_path / "tests").mkdir()

    def _mock_run(_cmd, cwd, timeout=600):
        return 0, "5 passed in 0.1s\n", "", 100

    monkeypatch.setattr(_verify_code, "_run_subprocess", _mock_run)
    result = _verify_code._run_pytest(tmp_path)
    assert result["status"] == "ok"
    assert result["rc"] == 0


def test_run_pytest_fail_mocked(tmp_path: Path, monkeypatch) -> None:
    """pytest 호출이 returncode=1 → status=fail. head_diagnostics 박제."""
    monkeypatch.setattr(_verify_code.shutil, "which", lambda _: "/usr/bin/pytest")
    (tmp_path / "tests").mkdir()

    def _mock_run(_cmd, cwd, timeout=600):
        return 1, "FAILED tests/a.py::test_b\n3 failed, 5 passed in 0.5s\n", "", 200

    monkeypatch.setattr(_verify_code, "_run_subprocess", _mock_run)
    result = _verify_code._run_pytest(tmp_path)
    assert result["status"] == "fail"
    assert "tests/a.py::test_b" in result["head_diagnostics"]


def test_run_pytest_no_tests_collected_skip(tmp_path: Path, monkeypatch) -> None:
    """pytest returncode=5 (no tests collected) → status=skip."""
    monkeypatch.setattr(_verify_code.shutil, "which", lambda _: "/usr/bin/pytest")
    (tmp_path / "tests").mkdir()

    def _mock_run(_cmd, cwd, timeout=600):
        return 5, "no tests ran in 0.0s\n", "", 50

    monkeypatch.setattr(_verify_code, "_run_subprocess", _mock_run)
    result = _verify_code._run_pytest(tmp_path)
    assert result["status"] == "skip"


# -------- _run_ruff --------


def test_run_ruff_no_tool_skip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(_verify_code.shutil, "which", lambda _: None)
    result = _verify_code._run_ruff(tmp_path)
    assert result["status"] == "skip"
    assert "ruff not installed" in result["reason"]


def test_run_ruff_no_config_skip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(_verify_code.shutil, "which", lambda _: "/usr/bin/ruff")
    # config 없음
    result = _verify_code._run_ruff(tmp_path)
    assert result["status"] == "skip"


def test_run_ruff_clean_mocked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(_verify_code.shutil, "which", lambda _: "/usr/bin/ruff")
    (tmp_path / "ruff.toml").write_text("line-length = 100", encoding="utf-8")

    def _mock_run(_cmd, cwd, timeout=600):
        return 0, "", "", 50

    monkeypatch.setattr(_verify_code, "_run_subprocess", _mock_run)
    result = _verify_code._run_ruff(tmp_path)
    assert result["status"] == "ok"
    assert result["counts"]["diagnostics"] == 0


def test_run_ruff_violations_mocked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(_verify_code.shutil, "which", lambda _: "/usr/bin/ruff")
    (tmp_path / "ruff.toml").write_text("line-length = 100", encoding="utf-8")

    def _mock_run(_cmd, cwd, timeout=600):
        return 1, "src/a.py:1:1: E501 line too long\nsrc/b.py:2:1: F401 unused\n", "", 80

    monkeypatch.setattr(_verify_code, "_run_subprocess", _mock_run)
    result = _verify_code._run_ruff(tmp_path)
    assert result["status"] == "fail"
    assert result["counts"]["diagnostics"] == 2


# -------- _run_mypy --------


def test_run_mypy_no_tool_skip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(_verify_code.shutil, "which", lambda _: None)
    result = _verify_code._run_mypy(tmp_path)
    assert result["status"] == "skip"


def test_run_mypy_no_config_skip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(_verify_code.shutil, "which", lambda _: "/usr/bin/mypy")
    result = _verify_code._run_mypy(tmp_path)
    assert result["status"] == "skip"


# -------- read_code_json / tool_result --------


def test_read_code_json_missing(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, command="implement")
    payload = _verify_code.read_code_json(ctx)
    assert payload == {}


def test_read_code_json_present(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, command="implement")
    ctx.validate_dir().mkdir(parents=True, exist_ok=True)
    sample = {"schema_version": 1, "command": "implement", "tools": []}
    ctx.validate_code_json_path().write_text(json.dumps(sample), encoding="utf-8")
    payload = _verify_code.read_code_json(ctx)
    assert payload == sample


def test_read_code_json_corrupt(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, command="implement")
    ctx.validate_dir().mkdir(parents=True, exist_ok=True)
    ctx.validate_code_json_path().write_text("not valid json {", encoding="utf-8")
    assert _verify_code.read_code_json(ctx) == {}


def test_tool_result_found() -> None:
    payload = {
        "tools": [
            {"tool": "pytest", "status": "ok"},
            {"tool": "ruff", "status": "fail"},
        ]
    }
    entry = _verify_code.tool_result(payload, "pytest")
    assert entry is not None
    assert entry["status"] == "ok"


def test_tool_result_missing() -> None:
    payload = {"tools": [{"tool": "pytest", "status": "ok"}]}
    assert _verify_code.tool_result(payload, "ruff") is None


def test_tool_result_empty() -> None:
    assert _verify_code.tool_result({"tools": []}, "pytest") is None


# -------- JSON 스키마 회귀 --------


def test_code_json_schema_research(tmp_path: Path) -> None:
    """research 모드 — JSON 스키마 기본 키 회귀."""
    ctx = _make_ctx(tmp_path, command="research")
    out = _verify_code.run(ctx)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "schema_version" in payload
    assert "command" in payload
    assert "command_skip" in payload
    assert "tools" in payload
    assert isinstance(payload["tools"], list)


def test_code_json_schema_implement(tmp_path: Path, monkeypatch) -> None:
    """implement 모드 — work_root 키 + tools 3건 (pytest/ruff/mypy)."""
    monkeypatch.setattr(_verify_code.shutil, "which", lambda _: None)  # 모두 SKIP
    ctx = _make_ctx(tmp_path, command="implement")
    out = _verify_code.run(ctx)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["command_skip"] is False
    assert "work_root" in payload
    tool_names = [t["tool"] for t in payload["tools"]]
    assert tool_names == ["pytest", "ruff", "mypy"]
