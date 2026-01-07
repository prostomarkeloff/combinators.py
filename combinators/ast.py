"""
Generic AST for fluent combinator chaining.

Architecture:
- FlowM[M, Raw, T, E] - generic Flow parameterized by monad
- Interpreter[M, Raw] - typeclass with extract + wrap + combinators
- Flow (LazyCoroResult) and FlowWriter (LazyCoroResultWriter) - sugar implementations

For custom monads:
1. Create your Interpreter with extract, wrap, and combinator functions
2. Use FlowM directly with your interpreter
3. Or create your own sugar class following the Flow/FlowWriter pattern
"""

from __future__ import annotations

import typing
from collections.abc import Awaitable, Callable, Coroutine, Sequence
from dataclasses import dataclass
from typing import Literal

from kungfu import LazyCoroResult, Result

from ._errors import ConditionNotMetError, TimeoutError
from ._types import NoError, Predicate, Selector
from .control.repeat import RepeatPolicy
from .control.retry import RetryPolicy
from .concurrency.race import RaceOkPolicy
from .concurrency.rate_limit import RateLimitPolicy
from .writer import LazyCoroResultWriter

# Generic Interpreter Protocol
@dataclass(frozen=True, slots=True)
class Interpreter[M, Raw, T, E]:
    """Typeclass for interpreting AST into a specific monad."""

    # Core operations
    extract: Callable[[Raw], Result[T, E]]
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, Raw]]], M]

    # Combinator functions (these call the generic *M functions)
    retry: Callable[[M, RetryPolicy[E]], M]
    tap: Callable[[M, Callable[[T], None]], M]
    tap_err: Callable[[M, Callable[[E], None]], M]
    delay: Callable[[M, float], M]
    rate_limit: Callable[[M, RateLimitPolicy], M]

# LazyCoroResult Sugar (Flow) - Existing Implementation
class Expr[T, E]:
    """
    AST node that can be lowered into executable LazyCoroResult.
    """

    def lower(self) -> LazyCoroResult[T, E]:
        raise NotImplementedError

@dataclass(frozen=True, slots=True)
class Base[T, E](Expr[T, E]):
    value: LazyCoroResult[T, E]

    def lower(self) -> LazyCoroResult[T, E]:
        return self.value

@dataclass(frozen=True, slots=True)
class Retry[T, E](Expr[T, E]):
    inner: Expr[T, E]
    policy: RetryPolicy[E]

    def lower(self) -> LazyCoroResult[T, E]:
        from .control.retry import retry
        return retry(self.inner.lower(), policy=self.policy)

@dataclass(frozen=True, slots=True)
class Timeout[T, E0](Expr[T, E0 | TimeoutError]):
    inner: Expr[T, E0]
    seconds: float

    def lower(self) -> LazyCoroResult[T, E0 | TimeoutError]:
        from .time.timeout import timeout
        return timeout(self.inner.lower(), seconds=self.seconds)

@dataclass(frozen=True, slots=True)
class Tap[T, E](Expr[T, E]):
    inner: Expr[T, E]
    effect: Callable[[T], None]

    def lower(self) -> LazyCoroResult[T, E]:
        from .transform.effects import tap
        return tap(self.inner.lower(), effect=self.effect)

@dataclass(frozen=True, slots=True)
class TapAsync[T, E](Expr[T, E]):
    inner: Expr[T, E]
    effect: Callable[[T], Awaitable[None]]

    def lower(self) -> LazyCoroResult[T, E]:
        from .transform.effects import tap_async
        return tap_async(self.inner.lower(), effect=self.effect)

@dataclass(frozen=True, slots=True)
class TapErr[T, E](Expr[T, E]):
    inner: Expr[T, E]
    effect: Callable[[E], None]

    def lower(self) -> LazyCoroResult[T, E]:
        from .transform.effects import tap_err
        return tap_err(self.inner.lower(), effect=self.effect)

@dataclass(frozen=True, slots=True)
class TapErrAsync[T, E](Expr[T, E]):
    inner: Expr[T, E]
    effect: Callable[[E], Awaitable[None]]

    def lower(self) -> LazyCoroResult[T, E]:
        from .transform.effects import tap_err_async
        return tap_err_async(self.inner.lower(), effect=self.effect)

