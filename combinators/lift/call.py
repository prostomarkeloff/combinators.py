"""Call functions with automatic lifting."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec

from kungfu import LazyCoroResult, Result

from .._types import Interp
from .up import catching_async

P = ParamSpec("P")
P_Catch = ParamSpec("P_Catch")

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

def call_catching[T, E, **P_Catch](
    func: Callable[P_Catch, Awaitable[T]],
    on_error: Callable[[Exception], E],
    *args: P_Catch.args,
    **kwargs: P_Catch.kwargs,
) -> Interp[T, E]:
    """Call async function with arguments, catch exceptions and lift into Interp.
    
    Use this when your function does NOT return Result[T, E] but can raise exceptions.
    
    Example:
        # Function that can raise
        async def fetch_user(user_id: int) -> User:
            return await api.get(f"/users/{user_id}")  # May raise HTTPException
        
        # Lift it with exception catching
        result = L.call_catching(
            fetch_user,
            on_error=lambda e: APIError(str(e)),
            user_id=42,
        )
    """
    return catching_async(
        lambda: func(*args, **kwargs),
        on_error=on_error,
    )

__all__ = (
    "call",
    "call_catching",
    "lifted",
    "wrap_async",
)
