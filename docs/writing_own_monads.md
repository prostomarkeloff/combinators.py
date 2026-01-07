# Writing Your Own Monads

A guide to extending combinators.py with custom effect types.

---

## Why Write Your Own Monad?

You probably don't need to. `LazyCoroResult` handles most cases, and `LazyCoroResultWriter` covers logging.

But sometimes you need effects that don't fit:

- **State threading**: Pass mutable state through a computation without globals
- **Environment reading**: Inject configuration without passing it through every function
- **Multiple logs**: Track different kinds of logs (errors, metrics, traces) separately
- **Caching**: Memoize expensive computations automatically
- **Transactions**: Track database operations and commit/rollback atomically

If you're thinking "I wish I could track X alongside my Result," you probably want a custom monad.

---

## The Monad Laws (Don't Skip This)

Before writing a monad, understand what makes a monad a monad. Three laws:

### 1. Left Identity

```python
pure(x).then(f) == f(x)
```

Wrapping a value and immediately unwrapping it does nothing.

### 2. Right Identity

```python
m.then(pure) == m
```

Unwrapping and immediately wrapping does nothing.

### 3. Associativity

```python
m.then(f).then(g) == m.then(lambda x: f(x).then(g))
```

Order of nesting doesn't matter.

**Why these matter:** If your monad doesn't obey these laws, combinators will behave unpredictably. `retry` might retry too much. `fallback` might skip alternatives. The laws guarantee composability.

**Testing:** Write property tests for these laws. If they pass, your monad is safe to use with combinators.

---

## Anatomy of a Monad

Every monad in combinators.py has the same structure:

```python
class MyMonad[T, E]:
    """
    A lazy async computation that produces Result[T, E] plus extra effects.
    """
    
    def __init__(self, fn: Callable[[], Coroutine[Any, Any, RawType]]):
        """
        fn: A function that, when called, returns a coroutine.
        RawType: The raw type this monad wraps (e.g., Result[T, E], WriterResult[T, E, Log[W]]).
        """
        self._fn = fn
    
    async def __call__(self) -> RawType:
        """Execute the computation."""
        return await self._fn()
    
    def map(self, f: Callable[[T], U]) -> MyMonad[U, E]:
        """Transform success value."""
        async def run() -> RawType:
            raw = await self._fn()
            # Extract Result, map it, reconstruct RawType
            ...
        return MyMonad(run)
    
    def then(self, f: Callable[[T], MyMonad[U, E]]) -> MyMonad[U, E]:
        """Chain computations (monadic bind)."""
        async def run() -> RawType:
            raw = await self._fn()
            # Extract Result, if Ok call f and merge effects, reconstruct RawType
            ...
        return MyMonad(run)
```

**Key components:**

1. **Lazy**: Wraps a fn, not a value
2. **Async**: The fn returns a coroutine
3. **Raw type**: What the fn actually produces (Result, WriterResult, StateResult, etc.)
4. **map/then**: Core operations for composition

---

## Example: State Monad

Let's build a monad that threads state through a computation.

### The problem

You're building a parser. Each parsing step consumes some input and produces a result:

```python
def parse_int(input: str) -> Result[tuple[int, str], ParseError]:
    """Parse int from start of input, return (value, remaining_input)."""
    match = re.match(r'^(\d+)', input)
    if not match:
        return Error(ParseError("expected int"))
    value = int(match.group(1))
    remaining = input[len(match.group(1)):]
    return Ok((value, remaining))
```

Now compose multiple parsers:

```python
def parse_pair(input: str) -> Result[tuple[tuple[int, int], str], ParseError]:
    result1 = parse_int(input)
    if isinstance(result1, Error):
        return result1
    
    value1, remaining1 = result1.value
    
    result2 = parse_int(remaining1)
    if isinstance(result2, Error):
        return result2
    
    value2, remaining2 = result2.value
    
    return Ok(((value1, value2), remaining2))
```

**The pain:** Threading `remaining` through manually is tedious and error-prone.

### The solution: State monad