@dataclass(frozen=True, slots=True)
class Reject[T, E](Expr[T, E]):
    inner: Expr[T, E]
    predicate: Predicate[T]
    error: Callable[[T], E]

    def lower(self) -> LazyCoroResult[T, E]:
        from .control.guard import reject
        return reject(self.inner.lower(), predicate=self.predicate, error=self.error)

@dataclass(frozen=True, slots=True)
class Ensure[T, E](Expr[T, E]):
    inner: Expr[T, E]
    predicate: Predicate[T]
    error: Callable[[T], E]

    def lower(self) -> LazyCoroResult[T, E]:
        from .control.guard import ensure
        return ensure(self.inner.lower(), predicate=self.predicate, error=self.error)

@dataclass(frozen=True, slots=True)
class RaceOk[T, E](Expr[T, E]):
    inner: Expr[T, E]
    others: tuple[LazyCoroResult[T, E], ...]
    policy: RaceOkPolicy

    def lower(self) -> LazyCoroResult[T, E]:
        from .concurrency.race import race_ok
        return race_ok(self.inner.lower(), *self.others, policy=self.policy)

@dataclass(frozen=True, slots=True)
class BestOf[T, E](Expr[T, E]):
    inner: Expr[T, E]
    n: int
    key: Selector[T, float]

    def lower(self) -> LazyCoroResult[T, E]:
        from .selection.best import best_of
        return best_of(self.inner.lower(), n=self.n, key=self.key)

@dataclass(frozen=True, slots=True)
class BestOfMany[T, E](Expr[T, E]):
    candidates: Sequence[LazyCoroResult[T, E]]
    key: Selector[T, float]

    def lower(self) -> LazyCoroResult[T, E]:
        from .selection.best import best_of_many
        return best_of_many(self.candidates, key=self.key)

@dataclass(frozen=True, slots=True)
class Delay[T, E](Expr[T, E]):
    inner: Expr[T, E]
    seconds: float

    def lower(self) -> LazyCoroResult[T, E]:
        from .time.delay import delay
        return delay(self.inner.lower(), seconds=self.seconds)

@dataclass(frozen=True, slots=True)
class Recover[T, E](Expr[T, NoError]):
    inner: Expr[T, E]
    default: T

    def lower(self) -> LazyCoroResult[T, NoError]:
        from .control.recover import recover
        return recover(self.inner.lower(), default=self.default)

@dataclass(frozen=True, slots=True)
class RecoverWith[T, E](Expr[T, NoError]):
    inner: Expr[T, E]
    handler: Callable[[E], T]

    def lower(self) -> LazyCoroResult[T, NoError]:
        from .control.recover import recover_with
        return recover_with(self.inner.lower(), handler=self.handler)

@dataclass(frozen=True, slots=True)
class RepeatUntil[T, E](Expr[T, E | ConditionNotMetError]):
    inner: Expr[T, E]
    condition: Predicate[T]
    policy: RepeatPolicy

    def lower(self) -> LazyCoroResult[T, E | ConditionNotMetError]:
        from .control.repeat import repeat_until
        return repeat_until(self.inner.lower(), condition=self.condition, policy=self.policy)

@dataclass(frozen=True, slots=True)
class RateLimit[T, E](Expr[T, E]):
    inner: Expr[T, E]
    policy: RateLimitPolicy

    def lower(self) -> LazyCoroResult[T, E]:
        from .concurrency.rate_limit import rate_limit
        return rate_limit(self.inner.lower(), policy=self.policy)

@dataclass(frozen=True, slots=True)
class Bracket[T, R, E](Expr[R, E]):
    acquire: LazyCoroResult[T, E]
    release: Callable[[T], Awaitable[None]]
    use: Callable[[T], LazyCoroResult[R, E]]

    def lower(self) -> LazyCoroResult[R, E]:
        from .control.bracket import bracket
        return bracket(self.acquire, release=self.release, use=self.use)

