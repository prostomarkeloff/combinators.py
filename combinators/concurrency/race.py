"""
Race combinators
================

Комбинаторы для гонки между вычислениями с extract + wrap паттерном.
"""

from __future__ import annotations

import asyncio
import typing
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Literal

from kungfu import Error, LazyCoroResult, Ok, Result

from .._helpers import extract_writer_result, identity, wrap_lazy_coro_result_writer
from ..writer import LazyCoroResultWriter


@dataclass(frozen=True, slots=True)
class RaceOkPolicy:
    """Configuration for race_ok: which error to return, whether to cancel."""

    cancel_pending: bool = True
    error_strategy: Literal["first", "last"] = "last"

    def __post_init__(self) -> None:
        if self.error_strategy not in ("first", "last"):
            raise ValueError("RaceOkPolicy.error_strategy must be 'first' or 'last'")


# ============================================================================
# Generic combinators (extract + wrap pattern)
# ============================================================================


def race_okM[M, T, E, Raw](
    *interps: Callable[[], Coroutine[typing.Any, typing.Any, Raw]],
    extract: Callable[[Raw], Result[T, E]],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, Raw]]], M],
    policy: RaceOkPolicy = RaceOkPolicy(),
) -> M:
    """
    Generic race_ok combinator.
    
    Run all, return first Ok. If all fail, return chosen error.
    """

    async def run() -> Raw:
        if not interps:
            raise ValueError("race_okM() requires at least one interpretation")

        tasks = [asyncio.create_task(i()) for i in interps]
        try:
            first_error_raw: Raw | None = None
            last_error_raw: Raw | None = None
            
            for fut in asyncio.as_completed(tasks):
                raw = await fut
                result = extract(raw)
                match result:
                    case Ok(_):
                        if policy.cancel_pending:
                            for t in tasks:
                                if not t.done():
                                    t.cancel()
                        return raw
                    case Error(_):
                        if first_error_raw is None:
                            first_error_raw = raw
                        last_error_raw = raw
            
            err_raw = first_error_raw if policy.error_strategy == "first" else last_error_raw
            if err_raw is None:
                raise RuntimeError("race_okM(): internal error (no results)")
            return err_raw
        finally:
            if policy.cancel_pending:
                for t in tasks:
                    if not t.done():
                        t.cancel()

    return wrap(run)


def raceM[M, T, E, Raw](
    *interps: Callable[[], Coroutine[typing.Any, typing.Any, Raw]],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, Raw]]], M],
) -> M:
    """
    Generic race combinator.
    
    Return first completed result (Ok or Error, whichever finishes first).
    Always cancels others.
    """

    async def run() -> Raw:
        if not interps:
            raise ValueError("raceM() requires at least one interpretation")

        tasks = [asyncio.create_task(i()) for i in interps]
        try:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            
            first_done = next(iter(done))
            raw = first_done.result()
            
            for t in pending:
                t.cancel()
            
            return raw
        finally:
            for t in tasks:
                if not t.done():
                    t.cancel()

    return wrap(run)


# ============================================================================
# Sugar for LazyCoroResult
# ============================================================================


def race_ok[T, E](
    *interps: LazyCoroResult[T, E],
    policy: RaceOkPolicy = RaceOkPolicy(),
) -> LazyCoroResult[T, E]:
    """Run all, return first Ok. If all fail, return chosen error."""
    return race_okM(
        *interps,
        extract=identity,
        wrap=LazyCoroResult,
        policy=policy,
    )


def race[T, E](*interps: LazyCoroResult[T, E]) -> LazyCoroResult[T, E]:
    """Return first completed result (Ok or Error)."""
    return raceM(*interps, wrap=LazyCoroResult)


# ============================================================================
# Sugar for LazyCoroResultWriter
# ============================================================================


def race_ok_w[T, E, W](
    *interps: LazyCoroResultWriter[T, E, W],
    policy: RaceOkPolicy = RaceOkPolicy(),
) -> LazyCoroResultWriter[T, E, W]:
    """
    Run all, return first Ok. If all fail, return chosen error.
    
    NOTE: Only winner's log is preserved. Other logs are discarded.
    """
    return race_okM(
        *interps,
        extract=extract_writer_result,
        wrap=wrap_lazy_coro_result_writer,
        policy=policy,
    )


def race_w[T, E, W](
    *interps: LazyCoroResultWriter[T, E, W],
) -> LazyCoroResultWriter[T, E, W]:
    """
    Return first completed result.
    
    NOTE: Only winner's log is preserved.
    """
    return raceM(*interps, wrap=wrap_lazy_coro_result_writer)


__all__ = ("RaceOkPolicy", "race", "race_ok", "race_w", "race_ok_w", "raceM", "race_okM")
