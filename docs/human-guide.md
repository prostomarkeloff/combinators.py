# The Human Guide to Robust Systems

> "To know is to know the cause." — Francis Bacon

This guide is more than a library manual—it's a way to think about programming under uncertainty.

Most Python code is written for the "happy path": networks never fail, databases are always reachable, and users send perfect JSON. Production systems don't work that way: latency and failure are normal.

This library helps you build systems that treat failure as a first-class concern—and keep behaving predictably when infrastructure doesn't cooperate.

---

## Part I: Foundations of Reliable Logic

### Chapter 1: Systematic Doubt in Programming

Consider this claim: "This function returns a user." Is it true?

Not always. The database might be down. The user might not exist. The network might time out. A memory error could strike.

Traditional programming assumes **optimistic execution**: we write code as if it will always succeed. In production, this optimism leaks into bugs.

This library takes a different approach: **defensive construction**. Assume every external call can fail, and make those failure boundaries explicit in types. That's not pessimism—it's engineering discipline: you can't control external systems, but you can control your response.

### Chapter 2: Errors as Data

In standard programming, an error is an "exception"—something abnormal that interrupts normal flow. In distributed systems, errors are routine: a database being unavailable is just another state.

The problem with exceptions is that they hide failure from the type system. When we treat errors as values, failures become explicit, typed, and programmatically handleable.

This is the **Result pattern**: every operation returns either success or failure, and both paths are explicit in the type signature.

---

## Part II: Type-Level Honesty

### Chapter 3: The Problem with Incomplete Type Signatures

#### Hidden Failure Modes

Consider a typical Python function signature:

```python
async def get_user_preferences(user_id: int) -> UserPreferences:
    config = await db.fetch(f"user:{user_id}:config")
    return UserPreferences.from_dict(config)
```

The signature promises: *"Give me an integer, get a UserPreferences object."*

But this is incomplete. The function actually might:
1.  Raise `ConnectionError` if the database is rebooting.
2.  Raise `TimeoutError` if the network is congested.
3.  Raise `KeyError` if the user ID doesn't exist.
4.  Raise `AttributeError` if the returned data is `None`.

The type signature shows only one return path, but the function has multiple invisible exit points. The map (signature) doesn't match the terrain (runtime behavior). Code "works" only when all external dependencies cooperate.

#### Exceptions Break Local Reasoning

`GOTO` statements are considered harmful because they break linear control flow—you can't understand code by reading it sequentially.

**Exceptions have the same problem.**

When an exception is raised, execution jumps to an unknown location: one line up, ten stack frames up, or to the top-level crash handler. Looking at a single line of code doesn't tell you where control goes next. You need to trace the entire call stack and exception hierarchy.

In distributed systems, failures aren't exceptional—they're routine. Using a mechanism designed for rare edge cases to handle common scenarios creates fragile architectures.

#### Explicit Error Handling

To build robust systems, make failure explicit. Treat errors as values, like any other data.

Using `Result[T, E]` (from the `kungfu` library):

```python
from kungfu import Result, Ok, Error

async def get_config() -> Result[dict, DBError]:
    try:
        data = await db.fetch("config")
        return Ok(data)
    except Exception as e:
        return Error(map_db_error(e))
```

Now the signature is complete. It says: *"I return either a dictionary OR a database error."*

The type checker sees both paths. Your IDE autocompletes both cases. No hidden surprises. You've made potential failures concrete and handleable. You can reason about the function by looking at its signature alone.

---

## Part III: Structured Error Handling

### Chapter 4: Structured Errors, Not Strings

#### Why String Errors Are Insufficient

A common mistake when adopting `Result` is returning `Error(str)`:

```python
# Bad: Can't be handled programmatically
return Error("Database connection failed after 3 attempts")
```

Strings are for humans, not programs. You can't react programmatically to "Connection failed" without fragile string parsing. You can't aggregate errors in metrics. You can't make automated decisions based on strings that might change between versions.

Errors should be **structured data** with a defined schema.

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class DBError(Exception):
    kind: Literal["connection", "timeout", "not_found", "unknown"]
    details: str
    retryable: bool
    service_id: str
```

Now error handling becomes precise. You match on structured signals, not strings:

```python
match result:
    case Error(e) if e.retryable:
        # Clear action: Retry
        ...
    case Error(e) if e.kind == "not_found":
        # Clear action: Return default
    ...
