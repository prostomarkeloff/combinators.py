"""
Writer monad specific lift helpers.

Namespace для работы с LazyCoroResultWriter[T, E, W].
"""

from __future__ import annotations

# Import namespaces
from . import call, down, up

# Convenience: декораторы в корне w
from .call import lifted

__all__ = (
    # Namespaces
    "up",     # L.w.up.pure(), L.w.up.tell()
    "down",   # L.w.down.to_writer_result(), L.w.down.unsafe()
    "call",   # L.w.call()
    # Convenience
    "lifted", # @L.w.lifted
)
