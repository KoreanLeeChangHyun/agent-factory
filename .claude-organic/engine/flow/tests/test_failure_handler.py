"""test_failure_handler.py — failure_handler.py 단위 테스트 (T-455 W06).

본 테스트 모듈은 plan.md §9 "4축 (Criteria 검증) 매핑" 의 5개 검증 케이스
중 4개 (① 5개 환경변수 phase별 동작 / ② sentinel idempotency / ③
retry-context.json 5필드 누적 / ⑤ failure_handler ↔ finalization 책임 분리)
를 커버한다. 케이스 ④ (subagent-stop.py sentinel 감지 + flow-fail-record
호출) 는 자매 모듈 `test_subagent_stop_sentinel.py` 가 검증한다.

테스트 격리:
  - tmp_path fixture 로 매 테스트마다 독립 workDir 사용.
  - PHASE_RETRY_MAX 는 모듈 로드 시 환경변수에서 스냅샷되므로 monkeypatch 로
    환경변수가 아닌 dict 자체를 직접 패치한다 (`monkeypatch.setitem`).
  - WORKFLOW_RETRY_PROMPT_N 는 failure_handler 모듈이 import 시점에 캐시한
    값을 사용하므로 `monkeypatch.setattr` 로 모듈 속성 직접 교체.
"""
from __future__ import annotations

import ast
import json
import os
import sys
import time
from pathlib import Path

import pytest

# sys.path 보장 — engine/ 디렉터리를 등록하여 flow.failure_handler 와 constants 를 import 가능하게 한다.
_TEST_DIR = Path(__file__).resolve().parent
_FLOW_DIR = _TEST_DIR.parent
_ENGINE_DIR = _FLOW_DIR.parent
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

import constants  # noqa: E402
from flow import failure_handler as fh  # noqa: E402
from flow.failure_handler import (  # noqa: E402
    LAST_ERROR_MAX_BYTES,
    RETRY_CONTEXT_FILENAME,
    RetryContext,
    SENTINEL_FILENAME,
    SENTINEL_RECORDED_FILENAME,
    create_sentinel,
    is_retry_available,
    load_retry_context,
    record_failure,
    update_retry_context,
)


# =============================================================================
# Case ① — 5개 환경변수 phase별 동작 (10 시나리오)
# =============================================================================


@pytest.fixture
def patched_phase_max(monkeypatch):
    """PHASE_RETRY_MAX 를 테스트 격리된 dict 로 교체.

    환경변수는 module import 시점에 스냅샷되므로 setenv 만으로는 효과 없음.
    constants.PHASE_RETRY_MAX 는 dict 이므로 setitem 으로 키 단위 패치 가능.
    """

    def _patch(values: dict[str, int]) -> None:
        for phase, val in values.items():
            monkeypatch.setitem(constants.PHASE_RETRY_MAX, phase, val)

    return _patch


@pytest.mark.parametrize(
    "phase",
    ["INIT", "PLAN", "WORK", "VALIDATE", "REPORT"],
)
def test_is_retry_available_returns_true_when_under_max(
    tmp_path, patched_phase_max, phase
):
    """각 phase 별로 retry_count < max 일 때 True 반환 (5 phase × 1 케이스)."""
    patched_phase_max({phase: 2})
    # 첫 시도 — retry-context 없음 → True (max>=1)
    assert is_retry_available(tmp_path, phase) is True


@pytest.mark.parametrize(
    "phase",
    ["INIT", "PLAN", "WORK", "VALIDATE", "REPORT"],
)
def test_is_retry_available_returns_false_when_disabled(
    tmp_path, patched_phase_max, phase
):
    """각 phase 별로 환경변수 0 (기본) 시 항상 False (5 phase × 1 케이스)."""
    patched_phase_max({phase: 0})
    assert is_retry_available(tmp_path, phase) is False


def test_is_retry_available_false_when_count_at_max(tmp_path, patched_phase_max):
    """retry_count >= max 일 때 False 반환.

    누적 규칙 (failure_handler 구현):
      - 1차 호출: existing 없음 → phase 미일치 분기 → new_count=0 (첫 진입 마커)
      - 2차 호출: existing.phase=="WORK" 일치 → new_count = 0+1 = 1
      - 3차 호출: existing.phase=="WORK" 일치 → new_count = 1+1 = 2

    따라서 max=2 에 도달하려면 3회 호출이 필요하다.
    """
    patched_phase_max({"WORK": 2})
    update_retry_context(tmp_path, "WORK", "first error")
    update_retry_context(tmp_path, "WORK", "second error")
    update_retry_context(tmp_path, "WORK", "third error")
    ctx = load_retry_context(tmp_path)
    assert ctx is not None
    assert ctx.retry_count == 2
    assert is_retry_available(tmp_path, "WORK") is False


