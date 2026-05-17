"""test_spawn.py — _spawn.py 단위 테스트.

대상:
  - new_session_uuid (UUID4 형식)
  - logical_session_name 명명 규약
  - spawn_claude cmd 구성 검증 (subprocess.Popen mock)
  - DEFAULT_PERMISSION_MODE 상수
  - SpawnResult dataclass
  - T-495 P1 — stream-json NDJSON line parsing + on_line callback + text 누적
"""

from __future__ import annotations

import io
import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from engine.v2._spawn import (
    DEFAULT_PERMISSION_MODE,
    SpawnResult,
    _extract_assistant_text,
    logical_session_name,
    new_session_uuid,
    spawn_claude,
    spawn_claude_resume,
)


def _make_popen_mock(stdout_lines: list[str], stderr: str = "", returncode: int = 0):
    """subprocess.Popen 의 in-memory mock factory.

    stdout 은 iter-able (readline 루프 호환), stdin 은 dummy, wait 은 returncode.
    """
    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    mock_proc.stdout = io.StringIO("\n".join(stdout_lines) + ("\n" if stdout_lines else ""))
    mock_proc.stderr = io.StringIO(stderr)
    mock_proc.wait = MagicMock(return_value=returncode)
    mock_proc.kill = MagicMock()
    return mock_proc


def test_new_session_uuid_format() -> None:
    sid = new_session_uuid()
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
    name = logical_session_name("T-901", "REPORT")
    assert "-" in name
    assert "T-901" not in name
    assert "T901" in name


def test_default_permission_mode() -> None:
    assert DEFAULT_PERMISSION_MODE == "bypassPermissions"


def test_spawn_claude_cmd_construction(tmp_path: Path) -> None:
    """Popen 호출 시 cmd 가 SPEC §8 + T-495 P1 stream-json 정합."""
    captured_cmd: list[str] = []

    def fake_popen(cmd, **kwargs):
        captured_cmd.extend(cmd)
        return _make_popen_mock(stdout_lines=[], returncode=0)

    with patch("engine.v2._spawn.subprocess.Popen", side_effect=fake_popen):
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
    # T-495 P1 — stream-json + verbose 필수
    assert "--output-format" in captured_cmd
    assert "stream-json" in captured_cmd
    assert "--verbose" in captured_cmd
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

    def fake_popen(cmd, **kwargs):
        captured_cmd.extend(cmd)
        return _make_popen_mock(stdout_lines=[], returncode=0)

    with patch("engine.v2._spawn.subprocess.Popen", side_effect=fake_popen):
        spawn_claude_resume(
            prompt_body="retry",
            session_id="abc-uuid",
            system_prompt="prompt",
            cwd=tmp_path,
            step="PLAN",
        )
    assert "--resume" in captured_cmd
    assert "--session-id" not in captured_cmd


def test_spawn_claude_timeout_captured(tmp_path: Path) -> None:
    """deadline 초과 (monotonic 진행 시 시뮬레이션) → timed_out=True, rc=-1.

    Popen 모드에서 timeout 시뮬레이션은 wait 이 TimeoutExpired 던지게.
    """
    import subprocess

    def fake_popen(cmd, **kwargs):
        proc = _make_popen_mock(stdout_lines=[], returncode=0)
        # wait 이 TimeoutExpired 만들어 spawn 측에서 kill + timed_out 진입
        proc.wait = MagicMock(side_effect=subprocess.TimeoutExpired(cmd=cmd, timeout=1))
        return proc

    with patch("engine.v2._spawn.subprocess.Popen", side_effect=fake_popen):
        result = spawn_claude(
            prompt_body="",
            session_id="x",
            system_prompt="",
            cwd=tmp_path,
            step="PLAN",
        )
    assert result.timed_out
    assert result.returncode == -1


def test_spawn_result_dataclass() -> None:
    r = SpawnResult(returncode=0, stdout="hi", stderr="")
    assert r.returncode == 0
    assert not r.timed_out
    # 신규 필드 default
    assert r.ndjson_lines == []
    assert r.terminal_reason == ""


# ---------------------------------------------------------------------------
# T-495 P1 — stream-json NDJSON line 처리
# ---------------------------------------------------------------------------