@dataclass(frozen=True, slots=True)
class BimapTap[T, E](Expr[T, E]):
    inner: Expr[T, E]
    on_ok: Callable[[T], None]
    on_err: Callable[[E], None]

    def lower(self) -> LazyCoroResult[T, E]:
        from .transform.effects import bimap_tap
        return bimap_tap(self.inner.lower(), on_ok=self.on_ok, on_err=self.on_err)

@dataclass(frozen=True, slots=True)
class FilterOr[T, E](Expr[T, E]):
    inner: Expr[T, E]
    predicate: Predicate[T]
    error: Callable[[T], E]

    def lower(self) -> LazyCoroResult[T, E]:
        from .transform.filter import filter_or
        return filter_or(self.inner.lower(), predicate=self.predicate, error=self.error)

@dataclass(frozen=True, slots=True)
class Fallback[T, E](Expr[T, E]):
    inner: Expr[T, E]
    alternatives: tuple[LazyCoroResult[T, E], ...]

    def lower(self) -> LazyCoroResult[T, E]:
        from .control.fallback import fallback_chain
        return fallback_chain(self.inner.lower(), *self.alternatives)

@dataclass(frozen=True, slots=True)
class Replicate[T, E](Expr[list[T], E]):
    inner: Expr[T, E]
    n: int

    def lower(self) -> LazyCoroResult[list[T], E]:
        from .collection.replicate import replicate
        return replicate(self.inner.lower(), n=self.n)

@dataclass(frozen=True, slots=True)
class Flow[T, E]:
    """
    Fluent builder for chaining combinators (LazyCoroResult).
    """

    expr: Expr[T, E]

    def retry(
        self,
        *,
        policy: RetryPolicy[E] | None = None,
        times: int | None = None,
        delay_seconds: float = 0.0,
        retry_on: Predicate[E] | None = None,
    ) -> Flow[T, E]:
        if policy is None:
            if times is None:
                raise ValueError("retry(): must provide either 'policy' or 'times'")
            policy = RetryPolicy.fixed(times=times, delay_seconds=delay_seconds, retry_on=retry_on)  # type: ignore[type-var]
        return Flow(Retry(self.expr, policy=policy))

    def timeout(self, *, seconds: float) -> Flow[T, E | TimeoutError]:
        return Flow(Timeout(self.expr, seconds=seconds))

    def tap(self, effect: Callable[[T], None]) -> Flow[T, E]:
        return Flow(Tap(self.expr, effect=effect))

    def tap_async(self, effect: Callable[[T], Awaitable[None]]) -> Flow[T, E]:
        return Flow(TapAsync(self.expr, effect=effect))

    def tap_err(self, effect: Callable[[E], None]) -> Flow[T, E]:
        return Flow(TapErr(self.expr, effect=effect))

    def tap_err_async(self, effect: Callable[[E], Awaitable[None]]) -> Flow[T, E]:
        return Flow(TapErrAsync(self.expr, effect=effect))

    def ensure(self, predicate: Predicate[T], error: Callable[[T], E]) -> Flow[T, E]:
        return Flow(Ensure(self.expr, predicate=predicate, error=error))

    def reject(self, predicate: Predicate[T], error: Callable[[T], E]) -> Flow[T, E]:
        return Flow(Reject(self.expr, predicate=predicate, error=error))

    def race_ok(
        self,
        *others: LazyCoroResult[T, E],
        policy: RaceOkPolicy | None = None,
        cancel_pending: bool = True,
        error_strategy: Literal["first", "last"] = "last",
    ) -> Flow[T, E]:
        if policy is None:
            policy = RaceOkPolicy(cancel_pending=cancel_pending, error_strategy=error_strategy)
        return Flow(RaceOk(self.expr, others=others, policy=policy))

    def best_of(self, *, n: int, key: Selector[T, float]) -> Flow[T, E]:
        return Flow(BestOf(self.expr, n=n, key=key))

    def delay(self, *, seconds: float) -> Flow[T, E]:
        return Flow(Delay(self.expr, seconds=seconds))

    def recover(self, *, default: T) -> Flow[T, NoError]:
        return Flow(Recover(self.expr, default=default))

    def recover_with(self, *, handler: Callable[[E], T]) -> Flow[T, NoError]:
        return Flow(RecoverWith(self.expr, handler=handler))

    def repeat_until(
        self,
        *,
        condition: Predicate[T],
        policy: RepeatPolicy | None = None,
        max_rounds: int | None = None,
        delay_seconds: float = 0.0,
    ) -> Flow[T, E | ConditionNotMetError]:
        if policy is None:
            if max_rounds is None:
                raise ValueError("repeat_until(): must provide either 'policy' or 'max_rounds'")
            policy = RepeatPolicy(max_rounds=max_rounds, delay_seconds=delay_seconds)
        return Flow(RepeatUntil(self.expr, condition=condition, policy=policy))

    def rate_limit(
        self,
        *,
        policy: RateLimitPolicy | None = None,
        max_per_second: float | None = None,
        burst: int | None = None,
    ) -> Flow[T, E]:
        if policy is None:
            if max_per_second is None:
                raise ValueError("rate_limit(): must provide either 'policy' or 'max_per_second'")
            policy = RateLimitPolicy(max_per_second=max_per_second, burst=burst)
        return Flow(RateLimit(self.expr, policy=policy))

    def bimap_tap(
        self,
        *,
        on_ok: Callable[[T], None],
        on_err: Callable[[E], None],
    ) -> Flow[T, E]:
        """Apply side effects to both success and error cases."""
        return Flow(BimapTap(self.expr, on_ok=on_ok, on_err=on_err))

    def filter_or(
        self,
        *,
        predicate: Predicate[T],
        error: Callable[[T], E],
    ) -> Flow[T, E]:
        """Filter success value by predicate, convert to error if fails."""
        return Flow(FilterOr(self.expr, predicate=predicate, error=error))

    def fallback(self, *alternatives: LazyCoroResult[T, E]) -> Flow[T, E]:
        """Try alternatives on error, left-to-right until success."""
        return Flow(Fallback(self.expr, alternatives=alternatives))

    def replicate(self, *, n: int) -> Flow[list[T], E]:
        """Run computation N times, collect all results."""
        return Flow(Replicate(self.expr, n=n))

    def compile(self) -> LazyCoroResult[T, E]:
        """Compile Flow AST into executable LazyCoroResult."""
        return self.expr.lower()

    def lower(self) -> LazyCoroResult[T, E]:
        """Alias for compile() - compiles Flow AST into executable LazyCoroResult."""
        return self.compile()

