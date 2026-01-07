"""Parallel combinators

Combinators for parallel execution with extract + wrap pattern."""

from __future__ import annotations

import asyncio
import typing
from collections.abc import Callable, Coroutine

from kungfu import Error, LazyCoroResult, Ok, Result

from .._helpers import (
    extract_writer_result,
    identity,
    merge_logs,
    wrap_lazy_coro_result_writer,
)
from ..writer import LazyCoroResultWriter, Log, WriterResult

# Generic combinator (extract + wrap pattern)
def parallelM[M, T, E, RawIn, RawOut](
    *interps: Callable[[], Coroutine[typing.Any, typing.Any, RawIn]],
    extract: Callable[[RawIn], Result[T, E]],
    combine_ok: Callable[[list[tuple[T, RawIn]]], RawOut],
    combine_err: Callable[[E, list[RawIn]], RawOut],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, RawOut]]], M],
) -> M:
    """Generic parallel combinator."""

    async def run() -> RawOut:
        raws: list[RawIn] = await asyncio.gather(*(i() for i in interps))
        
        # Extract all results, collect successes, fail on first error
        successes: list[tuple[T, RawIn]] = []
        for raw in raws:
            result = extract(raw)
            match result:
                case Ok(v):
                    successes.append((v, raw))
                case Error(e):
                    return combine_err(e, raws)
        
        return combine_ok(successes)

    return wrap(run)

# Sugar for LazyCoroResult
def parallel[T, E](*interps: LazyCoroResult[T, E]) -> LazyCoroResult[list[T], E]:
    """
    Run all concurrently, collect results. Fail-fast on first error.
    """
    def combine_ok(pairs: list[tuple[T, Result[T, E]]]) -> Result[list[T], E]:
        return Ok([v for v, _ in pairs])
    
    def combine_err(e: E, raws: list[Result[T, E]]) -> Result[list[T], E]:
        _ = raws  # Not needed for simple Result
        return Error(e)
    
    return parallelM(
        *interps,
        extract=identity,
        combine_ok=combine_ok,
        combine_err=combine_err,
        wrap=LazyCoroResult,
    )

# Sugar for LazyCoroResultWriter
def parallel_writer[T, E, W](
    *interps: LazyCoroResultWriter[T, E, W],
) -> LazyCoroResultWriter[list[T], E, W]:
    """
    Run all concurrently, collect results. Fail-fast on first error.
    
    Logs from all computations are merged (even on failure, logs up to failure are kept).
    """
    def combine_ok(
        pairs: list[tuple[T, WriterResult[T, E, Log[W]]]]
    ) -> WriterResult[list[T], E, Log[W]]:
        values = [v for v, _ in pairs]
        merged = merge_logs(wr.log for _, wr in pairs)
        return WriterResult(Ok(values), merged)
    
    def combine_err(
        e: E,
        raws: list[WriterResult[T, E, Log[W]]],
    ) -> WriterResult[list[T], E, Log[W]]:
        merged = merge_logs(wr.log for wr in raws)
        return WriterResult(Error(e), merged)
    
    return parallelM(
        *interps,
        extract=extract_writer_result,
        combine_ok=combine_ok,
        combine_err=combine_err,
        wrap=wrap_lazy_coro_result_writer,
    )

__all__ = ("parallel", "parallel_writer", "parallelM")
