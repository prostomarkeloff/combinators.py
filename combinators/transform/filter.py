"""
Filter combinators
==================

Alias для guard combinators для discoverability.
"""

from __future__ import annotations

from collections.abc import Callable

from kungfu import LazyCoroResult

from .._types import Predicate
from ..writer import LazyCoroResultWriter


def filter_or[T, E](
    interp: LazyCoroResult[T, E],
    *,
    predicate: Predicate[T],
    error: Callable[[T], E],
) -> LazyCoroResult[T, E]:
    """
    Turn Ok into Error if value fails predicate. Alias for ensure().
    """
    from ..control.guard import ensure
    return ensure(interp, predicate=predicate, error=error)


def filter_or_w[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    predicate: Predicate[T],
    error: Callable[[T], E],
) -> LazyCoroResultWriter[T, E, W]:
    """
    Turn Ok into Error if value fails predicate. Alias for ensure_w().
    """
    from ..control.guard import ensure_w
    return ensure_w(interp, predicate=predicate, error=error)


__all__ = ("filter_or", "filter_or_w")
