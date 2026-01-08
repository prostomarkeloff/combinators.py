<div align="center">

# combinators.py

**Build systems the declarative way**

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Types: pyright strict](https://img.shields.io/badge/types-pyright%20strict-blue)](https://github.com/microsoft/pyright)

</div>

---

> "Truth is more easily concluded from error than from confusion." — Francis Bacon

Most software is built on a foundation of hope—the hope that the "Happy Path" will prevail. But in distributed systems, the Happy Path is a statistical anomaly. Chaos is the default.

`combinators.py` is a framework for building asynchronous systems that don't just "work," but work **predictably**. It provides a set of mathematical primitives (combinators) to transform fragile code into a resilient, type-safe computation graph.

---

## Before & After

<table>
<tr>
<td width="50%">

**❌ Standard Python: 47 lines of chaos**

```python
async def fetch_with_retry(url):
    last_error = None
    for attempt in range(3):
        try:
            async with asyncio.timeout(5.0):
                result = await http.get(url)
                if result.status == 429:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return result.json()
        except asyncio.TimeoutError:
            last_error = TimeoutError()
        except Exception as e:
            last_error = e
            await asyncio.sleep(2 ** attempt)
    
    # Fallback to cache
    try:
        return await cache.get(url)
    except:
        return DEFAULT_VALUE
```

</td>
<td width="50%">

**✅ Combinators: 12 lines of intent**

```python
from combinators import flow, lift as L, fallback_chain
from combinators.control import RetryPolicy

fetch = (
    flow(L.call_catching(http.get, on_error=map_err, url=url))
    .retry(policy=RetryPolicy.exponential_jitter(times=3))
    .timeout(seconds=5.0)
    .compile()
)

result = await fallback_chain(fetch, cache_op, L.up.pure(DEFAULT))
```

</td>
</tr>
</table>

**The difference?** One is *instructions*. The other is *topology*. One hides failure in control flow. The other makes failure a first-class citizen of the type system.

---

## The Vision: Algebra Instead of Glue

When we build reliable systems, we are often forced to write "glue code": retry loops, timeout wrappers, and nested `try/except` blocks. This code is imperative, repetitive, and often hides the actual business logic.

`combinators.py` turns these reliability patterns into **first-class values**.

*   **Retry** is not a loop; it is a function.
*   **Timeout** is not an exception; it is a type transformation.
*   **Fallback** is not a nested branch; it is an algebraic choice.

By treating these patterns as values, we can compose them like LEGO bricks, building complex survival strategies from simple, honest building blocks.

---

## A Glimpse of the Future

Consider a multi-provider LLM pipeline. We want to race two providers, retry on rate limits, enforce an SLA, and guarantee content safety. In standard Python, this is a 50-line mess of concurrency and error handling. In `combinators.py`, it is a blueprint:

```python
from combinators import flow, lift as L, race_ok
from combinators.control import RetryPolicy

# 1. Lift external APIs into an honest context
fetch_openai = L.call_catching(
    openai.chat.completions.create,
    on_error=map_openai_error,
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}],
)

fetch_anthropic = L.call_catching(
    anthropic.messages.create,
    on_error=map_anthropic_error,
    model="claude-3",
    messages=[{"role": "user", "content": prompt}],
)

# 2. Compose the resilience strategy (The Blueprint)
pipeline = (
    flow(race_ok(fetch_openai, fetch_anthropic))  # Fastest success wins
    .retry(
        policy=RetryPolicy.exponential_jitter(times=3),
        retry_on=lambda e: e.kind == "rate_limit",  # Targeted retry
    )
    .timeout(seconds=10.0)                        # Enforce SLA
    .ensure(                                      # Domain invariant
        predicate=lambda r: r.content.safety_score > 0.9,
        error=lambda r: ContentPolicyError(score=r.content.safety_score),
    )
    .compile()
)

# 3. Execute with total type-safety
result = await pipeline  # Result[Message, APIError | TimeoutError | ContentPolicyError]

match result:
    case Ok(msg): 
        return Response(content=msg.text)
    case Error(ContentPolicyError(score)):
        return Response(error="unsafe_content", score=score, status=400)
    case Error(err):
        return Response(error="service_unavailable", details=str(err), status=503)
```

## The Distributed Mindset

Standard programming assumes a "Local World." In the local world, memory is cheap, latency is zero, and functions always return. 

Distributed systems exist in the "Global Chaos." In this world:
1.  **Latency is a feature, not a bug.** If you don't model time, time will destroy your system.
2.  **Partial success is a failure in disguise.** If two out of three nodes succeed, is your system in a valid state?
3.  **Observability is not optional.** If you can't see why a computation failed, you can't fix it.

`combinators.py` is designed for the Global Chaos. It treats these problems not as annoyances to be patched, but as fundamental properties of the computation.

### Type-Driven Reliability

In standard Python, exceptions are invisible. You cannot see that `fetch_user` might raise a `TimeoutError` without reading its source code.

In `combinators.py`, reliability is driven by the type system. When you add a `.timeout(2.0)` to your flow, the type signature of your pipeline changes. It evolves from `Interp[T, E]` to `Interp[T, E | TimeoutError]`.

This means the compiler becomes your partner in reliability. It prevents you from forgetting to handle a timeout. It forces you to acknowledge every failure mode you've introduced. This is what we call **Type-Driven Reliability**.

---

## Core Pillars

### I. The Honest Function
Standard Python functions lie. They claim to return a value but often throw an exception instead. `combinators.py` uses `Result[T, E]` to force functions to be honest about their failure modes. If a function can fail, it **must** say so in its type signature.

### II. The Fourth Dimension (Laziness)
A `Result` represents the past. An `Interp` (Blueprint) represents the future. By making computations lazy, we gain the power to modify them before they run. We can add retries to a future that hasn't happened yet.

### III. The Algebra of Composition
Computations are values. You can add them together (`fallback`), multiply them (`parallel`), or sequence them (`then`). These aren't metaphors; they are mathematical operations that preserve type safety and predictability.

### IV. The Fortress of Data
We don't "validate" data after it enters our system; we **parse** it at the border. By the time your business logic receives a value, it is guaranteed to be valid by its very type. We make illegal states unrepresentable.

---

## The Tower of Abstraction

`combinators.py` is built on three levels of power, each tradeable for simplicity:

| Level | Name | Purpose |
|-------|------|---------|
| **Level 1** | `Result[T, E]` | **Honesty.** Replace exceptions with explicit values. Use for leaf logic. |
| **Level 2** | `Interp[T, E]` | **Laziness.** Model computations as "blueprints". Use for building blocks. |
| **Level 3** | `Flow[T, E]` | **Composition.** Fluent API for chaining reliability patterns. Use for service boundaries. |

---

## Why Choose Combinators?

| Feature | Standard Python | Decorators | Combinators |
|---------|-----------------|------------|-------------|
| **Composition** | Nested `try/except` | Fixed stack | Algebraic & Fluid |
| **Type Safety** | Implicit (None) | Opaque | Explicit (Unions) |
| **Visibility** | Hidden in implementation | Hidden in decorators | First-class values |
| **Testing** | Heavy mocking | Hard to isolate | Test blueprints directly |
| **Concurrency** | Manual `asyncio.gather` | Hard to manage | Built-in (Batch, Race) |

---

## Real-World Case: Multi-Tier Read Path

Distributed systems thrive on redundancy. Here is a production-grade read path: **Primary DB** raced against a **Replica**, falling back to a **Cache**, and finally to a **Hardcoded Default**.

```python
from combinators import flow, lift as L, fallback_chain, race_ok
from combinators.control import RetryPolicy

# Define our tiers
primary = L.call_catching(db.get, on_error=map_db_error, key="config")
replica = L.call_catching(replica.get, on_error=map_db_error, key="config")
cache   = L.call_catching(redis.get, on_error=map_cache_error, key="config")

# Build the hierarchy
db_tier = (
    flow(race_ok(primary, replica)) # Low-latency dual-query
    .retry(times=2)                 # Transient retry
    .timeout(seconds=2.0)           # SLA enforcement
    .compile()
)

# The final read path: absolute resilience
read_path = fallback_chain(
    db_tier, 
    cache, 
    L.pure(DEFAULT_CONFIG) # The ultimate safety net
)

result = await read_path # Result[Config, Never]
```

---

## Installation

`combinators.py` requires Python 3.13+ and the `kungfu` library.

```bash
uv add git+https://github.com/prostomarkeloff/combinators.py.git
```

---

## Documentation

### Start Here

| Document | Purpose | Audience |
|----------|---------|----------|
| **[The Human Guide](docs/human-guide.md)** | Deep dive into philosophy and practice | Humans learning the library |
| **[LLM Reference](docs/llm-reference.md)** | Complete API reference, patterns, guidelines | AI assistants & code generation |
| **[The Emergence](docs/llm_emerges.md)** | LLM + Combinators: emergent patterns | Those curious about AI-assisted development |

### Deep Dives

| Document | What You'll Learn |
|----------|-------------------|
| **[Philosophy](docs/philosophy.md)** | Why the "Happy Path" is a myth. Explicit proofs, two-track model, system boundaries. |
| **[Writing Your Own Monads](docs/writing_own_monads.md)** | State monad, Reader monad, custom effects. When to extend, when to stop. |
| **[Examples](examples/)** | Working code: quickstart, caching, LLM pipelines, beautiful chaining. |

### Quick Navigation

| I want to... | Go to |
|-------------|-------|
| Learn the library from scratch | [Human Guide](docs/human-guide.md) |
| Generate code with AI | [LLM Reference](docs/llm-reference.md) |
| Understand why combinators + LLMs work | [The Emergence](docs/llm_emerges.md) |
| See the philosophy | [Philosophy](docs/philosophy.md) |
| Write a custom monad | [Writing Your Own Monads](docs/writing_own_monads.md) |
| Look up a function signature | [API Reference](docs/llm-reference.md#api-reference) |
| See common patterns | [Common Patterns](docs/llm-reference.md#common-patterns) |

---

<div align="center">

**Stop hoping your code works. Start proving it does.**

Created with ⚖️ by **[@prostomarkeloff](https://github.com/prostomarkeloff)**

</div>
