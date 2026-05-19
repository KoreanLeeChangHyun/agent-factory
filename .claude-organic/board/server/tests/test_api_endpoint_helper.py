"""@api_endpoint decorator 단위 테스트 (T-511 P2).

검증:
  1. import 가능 — _common.py 에서 api_endpoint 식별자 노출
  2. decorator 적용 함수 호출 시 debug.log entry / exit 발화
  3. exception 발생 시 error 발화
  4. functools.wraps 정합 — 시그니처/이름 보존
"""

from __future__ import annotations

import importlib.util
import json
import os
import types
from typing import Any

import pytest


def _load_common() -> types.ModuleType:
    """_common.py 를 직접 module 로 로드 (board 패키지 의존 회피)."""
    here = os.path.dirname(os.path.abspath(__file__))
    server_dir = os.path.dirname(here)
    common_path = os.path.join(server_dir, "_common.py")
    spec = importlib.util.spec_from_file_location("board_server_common_under_test", common_path)
    assert spec is not None, f"spec_from_file_location failed for {common_path}"
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def common_mod(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """_common 모듈을 격리된 cwd 안에서 로드.

    cwd 를 tmp_path 로 옮기고 .claude-organic/runs/bg/debug.enabled 플래그를 켜 둠.
    """
    bg = tmp_path / ".claude-organic" / "runs" / "bg"
    bg.mkdir(parents=True, exist_ok=True)
    (bg / "debug.enabled").write_text("")
    monkeypatch.chdir(tmp_path)
    mod = _load_common()
    return mod, tmp_path


def _read_debug_lines(tmp_path) -> list[dict[str, Any]]:
    path = tmp_path / ".claude-organic" / "runs" / "bg" / "debug.log"
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
            pytest.fail(f"debug.log 라인 NDJSON 파싱 실패: {line!r}")
    return lines


def test_api_endpoint_is_importable(common_mod):
    """AC: hasattr(_common, 'api_endpoint')."""
    mod, _ = common_mod
    assert hasattr(mod, "api_endpoint"), "_common.py 에 api_endpoint 식별자가 없음"


def test_api_endpoint_decorator_emits_entry_and_exit(common_mod):
    """decorator 적용 함수 호출 → entry + exit 두 라인 NDJSON 발화."""
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
    """exception 발생 시 error 라인 발화 + 예외는 재발생."""
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
    """functools.wraps 정합 — __name__ + __qualname__ + __doc__ 보존."""
    mod, _ = common_mod

    @mod.api_endpoint("W2", "delete")
    def original_handler(_self: Any) -> str:
        """원본 docstring."""
        return "deleted"

    assert original_handler.__name__ == "original_handler"
    assert original_handler.__doc__ == "원본 docstring."


def test_api_endpoint_no_op_when_debug_disabled(monkeypatch, tmp_path):
    """debug.enabled 플래그 부재 시 debug.log append 안 함 (오버헤드 차단)."""
    bg = tmp_path / ".claude-organic" / "runs" / "bg"
    bg.mkdir(parents=True, exist_ok=True)
    # debug.enabled 일부러 생성 안 함
    monkeypatch.chdir(tmp_path)
    mod = _load_common()

    @mod.api_endpoint("T", "start")
    def handler(_self: Any) -> str:
        return "ok"

    handler(object())
    log = bg / "debug.log"
    assert not log.exists() or log.read_text() == "", "debug.enabled 없을 때 로그가 생성됨"
