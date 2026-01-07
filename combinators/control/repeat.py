"""Repeat combinators

Combinators for repeat logic with extract + wrap pattern."""

from __future__ import annotations

import asyncio
import typing
from collections.abc import Callable, Coroutine
from dataclasses import dataclass

from kungfu import Error, LazyCoroResult, Ok, Result

from .._errors import ConditionNotMetError
from .._types import Predicate
from ..writer import LazyCoroResultWriter, Log, WriterResult

@dataclass(frozen=True, slots=True)
class RepeatPolicy:
    """Configuration for repeat_until."""

    max_rounds: int
    delay_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.max_rounds < 1:
            raise ValueError("RepeatPolicy.max_rounds must be >= 1")
        if self.delay_seconds < 0.0:
            raise ValueError("RepeatPolicy.delay_seconds must be >= 0")

# Generic combinator (extract + wrap pattern)
def repeat_untilM[M, T, E, RawIn, RawOut](
    interp: Callable[[], Coroutine[typing.Any, typing.Any, RawIn]],
    *,
    extract: Callable[[RawIn], Result[T, E]],
    get_value: Callable[[RawIn], T],
    condition: Predicate[T],
    policy: RepeatPolicy,
    widen_ok: Callable[[RawIn], RawOut],
    widen_err: Callable[[RawIn], RawOut],
    on_exhausted: Callable[[], RawOut],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, RawOut]]], M],
) -> M:
    """
    Generic repeat_until combinator.
    
    Run until Ok value satisfies condition, or give up after max_rounds.
    """

    async def run() -> RawOut:
        for round_idx in range(policy.max_rounds):
            raw = await interp()
            result = extract(raw)
            
            match result:
                case Ok(_):
                    value = get_value(raw)
                    if condition(value):
                        return widen_ok(raw)
                case Error(_):
                    return widen_err(raw)
            
            if round_idx + 1 < policy.max_rounds and policy.delay_seconds > 0.0:
                await asyncio.sleep(policy.delay_seconds)
        
        return on_exhausted()

    return wrap(run)

# Sugar for LazyCoroResult
def repeat_until[T, E](
    interp: LazyCoroResult[T, E],
    *,
    condition: Predicate[T],
    policy: RepeatPolicy,
) -> LazyCoroResult[T, E | ConditionNotMetError]:
    """Run until Ok value satisfies condition, or give up after max_rounds."""

    async def run() -> Result[T, E | ConditionNotMetError]:
        for round_idx in range(policy.max_rounds):
            r = await interp()
            match r:
                case Ok(value):
                    if condition(value):
                        return Ok(value)
                case Error(e):
                    return Error(e)
            
            if round_idx + 1 < policy.max_rounds and policy.delay_seconds > 0.0:
                await asyncio.sleep(policy.delay_seconds)
        
        return Error(ConditionNotMetError(policy.max_rounds))

    return LazyCoroResult(run)

# Sugar for LazyCoroResultWriter
def repeat_until_writer[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    condition: Predicate[T],
    policy: RepeatPolicy,
) -> LazyCoroResultWriter[T, E | ConditionNotMetError, W]:
    """Run until Ok value satisfies condition, or give up."""

    async def run() -> WriterResult[T, E | ConditionNotMetError, Log[W]]:
        for round_idx in range(policy.max_rounds):
            wr = await interp()
            match wr.result:
                case Ok(value):
                    if condition(value):
                        return WriterResult(Ok(value), wr.log)
                case Error(e):
                    return WriterResult(Error(e), wr.log)
            
            if round_idx + 1 < policy.max_rounds and policy.delay_seconds > 0.0:
                await asyncio.sleep(policy.delay_seconds)
        
        return WriterResult(Error(ConditionNotMetError(policy.max_rounds)), Log[W]())

    return LazyCoroResultWriter(run)

__all__ = ("RepeatPolicy", "repeat_until", "repeat_until_writer", "repeat_untilM")
