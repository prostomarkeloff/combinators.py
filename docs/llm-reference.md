# Combinators.py: LLM Reference Documentation

## Purpose
Structured reference for code generation and refactoring. Maximally concise and precise.

---

## Architecture Overview

### Core Types

```python
type Interp[T, E] = LazyCoroResult[T, E]  # Lazy async Result
type LCR[T, E] = LazyCoroResult[T, E]     # Alias
type NoError = Never                       # Bottom type for "never fails"
type Predicate[T] = Callable[[T], bool]
type Selector[T, K] = Callable[[T], K]
type Route[T, R, E] = Callable[[T], Awaitable[Result[R, E]]]
```

### Monads

1. **LazyCoroResult[T, E]**: Lazy async Result (from kungfu)
   - Raw type: `Result[T, E]`
   - Extract: `identity`
   - Wrap: `LazyCoroResult`

2. **LazyCoroResultWriter[T, E, W]**: Lazy async Result with Writer
   - Raw type: `WriterResult[T, E, Log[W]]`
   - Extract: `extract_writer_result`
   - Wrap: `wrap_lazy_coro_result_writer`

### Extract + Wrap Pattern

Generic combinators use extract + wrap:

```python
def combinatorM[M, T, E, Raw](
    interp: Callable[[], Coroutine[Any, Any, Raw]],
    *,
    extract: Callable[[Raw], Result[T, E]],
    wrap: Callable[[Callable[[], Coroutine[Any, Any, Raw]]], M],
    # ... combinator-specific params
) -> M:
    async def run() -> Raw:
        raw = await interp()
        result = extract(raw)
        # ... combinator logic using Result
        return new_raw
    return wrap(run)
```

Sugar functions call generic with concrete extract/wrap:

```python
def combinator[T, E](interp: LazyCoroResult[T, E], ...) -> LazyCoroResult[T, E]:
    return combinatorM(interp, extract=identity, wrap=LazyCoroResult, ...)

def combinator_w[T, E, W](interp: LazyCoroResultWriter[T, E, W], ...) -> LazyCoroResultWriter[T, E, W]:
    return combinatorM(interp, extract=extract_writer_result, wrap=wrap_lazy_coro_result_writer, ...)
```

---

## API Reference

### Lift Module (`combinators.lift`)

**Import:** `from combinators import lift as L`

#### Constructors

```python
L.pure(value: T) -> Interp[T, Never]
L.fail(error: E) -> Interp[Never, E]
L.from_result(result: Result[T, E]) -> Interp[T, E]
L.optional(value: T | None, error: E) -> Interp[T, E]
L.catching(func: Callable[[], T], error_type: type[E]) -> Interp[T, E]
L.catching_async(func: Callable[[], Awaitable[T]], error_type: type[E]) -> Interp[T, E]
L.call(func: Callable[P, Awaitable[Result[T, E]]], *args: P.args, **kwargs: P.kwargs) -> Interp[T, E]
L.wrap_async(thunk: Callable[[], Awaitable[Result[T, E]]]) -> Interp[T, E]
```

#### Decorators

```python
@L.lifted
async def func(...) -> Result[T, E]: ...
# Returns: Callable[..., Interp[T, E]]
```

#### Down (Execution)

```python
L.to_result(interp: Interp[T, E]) -> Awaitable[Result[T, E]]
L.unsafe(interp: Interp[T, E]) -> Awaitable[T]  # Raises on Error
L.or_else(interp: Interp[T, E], default: T) -> Awaitable[T]
```

### Control Flow Combinators

#### Retry

```python
from combinators.control import RetryPolicy

# Policy constructors
RetryPolicy.fixed(times: int, delay_seconds: float = 0.0, retry_on: Predicate[E] | None = None) -> RetryPolicy[E]
RetryPolicy.exponential(times: int, initial: float = 0.1, multiplier: float = 2.0, max_delay: float = 60.0, retry_on: Predicate[E] | None = None) -> RetryPolicy[E]
RetryPolicy.jitter(times: int, base: float = 1.0, jitter_factor: float = 0.5, retry_on: Predicate[E] | None = None) -> RetryPolicy[E]
RetryPolicy.exponential_jitter(times: int, initial: float = 0.1, multiplier: float = 2.0, max_delay: float = 60.0, jitter_factor: float = 0.3, retry_on: Predicate[E] | None = None) -> RetryPolicy[E]

# Combinators
retry(interp: Interp[T, E], *, policy: RetryPolicy[E]) -> Interp[T, E]
retry_w(interp: LazyCoroResultWriter[T, E, W], *, policy: RetryPolicy[E]) -> LazyCoroResultWriter[T, E, W]
retryM[M, T, E, Raw](interp: Callable[[], Coro[Raw]], *, extract: Callable[[Raw], Result[T, E]], wrap: Callable[[Callable[[], Coro[Raw]]], M], policy: RetryPolicy[E]) -> M
```

