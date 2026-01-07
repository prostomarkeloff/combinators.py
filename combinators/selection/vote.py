"""
Vote combinators
================

Голосование с судьёй.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

from kungfu import LazyCoroResult, Ok, Result

from ..concurrency.parallel import parallel, parallel_w
from ..writer import LazyCoroResultWriter, Log, WriterResult


def vote[T, E](
    candidates: Sequence[LazyCoroResult[T, E]],
    *,
    judge: Callable[[Sequence[T]], Awaitable[T]],
) -> LazyCoroResult[T, E]:
    """Run all candidates, let async judge pick winner."""

    async def pick(values: list[T]) -> Result[T, E]:
        winner = await judge(values)
        return Ok(winner)

    return parallel(*candidates).then(pick)


def vote_w[T, E, W](
    candidates: Sequence[LazyCoroResultWriter[T, E, W]],
    *,
    judge: Callable[[Sequence[T]], Awaitable[T]],
) -> LazyCoroResultWriter[T, E, W]:
    """Run all candidates, let async judge pick winner. Merges logs."""

    async def pick(values: list[T]) -> WriterResult[T, E, Log[W]]:
        winner = await judge(values)
        return WriterResult(Ok(winner), Log[W]())

    return parallel_w(*candidates).then(pick)


__all__ = ("vote", "vote_w")
