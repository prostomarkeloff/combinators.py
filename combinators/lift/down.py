"""
Lower monad to value.

Functions for executing Interp and extracting result as Result or value.
"""

from __future__ import annotations

from kungfu import Error, Ok, Result

from .._types import Interp

async def to_result[T, E](interp: Interp[T, E]) -> Result[T, E]:
    """Run interp and return Result."""
    return await interp()

async def unsafe[T, E](interp: Interp[T, E]) -> T:
    """Run and unwrap, raises on Error."""
    result = await interp()
    return result.unwrap()

async def or_else[T, E](interp: Interp[T, E], default: T) -> T:
    """Run and return value or default."""
    result = await interp()
    match result:
        case Ok(v):
            return v
        case Error(_):
            return default

__all__ = (
    "to_result",
    "unsafe",
    "or_else",
)
