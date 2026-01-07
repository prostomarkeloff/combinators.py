"""
Validate combinators
====================

Валидация с накоплением ошибок.
"""

from __future__ import annotations

import asyncio
import typing
from collections.abc import Callable, Coroutine, Sequence

from kungfu import Error, LazyCoroResult, Ok, Result

from ..writer import LazyCoroResultWriter, Log, WriterResult


# ============================================================================
# Generic combinator (extract + wrap pattern)
# ============================================================================


def validateM[M, T, E, RawIn, RawOut](
    interps: Sequence[Callable[[], Coroutine[typing.Any, typing.Any, RawIn]]],
    *,
    extract: Callable[[RawIn], Result[T, E]],
    get_value: Callable[[RawIn], T],
    get_error: Callable[[RawIn], E],
    combine_ok: Callable[[list[T], list[RawIn]], RawOut],
    combine_err: Callable[[list[E], list[RawIn]], RawOut],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, RawOut]]], M],
) -> M:
    """Generic validate combinator. Collects ALL errors."""

    async def run() -> RawOut:
        raws: list[RawIn] = await asyncio.gather(*(i() for i in interps))
        
        successes: list[T] = []
        failures: list[E] = []
        
        for raw in raws:
            result = extract(raw)
            match result:
                case Ok(_):
                    successes.append(get_value(raw))
                case Error(_):
                    failures.append(get_error(raw))
        
        if failures:
            return combine_err(failures, raws)
        return combine_ok(successes, raws)

    return wrap(run)


# ============================================================================
# Sugar for LazyCoroResult
# ============================================================================


def validate[T, E](
    interps: Sequence[LazyCoroResult[T, E]],
) -> LazyCoroResult[list[T], list[E]]:
    """Run all, collect ALL errors (not fail-fast)."""

    async def run() -> Result[list[T], list[E]]:
        results: list[Result[T, E]] = await asyncio.gather(*(i() for i in interps))
        
        successes: list[T] = []
        failures: list[E] = []
        
        for r in results:
            match r:
                case Ok(value):
                    successes.append(value)
                case Error(err):
                    failures.append(err)
        
        if failures:
            return Error(failures)
        return Ok(successes)

    return LazyCoroResult(run)


# ============================================================================
# Sugar for LazyCoroResultWriter
# ============================================================================


def validate_w[T, E, W](
    interps: Sequence[LazyCoroResultWriter[T, E, W]],
) -> LazyCoroResultWriter[list[T], list[E], W]:
    """Run all, collect ALL errors with log merging."""

    async def run() -> WriterResult[list[T], list[E], Log[W]]:
        wrs: list[WriterResult[T, E, Log[W]]] = await asyncio.gather(*(i() for i in interps))
        
        successes: list[T] = []
        failures: list[E] = []
        merged_log = Log[W]()
        
        for wr in wrs:
            merged_log = merged_log.combine(wr.log)
            match wr.result:
                case Ok(value):
                    successes.append(value)
                case Error(err):
                    failures.append(err)
        
        if failures:
            return WriterResult(Error(failures), merged_log)
        return WriterResult(Ok(successes), merged_log)

    return LazyCoroResultWriter(run)


__all__ = ("validate", "validate_w", "validateM")
