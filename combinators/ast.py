"""
Generic AST for fluent combinator chaining.

Architecture:
- FlowM[M, Raw, T, E] - generic Flow parameterized by monad
- Interpreter[M, Raw] - typeclass with extract + wrap + combinators
- Flow (LazyCoroResult) and FlowW (LazyCoroResultWriter) - sugar implementations

For custom monads:
1. Create your Interpreter with extract, wrap, and combinator functions
2. Use FlowM directly with your interpreter
3. Or create your own sugar class following the Flow/FlowW pattern
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


# ============================================================================
# Generic Interpreter Protocol
# ============================================================================


@dataclass(frozen=True, slots=True)
class Interpreter[M, Raw, T, E]:
    """
    Typeclass for interpreting AST into a specific monad.

    Users implement this for their custom monads to use FlowM.

    NOTE: This is a simplified interpreter that doesn't handle type-changing
    operations like timeout (E -> E | TimeoutError). For those, use the
    concrete Flow/FlowW implementations or handle manually.
    """

    # Core operations
    extract: Callable[[Raw], Result[T, E]]
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, Raw]]], M]

    # Combinator functions (these call the generic *M functions)
    retry: Callable[[M, RetryPolicy[E]], M]
    tap: Callable[[M, Callable[[T], None]], M]
    tap_err: Callable[[M, Callable[[E], None]], M]
    delay: Callable[[M, float], M]
    rate_limit: Callable[[M, RateLimitPolicy], M]


# ============================================================================
# LazyCoroResult Sugar (Flow) - Existing Implementation
# ============================================================================


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

    def lower(self) -> LazyCoroResult[T, E]:
        return self.expr.lower()


# ============================================================================
# LazyCoroResultWriter Sugar (FlowW)
# ============================================================================


@dataclass(frozen=True, slots=True)
class FlowW[T, E, W]:
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
    ) -> FlowW[T, E, W]:
        from .control.retry import retry_w
        if policy is None:
            if times is None:
                raise ValueError("retry(): must provide either 'policy' or 'times'")
            policy = RetryPolicy.fixed(times=times, delay_seconds=delay_seconds, retry_on=retry_on)  # type: ignore[type-var]
        return FlowW(retry_w(self.value, policy=policy))

    def timeout(self, *, seconds: float) -> FlowW[T, E | TimeoutError, W]:
        from .time.timeout import timeout_w
        return FlowW(timeout_w(self.value, seconds=seconds))

    def tap(self, effect: Callable[[T], None]) -> FlowW[T, E, W]:
        from .transform.effects import tap_w
        return FlowW(tap_w(self.value, effect=effect))

    def tap_async(self, effect: Callable[[T], Awaitable[None]]) -> FlowW[T, E, W]:
        from .transform.effects import tap_async_w
        return FlowW(tap_async_w(self.value, effect=effect))

    def tap_err(self, effect: Callable[[E], None]) -> FlowW[T, E, W]:
        from .transform.effects import tap_err_w
        return FlowW(tap_err_w(self.value, effect=effect))

    def tap_err_async(self, effect: Callable[[E], Awaitable[None]]) -> FlowW[T, E, W]:
        from .transform.effects import tap_err_async_w
        return FlowW(tap_err_async_w(self.value, effect=effect))

    def ensure(self, predicate: Predicate[T], error: Callable[[T], E]) -> FlowW[T, E, W]:
        from .control.guard import ensure_w
        return FlowW(ensure_w(self.value, predicate=predicate, error=error))

    def reject(self, predicate: Predicate[T], error: Callable[[T], E]) -> FlowW[T, E, W]:
        from .control.guard import reject_w
        return FlowW(reject_w(self.value, predicate=predicate, error=error))

    def race_ok(
        self,
        *others: LazyCoroResultWriter[T, E, W],
        policy: RaceOkPolicy | None = None,
        cancel_pending: bool = True,
        error_strategy: Literal["first", "last"] = "last",
    ) -> FlowW[T, E, W]:
        from .concurrency.race import race_ok_w
        if policy is None:
            policy = RaceOkPolicy(cancel_pending=cancel_pending, error_strategy=error_strategy)
        return FlowW(race_ok_w(self.value, *others, policy=policy))

    def best_of(self, *, n: int, key: Selector[T, float]) -> FlowW[T, E, W]:
        from .selection.best import best_of_w
        return FlowW(best_of_w(self.value, n=n, key=key))

    def delay(self, *, seconds: float) -> FlowW[T, E, W]:
        from .time.delay import delay_w
        return FlowW(delay_w(self.value, seconds=seconds))

    def recover(self, *, default: T) -> FlowW[T, NoError, W]:
        from .control.recover import recover_w
        return FlowW(recover_w(self.value, default=default))

    def recover_with(self, *, handler: Callable[[E], T]) -> FlowW[T, NoError, W]:
        from .control.recover import recover_with_w
        return FlowW(recover_with_w(self.value, handler=handler))

    def repeat_until(
        self,
        *,
        condition: Predicate[T],
        policy: RepeatPolicy | None = None,
        max_rounds: int | None = None,
        delay_seconds: float = 0.0,
    ) -> FlowW[T, E | ConditionNotMetError, W]:
        from .control.repeat import repeat_until_w
        if policy is None:
            if max_rounds is None:
                raise ValueError("repeat_until(): must provide either 'policy' or 'max_rounds'")
            policy = RepeatPolicy(max_rounds=max_rounds, delay_seconds=delay_seconds)
        return FlowW(repeat_until_w(self.value, condition=condition, policy=policy))

    def rate_limit(
        self,
        *,
        policy: RateLimitPolicy | None = None,
        max_per_second: float | None = None,
        burst: int | None = None,
    ) -> FlowW[T, E, W]:
        from .concurrency.rate_limit import rate_limit_w
        if policy is None:
            if max_per_second is None:
                raise ValueError("rate_limit(): must provide either 'policy' or 'max_per_second'")
            policy = RateLimitPolicy(max_per_second=max_per_second, burst=burst)
        return FlowW(rate_limit_w(self.value, policy=policy))

    def lower(self) -> LazyCoroResultWriter[T, E, W]:
        return self.value


# ============================================================================
# Generic FlowM for custom monads
# ============================================================================


@dataclass(frozen=True, slots=True)
class FlowM[M, Raw, T, E]:
    """
    Generic fluent builder for any monad following extract + wrap pattern.

    This is the base building block for custom monads. It stores:
    - value: The current monadic value
    - extract: Raw -> Result[T, E] to extract result for combinator logic
    - wrap: Thunk -> M to wrap computation back into monad

    Example for custom monad:

        # Define your interpreter functions
        def my_extract(raw: MyRaw[T, E]) -> Result[T, E]:
            return raw.result

        def my_wrap(thunk: Callable[[], Coro[MyRaw[T, E]]]) -> MyMonad[T, E]:
            return MyMonad(thunk)

        # Create Flow factory
        def my_flow(value: MyMonad[T, E]) -> FlowM[MyMonad[T, E], MyRaw[T, E], T, E]:
            return FlowM(value, my_extract, my_wrap, my_retry, my_timeout, ...)

    NOTE: Type-changing operations (timeout, recover) require creating new FlowM
    with updated type parameters. See Flow/FlowW for reference implementations.
    """

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


# ============================================================================
# Constructor functions
# ============================================================================


def ast[T, E](interp: LazyCoroResult[T, E]) -> Flow[T, E]:
    """Build a Flow (AST) from LazyCoroResult for fluent combinator chaining."""
    return Flow(Base(interp))


def ast_w[T, E, W](interp: LazyCoroResultWriter[T, E, W]) -> FlowW[T, E, W]:
    """Build a FlowW from LazyCoroResultWriter for fluent combinator chaining."""
    return FlowW(interp)


def ast_many[T, E](
    candidates: Sequence[LazyCoroResult[T, E]],
    *,
    key: Selector[T, float],
) -> Flow[T, E]:
    """Build Flow from multiple candidates, selecting best by key."""
    return Flow(BestOfMany(candidates=candidates, key=key))


def ast_many_w[T, E, W](
    candidates: Sequence[LazyCoroResultWriter[T, E, W]],
    *,
    key: Selector[T, float],
) -> FlowW[T, E, W]:
    """Build FlowW from multiple candidates, selecting best by key."""
    from .selection.best import best_of_many_w
    return FlowW(best_of_many_w(candidates, key=key))


def ast_bracket[T, R, E](
    acquire: LazyCoroResult[T, E],
    *,
    release: Callable[[T], Awaitable[None]],
    use: Callable[[T], LazyCoroResult[R, E]],
) -> Flow[R, E]:
    """Start Flow with resource management pattern (acquire → use → release)."""
    return Flow(Bracket(acquire=acquire, release=release, use=use))


def ast_bracket_w[T, R, E, W](
    acquire: LazyCoroResultWriter[T, E, W],
    *,
    release: Callable[[T], Awaitable[None]],
    use: Callable[[T], LazyCoroResultWriter[R, E, W]],
) -> FlowW[R, E, W]:
    """Start FlowW with resource management pattern (acquire → use → release)."""
    from .control.bracket import bracket_w
    return FlowW(bracket_w(acquire, release=release, use=use))


__all__ = (
    # LazyCoroResult AST
    "Expr",
    "Flow",
    "ast",
    "ast_bracket",
    "ast_many",
    # LazyCoroResultWriter AST
    "FlowW",
    "ast_w",
    "ast_bracket_w",
    "ast_many_w",
    # Generic AST
    "FlowM",
    "Interpreter",
)
