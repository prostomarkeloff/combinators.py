"""
Retry combinators
=================

Generic комбинаторы для retry логики с extract + wrap паттерном.
"""

from __future__ import annotations

import asyncio
import random
import typing
from collections.abc import Callable, Coroutine
from dataclasses import dataclass

from kungfu import Error, LazyCoroResult, Ok, Result

from .._helpers import extract_writer_result, identity, wrap_lazy_coro_result_writer
from .._types import Predicate
from ..writer import LazyCoroResultWriter


# BackoffStrategy = (attempt_num, error) -> delay_seconds
type BackoffStrategy[E] = Callable[[int, E], float]


def _fixed_backoff[E](delay: float) -> BackoffStrategy[E]:
    """Same delay every retry."""
    def strategy(attempt: int, error: E) -> float:
        _ = (attempt, error)
        return delay
    return strategy


def _exponential_backoff[E](
    initial: float,
    multiplier: float = 2.0,
    max_delay: float = 60.0,
) -> BackoffStrategy[E]:
    """Delay grows: initial * multiplier^attempt (capped at max_delay)."""
    def strategy(attempt: int, error: E) -> float:
        _ = error
        delay = initial * (multiplier ** attempt)
        return min(delay, max_delay)
    return strategy


def _jitter_backoff[E](
    base: float,
    jitter_factor: float = 0.5,
) -> BackoffStrategy[E]:
    """Base delay ± random noise."""
    def strategy(attempt: int, error: E) -> float:
        _ = (attempt, error)
        jitter = random.uniform(-jitter_factor, jitter_factor)
        return max(0.0, base * (1.0 + jitter))
    return strategy


def _exponential_jitter_backoff[E](
    initial: float,
    multiplier: float = 2.0,
    max_delay: float = 60.0,
    jitter_factor: float = 0.3,
) -> BackoffStrategy[E]:
    """Exponential growth + randomness = production-grade retry."""
    def strategy(attempt: int, error: E) -> float:
        _ = error
        base_delay = initial * (multiplier ** attempt)
        capped = min(base_delay, max_delay)
        jitter = random.uniform(-jitter_factor, jitter_factor)
        return max(0.0, capped * (1.0 + jitter))
    return strategy


@dataclass(frozen=True, slots=True)
class RetryPolicy[E]:
    """
    Retry configuration with pluggable backoff strategy.
    """

    times: int
    backoff: BackoffStrategy[E]
    retry_on: Predicate[E] | None = None

    def __post_init__(self) -> None:
        if self.times < 1:
            raise ValueError("RetryPolicy.times must be >= 1")
    
    @classmethod
    def fixed(
        cls,
        times: int,
        delay_seconds: float = 0.0,
        retry_on: Predicate[E] | None = None,
    ) -> RetryPolicy[E]:
        """Same delay every retry. Simple and predictable."""
        if delay_seconds < 0.0:
            raise ValueError("delay_seconds must be >= 0")
        return cls(times=times, backoff=_fixed_backoff(delay_seconds), retry_on=retry_on)
    
    @classmethod
    def exponential(
        cls,
        times: int,
        initial: float = 0.1,
        multiplier: float = 2.0,
        max_delay: float = 60.0,
        retry_on: Predicate[E] | None = None,
    ) -> RetryPolicy[E]:
        """Back off more aggressively with each failure."""
        if initial < 0.0:
            raise ValueError("initial must be >= 0")
        if multiplier < 1.0:
            raise ValueError("multiplier must be >= 1.0")
        if max_delay < initial:
            raise ValueError("max_delay must be >= initial")
        return cls(
            times=times,
            backoff=_exponential_backoff(initial, multiplier, max_delay),
            retry_on=retry_on,
        )
    
    @classmethod
    def jitter(
        cls,
        times: int,
        base: float = 1.0,
        jitter_factor: float = 0.5,
        retry_on: Predicate[E] | None = None,
    ) -> RetryPolicy[E]:
        """Randomized delays to avoid thundering herd."""
        if base < 0.0:
            raise ValueError("base must be >= 0")
        if jitter_factor < 0.0 or jitter_factor > 1.0:
            raise ValueError("jitter_factor must be in [0, 1]")
        return cls(times=times, backoff=_jitter_backoff(base, jitter_factor), retry_on=retry_on)
    
    @classmethod
    def exponential_jitter(
        cls,
        times: int,
        initial: float = 0.1,
        multiplier: float = 2.0,
        max_delay: float = 60.0,
        jitter_factor: float = 0.3,
        retry_on: Predicate[E] | None = None,
    ) -> RetryPolicy[E]:
        """Best of both: exponential growth + randomness."""
        if initial < 0.0:
            raise ValueError("initial must be >= 0")
        if multiplier < 1.0:
            raise ValueError("multiplier must be >= 1.0")
        if max_delay < initial:
            raise ValueError("max_delay must be >= initial")
        if jitter_factor < 0.0 or jitter_factor > 1.0:
            raise ValueError("jitter_factor must be in [0, 1]")
        return cls(
            times=times,
            backoff=_exponential_jitter_backoff(initial, multiplier, max_delay, jitter_factor),
            retry_on=retry_on,
        )


