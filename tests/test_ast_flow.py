"""Tests for the AST/Flow fluent builder."""

from __future__ import annotations

from typing import Any

import pytest
from kungfu import Error, LazyCoroResult, Ok, Result

from combinators import (
    ConditionNotMetError,
    RaceOkPolicy,
    RateLimitPolicy,
    RepeatPolicy,
    RetryPolicy,
    TimeoutError,
    chain,
    chain_bracket,
    chain_many,
    flow,
    flow_bracket,
    flow_many,
    flow_writer,
    flow_bracket_writer,
    flow_many_writer,
)
from combinators.ast import ast, ast_bracket, ast_many
from tests.conftest import Counter, FlakyOp, lcr_err, lcr_ok, w_err, w_ok


async def test_flow_basic_compile() -> None:
    f = flow(lcr_ok(1)).map(lambda x: x + 1)
    assert await f.compile()() == Ok(2)
    # lower is alias
    assert await f.lower()() == Ok(2)


async def test_flow_then() -> None:
    f = flow(lcr_ok(1)).then(lambda x: lcr_ok(x * 10))
    assert await f.compile()() == Ok(10)


async def test_flow_retry_via_times_arg() -> None:
    flaky = FlakyOp(fail_until=1, ok_value="ok")
    f = flow(flaky.lcr()).retry(times=3)
    assert await f.compile()() == Ok("ok")
    assert flaky.calls == 2


async def test_flow_retry_via_policy_arg() -> None:
    flaky = FlakyOp(fail_until=0, ok_value="ok")
    f = flow(flaky.lcr()).retry(policy=RetryPolicy.fixed(times=2))
    assert await f.compile()() == Ok("ok")


def test_flow_retry_requires_policy_or_times() -> None:
    with pytest.raises(ValueError):
        flow(lcr_ok(1)).retry()


async def test_flow_timeout_passes_through() -> None:
    f = flow(lcr_ok(1)).timeout(seconds=1.0)
    assert await f.compile()() == Ok(1)


async def test_flow_tap_runs_effect() -> None:
    c = Counter()
    f = flow(lcr_ok(1)).tap(c)
    await f.compile()()
    assert c.values == [1]


async def test_flow_tap_async_runs_effect() -> None:
    c = Counter()
    f = flow(lcr_ok(1)).tap_async(c.acall)
    await f.compile()()
    assert c.values == [1]


async def test_flow_tap_err_runs_effect() -> None:
    c = Counter()
    f = flow(lcr_err("e")).tap_err(c)
    await f.compile()()
    assert c.values == ["e"]


async def test_flow_tap_err_async_runs_effect() -> None:
    c = Counter()
    f = flow(lcr_err("e")).tap_err_async(c.acall)
    await f.compile()()
    assert c.values == ["e"]


async def test_flow_ensure_passes() -> None:
    f = flow(lcr_ok(5)).ensure(lambda x: x > 0, lambda x: "neg")
    assert await f.compile()() == Ok(5)


async def test_flow_ensure_fails() -> None:
    f = flow(lcr_ok(-1)).ensure(lambda x: x > 0, lambda x: f"neg:{x}")
    assert await f.compile()() == Error("neg:-1")


async def test_flow_reject_blocks_match() -> None:
    f = flow(lcr_ok(5)).reject(lambda x: x > 0, lambda x: "pos")
    assert await f.compile()() == Error("pos")


async def test_flow_race_ok() -> None:
    f = flow(lcr_err("primary")).race_ok(lcr_ok("alt"))
    assert await f.compile()() == Ok("alt")


async def test_flow_race_ok_with_policy() -> None:
    f = flow(lcr_err("primary")).race_ok(
        lcr_err("alt"),
        policy=RaceOkPolicy(error_strategy="first"),
    )
    assert await f.compile()() == Error("primary")


async def test_flow_best_of() -> None:
    counter = {"n": 0}

    async def run() -> Result[int, Any]:
        counter["n"] += 1
        return Ok(counter["n"])

    f = flow(LazyCoroResult(run)).best_of(n=3, key=lambda x: float(x))
    assert await f.compile()() == Ok(3)


async def test_flow_delay() -> None:
    f = flow(lcr_ok(1)).delay(seconds=0.0)
    assert await f.compile()() == Ok(1)


async def test_flow_recover_default() -> None:
    f = flow(lcr_err("e")).recover(default=99)
    assert await f.compile()() == Ok(99)


async def test_flow_recover_with_handler() -> None:
    f = flow(lcr_err("orig")).recover_with(handler=lambda e: f"recovered:{e}")
    assert await f.compile()() == Ok("recovered:orig")


