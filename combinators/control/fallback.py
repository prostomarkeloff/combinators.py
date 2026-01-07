"""
Fallback combinators
====================

Комбинаторы для fallback логики с extract + wrap паттерном.
"""

from __future__ import annotations

import typing
from collections.abc import Callable, Coroutine

from kungfu import Error, LazyCoroResult, Ok, Result

from .._helpers import extract_writer_result, identity, wrap_lazy_coro_result_writer
from ..writer import LazyCoroResultWriter


# ============================================================================
# Generic combinators (extract + wrap pattern)
# ============================================================================


def fallbackM[M, T, E, Raw](
    primary: Callable[[], Coroutine[typing.Any, typing.Any, Raw]],
    secondary: Callable[[], Coroutine[typing.Any, typing.Any, Raw]],
    *,
    extract: Callable[[Raw], Result[T, E]],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, Raw]]], M],
) -> M:
    """
    Generic fallback combinator.
    
    Try secondary if primary fails.
    
    Args:
        primary: Primary computation
        secondary: Fallback computation if primary fails
        extract: Function to extract Result[T, E] from Raw
        wrap: Constructor to wrap thunk back into monad M
    """

    async def run() -> Raw:
        raw = await primary()
        result = extract(raw)
        match result:
            case Ok(_):
                return raw
            case Error(_):
                return await secondary()

    return wrap(run)


def fallback_chainM[M, T, E, Raw](
    *interps: Callable[[], Coroutine[typing.Any, typing.Any, Raw]],
    extract: Callable[[Raw], Result[T, E]],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, Raw]]], M],
) -> M:
    """
    Generic fallback chain combinator.
    
    Try each until one succeeds. Returns last error if all fail.
    
    Args:
        interps: Sequence of computations to try
        extract: Function to extract Result[T, E] from Raw
        wrap: Constructor to wrap thunk back into monad M
    """

    async def run() -> Raw:
        last: Raw | None = None
        for interp in interps:
            raw = await interp()
            result = extract(raw)
            match result:
                case Ok(_):
                    return raw
                case Error(_):
                    last = raw
        if last is None:
            raise ValueError("fallback_chainM() requires at least one interpretation")
        return last

    return wrap(run)


# ============================================================================
# Sugar for LazyCoroResult
# ============================================================================


def fallback[T, E](
    primary: LazyCoroResult[T, E],
    secondary: LazyCoroResult[T, E],
) -> LazyCoroResult[T, E]:
    """Try secondary if primary fails."""
    return fallbackM(
        primary,
        secondary,
        extract=identity,
        wrap=LazyCoroResult,
    )


def fallback_with[T, E](
    primary: LazyCoroResult[T, E],
    *,
    secondary: Callable[[E], LazyCoroResult[T, E]],
) -> LazyCoroResult[T, E]:
    """
    Compute fallback based on primary's error.
    
    NOTE: This variant doesn't use fallbackM because secondary depends on error value.
    """

    async def run() -> Result[T, E]:
        r = await primary()
        match r:
            case Ok(_):
                return r
            case Error(e):
                return await secondary(e)()

    return LazyCoroResult(run)


def fallback_chain[T, E](*interps: LazyCoroResult[T, E]) -> LazyCoroResult[T, E]:
    """Try each until one succeeds. Returns last error if all fail."""
    return fallback_chainM(
        *interps,
        extract=identity,
        wrap=LazyCoroResult,
    )


# ============================================================================
# Sugar for LazyCoroResultWriter
# ============================================================================


def fallback_w[T, E, W](
    primary: LazyCoroResultWriter[T, E, W],
    secondary: LazyCoroResultWriter[T, E, W],
) -> LazyCoroResultWriter[T, E, W]:
    """
    Try secondary if primary fails.
    
    NOTE: If primary fails, its log is discarded. Only successful branch's log is kept.
    """
    return fallbackM(
        primary,
        secondary,
        extract=extract_writer_result,
        wrap=wrap_lazy_coro_result_writer,
    )


def fallback_chain_w[T, E, W](
    *interps: LazyCoroResultWriter[T, E, W],
) -> LazyCoroResultWriter[T, E, W]:
    """
    Try each until one succeeds. Returns last error if all fail.
    
    NOTE: Only successful branch's log is kept. Failed branches' logs are discarded.
    """
    return fallback_chainM(
        *interps,
        extract=extract_writer_result,
        wrap=wrap_lazy_coro_result_writer,
    )


__all__ = (
    "fallback",
    "fallback_chain",
    "fallback_with",
    "fallback_w",
    "fallback_chain_w",
    "fallbackM",
    "fallback_chainM",
)