def _should_retry[E](*, policy: RetryPolicy[E], attempt: int, error: E) -> bool:
    if attempt + 1 >= policy.times:
        return False
    if policy.retry_on is not None and not policy.retry_on(error):
        return False
    return True


def _delay_seconds[E](*, policy: RetryPolicy[E], attempt: int, error: E) -> float:
    return policy.backoff(attempt, error)


# ============================================================================
# Generic combinator (extract + wrap pattern)
# ============================================================================


def retryM[M, T, E, Raw](
    interp: Callable[[], Coroutine[typing.Any, typing.Any, Raw]],
    *,
    extract: Callable[[Raw], Result[T, E]],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, Raw]]], M],
    policy: RetryPolicy[E],
) -> M:
    """
    Generic retry combinator.
    
    Call interpretation N times until Ok, otherwise return Error.
    
    Args:
        interp: Callable returning Coroutine[Raw]
        extract: Function to extract Result[T, E] from Raw for retry logic
        wrap: Constructor to wrap thunk back into monad M
        policy: Retry policy with backoff strategy
    
    Example (LazyCoroResult):
        retryM(lcr, extract=identity, wrap=LazyCoroResult, policy=...)
    
    Example (custom monad):
        retryM(my_monad, extract=lambda r: r.result, wrap=MyMonad, policy=...)
    """

    async def run() -> Raw:
        last: Raw | None = None
        for attempt in range(policy.times):
            raw = await interp()
            result = extract(raw)
            
            match result:
                case Ok(_):
                    return raw
                case Error(e):
                    last = raw
            if not _should_retry(policy=policy, attempt=attempt, error=e):
                        return raw
            delay = _delay_seconds(policy=policy, attempt=attempt, error=e)
            if delay > 0.0:
                await asyncio.sleep(delay)

        if last is None:
            raise RuntimeError("retryM(): internal error (no attempts)")
        return last

    return wrap(run)


# ============================================================================
# Sugar for LazyCoroResult
# ============================================================================


def retry[T, E](
    interp: LazyCoroResult[T, E],
    *,
    policy: RetryPolicy[E],
) -> LazyCoroResult[T, E]:
    """
    Retry for LazyCoroResult.
    
    Call interpretation N times until Ok, otherwise return Error.
    """
    return retryM(
        interp,
        extract=identity,
        wrap=LazyCoroResult,
        policy=policy,
    )


# ============================================================================
# Sugar for LazyCoroResultWriter
# ============================================================================


def retry_w[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    policy: RetryPolicy[E],
) -> LazyCoroResultWriter[T, E, W]:
    """
    Retry for LazyCoroResultWriter.
    
    NOTE: При retry логи теряются между попытками - только финальный результат
    содержит лог последней попытки.
    """
    return retryM(
        interp,
        extract=extract_writer_result,
        wrap=wrap_lazy_coro_result_writer,
        policy=policy,
    )


__all__ = (
    "RetryPolicy",
    "retryM",
    "retry",
    "retry_w",
)
