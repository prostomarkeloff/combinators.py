"""Lift values into monad (LazyCoroResult)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Never

from kungfu import Error, LazyCoroResult, Ok, Result

from .._types import Interp

def pure[T](value: T) -> Interp[T, Never]:
    """Lift pure value into always-succeeding Interp."""
    return LazyCoroResult.pure(value)

def fail[E](error: E) -> Interp[Never, E]:
    """Create always-failing Interp."""
    return Error(error).to_async()

def from_result[T, E](value: Result[T, E]) -> Interp[T, E]:
    """Lift already-computed Result into Interp context."""
    async def run() -> Result[T, E]:
        return value

    return LazyCoroResult(run)

def optional[T, E](
    value: T | None,
    *,
    error: Callable[[], E],
) -> Interp[T, E]:
    """Convert Optional to Interp. None becomes Error(error())."""
    async def run() -> Result[T, E]:
        if value is None:
            return Error(error())
        return Ok(value)

    return LazyCoroResult(run)

def catching[T, E](
    fn: Callable[[], T],
    *,
    on_error: Callable[[Exception], E],
) -> Interp[T, E]:
    """Execute sync fn, catch exceptions and convert to Error."""
    async def run() -> Result[T, E]:
        try:
            return Ok(fn())
        except Exception as exc:
            return Error(on_error(exc))

    return LazyCoroResult(run)

def catching_async[T, E](
    fn: Callable[[], Awaitable[T]],
    *,
    on_error: Callable[[Exception], E],
) -> Interp[T, E]:
    """Execute async fn, catch exceptions and convert to Error."""
    async def run() -> Result[T, E]:
        try:
            return Ok(await fn())
        except Exception as exc:
            return Error(on_error(exc))

    return LazyCoroResult(run)

__all__ = (
    "pure",
    "fail",
    "from_result",
    "optional",
    "catching",
    "catching_async",
)
