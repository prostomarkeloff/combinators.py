"""
Вызов функций с автоматическим лифтингом.

Функции и декораторы для удобного вызова async функций и автоматического
подъема результата в монадический контекст.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec

from kungfu import LazyCoroResult, Result

from .._types import Interp

P = ParamSpec("P")


def wrap_async[T, E](
    thunk: Callable[[], Awaitable[Result[T, E]]],
) -> Interp[T, E]:
    """
    Wrap lazy async computation (thunk) into Interp.
    
    **When to use:** When you have a zero-arg callable (thunk) that returns
    an awaitable Result. For direct function calls with arguments, prefer `call()`.
    
    **Prefer `call()` for locality:**
        # ✅ Better: lift at call site
        L.call(fetch_user_impl, user_id)
        
        # ⚠️ Use wrap_async only when you need a thunk (zero-arg callable)
        L.call.wrap_async(lambda: fetch_user_impl(user_id))
    
    Example:
        from combinators import lift as L
        
        L.call.wrap_async(lambda: fetch_user(user_id))
        # or use L.call() for direct calls:
        L.call(fetch_user, user_id)
    
    **Grammar:** `L.call.wrap_async(thunk)` reads as "call wrap async thunk"
    
    NOTE: thunk must be a zero-arg callable (lambda) for laziness.
          Direct coroutine would execute immediately on creation.
    """
    async def run() -> Result[T, E]:
        return await thunk()

    return LazyCoroResult(run)


def lifted[T, E, **P](
    func: Callable[P, Awaitable[Result[T, E]]],
) -> Callable[P, Interp[T, E]]:
    """
    Decorator for automatically wrapping async functions to return Interp.
    
    **When to use:** For frequently-used functions where you want them to return
    Interp directly. Prefer `call()` at call site for better locality,
    but `@lifted` is useful for common utilities.
    
    **Design choice:**
    - ✅ `call()` at call site = maximum locality, pure functions
    - ✅ `@lifted` decorator = convenient for frequently-used functions
    
    Example:
        from combinators import lift as L
        
        @L.lifted
        async def fetch_user(user_id: int) -> Result[User, APIError]:
            await asyncio.sleep(0.01)
            return Ok(User(id=user_id, name="User"))
        
        # Usage: fetch_user now returns Interp directly
        result = await L.down(fetch_user(42))
        
        # Alternative with L.call() for locality:
        async def fetch_user_impl(user_id: int) -> Result[User, APIError]:
            ...
        
        result = await L.down(L.call(fetch_user_impl, 42))
    
    **Grammar:** `@L.lifted` reads as "lifted function"
    """
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Interp[T, E]:
        return wrap_async(lambda: func(*args, **kwargs))
    
    return wrapper


def call[T, E, **P](
    func: Callable[P, Awaitable[Result[T, E]]],
    *args: P.args,
    **kwargs: P.kwargs,
) -> Interp[T, E]:
    """
    Call async function with arguments and automatically lift into Interp.
    
    **When to use:** This is the preferred pattern for locality! Write pure
    functions and lift them at the call site. More explicit and readable
    than `wrap_async(lambda: ...)`.
    
    **Design philosophy:**
    - ✅ Pure functions (no Interp dependency) = easier to test & maintain
    - ✅ Lift at call site = maximum locality, clear intent
    - ✅ No lambda boilerplate = cleaner syntax
    
    Example:
        from combinators import lift as L
        
        # Pure function (no Interp dependency - easy to test!)
        async def fetch_user_impl(user_id: int) -> Result[User, APIError]:
            return Ok(User(id=user_id, name="User"))
        
        # Lift at call site (locality!)
        result = await L.down(L.call(fetch_user_impl, 42))
        
        # vs verbose alternative:
        # result = await L.down(L.call.wrap_async(lambda: fetch_user_impl(42)))
    
    **Grammar:** `L.call(func, *args, **kwargs)` reads as "call function with args"
    
    NOTE: Automatically creates a thunk. In most cases args are known at call site,
          so this is safe. For dynamic args, use wrap_async with explicit lambda.
    """
    return wrap_async(lambda: func(*args, **kwargs))


__all__ = (
    "call",
    "lifted",
    "wrap_async",
)