def test_is_retry_available_unknown_phase_returns_false(tmp_path, patched_phase_max):
    """알 수 없는 phase 명은 False (안전한 기본)."""
    patched_phase_max({"WORK": 5})
    assert is_retry_available(tmp_path, "UNKNOWN") is False
    assert is_retry_available(tmp_path, "") is False


# =============================================================================
# Case ② — sentinel + recorded 마커 idempotency
# =============================================================================


def test_create_sentinel_idempotent_same_registry_key(tmp_path):
    """같은 registry_key 로 2회 호출해도 sentinel 파일 1개만."""
    sentinel_path = create_sentinel(
        tmp_path, "20260510-test", phase="WORK", error="first"
    )
    assert sentinel_path.exists()
    first_payload = json.loads(sentinel_path.read_text(encoding="utf-8").strip())
    assert first_payload["registry_key"] == "20260510-test"

    # 2회째 호출 — 덮어쓰기 OK, 파일은 여전히 1개
    create_sentinel(tmp_path, "20260510-test", phase="WORK", error="second")
    files = list(tmp_path.iterdir())
    sentinels = [p for p in files if p.name == SENTINEL_FILENAME]
    assert len(sentinels) == 1
    second_payload = json.loads(sentinel_path.read_text(encoding="utf-8").strip())
    # error 필드는 두 번째 호출 값으로 덮어써져야 함
    assert second_payload["error"] == "second"


def test_record_failure_creates_recorded_marker(tmp_path):
    """record_failure() 가 .workflow-failed.recorded 마커를 생성."""
    record_failure(tmp_path, phase="WORK", error="oops")
    recorded = tmp_path / SENTINEL_RECORDED_FILENAME
    assert recorded.exists(), "recorded 마커가 생성되어야 함"


def test_record_failure_idempotent_marker_does_not_recreate(tmp_path):
    """recorded 마커가 이미 존재해도 record_failure 재호출이 안전.

    검증: recorded 파일의 mtime 이 갱신되지만 파일은 1개 유지.
    """
    record_failure(tmp_path, phase="WORK", error="first")
    recorded = tmp_path / SENTINEL_RECORDED_FILENAME
    assert recorded.exists()
    first_mtime = recorded.stat().st_mtime

    # mtime 분해능 확보를 위해 짧게 대기
    time.sleep(0.01)
    record_failure(tmp_path, phase="WORK", error="second")

    # 파일은 여전히 1개
    recorded_files = [p for p in tmp_path.iterdir() if p.name == SENTINEL_RECORDED_FILENAME]
    assert len(recorded_files) == 1
    # mtime touch 발생 — 갱신되었거나 동일 (시스템 분해능에 따라)
    assert recorded.stat().st_mtime >= first_mtime


# =============================================================================
# Case ③ — retry-context.json 5필드 누적
# =============================================================================


def test_retry_count_accumulates_same_phase(tmp_path):
    """같은 phase 3회 호출 → retry_count 0 → 1 → 2 누적."""
    update_retry_context(tmp_path, "WORK", "err1")
    ctx1 = load_retry_context(tmp_path)
    assert ctx1 is not None and ctx1.retry_count == 0

    update_retry_context(tmp_path, "WORK", "err2")
    ctx2 = load_retry_context(tmp_path)
    assert ctx2 is not None and ctx2.retry_count == 1

    update_retry_context(tmp_path, "WORK", "err3")
    ctx3 = load_retry_context(tmp_path)
    assert ctx3 is not None and ctx3.retry_count == 2


def test_retry_count_resets_on_phase_change(tmp_path):
    """phase 변경 시 retry_count 가 0 으로 reset."""
    update_retry_context(tmp_path, "WORK", "work-err1")
    update_retry_context(tmp_path, "WORK", "work-err2")
    ctx = load_retry_context(tmp_path)
    assert ctx is not None and ctx.retry_count == 1

    # phase 변경
    update_retry_context(tmp_path, "PLAN", "plan-err")
    ctx2 = load_retry_context(tmp_path)
    assert ctx2 is not None
    assert ctx2.phase == "PLAN"
    assert ctx2.retry_count == 0


def test_hint_history_accumulates_with_cap(tmp_path, monkeypatch):
    """cap=3 환경에서 4번째 hint 추가 시 가장 오래된 항목 제거 (FIFO)."""
    monkeypatch.setattr(fh, "WORKFLOW_RETRY_PROMPT_N", 3)

    update_retry_context(tmp_path, "WORK", "e1", hint="hint-1")
    update_retry_context(tmp_path, "WORK", "e2", hint="hint-2")
    update_retry_context(tmp_path, "WORK", "e3", hint="hint-3")
    ctx = load_retry_context(tmp_path)
    assert ctx is not None
    assert ctx.hint_history == ["hint-1", "hint-2", "hint-3"]

    # 4번째 hint → 가장 오래된 hint-1 이 pop
    update_retry_context(tmp_path, "WORK", "e4", hint="hint-4")
    ctx2 = load_retry_context(tmp_path)
    assert ctx2 is not None
    assert ctx2.hint_history == ["hint-2", "hint-3", "hint-4"]


