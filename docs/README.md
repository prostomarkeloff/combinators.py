# Combinators.py Documentation

This directory contains comprehensive documentation for the `combinators.py` library, a functional programming library for building resilient async pipelines in Python.

## 📚 Documentation Index

### Quick Navigation

| I want to... | Go to |
|-------------|-------|
| **Learn the library** | [Human Guide](#for-humans-narrative-guide) |
| **Generate code with AI** | [LLM Reference](#for-llms-reference-documentation) |
| **See examples** | [Examples](#examples) |
| **Understand a combinator** | [API Reference](./llm-reference.md#api-reference) |
| **Debug an issue** | [Troubleshooting](./human-guide.md#troubleshooting) |
| **Migrate from tenacity** | [Migration Guide](./human-guide.md#migration-guide) |
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
- 🐛 Troubleshooting guide
- 🔄 Migration from other libraries

**Use this when:**
- 📖 Learning the library from scratch
- 🤔 Understanding concepts and patterns
- 💡 Looking for examples and use cases
- ✅ Exploring best practices
- 🔍 Debugging issues

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

## 🚀 Quick Start

### Installation

```bash
uv add git+https://github.com/prostomarkeloff/combinators.py.git
```

**Requirements:** Python 3.13+, [kungfu](https://github.com/timoniq/kungfu)

### Basic Example

```python
from combinators import ast, call, lift as L
from kungfu import Ok, Error

# Define pure function
async def fetch_user(user_id: int) -> Result[User, APIError]:
    return await api.get(f"/users/{user_id}")

# Compose effects
pipeline = (
    ast(L.call(fetch_user, 42))
    .retry(times=3, delay_seconds=0.2)
    .timeout(seconds=5.0)
    .lower()
)

# Execute
result = await pipeline
match result:
    case Ok(user):
        print(f"Success: {user.name}")
    case Error(err):
        print(f"Failed: {err}")
```

### Next Steps

1. 📖 Read the [Human Guide](./human-guide.md) to understand core concepts
2. 🎯 Check [Common Patterns](./llm-reference.md#common-patterns) for recipes
3. 💻 Explore [examples/](../examples/) for working code
4. 🐛 Visit [Troubleshooting](./human-guide.md#troubleshooting) if you encounter issues

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
    ast(call(fetch))
    .retry(times=3, delay_seconds=0.2)
    .timeout(seconds=5.0)
    .lower()
)
```

**Benefits:**
- 👀 **Visible**: See all effects at the call site
- 🧩 **Composable**: Stack effects like LEGO blocks
- 🧪 **Testable**: Test policies and effects in isolation
- 📊 **Typed**: Errors are part of the type signature

## 💡 Key Concepts

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
- **Wrap**: Construct new monad from thunk

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

1. 🌟 **Introduction** - Philosophy and core concepts
2. 🧠 **Core Concepts** - Interp, composition, lifting, AST
3. 🏗️ **The Monadic Foundation** - Monads, extract + wrap, Writer
4. 🔧 **Combinators Explained** - All combinators with examples
5. 📐 **Patterns and Practices** - Locality, policies, incremental adoption
6. 🌍 **Real-World Examples** - Resilient fetching, LLM pipelines, batch processing
7. 🚀 **Advanced Topics** - Custom monads, Writer, Flow API, type safety
8. 🐛 **Troubleshooting** - Common issues and solutions
9. 🔄 **Migration Guide** - From tenacity, asyncio, try/except
10. ✅ **Best Practices** - Code patterns and anti-patterns

### LLM Reference Structure

1. 🏛️ **Architecture Overview** - Types, monads, extract + wrap pattern
2. 📋 **API Reference** - Complete function signatures organized by category
3. 🎯 **Common Patterns** - Code templates for common scenarios
4. 🔀 **Type Transformations** - How types change with combinators
5. ⚙️ **Implementation Notes** - Extract/wrap functions, log merging, error handling
6. 🤖 **Code Generation Guidelines** - When to use which variant, import patterns
7. 🧪 **Testing Patterns** - How to test combinators and policies
8. ⚠️ **Common Mistakes** - Pitfalls to avoid
9. ⚡ **Performance** - Complexity and cancellation behavior

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

