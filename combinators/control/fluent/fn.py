from __future__ import annotations

from ..retry import RetryPolicy
from ..._types import Predicate

def retry_policy[E](
    times: int,
    *,
    delay_seconds: float = 0.0,
    retry_on: Predicate[E] | None = None,
) -> RetryPolicy[E]:
    """Helper for fluent retry policy construction."""
    # type: ignore because RetryPolicy.fixed is generic over E which isn't in params.
    # Safe because caller context provides E, and retry_on type matches.
    return RetryPolicy.fixed(times=times, delay_seconds=delay_seconds, retry_on=retry_on)  # type: ignore[return-value]

__all__ = ("retry_policy",)