```python
from dataclasses import dataclass
from typing import Callable, Coroutine, Any
from kungfu import Result, Ok, Error

@dataclass
class StateResult[T, E, S]:
    """Result + state transformer."""
    result: Result[T, E]
    state_fn: Callable[[S], S]  # How to transform state

class LazyCoroResultState[T, E, S]:
    """
    A lazy async computation that produces Result[T, E] and transforms state S.
    """
    
    def __init__(
        self,
        fn: Callable[[], Coroutine[Any, Any, StateResult[T, E, S]]]
    ):
        self._fn = fn
    
    async def __call__(self) -> StateResult[T, E, S]:
        """Execute with default state transformer (identity)."""
        return await self._fn()
    
    async def run_with_state(self, initial_state: S) -> tuple[Result[T, E], S]:
        """Execute and apply state transformations."""
        state_result = await self._fn()
        final_state = state_result.state_fn(initial_state)
        return state_result.result, final_state
    
    def map(self, f: Callable[[T], U]) -> LazyCoroResultState[U, E, S]:
        """Transform success value (state unchanged)."""
        async def run() -> StateResult[U, E, S]:
            sr = await self._fn()
            return StateResult(
                result=sr.result.map(f),
                state_fn=sr.state_fn
            )
        return LazyCoroResultState(run)
    
    def then(
        self,
        f: Callable[[T], LazyCoroResultState[U, E, S]]
    ) -> LazyCoroResultState[U, E, S]:
        """Chain computations, threading state."""
        async def run() -> StateResult[U, E, S]:
            sr1 = await self._fn()
            
            match sr1.result:
                case Error() as e:
                    # Propagate error, keep state transformer
                    return StateResult(result=e, state_fn=sr1.state_fn)
                
                case Ok(value):
                    # Run next computation
                    next_computation = f(value)
                    sr2 = await next_computation()
                    
                    # Compose state transformers
                    def composed_state_fn(s: S) -> S:
                        intermediate = sr1.state_fn(s)
                        return sr2.state_fn(intermediate)
                    
                    return StateResult(
                        result=sr2.result,
                        state_fn=composed_state_fn
                    )
        
        return LazyCoroResultState(run)
    
    # State-specific operations
    
    @staticmethod
    def get() -> LazyCoroResultState[S, Never, S]:
        """Get current state."""
        async def run() -> StateResult[S, Never, S]:
            def state_fn(s: S) -> S:
                return s
            return StateResult(result=Ok(s), state_fn=state_fn)
        return LazyCoroResultState(run)
    
    @staticmethod
    def put(new_state: S) -> LazyCoroResultState[None, Never, S]:
        """Set state."""
        async def run() -> StateResult[None, Never, S]:
            def state_fn(_: S) -> S:
                return new_state
            return StateResult(result=Ok(None), state_fn=state_fn)
        return LazyCoroResultState(run)
    
    @staticmethod
    def modify(f: Callable[[S], S]) -> LazyCoroResultState[None, Never, S]:
        """Modify state."""
        async def run() -> StateResult[None, Never, S]:
            return StateResult(result=Ok(None), state_fn=f)
        return LazyCoroResultState(run)
```

### Using the State monad

Now the parser is clean:

```python
from combinators import lift as L

async def parse_int_impl() -> Result[int, ParseError]:
    """Parse int from current state."""
    state = await LazyCoroResultState.get()
    match = re.match(r'^(\d+)', state)
    if not match:
        return Error(ParseError("expected int"))
    
    value = int(match.group(1))
    remaining = state[len(match.group(1)):]
    
    await LazyCoroResultState.put(remaining)
    return Ok(value)

# Lift to State monad
parse_int = L.call(parse_int_impl)

# Compose parsers
def parse_pair() -> LazyCoroResultState[tuple[int, int], ParseError, str]:
    return (
        parse_int
        .then(lambda v1: parse_int.map(lambda v2: (v1, v2)))
    )

# Run
result, final_state = await parse_pair().run_with_state("123 456")
# result: Ok((123, 456))
# final_state: " 456"
```

**What we gained:** State threading is automatic. No more manually passing `remaining` through every function.

---

## Making It Work With Combinators

