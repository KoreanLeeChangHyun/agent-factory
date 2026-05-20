"""@api endpoint decorator unit testing (T-511 P2).

Warranty:
  1. FAQ importable —  common.py to api endpoint identifier exposure
  debug.log entry / exit when calling decorator application function
  3. FAQs error when an error occurs
  4. functools.wraps Formulation — Signature/Name Conservation
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import types
from typing import Any

import pytest


def _load_common() -> types.ModuleType:
    """Load _common.py directly as a module (avoiding dependency on the board package)."""
    agent_factory_root = Path(__file__).resolve().parents[3]
    common_path = agent_factory_root / "board" / "server" / "_common.py"
    spec = importlib.util.spec_from_file_location("board_server_common_under_test", common_path)
    assert spec is not None, f"spec_from_file_location failed for {common_path}"
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def common_mod(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """common module loaded inside cwd.

    Move cwd to tmp path and turn on the .agent-factory/runs/bg/debug.enabled flag.
    """
    bg = tmp_path / ".agent-factory" / "runs" / "bg"
    bg.mkdir(parents=True, exist_ok=True)
    (bg / "debug.enabled").write_text("")
    monkeypatch.chdir(tmp_path)
    mod = _load_common()
    return mod, tmp_path


def _read_debug_lines(tmp_path) -> list[dict[str, Any]]:
    path = tmp_path / ".agent-factory" / "runs" / "bg" / "debug.log"
    if not path.exists():
        return []
    lines: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            lines.append(json.loads(line))
        except json.JSONDecodeError:
            pytest.fail(f"debug.log line NDJSON parsing failed: {line!r}")
    return lines


def test_api_endpoint_is_importable(common_mod):
    """AC: hasattr(_common, 'api_endpoint')."""
    mod, _ = common_mod
    assert hasattr(mod, "api_endpoint"), "No api_endpoint identifier in _common.py"


def test_api_endpoint_decorator_emits_entry_and_exit(common_mod):
    """Call decorator application function → entry + exit two lines NDJSON utterance."""
    mod, tmp_path = common_mod

    @mod.api_endpoint("K", "test_ok")
    def handler(_self: Any) -> str:
        return "ok"

    handler(object())
    lines = _read_debug_lines(tmp_path)
    tags = [line.get("tag") for line in lines]
    assert any(t == "server.api.K.test_ok.entry" for t in tags), tags
    assert any(t == "server.api.K.test_ok.exit" for t in tags), tags


def test_api_endpoint_decorator_emits_error_on_exception(common_mod):
    """When an exception occurs, an error line is fired + the exception occurs again."""
    mod, tmp_path = common_mod

    @mod.api_endpoint("M", "save")
    def boom(_self: Any) -> None:
        raise RuntimeError("boom payload")

    with pytest.raises(RuntimeError, match="boom payload"):
        boom(object())

    lines = _read_debug_lines(tmp_path)
    tags = [line.get("tag") for line in lines]
    assert any(t == "server.api.M.save.entry" for t in tags), tags
    assert any(t == "server.api.M.save.error" for t in tags), tags


def test_api_endpoint_wraps_preserves_name_and_signature(common_mod):
    """functools.wraps Qualification — Preserve __name__ + __qualname__ + __doc__."""
    mod, _ = common_mod

    @mod.api_endpoint("W2", "delete")
    def original_handler(_self: Any) -> str:
        """Original docstring."""
        return "deleted"

    assert original_handler.__name__ == "original_handler"
    assert original_handler.__doc__ == "Original docstring."


def test_api_endpoint_no_op_when_debug_disabled(monkeypatch, tmp_path):
    """In the absence of the debug.enabled flag, do not append debug.log (block overhead)."""
    bg = tmp_path / ".agent-factory" / "runs" / "bg"
    bg.mkdir(parents=True, exist_ok=True)
    # debug.enabled intentionally not created
    monkeypatch.chdir(tmp_path)
    mod = _load_common()

    @mod.api_endpoint("T", "start")
    def handler(_self: Any) -> str:
        return "ok"

    handler(object())
    log = bg / "debug.log"
    assert not log.exists() or log.read_text() == "", "Logs are generated when debug.enabled is not present"
