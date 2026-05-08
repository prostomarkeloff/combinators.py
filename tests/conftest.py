"""Shared fixtures and helpers for combinators tests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from kungfu import Error, LazyCoroResult, Ok, Result

from combinators import LazyCoroResultWriter, Log, WriterResult


def lcr_ok[T](value: T) -> LazyCoroResult[T, Any]:
    async def run() -> Result[T, Any]:
        return Ok(value)
    return LazyCoroResult(run)


def lcr_err[E](err: E) -> LazyCoroResult[Any, E]:
    async def run() -> Result[Any, E]:
        return Error(err)
    return LazyCoroResult(run)


def lcr_from(fn: Callable[[], Awaitable[Result[Any, Any]]]) -> LazyCoroResult[Any, Any]:
    return LazyCoroResult(fn)


def w_ok[T, W](value: T, *log: W) -> LazyCoroResultWriter[T, Any, W]:
    async def run() -> WriterResult[T, Any, Log[W]]:
        return WriterResult(Ok(value), Log.of(*log))
    return LazyCoroResultWriter(run)


def w_err[E, W](err: E, *log: W) -> LazyCoroResultWriter[Any, E, W]:
    async def run() -> WriterResult[Any, E, Log[W]]:
        return WriterResult(Error(err), Log.of(*log))
    return LazyCoroResultWriter(run)


class Counter:
    """Simple call counter for asserting effect runs."""

    def __init__(self) -> None:
        self.n = 0
        self.values: list[Any] = []

    def __call__(self, value: Any = None) -> None:
        self.n += 1
        self.values.append(value)

    async def acall(self, value: Any = None) -> None:
        self.n += 1
        self.values.append(value)


class FlakyOp:
    """Builder for an LCR that fails first `fail_until` calls, then succeeds."""

    def __init__(self, fail_until: int, ok_value: Any = "ok", err: Any = "boom") -> None:
        self.fail_until = fail_until
        self.ok_value = ok_value
        self.err = err
        self.calls = 0

    def lcr(self) -> LazyCoroResult[Any, Any]:
        async def run() -> Result[Any, Any]:
            self.calls += 1
            if self.calls <= self.fail_until:
                return Error(self.err)
            return Ok(self.ok_value)
        return LazyCoroResult(run)
