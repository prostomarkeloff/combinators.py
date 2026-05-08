"""Tests for selection: best_of, best_of_many, vote."""

from __future__ import annotations

from typing import Any

from kungfu import Error, LazyCoroResult, Ok, Result

from combinators import best_of, best_of_many, vote
from tests.conftest import lcr_err, lcr_ok


async def test_best_of_picks_max_by_key() -> None:
    counter = {"n": 0}

    async def run() -> Result[int, Any]:
        counter["n"] += 1
        return Ok(counter["n"])

    interp = LazyCoroResult(run)
    out = await best_of(interp, n=4, key=lambda x: float(x))()
    assert out == Ok(4)


async def test_best_of_many_picks_max_by_key() -> None:
    candidates = [lcr_ok(2), lcr_ok(7), lcr_ok(5)]
    out = await best_of_many(candidates, key=lambda x: float(x))()
    assert out == Ok(7)


async def test_best_of_propagates_error() -> None:
    out = await best_of(lcr_err("e"), n=3, key=lambda x: 0.0)()
    assert out == Error("e")


async def test_vote_uses_judge_to_select_winner() -> None:
    candidates = [lcr_ok("a"), lcr_ok("b"), lcr_ok("a")]

    async def judge(values: Any) -> str:
        # majority
        return max(set(values), key=list(values).count)

    out = await vote(candidates, judge=judge)()
    assert out == Ok("a")


async def test_vote_propagates_error() -> None:
    async def judge(values: Any) -> Any:
        return values[0]

    out = await vote([lcr_ok(1), lcr_err("e")], judge=judge)()
    assert out == Error("e")
