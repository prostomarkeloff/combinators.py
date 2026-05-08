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
    combine: Callable[[T, RawIn], RawOut],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, RawOut]]], M],
) -> M:
    """
    Generic recover combinator.

    Turn any Error into Ok with fallback value. The original `raw` is always
    passed to `combine` so wrappers (e.g. Writer) can preserve side-data such
    as logs even on the recovered branch.
    """

    async def run() -> RawOut:
        raw = await interp()
        result = extract(raw)

        match result:
            case Ok(_):
                return combine(get_value(raw), raw)
            case Error(_):
                return combine(default, raw)

    return wrap(run)

def recover_withM[M, T, E, RawIn, RawOut](
    interp: Callable[[], Coroutine[typing.Any, typing.Any, RawIn]],
    *,
    extract: Callable[[RawIn], Result[T, E]],
    get_value: Callable[[RawIn], T],
    get_error: Callable[[RawIn], E],
    handler: Callable[[E], T],
    combine: Callable[[T, RawIn], RawOut],
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
def _lcr_get_value[T, E](r: Result[T, E]) -> T:
    return r.unwrap()

def _lcr_get_error[T, E](r: Result[T, E]) -> E:
    return r.unwrap_err()

def _lcr_combine[T, E](value: T, raw: Result[T, E]) -> Result[T, NoError]:
    _ = raw
    return Ok(value)

def recover[T, E](
    interp: LazyCoroResult[T, E],
    *,
    default: T,
) -> LazyCoroResult[T, NoError]:
    """Turn any Error into Ok with fallback value."""
    return recoverM(
        interp,
        extract=lambda r: r,
        get_value=_lcr_get_value,
        default=default,
        combine=_lcr_combine,
        wrap=LazyCoroResult,
    )

def recover_with[T, E](
    interp: LazyCoroResult[T, E],
    *,
    handler: Callable[[E], T],
) -> LazyCoroResult[T, NoError]:
    """Turn any Error into Ok using recovery function."""
    return recover_withM(
        interp,
        extract=lambda r: r,
        get_value=_lcr_get_value,
        get_error=_lcr_get_error,
        handler=handler,
        combine=_lcr_combine,
        wrap=LazyCoroResult,
    )

# Sugar for LazyCoroResultWriter
def _wr_extract[T, E, W](wr: WriterResult[T, E, Log[W]]) -> Result[T, E]:
    return wr.result

def _wr_get_value[T, E, W](wr: WriterResult[T, E, Log[W]]) -> T:
    return wr.result.unwrap()

def _wr_get_error[T, E, W](wr: WriterResult[T, E, Log[W]]) -> E:
    return wr.result.unwrap_err()

def _wr_combine[T, E, W](
    value: T,
    raw: WriterResult[T, E, Log[W]],
) -> WriterResult[T, NoError, Log[W]]:
    return WriterResult(Ok(value), raw.log)

def _wr_wrap[T, W](
    fn: Callable[[], Coroutine[typing.Any, typing.Any, WriterResult[T, NoError, Log[W]]]],
) -> LazyCoroResultWriter[T, NoError, W]:
    return LazyCoroResultWriter(fn)

def recover_writer[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    default: T,
) -> LazyCoroResultWriter[T, NoError, W]:
    """Turn any Error into Ok with fallback value. Preserves log."""
    return recoverM(
        interp,
        extract=_wr_extract,
        get_value=_wr_get_value,
        default=default,
        combine=_wr_combine,
        wrap=_wr_wrap,
    )

def recover_with_writer[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    handler: Callable[[E], T],
) -> LazyCoroResultWriter[T, NoError, W]:
    """Turn any Error into Ok using recovery function. Preserves log."""
    return recover_withM(
        interp,
        extract=_wr_extract,
        get_value=_wr_get_value,
        get_error=_wr_get_error,
        handler=handler,
        combine=_wr_combine,
        wrap=_wr_wrap,
    )

__all__ = (
    "recover",
    "recover_with",
    "recover_writer",
    "recover_with_writer",
    "recoverM",
    "recover_withM",
)
