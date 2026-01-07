"""
Lower Writer monad.

Functions for executing LazyCoroResultWriter and extracting results.
"""

from __future__ import annotations

from kungfu import Error, Ok, Result

from ...writer import LazyCoroResultWriter, Log, WriterResult

async def to_writer_result[T, E, W](
    writer: LazyCoroResultWriter[T, E, W],
) -> WriterResult[T, E, Log[W]]:
    """Run Writer and return WriterResult."""
    return await writer()

async def to_result[T, E, W](
    writer: LazyCoroResultWriter[T, E, W],
) -> Result[T, E]:
    """Run Writer and return only Result (discard log)."""
    wr = await writer()
    return wr.result

async def to_tuple[T, E, W](
    writer: LazyCoroResultWriter[T, E, W],
) -> tuple[Result[T, E], Log[W]]:
    """Run Writer and return (result, log) tuple."""
    wr = await writer()
    return (wr.result, wr.log)

async def unsafe[T, E, W](
    writer: LazyCoroResultWriter[T, E, W],
) -> tuple[T, Log[W]]:
    """Run and unwrap, raises on Error. Returns (value, log)."""
    wr = await writer()
    return (wr.result.unwrap(), wr.log)

async def or_else[T, E, W](
    writer: LazyCoroResultWriter[T, E, W],
    default: T,
) -> tuple[T, Log[W]]:
    """Run and return (value or default, log)."""
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

