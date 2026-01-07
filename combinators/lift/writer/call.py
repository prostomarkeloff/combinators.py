"""
Call functions for Writer monad.

Call and decorators for functions returning WriterResult.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec

from ...writer import LazyCoroResultWriter, Log, WriterResult

P = ParamSpec("P")

def call[T, E, W, **P](
    func: Callable[P, Awaitable[WriterResult[T, E, Log[W]]]],
    *args: P.args,
    **kwargs: P.kwargs,
) -> LazyCoroResultWriter[T, E, W]:
    """Call function returning WriterResult."""
    async def run() -> WriterResult[T, E, Log[W]]:
        return await func(*args, **kwargs)
    
    return LazyCoroResultWriter(run)

def lifted[T, E, W, **P](
    func: Callable[P, Awaitable[WriterResult[T, E, Log[W]]]],
) -> Callable[P, LazyCoroResultWriter[T, E, W]]:
    """Decorator for Writer functions."""
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> LazyCoroResultWriter[T, E, W]:
        return call(func, *args, **kwargs)
    
    return wrapper

__all__ = (
    "call",
    "lifted",
)