def test_extract_assistant_text_joins_blocks() -> None:
    """assistant message.content[].text 만 join."""
    obj = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": "hello "},
                {"type": "tool_use", "input": {}},
                {"type": "text", "text": "world"},
            ]
        },
    }
    assert _extract_assistant_text(obj) == "hello world"


def test_extract_assistant_text_skips_non_assistant() -> None:
    assert _extract_assistant_text({"type": "result", "result": "x"}) == ""
    assert _extract_assistant_text({"type": "system"}) == ""
    assert _extract_assistant_text({}) == ""


def test_spawn_parses_ndjson_lines(tmp_path: Path) -> None:
    """stream-json line 들이 ndjson_lines 에 누적되고 assistant.text 가 stdout 으로."""
    lines = [
        json.dumps({"type": "system", "subtype": "init", "session_id": "s1"}),
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "answer "}
        ]}}),
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "is 42"}
        ]}}),
        json.dumps({"type": "result", "subtype": "success", "result": "answer is 42",
                    "terminal_reason": "completed"}),
    ]

    def fake_popen(cmd, **kwargs):
        return _make_popen_mock(stdout_lines=lines, returncode=0)

    with patch("engine.v2._spawn.subprocess.Popen", side_effect=fake_popen):
        result = spawn_claude(
            prompt_body="q",
            session_id="11111111-2222-3333-4444-555555555555",
            system_prompt="",
            cwd=tmp_path,
            step="PLAN",
        )

    assert result.returncode == 0
    assert result.stdout == "answer is 42"
    assert len(result.ndjson_lines) == 4
    assert result.terminal_reason == "completed"


def test_spawn_on_line_callback_invoked(tmp_path: Path) -> None:
    """on_line(obj) 콜백이 NDJSON line 마다 호출."""
    lines = [
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "x"}
        ]}}),
        json.dumps({"type": "result", "result": "x"}),
    ]
    received: list[dict] = []

    def fake_popen(cmd, **kwargs):
        return _make_popen_mock(stdout_lines=lines, returncode=0)

    with patch("engine.v2._spawn.subprocess.Popen", side_effect=fake_popen):
        spawn_claude(
            prompt_body="",
            session_id="11111111-2222-3333-4444-555555555555",
            system_prompt="",
            cwd=tmp_path,
            step="PLAN",
            on_line=received.append,
        )

    assert len(received) == 2
    assert received[0]["type"] == "assistant"
    assert received[1]["type"] == "result"


def test_spawn_on_line_callback_exception_silent(tmp_path: Path) -> None:
    """on_line 콜백 예외는 silent 흡수 — driver 흐름 영향 0."""
    lines = [
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "y"}
        ]}}),
        json.dumps({"type": "result", "result": "y"}),
    ]
    call_count = {"n": 0}

    def boom(_obj):
        call_count["n"] += 1
        raise RuntimeError("intentional")

    def fake_popen(cmd, **kwargs):
        return _make_popen_mock(stdout_lines=lines, returncode=0)

    with patch("engine.v2._spawn.subprocess.Popen", side_effect=fake_popen):
        result = spawn_claude(
            prompt_body="",
            session_id="11111111-2222-3333-4444-555555555555",
            system_prompt="",
            cwd=tmp_path,
            step="PLAN",
            on_line=boom,
        )

    assert result.returncode == 0
    assert result.stdout == "y"
    # 콜백은 매 line 마다 호출 (2건)
    assert call_count["n"] == 2


def test_spawn_skips_invalid_json_lines(tmp_path: Path) -> None:
    """JSONDecodeError line 은 silent skip (noise 무시)."""
    lines = [
        "garbage non-json line",
        "",
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "ok"}
        ]}}),
        "another noise",
        json.dumps({"type": "result", "result": "ok"}),
    ]

    def fake_popen(cmd, **kwargs):
        return _make_popen_mock(stdout_lines=lines, returncode=0)

    with patch("engine.v2._spawn.subprocess.Popen", side_effect=fake_popen):
        result = spawn_claude(
            prompt_body="",
            session_id="11111111-2222-3333-4444-555555555555",
            system_prompt="",
            cwd=tmp_path,
            step="PLAN",
        )

    assert result.returncode == 0
    assert result.stdout == "ok"
    assert len(result.ndjson_lines) == 2  # garbage 2건 skip