# LazyCoroResultWriter Sugar (FlowWriter)
@dataclass(frozen=True, slots=True)
class FlowWriter[T, E, W]:
    """
    Fluent builder for chaining combinators (LazyCoroResultWriter).

    Direct value-based implementation (no AST) for simplicity.
    Each method calls the corresponding *_w combinator.
    """

    value: LazyCoroResultWriter[T, E, W]

    def retry(
        self,
        *,
        policy: RetryPolicy[E] | None = None,
        times: int | None = None,
        delay_seconds: float = 0.0,
        retry_on: Predicate[E] | None = None,
    ) -> FlowWriter[T, E, W]:
        from .control.retry import retry_writer
        if policy is None:
            if times is None:
                raise ValueError("retry(): must provide either 'policy' or 'times'")
            policy = RetryPolicy.fixed(times=times, delay_seconds=delay_seconds, retry_on=retry_on)  # type: ignore[type-var]
        return FlowWriter(retry_writer(self.value, policy=policy))

    def timeout(self, *, seconds: float) -> FlowWriter[T, E | TimeoutError, W]:
        from .time.timeout import timeout_writer
        return FlowWriter(timeout_writer(self.value, seconds=seconds))

    def tap(self, effect: Callable[[T], None]) -> FlowWriter[T, E, W]:
        from .transform.effects import tap_writer
        return FlowWriter(tap_writer(self.value, effect=effect))

    def tap_async(self, effect: Callable[[T], Awaitable[None]]) -> FlowWriter[T, E, W]:
        from .transform.effects import tap_async_writer
        return FlowWriter(tap_async_writer(self.value, effect=effect))

    def tap_err(self, effect: Callable[[E], None]) -> FlowWriter[T, E, W]:
        from .transform.effects import tap_err_writer
        return FlowWriter(tap_err_writer(self.value, effect=effect))

    def tap_err_async(self, effect: Callable[[E], Awaitable[None]]) -> FlowWriter[T, E, W]:
        from .transform.effects import tap_err_async_writer
        return FlowWriter(tap_err_async_writer(self.value, effect=effect))

    def ensure(self, predicate: Predicate[T], error: Callable[[T], E]) -> FlowWriter[T, E, W]:
        from .control.guard import ensure_writer
        return FlowWriter(ensure_writer(self.value, predicate=predicate, error=error))

    def reject(self, predicate: Predicate[T], error: Callable[[T], E]) -> FlowWriter[T, E, W]:
        from .control.guard import reject_writer
        return FlowWriter(reject_writer(self.value, predicate=predicate, error=error))

    def race_ok(
        self,
        *others: LazyCoroResultWriter[T, E, W],
        policy: RaceOkPolicy | None = None,
        cancel_pending: bool = True,
        error_strategy: Literal["first", "last"] = "last",
    ) -> FlowWriter[T, E, W]:
        from .concurrency.race import race_ok_writer
        if policy is None:
            policy = RaceOkPolicy(cancel_pending=cancel_pending, error_strategy=error_strategy)
        return FlowWriter(race_ok_writer(self.value, *others, policy=policy))

    def best_of(self, *, n: int, key: Selector[T, float]) -> FlowWriter[T, E, W]:
        from .selection.best import best_of_writer
        return FlowWriter(best_of_writer(self.value, n=n, key=key))

    def delay(self, *, seconds: float) -> FlowWriter[T, E, W]:
        from .time.delay import delay_writer
        return FlowWriter(delay_writer(self.value, seconds=seconds))

    def recover(self, *, default: T) -> FlowWriter[T, NoError, W]:
        from .control.recover import recover_writer
        return FlowWriter(recover_writer(self.value, default=default))

    def recover_with(self, *, handler: Callable[[E], T]) -> FlowWriter[T, NoError, W]:
        from .control.recover import recover_with_writer
        return FlowWriter(recover_with_writer(self.value, handler=handler))

    def repeat_until(
        self,
        *,
        condition: Predicate[T],
        policy: RepeatPolicy | None = None,
        max_rounds: int | None = None,
        delay_seconds: float = 0.0,
    ) -> FlowWriter[T, E | ConditionNotMetError, W]:
        from .control.repeat import repeat_until_writer
        if policy is None:
            if max_rounds is None:
                raise ValueError("repeat_until(): must provide either 'policy' or 'max_rounds'")
            policy = RepeatPolicy(max_rounds=max_rounds, delay_seconds=delay_seconds)
        return FlowWriter(repeat_until_writer(self.value, condition=condition, policy=policy))

    def rate_limit(
        self,
        *,
        policy: RateLimitPolicy | None = None,
        max_per_second: float | None = None,
        burst: int | None = None,
    ) -> FlowWriter[T, E, W]:
        from .concurrency.rate_limit import rate_limit_writer
        if policy is None:
            if max_per_second is None:
                raise ValueError("rate_limit(): must provide either 'policy' or 'max_per_second'")
            policy = RateLimitPolicy(max_per_second=max_per_second, burst=burst)
        return FlowWriter(rate_limit_writer(self.value, policy=policy))

    def bimap_tap(
        self,
        *,
        on_ok: Callable[[T], None],
        on_err: Callable[[E], None],
    ) -> FlowWriter[T, E, W]:
        """Apply side effects to both success and error cases."""
        from .transform.effects import bimap_tap_writer
        return FlowWriter(bimap_tap_writer(self.value, on_ok=on_ok, on_err=on_err))

    def filter_or(
        self,
        *,
        predicate: Predicate[T],
        error: Callable[[T], E],
    ) -> FlowWriter[T, E, W]:
        """Filter success value by predicate, convert to error if fails."""
        from .transform.filter import filter_or_writer
        return FlowWriter(filter_or_writer(self.value, predicate=predicate, error=error))

    def fallback(self, *alternatives: LazyCoroResultWriter[T, E, W]) -> FlowWriter[T, E, W]:
        """Try alternatives on error, left-to-right until success."""
        from .control.fallback import fallback_chain_writer
        return FlowWriter(fallback_chain_writer(self.value, *alternatives))

    def replicate(self, *, n: int) -> FlowWriter[list[T], E, W]:
        """Run computation N times, collect all results."""
        from .collection.replicate import replicate_writer
        return FlowWriter(replicate_writer(self.value, n=n))

    def compile(self) -> LazyCoroResultWriter[T, E, W]:
        """Compile and return the LazyCoroResultWriter."""
        return self.value

    def lower(self) -> LazyCoroResultWriter[T, E, W]:
        """Alias for compile() - compiles FlowWriter into executable LazyCoroResultWriter."""
        return self.compile()

