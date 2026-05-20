"""test subagent stop sentinel.py — subagent-stop.py sentinel detection module testing (T-455 W06).

This test validates plan.md §9 Case 4 NEWS
  - Call flow-fail-record only when setting HOOK FAIL RECORD=true environment variable
  - .workflow-failed sentinel call 0
  - 0 calls when .workflow-failed.recorded markers exist
  - call factor + number verification with subprocess.Popen mock

importlib.util loads `subagent-stop.py` directly — because the filename is high
Normal import is impossible. hooks/ directory for dispatcher dependencies
sys.path
"""
from __future__ import annotations

import importlib.util as _ilu
import json
import os
import sys
from pathlib import Path

import pytest

# sys.path Warranty — hooks/ + engine/ registration
_TEST_DIR = Path(__file__).resolve().parent
_AGENT_FACTORY_ROOT = _TEST_DIR.parents[2]
_ENGINE_DIR = _AGENT_FACTORY_ROOT / "engine"
_PROJECT_ROOT = _AGENT_FACTORY_ROOT.parent  # workspace/claude
_HOOKS_DIR = _AGENT_FACTORY_ROOT / "hooks"  # .agent-factory/hooks/

if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_SUBAGENT_STOP_PATH = _HOOKS_DIR / "subagent-stop.py"
assert _SUBAGENT_STOP_PATH.exists(), (
    f"subagent-stop.py must exist:   FIELD 0  "
)

_spec = _ilu.spec_from_file_location("subagent_stop_module", _SUBAGENT_STOP_PATH)
_subagent_stop_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_subagent_stop_mod)

_scan_and_trigger_fail_record = _subagent_stop_mod._scan_and_trigger_fail_record


# =============================================================================
# Create a mock workflow (scan active workflows to discover)
# =============================================================================


def _make_mock_runs(project_root: Path, registry_key: str = "20260510-123456") -> Path:
    """<project root>/.agent-factory/runs/<registry key>/

    scan active workflows() read status.json at least status.json
    Write. step is set to active phase (e.g. WORK).
    """
    runs_dir = project_root / ".agent-factory" / "runs" / registry_key
    runs_dir.mkdir(parents=True, exist_ok=True)
    status = {
        "step": "WORK",
        "phase": "WORK",
        "registryKey": registry_key,
        "workDir": f".agent-factory/runs/{registry_key}",
    }
    (runs_dir / "status.json").write_text(
        json.dumps(status, ensure_ascii=False), encoding="utf-8"
    )
    return runs_dir


def _install_fake_bin(project_root: Path) -> Path:
    """`.agent-factory/bin/flow-fail-record` generates a stack that can be executed.

    ` resolve fail record bin()' This executable file exist + access(X OK)
    Set up to chmod +x
    """
    bin_dir = project_root / ".agent-factory" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    bin_path = bin_dir / "flow-fail-record"
    bin_path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    bin_path.chmod(0o755)
    return bin_path


@pytest.fixture
def isolated_project(tmp_path, monkeypatch):
    """Created fake project root and binding with CLAUDE PROJECT DIR.

    ` resolve fail record bin()` This CLAUDE PROJECT DIR environment variable is first checked
    This forces hooks module to see fake root.
    """
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    # scan active workflows call resolve project root, so it also patches with fake root
    import common  # noqa: PLC0415

    monkeypatch.setattr(common, "resolve_project_root", lambda: str(tmp_path))

    # . agent-factory/.settings should be some helper is successful (for free but safe)
    settings_dir = tmp_path / ".agent-factory"
    settings_dir.mkdir(parents=True, exist_ok=True)
    (settings_dir / ".settings").write_text("", encoding="utf-8")

    return tmp_path


@pytest.fixture
def popen_recorder(monkeypatch):
    """fixture to record subprocess.Popen calls."""
    calls: list[list[str]] = []

    class _MockProc:
        pid = 12345

        def __init__(self, *a, **kw):
            pass

    def _fake_popen(cmd, *args, **kwargs):
        calls.append(list(cmd))
        return _MockProc()

    # subagent-stop module is called subprocess.Popen(...)
    monkeypatch.setattr(_subagent_stop_mod.subprocess, "Popen", _fake_popen)
    return calls


