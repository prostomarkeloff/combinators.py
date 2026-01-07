"""Recover combinators

Combinators for recovery with extract + wrap pattern."""

from __future__ import annotations

import typing
from collections.abc import Callable, Coroutine

from kungfu import Error, LazyCoroResult, Ok, Result

from .._types import NoError
from ..writer import LazyCoroResultWriter, Log, WriterResult

# Generic combinators (extract + wrap pattern)
def recoverM[M, T, E, RawIn, RawOut](
    interp: Callable[[], Coroutine[typing.Any, typing.Any, RawIn]],
    *,
    extract: Callable[[RawIn], Result[T, E]],
    get_value: Callable[[RawIn], T],
    default: T,
    combine: Callable[[T, RawIn | None], RawOut],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, RawOut]]], M],
) -> M:
    """
    Generic recover combinator.
    
    Turn any Error into Ok with fallback value.
    """

    async def run() -> RawOut:
        raw = await interp()
        result = extract(raw)
        
        match result:
            case Ok(_):
                return combine(get_value(raw), raw)
            case Error(_):
                return combine(default, None)

    return wrap(run)

def recover_withM[M, T, E, RawIn, RawOut](
    interp: Callable[[], Coroutine[typing.Any, typing.Any, RawIn]],
    *,
    extract: Callable[[RawIn], Result[T, E]],
    get_value: Callable[[RawIn], T],
    get_error: Callable[[RawIn], E],
    handler: Callable[[E], T],
    combine: Callable[[T, RawIn | None], RawOut],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, RawOut]]], M],
) -> M:
    """
    Generic recover_with combinator.
    
    Turn any Error into Ok using recovery function.
    """

    async def run() -> RawOut:
        raw = await interp()
        result = extract(raw)
        
        match result:
            case Ok(_):
                return combine(get_value(raw), raw)
            case Error(_):
                recovered = handler(get_error(raw))
                return combine(recovered, raw)

    return wrap(run)

# Sugar for LazyCoroResult
def recover[T, E](
    interp: LazyCoroResult[T, E],
    *,
    default: T,
) -> LazyCoroResult[T, NoError]:
    """Turn any Error into Ok with fallback value."""

    async def run() -> Result[T, NoError]:
        r = await interp()
        match r:
            case Ok(v):
                return Ok(v)
            case Error(_):
                return Ok(default)

    return LazyCoroResult(run)

def recover_with[T, E](
    interp: LazyCoroResult[T, E],
    *,
    handler: Callable[[E], T],
) -> LazyCoroResult[T, NoError]:
    """Turn any Error into Ok using recovery function."""

    async def run() -> Result[T, NoError]:
        r = await interp()
        match r:
            case Ok(v):
                return Ok(v)
            case Error(e):
                return Ok(handler(e))

    return LazyCoroResult(run)

# Sugar for LazyCoroResultWriter
def recover_writer[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    default: T,
) -> LazyCoroResultWriter[T, NoError, W]:
    """Turn any Error into Ok with fallback value. Preserves log."""

    async def run() -> WriterResult[T, NoError, Log[W]]:
        wr = await interp()
        match wr.result:
            case Ok(v):
                return WriterResult(Ok(v), wr.log)
            case Error(_):
                return WriterResult(Ok(default), wr.log)

    return LazyCoroResultWriter(run)

def recover_with_writer[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    handler: Callable[[E], T],
) -> LazyCoroResultWriter[T, NoError, W]:
    """Turn any Error into Ok using recovery function. Preserves log."""

    async def run() -> WriterResult[T, NoError, Log[W]]:
        wr = await interp()
        match wr.result:
            case Ok(v):
                return WriterResult(Ok(v), wr.log)
            case Error(e):
                return WriterResult(Ok(handler(e)), wr.log)

    return LazyCoroResultWriter(run)

__all__ = (
    "recover",
    "recover_with",
    "recover_writer",
    "recover_with_writer",
    "recoverM",
    "recover_withM",
)
