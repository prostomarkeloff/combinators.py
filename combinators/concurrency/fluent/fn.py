from __future__ import annotations

from typing import Literal

from ..race import RaceOkPolicy


def race_ok_policy(
    *,
    cancel_pending: bool = True,
    error_strategy: Literal["first", "last"] = "last",
) -> RaceOkPolicy:
    # Validation happens inside RaceOkPolicy.__post_init__.
    return RaceOkPolicy(cancel_pending=cancel_pending, error_strategy=error_strategy)

__all__ = ("race_ok_policy",)

