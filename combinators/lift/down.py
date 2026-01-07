"""
Опускание монады в значение.

Функции для выполнения Interp и извлечения результата в виде Result или значения.
"""

from __future__ import annotations

from kungfu import Error, Ok, Result

from .._types import Interp


async def to_result[T, E](interp: Interp[T, E]) -> Result[T, E]:
    """
    Run interp and return Result.
    
    **When to use:** Standard way to execute an Interp and get a Result.
    
    Example:
        from combinators import lift as L
        
        user_interp = L.up.pure(User(id=42))
        result = await L.down.to_result(user_interp)
        # result: Ok(User(id=42))
        
        # Or using callable shorthand:
        result = await L.down(user_interp)
    
    **Grammar:** `await L.down.to_result(interp)` reads as "run down to result"
    """
    return await interp()


async def unsafe[T, E](interp: Interp[T, E]) -> T:
    """
    Run and unwrap, raises on Error.
    
    **When to use:** When you're certain the computation will succeed,
    or when you want to propagate exceptions. Use with caution!
    
    Example:
        from combinators import lift as L
        
        user = await L.down.unsafe(fetch_user(42))
        # Returns User(id=42) or raises exception
    
    **Grammar:** `await L.down.unsafe(interp)` reads as "run down unsafe (may raise)"
    
    NOTE: Raises an exception if the Result is an Error.
          Use only when you're certain of success or want to propagate errors.
    """
    result = await interp()
    return result.unwrap()


async def or_else[T, E](interp: Interp[T, E], default: T) -> T:
    """
    Run and return value or default.
    
    **When to use:** When you want a fallback value instead of handling Error case.
    
    Example:
        from combinators import lift as L
        
        user = await L.down.or_else(
            fetch_user(42),
            default=User(id=0, name="Guest")
        )
        # Always returns a User, never an Error
    
    **Grammar:** `await L.down.or_else(interp, default=...)` reads as "run down or else default"
    """
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