#### Fallback

```python
fallback(primary: Interp[T, E], secondary: Interp[T, E]) -> Interp[T, E]
fallback_chain(*interps: Interp[T, E]) -> Interp[T, E]
fallback_with(primary: Interp[T, E], *, secondary: Callable[[E], Interp[T, E]]) -> Interp[T, E]
fallback_w(primary: LazyCoroResultWriter[T, E, W], secondary: LazyCoroResultWriter[T, E, W]) -> LazyCoroResultWriter[T, E, W]
fallback_chain_w(*interps: LazyCoroResultWriter[T, E, W]) -> LazyCoroResultWriter[T, E, W]
fallbackM[M, T, E, Raw](primary: Callable[[], Coro[Raw]], secondary: Callable[[], Coro[Raw]], *, extract: Callable[[Raw], Result[T, E]], wrap: Callable[[Callable[[], Coro[Raw]]], M]) -> M
fallback_chainM[M, T, E, Raw](*interps: Callable[[], Coro[Raw]], *, extract: Callable[[Raw], Result[T, E]], wrap: Callable[[Callable[[], Coro[Raw]]], M]) -> M
```

#### Recover

```python
recover(interp: Interp[T, E], *, default: T) -> Interp[T, NoError]
recover_with(interp: Interp[T, E], *, handler: Callable[[E], T]) -> Interp[T, NoError]
recover_w(interp: LazyCoroResultWriter[T, E, W], *, default: T) -> LazyCoroResultWriter[T, NoError, W]
recover_with_w(interp: LazyCoroResultWriter[T, E, W], *, handler: Callable[[E], T]) -> LazyCoroResultWriter[T, NoError, W]
```

#### Guard (Ensure/Reject)

```python
ensure(interp: Interp[T, E], *, predicate: Predicate[T], error: Callable[[T], E]) -> Interp[T, E]
reject(interp: Interp[T, E], *, predicate: Predicate[T], error: Callable[[T], E]) -> Interp[T, E]
ensure_w(interp: LazyCoroResultWriter[T, E, W], *, predicate: Predicate[T], error: Callable[[T], E]) -> LazyCoroResultWriter[T, E, W]
reject_w(interp: LazyCoroResultWriter[T, E, W], *, predicate: Predicate[T], error: Callable[[T], E]) -> LazyCoroResultWriter[T, E, W]
```

#### Bracket (Resource Management)

```python
bracket[T, R, E](acquire: Interp[T, E], *, release: Callable[[T], Awaitable[None]], use: Callable[[T], Interp[R, E]]) -> Interp[R, E]
bracket_on_error[T, R, E](acquire: Interp[T, E], *, release: Callable[[T], Awaitable[None]], use: Callable[[T], Interp[R, E]]) -> Interp[R, E]
with_resource[T, R, E](acquire: Interp[T, E], *, use: Callable[[T], Interp[R, E]]) -> Interp[R, E]  # Auto-release on success
bracket_w[T, R, E, W](acquire: LazyCoroResultWriter[T, E, W], *, release: Callable[[T], Awaitable[None]], use: Callable[[T], LazyCoroResultWriter[R, E, W]]) -> LazyCoroResultWriter[R, E, W]
bracketM[M, T, R, E, Raw](acquire: Callable[[], Coro[Raw]], *, release: Callable[[T], Awaitable[None]], use: Callable[[T], Callable[[], Coro[Raw]]], extract: Callable[[Raw], Result[T, E]], wrap: Callable[[Callable[[], Coro[Raw]]], M]) -> M
```

#### Repeat

```python
from combinators.control import RepeatPolicy

RepeatPolicy(max_rounds: int, delay_seconds: float = 0.0)

repeat_until[T, E](interp: Interp[T, E], *, condition: Predicate[T], policy: RepeatPolicy) -> Interp[T, E | ConditionNotMetError]
repeat_until_w[T, E, W](interp: LazyCoroResultWriter[T, E, W], *, condition: Predicate[T], policy: RepeatPolicy) -> LazyCoroResultWriter[T, E | ConditionNotMetError, W]
```

### Concurrency Combinators

#### Race

```python
from combinators.concurrency import RaceOkPolicy

RaceOkPolicy(cancel_pending: bool = True, error_strategy: Literal["first", "last"] = "last")

race(*interps: Interp[T, E]) -> Interp[T, E]  # First to finish (Ok or Error)
race_ok(*interps: Interp[T, E], policy: RaceOkPolicy = RaceOkPolicy()) -> Interp[T, E]  # First Ok wins
race_w(*interps: LazyCoroResultWriter[T, E, W]) -> LazyCoroResultWriter[T, E, W]
race_ok_w(*interps: LazyCoroResultWriter[T, E, W], policy: RaceOkPolicy = RaceOkPolicy()) -> LazyCoroResultWriter[T, E, W]
raceM[M, T, E, Raw](*interps: Callable[[], Coro[Raw]], wrap: Callable[[Callable[[], Coro[Raw]]], M]) -> M
race_okM[M, T, E, Raw](*interps: Callable[[], Coro[Raw]], *, extract: Callable[[Raw], Result[T, E]], wrap: Callable[[Callable[[], Coro[Raw]]], M], policy: RaceOkPolicy = RaceOkPolicy()) -> M
```

