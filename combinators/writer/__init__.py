"""Writer Monad

LazyCoroResultWriter - combined monad:
- Lazy (deferred computations)
- Coro (asynchronous)
- Result[T, E] (success/error)
- Writer[Log[W]] (log accumulation)

Built on top of kungfu library patterns."""

from .log import Log
from .result import WriterResult
from .monad import LazyCoroResultWriter, writer_ok, writer_error

__all__ = (
    "Log",
    "WriterResult",
    "LazyCoroResultWriter",
    "writer_ok",
    "writer_error",
)

