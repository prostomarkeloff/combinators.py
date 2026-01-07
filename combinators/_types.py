"""
Core type definitions for combinators.

Типы и алиасы используемые по всей библиотеке.
"""

from __future__ import annotations

import typing
from collections.abc import Awaitable, Callable

from kungfu import LazyCoroResult, Result

# ============================================================================
# Type aliases
# ============================================================================

# Predicate = function that tests a value
type Predicate[T] = Callable[[T], bool]

# Selector = function that extracts a key for comparison/sorting
type Selector[T, K] = Callable[[T], K]

# Route = function that branches control flow and produces new computation
type Route[T, R, E] = Callable[[T], Awaitable[Result[R, E]]]

# NoError = type representing "never fails" semantic
# NOTE: Используем Never (bottom type) вместо None для точности.
#       Never семантически означает "это значение не может быть создано",
#       что идеально для ошибок которые никогда не происходят.
type NoError = typing.Never

# ============================================================================
# Concrete type shortcuts
# ============================================================================

# LCR = LazyCoroResult shortcut
type LCR[T, E] = LazyCoroResult[T, E]

# Interp = Interpretation alias (legacy, kept for compatibility)
# NOTE: This is the concrete type for most combinators.
# For generic combinators, use retryM/timeoutM/etc. with extract+wrap pattern.
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
