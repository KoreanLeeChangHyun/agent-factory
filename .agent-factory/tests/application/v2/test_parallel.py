"""test_parallel.py — T-506 P3 + P4.

`engine.v2._parallel.parallel_spawn` 은 같은 level 의 phase / worker 를 동시
실행하는 ThreadPoolExecutor wrapper.

P3: 기본 골격 (성공 / 순서 보존 / max_workers clamp).
P4: fail_fast / fail_tolerant 분기.
"""

from __future__ import annotations

import threading
import time

import pytest

from engine.v2 import _common
from engine.v2._parallel import ParallelOutcome, parallel_spawn


# ---------------- P3 기본 골격 ----------------


def test_parallel_spawn_all_success() -> None:
    """모든 item 성공 — 결과 tuple list 길이 == items 길이."""
    items = [1, 2, 3, 4]
    results = parallel_spawn(items, fn=lambda x: x * 2, max_workers=2)
    assert len(results) == 4
    for r in results:
        assert r.ok is True
        assert r.exception is None


def test_parallel_spawn_preserves_order() -> None:
    """결과 list 가 입력 items 순서 보존."""
    items = ["a", "b", "c", "d"]
    results = parallel_spawn(items, fn=lambda x: x.upper(), max_workers=4)
    assert [r.item for r in results] == items
    assert [r.value for r in results] == ["A", "B", "C", "D"]


def test_parallel_spawn_max_workers_clamp(monkeypatch: pytest.MonkeyPatch) -> None:
    """max_workers 가 get_max_parallel() 보다 크면 clamp."""
    monkeypatch.setattr(_common, "_load_settings", lambda: {})
    monkeypatch.delenv("V2_MAX_PARALLEL", raising=False)  # default 4
    items = list(range(10))
    # max_workers=100 요청 → get_max_parallel()=4 로 clamp. 결과는 모두 처리됨.
    results = parallel_spawn(items, fn=lambda x: x, max_workers=100)
    assert len(results) == 10
    assert all(r.ok for r in results)


def test_parallel_spawn_runs_concurrently() -> None:
    """ThreadPoolExecutor 가 실제 동시 실행 — wall clock 시간 ≪ items × sleep."""
    sleep_s = 0.1

    def slow(x: int) -> int:
        time.sleep(sleep_s)
        return x

    t0 = time.monotonic()
    items = list(range(4))
    results = parallel_spawn(items, fn=slow, max_workers=4)
    elapsed = time.monotonic() - t0
    assert all(r.ok for r in results)
    # 순차였다면 4*0.1=0.4s. 동시 실행이면 ~0.1s. 0.3s 미만 — 여유 충분
    assert elapsed < 0.3, f"elapsed={elapsed:.3f}s — not concurrent"


def test_parallel_spawn_empty_items() -> None:
    """items=[] → 빈 list (no-op)."""
    assert parallel_spawn([], fn=lambda x: x, max_workers=4) == []


# ---------------- P4 fail-policy ----------------


def test_parallel_spawn_fail_tolerant_runs_all() -> None:
    """fail_fast=False — 일부 실패해도 모든 item 끝까지 실행."""
    started: list[int] = []
    lock = threading.Lock()

    def maybe_fail(x: int) -> int:
        with lock:
            started.append(x)
        time.sleep(0.05)
        if x == 1:
            raise ValueError("intentional")
        return x * 10

    items = [0, 1, 2, 3]
    results = parallel_spawn(items, fn=maybe_fail, max_workers=4, fail_fast=False)
    assert len(results) == 4
    by_item = {r.item: r for r in results}
    assert by_item[0].ok is True and by_item[0].value == 0
    assert by_item[1].ok is False
    assert isinstance(by_item[1].exception, ValueError)
    assert by_item[2].ok is True
    assert by_item[3].ok is True
    # 모두 시작됨
    assert set(started) == {0, 1, 2, 3}


def test_parallel_spawn_fail_fast_aborts_pending() -> None:
    """fail_fast=True — 한 item 실패 시 아직 제출 안된 future cancel.

    제출 단위는 ThreadPoolExecutor 의 worker 수. max_workers=1 + 3 items 케이스에서
    첫 item 이 fail → 2, 3 은 cancel 되어 ok=False, exception 은 CancelledError-like 또는
    아예 실행 안 됨.
    """
    started: list[int] = []
    lock = threading.Lock()

    def fail_first(x: int) -> int:
        with lock:
            started.append(x)
        if x == 0:
            raise RuntimeError("first item fails")
        time.sleep(0.5)  # 충분히 길게 — fail_fast 가 cancel 할 시간 확보
        return x

    items = [0, 1, 2]
    t0 = time.monotonic()
    results = parallel_spawn(items, fn=fail_first, max_workers=1, fail_fast=True)
    elapsed = time.monotonic() - t0
    # 결과 list 는 입력 길이 유지 (item, ok, exception) 형태 보존
    assert len(results) == 3
    assert results[0].ok is False
    assert isinstance(results[0].exception, RuntimeError)
    # 나머지는 cancel 또는 not_started — ok=False
    assert results[1].ok is False
    assert results[2].ok is False
    # max_workers=1 이라 첫 item 만 실행됨. 2,3 은 cancel.
    # elapsed 가 0.5s × 3 = 1.5s 보다 훨씬 작아야 (fail_fast 동작 증거)
    assert elapsed < 0.8, f"elapsed={elapsed:.3f}s — fail_fast 동작 안 함"


def test_parallel_spawn_fail_fast_default_true() -> None:
    """fail_fast 명시 안 하면 default True (SPEC §3.4 캐논)."""

    def fail_first(x: int) -> int:
        if x == 0:
            raise RuntimeError("boom")
        time.sleep(0.5)
        return x

    items = [0, 1, 2]
    t0 = time.monotonic()
    results = parallel_spawn(items, fn=fail_first, max_workers=1)
    elapsed = time.monotonic() - t0
    assert results[0].ok is False
    # default fail_fast=True 일 때 빠른 종료
    assert elapsed < 0.8


def test_parallel_outcome_dataclass_shape() -> None:
    """ParallelOutcome — item / ok / value / exception 필드."""
    results = parallel_spawn([42], fn=lambda x: x + 1, max_workers=1)
    r = results[0]
    assert isinstance(r, ParallelOutcome)
    assert r.item == 42
    assert r.ok is True
    assert r.value == 43
    assert r.exception is None


def test_parallel_spawn_max_workers_floor() -> None:
    """max_workers <= 0 이면 1로 clamp (defensive)."""
    items = [1, 2, 3]
    results = parallel_spawn(items, fn=lambda x: x, max_workers=0)
    assert len(results) == 3
    assert all(r.ok for r in results)
