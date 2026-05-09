"""test_subagent_stop_sentinel.py — subagent-stop.py sentinel 감지 단위 테스트 (T-455 W06).

본 테스트는 plan.md §9 Case ④ 를 검증한다:
  - HOOK_FAIL_RECORD=true 환경변수 설정 시만 flow-fail-record 호출
  - .workflow-failed sentinel 부재 시 호출 0건
  - .workflow-failed.recorded 마커 존재 시 호출 0건 (중복 차단)
  - subprocess.Popen mock (monkeypatch) 으로 호출 인자 + 횟수 검증

importlib.util 로 `subagent-stop.py` 를 직접 로드한다 — 파일명 하이픈 때문에
일반 import 가 불가능하다. dispatcher 의존성을 위해 hooks/ 디렉터리를
sys.path 에 등록한다.
"""
from __future__ import annotations

import importlib.util as _ilu
import json
import os
import sys
from pathlib import Path

import pytest

# sys.path 보장 — hooks/ + engine/ 등록
_TEST_DIR = Path(__file__).resolve().parent
_FLOW_DIR = _TEST_DIR.parent
_ENGINE_DIR = _FLOW_DIR.parent
_PROJECT_ROOT = _ENGINE_DIR.parent.parent  # workspace/claude 가 아닌 워크트리 루트
_HOOKS_DIR = _ENGINE_DIR.parent / "hooks"  # .claude-organic/hooks/

if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_SUBAGENT_STOP_PATH = _HOOKS_DIR / "subagent-stop.py"
assert _SUBAGENT_STOP_PATH.exists(), (
    f"subagent-stop.py 가 존재해야 함: {_SUBAGENT_STOP_PATH}"
)

_spec = _ilu.spec_from_file_location("subagent_stop_module", _SUBAGENT_STOP_PATH)
_subagent_stop_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_subagent_stop_mod)

_scan_and_trigger_fail_record = _subagent_stop_mod._scan_and_trigger_fail_record


# =============================================================================
# 헬퍼 — mock workflow 생성 (scan_active_workflows 가 발견하도록)
# =============================================================================


def _make_mock_runs(project_root: Path, registry_key: str = "20260510-123456") -> Path:
    """`<project_root>/.claude-organic/runs/<registry_key>/` 모의 디렉터리 생성.

    scan_active_workflows() 가 status.json 을 읽어 발견하도록 최소 status.json
    을 작성한다. step 은 활성 phase (예: WORK) 로 설정한다.
    """
    runs_dir = project_root / ".claude-organic" / "runs" / registry_key
    runs_dir.mkdir(parents=True, exist_ok=True)
    status = {
        "step": "WORK",
        "phase": "WORK",
        "registryKey": registry_key,
        "workDir": f".claude-organic/runs/{registry_key}",
    }
    (runs_dir / "status.json").write_text(
        json.dumps(status, ensure_ascii=False), encoding="utf-8"
    )
    return runs_dir


def _install_fake_bin(project_root: Path) -> Path:
    """`.claude-organic/bin/flow-fail-record` 를 실행 가능한 더미로 생성.

    `_resolve_fail_record_bin()` 이 실행 파일 존재 + access(X_OK) 를 검사하므로
    chmod +x 까지 설정한다.
    """
    bin_dir = project_root / ".claude-organic" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    bin_path = bin_dir / "flow-fail-record"
    bin_path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    bin_path.chmod(0o755)
    return bin_path


@pytest.fixture
def isolated_project(tmp_path, monkeypatch):
    """격리된 가짜 project_root 를 만들고 CLAUDE_PROJECT_DIR 로 바인딩.

    `_resolve_fail_record_bin()` 이 CLAUDE_PROJECT_DIR 환경변수를 우선 검사하므로
    이걸로 hooks 모듈이 가짜 root 를 보도록 강제한다.
    """
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    # scan_active_workflows 는 resolve_project_root 를 호출하므로 그것도 가짜 root 로 패치
    import common  # noqa: PLC0415

    monkeypatch.setattr(common, "resolve_project_root", lambda: str(tmp_path))

    # .claude-organic/.settings 가 있어야 일부 helper 가 성공 (없어도 무방하지만 안전을 위해)
    settings_dir = tmp_path / ".claude-organic"
    settings_dir.mkdir(parents=True, exist_ok=True)
    (settings_dir / ".settings").write_text("", encoding="utf-8")

    return tmp_path


@pytest.fixture
def popen_recorder(monkeypatch):
    """subprocess.Popen 호출을 가로채 인자를 기록하는 fixture."""
    calls: list[list[str]] = []

    class _MockProc:
        pid = 12345

        def __init__(self, *a, **kw):
            pass

    def _fake_popen(cmd, *args, **kwargs):
        calls.append(list(cmd))
        return _MockProc()

    # subagent-stop 모듈은 `import subprocess` 후 `subprocess.Popen(...)` 호출
    monkeypatch.setattr(_subagent_stop_mod.subprocess, "Popen", _fake_popen)
    return calls