```

### Chapter 5: Four Levels of Abstraction

`combinators.py` organizes code into four progressive levels, each building on the previous:

#### Level 0: Raw Async
Standard Python. Exceptions everywhere. Optimistic types. Manual `asyncio` management. High cognitive load, frequent bugs.

#### Level 1: Result
Introduces `Result[T, E]`. Failures become data. Control flow is explicit. Replace `try/except` for business logic errors.

#### Level 2: Interp (Lazy Computation)
Introduces `LazyCoroResult[T, E]` (aliased as `LCR` or referred to as **Interp** in this guide). Separates **definition** from **execution**. An `Interp` is a computation blueprint that hasn't run yet. This laziness lets you modify operations before executing them.

#### Level 3: Flow (Declarative Composition)
The `flow()` API wraps blueprints into **Flow ASTs** to apply resilience policies (retry, timeout, fallback). Declarative syntax describes **what** resilience looks like, while `.then()` and `.map()` on the blueprints themselves handle the data flow.

---

## Part IV: Lazy Computation

### Chapter 6: Why Laziness Matters

#### The Limitation of Eager Execution

`Result` is powerful, but limited: it represents **completed** computations. Once you have a `Result`, it's immutable history—you can't add retry/timeout policies after the fact.

For resilience (retry, fallback, recovery), you need to represent **future** work: work *to be done*, not work *already done*.

#### The Blueprint Pattern (`Interp` / `LCR`)

`LazyCoroResult[T, E]` is a computation blueprint—think architectural plans versus a building:

*   **Eager (`Result`):** "Here's the finished building." (Too late to change if it's broken)
*   **Lazy (`Interp`):** "Here are the construction plans."

With plans, you can modify before building (retry, timeout, strategy changes). Execution happens only when you `await` the blueprint.

---

## Part V: Lifting External Code

### Chapter 7: Integrating Unsafe Functions

Most libraries throw exceptions. You can't change that, but you can control how they enter your system. This process is called **Lifting**: converting raw functions into honest, lazy operations.

#### Catching Exceptions: `L.call_catching`

When calling a function that might throw, lift it into an `Interp`:

```python
from combinators import lift as L

# db.fetch throws exceptions
# Lift it into the Result world
fetch_op = L.call_catching(
    db.fetch,
    on_error=map_db_error,
    key="config"
)
```

#### Making Your Own Functions Lazy: `@L.lifted`

If you write functions that return `Result`, make them lazy so they can compose in pipelines:

```python
@L.lifted
async def parse_config(raw: dict) -> Result[Config, ParseError]:
    # ... pure logic ...
    return Ok(config)

# Calling this returns a Blueprint (Interp), not the result
op = parse_config(data) 
```

---

## Part VI: Building Resilient Pipelines

### Chapter 8: The Flow API

Composition connects operations to build larger systems. Standard code uses `if` and `await`, creating deeply nested "Pyramid of Doom" structures that are hard to read and test.

`combinators.py` uses `flow()` for decorating blueprints with resilience policies, and `.then()` for chaining them:

```python
from combinators import flow, lift as L

# 1. Define the base operation
base_op = L.call_catching(db.fetch, on_error=map_db_error, key="user_123")

# 2. Wrap in flow() to add policies
resilient_fetch = (
    flow(base_op)
    .retry(times=3)
    .timeout(seconds=2.0)
    .compile() # Returns a new Interp
)

# 3. Chain with other operations using .then()
pipeline = (
    resilient_fetch
    .then(parse_user)
    .map(lambda u: u.name)
)
```

This reads like a specification. It describes **what** should happen, not **how**. Policy (retries, timeouts) is separated from logic (fetch, parse). This is declarative programming.

### Chapter 9: Smart Retry Logic

#### The Thundering Herd Problem

When a service crashes and 1,000 clients retry simultaneously, the service can't recover—the retries become a denial-of-service attack. This is the "thundering herd" problem.

`combinators.py` implements production-grade retry policies with **backoff** (give the server time to recover) and **jitter** (randomize retry timing to desynchronize clients).

```python
from combinators.control import RetryPolicy

# Best practice: Always use jitter in production
policy = RetryPolicy.exponential_jitter(initial=0.1, max_delay=5.0)

pipeline = flow(op).retry(policy=policy).compile()
```

### Chapter 10: Fallback Strategies

#### Graceful Degradation

Robust systems aren't "up" or "down"—they operate at varying levels of degradation. Use **fallback chains** to define degradation tiers:

```python
from combinators import fallback_chain

# Tier 1: Primary DB (Fast, Fresh)
# Tier 2: Replica DB (Slower, Stale)
# Tier 3: Cache (Instant, Very Stale)
# Tier 4: Defaults (Hardcoded, Static)

robust_fetch = fallback_chain(primary, replica, cache, L.pure(DEFAULT))
```

Even when primary infrastructure fails, users get something better than a 500 error. You maintain continuity of service.

---

## Part VII: LLM-Assisted Development

### Chapter 11: Understanding LLM Behavior

Modern development often involves Large Language Models. To use them effectively, understand what they are: **pattern prediction engines**, not intelligent collaborators.

LLMs don't invent new logic—they predict statistically likely patterns based on context and mirror the patterns they see in your codebase. If your patterns are inconsistent, the model will reproduce that inconsistency.

#### Why LLMs Hallucinate
LLMs hallucinate when the codebase gives them too much freedom. If your baseline uses ad-hoc `try/except` and manual `asyncio.gather`, the model sees **implicit complexity** and assumes "anything goes," producing plausible code that fails at the edges.

#### Constrained Prediction Behaves Better

With a **highly constrained grammar**, the model is pushed into a narrower space of valid programs:

**1. Error Correction Emerges**
When the LLM generates code that doesn't fit the combinator grammar, the type checker fails. The LLM sees the error and *self-corrects* without human intervention:

```
LLM generates: 
result = await fetch_data()  # Wrong: returns Result, not raw value

Type checker:
error: Cannot await Result[T, E]

LLM regenerates:
from combinators import flow, lift as L
result = await flow(L.call(fetch_data, ...)).compile()  # Correct
```

The grammar acts like a **constraint solver**: the model doesn't need deep understanding, it needs to fit a valid shape.

**2. Pattern Breeding**
When you write a new combinator pattern, the LLM notices it and starts applying it elsewhere:

```python
# You write once:
pipeline = flow(op).retry(times=3).timeout(seconds=2.0).compile()

