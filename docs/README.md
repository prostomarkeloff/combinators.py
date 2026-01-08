# Combinators.py Documentation

This directory contains comprehensive documentation for the `combinators.py` library, a functional programming library for building resilient async pipelines in Python.

## 📚 Documentation Index

### Quick Navigation

| I want to... | Go to |
|-------------|-------|
| **Learn the library** | [Human Guide](#for-humans-narrative-guide) |
| **Generate code with AI** | [LLM Reference](#for-llms-reference-documentation) |
| **Understand LLM + Combinators synergy** | [The Emergence](#the-emergence-llm-patterns) |
| **See examples** | [Examples](#examples) |
| **Understand a combinator** | [API Reference](./llm-reference.md#api-reference) |
| **Write a custom monad** | [Writing Your Own Monads](#writing-your-own-monads) |
| **Learn patterns** | [Common Patterns](./llm-reference.md#common-patterns) |

---

## Documentation Versions

### For Humans: Narrative Guide

**[`human-guide.md`](./human-guide.md)** - A comprehensive narrative-style guide that explains:

- ✨ Core concepts and philosophy
- 🏗️ The monadic foundation
- 🔧 All combinators with examples
- 📐 Patterns and best practices
- 🌍 Real-world use cases
- 🚀 Advanced topics
- 📊 Testing strategies
- 🔄 Architectural integration

**Use this when:**
- 📖 Learning the library from scratch
- 🤔 Understanding concepts and patterns
- 💡 Looking for examples and use cases
- ✅ Exploring best practices
- 🔍 Designing resilient systems

### For LLMs: Reference Documentation

**[`llm-reference.md`](./llm-reference.md)** - A structured, maximally concise reference for code generation and refactoring:

- 📋 Complete API reference with signatures
- 🔀 Type transformations
- 🎯 Common patterns
- ⚙️ Implementation notes
- 🤖 Code generation guidelines
- 🧪 Testing patterns
- ⚡ Performance characteristics

**Use this when:**
- 🤖 Generating code with AI assistants
- 🔧 Refactoring existing code
- 🔍 Looking up function signatures
- 📊 Understanding type transformations
- 🛠️ Implementing custom combinators

### The Emergence: LLM Patterns

**[`llm_emerges.md`](./llm_emerges.md)** - A deep exploration of emergent behaviors when LLMs work with combinators:

- 🧠 The Constraint Hypothesis: stricter grammars → smarter models
- 🔄 Self-correction via type errors
- 🧬 Pattern breeding through the codebase
- 🏗️ Topology-driven development
- 🛡️ The Bulkhead Principle: separating LLM-controlled from infrastructure
- ✨ Observed emergent behaviors

**Use this when:**
- 🤔 Curious why FP + LLMs work so well together
- 🧪 Designing systems for AI-assisted development
- 💡 Understanding emergent patterns from constraints
- 🎯 Building LLM-friendly codebases

### Philosophy

**[`philosophy.md`](./philosophy.md)** - The foundational design principles:

- 🔐 Explicit Proofs: parse control flow, not just data
- 🛤️ The Two-Track Model: success and failure as parallel railways
- 🚧 System Boundaries: where types lie, where honesty matters
- 🔚 End-to-End Principle: application-level reliability

**Use this when:**
- 🤔 Understanding "why" behind design decisions
- 📖 Learning the theory that informs the practice
- 💡 Explaining combinators to others

### Writing Your Own Monads

**[`writing_own_monads.md`](./writing_own_monads.md)** - A guide to extending combinators.py:

- 📜 The monad laws (and why they matter)
- 🔄 State monad: threading mutable state without globals
- 📚 Reader monad: injecting configuration implicitly
- ✅ Validation monad: accumulating errors instead of short-circuiting
- 🔧 Making custom monads work with combinators via extract + wrap

**Use this when:**
- 🧪 You need effects that don't fit LazyCoroResult or Writer
- 🏗️ Building domain-specific effect systems
- 📖 Understanding how the library works internally

## 🚀 Quick Start

### Installation

```bash
uv add git+https://github.com/prostomarkeloff/combinators.py.git
```

**Requirements:** Python 3.13+, [kungfu](https://github.com/timoniq/kungfu)

### Basic Example

```python
from combinators import flow, lift as L
from kungfu import Ok, Error

# Define pure function
async def fetch_user(user_id: int) -> Result[User, APIError]:
    return await api.get(f"/users/{user_id}")

# Compose effects using lift namespace
pipeline = (
    flow(L.call(fetch_user, 42))
    .retry(times=3, delay_seconds=0.2)
    .timeout(seconds=5.0)
    .compile()
)

# Execute using down namespace
result = await L.down.to_result(pipeline)
match result:
    case Ok(user):
        print(f"Success: {user.name}")
    case Error(err):
        print(f"Failed: {err}")
```

### Writer Monad Example

```python
from combinators import lift as L, flow_writer
from combinators.writer import WriterResult, Log

async def fetch_with_logs(uid: int) -> WriterResult[User, Error, Log[str]]:
    result = await api.get(f"/users/{uid}")
    return WriterResult(result, Log.of(f"fetched_user_{uid}"))

# Compose with logging
writer = (
    flow_writer(L.writer.call(fetch_with_logs, 42))
    .retry(times=3)
    .compile()
    .with_log("operation_complete")
)

# Execute Writer
wr = await L.writer.down.to_writer_result(writer)
match wr.result:
    case Ok(user):
        print(f"Success: {user.name}, Logs: {list(wr.log)}")
    case Error(err):
        print(f"Error: {err}, Logs: {list(wr.log)}")
```

### Next Steps

1. 📖 Read the [Human Guide](./human-guide.md) to understand core concepts
2. 🎯 Check [Common Patterns](./llm-reference.md#common-patterns) for recipes
3. 💻 Explore [examples/](../examples/) for working code
4. 🧠 Read [The Emergence](./llm_emerges.md) for LLM-assisted development insights
5. 🔧 See [Writing Your Own Monads](./writing_own_monads.md) if you need custom effects

## 🎯 Library Overview

`combinators.py` provides:

- 🔧 **Combinators**: Functions that compose effects (retry, timeout, fallback, etc.)
- 🏗️ **Monads**: LazyCoroResult and LazyCoroResultWriter for structured effect handling
- 🔒 **Type Safety**: Full type hints with pyright strict mode support
- 🧩 **Composability**: Stack effects like building blocks
- ✅ **Testability**: Policies as data, effects as values

### Why Combinators?

Traditional approaches hide effects in decorators or middleware:

```python
# ❌ Hidden effects
@retry(times=3)
@timeout(5.0)
async def fetch(): ...
```

Combinators make effects **visible and composable**:

```python
# ✅ Explicit effects
result = await (
    flow(call(fetch))
    .retry(times=3, delay_seconds=0.2)
    .timeout(seconds=5.0)
    .compile()
)
```

**Benefits:**
- 👀 **Visible**: See all effects at the call site
- 🧩 **Composable**: Stack effects like LEGO blocks
- 🧪 **Testable**: Test policies and effects in isolation
- 📊 **Typed**: Errors are part of the type signature

## 💡 Key Concepts

### Lift Namespace Structure

The `lift` module uses a clean namespace for all operations:

```python
from combinators import lift as L

# Construction (L.up.*)
L.up.pure(value)         # Create success value
L.up.fail(error)         # Create error value
L.up.from_result(result) # From Result type
L.up.optional(value, error) # From Option

# Function calls
L.call(func, *args)      # Most common: lift function call

# Execution (L.down.*)
L.down.to_result(interp) # Get Result[T, E]
L.down.unsafe(interp)    # Unwrap (raises on Error)
L.down.or_else(interp, default) # Get value or default

# Writer monad (L.writer.*)
L.writer.up.pure(value, log=[...])  # Create Writer
L.writer.up.tell([...])             # Just log
L.writer.call(func, *args)          # Lift Writer function
L.writer.down.to_writer_result(w)   # Execute Writer
```

**Note:** Most functions are also available at the root (`L.pure()`, `L.call()`) for convenience, but the namespace provides clarity.

### Interp[T, E]

The core type: `type Interp[T, E] = LazyCoroResult[T, E]`

A **lazy, async computation** that produces `Result[T, E]` when executed.

- **Lazy**: Nothing executes until you `await`
- **Async**: Built on `async`/`await`
- **Typed**: `T` is success type, `E` is error type

### Extract + Wrap Pattern

Generic combinators work with any monad via:

- **Extract**: Get `Result[T, E]` from monad's raw type
- **Logic**: Implement combinator using `Result`
- **Wrap**: Construct new monad from fn

This pattern enables **code reuse** - write combinator logic once, use for multiple monads.

### Policies as Data

Effects are configured via **data structures**, not magic:

```python
from combinators.control import RetryPolicy

policy = RetryPolicy.exponential_jitter(
    times=5,
    initial=0.1,
    multiplier=2.0,
    max_delay=10.0,
    retry_on=lambda e: e.is_transient
)

# Policy is inspectable, serializable, testable
print(policy.times)  # 5
```

**Benefits:**
- 📊 Policies are data - print, serialize, store in config
- 🧪 Testable - assert on policy fields
- 🔧 Dynamic - build from environment, feature flags

## 📖 Documentation Structure

### Human Guide Structure

1. 🌟 **Foundations of Reliable Logic** - Systematic doubt, errors as data
2. 📊 **Type-Level Honesty** - Hidden failure modes, explicit error handling
3. 🏗️ **Structured Error Handling** - Four levels of abstraction
4. ⏳ **Lazy Computation** - Blueprints vs completed work
5. 🔧 **Lifting External Code** - Integrating unsafe functions
6. 🔄 **Building Resilient Pipelines** - Flow API, smart retry, fallbacks
7. 🤖 **LLM-Assisted Development** - Why FP works with LLMs
8. 📝 **Structured Logging** - Writer monad, Saga pattern
9. 📚 **Collection Processing** - Traverse, batch, validation
10. 🏛️ **System Architecture** - Topology patterns, testing strategies

### LLM Reference Structure

1. ⚡ **Quick Reference** - Core imports, namespace patterns, golden rules
2. 🏛️ **Architecture Overview** - Types, monads, extract + wrap pattern
3. 📋 **API Reference** - Complete function signatures by category
4. 🎯 **Common Patterns** - Resilient fetching, validation, resource management
5. 🔀 **Type Transformations** - How error/success types change
6. ⚙️ **Implementation Notes** - Extract/wrap, log merging, cancellation
7. 🤖 **Code Generation Guidelines** - Namespace patterns, import rules
8. 🧪 **Testing Patterns** - Testing policies and combinators
9. ⚠️ **Common Mistakes** - Pitfalls to avoid

### The Emergence Structure

1. 🔄 **The Strange Loop** - Freedom vs constraint paradox
2. 🧠 **The Hallucination Problem** - Why LLMs invent bugs
3. 🔐 **Grammar as Constraint Solver** - Type signatures as prompts
4. 🧬 **Pattern Breeding** - Replicator effect, vocabulary emergence
5. 🏗️ **Topology Emergence** - Programs as graphs
6. 🛡️ **The Bulkhead Principle** - Separating LLM from infrastructure
7. ✨ **Emergent Behaviors** - Error propagation, sagas, hedging
8. 🔮 **The Future** - Grammar-bound AI hypothesis

## 📂 Examples

Working code examples in [`../examples/`](../examples/):

| Example | Description |
|---------|-------------|
| `01_quickstart.py` | Basic usage patterns |
| `02_cache_fallback_race_ok.py` | Fallback and race strategies |
| `09_llm_resilient_pipeline.py` | LLM resilience patterns |
| `beautiful_chaining.py` | Real-world composition |

## 🤝 Contributing

When adding new combinators or features:

1. ✅ Update both documentation files
2. 📝 Add examples to human guide
3. 📋 Add signatures to LLM reference
4. 🔀 Document type transformations
5. 🧪 Include testing patterns
6. ⚡ Document performance characteristics

## 🔗 Related Resources

- 📚 [Main README](../README.md) - Project overview and installation
- 🏗️ [kungfu](https://github.com/timoniq/kungfu) - Foundation library for Result types
- 💻 [Examples](../examples/) - Working code examples
- 🐛 [GitHub Issues](https://github.com/prostomarkeloff/combinators.py/issues) - Report bugs or request features

## 📝 License

MIT - See [LICENSE](../LICENSE) for details

---

**Made with ❤️ by [@prostomarkeloff](https://github.com/prostomarkeloff)**

