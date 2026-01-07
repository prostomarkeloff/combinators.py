"""Internal helpers for combinators.

Common functions used across multiple combinator modules.
These are not part of the public API but can be used for creating custom monads."""

from __future__ import annotations

import typing
from collections.abc import Callable, Coroutine, Iterable

from kungfu import Result

from .writer import LazyCoroResultWriter, Log, WriterResult

# Identity function
def identity[T](x: T) -> T:
    """Identity function: returns its argument unchanged."""
    return x

# Extract functions (Raw -> Result[T, E])
def extract_result[T, E](r: Result[T, E]) -> Result[T, E]:
    """
    Extract Result from Result (identity for LazyCoroResult).
    
    LazyCoroResult's Raw type IS Result[T, E], so extract is identity.
    """
    return r

def extract_writer_result[T, E, W](wr: WriterResult[T, E, Log[W]]) -> Result[T, E]:
    """
    Extract Result from WriterResult.
    
    LazyCoroResultWriter's Raw type is WriterResult[T, E, Log[W]].
    """
    return wr.result

# Wrap functions (Fn -> M)
def wrap_lazy_coro_result_writer[T, E, W](
    fn: Callable[[], Coroutine[typing.Any, typing.Any, WriterResult[T, E, Log[W]]]]
) -> LazyCoroResultWriter[T, E, W]:
    """
    Wrap fn into LazyCoroResultWriter.
    
    This is the standard wrap function for LazyCoroResultWriter sugar functions.
    """
    return LazyCoroResultWriter(fn)

# Log merging helpers
def merge_logs[W](logs: Iterable[Log[W]]) -> Log[W]:
    """
    Merge multiple logs into one using monoidal combine.
    
    Usage:
        logs = [wr.log for wr in writer_results]
        merged = merge_logs(logs)
    """
    result = Log[W]()
    for log in logs:
        result = result.combine(log)
    return result

def merge_writer_logs[T, E, W](wrs: Iterable[WriterResult[T, E, Log[W]]]) -> Log[W]:
    """
    Extract and merge logs from multiple WriterResults.
    
    Convenience function for common pattern:
        merged_log = Log[W]()
        for wr in wrs:
            merged_log = merged_log.combine(wr.log)
    """
    return merge_logs(wr.log for wr in wrs)

__all__ = (
    # Identity
    "identity",
    # Extract functions
    "extract_result",
    "extract_writer_result",
    # Wrap functions
    "wrap_lazy_coro_result_writer",
    # Log merging
    "merge_logs",
    "merge_writer_logs",
)