# LLM sees this pattern and replicates it in similar contexts:
another_pipeline = flow(different_op).retry(times=5).timeout(seconds=1.0).compile()
```

The patterns **breed** through the codebase via LLM replication. Consistency emerges without enforcement.

**3. Cognitive Load Reduction**
When humans read LLM-generated combinator code, cognitive load is low because:
- Every operation follows the same grammar
- Type signatures are self-documenting
- Control flow is explicit

**LLMs have even lower cognitive load** here because there's less mutable state and less implicit control flow to track.

### Chapter 12: Why FP Works Well with LLMs

Functional programming and `combinators.py` fit LLM-assisted development because models perform best with **clear patterns**, **explicit context**, and **constrained grammars**.

#### 1. Strong Patterns Guide LLMs
`flow()`, `Result`, and `Interp` provide a strict grammar that acts as a **topology constraint**: generation becomes **solving for a valid graph** that satisfies the type system.

*   **Standard Python:** "Refactor these 50 lines of mixed logic and error handling." → LLM misses edge cases because the "rules" are implicit.
*   **Combinators:** "Add a retry policy to this operation." → LLM sees exactly where the `.retry()` combinator belongs. The API's grammar prevents it from inventing its own (buggy) retry loops.

#### 2. Local Reasoning Helps LLMs
In FP, function behavior is determined by input/output types. This **locality** is a superpower for LLMs: they don't need to track global state or complex class hierarchies. They only need to understand the immediate `Flow` or `Interp` context.

#### 3. Type Signatures as Implicit Prompts

**Type signatures act as specifications** that models often follow more reliably than prose.

```python
# This signature is a contract:
async def process_order(order_id: str) -> Interp[ProcessedOrder, OrderError]:
    ...
```

The LLM immediately knows:
- This function is **lazy** (returns `Interp`).
- It can fail with a **structured error** (`OrderError`).
- It must be `await`ed to get a `Result`.

#### 4. Self-Documenting Topologies

Consider this pipeline:

```python
from combinators import flow, lift as L

user_data = (
    flow(L.call(fetch_user, user_id))
    .retry(times=3)
    .timeout(seconds=2.0)
    .fallback(L.call(fetch_cached_user, user_id))
    .compile()
    .then(parse_user)
)
```

The **code structure is the documentation**: the topology is explicit, so modifying it is mostly a structural edit.

#### 5. Compositional Reasoning Emerges

Over time, LLMs exhibit **compositional reasoning**: they learn that complex requirements map to specific combinator combinations:
- "Resilience" → `.retry()` + `.timeout()`
- "Continuity" → `.fallback()` + `.recover()`
- "Backpressure" → `traverse_par(concurrency=N)`

### Chapter 13: Separating Infrastructure from Business Logic

The most common bug source in LLM-generated code is **Infrastructure Invention**. When an LLM doesn't see a clear way to handle retries or concurrency, it invents a way (usually a buggy one).

**Solution: The Combinator Bulkhead**
Infrastructure must be handled by the library. LLMs should never write `while True:` loops for retries or `asyncio.gather` for concurrency. They should *declare* these intents using combinators. This moves the "dangerous" logic from the LLM's imagination into a well-tested library.

### Chapter 14: Using LLM Reference Documentation

#### The `llm-reference.md` Document
`docs/llm-reference.md` serves as a constraint document for LLMs. Attach it to prompts to establish your system's "rules":
- "Use `Result`, not `try/except` for business logic"
- "Use `batch` or `traverse_par`, not loops for concurrency"

With these constraints, LLMs become effective at translating requirements into `Flow` pipelines and tend to preserve your architectural decisions.

#### LLM as Type-Driven Code Generator

With strong type constraints + reference docs, a few things become easier:

**1. Specification-to-Implementation Pipeline**
```
Human: "Fetch user, validate age >= 18, send welcome email. Handle all failures."

LLM generates:
```python
from combinators import flow, lift as L

pipeline = (
    flow(L.call(fetch_user, user_id))
    .retry(times=3)
    # NOTE: AgeError must be part of your error union (e.g. FetchError | AgeError).
    .ensure(lambda user: user.age >= 18, error=lambda user: AgeError(user.id))
    .compile()
    .then(send_welcome_email)
)
```

The model translated **intent** into **topology**.

**2. Type-Hole Filling**
```python
from combinators import flow, lift as L

fetch_data_op = L.call(fetch_data, ...)
pipeline = flow(fetch_data_op).compile().then(parse_data).map(format_output)
```

Type information helps fill gaps (the same way a human would).

**3. Error Type Propagation**

```python
# Human defines errors:
type FetchError = NetworkError | TimeoutError
type ParseError = ValidationError | SchemaError

# LLM generates a chained topology:
from combinators import flow, lift as L

def process() -> Interp[Output, FetchError | ParseError]:
    fetch_op = L.call(fetch, ...)
    return (
        flow(fetch_op).compile()
        .then(parse)
        .then(validate)
    )
```

With strong types, LLMs tend toward **topology-driven development**: they generate more often as **correctly connected graphs of effects**.

#### Training Through Feedback
When an LLM generates code that violates your patterns, explain why:
- "You used a try/except block. In this project, lift external calls with `L.call_catching`."
- "You used `asyncio.gather`. Use `batch` or `traverse_par` for better backpressure."

