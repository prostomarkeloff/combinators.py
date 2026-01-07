"""LazyCoroResultWriter Monad

Combined monad unifying:
- Lazy (deferred computations)
- Coro (asynchronous) 
- Result[T, E] (success/error)
- Writer[Log[W]] (log accumulation)

Built on top of kungfu library patterns."""

from __future__ import annotations

import typing
from collections.abc import Callable, Coroutine
from typing import assert_never

from kungfu import LazyCoroResult, Result, Ok, Error
from kungfu.library.caching import acache

from .log import Log
from .result import WriterResult

class LazyCoroResultWriter[T, E, W]:
    """Lazy Coroutine Result Writer Monad.
    
    Combines: Lazy + Coro + Result[T, E] + Writer[Log[W]]
    
    Monadic laws:
    - Left identity: pure(a).then(f) ≡ f(a)
    - Right identity: m.then(pure) ≡ m
    - Associativity: m.then(f).then(g) ≡ m.then(x => f(x).then(g))
    """

    __slots__ = ("_value",)

    def __init__(
        self,
        value: Callable[[], Coroutine[typing.Any, typing.Any, WriterResult[T, E, Log[W]]]],
        /,
    ) -> None:
        """Create LazyCoroResultWriter from a fn returning coroutine."""
        self._value = value

    @staticmethod
    def pure[V, LogT](value: V, log_type: type[LogT]) -> LazyCoroResultWriter[V, typing.Never, LogT]:
        """Lift a value into the monad with empty log."""
        _ = log_type  # Used only for type inference

        async def wrapper() -> WriterResult[V, typing.Never, Log[LogT]]:
            return WriterResult(Ok(value), Log[LogT]())

        return LazyCoroResultWriter(wrapper)

    @staticmethod
    def from_result[V, Err, LogT](
        result: Result[V, Err],
        log_type: type[LogT],
    ) -> LazyCoroResultWriter[V, Err, LogT]:
        """Lift a Result into the monad with empty log."""
        _ = log_type

        async def wrapper() -> WriterResult[V, Err, Log[LogT]]:
            return WriterResult(result, Log[LogT]())

        return LazyCoroResultWriter(wrapper)

    @staticmethod
    def tell[LogEntry](
        *entries: LogEntry,
    ) -> LazyCoroResultWriter[None, typing.Never, LogEntry]:
        """Write entries to the log without producing a value."""

        async def wrapper() -> WriterResult[None, typing.Never, Log[LogEntry]]:
            return WriterResult(Ok(None), Log.of(*entries))

        return LazyCoroResultWriter(wrapper)

    @staticmethod
    def from_lazy_coro_result[V, Err, LogT](
        lazy: LazyCoroResult[V, Err],
        log_type: type[LogT],
    ) -> LazyCoroResultWriter[V, Err, LogT]:
        """Convert kungfu LazyCoroResult to LazyCoroResultWriter with empty log."""
        _ = log_type

        async def wrapper() -> WriterResult[V, Err, Log[LogT]]:
            result = await lazy
            return WriterResult(result, Log[LogT]())

        return LazyCoroResultWriter(wrapper)

    # Functor operations

    def map[U](self, f: Callable[[T], U], /) -> LazyCoroResultWriter[U, E, W]:
        """Functor fmap - apply function to success value, preserve log."""

        async def wrapper() -> WriterResult[U, E, Log[W]]:
            wr = await self()
            return WriterResult(wr.result.map(f), wr.log)

        return LazyCoroResultWriter(wrapper)

    def map_err[F](self, f: Callable[[E], F], /) -> LazyCoroResultWriter[T, F, W]:
        """Map over error type."""

        async def wrapper() -> WriterResult[T, F, Log[W]]:
            wr = await self()
            return WriterResult(wr.result.map_err(f), wr.log)

        return LazyCoroResultWriter(wrapper)

    def map_log[V](self, f: Callable[[Log[W]], Log[V]], /) -> LazyCoroResultWriter[T, E, V]:
        """Transform the log."""

        async def wrapper() -> WriterResult[T, E, Log[V]]:
            wr = await self()
            return WriterResult(wr.result, f(wr.log))

        return LazyCoroResultWriter(wrapper)

    # Monad operations

    def then[U](
        self,
        f: Callable[[T], typing.Awaitable[WriterResult[U, E, Log[W]]]],
        /,
    ) -> LazyCoroResultWriter[U, E, W]:
        """
        Monadic bind (>>=).
        
        - On Ok: executes f, combines logs
        - On Error: short-circuit, preserves current log
        """

        async def wrapper() -> WriterResult[U, E, Log[W]]:
            wr = await self()
            match wr.result:
                case Ok(value):
                    next_wr = await f(value)
                    combined_log = wr.log.combine(next_wr.log)
                    return WriterResult(next_wr.result, combined_log)
                case Error(err):
                    return WriterResult(Error(err), wr.log)
                case _ as unreachable:
                    assert_never(unreachable)

        return LazyCoroResultWriter(wrapper)

    def then_result(
        self,
        f: Callable[[T], typing.Awaitable[Result[T, E]]],
        /,
    ) -> LazyCoroResultWriter[T, E, W]:
        """Bind with function returning plain Result (no log contribution)."""

        async def wrapper() -> WriterResult[T, E, Log[W]]:
            wr = await self()
            match wr.result:
                case Ok(value):
                    next_result = await f(value)
                    return WriterResult(next_result, wr.log)
                case Error(err):
                    return WriterResult(Error(err), wr.log)
                case _ as unreachable:
                    assert_never(unreachable)

        return LazyCoroResultWriter(wrapper)

    # Writer operations

    def with_log(self, *entries: W) -> LazyCoroResultWriter[T, E, W]:
        """Add entries to log without changing computation."""

        async def wrapper() -> WriterResult[T, E, Log[W]]:
            wr = await self()
            return WriterResult(wr.result, wr.log.combine(Log.of(*entries)))

        return LazyCoroResultWriter(wrapper)

    def listen(self) -> LazyCoroResultWriter[tuple[T, Log[W]], E, W]:
        """Get access to the log along with the value."""

        async def wrapper() -> WriterResult[tuple[T, Log[W]], E, Log[W]]:
            wr = await self()
            match wr.result:
                case Ok(value):
                    return WriterResult(Ok((value, wr.log)), wr.log)
                case Error(err):
                    return WriterResult(Error(err), wr.log)
                case _ as unreachable:
                    assert_never(unreachable)

        return LazyCoroResultWriter(wrapper)

    def censor(
        self,
        f: Callable[[Log[W]], Log[W]],
        /,
    ) -> LazyCoroResultWriter[T, E, W]:
        """Modify the log after computation."""

        async def wrapper() -> WriterResult[T, E, Log[W]]:
            wr = await self()
            return WriterResult(wr.result, f(wr.log))

        return LazyCoroResultWriter(wrapper)

    # Utility operations

    def cache(self) -> LazyCoroResultWriter[T, E, W]:
        """Cache the result - only compute once."""
        return LazyCoroResultWriter(acache(self))

    def unwrap(self) -> Coroutine[typing.Any, typing.Any, T]:
        """Unwrap the value, raising on error. Warning: loses log and error info!"""

        async def inner() -> T:
            wr = await self()
            return wr.result.unwrap()

        return inner()

    def to_lazy_coro_result(self) -> LazyCoroResult[tuple[T, Log[W]], E]:
        """Convert to kungfu LazyCoroResult, including log in success value."""

        async def wrapper() -> Result[tuple[T, Log[W]], E]:
            wr = await self()
            match wr.result:
                case Ok(value):
                    return Ok((value, wr.log))
                case Error(err):
                    return Error(err)
                case _ as unreachable:
                    assert_never(unreachable)

        return LazyCoroResult(wrapper)

    # Protocol methods

    def __call__(self) -> Coroutine[typing.Any, typing.Any, WriterResult[T, E, Log[W]]]:
        """Execute the lazy computation, returning coroutine."""
        return self._value()

    def __await__(self) -> typing.Generator[typing.Any, None, WriterResult[T, E, Log[W]]]:
        """Allow direct await on the writer."""
        return self().__await__()

# Convenience Constructors
def writer_ok[T, W](
    value: T,
    *log_entries: W,
) -> LazyCoroResultWriter[T, typing.Never, W]:
    """Create successful LazyCoroResultWriter with value and optional log entries."""

    async def wrapper() -> WriterResult[T, typing.Never, Log[W]]:
        return WriterResult(Ok(value), Log.of(*log_entries))

    return LazyCoroResultWriter(wrapper)

def writer_error[E, W](
    error: E,
    *log_entries: W,
) -> LazyCoroResultWriter[typing.Never, E, W]:
    """Create failed LazyCoroResultWriter with error and optional log entries."""

    async def wrapper() -> WriterResult[typing.Never, E, Log[W]]:
        return WriterResult(Error(error), Log.of(*log_entries))

    return LazyCoroResultWriter(wrapper)

__all__ = (
    "LazyCoroResultWriter",
    "writer_ok",
    "writer_error",
)

