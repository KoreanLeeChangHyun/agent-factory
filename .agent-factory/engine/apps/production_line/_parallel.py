"""v2 parallel — T-506 P3/P4. ThreadPoolExecutor 기반 동시 spawn 인프라.

SPEC.md §3.4 + §6.5 (T-506 추가).

driver 가 같은 topo level 의 phase 들 / 같은 phase 안 workers>1 일 때
worker 들을 동시 spawn 하는 wrapper. LLM 호출 X — 결정론 인프라.

핵심:
- ThreadPoolExecutor (asyncio 미채택, T-506 plan §캐논 SSOT 결정)
- max_workers 는 get_max_parallel() 가드로 clamp
- fail_fast=True (default): 한 item 실패 시 미시작 future 들 cancel
- fail_fast=False: 모든 item 끝까지 실행 후 결과 집계
- 결과 list 는 입력 items 순서 보존 (deterministic)
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from ._common import get_max_parallel


@dataclass
class ParallelOutcome:
    """parallel_spawn 한 item 의 결과.

    Attributes:
        item: 입력 item (예: Phase 객체, int, str ...)
        ok: 호출 성공 여부
        value: fn(item) 반환값 (실패 시 None)
        exception: 실패 시 raise 된 예외 (성공 시 None). fail_fast 가 cancel 한
                   future 는 CancelledError 또는 None.
    """

    item: Any
    ok: bool
    value: Any = None
    exception: BaseException | None = None


def parallel_spawn(
    items: Iterable[Any],
    *,
    fn: Callable[[Any], Any],
    max_workers: int,
    fail_fast: bool = True,
) -> list[ParallelOutcome]:
    """같은 level 의 items 를 ThreadPoolExecutor 로 동시 실행.

    Args:
        items: 처리할 item 리스트 (Phase / worker 등). order 보존.
        fn: 1 item → 결과값 함수. 예외 raise 시 outcome.ok=False.
        max_workers: 동시 worker 한계 — `get_max_parallel()` 로 clamp.
            <=0 → 1 로 floor (defensive).
        fail_fast: True (default) — 한 item 실패 시 미시작 future cancel + 즉시 종료.
            False — 모든 item 끝까지 실행 후 집계.

    Returns:
        입력 items 순서를 보존한 `ParallelOutcome` 리스트.
    """
    items_list = list(items)
    if not items_list:
        return []

    effective = max(1, min(int(max_workers), get_max_parallel()))

    outcomes: list[ParallelOutcome] = [
        ParallelOutcome(item=it, ok=False, value=None, exception=None)
        for it in items_list
    ]

    if fail_fast:
        return _spawn_fail_fast(items_list, outcomes, fn, effective)
    return _spawn_fail_tolerant(items_list, outcomes, fn, effective)


def _spawn_fail_tolerant(
    items_list: list[Any],
    outcomes: list[ParallelOutcome],
    fn: Callable[[Any], Any],
    workers: int,
) -> list[ParallelOutcome]:
    """모든 future 끝까지 wait + 결과 집계."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_idx = {
            pool.submit(fn, item): idx for idx, item in enumerate(items_list)
        }
        for fut in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[fut]
            try:
                value = fut.result()
                outcomes[idx] = ParallelOutcome(
                    item=items_list[idx], ok=True, value=value, exception=None
                )
            except BaseException as exc:  # noqa: BLE001 — outcome 으로 박제
                outcomes[idx] = ParallelOutcome(
                    item=items_list[idx], ok=False, value=None, exception=exc
                )
    return outcomes


def _spawn_fail_fast(
    items_list: list[Any],
    outcomes: list[ParallelOutcome],
    fn: Callable[[Any], Any],
    workers: int,
) -> list[ParallelOutcome]:
    """한 future fail 감지 시 미시작 future cancel + 즉시 종료."""
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
    try:
        future_to_idx: dict[concurrent.futures.Future, int] = {
            pool.submit(fn, item): idx for idx, item in enumerate(items_list)
        }
        aborted = False
        for fut in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[fut]
            try:
                value = fut.result()
                outcomes[idx] = ParallelOutcome(
                    item=items_list[idx], ok=True, value=value, exception=None
                )
            except BaseException as exc:  # noqa: BLE001 — outcome 으로 박제
                outcomes[idx] = ParallelOutcome(
                    item=items_list[idx], ok=False, value=None, exception=exc
                )
                aborted = True
                # 시작 안 한 future cancel — 이미 실행 중인 future 는 GIL 보호
                # 안에서 자기 결과 박제까지 진행됨 (강제 kill 없음).
                for other in future_to_idx:
                    if not other.done():
                        other.cancel()
                break
        if aborted:
            # cancel 된 future 결과 박제 — 빠른 종료
            for other, other_idx in future_to_idx.items():
                if outcomes[other_idx].ok or outcomes[other_idx].exception is not None:
                    continue
                if other.cancelled():
                    outcomes[other_idx] = ParallelOutcome(
                        item=items_list[other_idx],
                        ok=False,
                        value=None,
                        exception=concurrent.futures.CancelledError("aborted by fail_fast"),
                    )
                elif other.done():
                    # 이미 끝났지만 결과 박제 누락 — 안전망
                    try:
                        v = other.result(timeout=0)
                        outcomes[other_idx] = ParallelOutcome(
                            item=items_list[other_idx], ok=True, value=v, exception=None
                        )
                    except BaseException as exc:  # noqa: BLE001
                        outcomes[other_idx] = ParallelOutcome(
                            item=items_list[other_idx],
                            ok=False,
                            value=None,
                            exception=exc,
                        )
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return outcomes
