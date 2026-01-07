"""
Writer Monad
============

LazyCoroResultWriter - комбинированная монада:
- Lazy (отложенные вычисления)
- Coro (асинхронность)
- Result[T, E] (успех/ошибка)
- Writer[Log[W]] (аккумуляция логов)

Построена поверх kungfu library patterns.
"""

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

