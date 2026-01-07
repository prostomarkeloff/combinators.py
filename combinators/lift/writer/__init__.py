"""
Writer monad specific lift helpers.

Namespace for working with LazyCoroResultWriter[T, E, W].
"""

from __future__ import annotations

# Import namespaces
from . import call as call_ns
from . import down, up

# Convenience: commonly used functions in writer root
from .call import call, lifted

__all__ = (
    # Namespaces
    "up",      # L.writer.up.pure(), L.writer.up.tell()
    "down",    # L.writer.down.to_writer_result(), L.writer.down.unsafe()
    "call_ns", # L.writer.call_ns (module, for explicit access)
    # Convenience - most common operations
    "call",    # L.writer.call(func, *args)
    "lifted",  # @L.writer.lifted
)

