"""Tests for time combinators: delay, timeout."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from kungfu import Error, LazyCoroResult, Ok, Result

from combinators import TimeoutError, delay, timeout
from tests.conftest import lcr_err, lcr_ok


def slow_lcr(value: Any, sleep: float) -> LazyCoroResult[Any, Any]:
    async def run() -> Result[Any, Any]:
        await asyncio.sleep(sleep)
        return Ok(value)
    return LazyCoroResult(run)


# -- delay --

async def test_delay_sleeps_before_running() -> None:
    start = time.monotonic()
    out = await delay(lcr_ok("v"), seconds=0.01)()
    elapsed = time.monotonic() - start
    assert out == Ok("v")
    assert elapsed >= 0.005


async def test_delay_zero_seconds_skips_sleep() -> None:
    out = await delay(lcr_ok("v"), seconds=0.0)()
    assert out == Ok("v")


# -- timeout --

async def test_timeout_completes_before_limit() -> None:
    out = await timeout(lcr_ok("fast"), seconds=1.0)()
    assert out == Ok("fast")


async def test_timeout_passes_through_error() -> None:
    out = await timeout(lcr_err("err"), seconds=1.0)()
    assert out == Error("err")


async def test_timeout_fires_when_exceeded() -> None:
    out = await timeout(slow_lcr("slow", sleep=0.05), seconds=0.005)()
    assert isinstance(out, Error)
    err = out.error
    assert isinstance(err, TimeoutError)
    assert err.seconds == 0.005
    assert "0.005" in str(err)