Your custom monad needs extract + wrap functions to work with combinators.

### Extract function

Extracts `Result[T, E]` from your monad's raw type:

```python
def extract_state_result[T, E, S](sr: StateResult[T, E, S]) -> Result[T, E]:
    """Extract Result from StateResult."""
    return sr.result
```

### Wrap function

Constructs your monad from a fn:

```python
def wrap_lazy_coro_result_state[T, E, S](
    fn: Callable[[], Coroutine[Any, Any, StateResult[T, E, S]]]
) -> LazyCoroResultState[T, E, S]:
    """Wrap fn in LazyCoroResultState."""
    return LazyCoroResultState(fn)
```

### Using generic combinators

Now you can use any combinator with your monad:

```python
from combinators.control.retry import retryM
from combinators.control import RetryPolicy

def retry_state[T, E, S](
    computation: LazyCoroResultState[T, E, S],
    *,
    policy: RetryPolicy[E]
) -> LazyCoroResultState[T, E, S]:
    """Retry a State computation."""
    return retryM(
        computation,
        extract=extract_state_result,
        wrap=wrap_lazy_coro_result_state,
        policy=policy
    )

# Use it
parse_with_retry = retry_state(
    parse_int,
    policy=RetryPolicy.fixed(times=3, delay_seconds=0.1)
)
```

**Key insight:** Generic combinators (`*M` functions) work with any monad if you provide extract + wrap. You get retry, timeout, fallback, race, etc. for free.

---

## Example: Reader Monad

The Reader monad threads read-only configuration through a computation.

### The problem

You have functions that need configuration:

```python
@dataclass
class Config:
    api_url: str
    timeout: float
    retry_count: int

async def fetch_user(user_id: int, config: Config) -> Result[User, APIError]:
    # Use config.api_url, config.timeout
    ...

async def fetch_posts(user_id: int, config: Config) -> Result[list[Post], APIError]:
    # Use config.api_url
    ...

async def fetch_user_with_posts(user_id: int, config: Config) -> Result[UserWithPosts, APIError]:
    user_result = await fetch_user(user_id, config)
    if isinstance(user_result, Error):
        return user_result
    
    posts_result = await fetch_posts(user_id, config)
    if isinstance(posts_result, Error):
        return posts_result
    
    return Ok(UserWithPosts(user=user_result.value, posts=posts_result.value))
```

**The pain:** Passing `config` through every function is tedious.

### The solution: Reader monad

```python
@dataclass
class ReaderResult[T, E, R]:
    """Result + environment reader."""
    runner: Callable[[R], Coroutine[Any, Any, Result[T, E]]]

class LazyCoroResultReader[T, E, R]:
    """
    A lazy async computation that reads environment R and produces Result[T, E].
    """
    
    def __init__(
        self,
        fn: Callable[[], Coroutine[Any, Any, ReaderResult[T, E, R]]]
    ):
        self._fn = fn
    
    async def run_with_env(self, env: R) -> Result[T, E]:
        """Execute with environment."""
        reader_result = await self._fn()
        return await reader_result.runner(env)
    
    def map(self, f: Callable[[T], U]) -> LazyCoroResultReader[U, E, R]:
        async def run() -> ReaderResult[U, E, R]:
            rr = await self._fn()
            
            async def runner(env: R) -> Result[U, E]:
                result = await rr.runner(env)
                return result.map(f)
            
            return ReaderResult(runner=runner)
        
        return LazyCoroResultReader(run)
    
    def then(
        self,
        f: Callable[[T], LazyCoroResultReader[U, E, R]]
    ) -> LazyCoroResultReader[U, E, R]:
        async def run() -> ReaderResult[U, E, R]:
            rr1 = await self._fn()
            
            async def runner(env: R) -> Result[U, E]:
                result1 = await rr1.runner(env)
                
                match result1:
                    case Error() as e:
                        return e
                    case Ok(value):
                        next_computation = f(value)
                        rr2 = await next_computation()
                        return await rr2.runner(env)
            
            return ReaderResult(runner=runner)
        
        return LazyCoroResultReader(run)
    
    @staticmethod
    def ask() -> LazyCoroResultReader[R, Never, R]:
        """Get environment."""
        async def run() -> ReaderResult[R, Never, R]:
            async def runner(env: R) -> Result[R, Never]:
                return Ok(env)
            return ReaderResult(runner=runner)
        
        return LazyCoroResultReader(run)
    
    @staticmethod
    def asks(f: Callable[[R], T]) -> LazyCoroResultReader[T, Never, R]:
        """Get part of environment."""
        async def run() -> ReaderResult[T, Never, R]:
            async def runner(env: R) -> Result[T, Never]:
                return Ok(f(env))
            return ReaderResult(runner=runner)
        
        return LazyCoroResultReader(run)
```

