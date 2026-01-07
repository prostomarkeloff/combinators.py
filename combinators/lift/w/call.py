"""
Вызов функций для Writer монады.

Call и декораторы для функций возвращающих WriterResult.
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
    """
    Call function returning WriterResult.
    
    **When to use:** When you have an async function that returns WriterResult
    and you want to lift it into LazyCoroResultWriter.
    
    Example:
        from combinators import lift as L
        
        async def fetch_with_logs(uid: int) -> WriterResult[User, Error, Log[str]]:
            return WriterResult(Ok(User(id=uid)), Log(["fetched"]))
        
        writer = L.w.call(fetch_with_logs, 42)
        result = await L.down(writer)
    
    **Grammar:** `L.w.call(func, *args)` reads as "call Writer function with args"
    """
    async def run() -> WriterResult[T, E, Log[W]]:
        return await func(*args, **kwargs)
    
    return LazyCoroResultWriter(run)


def lifted[T, E, W, **P](
    func: Callable[P, Awaitable[WriterResult[T, E, Log[W]]]],
) -> Callable[P, LazyCoroResultWriter[T, E, W]]:
    """
    Decorator for Writer functions.
    
    **When to use:** For frequently-used functions that return WriterResult.
    
    Example:
        from combinators import lift as L
        
        @L.w.lifted
        async def fetch_with_logs(uid: int) -> WriterResult[User, Error, Log[str]]:
            return WriterResult(Ok(User(id=uid)), Log(["fetched"]))
        
        # Usage: fetch_with_logs now returns LazyCoroResultWriter
        result = await L.down(fetch_with_logs(42))
    
    **Grammar:** `@L.w.lifted` reads as "lifted Writer function"
    """
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> LazyCoroResultWriter[T, E, W]:
        return call(func, *args, **kwargs)
    
    return wrapper


__all__ = (
    "call",
    "lifted",
)
