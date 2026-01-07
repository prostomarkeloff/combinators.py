<div align="center">

# combinators.py

### _「 declarative way to build systems 」_

**Improve your code with monads**

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: strict](https://img.shields.io/badge/types-pyright%20strict-blue)](https://github.com/microsoft/pyright)

[Quick Start](#-quick-start) • [Examples](#examples) • [Documentation](docs/) • [Why Combinators?](#why-combinators)

---

> **⚠️ Status:** Under active development. API may change between versions.

</div>

---

```python
from combinators import ast, call, fallback_chain, race_ok
from combinators.concurrency import RaceOkPolicy
from kungfu import Ok, Error

# 🏎️ Race multiple replicas, retry on failure, timeout, fallback to cache
pipeline = (
    ast(race_ok(
        call(replica1.fetch, key),
        call(replica2.fetch, key),
        call(replica3.fetch, key),
        policy=RaceOkPolicy(cancel_pending=True, error_strategy="last")
    ))
    .retry(times=3, delay_seconds=0.2, retry_on=lambda e: e.is_transient)
    .timeout(seconds=5.0)
    .lower()
)

result = await fallback_chain(pipeline, call(cache.get, key))

match result:
    case Ok(data):
        print(f"✅ Success: {data}")
    case Error(err):
        print(f"❌ All sources failed: {err}")
```

<div align="center">

**`Interp[T, E]` is lazy `Result[T, E]` — typed, composable, testable**

</div>

---

## 📦 Installation

```bash
uv add git+https://github.com/prostomarkeloff/combinators.py.git
```

<details>
<summary><b>Requirements</b></summary>

- Python 3.13+
- [kungfu](https://github.com/timoniq/kungfu) - Result types and lazy coroutines

</details>

<div align="center">

### 🎯 What You Get

| Feature | Description |
|---------|-------------|
| 🔧 **Combinators** | Retry, timeout, fallback, race, parallel, and more |
| 🏗️ **Monads** | LazyCoroResult + Writer monad for structured effects |
| 🔒 **Type Safety** | Full pyright strict mode - errors in type signatures |
| 🧩 **Composability** | Stack effects like LEGO blocks |
| ✅ **Testability** | Policies as data, effects as values |

</div>

---

## 🤔 Why Combinators?

<div align="center">

**Traditional approaches hide effects. Combinators make them visible.**

</div>

### ❌ The decorator trap

Python developers love decorators. Need retry? `@retry`. Need timeout? `@timeout`. Need both?

```python
@timeout(5.0)
@retry(times=3, wait=exponential)
async def fetch_user(user_id: int) -> User:
    return await api.get(f"/users/{user_id}")
```

**Problems:**

1. **Composition is implicit.** What order do decorators execute? Top-down or bottom-up? You need to remember Python's decorator semantics.
2. **Retry logic is opaque.** What does `exponential` mean? 1s, 2s, 4s? 0.1s, 0.2s, 0.4s? Check the library docs.
3. **Can't compose dynamically.** Want different retry policies for different environments? Tough luck, decorators are static.
4. **Testing is hard.** How do you mock `@retry`? How do you verify timeout behavior? Decorators hide the control flow.

Libraries like [tenacity](https://github.com/jd/tenacity) make this worse:

```python
@retry(
    wait=wait_exponential(multiplier=1, min=4, max=10),
    stop=stop_after_attempt(7),
    retry=retry_if_exception_type(IOError),
    before_sleep=before_sleep_log(logger, logging.DEBUG)
)
async def fetch_user(user_id: int) -> User:
    ...
```

This is **configuration as decoration**. The retry policy is scattered across decorator parameters, invisible at the call site, and impossible to test without executing the entire decorated function.

### ❌ The middleware trap

Another popular approach: middleware.

```python
session = aiohttp.ClientSession()
session.middlewares.append(retry_middleware)
session.middlewares.append(timeout_middleware)
session.middlewares.append(logging_middleware)

response = await session.get("/users/42")
```

**Problems:**

1. **Global state.** Middleware is attached to the session. Every request uses the same policy. Want different timeout for health checks? Create another session.
2. **Order matters.** Middleware executes in registration order. Change the order, change the behavior. This is **implicit** and **brittle**.
3. **Invisible at call sites.** Look at `session.get("/users/42")`. Can you tell what effects are applied? No. You have to find where the session was created.
4. **Testing is painful.** Mock the session? Mock the middleware? Both? Neither?

### ✅ The combinator solution

Combinators keep effects **visible, composable, testable**:

```python
from combinators import ast, call

def fetch_user(user_id: int) -> Interp[User, APIError]:
    return (
        ast(call(api.get, f"/users/{user_id}"))
        .retry(times=3, delay_seconds=0.2, retry_on=lambda e: e.is_transient)
        .timeout(seconds=5.0)
        .tap(effect=lambda u: logger.info(f"Fetched {u.name}"))
        .lower()
    )
```

**Why it's better:**

- 👁️ **Visible** — Read the code, see the effects. No hidden magic.
- 🧩 **Composable** — Stack effects like LEGO blocks. Just function composition.
- 🧪 **Testable** — Policies are data. Test without mocking.
- 🔧 **Dynamic** — Build policies from config, environment, feature flags.

<div align="center">

**[See more comparisons](#vs-other-libraries) | [Read the full story](docs/human-guide.md#introduction)**

</div>

---

## 💡 What Are Combinators?

Combinators are **functions that take functions and return functions**. That's it.

```python
retry: (Interp[T, E], times: int, delay: float) -> Interp[T, E]
timeout: (Interp[T, E], seconds: float) -> Interp[T, TimeoutError | E]
fallback: (Interp[T, E], Interp[T, E]) -> Interp[T, E]
```

They transform computations, not decorate them.

### The primitive: `Interp[T, E]`

```python
type Interp[T, E] = LazyCoroResult[T, E]
```

An `Interp[T, E]` is a **lazy, async computation** that produces `Result[T, E]` when executed.

- **Lazy:** Nothing executes until you `await`. Compose first, run later.
- **Async:** Built on `async`/`await`, no thread pools or executors.
- **Typed:** `T` is the success type, `E` is the error type. No hidden exceptions.

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

### Lifting: from values to Interp

The `lift` module provides helpers to construct `Interp` values:

```python
from combinators import lift

# Pure value -> always-succeeding Interp
x = lift.pure(42)  # Interp[int, Never]

# Error value -> always-failing Interp
e = lift.fail(NotFoundError())  # Interp[Never, NotFoundError]

# Call a function (most common pattern)
result = lift.call(fetch_user, user_id)  # Interp[User, APIError]

# Wrap async function
result = lift.wrap_async(lambda: api.get("/data"))  # Interp[Data, APIError]

# From Result
from kungfu import Ok
from combinators import from_result
result = from_result(Ok(42))  # Interp[int, NoError]
```

**Locality principle:** Write pure functions, lift at call site:

```python
# Pure function (no Interp dependency)
async def fetch_user_impl(user_id: int) -> Result[User, APIError]:
    return await api.get(f"/users/{user_id}")

# Lift at call site (locality!)
from combinators import call
pipeline = (
    ast(call(fetch_user_impl, 42))
    .retry(times=3, delay_seconds=0.2)
    .timeout(seconds=5.0)
    .lower()
)
```

This means **no refactoring required**. Old code stays pure, compose effects where needed.

### The AST builder: `ast()`

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

## 🔥 Effects-Hell in Real Systems

Production systems need **multiple effects per operation**. Existing libraries force you to pick one paradigm. Combinators let you compose them all.

### Scenario: Resilient data fetching

You need to fetch user data with:

- **Retry** on transient errors (3x, exponential backoff)
- **Timeout** (2s)
- **Fallback** to cache or replica
- **Rate limiting** (10 req/sec)
- **Parallel** requests to multiple backends
- **Race** for fastest response
- **Validation** of the result
- **Logging** of successes and failures

With traditional approaches, this becomes a nightmare.

#### The traditional way (tenacity + asyncio)

```python
from tenacity import retry, stop_after_attempt, wait_exponential
import asyncio

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=0.2, max=1))
async def fetch_user_with_retry(user_id: int) -> User:
    async with asyncio.timeout(2.0):
        return await api.get(f"/users/{user_id}")

async def fetch_user_resilient(user_id: int) -> User:
    try:
        # Try primary source
        return await fetch_user_with_retry(user_id)
    except (TimeoutError, APIError):
        try:
            # Try cache
            return await cache.get(f"user:{user_id}")
        except CacheMiss:
            try:
                # Try replica
                return await replica.get(f"/users/{user_id}")
            except ReplicaError:
                # Give up
                raise
```

**Problems:**

1. **Nested try/except.** The deeper you go, the harder it is to follow.
2. **Retry logic is hidden.** `@retry` decorator parameters are metadata, not visible at call site.
3. **Timeout is per-call.** Can't configure different timeouts for cache vs replica.
4. **Can't race.** Sequential fallback means slow replicas block fast ones.
5. **Validation?** Add another `if` statement? Another try/except?

**Line count:** ~20 lines for basic resilience.

#### The combinator way

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

**Why it's better:**

1. **Declarative.** Read the code, see the effects. No hidden logic.
2. **Composable.** Each effect is explicit. Want to add validation? Call `.ensure()`. Want to add logging? Call `.tap()`.
3. **Testable.** Create an `Interp`, test the effects without executing the entire pipeline.
4. **Efficient.** `race_ok` cancels pending tasks on first success. No wasted work.

**Line count:** ~15 lines for **more** resilience (race + retry + timeout + fallback).

### Real-world example: LLM resilient pipeline

LLMs are slow and unreliable. You want:

- Race a fast model vs. a smart model
- Retry on rate limits
- Pick the best of N attempts
- Validate quality
- Fallback to cached response

```python
from combinators import ast, call, race_ok, fallback_chain
from combinators.concurrency import RaceOkPolicy

async def llm_fast(prompt: str) -> Result[Sample, ModelError]:
    # Fast but low quality
    ...

async def llm_smart(prompt: str) -> Result[Sample, ModelError]:
    # Slow but high quality
    ...

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

**This code:**

1. Races fast model vs. smart model
2. Retries 3x on transient errors (rate limits)
3. Runs 3 attempts, picks best by quality
4. Validates quality >= 0.8
5. Falls back to cache if all fail

**Traditional approach:** 50+ lines of nested try/except with explicit state management. **Combinators:** 20 lines, all effects visible.

---

## 📖 Programs Are Text

Code is **text** that humans read. Readability isn't a nice-to-have, it's **the key to maintainability**.

### Declarative beats imperative

Compare these two programs:

**Imperative (traditional):**

```python
async def fetch_user(user_id: int) -> User:
    for attempt in range(3):
        try:
            async with asyncio.timeout(5.0):
                user = await api.get(f"/users/{user_id}")
                logger.info(f"Fetched: {user.name}")
                if user.is_active:
                    return user
                else:
                    raise InactiveUserError()
        except (TimeoutError, ConnectionError) as e:
            if attempt < 2:
                await asyncio.sleep(0.2 * (2 ** attempt))
            else:
                try:
                    return await cache.get(f"user:{user_id}")
                except CacheMiss:
                    raise UserNotFoundError()
```

Read this code. What does it do? You have to **execute it mentally**:

1. Loop 3 times (retry)
2. Timeout of 5 seconds
3. Fetch user
4. Log the result
5. Check if active
6. If error, sleep exponentially
7. After 3 attempts, try cache
8. If cache misses, raise error

**Declarative (combinators):**

```python
def fetch_user(user_id: int) -> Interp[User, APIError]:
    return (
        ast(call(api.get, f"/users/{user_id}"))
        .retry(times=3, delay_seconds=0.2, retry_on=lambda e: e.is_transient)
        .timeout(seconds=5.0)
        .tap(effect=lambda u: logger.info(f"Fetched: {u.name}"))
        .ensure(predicate=lambda u: u.is_active, error=lambda u: InactiveUserError())
        .recover_with(handler=lambda _: call(cache.get, f"user:{user_id}"))
        .lower()
    )
```

Read this code aloud:

> "Fetch user, retry 3 times with 0.2s delay on transient errors, timeout after 5 seconds, log the result, ensure user is active, recover from errors by fetching from cache."

**The difference:** Declarative code says **what** you want. Imperative code says **how** to do it. Humans care about **what**, not **how**.

### Policies as data, not magic

Decorators hide policies in metadata:

```python
@retry(wait=wait_exponential(multiplier=1, min=4, max=10))
async def fetch():
    ...
```

What does `wait_exponential(multiplier=1, min=4, max=10)` mean?

- 4s, 8s, 10s?
- 1s, 4s, 8s?
- Something else?

You have to read the library docs. **The code doesn't tell you.**

Combinators make policies explicit:

```python
from combinators.control import RetryPolicy

from combinators.control import RetryPolicy

policy = RetryPolicy.fixed(
    times=3,
    delay_seconds=0.5,
    retry_on=lambda e: e.is_transient  # Only retry transient errors
)

from combinators import retry
result = await retry(fetch(), policy=policy)
```

**Why it's better:**

1. **Policy is data.** A `dataclass`, not magic. You can print it, serialize it, store it in a config file.
2. **Self-documenting.** Read the policy, understand the behavior. No docs required.
3. **Testable.** Create a policy, assert on its fields. No mocking required.
4. **Dynamic.** Build policies from config, environment, feature flags.

Example: different retry policies for dev vs. prod:

```python
import os

if os.getenv("ENV") == "production":
    policy = RetryPolicy.fixed(times=5, delay_seconds=1.0)
else:
    policy = RetryPolicy.fixed(times=1, delay_seconds=0.1)  # Fast feedback in dev

result = await retry(fetch(), policy=policy)
```

Can't do this with decorators.

### Types are documentation

`pyright --strict` passes the entire codebase. Types don't lie:

```python
# fetch_user returns Result[User, APIError]
result: Result[User, APIError] = await fetch_user(42)

# Add timeout: now returns Result[User, APIError | TimeoutError]
result: Result[User, APIError | TimeoutError] = await (
    ast(fetch_user(42))
    .timeout(seconds=5.0)
    .lower()
)

# Add fallback: error type narrows back to APIError (fallback handles TimeoutError)
result: Result[User, APIError] = await fallback(
    ast(fetch_user(42)).timeout(seconds=5.0).lower(),
    call(cache.get, f"user:42")
)
```

**The key insight:** If a combinator changes the error type, it's **visible in the signature**. No hidden exceptions, no surprises.

Compare to traditional code:

```python
async def fetch_user(user_id: int) -> User:
    # What exceptions can this raise?
    # TimeoutError? ConnectionError? APIError?
    # You have to read the implementation to know.
    ...
```

With combinators, **the type signature is the contract**.

---

## 🎯 Locality as First Principle

**Locality** means: everything you need to understand a piece of code is **right there**, not scattered across files or hidden in global state.

### Effects at the call site

Decorators hide effects:

```python
@retry(times=3)
@timeout(5.0)
async def fetch():
    ...

# Call site: no idea retry/timeout are applied
result = await fetch()
```

Middleware hides effects:

```python
session = aiohttp.ClientSession()
session.middlewares.append(retry_middleware)
session.middlewares.append(timeout_middleware)

# Call site: no idea what middleware is active
response = await session.get("/users/42")
```

Combinators keep effects **visible**:

```python
result = await (
    ast(fetch())
    .retry(times=3, delay_seconds=0.2)
    .timeout(seconds=5.0)
    .lower()
)

# Read the code, see the effects. No surprises.
```

**Why it matters:** When debugging, you don't want to hunt for where retry logic is defined. You want to **see it at the call site**.

### No global state

Combinators don't use global state. Everything is **explicit**:

```python
# ❌ Bad: global config
RETRY_TIMES = 3
RETRY_DELAY = 0.2

async def fetch():
    for attempt in range(RETRY_TIMES):
        ...

# ✅ Good: explicit policy
from combinators.control import RetryPolicy
policy = RetryPolicy.fixed(times=3, delay_seconds=0.2)
result = await retry(fetch(), policy=policy)
```

**Why it matters:**

- **Testing.** Create a policy, test retry logic in isolation.
- **Flexibility.** Different policies for different operations.
- **Refactoring.** Change retry behavior without touching global state.

### Incremental adoption

You don't need to rewrite your codebase to use combinators. Start small:

**Week 1: Add validation**

```python
from combinators import validate, call

def validate_form(form: Form) -> Interp[Form, list[str]]:
    return validate([
        call(validate_email, form.email),
        call(validate_password, form.password),
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

**No big rewrite.** Each step is **local** and **independent**. Old code doesn't need refactoring.

### Composition over configuration

Frameworks love configuration objects:

```python
# ❌ Bad: configuration blob
config = {
    "retry": {"times": 3, "delay": 0.2},
    "timeout": {"seconds": 5.0},
    "fallback": {"enabled": True, "source": "cache"}
}

result = await fetch_with_config(user_id, config)
```

**Problems:**

1. **Opaque.** What does this config do? You have to read the implementation.
2. **Order-dependent.** Does retry happen before or after timeout? Config doesn't say.
3. **Hard to test.** Mock the config? Mock the entire system?

Combinators **compose**:

```python
# ✅ Good: explicit composition
result = await (
    ast(fetch(user_id))
    .retry(times=3, delay_seconds=0.2)
    .timeout(seconds=5.0)
    .lower()
)

# Order is explicit: retry THEN timeout
# Want timeout THEN retry? Swap the lines.
```

**Why it's better:**

- **Visible.** Read the code, see the order.
- **Flexible.** Rearrange combinators to change behavior.
- **Testable.** Test each combinator in isolation.

---

## 🚀 Core API

<div align="center">

**Quick reference for the most common combinators**

[Full API Reference →](docs/llm-reference.md#api-reference)

</div>

### Control Flow

```python
from combinators import retry, fallback, recover, ensure

# Retry on failure
from combinators.control import RetryPolicy
policy = RetryPolicy.fixed(times=3, delay_seconds=0.2, retry_on=lambda e: e.is_transient)
await retry(fetch(), policy=policy)

# Fallback to alternative
await fallback(primary(), secondary())

# Recover from errors
await recover(fetch(), default=default_value)
# Or with handler:
await recover_with(fetch(), handler=lambda e: default_value)

# Validate result (using Flow API)
from combinators import ast, call
await (
    ast(call(fetch))
    .ensure(predicate=lambda x: x.is_valid, error=lambda x: InvalidError())
    .lower()
)
```

### Concurrency

```python
from combinators import parallel, race, race_ok, batch, gather2

# Run in parallel, collect all results
await parallel([fetch(1), fetch(2), fetch(3)])

# Race: first to finish wins
await race(fetch_from_db(), fetch_from_api())

# Race for first success (ignore failures)
await race_ok(replica1(), replica2(), replica3())

# Bounded parallelism
await batch(items, handler=process_item, concurrency=10)

# Zip two computations
await gather2(fetch_user(1), fetch_posts(1))
```

### Collections

```python
from combinators import traverse, sequence, fold, validate

# Apply handler to each item (sequential)
await traverse([1, 2, 3], handler=fetch_user)

# Apply handler to each item (parallel)
await traverse_par([1, 2, 3], handler=fetch_user, concurrency=10)

# Sequence a list of Interps
await sequence([fetch(1), fetch(2), fetch(3)])

# Reduce a list (effectful fold)
from combinators import pure
await fold([1, 2, 3], handler=lambda acc, x: pure(acc + x), initial=0)

# Validate multiple computations (collect ALL errors)
await validate([check1(), check2(), check3()])
```

### Time

```python
from combinators import timeout, delay

# Add timeout
await timeout(fetch(), seconds=5.0)

# Delay before executing
await delay(fetch(), seconds=1.0)
```

### Transform

```python
from combinators import tap, tap_err

# Side effect on success
await tap(fetch(), effect=lambda x: logger.info(f"Got {x}"))

# Side effect on error
await tap_err(fetch(), effect=lambda e: logger.error(f"Failed: {e}"))
```

---

## ⚖️ vs Other Libraries

| Feature | tenacity | asyncio | combinators.py |
|---------|----------|---------|----------------|
| **Retry** | `@retry(...)` decorator | Manual loop | `retry(...)` combinator |
| **Composability** | Decorators stack implicitly | Manual composition | Explicit composition |
| **Visibility** | Hidden in decorators | Scattered in code | Explicit at call site |
| **Type safety** | No types | No types | `Result[T, E]` |
| **Testing** | Mock decorators | Mock primitives | Test policies |
| **Dynamic policies** | Static decorators | Manual | Policies as data |
| **Error handling** | Exceptions | Exceptions | `Result[T, E]` |
| **Fallback** | Not built-in | Manual | `fallback(...)` |
| **Race** | Not built-in | `asyncio.create_task` | `race_ok(...)` |
| **Validation** | Not built-in | Manual | `validate(...)` |

---

## 💻 Examples

<div align="center">

See [`examples/`](examples/) for working code

</div>

| Example | What it demonstrates |
|---------|---------------------|
| [`01_quickstart.py`](examples/01_quickstart.py) | 🚀 Basic usage patterns |
| [`02_cache_fallback_race_ok.py`](examples/02_cache_fallback_race_ok.py) | 🏎️ Fallback + race strategies |
| [`09_llm_resilient_pipeline.py`](examples/09_llm_resilient_pipeline.py) | 🤖 LLM resilience patterns |
| [`beautiful_chaining.py`](examples/beautiful_chaining.py) | ✨ Real-world composition |

---

## 📚 Documentation

<div align="center">

### Choose Your Path

| For Humans 📖 | For AI 🤖 |
|---------------|----------|
| [**Human Guide**](docs/human-guide.md) | [**LLM Reference**](docs/llm-reference.md) |
| Narrative-style learning | Structured API reference |
| Concepts & philosophy | Code generation guidelines |
| Real-world examples | Type transformations |
| Troubleshooting | Performance characteristics |

**[📁 Documentation Index](docs/) • [🐛 Troubleshooting](docs/human-guide.md#troubleshooting) • [🔄 Migration Guide](docs/human-guide.md#migration-guide)**

</div>

---

## 🤝 Contributing

We welcome contributions! Here's how to help:

- 🐛 [Report bugs](https://github.com/prostomarkeloff/combinators.py/issues)
- 💡 [Suggest features](https://github.com/prostomarkeloff/combinators.py/issues)
- 📝 Improve documentation
- 🔧 Submit pull requests

See [contributing guidelines](docs/README.md#-contributing) for details.

---

## 🔗 Related Projects

- [kungfu](https://github.com/timoniq/kungfu) — Result types and lazy coroutines (foundation)
- [tenacity](https://github.com/jd/tenacity) — Retry library (alternative approach)
- [returns](https://github.com/dry-python/returns) — Railway-oriented programming in Python

---

## ⭐ Show Your Support

If you find this project useful:
- ⭐ Star the repo
- 📣 Share with others
- 💬 Join the discussion
- 🤝 Contribute

---

<div align="center">

## 📄 License

**MIT** — See [LICENSE](LICENSE) for details

---

**Made with ❤️ by [@prostomarkeloff](https://github.com/prostomarkeloff)**

[⬆ Back to Top](#combinatorspy)

</div>