# =============================================================================
# T/T
# =============================================================================


def test_no_call_when_flag_disabled(isolated_project, popen_recorder):
    """0 Popen calls when HOOK FAIL RECORD inactive (False)."""
    runs_dir = _make_mock_runs(isolated_project)
    (runs_dir / ".workflow-failed").write_text(
        json.dumps({"registry_key": "20260510-123456"}), encoding="utf-8"
    )
    _install_fake_bin(isolated_project)

    _scan_and_trigger_fail_record({"HOOK_FAIL_RECORD": False})

    assert popen_recorder == []


def test_no_call_when_flag_missing(isolated_project, popen_recorder):
    """flag dict has no key itself (default False) Popen call 0."""
    runs_dir = _make_mock_runs(isolated_project)
    (runs_dir / ".workflow-failed").write_text("{}", encoding="utf-8")
    _install_fake_bin(isolated_project)

    _scan_and_trigger_fail_record({})  # HOOK FAIL RECORD Keyless

    assert popen_recorder == []


def test_no_call_when_sentinel_absent(isolated_project, popen_recorder):
    """0 Popen calls when sentinel is broken."""
    _make_mock_runs(isolated_project)  # status.json
    _install_fake_bin(isolated_project)

    _scan_and_trigger_fail_record({"HOOK_FAIL_RECORD": True})

    assert popen_recorder == []


def test_no_call_when_recorded_marker_exists(isolated_project, popen_recorder):
    """. popen call 0 if workflow-failed.recorded marker already."""
    runs_dir = _make_mock_runs(isolated_project)
    (runs_dir / ".workflow-failed").write_text("{}", encoding="utf-8")
    (runs_dir / ".workflow-failed.recorded").touch()
    _install_fake_bin(isolated_project)

    _scan_and_trigger_fail_record({"HOOK_FAIL_RECORD": True})

    assert popen_recorder == []


def test_no_call_when_bin_missing(isolated_project, popen_recorder):
    """0 Popen calls for the flow-fail-record executable."""
    runs_dir = _make_mock_runs(isolated_project)
    (runs_dir / ".workflow-failed").write_text("{}", encoding="utf-8")
    # install fake bin Unsubscribe — Unsubscribe

    _scan_and_trigger_fail_record({"HOOK_FAIL_RECORD": True})

    assert popen_recorder == []


def test_call_dispatched_when_all_conditions_met(isolated_project, popen_recorder):
    """The flow-fail-record non-blocking Popen calls are encountered when all conditions are met."""
    runs_dir = _make_mock_runs(isolated_project, registry_key="20260510-130000")
    (runs_dir / ".workflow-failed").write_text(
        json.dumps({"registry_key": "20260510-130000"}), encoding="utf-8"
    )
    bin_path = _install_fake_bin(isolated_project)

    _scan_and_trigger_fail_record({"HOOK_FAIL_RECORD": True})

    assert len(popen_recorder) == 1, (
        f"Popen 1 call expectations, actual:   FIELD 0 "
    )
    cmd = popen_recorder[0]
    assert cmd[0] == str(bin_path), (
        f"The flow-fail-record bin path should be cmd[0]:   FIELD 0  "
    )
    assert cmd[1] == "record"
    assert cmd[2] == "20260510-130000"


def test_multiple_workflows_only_failed_ones_dispatch(
    isolated_project, popen_recorder
):
    """Only dispatches sentinel during multiple workflows (preserving idempotency)."""
    # WF1: sentinel available → dispatch
    wf1 = _make_mock_runs(isolated_project, registry_key="20260510-111111")
    (wf1 / ".workflow-failed").write_text(
        json.dumps({"registry_key": "20260510-111111"}), encoding="utf-8"
    )
    # WF2: No sendinel → skip
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
    """Undisabled files are processed by None and dispatch skip."""
    bin_dir = isolated_project / ".agent-factory" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    bin_path = bin_dir / "flow-fail-record"
    bin_path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    bin_path.chmod(0o644)  # No license

    resolved = _subagent_stop_mod._resolve_fail_record_bin()
    assert resolved is None