async def test_flow_repeat_until_via_max_rounds() -> None:
    counter = {"n": 0}

    async def run() -> Result[int, Any]:
        counter["n"] += 1
        return Ok(counter["n"])

    f = flow(LazyCoroResult(run)).repeat_until(condition=lambda x: x == 2, max_rounds=5)
    assert await f.compile()() == Ok(2)


def test_flow_repeat_until_requires_args() -> None:
    with pytest.raises(ValueError):
        flow(lcr_ok(1)).repeat_until(condition=lambda x: True)


async def test_flow_repeat_until_via_policy() -> None:
    f = flow(lcr_ok(1)).repeat_until(condition=lambda x: x > 100, policy=RepeatPolicy(max_rounds=2))
    out = await f.compile()()
    assert isinstance(out, Error) and isinstance(out.error, ConditionNotMetError)


async def test_flow_rate_limit_via_max_per_second() -> None:
    f = flow(lcr_ok(1)).rate_limit(max_per_second=100, burst=10)
    assert await f.compile()() == Ok(1)


def test_flow_rate_limit_requires_args() -> None:
    with pytest.raises(ValueError):
        flow(lcr_ok(1)).rate_limit()


async def test_flow_rate_limit_via_policy() -> None:
    f = flow(lcr_ok(1)).rate_limit(policy=RateLimitPolicy(max_per_second=100))
    assert await f.compile()() == Ok(1)


async def test_flow_bimap_tap() -> None:
    okc, errc = Counter(), Counter()
    await flow(lcr_ok(1)).bimap_tap(on_ok=okc, on_err=errc).compile()()
    await flow(lcr_err("e")).bimap_tap(on_ok=okc, on_err=errc).compile()()
    assert okc.values == [1] and errc.values == ["e"]


async def test_flow_filter_or() -> None:
    f = flow(lcr_ok(-1)).filter_or(predicate=lambda x: x > 0, error=lambda x: f"neg:{x}")
    assert await f.compile()() == Error("neg:-1")


async def test_flow_fallback_chain() -> None:
    f = flow(lcr_err("a")).fallback(lcr_err("b"), lcr_ok("c"))
    assert await f.compile()() == Ok("c")


async def test_flow_replicate() -> None:
    counter = {"n": 0}

    async def run() -> Result[int, Any]:
        counter["n"] += 1
        return Ok(counter["n"])

    f = flow(LazyCoroResult(run)).replicate(n=3)
    assert await f.compile()() == Ok([1, 2, 3])


async def test_flow_chained_pipeline() -> None:
    c = Counter()
    f = (
        flow(lcr_ok(1))
        .map(lambda x: x + 1)
        .tap(c)
        .ensure(lambda x: x > 0, lambda x: "neg")
        .recover(default=0)
    )
    assert await f.compile()() == Ok(2)
    assert c.values == [2]


async def test_flow_many_picks_best() -> None:
    f = flow_many([lcr_ok(2), lcr_ok(7), lcr_ok(5)], key=lambda x: float(x))
    assert await f.compile()() == Ok(7)


async def test_flow_bracket() -> None:
    released: list[str] = []

    async def release(r: str) -> None:
        released.append(r)

    f = flow_bracket(lcr_ok("res"), release=release, use=lambda r: lcr_ok(f"used:{r}"))
    assert await f.compile()() == Ok("used:res")
    assert released == ["res"]


def test_flow_aliases_match() -> None:
    assert flow is chain is ast
    assert flow_bracket is chain_bracket is ast_bracket
    assert flow_many is chain_many is ast_many


# -- FlowWriter --

async def test_flow_writer_basic() -> None:
    fw = flow_writer(w_ok(1, "lg")).map(lambda x: x + 1)
    wr = await fw.compile()()
    assert wr.result == Ok(2)


async def test_flow_writer_then() -> None:
    fw = flow_writer(w_ok(1, "a")).then(lambda x: w_ok(x * 10, "b"))
    wr = await fw.compile()()
    assert wr.result == Ok(10)
    assert list(wr.log) == ["a", "b"]


async def test_flow_writer_retry_times() -> None:
    fw = flow_writer(w_ok(1, "lg")).retry(times=2)
    wr = await fw.compile()()
    assert wr.result == Ok(1)


def test_flow_writer_retry_requires_args() -> None:
    with pytest.raises(ValueError):
        flow_writer(w_ok(1, "lg")).retry()


async def test_flow_writer_timeout() -> None:
    fw = flow_writer(w_ok(1, "lg")).timeout(seconds=1.0)
    wr = await fw.compile()()
    assert wr.result == Ok(1)


async def test_flow_writer_taps() -> None:
    okc, errc = Counter(), Counter()
    await flow_writer(w_ok(1, "lg")).tap(okc).tap_err(errc).compile()()
    await flow_writer(w_ok(1, "lg")).tap_async(okc.acall).tap_err_async(errc.acall).compile()()
    assert okc.values == [1, 1] and errc.values == []


