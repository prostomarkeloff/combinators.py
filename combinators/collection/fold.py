"""
Fold combinators
================

Effectful fold с extract + wrap паттерном.
"""

from __future__ import annotations

import typing
from collections.abc import Callable, Coroutine, Sequence

from kungfu import Error, LazyCoroResult, Ok, Result

from ..writer import LazyCoroResultWriter, Log, WriterResult


# ============================================================================
# Generic combinator (extract + wrap pattern)
# ============================================================================


def foldM[M, A, T, E, RawIn, RawOut](
    items: Sequence[A],
    handler: Callable[[T, A], Callable[[], Coroutine[typing.Any, typing.Any, RawIn]]],
    *,
    initial: T,
    extract: Callable[[RawIn], Result[T, E]],
    get_value: Callable[[RawIn], T],
    combine_ok: Callable[[T, list[RawIn]], RawOut],
    combine_err: Callable[[E, list[RawIn]], RawOut],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, RawOut]]], M],
) -> M:
    """Generic fold combinator."""

    async def run() -> RawOut:
        acc = initial
        raws: list[RawIn] = []
        
        for item in items:
            raw = await handler(acc, item)()
            raws.append(raw)
            result = extract(raw)
            match result:
                case Ok(_):
                    acc = get_value(raw)
                case Error(e):
                    return combine_err(e, raws)
        
        return combine_ok(acc, raws)

    return wrap(run)


# ============================================================================
# Sugar for LazyCoroResult
# ============================================================================


def fold[A, T, E](
    items: Sequence[A],
    handler: Callable[[T, A], LazyCoroResult[T, E]],
    *,
    initial: T,
) -> LazyCoroResult[T, E]:
    """Effectful fold: build up state through sequential effects."""

    async def run() -> Result[T, E]:
        acc = initial
        for item in items:
            r = await handler(acc, item)()
            match r:
                case Ok(new_acc):
                    acc = new_acc
                case Error(e):
                    return Error(e)
        return Ok(acc)

    return LazyCoroResult(run)


# ============================================================================
# Sugar for LazyCoroResultWriter
# ============================================================================


def fold_w[A, T, E, W](
    items: Sequence[A],
    handler: Callable[[T, A], LazyCoroResultWriter[T, E, W]],
    *,
    initial: T,
) -> LazyCoroResultWriter[T, E, W]:
    """Effectful fold with log merging."""

    async def run() -> WriterResult[T, E, Log[W]]:
        acc = initial
        merged_log = Log[W]()
        
        for item in items:
            wr = await handler(acc, item)()
            merged_log = merged_log.combine(wr.log)
            match wr.result:
                case Ok(new_acc):
                    acc = new_acc
                case Error(e):
                    return WriterResult(Error(e), merged_log)
        
        return WriterResult(Ok(acc), merged_log)

    return LazyCoroResultWriter(run)


__all__ = ("fold", "fold_w", "foldM")