### Using the Reader monad

```python
async def fetch_user_impl(user_id: int) -> LazyCoroResultReader[User, APIError, Config]:
    config = await LazyCoroResultReader.ask()
    # Use config
    result = await api.get(f"{config.api_url}/users/{user_id}")
    return L.from_result(result)

async def fetch_posts_impl(user_id: int) -> LazyCoroResultReader[list[Post], APIError, Config]:
    api_url = await LazyCoroResultReader.asks(lambda c: c.api_url)
    # Use api_url
    ...

def fetch_user_with_posts(user_id: int) -> LazyCoroResultReader[UserWithPosts, APIError, Config]:
    return (
        fetch_user_impl(user_id)
        .then(lambda user: 
            fetch_posts_impl(user_id)
            .map(lambda posts: UserWithPosts(user=user, posts=posts))
        )
    )

# Run
config = Config(api_url="https://api.example.com", timeout=5.0, retry_count=3)
result = await fetch_user_with_posts(42).run_with_env(config)
```

**What we gained:** No more passing `config` explicitly. It's implicitly available via `ask()`.

---

## Example: Custom Error Accumulation

You want to collect multiple errors without short-circuiting.

```python
@dataclass
class ValidationResult[T, E]:
    """Either success with value, or failure with accumulated errors."""
    value: T | None
    errors: list[E]
    
    @property
    def is_ok(self) -> bool:
        return len(self.errors) == 0
    
    def to_result(self) -> Result[T, list[E]]:
        if self.is_ok:
            return Ok(self.value)
        return Error(self.errors)

class LazyCoroValidation[T, E]:
    """
    A computation that accumulates errors instead of short-circuiting.
    """
    
    def __init__(
        self,
        fn: Callable[[], Coroutine[Any, Any, ValidationResult[T, E]]]
    ):
        self._fn = fn
    
    async def __call__(self) -> ValidationResult[T, E]:
        return await self._fn()
    
    def map(self, f: Callable[[T], U]) -> LazyCoroValidation[U, E]:
        async def run() -> ValidationResult[U, E]:
            vr = await self._fn()
            if vr.is_ok:
                return ValidationResult(value=f(vr.value), errors=[])
            return ValidationResult(value=None, errors=vr.errors)
        return LazyCoroValidation(run)
    
    def then(
        self,
        f: Callable[[T], LazyCoroValidation[U, E]]
    ) -> LazyCoroValidation[U, E]:
        async def run() -> ValidationResult[U, E]:
            vr1 = await self._fn()
            
            if not vr1.is_ok:
                return ValidationResult(value=None, errors=vr1.errors)
            
            next_computation = f(vr1.value)
            vr2 = await next_computation()
            
            # Combine errors
            all_errors = vr1.errors + vr2.errors
            
            if vr2.is_ok:
                return ValidationResult(value=vr2.value, errors=all_errors)
            return ValidationResult(value=None, errors=all_errors)
        
        return LazyCoroValidation(run)
    
    def and_also(
        self,
        other: LazyCoroValidation[U, E]
    ) -> LazyCoroValidation[tuple[T, U], E]:
        """
        Run both validations, accumulate all errors.
        Success only if both succeed.
        """
        async def run() -> ValidationResult[tuple[T, U], E]:
            vr1 = await self._fn()
            vr2 = await other()
            
            all_errors = vr1.errors + vr2.errors
            
            if vr1.is_ok and vr2.is_ok:
                return ValidationResult(
                    value=(vr1.value, vr2.value),
                    errors=[]
                )
            
            return ValidationResult(value=None, errors=all_errors)
        
        return LazyCoroValidation(run)
```