#### Parallel

```python
parallel(interps: Sequence[Interp[T, E]]) -> Interp[list[T], E]
parallel_w(interps: Sequence[LazyCoroResultWriter[T, E, W]]) -> LazyCoroResultWriter[list[T], E, W]
```

#### Batch

```python
batch[A, T, E](items: Sequence[A], handler: Callable[[A], Interp[T, E]], *, concurrency: int = 10) -> Interp[list[T], E]
batch_all[A, T, E](items: Sequence[A], handler: Callable[[A], Interp[T, E]], *, concurrency: int = 10) -> Interp[list[Result[T, E]], NoError]  # Never fails, collects all results
batch_w[A, T, E, W](items: Sequence[A], handler: Callable[[A], LazyCoroResultWriter[T, E, W]], *, concurrency: int = 10) -> LazyCoroResultWriter[list[T], E, W]
batch_all_w[A, T, E, W](items: Sequence[A], handler: Callable[[A], LazyCoroResultWriter[T, E, W]], *, concurrency: int = 10) -> LazyCoroResultWriter[list[Result[T, E]], NoError, W]
```

#### Gather

```python
gather2[T1, T2, E](interp1: Interp[T1, E], interp2: Interp[T2, E]) -> Interp[tuple[T1, T2], E]
gather3[T1, T2, T3, E](interp1: Interp[T1, E], interp2: Interp[T2, E], interp3: Interp[T3, E]) -> Interp[tuple[T1, T2, T3], E]
gather2_w[T1, T2, E, W](interp1: LazyCoroResultWriter[T1, E, W], interp2: LazyCoroResultWriter[T2, E, W]) -> LazyCoroResultWriter[tuple[T1, T2], E, W]
gather3_w[T1, T2, T3, E, W](interp1: LazyCoroResultWriter[T1, E, W], interp2: LazyCoroResultWriter[T2, E, W], interp3: LazyCoroResultWriter[T3, E, W]) -> LazyCoroResultWriter[tuple[T1, T2, T3], E, W]
```

#### Zip

```python
zip_par[T1, T2, E](interp1: Interp[T1, E], interp2: Interp[T2, E]) -> Interp[tuple[T1, T2], E]  # Alias for gather2
zip_with[T1, T2, R, E](interp1: Interp[T1, E], interp2: Interp[T2, E], f: Callable[[T1, T2], R]) -> Interp[R, E]
zip_par_w[T1, T2, E, W](interp1: LazyCoroResultWriter[T1, E, W], interp2: LazyCoroResultWriter[T2, E, W]) -> LazyCoroResultWriter[tuple[T1, T2], E, W]
zip_with_w[T1, T2, R, E, W](interp1: LazyCoroResultWriter[T1, E, W], interp2: LazyCoroResultWriter[T2, E, W], f: Callable[[T1, T2], R]) -> LazyCoroResultWriter[R, E, W]
```

#### Rate Limit

```python
from combinators.concurrency import RateLimitPolicy

RateLimitPolicy(max_per_second: float, burst: int | None = None)

rate_limit(interp: Interp[T, E], *, policy: RateLimitPolicy) -> Interp[T, E]
rate_limit_w(interp: LazyCoroResultWriter[T, E, W], *, policy: RateLimitPolicy) -> LazyCoroResultWriter[T, E, W]
rate_limitM[M, T, E, Raw](interp: Callable[[], Coro[Raw]], *, extract: Callable[[Raw], Result[T, E]], wrap: Callable[[Callable[[], Coro[Raw]]], M], policy: RateLimitPolicy) -> M
```

### Collection Combinators

#### Traverse

```python
traverse[A, T, E](items: Sequence[A], handler: Callable[[A], Interp[T, E]]) -> Interp[list[T], E]  # Sequential
traverse_par[A, T, E](items: Sequence[A], handler: Callable[[A], Interp[T, E]], *, concurrency: int = 10) -> Interp[list[T], E]  # Parallel
traverse_w[A, T, E, W](items: Sequence[A], handler: Callable[[A], LazyCoroResultWriter[T, E, W]]) -> LazyCoroResultWriter[list[T], E, W]
traverse_par_w[A, T, E, W](items: Sequence[A], handler: Callable[[A], LazyCoroResultWriter[T, E, W]], *, concurrency: int = 10) -> LazyCoroResultWriter[list[T], E, W]
traverseM[M, A, T, E, RawIn, RawOut](items: Sequence[A], handler: Callable[[A], Callable[[], Coro[RawIn]]], *, extract: Callable[[RawIn], Result[T, E]], combine_ok: Callable[[list[tuple[T, RawIn]]], RawOut], combine_err: Callable[[E, list[RawIn]], RawOut], wrap: Callable[[Callable[[], Coro[RawOut]]], M]) -> M
```