# Generic FlowM for custom monads
@dataclass(frozen=True, slots=True)
class FlowM[M, Raw, T, E]:
    """Generic fluent builder for any monad following extract + wrap pattern."""

    value: M
    extract: Callable[[Raw], Result[T, E]]
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, Raw]]], M]

    # Combinator functions - user provides these for their monad
    _retry: Callable[[M, RetryPolicy[E]], M]
    _tap: Callable[[M, Callable[[T], None]], M]
    _tap_err: Callable[[M, Callable[[E], None]], M]
    _delay: Callable[[M, float], M]
    _rate_limit: Callable[[M, RateLimitPolicy], M]
    _ensure: Callable[[M, Predicate[T], Callable[[T], E]], M]
    _reject: Callable[[M, Predicate[T], Callable[[T], E]], M]

    def retry(
        self,
        *,
        policy: RetryPolicy[E] | None = None,
        times: int | None = None,
        delay_seconds: float = 0.0,
        retry_on: Predicate[E] | None = None,
    ) -> FlowM[M, Raw, T, E]:
        if policy is None:
            if times is None:
                raise ValueError("retry(): must provide either 'policy' or 'times'")
            policy = RetryPolicy.fixed(times=times, delay_seconds=delay_seconds, retry_on=retry_on)  # type: ignore[type-var]
        return FlowM(
            self._retry(self.value, policy),
            self.extract,
            self.wrap,
            self._retry,
            self._tap,
            self._tap_err,
            self._delay,
            self._rate_limit,
            self._ensure,
            self._reject,
        )

    def tap(self, effect: Callable[[T], None]) -> FlowM[M, Raw, T, E]:
        return FlowM(
            self._tap(self.value, effect),
            self.extract,
            self.wrap,
            self._retry,
            self._tap,
            self._tap_err,
            self._delay,
            self._rate_limit,
            self._ensure,
            self._reject,
        )

    def tap_err(self, effect: Callable[[E], None]) -> FlowM[M, Raw, T, E]:
        return FlowM(
            self._tap_err(self.value, effect),
            self.extract,
            self.wrap,
            self._retry,
            self._tap,
            self._tap_err,
            self._delay,
            self._rate_limit,
            self._ensure,
            self._reject,
        )

    def delay(self, *, seconds: float) -> FlowM[M, Raw, T, E]:
        return FlowM(
            self._delay(self.value, seconds),
            self.extract,
            self.wrap,
            self._retry,
            self._tap,
            self._tap_err,
            self._delay,
            self._rate_limit,
            self._ensure,
            self._reject,
        )

    def rate_limit(
        self,
        *,
        policy: RateLimitPolicy | None = None,
        max_per_second: float | None = None,
        burst: int | None = None,
    ) -> FlowM[M, Raw, T, E]:
        if policy is None:
            if max_per_second is None:
                raise ValueError("rate_limit(): must provide either 'policy' or 'max_per_second'")
            policy = RateLimitPolicy(max_per_second=max_per_second, burst=burst)
        return FlowM(
            self._rate_limit(self.value, policy),
            self.extract,
            self.wrap,
            self._retry,
            self._tap,
            self._tap_err,
            self._delay,
            self._rate_limit,
            self._ensure,
            self._reject,
        )

    def ensure(self, predicate: Predicate[T], error: Callable[[T], E]) -> FlowM[M, Raw, T, E]:
        return FlowM(
            self._ensure(self.value, predicate, error),
            self.extract,
            self.wrap,
            self._retry,
            self._tap,
            self._tap_err,
            self._delay,
            self._rate_limit,
            self._ensure,
            self._reject,
        )

    def reject(self, predicate: Predicate[T], error: Callable[[T], E]) -> FlowM[M, Raw, T, E]:
        return FlowM(
            self._reject(self.value, predicate, error),
            self.extract,
            self.wrap,
            self._retry,
            self._tap,
            self._tap_err,
            self._delay,
            self._rate_limit,
            self._ensure,
            self._reject,
        )

    def lower(self) -> M:
        return self.value

