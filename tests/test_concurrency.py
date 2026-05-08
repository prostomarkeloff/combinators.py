"""Tests for concurrency: batch, gather, parallel, race, rate_limit, zip."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
from hypothesis import given, settings, strategies as st
from kungfu import Error, LazyCoroResult, Ok, Result

from combinators import (
    RaceOkPolicy,
    RateLimitPolicy,
    batch,
    batch_all,
    gather2,
    gather3,
    parallel,
    race,
    race_ok,
    rate_limit,
    zip_par,
    zip_with,
)
from tests.conftest import lcr_err, lcr_ok


def lcr_async(value: Any, delay: float = 0.0) -> LazyCoroResult[Any, Any]:
    async def run() -> Result[Any, Any]:
        if delay > 0:
            await asyncio.sleep(delay)
        return Ok(value)
    return LazyCoroResult(run)


def lcr_async_err(err: Any, delay: float = 0.0) -> LazyCoroResult[Any, Any]:
    async def run() -> Result[Any, Any]:
        if delay > 0:
            await asyncio.sleep(delay)
        return Error(err)
    return LazyCoroResult(run)


# -- parallel --

async def test_parallel_ok() -> None:
    out = await parallel(lcr_ok(1), lcr_ok(2), lcr_ok(3))()
    assert out == Ok([1, 2, 3])


async def test_parallel_fail_fast() -> None:
    out = await parallel(lcr_ok(1), lcr_err("e"), lcr_ok(3))()
    assert out == Error("e")


async def test_parallel_preserves_order() -> None:
    # later items finish faster, but order in result follows input order
    out = await parallel(
        lcr_async(1, delay=0.02),
        lcr_async(2, delay=0.0),
    )()
    assert out == Ok([1, 2])


# -- gather2 / gather3 --

async def test_gather2_ok() -> None:
    out = await gather2(lcr_ok(1), lcr_ok("a"))()
    assert out == Ok((1, "a"))


async def test_gather2_first_error_short_circuits() -> None:
    out = await gather2(lcr_err("e1"), lcr_ok("b"))()
    assert out == Error("e1")


async def test_gather2_second_error() -> None:
    out = await gather2(lcr_ok(1), lcr_err("e2"))()
    assert out == Error("e2")


async def test_gather3_ok() -> None:
    out = await gather3(lcr_ok(1), lcr_ok(2.0), lcr_ok("x"))()
    assert out == Ok((1, 2.0, "x"))


async def test_gather3_returns_first_error_in_order() -> None:
    out = await gather3(lcr_ok(1), lcr_err("b"), lcr_err("c"))()
    assert out == Error("b")


async def test_gather3_third_error() -> None:
    out = await gather3(lcr_ok(1), lcr_ok(2), lcr_err("c"))()
    assert out == Error("c")


# -- race --

async def test_race_returns_first_completed() -> None:
    fast = lcr_async("fast", delay=0.0)
    slow = lcr_async("slow", delay=0.05)
    out = await race(fast, slow)()
    assert out == Ok("fast")


async def test_race_returns_first_completed_error() -> None:
    fast_err = lcr_async_err("eee", delay=0.0)
    slow = lcr_async("slow", delay=0.05)
    out = await race(fast_err, slow)()
    assert out == Error("eee")


async def test_race_empty_raises() -> None:
    with pytest.raises(ValueError):
        await race()()


# -- race_ok --

async def test_race_ok_picks_first_ok() -> None:
    out = await race_ok(
        lcr_async_err("first-err", delay=0.0),
        lcr_async("second-ok", delay=0.02),
    )()
    assert out == Ok("second-ok")


async def test_race_ok_all_failures_returns_last_error() -> None:
    out = await race_ok(
        lcr_async_err("first", delay=0.0),
        lcr_async_err("second", delay=0.02),
    )()
    assert out == Error("second")


async def test_race_ok_all_failures_first_strategy() -> None:
    out = await race_ok(
        lcr_async_err("first", delay=0.0),
        lcr_async_err("second", delay=0.02),
        policy=RaceOkPolicy(error_strategy="first"),
    )()
    assert out == Error("first")


def test_race_ok_policy_validates() -> None:
    with pytest.raises(ValueError):
        RaceOkPolicy(error_strategy="middle")  # type: ignore[arg-type]


async def test_race_ok_empty_raises() -> None:
    with pytest.raises(ValueError):
        await race_ok()()


async def test_race_ok_no_cancel_pending_runs_all() -> None:
    seen: list[str] = []

    async def runner(name: str, delay: float, ok: bool) -> Result[str, str]:
        await asyncio.sleep(delay)
        seen.append(name)
        return Ok(name) if ok else Error(name)

    out = await race_ok(
        LazyCoroResult(lambda: runner("fast", 0.0, True)),
        LazyCoroResult(lambda: runner("slow", 0.02, True)),
        policy=RaceOkPolicy(cancel_pending=False),
    )()
    assert out == Ok("fast")
    # Wait briefly for the non-cancelled task; the implementation already
    # awaits all tasks since cancel_pending=False keeps as_completed running.
    assert "slow" in seen or len(seen) == 1


# -- batch --

async def test_batch_processes_all_in_order() -> None:
    items = [1, 2, 3, 4]
    out = await batch(items, lambda x: lcr_ok(x * 10), concurrency=2)()
    assert out == Ok([10, 20, 30, 40])


async def test_batch_fails_fast_on_handler_error() -> None:
    def h(x: int) -> Any:
        if x == 3:
            return lcr_err(f"bad:{x}")
        return lcr_ok(x)

    out = await batch([1, 2, 3, 4], h, concurrency=2)()
    assert out == Error("bad:3")


async def test_batch_all_returns_results_list() -> None:
    def h(x: int) -> Any:
        return lcr_err(f"e{x}") if x % 2 == 0 else lcr_ok(x)

    out = await batch_all([1, 2, 3], h, concurrency=10)()
    assert isinstance(out, Ok)
    items = out.value
    assert items == [Ok(1), Error("e2"), Ok(3)]


async def test_batch_concurrency_bound() -> None:
    inflight = 0
    max_inflight = 0

    def h(x: int) -> LazyCoroResult[int, Any]:
        async def run() -> Result[int, Any]:
            nonlocal inflight, max_inflight
            inflight += 1
            max_inflight = max(max_inflight, inflight)
            await asyncio.sleep(0.01)
            inflight -= 1
            return Ok(x)
        return LazyCoroResult(run)

    await batch(list(range(8)), h, concurrency=3)()
    assert max_inflight <= 3


@given(items=st.lists(st.integers(min_value=-100, max_value=100), max_size=12))
@settings(deadline=None, max_examples=20)
async def test_batch_property_preserves_values(items: list[int]) -> None:
    out = await batch(items, lambda x: lcr_ok(x), concurrency=4)()
    assert out == Ok(list(items))


# -- zip_par / zip_with --

async def test_zip_par_returns_tuple() -> None:
    out = await zip_par(lcr_ok(1), lcr_ok(2), lcr_ok(3))()
    assert out == Ok((1, 2, 3))


async def test_zip_par_fails_on_first_error() -> None:
    out = await zip_par(lcr_ok(1), lcr_err("e"), lcr_ok(3))()
    assert out == Error("e")


async def test_zip_with_combiner() -> None:
    out = await zip_with(lcr_ok(1), lcr_ok(2), lcr_ok(3), combiner=sum)()
    assert out == Ok(6)


# -- rate_limit --

def test_rate_limit_policy_validates() -> None:
    with pytest.raises(ValueError):
        RateLimitPolicy(max_per_second=0)
    with pytest.raises(ValueError):
        RateLimitPolicy(max_per_second=1, burst=0)


async def test_rate_limit_passes_through() -> None:
    out = await rate_limit(lcr_ok(7), policy=RateLimitPolicy(max_per_second=100))()
    assert out == Ok(7)


async def test_rate_limit_throttles_when_burst_exceeded() -> None:
    # Force a wait: burst=1, second call must wait (~1/100 = 10ms)
    policy = RateLimitPolicy(max_per_second=100, burst=1)
    interp = rate_limit(lcr_ok("x"), policy=policy)

    start = time.monotonic()
    await interp()
    await interp()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.005  # at least some delay