#### Sequence

```python
sequence[T, E](interps: Sequence[Interp[T, E]]) -> Interp[list[T], E]
sequence_w[T, E, W](interps: Sequence[LazyCoroResultWriter[T, E, W]]) -> LazyCoroResultWriter[list[T], E, W]
```

#### Fold

```python
fold[A, T, E](items: Sequence[A], *, initial: T, reducer: Callable[[T, A], Interp[T, E]]) -> Interp[T, E]
fold_w[A, T, E, W](items: Sequence[A], *, initial: T, reducer: Callable[[T, A], LazyCoroResultWriter[T, E, W]]) -> LazyCoroResultWriter[T, E, W]
foldM[M, A, T, E, Raw](items: Sequence[A], *, initial: T, reducer: Callable[[T, A], Callable[[], Coro[Raw]], extract: Callable[[Raw], Result[T, E]], wrap: Callable[[Callable[[], Coro[Raw]]], M]) -> M
```

#### Validate

```python
validate[T, E](interps: Sequence[Interp[T, E]]) -> Interp[list[T], list[E]]  # Collects ALL errors
validate_w[T, E, W](interps: Sequence[LazyCoroResultWriter[T, E, W]]) -> LazyCoroResultWriter[list[T], list[E], W]
validateM[M, T, E, Raw](interps: Sequence[Callable[[], Coro[Raw]]], *, extract: Callable[[Raw], Result[T, E]], wrap: Callable[[Callable[[], Coro[Raw]]], M]) -> M
```

#### Partition

```python
partition[T, E](interps: Sequence[Interp[T, E]]) -> Interp[tuple[list[T], list[E]], NoError]  # Never fails
partition_w[T, E, W](interps: Sequence[LazyCoroResultWriter[T, E, W]]) -> LazyCoroResultWriter[tuple[list[T], list[E]], NoError, W]
partitionM[M, T, E, Raw](interps: Sequence[Callable[[], Coro[Raw]]], *, extract: Callable[[Raw], Result[T, E]], wrap: Callable[[Callable[[], Coro[Raw]]], M]) -> M
```

#### Replicate

```python
replicate[T, E](interp: Interp[T, E], n: int) -> Interp[list[T], E]
replicate_w[T, E, W](interp: LazyCoroResultWriter[T, E, W], n: int) -> LazyCoroResultWriter[list[T], E, W]
```

### Time Combinators

```python
timeout(interp: Interp[T, E], *, seconds: float) -> Interp[T, E | TimeoutError]
delay(interp: Interp[T, E], *, seconds: float) -> Interp[T, E]
timeout_w(interp: LazyCoroResultWriter[T, E, W], *, seconds: float) -> LazyCoroResultWriter[T, E | TimeoutError, W]
delay_w(interp: LazyCoroResultWriter[T, E, W], *, seconds: float) -> LazyCoroResultWriter[T, E, W]
timeoutM[M, T, E, Raw](interp: Callable[[], Coro[Raw]], *, extract: Callable[[Raw], Result[T, E]], wrap: Callable[[Callable[[], Coro[Raw]]], M], seconds: float) -> M
delayM[M, T, E, Raw](interp: Callable[[], Coro[Raw]], *, extract: Callable[[Raw], Result[T, E]], wrap: Callable[[Callable[[], Coro[Raw]]], M], seconds: float) -> M
```

### Transform Combinators

