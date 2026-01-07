"""
WriterResult - Result with accumulated log
==========================================
"""

from __future__ import annotations

from kungfu import Result


class WriterResult[T, E, W]:
    """
    Result with accumulated writer log.
    
    Combines:
    - Result[T, E]: computation result (success or error)
    - W: accumulated log
    
    This is the "unwrapped" form of LazyCoroResultWriter.
    """

    __slots__ = ("_result", "_log")
    __match_args__ = ("_result", "_log")

    def __init__(self, result: Result[T, E], log: W) -> None:
        self._result = result
        self._log = log

    @property
    def result(self) -> Result[T, E]:
        """The underlying Result."""
        return self._result

    @property
    def log(self) -> W:
        """The accumulated log."""
        return self._log

    def __repr__(self) -> str:
        return f"WriterResult({self._result!r}, log={self._log!r})"


__all__ = ("WriterResult",)