# Constructor functions
def ast[T, E](interp: LazyCoroResult[T, E]) -> Flow[T, E]:
    """Build a Flow (AST) from LazyCoroResult for fluent combinator chaining."""
    return Flow(Base(interp))

def ast_writer[T, E, W](interp: LazyCoroResultWriter[T, E, W]) -> FlowWriter[T, E, W]:
    """Build a FlowWriter from LazyCoroResultWriter for fluent combinator chaining."""
    return FlowWriter(interp)

def ast_many[T, E](
    candidates: Sequence[LazyCoroResult[T, E]],
    *,
    key: Selector[T, float],
) -> Flow[T, E]:
    """Build Flow from multiple candidates, selecting best by key."""
    return Flow(BestOfMany(candidates=candidates, key=key))

def ast_many_writer[T, E, W](
    candidates: Sequence[LazyCoroResultWriter[T, E, W]],
    *,
    key: Selector[T, float],
) -> FlowWriter[T, E, W]:
    """Build FlowWriter from multiple candidates, selecting best by key."""
    from .selection.best import best_of_many_writer
    return FlowWriter(best_of_many_writer(candidates, key=key))

def ast_bracket[T, R, E](
    acquire: LazyCoroResult[T, E],
    *,
    release: Callable[[T], Awaitable[None]],
    use: Callable[[T], LazyCoroResult[R, E]],
) -> Flow[R, E]:
    """Start Flow with resource management pattern (acquire → use → release)."""
    return Flow(Bracket(acquire=acquire, release=release, use=use))