This feedback aligns the LLM's predictions with your system's conventions.

#### Codebase Evolution via LLM Refactoring

With declarative code, LLMs can perform large-scale refactors that would be risky with imperative code:

**Automatic Performance Optimization:**
```python
# LLM analyzes codebase, finds pattern:
for item in items:
    result = await process(item)  # Sequential!

# Refactors to:
results = await traverse_par(items, process, concurrency=10)
```

**Automatic Resilience Injection:**
```python
# LLM finds operations without timeouts
from combinators import flow, lift as L

fetch_op = L.call(fetch, ...)
result = await flow(fetch_op).compile()

# Adds timeouts based on SLA rules from docs
result = await flow(fetch_op).timeout(seconds=2.0).compile()
```

Over time, the LLM becomes a **vigilant refactoring agent**, applying learned patterns to improve consistency.

### Chapter 15: Safe Refactoring

In standard codebases, large refactors are risky, requiring extensive tests and manual review. In declarative codebases, refactoring often means **reorganizing the AST**.

Because `flow()` builds a data structure before execution, programs are data. LLMs can refactor by moving blocks within a `Flow`.

**Example:**
"Move the `timeout` from the whole pipeline to only the database fetch step."

In standard code: move `try/except` blocks, change variable scopes, risk introducing bugs.
In `combinators.py`: move the `.timeout()` call. Minimal bug risk because execution logic doesn't change.

---

## Part VIII: Structured Logging (Writer Monad)

### Chapter 16: Problems with Global Loggers

Traditional logging is a side effect—it happens "outside" your computation. This makes logs hard to test and hard to follow in async flows where 100 tasks interleave. Logs become a jumbled mess.

#### Logs as First-Class Data

The `Writer` monad (`LazyCoroResultWriter`) makes logs part of the result:

```python
from combinators import flow_writer, lift as L
from combinators.writer import Log, WriterResult
from kungfu import Ok

async def step_one(x: int) -> WriterResult[int, str, Log[str]]:
    # Return value AND a log entry
    return WriterResult(Ok(x + 1), Log.of("Incremented value"))

# Logs accumulate automatically during chaining
wr = await (
    flow_writer(L.writer.call(step_one, 41))
    .compile()
    .then(step_two)
)
print(list(wr.log)) # ["Incremented value", "Step two finished"]
```

### Chapter 17: Saga Pattern with Writer

In distributed systems, multi-service transactions aren't atomic. If flight booking succeeds but hotel booking fails, you must cancel the flight. This is the **Saga Pattern**.

#### Compensators as Logs

Instead of logging strings, log **Compensators** (blueprints to undo the work):

```python
from combinators import flow_writer, lift as L
from combinators._types import Interp
from combinators.writer import Log, WriterResult
from kungfu import Error, Ok

# A compensator is just a blueprint to undo an action
type Compensator = Interp[None, None]

async def book_flight(user_id: str) -> WriterResult[FlightId, BookingError, Log[Compensator]]:
    flight = await api.book_flight(user_id)
    # The "log entry" is the instruction for how to cancel this specific flight
    # NOTE: cancellation is modeled as a *blueprint* so it can be retried/timeouted if needed.
    cancel_op = L.call(api.cancel_flight, id=flight.id)
    return WriterResult(Ok(flight.id), Log.of(cancel_op))

# Saga execution: chaining automatically accumulates the 'undo' instructions
wr = await (
    flow_writer(L.writer.call(book_flight, "user_1"))
    .compile()
    .then(book_hotel)
)

match wr.result:
    case Ok(_):
        print("Success!")
    case Error(e):
        print(f"Failed: {e}. Rolling back...")
        # Rollback is just iterating through the accumulated log in reverse
        for compensator in reversed(wr.log):
            _ = await compensator
```

#### The Emergent Power of First-Class Compensation

1. **Compensation is Composable**: Compensators can themselves be wrapped in `.retry()` or `.timeout()`.
2. **Deterministic Rollback**: Because the log travels with the result, you always have the exact set of instructions needed to rollback *that specific* execution.
3. **Auditability**: The log is a data structure. You can inspect what *would* have been undone, or serialize it for later "time-travel" debugging.

#### Why the Writer Emerges as the Saga Solution

Using `LazyCoroResultWriter[T, E, Log[Compensator]]`, we transform distributed state management into **instruction accumulation**. The saga becomes a first-class value describing both forward progress and rollback.

1.  **Implicit Context**: You don't need a global transaction manager. The "transaction" state is just the `Writer` log.
2.  **Locality**: The logic for undoing an operation lives right next to the operation itself.
3.  **Compositionality**: If `process_A` is a saga and `process_B` is a saga, `process_A.then(process_B)` is automatically a larger saga with combined rollback logic.

#### Higher-Order Saga Patterns

While `flow_writer` provides the core mechanics, you can easily build ergonomic wrappers for your domain. The key is that since compensators are **data** (blueprints), your wrapper can:
- **Filter** which compensators to run based on error types.
- **Retry** individual compensation steps.
- **Log** exactly which steps were undone for compliance.

This transforms the Saga pattern from a "distributed systems headache" into a **provable property of your result type**.

---

## Part IX: Collection Processing

### Chapter 18: Traverse for Async Mapping

