"""Call functions with automatic lifting."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec

from kungfu import LazyCoroResult, Result

from .._types import Interp

P = ParamSpec("P")

def wrap_async[T, E](
    fn: Callable[[], Awaitable[Result[T, E]]],
) -> Interp[T, E]:
    """Wrap lazy async computation (fn) into Interp."""
    async def run() -> Result[T, E]:
        return await fn()

    return LazyCoroResult(run)

def lifted[T, E, **P](
    func: Callable[P, Awaitable[Result[T, E]]],
) -> Callable[P, Interp[T, E]]:
    """Decorator that wraps async function to return Interp."""
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Interp[T, E]:
        return wrap_async(lambda: func(*args, **kwargs))
    
    return wrapper

def call[T, E, **P](
    func: Callable[P, Awaitable[Result[T, E]]],
    *args: P.args,
    **kwargs: P.kwargs,
) -> Interp[T, E]:
    """Call async function with arguments and lift into Interp."""
    return wrap_async(lambda: func(*args, **kwargs))

__all__ = (
    "call",
    "lifted",
    "wrap_async",
)
