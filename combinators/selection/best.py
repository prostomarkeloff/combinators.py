"""Best-of combinators

Selection of best result."""

from __future__ import annotations

from collections.abc import Sequence

from kungfu import LazyCoroResult

from .._types import Selector
from ..concurrency.parallel import parallel, parallel_writer
from ..writer import LazyCoroResultWriter

def best_of[T, E](
    interp: LazyCoroResult[T, E],
    *,
    n: int,
    key: Selector[T, float],
) -> LazyCoroResult[T, E]:
    """Run N times, pick best by key."""
    copies = [interp for _ in range(n)]
    return parallel(*copies).map(lambda values: max(values, key=key))

def best_of_many[T, E](
    candidates: Sequence[LazyCoroResult[T, E]],
    *,
    key: Selector[T, float],
) -> LazyCoroResult[T, E]:
    """Run all candidates, pick best by key."""
    return parallel(*candidates).map(lambda values: max(values, key=key))

def best_of_writer[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    n: int,
    key: Selector[T, float],
) -> LazyCoroResultWriter[T, E, W]:
    """Run N times, pick best by key. Merges logs."""
    copies = [interp for _ in range(n)]
    return parallel_writer(*copies).map(lambda values: max(values, key=key))

def best_of_many_writer[T, E, W](
    candidates: Sequence[LazyCoroResultWriter[T, E, W]],
    *,
    key: Selector[T, float],
) -> LazyCoroResultWriter[T, E, W]:
    """Run all candidates, pick best by key. Merges logs."""
    return parallel_writer(*candidates).map(lambda values: max(values, key=key))

__all__ = ("best_of", "best_of_many", "best_of_writer", "best_of_many_writer")