# =============================================================================
# 테스트
# =============================================================================


def test_no_call_when_flag_disabled(isolated_project, popen_recorder):
    """HOOK_FAIL_RECORD 미활성 (False) 시 Popen 호출 0건."""
    runs_dir = _make_mock_runs(isolated_project)
    (runs_dir / ".workflow-failed").write_text(
        json.dumps({"registry_key": "20260510-123456"}), encoding="utf-8"
    )
    _install_fake_bin(isolated_project)

    _scan_and_trigger_fail_record({"HOOK_FAIL_RECORD": False})

    assert popen_recorder == []


def test_no_call_when_flag_missing(isolated_project, popen_recorder):
    """flag dict 에 키 자체가 없어도 (기본 False) Popen 호출 0건."""
    runs_dir = _make_mock_runs(isolated_project)
    (runs_dir / ".workflow-failed").write_text("{}", encoding="utf-8")
    _install_fake_bin(isolated_project)

    _scan_and_trigger_fail_record({})  # HOOK_FAIL_RECORD 키 없음

    assert popen_recorder == []


def test_no_call_when_sentinel_absent(isolated_project, popen_recorder):
    """sentinel 부재 시 Popen 호출 0건."""
    _make_mock_runs(isolated_project)  # status.json 만 생성, sentinel 없음
    _install_fake_bin(isolated_project)

    _scan_and_trigger_fail_record({"HOOK_FAIL_RECORD": True})

    assert popen_recorder == []


def test_no_call_when_recorded_marker_exists(isolated_project, popen_recorder):
    """.workflow-failed.recorded 마커가 이미 있으면 Popen 호출 0건."""
    runs_dir = _make_mock_runs(isolated_project)
    (runs_dir / ".workflow-failed").write_text("{}", encoding="utf-8")
    (runs_dir / ".workflow-failed.recorded").touch()
    _install_fake_bin(isolated_project)

    _scan_and_trigger_fail_record({"HOOK_FAIL_RECORD": True})

    assert popen_recorder == []


def test_no_call_when_bin_missing(isolated_project, popen_recorder):
    """flow-fail-record 실행 파일 부재 시 Popen 호출 0건."""
    runs_dir = _make_mock_runs(isolated_project)
    (runs_dir / ".workflow-failed").write_text("{}", encoding="utf-8")
    # _install_fake_bin 호출 안 함 — 실행 파일 부재

    _scan_and_trigger_fail_record({"HOOK_FAIL_RECORD": True})

    assert popen_recorder == []


def test_call_dispatched_when_all_conditions_met(isolated_project, popen_recorder):
    """모든 조건 충족 시 flow-fail-record 비차단 Popen 호출 발생."""
    runs_dir = _make_mock_runs(isolated_project, registry_key="20260510-130000")
    (runs_dir / ".workflow-failed").write_text(
        json.dumps({"registry_key": "20260510-130000"}), encoding="utf-8"
    )
    bin_path = _install_fake_bin(isolated_project)

    _scan_and_trigger_fail_record({"HOOK_FAIL_RECORD": True})

    assert len(popen_recorder) == 1, (
        f"Popen 1회 호출 기대, 실제: {len(popen_recorder)}건"
    )
    cmd = popen_recorder[0]
    assert cmd[0] == str(bin_path), (
        f"flow-fail-record bin 경로가 cmd[0] 이어야 함: {cmd}"
    )
    assert cmd[1] == "record"
    assert cmd[2] == "20260510-130000"


def test_multiple_workflows_only_failed_ones_dispatch(
    isolated_project, popen_recorder
):
    """다중 워크플로우 중 sentinel 있는 것만 dispatch (idempotency 보존)."""
    # WF1: sentinel 있음 → dispatch
    wf1 = _make_mock_runs(isolated_project, registry_key="20260510-111111")
    (wf1 / ".workflow-failed").write_text(
        json.dumps({"registry_key": "20260510-111111"}), encoding="utf-8"
    )
    # WF2: sentinel 없음 → skip
    _make_mock_runs(isolated_project, registry_key="20260510-222222")
    # WF3: sentinel + recorded → skip
    wf3 = _make_mock_runs(isolated_project, registry_key="20260510-333333")
    (wf3 / ".workflow-failed").write_text("{}", encoding="utf-8")
    (wf3 / ".workflow-failed.recorded").touch()

    _install_fake_bin(isolated_project)

    _scan_and_trigger_fail_record({"HOOK_FAIL_RECORD": True})

    assert len(popen_recorder) == 1
    assert popen_recorder[0][2] == "20260510-111111"


def test_resolve_fail_record_bin_returns_none_when_not_executable(
    isolated_project,
):
    """비실행 파일은 None 으로 처리되어 dispatch skip."""
    bin_dir = isolated_project / ".claude-organic" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    bin_path = bin_dir / "flow-fail-record"
    bin_path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    bin_path.chmod(0o644)  # 실행 권한 없음

    resolved = _subagent_stop_mod._resolve_fail_record_bin()
    assert resolved is None
