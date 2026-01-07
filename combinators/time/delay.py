"""Delay combinators

Combinators for delay with extract + wrap pattern."""

from __future__ import annotations

import asyncio
import typing
from collections.abc import Callable, Coroutine

from kungfu import LazyCoroResult

from ..writer import LazyCoroResultWriter, Log, WriterResult

# Generic combinator (extract + wrap pattern)
def delayM[M, T, E, Raw](
    interp: Callable[[], Coroutine[typing.Any, typing.Any, Raw]],
    *,
    seconds: float,
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, Raw]]], M],
) -> M:
    """
    Generic delay combinator.
    
    Sleep before running.
    """

    async def run() -> Raw:
        if seconds > 0.0:
            await asyncio.sleep(seconds)
        return await interp()

    return wrap(run)

# Sugar for LazyCoroResult
def delay[T, E](
    interp: LazyCoroResult[T, E],
    *,
    seconds: float,
) -> LazyCoroResult[T, E]:
    """Sleep before running."""
    return delayM(interp, seconds=seconds, wrap=LazyCoroResult)

# Sugar for LazyCoroResultWriter
def delay_writer[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    seconds: float,
) -> LazyCoroResultWriter[T, E, W]:
    """Sleep before running. Preserves log."""
    
    def wrap_wr(
        fn: Callable[[], Coroutine[typing.Any, typing.Any, WriterResult[T, E, Log[W]]]]
    ) -> LazyCoroResultWriter[T, E, W]:
        return LazyCoroResultWriter(fn)
    
    return delayM(interp, seconds=seconds, wrap=wrap_wr)

__all__ = ("delay", "delay_writer", "delayM")