```python
tap(interp: Interp[T, E], *, effect: Callable[[T], None]) -> Interp[T, E]
tap_async(interp: Interp[T, E], *, effect: Callable[[T], Awaitable[None]]) -> Interp[T, E]
tap_err(interp: Interp[T, E], *, effect: Callable[[E], None]) -> Interp[T, E]
tap_err_async(interp: Interp[T, E], *, effect: Callable[[E], Awaitable[None]]) -> Interp[T, E]
bimap_tap(interp: Interp[T, E], *, on_ok: Callable[[T], None], on_err: Callable[[E], None]) -> Interp[T, E]
filter_or(interp: Interp[T, E], *, predicate: Predicate[T], error: E) -> Interp[T, E]
tap_w(interp: LazyCoroResultWriter[T, E, W], *, effect: Callable[[T], None]) -> LazyCoroResultWriter[T, E, W]
tap_async_w(interp: LazyCoroResultWriter[T, E, W], *, effect: Callable[[T], Awaitable[None]]) -> LazyCoroResultWriter[T, E, W]
tap_err_w(interp: LazyCoroResultWriter[T, E, W], *, effect: Callable[[E], None]) -> LazyCoroResultWriter[T, E, W]
tap_err_async_w(interp: LazyCoroResultWriter[T, E, W], *, effect: Callable[[E], Awaitable[None]]) -> LazyCoroResultWriter[T, E, W]
bimap_tap_w(interp: LazyCoroResultWriter[T, E, W], *, on_ok: Callable[[T], None], on_err: Callable[[E], None]) -> LazyCoroResultWriter[T, E, W]
filter_or_w(interp: LazyCoroResultWriter[T, E, W], *, predicate: Predicate[T], error: E) -> LazyCoroResultWriter[T, E, W]
tapM[M, T, E, Raw](interp: Callable[[], Coro[Raw]], *, extract: Callable[[Raw], Result[T, E]], wrap: Callable[[Callable[[], Coro[Raw]]], M], effect: Callable[[T], None]) -> M
tap_asyncM[M, T, E, Raw](interp: Callable[[], Coro[Raw]], *, extract: Callable[[Raw], Result[T, E]], wrap: Callable[[Callable[[], Coro[Raw]]], M], effect: Callable[[T], Awaitable[None]]) -> M
tap_errM[M, T, E, Raw](interp: Callable[[], Coro[Raw]], *, extract: Callable[[Raw], Result[T, E]], wrap: Callable[[Callable[[], Coro[Raw]]], M], effect: Callable[[E], None]) -> M
tap_err_asyncM[M, T, E, Raw](interp: Callable[[], Coro[Raw]], *, extract: Callable[[Raw], Result[T, E]], wrap: Callable[[Callable[[], Coro[Raw]]], M], effect: Callable[[E], Awaitable[None]]) -> M
```

### Selection Combinators

```python
best_of[T, E](interp: Interp[T, E], *, n: int, key: Selector[T, float]) -> Interp[T, E]  # Run N times, pick best
best_of_many[T, E](candidates: Sequence[Interp[T, E]], *, key: Selector[T, float]) -> Interp[T, E]  # Run all, pick best
vote[T, E](candidates: Sequence[Interp[T, E]], *, judge: Callable[[Sequence[T]], Awaitable[T]]) -> Interp[T, E]  # Judge picks winner
best_of_w[T, E, W](interp: LazyCoroResultWriter[T, E, W], *, n: int, key: Selector[T, float]) -> LazyCoroResultWriter[T, E, W]
best_of_many_w[T, E, W](candidates: Sequence[LazyCoroResultWriter[T, E, W]], *, key: Selector[T, float]) -> LazyCoroResultWriter[T, E, W]
vote_w[T, E, W](candidates: Sequence[LazyCoroResultWriter[T, E, W]], *, judge: Callable[[Sequence[T]], Awaitable[T]]) -> LazyCoroResultWriter[T, E, W]
```

### AST / Flow API

```python
from combinators.ast import Flow, FlowW, ast, ast_w, ast_bracket, ast_many

# Create Flow from LazyCoroResult
flow = ast(interp: Interp[T, E]) -> Flow[T, E]

# Flow methods (all return Flow with updated expr)
flow.retry(*, policy: RetryPolicy[E] | None = None, times: int | None = None, delay_seconds: float = 0.0, retry_on: Predicate[E] | None = None) -> Flow[T, E]
flow.timeout(*, seconds: float) -> Flow[T, E | TimeoutError]
flow.tap(effect: Callable[[T], None]) -> Flow[T, E]
flow.tap_async(effect: Callable[[T], Awaitable[None]]) -> Flow[T, E]
flow.tap_err(effect: Callable[[E], None]) -> Flow[T, E]
flow.tap_err_async(effect: Callable[[E], Awaitable[None]]) -> Flow[T, E]
flow.ensure(predicate: Predicate[T], error: Callable[[T], E]) -> Flow[T, E]
flow.reject(predicate: Predicate[T], error: Callable[[T], E]) -> Flow[T, E]
flow.race_ok(*others: Interp[T, E], policy: RaceOkPolicy | None = None, cancel_pending: bool = True, error_strategy: Literal["first", "last"] = "last") -> Flow[T, E]
flow.best_of(*, n: int, key: Selector[T, float]) -> Flow[T, E]
flow.delay(*, seconds: float) -> Flow[T, E]
flow.recover(*, default: T) -> Flow[T, NoError]
flow.recover_with(*, handler: Callable[[E], T]) -> Flow[T, NoError]
flow.repeat_until(*, condition: Predicate[T], policy: RepeatPolicy | None = None, max_rounds: int | None = None, delay_seconds: float = 0.0) -> Flow[T, E | ConditionNotMetError]
flow.rate_limit(*, policy: RateLimitPolicy | None = None, max_per_second: float | None = None, burst: int | None = None) -> Flow[T, E]
flow.lower() -> Interp[T, E]  # Finalize AST to executable Interp

# Create FlowW from LazyCoroResultWriter
flow_w = ast_w(interp: LazyCoroResultWriter[T, E, W]) -> FlowW[T, E, W]

# FlowW methods (same as Flow, but return FlowW)
flow_w.lower() -> LazyCoroResultWriter[T, E, W]

# Bracket pattern
ast_bracket[T, R, E](acquire: Interp[T, E], *, release: Callable[[T], Awaitable[None]], use: Callable[[T], Interp[R, E]]) -> Flow[R, E]
ast_bracket_w[T, R, E, W](acquire: LazyCoroResultWriter[T, E, W], *, release: Callable[[T], Awaitable[None]], use: Callable[[T], LazyCoroResultWriter[R, E, W]]) -> FlowW[R, E, W]

# Best of many
ast_many[T, E](candidates: Sequence[Interp[T, E]], *, key: Selector[T, float]) -> Flow[T, E]
ast_many_w[T, E, W](candidates: Sequence[LazyCoroResultWriter[T, E, W]], *, key: Selector[T, float]) -> FlowW[T, E, W]
```