### Using Validation

```python
def validate_email(email: str) -> LazyCoroValidation[str, str]:
    async def run() -> ValidationResult[str, str]:
        if "@" not in email:
            return ValidationResult(value=None, errors=["Email must contain @"])
        if len(email) < 5:
            return ValidationResult(value=None, errors=["Email too short"])
        return ValidationResult(value=email, errors=[])
    return LazyCoroValidation(run)

def validate_password(password: str) -> LazyCoroValidation[str, str]:
    async def run() -> ValidationResult[str, str]:
        errors = []
        if len(password) < 8:
            errors.append("Password must be at least 8 characters")
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain a number")
        if not any(c.isupper() for c in password):
            errors.append("Password must contain uppercase letter")
        
        if errors:
            return ValidationResult(value=None, errors=errors)
        return ValidationResult(value=password, errors=[])
    return LazyCoroValidation(run)

# Validate both, collect ALL errors
validation = validate_email("bad").and_also(validate_password("weak"))
result = await validation()

# result.errors might be:
# ["Email must contain @", "Password must be at least 8 characters", 
#  "Password must contain a number", "Password must contain uppercase letter"]
```

**Key difference from Result:** Result short-circuits on first error. Validation accumulates all errors.

---

## Writing Custom Combinators

Once you have a monad, you probably want custom combinators for it.

### Pattern: Transform the raw type

```python
def validate_state[T, E, S](
    computation: LazyCoroResultState[T, E, S],
    *,
    predicate: Callable[[T], bool],
    error: Callable[[T], E]
) -> LazyCoroResultState[T, E, S]:
    """Validate result, fail if predicate returns False."""
    async def run() -> StateResult[T, E, S]:
        sr = await computation()
        
        match sr.result:
            case Ok(value):
                if not predicate(value):
                    return StateResult(
                        result=Error(error(value)),
                        state_fn=sr.state_fn
                    )
                return sr
            case Error():
                return sr
    
    return LazyCoroResultState(run)
```

### Pattern: Combine multiple computations

```python
def sequence_state[T, E, S](
    computations: list[LazyCoroResultState[T, E, S]]
) -> LazyCoroResultState[list[T], E, S]:
    """Run computations sequentially, collect results, thread state."""
    async def run() -> StateResult[list[T], E, S]:
        results = []
        state_fns = []
        
        for comp in computations:
            sr = await comp()
            
            match sr.result:
                case Error() as e:
                    # Compose state functions up to this point
                    def composed(s: S) -> S:
                        for fn in state_fns:
                            s = fn(s)
                        return sr.state_fn(s)
                    
                    return StateResult(result=e, state_fn=composed)
                
                case Ok(value):
                    results.append(value)
                    state_fns.append(sr.state_fn)
        
        # All succeeded - compose all state functions
        def final_state_fn(s: S) -> S:
            for fn in state_fns:
                s = fn(s)
            return s
        
        return StateResult(result=Ok(results), state_fn=final_state_fn)
    
    return LazyCoroResultState(run)
```

### Pattern: Use generic combinator

For combinators that only care about Result, use the generic version:

```python
def retry_state[T, E, S](
    computation: LazyCoroResultState[T, E, S],
    *,
    policy: RetryPolicy[E]
) -> LazyCoroResultState[T, E, S]:
    """Retry a State computation."""
    return retryM(
        computation,
        extract=extract_state_result,
        wrap=wrap_lazy_coro_result_state,
        policy=policy
    )

def timeout_state[T, E, S](
    computation: LazyCoroResultState[T, E, S],
    *,
    seconds: float
) -> LazyCoroResultState[T, E | TimeoutError, S]:
    """Add timeout to State computation."""
    return timeoutM(
        computation,
        extract=extract_state_result,
        wrap=wrap_lazy_coro_result_state,
        seconds=seconds
    )
```

