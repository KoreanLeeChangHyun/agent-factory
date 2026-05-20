"""test_parallel.py — T-506 P3 + P4.

`engine.apps.production line. parallel.parallel spawn` simultaneous level of phase/worker
threadPoolExecutor wrapper

P3: Basic skeleton (permanent / sequence preservation / max workers clamp).
P4: fail fast / fail tolerant branch.
"""

from __future__ import annotations

import threading
import time

import pytest

from engine.apps.production_line import _common
from engine.apps.production_line._parallel import ParallelOutcome, parallel_spawn


# ---------------- P3 Basic skeleton ----------------


def test_parallel_spawn_all_success() -> None:
    """All item success — result tuple list length == item length."""
    items = [1, 2, 3, 4]
    results = parallel_spawn(items, fn=lambda x: x * 2, max_workers=2)
    assert len(results) == 4
    for r in results:
        assert r.ok is True
        assert r.exception is None


def test_parallel_spawn_preserves_order() -> None:
    """The result list is input items to preserve the order."""
    items = ["a", "b", "c", "d"]
    results = parallel_spawn(items, fn=lambda x: x.upper(), max_workers=4)
    assert [r.item for r in results] == items
    assert [r.value for r in results] == ["A", "B", "C", "D"]


def test_parallel_spawn_max_workers_clamp(monkeypatch: pytest.MonkeyPatch) -> None:
    """get max parallel()"""
    monkeypatch.setattr(_common, "_load_settings", lambda: {})
    monkeypatch.delenv("V2_MAX_PARALLEL", raising=False)  # default 4
    items = list(range(10))
    # max workers=100 request → get max parallel()=4 clamp. All results are processed.
    results = parallel_spawn(items, fn=lambda x: x, max_workers=100)
    assert len(results) == 10
    assert all(r.ok for r in results)


def test_parallel_spawn_runs_concurrently() -> None:
    """ThreadPoolExecutor runs real simultaneous — wall clock time ≪ items × sleep."""
    sleep_s = 0.1

    def slow(x: int) -> int:
        time.sleep(sleep_s)
        return x

    t0 = time.monotonic()
    items = list(range(4))
    results = parallel_spawn(items, fn=slow, max_workers=4)
    elapsed = time.monotonic() - t0
    assert all(r.ok for r in results)
    # 4*0.1=0.4s -0.1s. Less than 0.3s — Free
    assert elapsed < 0.3, f"elapsed={elapsed:.3f}s — not concurrent"


def test_parallel_spawn_empty_items() -> None:
    """list(no-op)"""
    assert parallel_spawn([], fn=lambda x: x, max_workers=4) == []


# ---------------- P4 fail-policy ----------------


def test_parallel_spawn_fail_tolerant_runs_all() -> None:
    """fail fast=False — run until all item ends even if some failed."""
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
    # Get started
    assert set(started) == {0, 1, 2, 3}


def test_parallel_spawn_fail_fast_aborts_pending() -> None:
    """fail fast=True — the future cancel not yet submitted when one item failed.

    The submission unit can worker of threadPoolExecutor. max workers=1 + 3 items in case
    ok=False, exception
    Not run.
    """
    started: list[int] = []
    lock = threading.Lock()

    def fail_first(x: int) -> int:
        with lock:
            started.append(x)
        if x == 0:
            raise RuntimeError("first item fails")
        time.sleep(0.5)  # long enough — fail fast has time to cancel
        return x

    items = [0, 1, 2]
    t0 = time.monotonic()
    results = parallel_spawn(items, fn=fail_first, max_workers=1, fail_fast=True)
    elapsed = time.monotonic() - t0
    # Results list retains input length (item, ok, exception) form
    assert len(results) == 3
    assert results[0].ok is False
    assert isinstance(results[0].exception, RuntimeError)
    # ok=False
    assert results[1].ok is False
    assert results[2].ok is False
    # max workers=1 . 2,3 BIT.
    # elapsed is much smaller than 0.5s × 3 = 1.5s (fail fast action proof)
    assert elapsed < 0.8, f"elapsed=   FIELD 0   s — fail fast"


def test_parallel_spawn_fail_fast_default_true() -> None:
    """default True (SPEC §3.4 canon) if fail fast is not specified."""

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
    # default fail fast=True
    assert elapsed < 0.8


def test_parallel_outcome_dataclass_shape() -> None:
    """ParallelOutcome — item / ok / value / exception field."""
    results = parallel_spawn([42], fn=lambda x: x + 1, max_workers=1)
    r = results[0]
    assert isinstance(r, ParallelOutcome)
    assert r.item == 42
    assert r.ok is True
    assert r.value == 43
    assert r.exception is None


def test_parallel_spawn_max_workers_floor() -> None:
    """max workers <= 0 Clamp(dSchool)."""
    items = [1, 2, 3]
    results = parallel_spawn(items, fn=lambda x: x, max_workers=0)
    assert len(results) == 3
    assert all(r.ok for r in results)