You have user IDs and need to fetch their profiles. Profiles might fail. This is the classic "map" problem with failure and async.

Standard approach:
```python
results = []
for id in ids:
    try:
        results.append(await fetch(id))
    except: ...
```

This is tedious and error-prone. Parallel execution? Concurrency limits? Hard to add.

The `combinators` approach:
```python
from combinators.collection.traverse import traverse

# Sequential: one by one
profiles_op = traverse(user_ids, fetch_profile_op)

# Parallel: concurrent with backpressure control
profiles_op_par = traverse_par(user_ids, fetch_profile_op, concurrency=10)
```

`traverse` converts `list[A]` and `A -> Interp[B]` into `Interp[list[B]]`. It handles result gathering and error propagation automatically.

---

## Part X: System Architecture Patterns

### Chapter 19: Visualizing System Structure

Think of systems as graphs:
- **Nodes**: functions (your logic)
- **Edges**: pipelines (data flow)
- **Boundaries**: services (system limits)

In standard code, connections are implicit (exceptions). In `combinators.py`, every connection is explicit—a clear graph edge.

#### Emergent Topology: Graph Theory Meets Production

When you build with combinators, your system's topology becomes **analyzable** and **transformable**:

**1. Structural analysis (advanced)**
`flow()` builds an AST (`Flow.expr`) and only runs after `.compile()`. That means the pipeline's shape is available *before execution* for tooling.

**2. Policy as higher-order functions**
Instead of rewriting the tree, standardize wrappers that add policies at the boundary:

```python
from combinators import TimeoutError, flow
from combinators._types import Interp

def resilient[T, E](op: Interp[T, E]) -> Interp[T, E | TimeoutError]:
    return flow(op).retry(times=3, delay_seconds=0.1).timeout(seconds=2.0).compile()
```

Your **code IS the documentation**: the topology lives in the chain.

#### Resilience Patterns as Graph Transforms

Resilient systems have topologies supporting redirection and isolation:

**Fallback (Alternative Path)**
```
     ┌──> Primary ──┐
Start┤             ├──> End
     └──> Fallback ┘
```
Graph property: Multiple paths from Start to End. If primary fails, traverse alternative edge.

**Race (Parallel Competition)**
```
     ┌──> Provider A ──┐
Start├──> Provider B ──┤──> End (first success)
     └──> Provider C ──┘
```
Graph property: All paths execute simultaneously. First successful path cancels others.

**Batch (Sequential Funnel)**
```
Items[1..N] ──> [Concurrency Limiter] ──> Process ──> Results
```
Graph property: Funnel restricts flow rate. Backpressure prevents overload.

**Chain (Sequential Dependencies)**
```
Fetch ──> Parse ──> Validate ──> Save
```
Graph property: Linear dependency. Each step needs previous step's output.

#### Emergent Patterns from Topology Composition

When you combine basic patterns, new behaviors emerge:

**Pattern: Hedged Race + Delay**
```python
hedged = race_ok(
    primary_op,
    flow(backup_op).delay(seconds=0.1).compile()  # Start backup after 100ms
)
```
Topology: Two paths, but second has delayed start. If primary is fast, backup never starts. If primary is slow, backup begins and may finish first.

**Emergent behavior:** Automatic adaptive latency optimization without explicit logic.

**Pattern: Fallback Chain with Increasing Staleness**
```python
data = fallback_chain(
    fetch_fresh,      # Latency: 100ms, freshness: 0s
    fetch_replica,    # Latency: 50ms, freshness: 5s  
    fetch_cache,      # Latency: 1ms, freshness: 60s
)
```
Topology: Linear fallback chain with decreasing latency, increasing staleness.

**Emergent behavior:** System automatically trades freshness for availability. No explicit freshness logic—it emerges from the topology.

**Pattern: Parallel Validation with Majority Vote**
```python
from collections.abc import Sequence

from combinators.selection import vote

async def majority(values: Sequence[bool]) -> bool:
    return sum(values) >= 2

result = await vote([validator_a, validator_b, validator_c], judge=majority)
```
Topology: Three parallel paths converge through a voting gate.

**Emergent behavior:** Byzantine fault tolerance. One validator can fail or be malicious—system still gets correct result.

#### Topology Algebra

Operations on topologies compose algebraically:

```python
# Identity: flow(f).compile() == f
identity = flow(op).compile()

# Composition: (f . g) . h == f . (g . h)
composed = flow(f).compile().then(g).then(h)
# Same as:
composed2 = flow(f).compile().then(lambda x: flow(g).compile().then(h))

# Retry is idempotent on idempotent operations:
safe = flow(idempotent_op).retry(times=3).retry(times=5).compile()
# Effectively: retry(times=3) because retrying a retry is redundant
```

**Emergent Property:** Your pipelines obey mathematical laws. You can reason about them algebraically, proving properties before runtime.

By visualizing architecture this way, you design for resilience before writing code. Resilience becomes a **provable property** of system structure.

---

## Part XI: Testing Strategies

### Chapter 20: Testing Lazy Operations

Async testing pain point: mocking time-dependent behavior (retries, timeouts). Testing 3 retries usually requires complex state-tracking mocks or brittle `asyncio` tricks.

In `combinators.py`, everything is an `Interp` (blueprint). Mock the *blueprint*, not the *execution*:

