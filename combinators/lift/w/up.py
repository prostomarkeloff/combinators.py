"""
Подъем значений в Writer монаду (LazyCoroResultWriter).

Writer-specific lift functions для работы с LazyCoroResultWriter[T, E, W].
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
    """
    Lift value into Writer with optional log.
    
    **When to use:** When you have a plain value and want to create
    a Writer monad with an associated log.
    
    Example:
        from combinators import lift as L
        
        user = L.w.up.pure(User(id=42), log=["created user"])
        result = await L.down(user)
        # WriterResult(Ok(User(id=42)), Log(["created user"]))
    
    **Grammar:** `L.w.up.pure(value, log=...)` reads as "lift up into Writer pure value"
    """
    async def run() -> WriterResult[T, object, Log[W]]:
        return WriterResult(Ok(value), Log(log or []))
    
    return LazyCoroResultWriter(run)


def tell[W](log: list[W]) -> LazyCoroResultWriter[None, object, W]:
    """
    Create Writer with only log, no value.
    
    **When to use:** When you just want to log something without producing a value.
    Useful for side-effect logging in a pipeline.
    
    Example:
        from combinators import lift as L
        
        logged = L.w.up.tell(["operation started"])
        # WriterResult(Ok(None), Log(["operation started"]))
    
    **Grammar:** `L.w.up.tell(log)` reads as "lift up tell (log only)"
    """
    return pure(None, log=log)


def from_result[T, E, W](
    result: Result[T, E],
    *,
    log: list[W] | None = None,
) -> LazyCoroResultWriter[T, E, W]:
    """
    Lift Result into Writer with log.
    
    **When to use:** When you have a Result and want to add logging context.
    
    Example:
        from combinators import lift as L
        
        result = Ok(User(id=42))
        writer = L.w.up.from_result(result, log=["fetched from db"])
        # WriterResult(Ok(User(id=42)), Log(["fetched from db"]))
    
    **Grammar:** `L.w.up.from_result(result, log=...)` reads as "lift up from result with log"
    """
    async def run() -> WriterResult[T, E, Log[W]]:
        return WriterResult(result, Log(log or []))
    
    return LazyCoroResultWriter(run)


def fail[E, W](
    error: E,
    *,
    log: list[W] | None = None,
) -> LazyCoroResultWriter[Never, E, W]:
    """
    Create always-failing Writer with optional log.
    
    **When to use:** When you need to fail with an error and optionally log the failure.
    
    Example:
        from combinators import lift as L
        
        failed = L.w.up.fail(
            ValidationError("bad input"),
            log=["validation failed"]
        )
    
    **Grammar:** `L.w.up.fail(error, log=...)` reads as "lift up fail with log"
    """
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