### Writer Monad

```python
from combinators.writer import LazyCoroResultWriter, WriterResult, Log, writer_ok, writer_error

# Constructors
LazyCoroResultWriter.pure(value: T, log_type: type[W]) -> LazyCoroResultWriter[T, Never, W]
LazyCoroResultWriter.from_result(result: Result[T, E], log_type: type[W]) -> LazyCoroResultWriter[T, E, W]
LazyCoroResultWriter.tell(*entries: W) -> LazyCoroResultWriter[None, Never, W]
LazyCoroResultWriter.from_lazy_coro_result(lazy: Interp[T, E], log_type: type[W]) -> LazyCoroResultWriter[T, E, W]
writer_ok(value: T, *log_entries: W) -> LazyCoroResultWriter[T, Never, W]
writer_error(error: E, *log_entries: W) -> LazyCoroResultWriter[Never, E, W]

# Operations
writer.map(f: Callable[[T], U]) -> LazyCoroResultWriter[U, E, W]
writer.map_err(f: Callable[[E], F]) -> LazyCoroResultWriter[T, F, W]
writer.map_log(f: Callable[[Log[W]], Log[V]]) -> LazyCoroResultWriter[T, E, V]
writer.then(f: Callable[[T], Awaitable[WriterResult[U, E, Log[W]]]]) -> LazyCoroResultWriter[U, E, W]
writer.then_result(f: Callable[[T], Awaitable[Result[U, E]]]) -> LazyCoroResultWriter[U, E, W]
writer.with_log(*entries: W) -> LazyCoroResultWriter[T, E, W]
writer.listen() -> LazyCoroResultWriter[tuple[T, Log[W]], E, W]
writer.censor(f: Callable[[Log[W]], Log[W]]) -> LazyCoroResultWriter[T, E, W]
writer.cache() -> LazyCoroResultWriter[T, E, W]
writer.unwrap() -> Coroutine[Any, Any, T]  # Raises on error, loses log
writer.to_lazy_coro_result() -> Interp[tuple[T, Log[W]], E]

# Log operations
Log.of(*entries: W) -> Log[W]
log.combine(other: Log[W]) -> Log[W]
log.entries: list[W]
```

---

## Common Patterns

### Pattern: Resilient Fetching

```python
from combinators import ast, call, fallback_chain, race_ok
from combinators.concurrency import RaceOkPolicy

def fetch_resilient(key: str) -> Interp[Data, Error]:
    raced = (
        ast(race_ok(
            call(primary.get, key),
            call(replica.get, key),
            policy=RaceOkPolicy(cancel_pending=True, error_strategy="last")
        ))
        .retry(times=3, delay_seconds=0.2, retry_on=lambda e: e.is_transient)
        .timeout(seconds=2.0)
        .lower()
    )
    return fallback_chain(raced, ast(call(cache.get, key)).timeout(seconds=0.5).lower())
```

### Pattern: Conditional Retry

```python
from combinators import ast, call
from combinators.control import RetryPolicy

# Only retry on specific errors
def fetch_with_smart_retry(key: str) -> Interp[Data, Error]:
    return (
        ast(call(api.get, key))
        .retry(
            policy=RetryPolicy.exponential_jitter(
                times=5,
                initial=0.1,
                retry_on=lambda e: isinstance(e, (TimeoutError, RateLimitError))
            )
        )
        .lower()
    )
```

### Pattern: Parallel with Partial Failure