```python
# NOTE: AsyncMock returns Result values directly, so we lift it with L.call (not call_catching).
from unittest.mock import AsyncMock

from combinators import flow, lift as L
from kungfu import Error, Ok

# Mock that fails twice, then succeeds
mock_op = AsyncMock(side_effect=[Error("fail"), Error("fail"), Ok("success")])

# Lift mock into a blueprint
op = L.call(mock_op)

# Run through pipeline
pipeline = flow(op).retry(times=3).compile()
result = await pipeline

# Verify
assert result.is_ok()
assert mock_op.call_count == 3
```

Testing retries becomes straightforward: define the sequence of outcomes. This is **deterministic testing of nondeterministic systems**.

---

## Part XII: Shifting Perspective

### Chapter 21: From Implementation to Design

When you move from `if/try` to `flow()`, you shift from **implementation** (writing instructions) to **design** (defining systems).

Instead of event loop details or `try/except` syntax, you focus on **resilience architecture**:
- "What's the timeout policy for this dependency?"
- "Do we have a fallback for this critical path?"
- "How do we aggregate errors across batch requests?"

You're building structures that withstand failures. You're moving from "what it does" to "how well it does it."

---

## Part XIII: User-Centric Failure Handling

### Chapter 22: Failure from the User's View

When systems fail, it affects real people: someone waiting to buy a gift, check their balance, or send a message.

#### Graceful Degradation Tiers
Provide the **best available truth**, even during failures:
1.  **Fresh data:** Primary database (ideal)
2.  **Stale data:** Cache (acceptable)
3.  **Default state:** Fallback UI allowing continued use (minimal)

Using `fallback_chain` respects user time and intent. Fail softly instead of crashing hard. This is engineering with empathy.

---

## Part XIV: Distributed State Management

### Chapter 23: Beyond the Monolithic Database

Early computing assumed a "One True Database": put all data in one place, protect with transactions, achieve robustness.

This doesn't work in distributed systems.

In distributed systems, there's no single source of truth—only **cached views of the past**. By the time packets travel from server to database and back, state has changed. You're looking at history, not current reality.

#### Eventual Consistency
Three database replicas eventually agree (eventual consistency), but at any moment might disagree. This isn't a bug—it's information physics.

In `combinators.py`, treat every state fetch as **potentially outdated**:

```python
from combinators import race_ok, fallback_chain

# Query three replicas, take first success
# Don't wait for agreement—any replica's view is valid
op = race_ok(replica_a, replica_b, replica_c)
```

By accepting distributed state reality, we build **consistency-agnostic** systems instead of fighting physics.

### Chapter 24: Data Leases and Timeouts

Every data point should have an expiration—a **lease** on its validity.

When fetching a user's balance, you have a lease on that truth for, say, 10 seconds. After that, refetch.

In `combinators.py`, `timeout()` isn't just network safety—it's **lease enforcement**. It says: "If data doesn't arrive in time, it's no longer useful."

---

## Part XV: Observability as Data

### Chapter 25: Beyond Dashboard Metrics

Dashboards show high-level summaries—green or red lights. They tell you *that* something's wrong, rarely *why* or *how* the system responded.

#### Observability in the Type System
Standard programming bolts on observability via side effects (logs, spans, metrics). Better engineering makes observability a **result type property**.

Using the `Writer` monad, results carry their own explanations:

```python
# Result isn't just '42'
# It's '42' PLUS the trace showing it came from Cache-B
# after Replica-A timed out
result = await pipeline
print(result.log) # Context is right here
```

When failures occur, don't hunt through log aggregators. Check the `Result` object. Errors are structured, traces attached, context preserved. This is **self-contained observability**.

---

## Part XVI: The End-to-End Principle

### Chapter 26: Application-Level Reliability

The "End-to-End Principle": functions implemented at lower system layers (network, OS) have less value than the same functions at higher layers (application).

#### Why Application-Level Retry Matters
TCP retries lost packets. Service meshes (Istio) retry failed HTTP calls. Why do we also need `.retry()` in application code?

Lower layers **lack business context**:
- TCP doesn't know if operations are idempotent
- Istio doesn't know about fallback strategies
- Only the **application** understands failure costs

Using combinators, you implement end-to-end logic where there's sufficient context for correct decisions: your business layer. You take responsibility for system integrity instead of delegating to "smart" infrastructure.

---

## Part XVII: Design Philosophy

### Chapter 27: Complexity vs Complication

Reflect on code quality:

Standard code is **complicated**: tangled `if`, `try`, `while`, and global state. A knot only the original author can untie.

Code built with `combinators.py` is **complex** but **simple**. Many parts, deep interactions, but consistent fundamental laws. A structure, not a knot.

#### Engineering Discipline
The goal isn't code that works—it's structures that **can't break** (or break predictably).

Writing robust code is disciplined engineering: acknowledging we can't anticipate every failure, but building systems that handle unforeseen failures gracefully.

---

## Part XVIII: Advanced Concurrency Patterns

### Chapter 28: Race vs Gather

`asyncio.gather()` is powerful but dangerous—like juggling 100 balls. When one drops, tracking the rest becomes chaotic.

#### Race for Low Latency
`race_ok()` is the primary latency-reduction tool (competitive model):

```python
from combinators import race_ok

# Start three regional requests
# When first Ok arrives, cancel the others immediately
# No wasted resources
op = race_ok(us_east, us_west, eu_central)
```