def test_hint_history_skips_empty_hint(tmp_path, monkeypatch):
    """빈 hint / None 은 hint_history 에 append 안 함."""
    monkeypatch.setattr(fh, "WORKFLOW_RETRY_PROMPT_N", 3)
    update_retry_context(tmp_path, "WORK", "err", hint=None)
    update_retry_context(tmp_path, "WORK", "err", hint="")
    update_retry_context(tmp_path, "WORK", "err", hint="   ")
    ctx = load_retry_context(tmp_path)
    assert ctx is not None
    assert ctx.hint_history == []


def test_last_error_truncated_to_4kb(tmp_path):
    """last_error 가 4097 chars 입력 시 4096 bytes 로 truncate."""
    long_error = "a" * 4097
    update_retry_context(tmp_path, "WORK", long_error)
    ctx = load_retry_context(tmp_path)
    assert ctx is not None
    encoded = ctx.last_error.encode("utf-8")
    assert len(encoded) <= LAST_ERROR_MAX_BYTES
    # ASCII 'a' 만 있으므로 정확히 4096 chars
    assert len(ctx.last_error) == 4096


def test_last_attempt_at_iso8601_kst(tmp_path):
    """last_attempt_at 이 ISO 8601 KST (`+09:00`) 패턴."""
    import re

    update_retry_context(tmp_path, "WORK", "err")
    ctx = load_retry_context(tmp_path)
    assert ctx is not None
    # YYYY-MM-DDTHH:MM:SS+09:00
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+09:00$")
    assert pattern.match(ctx.last_attempt_at), (
        f"unexpected timestamp format: {ctx.last_attempt_at!r}"
    )


def test_retry_context_all_five_fields_persisted(tmp_path):
    """5필드 (phase, retry_count, last_error, last_attempt_at, hint_history)
    이 모두 retry-context.json 에 영속화된다."""
    update_retry_context(tmp_path, "WORK", "err", hint="h1")
    ctx_path = tmp_path / RETRY_CONTEXT_FILENAME
    assert ctx_path.exists()
    raw = json.loads(ctx_path.read_text(encoding="utf-8"))
    assert set(raw.keys()) >= {
        "phase",
        "retry_count",
        "last_error",
        "last_attempt_at",
        "hint_history",
    }


# =============================================================================
# Case ⑤ — failure_handler ↔ finalization 책임 분리 (정적 분석)
# =============================================================================


def test_finalization_does_not_import_failure_handler():
    """finalization.py 가 failure_handler 를 import 하지 않음을 정적 분석 검증.

    책임 분리 캐논: failure_handler.py 는 단계별 실패 처리, finalization.py 는
    종결 책임. finalization 이 failure_handler 를 import 하면 책임 흡수가
    발생한 것이므로 차단한다.
    """
    finalization_path = _FLOW_DIR / "finalization.py"
    assert finalization_path.exists(), "finalization.py 가 존재해야 함"
    src = finalization_path.read_text(encoding="utf-8")
    tree = ast.parse(src)

    bad_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "failure_handler" in (alias.name or ""):
                    bad_imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if "failure_handler" in module:
                names = ", ".join(a.name for a in node.names)
                bad_imports.append(f"from {module} import {names}")

    assert not bad_imports, (
        "finalization.py 가 failure_handler 를 import 함 (책임 흡수 위반): "
        f"{bad_imports}"
    )


def test_failure_handler_does_not_import_finalization():
    """역방향 책임 분리: failure_handler.py 가 finalization 을 import 안 함."""
    fh_path = _FLOW_DIR / "failure_handler.py"
    assert fh_path.exists()
    src = fh_path.read_text(encoding="utf-8")
    tree = ast.parse(src)

    bad_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "finalization" in (alias.name or ""):
                    bad_imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if "finalization" in module:
                names = ", ".join(a.name for a in node.names)
                bad_imports.append(f"from {module} import {names}")

    assert not bad_imports, (
        "failure_handler.py 가 finalization 을 import 함 (역방향 흡수 위반): "
        f"{bad_imports}"
    )


# =============================================================================
# 보조 — RetryContext dataclass 단위 검증
# =============================================================================


def test_retry_context_from_dict_handles_missing_fields():
    """from_dict 가 필드 누락에도 graceful 하게 동작."""
    ctx = RetryContext.from_dict({})
    assert ctx.phase == ""
    assert ctx.retry_count == 0
    assert ctx.last_error == ""
    assert ctx.last_attempt_at == ""
    assert ctx.hint_history == []


def test_retry_context_from_dict_rejects_non_dict():
    """from_dict 가 non-dict 입력에도 graceful 하게 동작."""
    ctx = RetryContext.from_dict(None)  # type: ignore[arg-type]
    assert ctx.phase == ""
    ctx2 = RetryContext.from_dict([1, 2, 3])  # type: ignore[arg-type]
    assert ctx2.retry_count == 0
