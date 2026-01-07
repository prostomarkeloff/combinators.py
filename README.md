# combinators.py

**Declarative way to build systems**

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Types: pyright strict](https://img.shields.io/badge/types-pyright%20strict-blue)](https://github.com/microsoft/pyright)

<p align="center">
  <strong>"Make illegal states unrepresentable."</strong>
</p>

---

```python
from combinators import flow, lift as L, race_ok, parallel

# 1. Define your units of work (Blueprints, not Tasks)
fetch_openai = L.call(openai.generate, prompt)
fetch_anthropic = L.call(anthropic.generate, prompt)

# 2. Compose the Resilient Pipeline
pipeline = (
    # Race providers: First success wins.
    flow(race_ok(fetch_openai, fetch_anthropic))
    
    # Policy: Retry rate limits, fast fail on auth errors
    .retry(
        times=3,
        delay_seconds=0.5,
        retry_on=lambda e: e.is_rate_limit
    )
    
    # SLA: Must respond within 2 seconds
    .timeout(seconds=2.0)
    
    # Quality Control: Switch to Failure Track if answer is unsafe
    .ensure(
        predicate=lambda r: r.safety_score > 0.9,
        error=lambda r: UnsafeContentError(r)
    )

    .compile()
)

# 3. Execute. The type system guarantees you handle the result.
# result: Result[Response, APIError | TimeoutError | UnsafeContentError]
result = await pipeline
```

## The Big Lie

Consider this standard Python type signature:

```python
async def fetch_user(id: int) -> User:
    ...
```

**This is a lie.**

This function claims it takes an `int` and returns a `User`. It does not tell you that:
1. It might raise `TimeoutError`.
2. It might raise `ConnectionError`.
3. It might raise `ValidationException` if the ID is negative.
4. It might hang forever if configured incorrectly.

Your type signature is a contract. When you use exceptions for control flow, you are writing checks that bounce.

## Explicit Proofs

We shouldn't just check if things are valid; we should structure our data so that validity is guaranteed by construction.

In the async world, this means rejecting implicit exceptions in favor of explicit **Results**.

```python
# The Truth
async def fetch_user(id: int) -> Result[User, APIError | TimeoutError]:
    ...
```

Now the typechecker forces you to handle the sad path. The error is no longer a ghost in the machine; it is a value in your code.

## The Two Tracks

Think of every operation as a junction. The path splits: one way for success, another for failure.

Traditional code tangles these paths together. You end up constantly checking for `None` or wrapping huge blocks in `try/except`.

`combinators.py` gives you the tools to keep these paths separate but parallel.

```python
from combinators import flow, lift as L

# The Happy Path is clean. The Sad Path is handled on the side rails.
pipeline = (
    flow(L.call(api.get_user, 42))
    .retry(times=3)               # If Failure Track (Error), try again
    .timeout(seconds=5.0)         # If time > 5s, switch to Failure Track (Timeout)
    .compile()
)
```

## Composition > Extension

We build robust systems by composing small, understandable pieces, not by extending objects or stacking global middleware.

This library is a collection of **combinators**. 

*   **Decorators are opaque.** You can't see what they do to the return type.
*   **Combinators are transparent.** They are functions that take a computation and return a new computation.

```python
# Extension (The Old Way)
@retry # Hidden logic, hidden state, hidden types
async def do_thing(): ...

# Composition (The Way)
op = L.call(do_thing)
reliable_op = retry(op, policy=exponential)
```

## The Algebra of Systems

We treat async operations as **values**. Once they are values, we can perform algebra on them.

*   **Product (AND):** `parallel(a, b)` — Run both. Fails if either fails.
*   **Sum (OR):** `race(a, b)` — Run both. Succeeds if either succeeds.
*   **Fallback:** `fallback_chain(a, b)` — If A fails, try B.

## Installation

```bash
uv add git+https://github.com/prostomarkeloff/combinators.py.git
```

Requires Python 3.13+ and [kungfu](https://github.com/timoniq/kungfu).

## Documentation

- **[Human Guide](docs/human-guide.md)** — From "I hope this works" to "I can prove this works".
- **[Philosophy](docs/philosophy.md)** — The intersection of Functional Programming and Distributed Systems.
- **[LLM Reference](docs/llm-reference.md)** — The raw API contracts.

## Example: The Resilient Pipeline

```python
from combinators import flow, lift as L, race_ok

# 1. Define the unit of work (Lazy)
fetch = L.call(db.fetch, query)

# 2. Define the policy (Data)
policy = RetryPolicy.exponential_jitter(times=3)

# 3. Compose the system
# "Race two databases. If the winner fails, retry it. If that times out, fail."
pipeline = (
    flow(race_ok(fetch, fetch_replica))
    .retry(policy=policy)
    .timeout(seconds=2.0)
    .compile()
)

# 4. Execute (Explicit Result)
result = await pipeline
# result is Result[Row, DBError | TimeoutError]
```

---

**[@prostomarkeloff](https://github.com/prostomarkeloff)**
