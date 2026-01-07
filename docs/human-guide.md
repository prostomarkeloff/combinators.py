# Combinators.py: A Guide to Functional Programming with Effects

## Table of Contents

1. [Introduction](#introduction)
2. [Core Concepts](#core-concepts)
3. [The Monadic Foundation](#the-monadic-foundation)
4. [Combinators Explained](#combinators-explained)
5. [Patterns and Practices](#patterns-and-practices)
6. [Real-World Examples](#real-world-examples)
7. [Advanced Topics](#advanced-topics)

---

## Introduction

### What Are Combinators?

Combinators are **functions that take functions and return functions**. They transform computations, enabling you to compose effects like building blocks rather than nesting try/except blocks or decorating functions.

In `combinators.py`, combinators work with **lazy, async computations** that produce `Result[T, E]` values. This gives you:

- **Type safety**: Errors are part of the type signature, not hidden exceptions
- **Composability**: Stack effects like LEGO blocks
- **Testability**: Test policies and effects in isolation
- **Visibility**: See all effects at the call site, not hidden in decorators

### The Philosophy

**Effects are composition, not decoration.**

Traditional Python code hides effects in decorators or middleware:

```python
@retry(times=3)
@timeout(5.0)
async def fetch_user(user_id: int) -> User:
    ...
```

**Problems:**
- Effects are invisible at call sites
- Order of execution is implicit
- Policies are scattered in decorator parameters
- Testing requires mocking decorators

Combinators make effects **explicit and composable**:

```python
from combinators import ast, call

def fetch_user(user_id: int) -> Interp[User, APIError]:
    return (
        ast(call(api.get, f"/users/{user_id}"))
        .retry(times=3, delay_seconds=0.2)
        .timeout(seconds=5.0)
        .lower()
    )
```

**Benefits:**
- Read the code, see the effects
- Order is explicit: retry THEN timeout
- Policies are data, not magic
- Test by creating policies and asserting behavior

---

## Core Concepts

### The Primitive: `Interp[T, E]`

```python
type Interp[T, E] = LazyCoroResult[T, E]
```

An `Interp[T, E]` is a **lazy, async computation** that produces `Result[T, E]` when executed.

- **Lazy**: Nothing executes until you `await`. Compose first, run later.
- **Async**: Built on `async`/`await`, no thread pools or executors.
- **Typed**: `T` is the success type, `E` is the error type. No hidden exceptions.

Think of `Interp` as `Result` made lazy:

```python
from kungfu import Result, Ok, Error

# Result[T, E] is eager
def divide(a: int, b: int) -> Result[float, str]:
    if b == 0:
        return Error("division by zero")
    return Ok(a / b)

# Interp[T, E] is lazy
from combinators import call

def divide_interp(a: int, b: int) -> Interp[float, str]:
    return call(divide, a, b)

# Execute
result = await divide_interp(10, 2)  # Result[float, str] = Ok(5.0)
```

### Composition: `.map()` and `.then()`

Combinators compose through `.map()` (transform success) and `.then()` (chain computations):

```python
from combinators import pure

# Start with a value
interp = pure(42)

# Transform success values
doubled = interp.map(lambda x: x * 2)  # Interp[int, Never]

# Chain another computation
chained = doubled.then(lambda x: pure(x + 10))  # Interp[int, Never]

# Execute
value = await chained  # Result[int, Never] = Ok(94)
```

**Semantics:**

- `.map(f)` — apply `f: T -> R` to `Ok(T)`, pass `Error(E)` unchanged
- `.then(f)` — if `Ok(T)`, call `f(T) -> Interp[R, E]`; if `Error(E)`, short-circuit

This is the Kleisli category for `Result`. If you know monads, you already know combinators.

### Lifting: From Values to Interp

The `lift` module provides helpers to construct `Interp` values:

```python
from combinators import lift as L

# Pure value -> always-succeeding Interp
x = L.pure(42)  # Interp[int, Never]

# Error value -> always-failing Interp
e = L.fail(NotFoundError())  # Interp[Never, NotFoundError]

# Call a function (most common pattern)
result = L.call(fetch_user, user_id)  # Interp[User, APIError]

# Wrap async function
result = L.wrap_async(lambda: api.get("/data"))  # Interp[Data, APIError]

# From Result
from kungfu import Ok
result = L.from_result(Ok(42))  # Interp[int, NoError]
```

**Locality principle:** Write pure functions, lift at call site:

```python
# Pure function (no Interp dependency)
async def fetch_user_impl(user_id: int) -> Result[User, APIError]:
    return await api.get(f"/users/{user_id}")

# Lift at call site (locality!)
pipeline = (
    ast(L.call(fetch_user_impl, 42))
    .retry(times=3, delay_seconds=0.2)
    .timeout(seconds=5.0)
    .lower()
)
```

This means **no refactoring required**. Old code stays pure, compose effects where needed.

### The AST Builder: `ast()`

The `ast()` function creates a fluent builder for composing effects:

```python
from combinators import ast, call

pipeline = (
    ast(call(fetch_user, 42))
    .retry(times=3, delay_seconds=0.2)
    .timeout(seconds=5.0)
    .tap(effect=lambda u: print(u.name))
    .ensure(predicate=lambda u: u.is_active, error=lambda u: InactiveUserError())
    .lower()  # Finalize: Interp[User, APIError | TimeoutError]
)

result = await pipeline
```

**Note:** `.lower()` is required to finalize the AST into an executable `Interp`. Think of it as "compile the pipeline".

---

## The Monadic Foundation

### Understanding Monads

A monad is a way to structure computations. In `combinators.py`, we work with two monads:

1. **LazyCoroResult** (`Interp`) - lazy async Result
2. **LazyCoroResultWriter** - lazy async Result with logging

Both follow the same pattern:

- **Pure**: Lift a value into the monad
- **Map**: Transform success values (functor)
- **Then**: Chain computations (monadic bind)

### The Extract + Wrap Pattern

For generic combinators that work with any monad, we use the **extract + wrap pattern**:

```python
def retryM[M, T, E, Raw](
    interp: Callable[[], Coroutine[Any, Any, Raw]],
    *,
    extract: Callable[[Raw], Result[T, E]],
    wrap: Callable[[Callable[[], Coroutine[Any, Any, Raw]]], M],
    policy: RetryPolicy[E],
) -> M:
    # Generic retry logic using extract to check Result
    # and wrap to construct new monad
```

**How it works:**

1. **Extract**: Get `Result[T, E]` from the monad's raw type
2. **Logic**: Implement combinator logic using `Result`
3. **Wrap**: Construct new monad from thunk

**Example for LazyCoroResult:**

```python
def retry[T, E](
    interp: LazyCoroResult[T, E],
    *,
    policy: RetryPolicy[E],
) -> LazyCoroResult[T, E]:
    return retryM(
        interp,
        extract=identity,  # LazyCoroResult's Raw IS Result[T, E]
        wrap=LazyCoroResult,
        policy=policy,
    )
```

**Example for LazyCoroResultWriter:**

```python
def retry_w[T, E, W](
    interp: LazyCoroResultWriter[T, E, W],
    *,
    policy: RetryPolicy[E],
) -> LazyCoroResultWriter[T, E, W]:
    return retryM(
        interp,
        extract=extract_writer_result,  # Extract Result from WriterResult
        wrap=wrap_lazy_coro_result_writer,
        policy=policy,
    )
```

This pattern enables **code reuse**: write combinator logic once, use it for multiple monads.

### Writer Monad: Logging Without Side Effects

The Writer monad accumulates logs without side effects:

```python
from combinators.writer import LazyCoroResultWriter, writer_ok

# Create writer with value and log
writer = writer_ok(User(id=42), "user_fetched", "cache_hit")

# Add more log entries
writer = writer.with_log("validated", "processed")

# Execute and get both value and log
wr = await writer
match wr.result:
    case Ok(user):
        print(f"User: {user.id}")
        print(f"Log: {wr.log.entries}")  # ["user_fetched", "cache_hit", "validated", "processed"]
```

**Why Writer?**

- **No side effects**: Logs are part of the computation, not global state
- **Composable**: Logs merge automatically when chaining computations
- **Testable**: Assert on logs just like you assert on values

---

## Combinators Explained

### Control Flow Combinators

#### Retry

Retry a computation multiple times with configurable backoff:

```python
from combinators import ast, call
from combinators.control import RetryPolicy

# Simple retry
pipeline = (
    ast(call(fetch_user, 42))
    .retry(times=3, delay_seconds=0.2)
    .lower()
)

# Advanced retry with policy
policy = RetryPolicy.exponential_jitter(
    times=5,
    initial=0.1,
    multiplier=2.0,
    max_delay=10.0,
    retry_on=lambda e: e.is_transient
)

pipeline = (
    ast(call(fetch_user, 42))
    .retry(policy=policy)
    .lower()
)
```

**Backoff strategies:**

- `fixed`: Same delay every retry
- `exponential`: Delay grows exponentially
- `jitter`: Random delays to avoid thundering herd
- `exponential_jitter`: Best of both worlds

#### Fallback

Try alternative computation if primary fails:

```python
from combinators import fallback, fallback_chain

# Simple fallback
result = await fallback(
    call(api.get, "/users/42"),
    call(cache.get, "user:42")
)

# Chain multiple fallbacks
result = await fallback_chain(
    call(primary_api.get, "/users/42"),
    call(replica_api.get, "/users/42"),
    call(cache.get, "user:42")
)
```

#### Recover

Handle errors by providing default values:

```python
from combinators import recover, recover_with

# Recover with default value
result = await recover(
    call(fetch_user, 42),
    default=User(id=0, name="Guest")
)

# Recover with handler function
result = await recover_with(
    call(fetch_user, 42),
    handler=lambda e: User(id=0, name=f"Error: {e}")
)
```

#### Ensure / Reject

Validate results with predicates:

```python
from combinators import ast, call

# Ensure condition is met (fail if not)
pipeline = (
    ast(call(fetch_user, 42))
    .ensure(
        predicate=lambda u: u.is_active,
        error=lambda u: InactiveUserError(user_id=u.id)
    )
    .lower()
)

# Reject if condition is met (fail if condition is true)
pipeline = (
    ast(call(fetch_user, 42))
    .reject(
        predicate=lambda u: u.is_banned,
        error=lambda u: BannedUserError(user_id=u.id)
    )
    .lower()
)
```

#### Bracket (Resource Management)

Acquire resource, use it, release it (even on error):

```python
from combinators import ast_bracket

pipeline = ast_bracket(
    acquire=call(db.connect),
    release=lambda conn: call(conn.close),
    use=lambda conn: call(conn.query, "SELECT * FROM users")
)

result = await pipeline
```

**Real-world example: File handling**

```python
from combinators import bracket, call

async def read_file_safe(path: str) -> Interp[str, IOError]:
    async def acquire() -> Result[File, IOError]:
        return await open_file(path)
    
    async def release(file: File) -> None:
        await file.close()
    
    def use(file: File) -> Interp[str, IOError]:
        return call(file.read)
    
    return bracket(
        acquire=call(acquire),
        release=release,
        use=use
    )
```

**Key insight:** `release` is **always** called, even if `use` fails. This prevents resource leaks.

### Concurrency Combinators

#### Race

Run multiple computations, return first to complete:

```python
from combinators import race, race_ok

# Race: first to finish (Ok or Error)
result = await race(
    call(api.get, "/users/42"),
    call(cache.get, "user:42")
)

# Race OK: first success wins, ignore failures
from combinators.concurrency import RaceOkPolicy

result = await race_ok(
    call(replica1.get, "/users/42"),
    call(replica2.get, "/users/42"),
    call(replica3.get, "/users/42"),
    policy=RaceOkPolicy(cancel_pending=True, error_strategy="last")
)
```

#### Parallel

Run multiple computations in parallel, collect all results:

```python
from combinators import parallel

results = await parallel([
    call(fetch_user, 1),
    call(fetch_user, 2),
    call(fetch_user, 3)
])
# Result[list[User], APIError]
```

#### Batch

Process items in parallel with bounded concurrency:

```python
from combinators import batch

user_ids = [1, 2, 3, 4, 5]

results = await batch(
    user_ids,
    handler=lambda uid: call(fetch_user, uid),
    concurrency=3  # Max 3 concurrent requests
)
```

#### Gather

Zip multiple computations:

```python
from combinators import gather2, gather3

# Gather 2
user, posts = await gather2(
    call(fetch_user, 42),
    call(fetch_posts, 42)
)

# Gather 3
user, posts, comments = await gather3(
    call(fetch_user, 42),
    call(fetch_posts, 42),
    call(fetch_comments, 42)
)
```

### Collection Combinators

#### Traverse

Apply handler to each item, collect results:

```python
from combinators import traverse, traverse_par

user_ids = [1, 2, 3]

# Sequential traverse
users = await traverse(user_ids, handler=lambda uid: call(fetch_user, uid))

# Parallel traverse
users = await traverse_par(
    user_ids,
    handler=lambda uid: call(fetch_user, uid),
    concurrency=10
)
```

#### Sequence

Sequence a list of Interps:

```python
from combinators import sequence

interps = [
    call(fetch_user, 1),
    call(fetch_user, 2),
    call(fetch_user, 3)
]

users = await sequence(interps)
```

#### Fold

Reduce a list with a reducer function:

```python
from combinators import fold

numbers = [1, 2, 3, 4, 5]

sum_result = await fold(
    numbers,
    initial=0,
    reducer=lambda acc, x: acc + x
)
```

#### Validate

Run multiple validations, collect ALL errors:

```python
from combinators import validate

errors = await validate([
    call(check_email, email),
    call(check_password, password),
    call(check_age, age)
])

match errors:
    case Ok(_):
        # All validations passed
        pass
    case Error(err_list):
        # err_list contains ALL validation errors
        print(f"Found {len(err_list)} errors")
```

### Time Combinators

#### Timeout

Add timeout to computation:

```python
from combinators import ast, call

pipeline = (
    ast(call(fetch_user, 42))
    .timeout(seconds=5.0)
    .lower()
)

# Error type changes: APIError -> APIError | TimeoutError
result: Result[User, APIError | TimeoutError] = await pipeline
```

#### Delay

Delay before executing:

```python
from combinators import ast, call

pipeline = (
    ast(call(fetch_user, 42))
    .delay(seconds=1.0)
    .lower()
)
```

### Transform Combinators

#### Tap

Side effect on success (doesn't change value):

```python
from combinators import ast, call

pipeline = (
    ast(call(fetch_user, 42))
    .tap(effect=lambda u: logger.info(f"Fetched user {u.id}"))
    .lower()
)
```

#### Tap Error

Side effect on error:

```python
from combinators import ast, call

pipeline = (
    ast(call(fetch_user, 42))
    .tap_err(effect=lambda e: logger.error(f"Failed: {e}"))
    .lower()
)
```

### Selection Combinators

#### Best Of

Run computation N times, pick best result:

```python
from combinators import ast, call

pipeline = (
    ast(call(generate_text, prompt))
    .best_of(n=3, key=lambda text: text.quality_score)
    .lower()
)
```

#### Vote

Run multiple computations, pick most common result:

```python
from combinators import vote

# Simple majority vote
async def majority_judge(results: Sequence[str]) -> str:
    from collections import Counter
    counts = Counter(results)
    return counts.most_common(1)[0][0]

result = await vote(
    [
        call(model1.predict, input),
        call(model2.predict, input),
        call(model3.predict, input),
    ],
    judge=majority_judge
)
```

**Advanced example: Weighted voting**

```python
async def weighted_judge(results: Sequence[tuple[str, float]]) -> str:
    """Judge picks result with highest total weight."""
    from collections import defaultdict
    weights = defaultdict(float)
    
    for result, weight in results:
        weights[result] += weight
    
    return max(weights.items(), key=lambda x: x[1])[0]

# Each model returns (prediction, confidence)
result = await vote(
    [
        call(model1.predict_with_confidence, input),
        call(model2.predict_with_confidence, input),
        call(model3.predict_with_confidence, input),
    ],
    judge=weighted_judge
)
```

---

## Patterns and Practices

### The Locality Principle

**Locality** means: everything you need to understand a piece of code is **right there**, not scattered across files or hidden in global state.

**Effects at the call site:**

```python
# ✅ Good: effects visible
result = await (
    ast(call(fetch_user, 42))
    .retry(times=3, delay_seconds=0.2)
    .timeout(seconds=5.0)
    .lower()
)

# ❌ Bad: effects hidden in decorators
@retry(times=3)
@timeout(5.0)
async def fetch_user(user_id: int) -> User:
    ...
```

### Policies as Data

Policies are **data structures**, not magic:

```python
from combinators.control import RetryPolicy

# Policy is a dataclass - inspectable, serializable, testable
policy = RetryPolicy.exponential_jitter(
    times=5,
    initial=0.1,
    multiplier=2.0,
    max_delay=10.0,
    retry_on=lambda e: e.is_transient
)

# Can be built from config
import os

if os.getenv("ENV") == "production":
    policy = RetryPolicy.exponential_jitter(times=5, initial=0.1)
else:
    policy = RetryPolicy.fixed(times=1, delay_seconds=0.1)

result = await retry(call(fetch_user, 42), policy=policy)
```

### Incremental Adoption

You don't need to rewrite your codebase. Start small:

**Week 1: Add validation**

```python
from combinators import validate

def validate_form(form: Form) -> Interp[Form, list[str]]:
    return validate([
        call(check_email, form.email),
        call(check_password, form.password),
    ]).map(lambda _: form)
```

**Week 2: Add retry to API calls**

```python
from combinators import ast, call

def fetch_user(user_id: int) -> Interp[User, APIError]:
    return (
        ast(call(api.get, f"/users/{user_id}"))
        .retry(times=3, delay_seconds=0.2)
        .lower()
    )
```

**Week 3: Compose them**

```python
def process_form(form: Form) -> Interp[ProcessedForm, APIError]:
    validated = await validate_form(form)
    
    return (
        ast(call(api.submit, validated.unwrap()))
        .retry(times=3, delay_seconds=0.2)
        .lower()
    )
```

### Composition Over Configuration

**Avoid configuration blobs:**

```python
# ❌ Bad: opaque configuration
config = {
    "retry": {"times": 3, "delay": 0.2},
    "timeout": {"seconds": 5.0},
}

result = await fetch_with_config(user_id, config)
```

**Prefer explicit composition:**

```python
# ✅ Good: explicit composition
result = await (
    ast(call(fetch_user, user_id))
    .retry(times=3, delay_seconds=0.2)
    .timeout(seconds=5.0)
    .lower()
)
```

### Common Composition Patterns

#### Pattern: Retry + Timeout

```python
# Order matters: retry THEN timeout
# Each retry attempt has 2s timeout, total 3 attempts
result = await (
    ast(call(fetch_user, 42))
    .retry(times=3, delay_seconds=0.5)
    .timeout(seconds=2.0)  # Per-attempt timeout
    .lower()
)

# vs. timeout THEN retry
# Total operation has 2s timeout, retries within that window
result = await (
    ast(call(fetch_user, 42))
    .timeout(seconds=2.0)  # Total timeout
    .retry(times=3, delay_seconds=0.5)
    .lower()
)
```

#### Pattern: Race + Fallback

```python
# Try fast sources first, fallback to slow but reliable
from combinators import race_ok, fallback_chain

fast_sources = race_ok(
    call(cache.get, key),
    call(cdn.get, key),
    policy=RaceOkPolicy(cancel_pending=True)
)

slow_sources = race_ok(
    call(primary_db.get, key),
    call(replica_db.get, key),
)

result = await fallback_chain(
    ast(fast_sources).timeout(seconds=0.5).lower(),
    ast(slow_sources).timeout(seconds=5.0).lower(),
)
```

#### Pattern: Parallel + Validation

```python
# Fetch multiple items, validate each, collect errors
from combinators import traverse_par, validate

async def fetch_and_validate(user_id: int) -> Interp[User, ValidationError]:
    return (
        ast(call(fetch_user, user_id))
        .ensure(
            predicate=lambda u: u.is_active,
            error=lambda u: ValidationError(f"User {u.id} is inactive")
        )
        .lower()
    )

# Parallel fetch + validation
results = await traverse_par(
    user_ids,
    handler=fetch_and_validate,
    concurrency=10
)

# Or collect all errors instead of failing fast
validation_results = await validate([
    fetch_and_validate(uid) for uid in user_ids
])
```

#### Pattern: Best-of + Retry

```python
# Generate N samples, pick best, retry if quality too low
from combinators import best_of, repeat_until

def generate_high_quality(prompt: str) -> Interp[Sample, ModelError]:
    return (
        ast(call(llm.generate, prompt))
        .best_of(n=5, key=lambda s: s.quality_score)
        .repeat_until(
            condition=lambda s: s.quality_score >= 0.8,
            policy=RepeatPolicy(max_rounds=3, delay_seconds=1.0)
        )
        .lower()
    )
```

#### Pattern: Batch with Individual Retry

```python
# Process items in batches, retry each item individually
from combinators import batch

def process_with_retry(item: Item) -> Interp[Result, ProcessError]:
    return (
        ast(call(process_item, item))
        .retry(times=3, delay_seconds=0.2)
        .timeout(seconds=10.0)
        .lower()
    )

results = await batch(
    items,
    handler=process_with_retry,
    concurrency=20
)
```

---

## Real-World Examples

### Resilient Data Fetching

Fetch user data with retry, timeout, fallback, and race:

```python
from combinators import ast, call, fallback_chain, race_ok
from combinators.concurrency import RaceOkPolicy

def fetch_user_resilient(user_id: int) -> Interp[User, APIError]:
    # Race primary + replica, retry on failure, timeout
    raced = (
        ast(race_ok(
            call(api.get, f"/users/{user_id}"),
            call(replica.get, f"/users/{user_id}"),
            policy=RaceOkPolicy(cancel_pending=True, error_strategy="last")
        ))
        .retry(times=3, delay_seconds=0.2, retry_on=lambda e: e.is_transient)
        .timeout(seconds=2.0)
        .lower()
    )
    
    # Fallback to cache if race fails
    return fallback_chain(
        raced,
        ast(call(cache.get, f"user:{user_id}")).timeout(seconds=0.5).lower()
    )

result = await fetch_user_resilient(42)
```

### LLM Resilient Pipeline

Race fast vs smart models, retry on rate limits, pick best result:

```python
from combinators import ast, call, race_ok, fallback_chain
from combinators.concurrency import RaceOkPolicy

def generate_sample(prompt: str) -> Interp[Sample, ModelError]:
    # Race fast vs smart, retry on transients, pick best of 3, validate quality
    pipeline = (
        ast(race_ok(
            call(llm_fast, prompt),
            call(llm_smart, prompt),
            policy=RaceOkPolicy(cancel_pending=True, error_strategy="last")
        ))
        .retry(times=3, delay_seconds=0.05, retry_on=lambda e: e.transient)
        .best_of(n=3, key=lambda s: s.quality)
        .ensure(
            predicate=lambda s: s.quality >= 0.8,
            error=lambda s: ModelError(source="guard", message=f"quality={s.quality:.2f}")
        )
        .lower()
    )
    
    # Fallback to cached response
    return fallback_chain(
        pipeline,
        call(cache.get_sample, prompt)
    )

result = await generate_sample("Explain monads")
```

### Batch Processing with Rate Limiting

Process items in batches with rate limiting:

```python
from combinators import batch, ast, call
from combinators.concurrency import RateLimitPolicy

def process_items(items: list[Item]) -> Interp[list[ProcessedItem], ProcessingError]:
    return batch(
        items,
        handler=lambda item: (
            ast(call(process_item, item))
            .rate_limit(policy=RateLimitPolicy(max_per_second=10.0, burst=5))
            .lower()
        ),
        concurrency=10
    )

results = await process_items([item1, item2, item3, ...])
```

---

## Advanced Topics

### Custom Monads

You can create custom monads using the extract + wrap pattern:

```python
from combinators._helpers import extract_result, identity

class MyMonad[T, E]:
    def __init__(self, thunk: Callable[[], Coroutine[Any, Any, Result[T, E]]]):
        self._thunk = thunk
    
    async def __call__(self) -> Result[T, E]:
        return await self._thunk()

def my_retry[T, E](
    interp: MyMonad[T, E],
    *,
    policy: RetryPolicy[E],
) -> MyMonad[T, E]:
    from combinators.control.retry import retryM
    
    return retryM(
        interp,
        extract=identity,  # MyMonad's Raw IS Result[T, E]
        wrap=MyMonad,
        policy=policy,
    )
```

### Writer Monad for Logging

Use Writer monad for structured logging:

```python
from combinators.writer import LazyCoroResultWriter, writer_ok
from combinators import ast_w

def fetch_user_with_logs(user_id: int) -> LazyCoroResultWriter[User, APIError, str]:
    return (
        ast_w(writer_ok(User(id=user_id), f"fetching_user_{user_id}"))
        .with_log("started")
        .then_result(lambda u: call(api.get, f"/users/{u.id}"))
        .with_log("completed")
    )

wr = await fetch_user_with_logs(42)
match wr.result:
    case Ok(user):
        print(f"User: {user.id}")
        print(f"Log: {wr.log.entries}")  # ["fetching_user_42", "started", "completed"]
```

### Flow API for Fluent Composition

Use the Flow API for readable pipelines:

```python
from combinators import ast

pipeline = (
    ast(call(fetch_user, 42))
    .retry(times=3, delay_seconds=0.2)
    .timeout(seconds=5.0)
    .tap(effect=lambda u: logger.info(f"Fetched {u.name}"))
    .ensure(predicate=lambda u: u.is_active, error=lambda u: InactiveUserError())
    .lower()
)

result = await pipeline
```

### Type Safety

Types are documentation. The type checker ensures correctness:

```python
# fetch_user returns Result[User, APIError]
result: Result[User, APIError] = await fetch_user(42)

# Add timeout: now returns Result[User, APIError | TimeoutError]
result: Result[User, APIError | TimeoutError] = await (
    ast(fetch_user(42))
    .timeout(seconds=5.0)
    .lower()
)

# Add fallback: error type narrows back to APIError
result: Result[User, APIError] = await fallback(
    ast(fetch_user(42)).timeout(seconds=5.0).lower(),
    call(cache.get, "user:42")
)
```

---

## Troubleshooting

### Common Issues and Solutions

#### Issue: "Forgot to call `.lower()`"

**Symptom:**
```python
pipeline = ast(call(fetch_user, 42)).retry(times=3)
result = await pipeline  # TypeError: object Flow can't be used in 'await' expression
```

**Solution:** Always call `.lower()` to finalize the AST:
```python
pipeline = ast(call(fetch_user, 42)).retry(times=3).lower()
result = await pipeline  # ✅ Works
```

**Why:** `ast()` returns a `Flow` builder, not an executable `Interp`. `.lower()` compiles the AST into an executable computation.

---

#### Issue: "Type errors with error unions"

**Symptom:**
```python
# Type checker complains: Expected APIError, got APIError | TimeoutError
result: Result[User, APIError] = await (
    ast(call(fetch_user, 42))
    .timeout(seconds=5.0)
    .lower()
)
```

**Solution:** Update the type annotation to include all possible errors:
```python
result: Result[User, APIError | TimeoutError] = await (
    ast(call(fetch_user, 42))
    .timeout(seconds=5.0)
    .lower()
)
```

**Why:** Combinators like `timeout()` add new error types. The type system tracks this to prevent unhandled errors.

**Alternative:** Use `recover()` or `fallback()` to handle the timeout and narrow the error type back:
```python
result: Result[User, APIError] = await fallback(
    ast(call(fetch_user, 42)).timeout(seconds=5.0).lower(),
    call(cache.get, "user:42")  # Handles TimeoutError
)
```

---

#### Issue: "Logs disappear in race/fallback"

**Symptom:**
```python
result = await race_ok_w(
    writer_ok(1, "log1"),
    writer_ok(2, "log2"),
    writer_ok(3, "log3"),
)
# Only winner's log is preserved
```

**Solution:** This is expected behavior. Only the winning computation's log is kept. If you need all logs, use `parallel_w()` instead:
```python
results = await parallel_w([
    writer_ok(1, "log1"),
    writer_ok(2, "log2"),
    writer_ok(3, "log3"),
])
# All logs are merged
```

**Why:** `race_ok` cancels pending tasks on first success. Cancelled tasks lose their logs. This is a tradeoff for performance.

---

#### Issue: "Retry doesn't work as expected"

**Symptom:**
```python
# Retries even on permanent errors
result = await retry(
    call(fetch_user, 42),
    policy=RetryPolicy.fixed(times=3, delay_seconds=0.2)
)
```

**Solution:** Use `retry_on` predicate to only retry transient errors:
```python
result = await retry(
    call(fetch_user, 42),
    policy=RetryPolicy.fixed(
        times=3,
        delay_seconds=0.2,
        retry_on=lambda e: e.is_transient  # Only retry transient errors
    )
)
```

**Why:** By default, `retry()` retries on **all** errors. Use `retry_on` to filter which errors should trigger a retry.

---

#### Issue: "Performance problems with large collections"

**Symptom:**
```python
# Processes 10,000 items sequentially - very slow
results = await traverse(items, handler=process_item)
```

**Solution:** Use `traverse_par()` with bounded concurrency:
```python
results = await traverse_par(
    items,
    handler=process_item,
    concurrency=50  # Process 50 items at a time
)
```

**Why:** `traverse()` is sequential. For I/O-bound operations, use `traverse_par()` to process items in parallel.

**Alternative:** Use `batch()` for more control:
```python
results = await batch(
    items,
    handler=lambda item: ast(call(process_item, item)).retry(times=2).lower(),
    concurrency=50
)
```

---

#### Issue: "Can't compose different error types"

**Symptom:**
```python
# Type error: APIError incompatible with DBError
user = await fetch_user(42)  # Result[User, APIError]
posts = await fetch_posts(user.unwrap().id)  # Result[Posts, DBError]
```

**Solution:** Map errors to a common type:
```python
from dataclasses import dataclass

@dataclass
class AppError:
    source: str
    message: str

def to_app_error(e: APIError | DBError) -> AppError:
    return AppError(source=type(e).__name__, message=str(e))

user = await fetch_user(42).map_err(to_app_error)  # Result[User, AppError]
posts = await fetch_posts(user.unwrap().id).map_err(to_app_error)  # Result[Posts, AppError]
```

**Why:** Different error types are incompatible. Map them to a common error type for composition.

---

### Debugging Tips

#### Enable verbose logging

Use `tap()` and `tap_err()` to log intermediate values:

```python
pipeline = (
    ast(call(fetch_user, 42))
    .tap(effect=lambda u: logger.debug(f"Fetched: {u}"))
    .retry(times=3, delay_seconds=0.2)
    .tap_err(effect=lambda e: logger.error(f"Failed: {e}"))
    .timeout(seconds=5.0)
    .lower()
)
```

#### Inspect policies

Policies are dataclasses - print them to understand behavior:

```python
policy = RetryPolicy.exponential_jitter(times=5, initial=0.1)
print(policy)  # RetryPolicy(times=5, backoff=<function>, retry_on=None)
```

#### Test combinators in isolation

Create simple test cases:

```python
from combinators import pure, fail, retry
from combinators.control import RetryPolicy

async def test_retry():
    attempts = 0
    
    async def flaky() -> Result[int, str]:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return Error("transient")
        return Ok(42)
    
    result = await retry(
        call(flaky),
        policy=RetryPolicy.fixed(times=3, delay_seconds=0.0)
    )
    
    assert result == Ok(42)
    assert attempts == 3
```

---

## Migration Guide

### From tenacity to combinators

**Before (tenacity):**
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=0.2))
async def fetch_user(user_id: int) -> User:
    return await api.get(f"/users/{user_id}")
```

**After (combinators):**
```python
from combinators import ast, call
from combinators.control import RetryPolicy

def fetch_user(user_id: int) -> Interp[User, APIError]:
    return (
        ast(call(api.get, f"/users/{user_id}"))
        .retry(policy=RetryPolicy.exponential(times=3, initial=0.2))
        .lower()
    )
```

**Key differences:**
- Effects are visible at call site, not hidden in decorator
- Policy is explicit data structure, not decorator parameters
- Returns `Interp[User, APIError]`, not `User` (errors in type signature)

---

### From asyncio.timeout to combinators

**Before (asyncio):**
```python
import asyncio

async def fetch_with_timeout(user_id: int) -> User:
    async with asyncio.timeout(5.0):
        return await api.get(f"/users/{user_id}")
```

**After (combinators):**
```python
from combinators import ast, call

def fetch_with_timeout(user_id: int) -> Interp[User, APIError | TimeoutError]:
    return (
        ast(call(api.get, f"/users/{user_id}"))
        .timeout(seconds=5.0)
        .lower()
    )
```

**Key differences:**
- Timeout is composable with other effects (retry, fallback, etc.)
- Error type includes `TimeoutError` (explicit in signature)
- Can be tested without actually waiting

---

### From try/except to combinators

**Before (exceptions):**
```python
async def fetch_user_resilient(user_id: int) -> User:
    try:
        return await api.get(f"/users/{user_id}")
    except APIError:
        try:
            return await cache.get(f"user:{user_id}")
        except CacheMiss:
            raise UserNotFoundError()
```

**After (combinators):**
```python
from combinators import fallback_chain, call

def fetch_user_resilient(user_id: int) -> Interp[User, UserNotFoundError]:
    return fallback_chain(
        call(api.get, f"/users/{user_id}"),
        call(cache.get, f"user:{user_id}"),
        fail(UserNotFoundError())
    )
```

**Key differences:**
- No nested try/except - flat composition
- Error handling is explicit in the chain
- Type signature shows all possible errors

---

## Best Practices

### 1. Keep functions pure, lift at call site

**❌ Bad:**
```python
async def fetch_user(user_id: int) -> Interp[User, APIError]:
    # Function returns Interp - forces all callers to use combinators
    return call(api.get, f"/users/{user_id}")
```

**✅ Good:**
```python
async def fetch_user_impl(user_id: int) -> Result[User, APIError]:
    # Pure function - can be used with or without combinators
    return await api.get(f"/users/{user_id}")

# Lift at call site when needed
pipeline = ast(call(fetch_user_impl, 42)).retry(times=3).lower()
```

**Why:** Pure functions are more reusable. Lift to `Interp` only when you need combinator effects.

---

### 2. Use type aliases for complex error unions

**❌ Bad:**
```python
def fetch_data(key: str) -> Interp[Data, APIError | TimeoutError | CacheError | ValidationError]:
    ...
```

**✅ Good:**
```python
type FetchError = APIError | TimeoutError | CacheError | ValidationError

def fetch_data(key: str) -> Interp[Data, FetchError]:
    ...
```

**Why:** Shorter signatures, easier to read, single source of truth for error types.

---

### 3. Build policies from config

**❌ Bad:**
```python
# Hardcoded policies scattered across codebase
result = await retry(fetch(), policy=RetryPolicy.fixed(times=3, delay_seconds=0.2))
```

**✅ Good:**
```python
# Centralized config
@dataclass
class AppConfig:
    retry_times: int
    retry_delay: float
    timeout_seconds: float

config = load_config()

def make_retry_policy() -> RetryPolicy:
    return RetryPolicy.fixed(
        times=config.retry_times,
        delay_seconds=config.retry_delay
    )

# Use throughout codebase
result = await retry(fetch(), policy=make_retry_policy())
```

**Why:** Policies can be adjusted without code changes. Easier to test with different configs.

---

### 4. Prefer `ast()` for complex pipelines

**❌ Bad (deeply nested):**
```python
result = await timeout(
    retry(
        tap(
            call(fetch_user, 42),
            effect=lambda u: logger.info(f"Fetched {u}")
        ),
        policy=RetryPolicy.fixed(times=3)
    ),
    seconds=5.0
)
```

**✅ Good (flat pipeline):**
```python
result = await (
    ast(call(fetch_user, 42))
    .tap(effect=lambda u: logger.info(f"Fetched {u}"))
    .retry(times=3, delay_seconds=0.2)
    .timeout(seconds=5.0)
    .lower()
)
```

**Why:** Flat is better than nested. Read top-to-bottom, not inside-out.

---

### 5. Test policies separately from business logic

**✅ Good:**
```python
def test_retry_policy():
    policy = RetryPolicy.exponential(times=3, initial=0.1)
    
    # Test backoff calculation
    assert policy.backoff(0, Error("test")) == 0.1
    assert policy.backoff(1, Error("test")) == 0.2
    assert policy.backoff(2, Error("test")) == 0.4

async def test_fetch_user():
    # Test business logic with simple policy
    result = await fetch_user(42)
    assert result == Ok(User(id=42))
```

**Why:** Policies are data - test them directly. Business logic tests don't need to verify retry behavior.

---

## Conclusion

Combinators enable you to build resilient, composable async systems by treating effects as first-class values. The key principles are:

1. **Effects are composition, not decoration**
2. **Policies are data, not magic**
3. **Types are documentation**
4. **Locality matters**

Start small, compose incrementally, and enjoy the benefits of functional programming with effects.

### Next Steps

- Read the [LLM Reference](./llm-reference.md) for complete API documentation
- Check out [examples/](../examples/) for working code
- Join the discussion on [GitHub](https://github.com/prostomarkeloff/combinators.py)

### Further Reading

- [Railway Oriented Programming](https://fsharpforfunandprofit.com/rop/) - The philosophy behind Result types
- [Functional Programming in Scala](https://www.manning.com/books/functional-programming-in-scala) - Deep dive into FP concepts
- [Algebraic Effects](https://overreacted.io/algebraic-effects-for-the-rest-of-us/) - The theory behind effect systems
