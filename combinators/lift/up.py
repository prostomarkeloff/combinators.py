"""
Подъем значений в монаду (LazyCoroResult).

Функции для преобразования обычных значений, Result, Optional, и exception-based
кода в монадический контекст Interp.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Never

from kungfu import Error, LazyCoroResult, Ok, Result

from .._types import Interp


def pure[T](value: T) -> Interp[T, Never]:
    """
    Lift pure value into always-succeeding Interp.
    
    Short alias for LazyCoroResult.pure() — classic FP term for
    "lift value into computational context".
    
    **When to use:** When you have a plain value and need to start an Interp chain.
    
    Example:
        from combinators import lift as L
        
        user = L.up.pure(User(id=42))
        result = await L.down(user)  # Ok(User(id=42))
    
    **Grammar:** `L.up.pure(value)` reads as "lift up pure value"
    """
    return LazyCoroResult.pure(value)


def fail[E](error: E) -> Interp[Never, E]:
    """
    Create always-failing Interp. Dual of pure().
    
    **When to use:** When you need to start a chain with a known error.
    
    Example:
        from combinators import lift as L
        
        error = L.up.fail(ValidationError("bad input"))
        result = await L.down(error)  # Error(ValidationError(...))
    
    **Grammar:** `L.up.fail(error)` reads as "lift up fail with error"
    
    NOTE: Return type Interp[Never, E] means "never produces a value".
          Never (bottom type) is semantically correct here.
    """
    return Error(error).to_async()


def from_result[T, E](value: Result[T, E]) -> Interp[T, E]:
    """
    Lift already-computed Result into Interp context.
    
    **When to use:** When you have a sync function returning Result and need
    to continue an Interp pipeline. Use in `.then()` chains.
    
    Example:
        from combinators import lift as L
        
        def validate_score(user: User) -> Result[User, Error]: ...
        
        fetch_user(42).map(validate_score).then(L.up.from_result)
    
    **Grammar:** `L.up.from_result(result)` reads as "lift up from result"
    
    NOTE: This is NOT lazy — result is already computed.
          For lazy evaluation, use wrap_async with a thunk.
    """
    async def run() -> Result[T, E]:
        return value

    return LazyCoroResult(run)


def optional[T, E](
    value: T | None,
    *,
    error: Callable[[], E],
) -> Interp[T, E]:
    """
    Convert Optional to Interp. None becomes Error(error()).
    
    **When to use:** Database lookups, cache checks, config reads — anywhere
    you get Optional and need to convert None to an error.
    
    Example:
        from combinators import lift as L
        
        def get_user(user_id: int) -> Interp[User, NotFoundError]:
            user = db.find(user_id)  # returns User | None
            return L.up.optional(user, error=lambda: NotFoundError(user_id))
    
    **Grammar:** `L.up.optional(value, error=...)` reads as "lift up optional value"
    
    NOTE: error is a thunk (zero-arg callable) to avoid computing
          error message when value is present.
    """
    async def run() -> Result[T, E]:
        if value is None:
            return Error(error())
        return Ok(value)

    return LazyCoroResult(run)


def catching[T, E](
    thunk: Callable[[], T],
    *,
    on_error: Callable[[Exception], E],
) -> Interp[T, E]:
    """
    Execute sync thunk, catch exceptions and convert to Error.
    
    **When to use:** Bridge between exception-based code and Result-based combinators.
    For sync code that throws exceptions.
    
    Example:
        from combinators import lift as L
        import json
        
        def parse_json(raw: str) -> Interp[dict, ParseError]:
            return L.up.catching(
                lambda: json.loads(raw),
                on_error=lambda e: ParseError(str(e)),
            )
    
    **Grammar:** `L.up.catching(thunk, on_error=...)` reads as "lift up catching exceptions"
    
    NOTE: Catches all Exception subclasses. For specific exceptions,
          filter in on_error or use try/except manually.
    """
    async def run() -> Result[T, E]:
        try:
            return Ok(thunk())
        except Exception as exc:
            return Error(on_error(exc))

    return LazyCoroResult(run)


def catching_async[T, E](
    thunk: Callable[[], Awaitable[T]],
    *,
    on_error: Callable[[Exception], E],
) -> Interp[T, E]:
    """
    Execute async thunk, catch exceptions and convert to Error.
    
    **When to use:** Async version of catching() for code that uses exceptions
    instead of Result (legacy code, third-party libraries).
    
    Example:
        from combinators import lift as L
        import httpx
        
        def fetch_external(url: str) -> Interp[Response, FetchError]:
            return L.up.catching_async(
                lambda: httpx.get(url),
                on_error=lambda e: FetchError(str(e)),
            )
    
    **Grammar:** `L.up.catching_async(thunk, on_error=...)` reads as "lift up catching async"
    """
    async def run() -> Result[T, E]:
        try:
            return Ok(await thunk())
        except Exception as exc:
            return Error(on_error(exc))

    return LazyCoroResult(run)


__all__ = (
    "pure",
    "fail",
    "from_result",
    "optional",
    "catching",
    "catching_async",
)