async def test_flow_writer_ensure_reject() -> None:
    fw1 = flow_writer(w_ok(5, "lg")).ensure(lambda x: x > 0, lambda x: "neg")
    fw2 = flow_writer(w_ok(5, "lg")).reject(lambda x: x > 0, lambda x: "pos")
    assert (await fw1.compile()()).result == Ok(5)
    assert (await fw2.compile()()).result == Error("pos")


async def test_flow_writer_race_ok() -> None:
    fw = flow_writer(w_err("a", "p")).race_ok(w_ok("b", "s"))
    wr = await fw.compile()()
    assert wr.result == Ok("b")


async def test_flow_writer_race_ok_policy() -> None:
    fw = flow_writer(w_err("a", "p")).race_ok(w_err("b", "q"), policy=RaceOkPolicy(error_strategy="first"))
    wr = await fw.compile()()
    assert wr.result == Error("a")


async def test_flow_writer_best_of() -> None:
    n = {"x": 0}

    async def run():
        from combinators import LazyCoroResultWriter, WriterResult, Log
        n["x"] += 1
        return WriterResult(Ok(n["x"]), Log.of(f"n{n['x']}"))

    from combinators import LazyCoroResultWriter
    fw = flow_writer(LazyCoroResultWriter(run)).best_of(n=3, key=lambda x: float(x))
    wr = await fw.compile()()
    assert wr.result == Ok(3)


async def test_flow_writer_delay_recover_recover_with() -> None:
    fw = flow_writer(w_err("e", "lg")).recover(default=99)
    wr = await fw.compile()()
    assert wr.result == Ok(99)

    fw2 = flow_writer(w_err("e", "lg")).recover_with(handler=lambda e: f"r:{e}")
    wr2 = await fw2.compile()()
    assert wr2.result == Ok("r:e")

    fw3 = flow_writer(w_ok(1, "lg")).delay(seconds=0.0)
    assert (await fw3.compile()()).result == Ok(1)


async def test_flow_writer_repeat_until() -> None:
    n = {"x": 0}

    async def run():
        from combinators import WriterResult, Log
        n["x"] += 1
        return WriterResult(Ok(n["x"]), Log.of(f"n{n['x']}"))

    from combinators import LazyCoroResultWriter
    fw = flow_writer(LazyCoroResultWriter(run)).repeat_until(condition=lambda x: x == 2, max_rounds=5)
    wr = await fw.compile()()
    assert wr.result == Ok(2)


def test_flow_writer_repeat_until_requires_args() -> None:
    with pytest.raises(ValueError):
        flow_writer(w_ok(1, "lg")).repeat_until(condition=lambda x: True)


async def test_flow_writer_rate_limit() -> None:
    fw = flow_writer(w_ok(1, "lg")).rate_limit(max_per_second=100, burst=10)
    wr = await fw.compile()()
    assert wr.result == Ok(1)


def test_flow_writer_rate_limit_requires_args() -> None:
    with pytest.raises(ValueError):
        flow_writer(w_ok(1, "lg")).rate_limit()


async def test_flow_writer_bimap_tap_filter_or_fallback() -> None:
    okc, errc = Counter(), Counter()
    fw = (
        flow_writer(w_ok(5, "a"))
        .bimap_tap(on_ok=okc, on_err=errc)
        .filter_or(predicate=lambda x: x > 0, error=lambda x: "neg")
        .fallback(w_ok(99, "b"))
    )
    wr = await fw.compile()()
    assert wr.result == Ok(5)
    assert okc.values == [5]


async def test_flow_writer_replicate() -> None:
    fw = flow_writer(w_ok(1, "lg")).replicate(n=3)
    wr = await fw.compile()()
    assert wr.result == Ok([1, 1, 1])


async def test_flow_writer_lower_alias() -> None:
    fw = flow_writer(w_ok(1, "lg"))
    assert fw.compile() is fw.lower()


# -- flow_bracket_writer / flow_many_writer --

async def test_flow_bracket_writer() -> None:
    released: list[str] = []

    async def release(r: str) -> None:
        released.append(r)

    fbw = flow_bracket_writer(w_ok("res", "a"), release=release, use=lambda r: w_ok(f"u:{r}", "b"))
    wr = await fbw.compile()()
    assert wr.result == Ok("u:res")
    assert released == ["res"]


async def test_flow_many_writer() -> None:
    fw = flow_many_writer([w_ok(2, "a"), w_ok(7, "b")], key=lambda x: float(x))
    wr = await fw.compile()()
    assert wr.result == Ok(7)
