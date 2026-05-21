"""Production-line parallel — T-506 P3/P4. ThreadPoolExecutor based concurrent spawn infrastructure.

SPEC.md §3.4 + §6.5 (added T-506).

When drivers are in phases of the same topo level / workers in the same phase > 1
A wrapper that spawns workers simultaneously. LLM Calls X — Deterministic Infrastructure.

core:
- ThreadPoolExecutor (asyncio not adopted, T-506 plan §Canon SSOT decision)
- max_workers clamps to the get_max_parallel() guard
- fail_fast=True (default): Cancel non-starting futures when one item fails
- fail_fast=False: Run all items to the end and aggregate results
- The resulting list preserves the order of input items (deterministic)
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from ._common import get_max_parallel


@dataclass
class ParallelOutcome:
    """parallel_spawn Result of one item.

    Attributes:
        item: input item (e.g. Phase object, int, str...)
        ok: Whether the call was successful or not
        value: fn(item) return value (None on failure)
        exception: Exception raised on failure (None on success). fail_fast cancels
                   future is CancelledError or None.
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
    """Simultaneously execute items of the same level with ThreadPoolExecutor.

    Args:
        items: List of items to be processed (Phase / worker, etc.). order preservation.
        fn: 1 item → result value function. When exception is raised, outcome.ok=False.
        max_workers: Simultaneous worker limit — clamped with `get_max_parallel()`.
            <=0 → 1 floor (defensive).
        fail_fast: True (default) — If one item fails, future cancel + immediate termination.
            False — All items are executed to the end and then counted.

    Returns:
        A `ParallelOutcome` list that preserves the order of input items.
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
    """Wait until the end of all futures + aggregate results."""
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
            except BaseException as exc:  # noqa: BLE001 — Stuffed with outcome
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
    """When a future fail is detected, the non-starting future cancel + terminates immediately."""
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
            except BaseException as exc:  # noqa: BLE001 — Stuffed with outcome
                outcomes[idx] = ParallelOutcome(
                    item=items_list[idx], ok=False, value=None, exception=exc
                )
                aborted = True
                # Cancel a future that has not started — Futures that are already running are GIL protected
                # Inside, the animal is even taxidermied (no forced killing).
                for other in future_to_idx:
                    if not other.done():
                        other.cancel()
                break
        if aborted:
            # Stuffing canceled future results — quick exit
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
                    # Already done but missing the results taxidermy — a safety net
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