**Rule of thumb:** If the combinator only transforms Result and doesn't care about the monad's extra effects, use the generic version.

---

## Testing Your Monad

### Test monad laws

```python
async def test_left_identity():
    """pure(x).then(f) == f(x)"""
    x = 42
    
    def f(n: int) -> LazyCoroResultState[int, str, str]:
        return LazyCoroResultState.pure(n * 2)
    
    # Left side: pure(x).then(f)
    left = LazyCoroResultState.pure(x).then(f)
    left_result, left_state = await left.run_with_state("initial")
    
    # Right side: f(x)
    right = f(x)
    right_result, right_state = await right.run_with_state("initial")
    
    assert left_result == right_result
    assert left_state == right_state

async def test_right_identity():
    """m.then(pure) == m"""
    m = LazyCoroResultState.pure(42)
    
    left = m.then(LazyCoroResultState.pure)
    left_result, left_state = await left.run_with_state("initial")
    
    right = m
    right_result, right_state = await right.run_with_state("initial")
    
    assert left_result == right_result
    assert left_state == right_state

async def test_associativity():
    """m.then(f).then(g) == m.then(lambda x: f(x).then(g))"""
    m = LazyCoroResultState.pure(1)
    
    def f(n: int) -> LazyCoroResultState[int, str, str]:
        return LazyCoroResultState.pure(n + 1)
    
    def g(n: int) -> LazyCoroResultState[int, str, str]:
        return LazyCoroResultState.pure(n * 2)
    
    # Left: m.then(f).then(g)
    left = m.then(f).then(g)
    left_result, _ = await left.run_with_state("initial")
    
    # Right: m.then(lambda x: f(x).then(g))
    right = m.then(lambda x: f(x).then(g))
    right_result, _ = await right.run_with_state("initial")
    
    assert left_result == right_result
```

### Test extract + wrap

```python
async def test_extract_preserves_result():
    """extract should get Result from raw type."""
    sr = StateResult(result=Ok(42), state_fn=lambda s: s)
    result = extract_state_result(sr)
    assert result == Ok(42)

async def test_wrap_creates_monad():
    """wrap should create monad from fn."""
    async def test_fn() -> StateResult[int, str, str]:
        return StateResult(result=Ok(42), state_fn=lambda s: s)
    
    monad = wrap_lazy_coro_result_state(test_fn)
    assert isinstance(monad, LazyCoroResultState)
    
    result, _ = await monad.run_with_state("initial")
    assert result == Ok(42)
```

### Test custom combinators work

```python
async def test_retry_state_works():
    """retry_state should retry failed computations."""
    attempts = 0
    
    async def flaky() -> StateResult[int, str, str]:
        nonlocal attempts
        attempts += 1
        
        if attempts < 3:
            return StateResult(
                result=Error("transient"),
                state_fn=lambda s: s + "."
            )
        
        return StateResult(
            result=Ok(42),
            state_fn=lambda s: s + "!"
        )
    
    computation = LazyCoroResultState(flaky)
    retried = retry_state(
        computation,
        policy=RetryPolicy.fixed(times=3, delay_seconds=0.0)
    )
    
    result, final_state = await retried.run_with_state("start")
    
    assert result == Ok(42)
    assert attempts == 3
    assert final_state == "start!"  # Only successful attempt's state applied
```

---

## Common Pitfalls

### Pitfall 1: Not composing effects correctly

```python
# ❌ Wrong: state transformers aren't composed
def then(self, f):
    async def run():
        sr1 = await self._fn()
        if sr1.result.is_error():
            return sr1
        
        next_comp = f(sr1.result.value)
        sr2 = await next_comp()
        
        # Missing: compose state_fn from sr1 and sr2
        return sr2  # Wrong! This loses sr1's state changes
    
    return LazyCoroResultState(run)

# ✅ Correct: compose state transformers
def then(self, f):
    async def run():
        sr1 = await self._fn()
        if sr1.result.is_error():
            return sr1
        
        next_comp = f(sr1.result.value)
        sr2 = await next_comp()
        
        # Compose state transformers
        def composed_state_fn(s):
            intermediate = sr1.state_fn(s)
            return sr2.state_fn(intermediate)
        
        return StateResult(result=sr2.result, state_fn=composed_state_fn)
    
    return LazyCoroResultState(run)
```

