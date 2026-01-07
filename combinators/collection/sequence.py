"""Sequence combinators

Structure flipping with extract + wrap pattern."""

from __future__ import annotations

from collections.abc import Sequence

from kungfu import LazyCoroResult

from ..writer import LazyCoroResultWriter

def sequence[T, E](interps: Sequence[LazyCoroResult[T, E]]) -> LazyCoroResult[list[T], E]:
    """
    Flip structure: [Interp[T]] -> Interp[[T]].
    
    Implemented as traverse(id).
    """
    from .traverse import traverse
    return traverse(interps, handler=lambda i: i)

def sequence_writer[T, E, W](
    interps: Sequence[LazyCoroResultWriter[T, E, W]],
) -> LazyCoroResultWriter[list[T], E, W]:
    """Flip structure with log merging."""
    from .traverse import traverse_writer
    return traverse_writer(interps, handler=lambda i: i)

__all__ = ("sequence", "sequence_writer")
