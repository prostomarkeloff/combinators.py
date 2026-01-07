# The Human Guide to Robust Systems

This guide will take you from the "Happy Path" mentality of standard Python to the "Robust Engineering" mentality of `combinators.py`.

---

## Chapter 1: The Lie of `await`

You are used to writing code like this:

```python
async def get_config() -> dict:
    return await db.fetch("config")
```

This code is optimistic. It assumes the database is up, the network is fast, and the data exists.
When those assumptions fail, your program crashes or enters an undefined state.

### The Explicit Boundary

The first step to recovery is admitting there is a problem. We change the return type.

```python
from kungfu import Result
from combinators import lift as L

# We lift the operation into a managed context
# explicit_fetch is now a "LazyCoroResult" (an Interp)
explicit_fetch = L.call(db.fetch, "config")
```

`explicit_fetch` is not a running task. It is a **blueprint**. It says: "If you run me, I will try to fetch config, and I promise to give you a `Result`."

---

## Chapter 2: The Two Tracks (Flow)

Now that we have a blueprint, we can start laying track.

We use `flow()` to start a pipeline. Think of `flow` as the entrance.

```python
from combinators import flow

pipeline = flow(explicit_fetch)
```

### Station 1: The Retry Loop

The first switch on our track is robustness. If the DB flickers, we shouldn't derail.

```python
from combinators.control import RetryPolicy

# This is data, not code.
policy = RetryPolicy.exponential_jitter(times=3)

pipeline = pipeline.retry(policy=policy)
```

**Visualizing the Track:**
```text
      [Start]
         |
         v
    [Try Operation] <-------+
         |                  |
    [Success?] -- No --> [Retry?] -- Yes --+
         |                  |
        Yes                 No
         |                  |
         v                  v
    [Success Track]    [Failure Track]
```

### Station 2: The Timeout Switch

Retrying forever is indistinguishable from hanging. We need a dead man's switch.

```python
pipeline = pipeline.timeout(seconds=2.0)
```

Notice what happened to the type.
Input: `Interp[Config, DBError]`
Output: `Interp[Config, DBError | TimeoutError]`

The compiler now knows that `TimeoutError` is a possibility. You cannot forget to handle it.

---

## Chapter 3: Making Illegal States Unrepresentable

Standard Python code often "validates" data like this:

```python
data = await fetch()
if not data['is_active']:
    raise InactiveError()
```

In `combinators.py`, we use the `.ensure()` combinator to **prove** validity on the Success Track.

```python
def check_active(cfg: dict) -> bool:
    return cfg.get('is_active', False)

pipeline = (
    pipeline
    .ensure(check_active, error=lambda c: ConfigError("Inactive"))
)
```

If this pipeline succeeds (returns `Ok`), you **mathematically know** the config is active. You don't need to check it again. The type `Result` carries this proof.

---

## Chapter 4: Handling the Sad Path

We've built the railway. Now we need to handle the trains that arrive on the Failure Track.

You have two choices:
1. **Recover:** Switch the train back to the Success Track.
2. **Crash (Safely):** Log the error and alert the user.

### Recovery (The Fallback)

```python
# If the DB fails, use the local cache
pipeline = pipeline.fallback(L.call(cache.get, "config"))
```

This is the "Sum Type" behavior (OR). Do A. If A fails, Do B.

### Safe Crash (Pattern Matching)

At the end of the world (your entry point), you **must** handle the result.

```python
result = await pipeline.compile()

match result:
    case Ok(config):
        # Success Track: We have active, valid config.
        start_app(config)
        
    case Error(DBError()):
        # Failure Track: The DB is dead.
        logger.critical("Database down")
        
    case Error(TimeoutError()):
        # Failure Track: The DB is too slow.
        logger.warning("Database timeout")
        
    case Error(ConfigError()):
        # Failure Track: Logic error.
        logger.error("Invalid config")
```

This is **exhaustive**. If you add a new error source (e.g., `AuthError`), `pyright` will scream at you until you handle it.

---

## Chapter 5: Advanced Engineering

### The "Race" (Parallelism)

Sometimes you want the fastest answer, not just any answer.

```python
from combinators import race_ok

# Race the primary and the replica.
# First one to cross the finish line on the Green Track wins.
fastest_db = race_ok(
    L.call(primary.get, "config"),
    L.call(replica.get, "config")
)
```

### The "Traverse" (Batching)

Processing a list of items? Don't write a `for` loop with `try/except`.

```python
from combinators import traverse
from combinators import lift as L

items = [1, 2, 3, 4]

# Process all items in parallel.
# If ANY fail, the whole train stops (Fail Fast).
# Returns Result[list[Processed], FirstError]
result = await traverse(items, process_func, concurrency=2)
```

---

## Summary

1.  **Lift** your operations into `Interp` (blueprints).
2.  **Flow** them through combinators (switches).
3.  **Compile** the pipeline.
4.  **Match** the final Result.

Stop hoping your code works. Start proving it does.
