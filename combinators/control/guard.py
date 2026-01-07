"""
Guard combinators
=================

Комбинаторы для валидации с extract + wrap паттерном.
"""

from __future__ import annotations

import typing
from collections.abc import Callable, Coroutine

from kungfu import Error, LazyCoroResult, Ok, Result

from .._types import Predicate
from ..writer import LazyCoroResultWriter, Log, WriterResult


# ============================================================================
# Generic combinators (extract + wrap pattern)
# ============================================================================


def ensureM[M, T, E, Raw](
    interp: Callable[[], Coroutine[typing.Any, typing.Any, Raw]],
    *,
    extract: Callable[[Raw], Result[T, E]],
    get_value: Callable[[Raw], T],
    predicate: Predicate[T],
    error: Callable[[T], E],
    combine_ok: Callable[[T, Raw], Raw],
    combine_err: Callable[[E, Raw], Raw],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, Raw]]], M],
) -> M:
    """
    Generic ensure combinator.
    
    Turn Ok into Error if value FAILS validation check.
    """

    async def run() -> Raw:
        raw = await interp()
        result = extract(raw)
        
        match result:
            case Error(_):
                return raw
            case Ok(_):
                value = get_value(raw)
                if predicate(value):
                    return combine_ok(value, raw)
                else:
                    return combine_err(error(value), raw)

    return wrap(run)


def rejectM[M, T, E, Raw](
    interp: Callable[[], Coroutine[typing.Any, typing.Any, Raw]],
    *,
    extract: Callable[[Raw], Result[T, E]],
    get_value: Callable[[Raw], T],
    predicate: Predicate[T],
    error: Callable[[T], E],
    combine_ok: Callable[[T, Raw], Raw],
    combine_err: Callable[[E, Raw], Raw],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, Raw]]], M],
) -> M:
    """
    Generic reject combinator.
    
    Turn Ok into Error if value MATCHES condition. Dual of ensure.
    """

    async def run() -> Raw:
        raw = await interp()
        result = extract(raw)
        
        match result:
            case Error(_):
                return raw
            case Ok(_):
                value = get_value(raw)
                if predicate(value):
                    return combine_err(error(value), raw)
                else:
                    return combine_ok(value, raw)

    return wrap(run)


# ============================================================================
# Sugar for LazyCoroResult
# ============================================================================


def ensure[T, E](
    interp: LazyCoroResult[T, E],
    *,
    predicate: Predicate[T],
    error: Callable[[T], E],
) -> LazyCoroResult[T, E]:
    """Turn Ok into Error if value FAILS validation check."""

    async def check(value: T) -> Result[T, E]:
        return Ok(value) if predicate(value) else Error(error(value))

    return interp.then(check)


def reject[T, E](
    interp: LazyCoroResult[T, E],
    *,
    predicate: Predicate[T],
    error: Callable[[T], E],
) -> LazyCoroResult[T, E]:
    """Turn Ok into Error if value MATCHES condition."""

    async def check(value: T) -> Result[T, E]:
        return Error(error(value)) if predicate(value) else Ok(value)

    return interp.then(check)


# ============================================================================
# Sugar for LazyCoroResultWriter
# ============================================================================


def ensure_w[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    predicate: Predicate[T],
    error: Callable[[T], E],
) -> LazyCoroResultWriter[T, E, W]:
    """Turn Ok into Error if value FAILS validation check. Preserves log."""
    
    def extract(wr: WriterResult[T, E, Log[W]]) -> Result[T, E]:
        return wr.result
    
    def get_value(wr: WriterResult[T, E, Log[W]]) -> T:
        return wr.result.unwrap()
    
    def combine_ok(value: T, wr: WriterResult[T, E, Log[W]]) -> WriterResult[T, E, Log[W]]:
        _ = value
        return wr
    
    def combine_err(e: E, wr: WriterResult[T, E, Log[W]]) -> WriterResult[T, E, Log[W]]:
        return WriterResult(Error(e), wr.log)
    
    def wrap_wr(
        thunk: Callable[[], Coroutine[typing.Any, typing.Any, WriterResult[T, E, Log[W]]]]
    ) -> LazyCoroResultWriter[T, E, W]:
        return LazyCoroResultWriter(thunk)
    
    return ensureM(
        interp,
        extract=extract,
        get_value=get_value,
        predicate=predicate,
        error=error,
        combine_ok=combine_ok,
        combine_err=combine_err,
        wrap=wrap_wr,
    )


def reject_w[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    predicate: Predicate[T],
    error: Callable[[T], E],
) -> LazyCoroResultWriter[T, E, W]:
    """Turn Ok into Error if value MATCHES condition. Preserves log."""
    
    def extract(wr: WriterResult[T, E, Log[W]]) -> Result[T, E]:
        return wr.result
    
    def get_value(wr: WriterResult[T, E, Log[W]]) -> T:
        return wr.result.unwrap()
    
    def combine_ok(value: T, wr: WriterResult[T, E, Log[W]]) -> WriterResult[T, E, Log[W]]:
        _ = value
        return wr
    
    def combine_err(e: E, wr: WriterResult[T, E, Log[W]]) -> WriterResult[T, E, Log[W]]:
        return WriterResult(Error(e), wr.log)
    
    def wrap_wr(
        thunk: Callable[[], Coroutine[typing.Any, typing.Any, WriterResult[T, E, Log[W]]]]
    ) -> LazyCoroResultWriter[T, E, W]:
        return LazyCoroResultWriter(thunk)
    
    return rejectM(
        interp,
        extract=extract,
        get_value=get_value,
        predicate=predicate,
        error=error,
        combine_ok=combine_ok,
        combine_err=combine_err,
        wrap=wrap_wr,
    )


__all__ = ("ensure", "reject", "ensure_w", "reject_w", "ensureM", "rejectM")
