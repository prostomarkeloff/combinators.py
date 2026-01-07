"""
Опускание Writer монады.

Функции для выполнения LazyCoroResultWriter и извлечения результата.
"""

from __future__ import annotations

from kungfu import Error, Ok, Result

from ...writer import LazyCoroResultWriter, Log, WriterResult


async def to_writer_result[T, E, W](
    writer: LazyCoroResultWriter[T, E, W],
) -> WriterResult[T, E, Log[W]]:
    """
    Run Writer and return WriterResult.
    
    **When to use:** Standard way to execute a Writer and get both result and log.
    
    Example:
        from combinators import lift as L
        
        writer = L.w.up.pure(User(id=42), log=["created"])
        wr = await L.w.down.to_writer_result(writer)
        # WriterResult(Ok(User(id=42)), Log(["created"]))
    
    **Grammar:** `await L.w.down.to_writer_result(writer)` reads as "run down to writer result"
    """
    return await writer()


async def to_result[T, E, W](
    writer: LazyCoroResultWriter[T, E, W],
) -> Result[T, E]:
    """
    Run Writer and return only Result (discard log).
    
    **When to use:** When you only care about the result, not the log.
    
    Example:
        from combinators import lift as L
        
        writer = L.w.up.pure(User(id=42), log=["created"])
        result = await L.w.down.to_result(writer)
        # Ok(User(id=42)) - log is discarded
    
    **Grammar:** `await L.w.down.to_result(writer)` reads as "run down to result (discard log)"
    """
    wr = await writer()
    return wr.result


async def to_tuple[T, E, W](
    writer: LazyCoroResultWriter[T, E, W],
) -> tuple[Result[T, E], Log[W]]:
    """
    Run Writer and return (result, log) tuple.
    
    **When to use:** When you want to separately handle result and log.
    
    Example:
        from combinators import lift as L
        
        writer = L.w.up.pure(User(id=42), log=["created"])
        result, log = await L.w.down.to_tuple(writer)
        # result: Ok(User(id=42))
        # log: Log(["created"])
    
    **Grammar:** `await L.w.down.to_tuple(writer)` reads as "run down to tuple"
    """
    wr = await writer()
    return (wr.result, wr.log)


async def unsafe[T, E, W](
    writer: LazyCoroResultWriter[T, E, W],
) -> tuple[T, Log[W]]:
    """
    Run and unwrap, raises on Error. Returns (value, log).
    
    **When to use:** When you're certain the computation will succeed.
    
    Example:
        from combinators import lift as L
        
        writer = L.w.up.pure(User(id=42), log=["created"])
        value, log = await L.w.down.unsafe(writer)
        # value: User(id=42)
        # log: Log(["created"])
    
    **Grammar:** `await L.w.down.unsafe(writer)` reads as "run down unsafe (may raise)"
    
    NOTE: Raises an exception if the Result is an Error.
    """
    wr = await writer()
    return (wr.result.unwrap(), wr.log)


async def or_else[T, E, W](
    writer: LazyCoroResultWriter[T, E, W],
    default: T,
) -> tuple[T, Log[W]]:
    """
    Run and return (value or default, log).
    
    **When to use:** When you want a fallback value but still keep the log.
    
    Example:
        from combinators import lift as L
        
        writer = L.w.up.fail(NotFoundError(), log=["lookup failed"])
        value, log = await L.w.down.or_else(writer, default=User(id=0))
        # value: User(id=0)
        # log: Log(["lookup failed"])
    
    **Grammar:** `await L.w.down.or_else(writer, default=...)` reads as "run down or else default"
    """
    wr = await writer()
    match wr.result:
        case Ok(v):
            return (v, wr.log)
        case Error(_):
            return (default, wr.log)


__all__ = (
    "to_writer_result",
    "to_result",
    "to_tuple",
    "unsafe",
    "or_else",
)
