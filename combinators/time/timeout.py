"""Timeout combinators

Combinators for execution time limiting."""

from __future__ import annotations

import asyncio
import typing
from collections.abc import Callable, Coroutine

from kungfu import Error, LazyCoroResult, Ok, Result

from .._errors import TimeoutError
from .._helpers import extract_writer_result, identity
from ..writer import LazyCoroResultWriter, Log, WriterResult

# Generic combinator (extract + wrap pattern)
def timeoutM[M, T, E, RawIn, RawOut](
    interp: Callable[[], Coroutine[typing.Any, typing.Any, RawIn]],
    *,
    seconds: float,
    extract: Callable[[RawIn], Result[T, E]],
    widen: Callable[[RawIn], RawOut],
    on_timeout: Callable[[], RawOut],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, RawOut]]], M],
) -> M:
    """Generic timeout combinator."""

    async def run() -> RawOut:
        try:
            raw_in = await asyncio.wait_for(interp(), timeout=seconds)
            return widen(raw_in)
        except asyncio.TimeoutError:
            return on_timeout()

    return wrap(run)

# Sugar for LazyCoroResult
def timeout[T, E](
    interp: LazyCoroResult[T, E],
    *,
    seconds: float,
) -> LazyCoroResult[T, E | TimeoutError]:
    """
    Timeout for LazyCoroResult.
    
    Fail if takes too long. Adds TimeoutError to error channel.
    """
    def widen(r: Result[T, E]) -> Result[T, E | TimeoutError]:
        match r:
            case Ok(v):
                return Ok(v)
            case Error(e):
                return Error(e)
    
    def on_timeout() -> Result[T, E | TimeoutError]:
        return Error(TimeoutError(seconds))
    
    return timeoutM(
        interp,
        seconds=seconds,
        extract=identity,
        widen=widen,
        on_timeout=on_timeout,
        wrap=LazyCoroResult,
    )

# Sugar for LazyCoroResultWriter
def timeout_writer[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    seconds: float,
) -> LazyCoroResultWriter[T, E | TimeoutError, W]:
    """
    Timeout for LazyCoroResultWriter.
    
    Fail if takes too long. Adds TimeoutError to error channel.
    Preserves log from the operation if it completed before timeout.
    """
    def widen(wr: WriterResult[T, E, Log[W]]) -> WriterResult[T, E | TimeoutError, Log[W]]:
        match wr.result:
            case Ok(v):
                return WriterResult(Ok(v), wr.log)
            case Error(e):
                return WriterResult(Error(e), wr.log)
    
    def on_timeout() -> WriterResult[T, E | TimeoutError, Log[W]]:
        return WriterResult(Error(TimeoutError(seconds)), Log[W]())
    
    def wrap_wr(
        fn: Callable[[], Coroutine[typing.Any, typing.Any, WriterResult[T, E | TimeoutError, Log[W]]]]
    ) -> LazyCoroResultWriter[T, E | TimeoutError, W]:
        return LazyCoroResultWriter(fn)
    
    return timeoutM(
        interp,
        seconds=seconds,
        extract=extract_writer_result,
        widen=widen,
        on_timeout=on_timeout,
        wrap=wrap_wr,
    )

__all__ = ("timeout", "timeout_writer", "timeoutM")
