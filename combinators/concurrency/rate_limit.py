"""
Rate limit combinators
======================

Комбинаторы для rate limiting с extract + wrap паттерном.
"""

from __future__ import annotations

import asyncio
import time
import typing
from collections.abc import Callable, Coroutine
from dataclasses import dataclass

from kungfu import LazyCoroResult

from ..writer import LazyCoroResultWriter, Log, WriterResult


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    """
    Token bucket configuration: sustained rate + burst capacity.
    """
    
    max_per_second: float
    burst: int | None = None
    
    def __post_init__(self) -> None:
        if self.max_per_second <= 0:
            raise ValueError("RateLimitPolicy.max_per_second must be > 0")
        if self.burst is not None and self.burst < 1:
            raise ValueError("RateLimitPolicy.burst must be >= 1")


class _TokenBucket:
    """Token bucket rate limiter."""
    
    def __init__(self, max_per_second: float, burst: int) -> None:
        self.max_per_second = max_per_second
        self.burst = burst
        self.tokens = float(burst)
        self.last_refill = time.monotonic()
    
    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        new_tokens = elapsed * self.max_per_second
        self.tokens = min(self.burst, self.tokens + new_tokens)
        self.last_refill = now
    
    async def acquire(self) -> None:
        while True:
            self._refill()
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return
            wait_time = (1.0 - self.tokens) / self.max_per_second + 0.001
            await asyncio.sleep(wait_time)


# ============================================================================
# Generic combinator (extract + wrap pattern)
# ============================================================================


def rate_limitM[M, T, E, Raw](
    interp: Callable[[], Coroutine[typing.Any, typing.Any, Raw]],
    *,
    policy: RateLimitPolicy,
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, Raw]]], M],
) -> M:
    """
    Generic rate limit combinator.
    
    Throttle with token bucket: allows burst while maintaining average rate.
    """
    burst = policy.burst if policy.burst is not None else int(policy.max_per_second)
    bucket = _TokenBucket(policy.max_per_second, burst)
    
    async def run() -> Raw:
        await bucket.acquire()
        return await interp()
    
    return wrap(run)


# ============================================================================
# Sugar for LazyCoroResult
# ============================================================================


def rate_limit[T, E](
    interp: LazyCoroResult[T, E],
    *,
    policy: RateLimitPolicy,
) -> LazyCoroResult[T, E]:
    """Throttle with token bucket."""
    return rate_limitM(interp, policy=policy, wrap=LazyCoroResult)


# ============================================================================
# Sugar for LazyCoroResultWriter
# ============================================================================


def rate_limit_w[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    policy: RateLimitPolicy,
) -> LazyCoroResultWriter[T, E, W]:
    """Throttle with token bucket. Preserves log."""
    
    def wrap_wr(
        thunk: Callable[[], Coroutine[typing.Any, typing.Any, WriterResult[T, E, Log[W]]]]
    ) -> LazyCoroResultWriter[T, E, W]:
        return LazyCoroResultWriter(thunk)
    
    return rate_limitM(interp, policy=policy, wrap=wrap_wr)


__all__ = ("RateLimitPolicy", "rate_limit", "rate_limit_w", "rate_limitM")