#### Batch for Stability
`batch()` is the primary stability tool (cooperative model). Implements **backpressure**—the system's ability to say "can't handle more now":

```python
from combinators import batch

# Process 10,000 users in batches of 50
# Keeps event loop responsive
# Prevents memory exhaustion
results = await batch(user_ids, process_op, concurrency=50)
```

### Chapter 29: Application-Level Rate Limiting

Rate limiting usually happens at API gateways. But what about calling third-party APIs with strict quotas? You need self-imposed limits.

In `combinators.py`, rate limiting is a combinator:

```python
from combinators import flow, lift as L

# Pipeline never exceeds 5 calls/second
# regardless of invocation frequency
pipeline = (
    flow(L.call(api_call, ...))
    .rate_limit(max_per_second=5)
    .compile()
)
```

---

## Part XIX: Advanced Type Patterns

### Chapter 30: Generic Monadic Operations

`Interp[T, E]` is generic over `T` and `E`. But what if you want functions that work for *any* monad-like type?

The library uses the `Extract + Wrap` pattern:

```python
def retryM[M, T, E, Raw](
    interp: Callable[[], Coroutine[Any, Any, Raw]],
    *,
    extract: Callable[[Raw], Result[T, E]],
    wrap: Callable[[Callable[[], Coroutine[Any, Any, Raw]]], M],
    policy: RetryPolicy[E],
) -> M:
    ...
```

This applies resilience policies to `Writer`, `State`, or custom monads without rewriting logic for each. This is **higher-order resilience**.

### Chapter 31: Higher-Kinded Type Emulation

Python lacks `M[T]` (higher-kinded types). But we can emulate them using `TypeVar` and protocols, achieving Haskell/Scala expressiveness within Python's type system.

When you see `flow(...)`, that's a **type-safe composition boundary**. The library ensures that chaining with `.then()` matches output types to input types. Type mismatches show in your IDE before runtime.

---

## Part XX: Architectural Integration

### Chapter 32: Onion/Hexagonal Architecture

In "Onion" or "Hexagonal" architecture, core business logic sits at the center, infrastructure at the edges.

`combinators.py` integrates naturally:

1.  **Core:** Business logic as `Flow` blueprints
2.  **Gateways:** External calls as lifted `Interp` blueprints
3.  **App Service:** Composes core and gateways into pipelines

Core logic stays pure and testable (mock blueprints), while infrastructure concerns (retries, timeouts) are declared at boundaries.

### Chapter 33: Testing Complex Logic

How do you test systems with complex retry and fallback? Mock the **blueprint**:

```python
# Mock the blueprint, not the database driver
with patch("app.gateways.fetch_op") as mock:
    # First fetch fails, second succeeds
    mock.side_effect = [
        L.fail(DBError("timeout")),
        L.pure(UserData(id=1, name="John")),
    ]
    
    # Run app service
    result = await app_service.run(user_id=1)
    
    # Verify retry handling
    assert result.is_ok()
```

This tests **failure response**, not just happy paths.

---

## Part XXI: Code as Data

### Chapter 34: The AST Approach

A key functional programming insight: **code is data**.

When you write `flow()`, you're not executing—you're building a tree (AST), a static representation of intent.

#### Why This Matters
Data can be **transformed**:
- Write a "compiler" adding logging to every tree node
- Write an "optimizer" merging adjacent timeouts
- Write a "visualizer" converting `Flow` to Mermaid diagrams

Treating programs as data enables meta-programming. You're limited only by your imagination, not the Python interpreter.

---

## Appendix A: Common Patterns

### Pattern: SLA-Based Timeout with Fallback
Finish within time budget, or return cached value:
```python
from combinators import fallback_chain, flow

pipeline = fallback_chain(
    flow(fetch_fresh).timeout(seconds=0.2).compile(),
    fetch_cached,
)
```

### Pattern: Parallel Map-Reduce
Process items in parallel, then reduce:
```python
results_op = traverse_par(items, map_op, concurrency=10)
final_op = results_op.then(lambda results: fold(results, initial=0, handler=reduce_op))
```

### Pattern: Error-Specific Fallback
Switch fallback based on error type:
```python
from combinators import TimeoutError, fallback_with, flow, lift as L

primary_op = flow(primary).compile()
pipeline = fallback_with(
    primary_op,
    secondary=lambda e: fallback_cache if isinstance(e, TimeoutError) else L.fail(e),
)
```

### Pattern: Local Saga (Cleanup Accumulation)
```python
# Accumulate compensators as you go
saga = (
    flow_writer(step1) # logs Compensator1
    .compile()
    .then(step2)       # logs Compensator2
)

result = await saga
if result.is_error():
    # Run compensators in reverse
    for op in reversed(result.log.entries):
        await op()
```

### Pattern: Hedged Requests
Start backup if primary is slow:
```python
from combinators import flow, lift as L

request = flow(L.call(fetch, ...)).compile()
hedged = race_ok(
    request,
    flow(request).delay(seconds=0.1).compile()
)
```

### Pattern: Aggregate Validation Errors
Collect all errors, not just first:
```python
from combinators.collection.validate import validate
results = await validate(form_fields, parse_field_op)
# returns Error(list[ValidationError]) if any fail
```

### Pattern: Bulkhead (Resource Isolation)
Prevent one service exhausting connections:
```python
# Limit concurrent calls
resource_limited_op = (
    flow(dangerous_op)
    .rate_limit(max_per_second=10) # Acts as bulkhead
    .compile()
)
```

