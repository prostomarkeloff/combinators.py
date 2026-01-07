# The Philosophy

This library is not just a collection of utilities. It is an implementation of specific design principles drawn from functional programming and distributed systems theory.

It stands on three core pillars: **Explicit Proofs**, **The Two-Track Model**, and **System Boundaries**.

## 1. Explicit Proofs

The common advice is to "parse, don't validate." We apply this concept to **control flow**.

A boolean check is weak:
```python
if await is_server_up():
    # We *hope* it's still up
    data = await fetch()
```

A generic Exception is a GOTO:
```python
try:
    data = await fetch()
except Exception:
    # We lost the context. What failed?
    ...
```

In `combinators.py`, we don't "validate" that an operation succeeded. We return a `Result` type that **contains the proof of success** or the **evidence of failure**.

By "parsing" the unpredictable world of IO into a structured `Result[T, E]`, we make illegal states (like accessing data that failed to load) unrepresentable.

## 2. The Two-Track Model

Async programming often devolves into the "Arrow code" anti-pattern—deeply nested `try/except/else` blocks.

We visualize functional error handling as two parallel tracks.
Imagine a function as a piece of railway track.
- The **Success Track** is the happy path (Ok).
- The **Failure Track** is the sad path (Error).

### The Combinator Switch
Combinators are the switches between these tracks.

- `.map(f)`: Works on the Success Track. If successful, apply `f`. If failed, pass through.
- `.map_err(f)`: Works on the Failure Track. Transform the error.
- `.retry()`: A loopback switch. If failed, go back to the start. If successful, continue.
- `.recover()`: A crossover switch. If failed, switch to Success (using a default).
- `.ensure()`: A trapdoor. If successful but predicate fails, switch to Failure.

This visual model allows us to build complex pipelines without ever nesting our code.

## 3. System Boundaries

System Boundaries are the most critical part of design.

A system boundary is where your clean, perfect code meets the messy, chaotic outside world. Databases, APIs, file systems.
**Boundaries are where types lie.**

The standard library says `open()` returns a `File`. It lies. It might return `FileNotFoundError`, `PermissionError`, `IsADirectoryError`.

In this library, we enforce explicit boundaries.
- **Internal code:** Can use `T`.
- **Boundary code:** Must return `Result[T, E]`.

We use `Interp[T, E]` (Interpretation) to represent a boundary computation that *has not happened yet*. This allows us to wrap the boundary in protection (timeout, retry) *before* we cross it.

## 4. End-to-End Principle

Reliability cannot be purely solved at the infrastructure layer (TCP retries, Load Balancers). It must be solved at the application layer.

If a request fails, simply retrying it blindly is dangerous (see "Thundering Herd").
The **Application** must decide:
- Is this safe to retry? (Idempotency)
- Do we have a fallback? (Business logic)
- Is the data stale? (Timeouts)

`combinators.py` gives you the tools to express these **End-to-End** guarantees as clear, readable code, rather than hidden infrastructure config.

## Summary

1.  **Values over Actions**: An operation is a noun (`Interp`), not a verb.
2.  **Explicit over Implicit**: Errors are values, not control flow exceptions.
3.  **Composition over Extension**: Build pipelines, don't decorate functions.
4.  **Local Reasoning**: Understand the component without understanding the whole system.
