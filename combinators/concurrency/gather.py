"""
Gather combinators
==================

Комбинаторы для gather с extract + wrap паттерном.
"""

from __future__ import annotations

import asyncio
import typing
from collections.abc import Callable, Coroutine

from kungfu import Error, LazyCoroResult, Ok, Result

from .._helpers import extract_writer_result, identity
from ..writer import LazyCoroResultWriter, Log, WriterResult


# ============================================================================
# Generic combinators (extract + wrap pattern)
# ============================================================================


def gather2M[M, A, B, E, RawA, RawB, RawOut](
    a: Callable[[], Coroutine[typing.Any, typing.Any, RawA]],
    b: Callable[[], Coroutine[typing.Any, typing.Any, RawB]],
    *,
    extract_a: Callable[[RawA], Result[A, E]],
    extract_b: Callable[[RawB], Result[B, E]],
    combine_ok: Callable[[A, B, RawA, RawB], RawOut],
    combine_err: Callable[[E], RawOut],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, RawOut]]], M],
) -> M:
    """Generic gather2 combinator."""

    async def run() -> RawOut:
        raw_a, raw_b = await asyncio.gather(a(), b())
        
        result_a = extract_a(raw_a)
        match result_a:
            case Error(e):
                return combine_err(e)
            case Ok(val_a):
                pass
        
        result_b = extract_b(raw_b)
        match result_b:
            case Error(e):
                return combine_err(e)
            case Ok(val_b):
                pass
        
        return combine_ok(val_a, val_b, raw_a, raw_b)

    return wrap(run)


def gather3M[M, A, B, C, E, RawA, RawB, RawC, RawOut](
    a: Callable[[], Coroutine[typing.Any, typing.Any, RawA]],
    b: Callable[[], Coroutine[typing.Any, typing.Any, RawB]],
    c: Callable[[], Coroutine[typing.Any, typing.Any, RawC]],
    *,
    extract_a: Callable[[RawA], Result[A, E]],
    extract_b: Callable[[RawB], Result[B, E]],
    extract_c: Callable[[RawC], Result[C, E]],
    combine_ok: Callable[[A, B, C, RawA, RawB, RawC], RawOut],
    combine_err: Callable[[E], RawOut],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, RawOut]]], M],
) -> M:
    """Generic gather3 combinator."""

    async def run() -> RawOut:
        raw_a, raw_b, raw_c = await asyncio.gather(a(), b(), c())
        
        result_a = extract_a(raw_a)
        match result_a:
            case Error(e):
                return combine_err(e)
            case Ok(val_a):
                pass
        
        result_b = extract_b(raw_b)
        match result_b:
            case Error(e):
                return combine_err(e)
            case Ok(val_b):
                pass
        
        result_c = extract_c(raw_c)
        match result_c:
            case Error(e):
                return combine_err(e)
            case Ok(val_c):
                pass
        
        return combine_ok(val_a, val_b, val_c, raw_a, raw_b, raw_c)

    return wrap(run)


# ============================================================================
# Sugar for LazyCoroResult
# ============================================================================


def gather2[A, B, E](
    a: LazyCoroResult[A, E],
    b: LazyCoroResult[B, E],
) -> LazyCoroResult[tuple[A, B], E]:
    """Run two concurrently, preserve heterogeneous types."""
    def combine_ok(
        val_a: A, val_b: B,
        raw_a: Result[A, E], raw_b: Result[B, E],
    ) -> Result[tuple[A, B], E]:
        _ = (raw_a, raw_b)
        return Ok((val_a, val_b))
    
    def combine_err(e: E) -> Result[tuple[A, B], E]:
        return Error(e)
    
    return gather2M(
        a, b,
        extract_a=identity,
        extract_b=identity,
        combine_ok=combine_ok,
        combine_err=combine_err,
        wrap=LazyCoroResult,
    )