### Pattern: Sharded Processing
For large datasets, shard before parallel processing:
```python
from itertools import batched

from combinators.collection.traverse import traverse_par

async def process_large_list(items: list[int]) -> None:
    # Process shards sequentially, items inside each shard in parallel
    for shard in batched(items, 10_000):
        _ = await traverse_par(shard, process_op, concurrency=100)
```

### Pattern: Simple Circuit Breaker
Delay after failure:
```python
# Basic circuit breaker via delay
breaker_op = (
    flow(op)
    .retry(times=3, delay_seconds=5.0) # Wait 5s before retry
    .compile()
)
```

### Pattern: Score-Based Selection
Pick best result by score:
```python
from combinators.selection.best import best_of

# Pick result with highest confidence
best_ai_response = await (
    flow(gpt4_op)
    .best_of(n=3, key=lambda r: r.confidence)
    .compile()
)
```

### Pattern: Double-Check Consistency
Compare two sources, fail on mismatch:
```python
def double_check(op1, op2):
    return parallel(op1, op2).then(
        lambda res: L.pure(res[0]) if res[0] == res[1] else L.fail(ConsistencyError(res))
    )
```

### Pattern: Adaptive Timeout
Increase timeout per attempt:
```python
def adaptive_timeout(attempt: int) -> float:
    return 1.0 * (2 ** attempt)

# Requires custom combinator or flow loop
# Shows time as a variable
```

### Pattern: Health Monitoring Probe
Monitor pipeline health:
```python
pipeline = (
    flow(op)
    .bimap_tap(on_ok=lambda _: stats.mark_ok(), on_err=lambda _: stats.mark_err())
    .compile()
)
```

---

## Part XXII: Conclusion

### Chapter 35: Principled Failure Handling

We've covered systematic doubt, distributed systems, and type-level honesty. Error handling isn't a chore—it's core engineering.

Robust systems don't never fail. They **fail gracefully**:
- Clear, structured error messages
- Exhaust reasonable alternatives first
- Leave no corrupted state
- Attach complete execution traces

A `Result` containing an `Error` shouldn't cause frustration. It should provide satisfaction: you've built a structure accurately reflecting reality.

The universe is chaotic. Your logic doesn't have to be.

---

## Appendix B: Glossary

*   **Result:** Sum type representing Success (Ok) or Failure (Error)
*   **Interp / LazyCoroResult:** Computation blueprint (lazy, async)
*   **Flow:** Fluent API for building computation pipelines
*   **Lifting:** Converting standard functions into combinator context
*   **Combinator:** Higher-order function that modifies computations
*   **Writer:** Monad accumulating logs with results
*   **AST:** Abstract Syntax Tree (Flow pipeline representation)
*   **Structured Concurrency:** Treating concurrent task lifetimes like block scopes
*   **Invariant:** Condition remaining true across system states
*   **Monad:** Pattern for composing computations with context
*   **Saga Pattern:** Transaction sequence with compensating actions
*   **End-to-End Principle:** Application layer is where reliability is guaranteed

---

## Appendix C: FAQ

#### 1. Why not use `@retry` decorators?
Decorators are opaque—they hide failure costs. Combinators are explicit in type signatures and enable complex logic ("retry, then fallback").

#### 2. Is there performance overhead?
Minimal. AST building happens once at `.compile()` time. Runtime is just async function calls. `batch` and `race_ok` often outperform manual async code.

#### 3. Can I use this with sync code?
Yes. Use `L.pure` or `L.call_catching` to bring sync logic into async pipelines. For CPU-bound sync work, prefer `asyncio.to_thread()` (inside your own lifted function) to avoid blocking the event loop.

#### 4. How do I handle multiple error types?
Use Union types (`Error1 | Error2`). Type checkers (Pyright) force you to handle all cases in `match` statements.

#### 5. Why is laziness important?
Without laziness, you can't add retries/timeouts to started operations. Laziness gives control over future execution—programs become declarative intent, not just event sequences.

#### 6. Can I use this with FastAPI?
Yes. Compile flows in route handlers, await them, then match to convert `Result` to responses:

```python
@app.get("/user/{id}")
async def get_user(id: int):
    result = await user_pipeline(id)
    match result:
        case Ok(user): return user
        case Error(e): e.raise_http()
```

#### 7. How do I handle file streams?
Combinators are for discrete computations. Use async iterators for streams, but wrap chunks/processing steps in `Interp` for robust handling.

#### 8. Is this compatible with `anyio`?
Yes. Built on standard `asyncio`, works with `anyio` wrappers. Structured concurrency patterns align with `anyio` Task Groups.

#### 9. Why `kungfu.Result` instead of custom?
`kungfu` is optimized, type-safe, and follows Rust patterns. No need to reinvent well-tested implementations.

#### 10. What defines a combinator?
Combinators exist through composition—connecting to others. In isolation, they're incomplete. Their purpose is being part of larger systems.

---

## Final Thoughts

Closing this guide and returning to your IDE, remember: code reflects your relationship with reality. The world is messy, networks unreliable, futures uncertain.

Choosing robust patterns over easy ones isn't just better software—it's disciplined engineering. Build systems that withstand chaos.

Go build something that lasts.

---

*This guide evolves as we discover new patterns for managing complexity.*
