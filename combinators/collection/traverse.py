"""Traverse combinators

Monadic traverse with extract + wrap pattern."""

from __future__ import annotations

import typing
from collections.abc import Callable, Coroutine, Sequence

from kungfu import Error, LazyCoroResult, Ok, Result

from .._helpers import extract_writer_result, identity, merge_logs
from ..writer import LazyCoroResultWriter, Log, WriterResult

# Generic combinators (extract + wrap pattern)
def traverseM[M, A, T, E, RawIn, RawOut](
    items: Sequence[A],
    handler: Callable[[A], Callable[[], Coroutine[typing.Any, typing.Any, RawIn]]],
    *,
    extract: Callable[[RawIn], Result[T, E]],
    combine_ok: Callable[[list[tuple[T, RawIn]]], RawOut],
    combine_err: Callable[[E, list[RawIn]], RawOut],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, RawOut]]], M],
) -> M:
    """Generic traverse combinator. Sequential execution."""

    async def run() -> RawOut:
        pairs: list[tuple[T, RawIn]] = []
        raws: list[RawIn] = []
        
        for item in items:
            raw = await handler(item)()
            raws.append(raw)
            result = extract(raw)
            match result:
                case Ok(v):
                    pairs.append((v, raw))
                case Error(e):
                    return combine_err(e, raws)
        
        return combine_ok(pairs)

    return wrap(run)

# Sugar for LazyCoroResult
def traverse[A, T, E](
    items: Sequence[A],
    handler: Callable[[A], LazyCoroResult[T, E]],
) -> LazyCoroResult[list[T], E]:
    """Monadic map: A -> Interp[B]. Sequential to preserve effect order."""
    def combine_ok(pairs: list[tuple[T, Result[T, E]]]) -> Result[list[T], E]:
        return Ok([v for v, _ in pairs])
    
    def combine_err(e: E, raws: list[Result[T, E]]) -> Result[list[T], E]:
        _ = raws
        return Error(e)
    
    return traverseM(
        items,
        handler,
        extract=identity,
        combine_ok=combine_ok,
        combine_err=combine_err,
        wrap=LazyCoroResult,
    )

def traverse_par[A, T, E](
    items: Sequence[A],
    handler: Callable[[A], LazyCoroResult[T, E]],
    *,
    concurrency: int = 10,
) -> LazyCoroResult[list[T], E]:
    """Parallel traverse: order doesn't matter, speed matters."""
    from ..concurrency.batch import batch
    return batch(items, handler, concurrency=concurrency)

# Sugar for LazyCoroResultWriter
def traverse_writer[A, T, E, W](
    items: Sequence[A],
    handler: Callable[[A], LazyCoroResultWriter[T, E, W]],
) -> LazyCoroResultWriter[list[T], E, W]:
    """Monadic map with log merging."""
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
    
    def wrap_wr(
        fn: Callable[[], Coroutine[typing.Any, typing.Any, WriterResult[list[T], E, Log[W]]]]
    ) -> LazyCoroResultWriter[list[T], E, W]:
        return LazyCoroResultWriter(fn)
    
    return traverseM(
        items,
        handler,
        extract=extract_writer_result,
        combine_ok=combine_ok,
        combine_err=combine_err,
        wrap=wrap_wr,
    )

def traverse_par_writer[A, T, E, W](
    items: Sequence[A],
    handler: Callable[[A], LazyCoroResultWriter[T, E, W]],
    *,
    concurrency: int = 10,
) -> LazyCoroResultWriter[list[T], E, W]:
    """Parallel traverse with log merging."""
    from ..concurrency.batch import batch_writer
    return batch_writer(items, handler, concurrency=concurrency)

__all__ = ("traverse", "traverse_par", "traverse_writer", "traverse_par_writer", "traverseM")
