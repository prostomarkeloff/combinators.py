"""Replicate combinators

Multiple execution with extract + wrap pattern."""

from __future__ import annotations

from kungfu import LazyCoroResult

from ..writer import LazyCoroResultWriter

def replicate[T, E](
    interp: LazyCoroResult[T, E],
    *,
    n: int,
) -> LazyCoroResult[list[T], E]:
    """Run N times, collect all results (Haskell's replicateM)."""
    if n < 0:
        raise ValueError(f"replicate(): n must be >= 0, got {n}")
    
    from .sequence import sequence
    return sequence([interp for _ in range(n)])

def replicate_writer[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    n: int,
) -> LazyCoroResultWriter[list[T], E, W]:
    """Run N times, collect all results with log merging."""
    if n < 0:
        raise ValueError(f"replicate_writer(): n must be >= 0, got {n}")
    
    from .sequence import sequence_writer
    return sequence_writer([interp for _ in range(n)])

__all__ = ("replicate", "replicate_writer")
