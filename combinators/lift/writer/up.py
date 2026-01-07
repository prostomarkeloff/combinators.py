"""
Lift values into Writer monad (LazyCoroResultWriter).

Writer-specific lift functions for working with LazyCoroResultWriter[T, E, W].
"""

from __future__ import annotations

from typing import Never

from kungfu import Ok, Result

from ...writer import LazyCoroResultWriter, Log, WriterResult

def pure[T, W](
    value: T,
    *,
    log: list[W] | None = None,
) -> LazyCoroResultWriter[T, object, W]:
    """Lift value into Writer with optional log."""
    async def run() -> WriterResult[T, object, Log[W]]:
        return WriterResult(Ok(value), Log(log or []))
    
    return LazyCoroResultWriter(run)

def tell[W](log: list[W]) -> LazyCoroResultWriter[None, object, W]:
    """Create Writer with only log, no value."""
    return pure(None, log=log)

def from_result[T, E, W](
    result: Result[T, E],
    *,
    log: list[W] | None = None,
) -> LazyCoroResultWriter[T, E, W]:
    """Lift Result into Writer with log."""
    async def run() -> WriterResult[T, E, Log[W]]:
        return WriterResult(result, Log(log or []))
    
    return LazyCoroResultWriter(run)

def fail[E, W](
    error: E,
    *,
    log: list[W] | None = None,
) -> LazyCoroResultWriter[Never, E, W]:
    """Create always-failing Writer with optional log."""
    from kungfu import Error
    
    async def run() -> WriterResult[Never, E, Log[W]]:
        return WriterResult(Error(error), Log(log or []))
    
    return LazyCoroResultWriter(run)

__all__ = (
    "pure",
    "tell",
    "from_result",
    "fail",
)

