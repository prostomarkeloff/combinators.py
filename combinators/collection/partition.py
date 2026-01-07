"""Partition combinators

Partition results with extract + wrap pattern."""

from __future__ import annotations

import asyncio
import typing
from collections.abc import Callable, Coroutine, Sequence

from kungfu import Error, LazyCoroResult, Ok, Result

from .._types import NoError
from ..writer import LazyCoroResultWriter, Log, WriterResult

# Generic combinator (extract + wrap pattern)
def partitionM[M, T, E, RawIn, RawOut](
    interps: Sequence[Callable[[], Coroutine[typing.Any, typing.Any, RawIn]]],
    *,
    extract: Callable[[RawIn], Result[T, E]],
    get_value: Callable[[RawIn], T],
    get_error: Callable[[RawIn], E],
    combine: Callable[[list[T], list[E], list[RawIn]], RawOut],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, RawOut]]], M],
) -> M:
    """Generic partition combinator."""

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
        
        return combine(successes, failures, raws)

    return wrap(run)

# Sugar for LazyCoroResult
def partition[T, E](
    interps: Sequence[LazyCoroResult[T, E]],
) -> LazyCoroResult[tuple[list[T], list[E]], NoError]:
    """Run all, separate into (successes, failures). Never fails."""

    async def run() -> Result[tuple[list[T], list[E]], NoError]:
        results: list[Result[T, E]] = await asyncio.gather(*(i() for i in interps))
        
        successes: list[T] = []
        failures: list[E] = []
        
        for r in results:
            match r:
                case Ok(value):
                    successes.append(value)
                case Error(err):
                    failures.append(err)
        
        return Ok((successes, failures))

    return LazyCoroResult(run)

# Sugar for LazyCoroResultWriter
def partition_writer[T, E, W](
    interps: Sequence[LazyCoroResultWriter[T, E, W]],
) -> LazyCoroResultWriter[tuple[list[T], list[E]], NoError, W]:
    """Run all, separate into (successes, failures). Merge logs."""

    async def run() -> WriterResult[tuple[list[T], list[E]], NoError, Log[W]]:
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
        
        return WriterResult(Ok((successes, failures)), merged_log)

    return LazyCoroResultWriter(run)

__all__ = ("partition", "partition_writer", "partitionM")
