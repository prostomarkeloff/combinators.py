"""
Zip combinators
===============

Комбинаторы для zip с extract + wrap паттерном.
"""

from __future__ import annotations

import asyncio
import typing
from collections.abc import Callable, Coroutine

from kungfu import Error, LazyCoroResult, Ok, Result

from .._helpers import extract_writer_result, identity, merge_logs
from ..writer import LazyCoroResultWriter, Log, WriterResult


# ============================================================================
# Generic combinators (extract + wrap pattern)
# ============================================================================


def zip_parM[M, T, E, RawIn, RawOut](
    *interps: Callable[[], Coroutine[typing.Any, typing.Any, RawIn]],
    extract: Callable[[RawIn], Result[T, E]],
    combine_ok: Callable[[list[tuple[T, RawIn]]], RawOut],
    combine_err: Callable[[E, list[RawIn]], RawOut],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, RawOut]]], M],
) -> M:
    """
    Generic zip_par combinator.
    
    Run in parallel, return tuple.
    """

    async def run() -> RawOut:
        raws: list[RawIn] = await asyncio.gather(*(i() for i in interps))
        
        pairs: list[tuple[T, RawIn]] = []
        for raw in raws:
            result = extract(raw)
            match result:
                case Ok(v):
                    pairs.append((v, raw))
                case Error(e):
                    return combine_err(e, raws)
        
        return combine_ok(pairs)

    return wrap(run)


# ============================================================================
# Sugar for LazyCoroResult
# ============================================================================


def zip_par[T, E](*interps: LazyCoroResult[T, E]) -> LazyCoroResult[tuple[T, ...], E]:
    """
    Run in parallel, return tuple.
    """
    def combine_ok(pairs: list[tuple[T, Result[T, E]]]) -> Result[tuple[T, ...], E]:
        return Ok(tuple(v for v, _ in pairs))
    
    def combine_err(e: E, raws: list[Result[T, E]]) -> Result[tuple[T, ...], E]:
        _ = raws
        return Error(e)
    
    return zip_parM(
        *interps,
        extract=identity,
        combine_ok=combine_ok,
        combine_err=combine_err,
        wrap=LazyCoroResult,
    )


def zip_with[T, R, E](
    *interps: LazyCoroResult[T, E],
    combiner: Callable[[tuple[T, ...]], R],
) -> LazyCoroResult[R, E]:
    """
    Run in parallel, transform results with function.
    """
    return zip_par(*interps).map(combiner)


# ============================================================================
# Sugar for LazyCoroResultWriter
# ============================================================================


def zip_par_w[T, E, W](
    *interps: LazyCoroResultWriter[T, E, W],
) -> LazyCoroResultWriter[tuple[T, ...], E, W]:
    """
    Run in parallel, return tuple. Merge logs.
    """
    def combine_ok(
        pairs: list[tuple[T, WriterResult[T, E, Log[W]]]]
    ) -> WriterResult[tuple[T, ...], E, Log[W]]:
        values = tuple(v for v, _ in pairs)
        merged = merge_logs(wr.log for _, wr in pairs)
        return WriterResult(Ok(values), merged)
    
    def combine_err(
        e: E,
        raws: list[WriterResult[T, E, Log[W]]],
    ) -> WriterResult[tuple[T, ...], E, Log[W]]:
        merged = merge_logs(wr.log for wr in raws)
        return WriterResult(Error(e), merged)
    
    def wrap_wr(
        thunk: Callable[[], Coroutine[typing.Any, typing.Any, WriterResult[tuple[T, ...], E, Log[W]]]]
    ) -> LazyCoroResultWriter[tuple[T, ...], E, W]:
        return LazyCoroResultWriter(thunk)
    
    return zip_parM(
        *interps,
        extract=extract_writer_result,
        combine_ok=combine_ok,
        combine_err=combine_err,
        wrap=wrap_wr,
    )


def zip_with_w[T, R, E, W](
    *interps: LazyCoroResultWriter[T, E, W],
    combiner: Callable[[tuple[T, ...]], R],
) -> LazyCoroResultWriter[R, E, W]:
    """
    Run in parallel, transform results with function. Merge logs.
    """
    return zip_par_w(*interps).map(combiner)


__all__ = ("zip_par", "zip_with", "zip_par_w", "zip_with_w", "zip_parM")
