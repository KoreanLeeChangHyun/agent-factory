"""Tests for Claude Code hook dispatcher adapter utilities."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

from engine.adapters.hooks import dispatcher


ROOT = Path(__file__).resolve().parents[3]


def test_load_env_flags_parses_hook_settings(tmp_path: Path, monkeypatch) -> None:
    settings_dir = tmp_path / ".agent-factory"
    settings_dir.mkdir()
    (settings_dir / ".settings").write_text(
        "\n".join(
            [
                "HOOK_ENABLED=true",
                "HOOK_DISABLED=0",
                "HOOK_OTHER=off",
                "NOT_A_HOOK=true",
                "HOOK_CUSTOM=value",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(dispatcher, "_find_project_root", lambda: str(tmp_path))

    assert dispatcher.load_env_flags() == {
        "HOOK_ENABLED": True,
        "HOOK_DISABLED": False,
        "HOOK_OTHER": False,
        "HOOK_CUSTOM": True,
    }


def test_is_enabled_defaults_to_true_for_missing_flags() -> None:
    assert dispatcher.is_enabled({}, "HOOK_MISSING") is True
    assert dispatcher.is_enabled({"HOOK_PRESENT": False}, "HOOK_PRESENT") is False


def test_scripts_dir_resolves_under_engine(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(dispatcher, "_find_project_root", lambda: str(tmp_path))

    assert dispatcher.scripts_dir("guards", "example.py") == str(
        tmp_path / ".agent-factory" / "engine" / "guards" / "example.py"
    )


def test_dispatch_skips_disabled_or_missing_script(tmp_path: Path) -> None:
    missing = tmp_path / "missing.py"

    assert dispatcher.dispatch("HOOK_TEST", str(missing), b"{}", flags={"HOOK_TEST": True}) is None
    assert dispatcher.dispatch("HOOK_TEST", str(missing), b"{}", flags={"HOOK_TEST": False}) is None


def test_collect_exit_codes_returns_first_failure() -> None:
    assert dispatcher.collect_exit_codes(
        [
            None,
            subprocess.CompletedProcess(args=["ok"], returncode=0),
            subprocess.CompletedProcess(args=["fail"], returncode=7),
            subprocess.CompletedProcess(args=["later"], returncode=9),
        ]
    ) == 7


def test_hooks_dispatcher_wrapper_exports_adapter_functions() -> None:
    wrapper_path = ROOT / "hooks" / "dispatcher.py"
    spec = importlib.util.spec_from_file_location("hook_dispatcher_wrapper_test", wrapper_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module

    spec.loader.exec_module(module)

    assert module.load_env_flags is dispatcher.load_env_flags
    assert module.scripts_dir is dispatcher.scripts_dir