def gather3[A, B, C, E](
    a: LazyCoroResult[A, E],
    b: LazyCoroResult[B, E],
    c: LazyCoroResult[C, E],
) -> LazyCoroResult[tuple[A, B, C], E]:
    """Run three concurrently, preserve heterogeneous types."""
    def combine_ok(
        val_a: A, val_b: B, val_c: C,
        raw_a: Result[A, E], raw_b: Result[B, E], raw_c: Result[C, E],
    ) -> Result[tuple[A, B, C], E]:
        _ = (raw_a, raw_b, raw_c)
        return Ok((val_a, val_b, val_c))
    
    def combine_err(e: E) -> Result[tuple[A, B, C], E]:
        return Error(e)
    
    return gather3M(
        a, b, c,
        extract_a=identity,
        extract_b=identity,
        extract_c=identity,
        combine_ok=combine_ok,
        combine_err=combine_err,
        wrap=LazyCoroResult,
    )


# ============================================================================
# Sugar for LazyCoroResultWriter
# ============================================================================


def gather2_w[A, B, E, W](
    a: LazyCoroResultWriter[A, E, W],
    b: LazyCoroResultWriter[B, E, W],
) -> LazyCoroResultWriter[tuple[A, B], E, W]:
    """Run two concurrently, merge logs."""
    def combine_ok(
        val_a: A, val_b: B,
        raw_a: WriterResult[A, E, Log[W]],
        raw_b: WriterResult[B, E, Log[W]],
    ) -> WriterResult[tuple[A, B], E, Log[W]]:
        merged = raw_a.log.combine(raw_b.log)
        return WriterResult(Ok((val_a, val_b)), merged)
    
    def combine_err(e: E) -> WriterResult[tuple[A, B], E, Log[W]]:
        return WriterResult(Error(e), Log[W]())
    
    def wrap_wr(
        thunk: Callable[[], Coroutine[typing.Any, typing.Any, WriterResult[tuple[A, B], E, Log[W]]]]
    ) -> LazyCoroResultWriter[tuple[A, B], E, W]:
        return LazyCoroResultWriter(thunk)
    
    return gather2M(
        a, b,
        extract_a=extract_writer_result,
        extract_b=extract_writer_result,
        combine_ok=combine_ok,
        combine_err=combine_err,
        wrap=wrap_wr,
    )


def gather3_w[A, B, C, E, W](
    a: LazyCoroResultWriter[A, E, W],
    b: LazyCoroResultWriter[B, E, W],
    c: LazyCoroResultWriter[C, E, W],
) -> LazyCoroResultWriter[tuple[A, B, C], E, W]:
    """Run three concurrently, merge logs."""
    def combine_ok(
        val_a: A, val_b: B, val_c: C,
        raw_a: WriterResult[A, E, Log[W]],
        raw_b: WriterResult[B, E, Log[W]],
        raw_c: WriterResult[C, E, Log[W]],
    ) -> WriterResult[tuple[A, B, C], E, Log[W]]:
        merged = raw_a.log.combine(raw_b.log).combine(raw_c.log)
        return WriterResult(Ok((val_a, val_b, val_c)), merged)
    
    def combine_err(e: E) -> WriterResult[tuple[A, B, C], E, Log[W]]:
        return WriterResult(Error(e), Log[W]())
    
    def wrap_wr(
        thunk: Callable[[], Coroutine[typing.Any, typing.Any, WriterResult[tuple[A, B, C], E, Log[W]]]]
    ) -> LazyCoroResultWriter[tuple[A, B, C], E, W]:
        return LazyCoroResultWriter(thunk)
    
    return gather3M(
        a, b, c,
        extract_a=extract_writer_result,
        extract_b=extract_writer_result,
        extract_c=extract_writer_result,
        combine_ok=combine_ok,
        combine_err=combine_err,
        wrap=wrap_wr,
    )


__all__ = ("gather2", "gather3", "gather2_w", "gather3_w", "gather2M", "gather3M")
