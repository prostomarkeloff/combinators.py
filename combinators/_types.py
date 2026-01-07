"""Core type definitions for combinators."""

from __future__ import annotations

import typing
from collections.abc import Awaitable, Callable

from kungfu import LazyCoroResult, Result

# Function that tests a value
type Predicate[T] = Callable[[T], bool]

# Function that extracts a key for comparison/sorting
type Selector[T, K] = Callable[[T], K]

# Function that branches control flow and produces new computation
type Route[T, R, E] = Callable[[T], Awaitable[Result[R, E]]]

# Type representing "never fails" semantic (uses Never instead of None)
type NoError = typing.Never

# LazyCoroResult shortcut
type LCR[T, E] = LazyCoroResult[T, E]

# Interpretation alias (concrete type for most combinators)
type Interp[T, E] = LazyCoroResult[T, E]

__all__ = (
    # Type aliases
    "Predicate",
    "Selector",
    "Route",
    "NoError",
    # Concrete shortcuts
    "LCR",
    "Interp",
)