```python
from combinators import batch_all

# Process all items, collect both successes and failures
results = await batch_all(
    items,
    handler=lambda item: call(process_item, item),
    concurrency=10
)
# results: list[Result[T, E]] - never fails, returns all results
```

### Pattern: Cascading Timeouts

```python
from combinators import ast, call, fallback_chain

# Fast path with short timeout, slow path with longer timeout
def fetch_with_cascading_timeouts(key: str) -> Interp[Data, Error]:
    fast = ast(call(cache.get, key)).timeout(seconds=0.1).lower()
    medium = ast(call(cdn.get, key)).timeout(seconds=1.0).lower()
    slow = ast(call(db.get, key)).timeout(seconds=5.0).lower()
    
    return fallback_chain(fast, medium, slow)
```

### Pattern: Batch Processing

```python
from combinators import batch

def process_batch(items: list[Item]) -> Interp[list[Processed], Error]:
    return batch(
        items,
        handler=lambda item: ast(call(process_item, item)).retry(times=2).lower(),
        concurrency=10
    )
```

### Pattern: Validation

```python
from combinators import validate

def validate_form(form: Form) -> Interp[Form, list[str]]:
    return validate([
        call(check_email, form.email),
        call(check_password, form.password),
        call(check_age, form.age)
    ]).map(lambda _: form)
```

### Pattern: Resource Management

```python
from combinators import ast_bracket

def with_db[T, E](use: Callable[[DB], Interp[T, E]]) -> Interp[T, E]:
    return ast_bracket(
        acquire=call(db.connect),
        release=lambda conn: call(conn.close),
        use=use
    )
```

### Pattern: Writer for Logging

```python
from combinators.writer import writer_ok
from combinators import ast_w

def fetch_with_logs(key: str) -> LazyCoroResultWriter[Data, Error, str]:
    return (
        ast_w(writer_ok(None, f"fetching_{key}"))
        .then_result(lambda _: call(api.get, key))
        .with_log("completed")
    )
```

---

## Type Transformations

### Error Type Changes

- `timeout`: `E -> E | TimeoutError`
- `recover`: `E -> NoError`
- `recover_with`: `E -> NoError`
- `repeat_until`: `E -> E | ConditionNotMetError`
- `validate`: `E -> list[E]` (collects all errors)

### Success Type Changes

- `traverse`: `Interp[T, E] -> Interp[list[T], E]`
- `sequence`: `Sequence[Interp[T, E]] -> Interp[list[T], E]`
- `fold`: `Sequence[A] -> Interp[T, E]` (via reducer)
- `gather2`: `(Interp[T1, E], Interp[T2, E]) -> Interp[tuple[T1, T2], E]`
- `best_of`: `Interp[T, E] -> Interp[T, E]` (same type, but runs N times)
- `vote`: `*Interp[T, E] -> Interp[T, E]`

---

## Implementation Notes

### Extract Functions

- `identity`: For LazyCoroResult (Raw = Result[T, E])
  ```python
  def identity[T](x: T) -> T:
      return x
  ```
- `extract_writer_result`: For LazyCoroResultWriter (Raw = WriterResult[T, E, Log[W]])
  ```python
  def extract_writer_result[T, E, W](wr: WriterResult[T, E, Log[W]]) -> Result[T, E]:
      return wr.result
  ```

### Wrap Functions

- `LazyCoroResult`: Constructor for LazyCoroResult
  ```python
  LazyCoroResult(thunk: Callable[[], Coroutine[Any, Any, Result[T, E]]])
  ```
- `wrap_lazy_coro_result_writer`: Constructor for LazyCoroResultWriter
  ```python
  def wrap_lazy_coro_result_writer[T, E, W](
      thunk: Callable[[], Coroutine[Any, Any, WriterResult[T, E, Log[W]]]]
  ) -> LazyCoroResultWriter[T, E, W]:
      return LazyCoroResultWriter(thunk)
  ```

### Generic Combinators

All generic combinators (`*M` functions) follow this pattern:

1. Take `Callable[[], Coroutine[Any, Any, Raw]]` (thunk)
2. Take `extract: Callable[[Raw], Result[T, E]]`
3. Take `wrap: Callable[[Callable[[], Coroutine[Any, Any, Raw]]], M]`
4. Return `M`

Sugar functions (`*` and `*_w`) call generic with concrete extract/wrap.

**Example implementation pattern:**
```python
def retryM[M, T, E, Raw](
    interp: Callable[[], Coroutine[Any, Any, Raw]],
    *,
    extract: Callable[[Raw], Result[T, E]],
    wrap: Callable[[Callable[[], Coroutine[Any, Any, Raw]]], M],
    policy: RetryPolicy[E],
) -> M:
    async def run() -> Raw:
        for attempt in range(policy.times):
            raw = await interp()
            result = extract(raw)
            if result.is_ok():
                return raw
            # ... retry logic
        return raw
    
    return wrap(run)

# Sugar for LazyCoroResult
def retry[T, E](interp: LazyCoroResult[T, E], *, policy: RetryPolicy[E]) -> LazyCoroResult[T, E]:
    return retryM(interp, extract=identity, wrap=LazyCoroResult, policy=policy)
```

