from __future__ import annotations

class TimeoutError(Exception):
    """Interpretation took too long."""

    seconds: float

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        super().__init__(f"Timed out after {seconds}s")

class ConditionNotMetError(Exception):
    """repeat_until exhausted max_rounds without satisfying condition."""

    rounds: int

    def __init__(self, rounds: int) -> None:
        self.rounds = rounds
        super().__init__(f"Condition not met after {rounds} rounds")

__all__ = ("ConditionNotMetError", "TimeoutError")