def ast_bracket_writer[T, R, E, W](
    acquire: LazyCoroResultWriter[T, E, W],
    *,
    release: Callable[[T], Awaitable[None]],
    use: Callable[[T], LazyCoroResultWriter[R, E, W]],
) -> FlowWriter[R, E, W]:
    """Start FlowWriter with resource management pattern (acquire → use → release)."""
    from .control.bracket import bracket_writer
    return FlowWriter(bracket_writer(acquire, release=release, use=use))

# Primary functions (flow is the main API)
flow = ast
flow_writer = ast_writer
flow_many = ast_many
flow_many_writer = ast_many_writer
flow_bracket = ast_bracket
flow_bracket_writer = ast_bracket_writer

# Aliases: chain
chain = ast
chain_writer = ast_writer
chain_many = ast_many
chain_many_writer = ast_many_writer
chain_bracket = ast_bracket
chain_bracket_writer = ast_bracket_writer

__all__ = (
    # Core types
    "Expr",
    "Flow",
    "FlowWriter",
    "FlowM",
    "Interpreter",
    # Primary functions
    "flow",
    "flow_writer",
    "flow_many",
    "flow_many_writer",
    "flow_bracket",
    "flow_bracket_writer",
    # Aliases: chain
    "chain",
    "chain_writer",
    "chain_many",
    "chain_many_writer",
    "chain_bracket",
    "chain_bracket_writer",
    # Aliases: ast (legacy)
    "ast",
    "ast_writer",
    "ast_many",
    "ast_many_writer",
    "ast_bracket",
    "ast_bracket_writer",
)
