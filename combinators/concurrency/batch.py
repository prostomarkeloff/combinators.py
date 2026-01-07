"""
Batch combinators
=================

Комбинаторы для batch обработки с extract + wrap паттерном.
"""

from __future__ import annotations

import asyncio
import typing
from collections.abc import Callable, Coroutine, Sequence

from kungfu import Error, LazyCoroResult, Ok, Result

from .._helpers import extract_writer_result, merge_logs
from .._types import NoError
from ..writer import LazyCoroResultWriter, Log, WriterResult


# ============================================================================
# Generic combinators (extract + wrap pattern)
# ============================================================================


def batchM[M, A, T, E, RawIn, RawOut](
    items: Sequence[A],
    handler: Callable[[A], Callable[[], Coroutine[typing.Any, typing.Any, RawIn]]],
    *,
    concurrency: int,
    extract: Callable[[RawIn], Result[T, E]],
    combine_ok: Callable[[list[tuple[T, RawIn]]], RawOut],
    combine_err: Callable[[E, list[RawIn | None]], RawOut],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, RawOut]]], M],
) -> M:
    """
    Generic batch combinator.
    
    Process with bounded concurrency. Results match input order.
    """

    async def run() -> RawOut:
        semaphore = asyncio.Semaphore(concurrency)
        raws: list[RawIn | None] = [None] * len(items)

        async def process(idx: int, item: A) -> None:
            async with semaphore:
                raws[idx] = await handler(item)()

        await asyncio.gather(*(process(i, item) for i, item in enumerate(items)))

        pairs: list[tuple[T, RawIn]] = []
        for raw in raws:
            if raw is None:
                raise RuntimeError("batchM(): internal error (missing result)")
            result = extract(raw)
            match result:
                case Ok(v):
                    pairs.append((v, raw))
                case Error(e):
                    return combine_err(e, raws)

        return combine_ok(pairs)

    return wrap(run)


def batch_allM[M, A, T, E, RawIn, RawOut](
    items: Sequence[A],
    handler: Callable[[A], Callable[[], Coroutine[typing.Any, typing.Any, RawIn]]],
    *,
    concurrency: int,
    combine: Callable[[list[RawIn]], RawOut],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, RawOut]]], M],
) -> M:
    """
    Generic batch_all combinator.
    
    Process all with bounded concurrency, collect all results.
    Never fails - returns all results (caller handles successes/failures).
    """

    async def run() -> RawOut:
        semaphore = asyncio.Semaphore(concurrency)
        raws: list[RawIn | None] = [None] * len(items)

        async def process(idx: int, item: A) -> None:
            async with semaphore:
                raws[idx] = await handler(item)()

        await asyncio.gather(*(process(i, item) for i, item in enumerate(items)))

        finalized: list[RawIn] = []
        for raw in raws:
            if raw is None:
                raise RuntimeError("batch_allM(): internal error (missing result)")
            finalized.append(raw)
        
        return combine(finalized)

    return wrap(run)


# ============================================================================
# Sugar for LazyCoroResult
# ============================================================================


def batch[A, T, E](
    items: Sequence[A],
    handler: Callable[[A], LazyCoroResult[T, E]],
    *,
    concurrency: int = 5,
) -> LazyCoroResult[list[T], E]:
    """
    Process with bounded concurrency. Results match input order.
    """
    def extract_result(r: Result[T, E]) -> Result[T, E]:
        return r
    
    def combine_ok(pairs: list[tuple[T, Result[T, E]]]) -> Result[list[T], E]:
        return Ok([v for v, _ in pairs])
    
    def combine_err(e: E, raws: list[Result[T, E] | None]) -> Result[list[T], E]:
        _ = raws
        return Error(e)
    
    return batchM(
        items,
        handler,
        concurrency=concurrency,
        extract=extract_result,
        combine_ok=combine_ok,
        combine_err=combine_err,
        wrap=LazyCoroResult,
    )


def batch_all[A, T, E](
    items: Sequence[A],
    handler: Callable[[A], LazyCoroResult[T, E]],
    *,
    concurrency: int = 5,
) -> LazyCoroResult[list[Result[T, E]], NoError]:
    """
    Process all with bounded concurrency, collect Ok and Error both.
    Never fails - returns list[Result].
    """
    def combine(raws: list[Result[T, E]]) -> Result[list[Result[T, E]], NoError]:
        return Ok(raws)
    
    return batch_allM(
        items,
        handler,
        concurrency=concurrency,
        combine=combine,
        wrap=LazyCoroResult,
    )


# ============================================================================
# Sugar for LazyCoroResultWriter
# ============================================================================


def batch_w[A, T, E, W](
    items: Sequence[A],
    handler: Callable[[A], LazyCoroResultWriter[T, E, W]],
    *,
    concurrency: int = 5,
) -> LazyCoroResultWriter[list[T], E, W]:
    """
    Process with bounded concurrency. Results match input order.
    
    Logs from all computations are merged.
    """
    def combine_ok(
        pairs: list[tuple[T, WriterResult[T, E, Log[W]]]]
    ) -> WriterResult[list[T], E, Log[W]]:
        values = [v for v, _ in pairs]
        merged = merge_logs(wr.log for _, wr in pairs)
        return WriterResult(Ok(values), merged)
    
    def combine_err(
        e: E,
        raws: list[WriterResult[T, E, Log[W]] | None],
    ) -> WriterResult[list[T], E, Log[W]]:
        merged = merge_logs(wr.log for wr in raws if wr is not None)
        return WriterResult(Error(e), merged)
    
    def wrap_wr(
        thunk: Callable[[], Coroutine[typing.Any, typing.Any, WriterResult[list[T], E, Log[W]]]]
    ) -> LazyCoroResultWriter[list[T], E, W]:
        return LazyCoroResultWriter(thunk)
    
    return batchM(
        items,
        handler,
        concurrency=concurrency,
        extract=extract_writer_result,
        combine_ok=combine_ok,
        combine_err=combine_err,
        wrap=wrap_wr,
    )


def batch_all_w[A, T, E, W](
    items: Sequence[A],
    handler: Callable[[A], LazyCoroResultWriter[T, E, W]],
    *,
    concurrency: int = 5,
) -> LazyCoroResultWriter[list[WriterResult[T, E, Log[W]]], NoError, W]:
    """
    Process all with bounded concurrency, collect all results.
    Never fails - returns all WriterResults with merged logs.
    """
    def combine(
        raws: list[WriterResult[T, E, Log[W]]]
    ) -> WriterResult[list[WriterResult[T, E, Log[W]]], NoError, Log[W]]:
        merged = merge_logs(wr.log for wr in raws)
        return WriterResult(Ok(raws), merged)
    
    def wrap_wr(
        thunk: Callable[[], Coroutine[typing.Any, typing.Any, WriterResult[list[WriterResult[T, E, Log[W]]], NoError, Log[W]]]]
    ) -> LazyCoroResultWriter[list[WriterResult[T, E, Log[W]]], NoError, W]:
        return LazyCoroResultWriter(thunk)
    
    return batch_allM(
        items,
        handler,
        concurrency=concurrency,
        combine=combine,
        wrap=wrap_wr,
    )


__all__ = ("batch", "batch_all", "batch_w", "batch_all_w", "batchM", "batch_allM")