### Log Merging

Writer monad automatically merges logs when chaining:

```python
writer1.then(lambda v: writer2)  # Logs merge: writer1.log.combine(writer2.log)
```

**Log combining rules:**
- Sequential operations (`.then()`): logs concatenate
- Parallel operations (`parallel_w`): logs merge in completion order
- Race operations (`race_ok_w`): only winner's log is kept
- Retry operations (`retry_w`): only final attempt's log is kept

### Error Handling

- Short-circuit: `Error` propagates through `.then()`, `.map()` passes it unchanged
- Type narrowing: Error types change based on combinators (see Type Transformations)
- No exceptions: All errors are values in the `Result[T, E]` type

### Performance Characteristics

| Combinator | Time Complexity | Space Complexity | Notes |
|------------|----------------|------------------|-------|
| `retry` | O(n * T) | O(1) | n = attempts, T = operation time |
| `parallel` | O(T) | O(n) | T = slowest operation, n = items |
| `race_ok` | O(T) | O(n) | T = fastest success, n = candidates |
| `traverse` | O(n * T) | O(n) | Sequential, n = items |
| `traverse_par` | O(T) | O(c) | c = concurrency limit |
| `batch` | O(n * T / c) | O(c) | c = concurrency limit |
| `validate` | O(n * T) | O(n) | Collects all errors |
| `fallback_chain` | O(n * T) | O(1) | n = alternatives, short-circuits |

### Cancellation Behavior

- `race_ok(cancel_pending=True)`: Cancels pending tasks on first success
- `race_ok(cancel_pending=False)`: Lets all tasks complete
- `timeout`: Cancels wrapped task on timeout
- `batch`: Does not cancel on individual failures
- `parallel`: Does not cancel on individual failures

---

## Code Generation Guidelines

### When to Use Which Variant

1. **LazyCoroResult** (`Interp`): Default choice, no logging needed
2. **LazyCoroResultWriter**: Need structured logging without side effects
3. **Generic (`*M`)**: Creating custom monads or reusable combinator logic

### Import Patterns

```python
# Recommended: namespace import for lift
from combinators import lift as L

# Direct imports for combinators
from combinators import retry, fallback, timeout, ast, call

# Policy imports
from combinators.control import RetryPolicy, RepeatPolicy
from combinators.concurrency import RaceOkPolicy, RateLimitPolicy
```

### Function Naming

- `*`: LazyCoroResult sugar
- `*_w`: LazyCoroResultWriter sugar
- `*M`: Generic combinator (extract + wrap)

### AST vs Direct

- **AST (`ast()`)**: Fluent chaining, readable pipelines
- **Direct**: Function composition, programmatic construction

```python
# AST (fluent)
pipeline = (
    ast(call(fetch, key))
    .retry(times=3)
    .timeout(seconds=5.0)
    .lower()
)

# Direct (composition)
pipeline = timeout(retry(call(fetch, key), times=3), seconds=5.0)
```

---

## Testing Patterns

### Test Policies

```python
def test_retry_policy():
    policy = RetryPolicy.fixed(times=3, delay_seconds=0.1)
    assert policy.times == 3
    assert policy.backoff(0, Error("test")) == 0.1
```

### Test Combinators

```python
async def test_fallback():
    primary = L.fail(Error("primary failed"))
    secondary = L.pure(42)
    result = await fallback(primary, secondary)
    assert result == Ok(42)
```

### Test Writer

```python
async def test_writer_logs():
    writer = writer_ok(42, "log1", "log2")
    wr = await writer
    assert wr.result == Ok(42)
    assert len(wr.log.entries) == 2
```

---

## Common Mistakes

1. **Forgetting `.lower()`**: AST must be finalized before execution
2. **Wrong extract function**: Use `identity` for LazyCoroResult, `extract_writer_result` for Writer
3. **Type mismatches**: Error types change with combinators (timeout adds `TimeoutError`)
4. **Log loss**: Failed branches in fallback/race discard logs (only winner's log kept)
5. **Not awaiting**: Interp is lazy, must await to execute

---

## Performance Considerations

- **Lazy evaluation**: Nothing executes until `await`
- **Early cancellation**: `race_ok` with `cancel_pending=True` cancels pending tasks
- **Bounded concurrency**: Use `batch`/`traverse_par` with `concurrency` limit
- **Rate limiting**: Use `rate_limit` to avoid overwhelming services
- **Caching**: Writer monad has `.cache()` for expensive computations