### Pitfall 2: Forgetting laziness

```python
# ❌ Wrong: executes immediately
def my_combinator(computation):
    result = await computation()  # Executes now!
    # ... transform result
    return LazyCoroResult(lambda: Ok(transformed))

# ✅ Correct: wrap in fn
def my_combinator(computation):
    async def run():
        result = await computation()  # Executes only when run() is called
        # ... transform result
        return Ok(transformed)
    
    return LazyCoroResult(run)
```

### Pitfall 3: Not handling errors in both paths

```python
# ❌ Wrong: doesn't preserve errors properly
def map(self, f):
    async def run():
        sr = await self._fn()
        # Assumes result is always Ok
        new_value = f(sr.result.value)  # Crashes on Error!
        return StateResult(result=Ok(new_value), state_fn=sr.state_fn)
    
    return LazyCoroResultState(run)

# ✅ Correct: handle both Ok and Error
def map(self, f):
    async def run():
        sr = await self._fn()
        return StateResult(
            result=sr.result.map(f),  # map handles both Ok and Error
            state_fn=sr.state_fn
        )
    
    return LazyCoroResultState(run)
```

---

## Performance Considerations

### Fn overhead

Each combinator adds a function call. For 10 combinators, that's 10 function calls per execution.

**Usually fine:** Modern Python is fast enough. Unless you're in a hot loop executing millions of times per second, don't worry.

**If it matters:** Compile your pipeline once, reuse the compiled version:

```python
# ❌ Slow: compiles on every call
def fetch_user(user_id: int):
    return (
        flow(L.call(api.get, f"/users/{user_id}"))
        .retry(times=3)
        .timeout(seconds=5.0)
        .compile()
    )

# ✅ Fast: compile once
_fetch_user_pipeline = (
    flow(L.call(api.get, "/users/{user_id}"))
    .retry(times=3)
    .timeout(seconds=5.0)
    .compile()
)

def fetch_user(user_id: int):
    return _fetch_user_pipeline
```

### State accumulation

If your monad accumulates unbounded data (logs, state history), it can grow large:

```python
# ❌ Potential memory issue
writer = flow_writer(L.writer.call(generate_text, prompt))
for _ in range(1000):
    writer = writer.with_log(f"iteration_{_}")  # Accumulates 1000 log entries
```

**Solution:** Provide a way to clear accumulated data:

```python
# ✅ Better
writer = writer.censor(lambda log: Log.of(*log.entries[-10:]))  # Keep only last 10
```

---

## When to Stop

Custom monads are powerful, but they add complexity. Stop when:

1. **Existing monads work**: Can you solve it with LazyCoroResult or Writer? Use those.

2. **The pattern doesn't repeat**: If you only need the effect once, just write it directly. Don't abstract.

3. **The team doesn't understand it**: If explaining your monad takes more than 5 minutes, it might be too complex.

4. **The laws don't hold**: If you can't make the monad laws work, you don't have a monad. Use a different pattern.

---

## Further Reading

### Theory

- **"Monads for Functional Programming"** by Philip Wadler - The original paper
- **"Monad Transformers Step by Step"** - Combining multiple effects
- **Haskell documentation** - The gold standard for monad design

### Practice

- `combinators.py` [source code](../combinators/) - See how Writer is implemented
- [Examples](../examples/) - Real code using custom effects
- [Human Guide](./human-guide.md) - Foundations

---

## Conclusion

Writing your own monad isn't magic. It's:

1. Define a raw type (like StateResult, ReaderResult)
2. Wrap it in a lazy async container
3. Implement map and then
4. Test the monad laws
5. Write extract + wrap functions
6. Enjoy free combinators

Start simple. The State monad is ~100 lines. The Reader monad is ~80 lines. You don't need a PhD to write useful abstractions.

The hardest part isn't the code—it's knowing when to stop.

