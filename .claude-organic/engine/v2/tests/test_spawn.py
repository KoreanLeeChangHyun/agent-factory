"""test_spawn.py — _spawn.py 단위 테스트.

대상:
  - new_session_uuid (UUID4 형식)
  - logical_session_name 명명 규약
  - spawn_claude cmd 구성 검증 (subprocess.run mock)
  - DEFAULT_PERMISSION_MODE 상수
  - SpawnResult dataclass
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from engine.v2._spawn import (
    DEFAULT_PERMISSION_MODE,
    SpawnResult,
    logical_session_name,
    new_session_uuid,
    spawn_claude,
    spawn_claude_resume,
)


def test_new_session_uuid_format() -> None:
    sid = new_session_uuid()
    # uuid.UUID 가 파싱 실패 시 ValueError
    parsed = uuid.UUID(sid)
    assert parsed.version == 4


def test_new_session_uuid_unique() -> None:
    ids = {new_session_uuid() for _ in range(100)}
    assert len(ids) == 100  # collision 0


def test_logical_session_name_no_phase() -> None:
    assert logical_session_name("T-489", "PLAN") == "wf-T489-PLAN"
    assert logical_session_name("T-489", "VALIDATE") == "wf-T489-VALIDATE"


def test_logical_session_name_with_phase() -> None:
    assert logical_session_name("T-489", "WORK", "P1") == "wf-T489-WORK-P1"
    assert logical_session_name("T-1", "WORK", "P9") == "wf-T1-WORK-P9"


def test_logical_session_name_strips_dash() -> None:
    # T-489 → T489 (dash 제거)
    name = logical_session_name("T-901", "REPORT")
    assert "-" in name  # wf-T901-REPORT 의 dash
    assert "T-901" not in name
    assert "T901" in name


def test_default_permission_mode() -> None:
    assert DEFAULT_PERMISSION_MODE == "bypassPermissions"


def test_spawn_claude_cmd_construction(tmp_path: Path) -> None:
    """subprocess.run 호출 시 cmd 가 SPEC §8 정합."""
    captured_cmd: list[str] = []
    def fake_run(cmd, **kwargs):
        captured_cmd.extend(cmd)
        return MagicMock(returncode=0, stdout="ok", stderr="")

    with patch("engine.v2._spawn.subprocess.run", side_effect=fake_run):
        result = spawn_claude(
            prompt_body="hi",
            session_id="11111111-2222-3333-4444-555555555555",
            system_prompt="you are PLAN",
            cwd=tmp_path,
            step="PLAN",
        )
    assert result.returncode == 0
    assert captured_cmd[0] == "claude"
    assert captured_cmd[1] == "-p"
    assert "--session-id" in captured_cmd
    assert "11111111-2222-3333-4444-555555555555" in captured_cmd
    assert "--append-system-prompt" in captured_cmd
    assert "you are PLAN" in captured_cmd
    assert "--permission-mode" in captured_cmd
    assert "bypassPermissions" in captured_cmd
    assert "--add-dir" in captured_cmd
    assert str(tmp_path) in captured_cmd


def test_spawn_claude_resume_cmd(tmp_path: Path) -> None:
    """resume=True 시 --session-id 가 아닌 --resume 옵션 사용."""
    captured_cmd: list[str] = []
    def fake_run(cmd, **kwargs):
        captured_cmd.extend(cmd)
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("engine.v2._spawn.subprocess.run", side_effect=fake_run):
        spawn_claude_resume(
            prompt_body="retry",
            session_id="abc-uuid",
            system_prompt="prompt",
            cwd=tmp_path,
            step="PLAN",
        )
    assert "--resume" in captured_cmd
    assert "--session-id" not in captured_cmd


def test_spawn_claude_timeout_captured() -> None:
    """subprocess.TimeoutExpired → SpawnResult(timed_out=True, returncode=-1)."""
    import subprocess
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=1)

    with patch("engine.v2._spawn.subprocess.run", side_effect=fake_run):
        result = spawn_claude(
            prompt_body="",
            session_id="x",
            system_prompt="",
            cwd=Path("/tmp"),
            step="PLAN",
        )
    assert result.timed_out
    assert result.returncode == -1


def test_spawn_result_dataclass() -> None:
    r = SpawnResult(returncode=0, stdout="hi", stderr="")
    assert r.returncode == 0
    assert not r.timed_out
