"""Side effects combinators

Effects execute for observation only (logging, metrics, debugging)
and don't change the computation result."""

from __future__ import annotations

import typing
from collections.abc import Awaitable, Callable, Coroutine

from kungfu import Error, LazyCoroResult, Ok, Result

from ..writer import LazyCoroResultWriter, Log, WriterResult

# Generic combinators (extract + wrap pattern)
def tapM[M, T, E, Raw](
    interp: Callable[[], Coroutine[typing.Any, typing.Any, Raw]],
    *,
    extract: Callable[[Raw], Result[T, E]],
    get_value: Callable[[Raw], T],
    effect: Callable[[T], None],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, Raw]]], M],
) -> M:
    """Generic tap combinator."""

    async def run() -> Raw:
        raw = await interp()
        result = extract(raw)
        match result:
            case Ok(_):
                effect(get_value(raw))
            case Error(_):
                pass
        return raw

    return wrap(run)

def tap_asyncM[M, T, E, Raw](
    interp: Callable[[], Coroutine[typing.Any, typing.Any, Raw]],
    *,
    extract: Callable[[Raw], Result[T, E]],
    get_value: Callable[[Raw], T],
    effect: Callable[[T], Awaitable[None]],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, Raw]]], M],
) -> M:
    """Generic tap_async combinator."""

    async def run() -> Raw:
        raw = await interp()
        result = extract(raw)
        match result:
            case Ok(_):
                await effect(get_value(raw))
            case Error(_):
                pass
        return raw

    return wrap(run)

def tap_errM[M, T, E, Raw](
    interp: Callable[[], Coroutine[typing.Any, typing.Any, Raw]],
    *,
    extract: Callable[[Raw], Result[T, E]],
    get_error: Callable[[Raw], E],
    effect: Callable[[E], None],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, Raw]]], M],
) -> M:
    """Generic tap_err combinator."""

    async def run() -> Raw:
        raw = await interp()
        result = extract(raw)
        match result:
            case Error(_):
                effect(get_error(raw))
            case Ok(_):
                pass
        return raw

    return wrap(run)

def tap_err_asyncM[M, T, E, Raw](
    interp: Callable[[], Coroutine[typing.Any, typing.Any, Raw]],
    *,
    extract: Callable[[Raw], Result[T, E]],
    get_error: Callable[[Raw], E],
    effect: Callable[[E], Awaitable[None]],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, Raw]]], M],
) -> M:
    """Generic tap_err_async combinator."""

    async def run() -> Raw:
        raw = await interp()
        result = extract(raw)
        match result:
            case Error(_):
                await effect(get_error(raw))
            case Ok(_):
                pass
        return raw

    return wrap(run)

# Sugar for LazyCoroResult
def tap[T, E](
    interp: LazyCoroResult[T, E],
    *,
    effect: Callable[[T], None],
) -> LazyCoroResult[T, E]:
    """Execute sync side effect on Ok value, pass through unchanged."""

    async def run() -> Result[T, E]:
        r = await interp()
        match r:
            case Ok(value):
                effect(value)
            case Error(_):
                pass
        return r

    return LazyCoroResult(run)

def tap_async[T, E](
    interp: LazyCoroResult[T, E],
    *,
    effect: Callable[[T], Awaitable[None]],
) -> LazyCoroResult[T, E]:
    """Execute async side effect on Ok value, pass through unchanged."""

    async def run() -> Result[T, E]:
        r = await interp()
        match r:
            case Ok(value):
                await effect(value)
            case Error(_):
                pass
        return r

    return LazyCoroResult(run)

def tap_err[T, E](
    interp: LazyCoroResult[T, E],
    *,
    effect: Callable[[E], None],
) -> LazyCoroResult[T, E]:
    """Execute sync side effect on Error value, pass through unchanged."""

    async def run() -> Result[T, E]:
        r = await interp()
        match r:
            case Error(e):
                effect(e)
            case Ok(_):
                pass
        return r

    return LazyCoroResult(run)

def tap_err_async[T, E](
    interp: LazyCoroResult[T, E],
    *,
    effect: Callable[[E], Awaitable[None]],
) -> LazyCoroResult[T, E]:
    """Execute async side effect on Error value, pass through unchanged."""

    async def run() -> Result[T, E]:
        r = await interp()
        match r:
            case Error(e):
                await effect(e)
            case Ok(_):
                pass
        return r

    return LazyCoroResult(run)

def bimap_tap[T, E](
    interp: LazyCoroResult[T, E],
    *,
    on_ok: Callable[[T], None],
    on_err: Callable[[E], None],
) -> LazyCoroResult[T, E]:
    """Execute side effect on both Ok and Error, pass through unchanged."""

    async def run() -> Result[T, E]:
        r = await interp()
        match r:
            case Ok(value):
                on_ok(value)
            case Error(e):
                on_err(e)
        return r

    return LazyCoroResult(run)

# Sugar for LazyCoroResultWriter
def tap_writer[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    effect: Callable[[T], None],
) -> LazyCoroResultWriter[T, E, W]:
    """Execute sync side effect on Ok value. Preserves log."""

    async def run() -> WriterResult[T, E, Log[W]]:
        wr = await interp()
        match wr.result:
            case Ok(value):
                effect(value)
            case Error(_):
                pass
        return wr

    return LazyCoroResultWriter(run)

def tap_async_writer[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    effect: Callable[[T], Awaitable[None]],
) -> LazyCoroResultWriter[T, E, W]:
    """Execute async side effect on Ok value. Preserves log."""

    async def run() -> WriterResult[T, E, Log[W]]:
        wr = await interp()
        match wr.result:
            case Ok(value):
                await effect(value)
            case Error(_):
                pass
        return wr

    return LazyCoroResultWriter(run)

def tap_err_writer[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    effect: Callable[[E], None],
) -> LazyCoroResultWriter[T, E, W]:
    """Execute sync side effect on Error value. Preserves log."""

    async def run() -> WriterResult[T, E, Log[W]]:
        wr = await interp()
        match wr.result:
            case Error(e):
                effect(e)
            case Ok(_):
                pass
        return wr

    return LazyCoroResultWriter(run)

def tap_err_async_writer[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    effect: Callable[[E], Awaitable[None]],
) -> LazyCoroResultWriter[T, E, W]:
    """Execute async side effect on Error value. Preserves log."""

    async def run() -> WriterResult[T, E, Log[W]]:
        wr = await interp()
        match wr.result:
            case Error(e):
                await effect(e)
            case Ok(_):
                pass
        return wr

    return LazyCoroResultWriter(run)

def bimap_tap_writer[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    on_ok: Callable[[T], None],
    on_err: Callable[[E], None],
) -> LazyCoroResultWriter[T, E, W]:
    """Execute side effect on both Ok and Error. Preserves log."""

    async def run() -> WriterResult[T, E, Log[W]]:
        wr = await interp()
        match wr.result:
            case Ok(value):
                on_ok(value)
            case Error(e):
                on_err(e)
        return wr

    return LazyCoroResultWriter(run)

__all__ = (
    # LazyCoroResult
    "bimap_tap",
    "tap",
    "tap_async",
    "tap_err",
    "tap_err_async",
    # LazyCoroResultWriter
    "bimap_tap_writer",
    "tap_writer",
    "tap_async_writer",
    "tap_err_writer",
    "tap_err_async_writer",
    # Generic
    "tapM",
    "tap_asyncM",
    "tap_errM",
    "tap_err_asyncM",
)
