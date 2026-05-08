"""Tests for Writer monad and *_writer combinators."""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st
from kungfu import Error, Ok, Result

from combinators import (
    LazyCoroResultWriter,
    Log,
    RetryPolicy,
    WriterResult,
    bracket_on_error_writer,
    bracket_writer,
    fallback_chain_writer,
    fallback_writer,
    fold_writer,
    gather2_writer,
    gather3_writer,
    parallel_writer,
    partition_writer,
    race_ok_writer,
    race_writer,
    rate_limit_writer,
    RateLimitPolicy,
    recover_with_writer,
    recover_writer,
    reject_writer,
    delay_writer,
    timeout_writer,
    ensure_writer,
    repeat_until_writer,
    RepeatPolicy,
    replicate_writer,
    retry_writer,
    sequence_writer,
    traverse_writer,
    traverse_par_writer,
    validate_writer,
    with_resource_writer,
    zip_par_writer,
    zip_with_writer,
    bimap_tap_writer,
    filter_or_writer,
    tap_async_writer,
    tap_err_async_writer,
    tap_err_writer,
    tap_writer,
    best_of_writer,
    best_of_many_writer,
    vote_writer,
    writer,
)
from combinators.writer import writer_error, writer_ok
from tests.conftest import Counter, w_err, w_ok


# -- Log --

def test_log_empty_combine_identity() -> None:
    a: Log[int] = Log.of(1, 2, 3)
    assert list(a.combine(Log())) == [1, 2, 3]
    assert list(Log().combine(a)) == [1, 2, 3]


@given(
    a=st.lists(st.integers()),
    b=st.lists(st.integers()),
    c=st.lists(st.integers()),
)
def test_log_associativity(a: list[int], b: list[int], c: list[int]) -> None:
    la, lb, lc = Log[int](a), Log[int](b), Log[int](c)
    left = la.combine(lb).combine(lc)
    right = la.combine(lb.combine(lc))
    assert list(left) == list(right) == a + b + c


def test_log_tell_appends_one_item() -> None:
    log: Log[str] = Log.of("a")
    grown = log.tell("b")
    assert list(grown) == ["a", "b"]
    # original is not mutated
    assert list(log) == ["a"]


# -- WriterResult --

def test_writer_result_props() -> None:
    wr = WriterResult(Ok(1), Log.of("x"))
    assert wr.result == Ok(1)
    assert list(wr.log) == ["x"]
    assert "log=" in repr(wr)


# -- LazyCoroResultWriter constructors --

async def test_writer_pure_has_empty_log() -> None:
    wr = await LazyCoroResultWriter.pure(7, log_type=str)()
    assert wr.result == Ok(7) and list(wr.log) == []


async def test_writer_from_result() -> None:
    wr = await LazyCoroResultWriter.from_result(Error("e"), log_type=str)()
    assert wr.result == Error("e") and list(wr.log) == []


async def test_writer_tell() -> None:
    wr = await LazyCoroResultWriter.tell("a", "b")()
    assert wr.result == Ok(None) and list(wr.log) == ["a", "b"]


async def test_writer_from_lazy_coro_result() -> None:
    from kungfu import LazyCoroResult

    async def run() -> Result[int, str]:
        return Ok(3)

    interp = LazyCoroResult(run)
    wr = await LazyCoroResultWriter.from_lazy_coro_result(interp, log_type=str)()
    assert wr.result == Ok(3) and list(wr.log) == []


async def test_writer_ok_helper() -> None:
    wr = await writer_ok(1, "log1", "log2")()
    assert wr.result == Ok(1) and list(wr.log) == ["log1", "log2"]


async def test_writer_error_helper() -> None:
    wr = await writer_error("boom", "log1")()
    assert wr.result == Error("boom") and list(wr.log) == ["log1"]


# -- monad operations --

async def test_map_preserves_log_and_transforms_value() -> None:
    wr = await w_ok(2, "lg").map(lambda x: x + 1)()
    assert wr.result == Ok(3) and list(wr.log) == ["lg"]


async def test_map_err_transforms_error_only() -> None:
    wr = await w_err("e", "lg").map_err(lambda e: f"E:{e}")()
    assert wr.result == Error("E:e") and list(wr.log) == ["lg"]


async def test_map_log_transforms_log() -> None:
    wr = await w_ok(1, "a", "b").map_log(lambda log: Log.of(*[s.upper() for s in log]))()
    assert list(wr.log) == ["A", "B"]


async def test_then_combines_logs() -> None:
    base = w_ok(2, "first")

    async def step(x: int) -> WriterResult[int, str, Log[str]]:
        return WriterResult(Ok(x * 10), Log.of("second"))

    wr = await base.then(step)()
    assert wr.result == Ok(20) and list(wr.log) == ["first", "second"]


async def test_then_short_circuits_on_error() -> None:
    base = w_err("e", "first")

    async def step(x: object) -> WriterResult[int, str, Log[str]]:
        return WriterResult(Ok(99), Log.of("second"))

    wr = await base.then(step)()
    assert wr.result == Error("e") and list(wr.log) == ["first"]


async def test_then_result_keeps_existing_log() -> None:
    base = w_ok(3, "first")

    async def step(x: int) -> Result[int, str]:
        return Ok(x + 1)

    wr = await base.then_result(step)()
    assert wr.result == Ok(4) and list(wr.log) == ["first"]


async def test_then_result_short_circuit() -> None:
    base = w_err("e", "first")

    async def step(x: object) -> Result[int, str]:
        return Ok(99)

    wr = await base.then_result(step)()
    assert wr.result == Error("e") and list(wr.log) == ["first"]


async def test_with_log_appends() -> None:
    wr = await w_ok(1, "a").with_log("b", "c")()
    assert list(wr.log) == ["a", "b", "c"]


async def test_listen_returns_value_and_log() -> None:
    wr = await w_ok(1, "a", "b").listen()()
    assert wr.result.unwrap()[0] == 1
    assert list(wr.result.unwrap()[1]) == ["a", "b"]


async def test_listen_short_circuits_on_error() -> None:
    wr = await w_err("e", "a").listen()()
    assert wr.result == Error("e") and list(wr.log) == ["a"]


async def test_censor_modifies_log_only() -> None:
    wr = await w_ok(1, "a", "b").censor(lambda log: Log[str]())()
    assert wr.result == Ok(1) and list(wr.log) == []


async def test_cache_returns_same_results() -> None:
    counter = {"n": 0}

    async def run() -> WriterResult[int, str, Log[str]]:
        counter["n"] += 1
        return WriterResult(Ok(counter["n"]), Log.of("once"))

    cached = LazyCoroResultWriter(run).cache()
    a = await cached()
    b = await cached()
    assert a.result == b.result and counter["n"] == 1


async def test_unwrap_returns_value() -> None:
    val = await w_ok(7).unwrap()
    assert val == 7


async def test_to_lazy_coro_result_keeps_log_in_value_on_ok() -> None:
    inner = await w_ok(1, "a", "b").to_lazy_coro_result()()
    assert isinstance(inner, Ok)
    value, log = inner.unwrap()
    assert value == 1 and list(log) == ["a", "b"]


async def test_to_lazy_coro_result_passes_through_error() -> None:
    inner = await w_err("oops", "a").to_lazy_coro_result()()
    assert inner == Error("oops")


# -- _writer combinators (sanity / log merging) --

async def test_retry_writer_uses_last_log_on_exhaustion() -> None:
    n = {"x": 0}

    async def run() -> WriterResult[int, str, Log[str]]:
        n["x"] += 1
        return WriterResult(Error("e"), Log.of(f"attempt-{n['x']}"))

    wr = await retry_writer(LazyCoroResultWriter(run), policy=RetryPolicy.fixed(times=3))()
    assert wr.result == Error("e")
    assert list(wr.log) == ["attempt-3"]


async def test_retry_writer_returns_first_ok() -> None:
    n = {"x": 0}

    async def run() -> WriterResult[int, str, Log[str]]:
        n["x"] += 1
        if n["x"] < 2:
            return WriterResult(Error("e"), Log.of("e1"))
        return WriterResult(Ok(42), Log.of("ok"))

    wr = await retry_writer(LazyCoroResultWriter(run), policy=RetryPolicy.fixed(times=3))()
    assert wr.result == Ok(42)
    assert list(wr.log) == ["ok"]


async def test_fallback_writer_uses_secondary() -> None:
    wr = await fallback_writer(w_err("e", "p"), w_ok(2, "s"))()
    assert wr.result == Ok(2) and list(wr.log) == ["s"]


async def test_fallback_chain_writer() -> None:
    wr = await fallback_chain_writer(w_err("a", "1"), w_err("b", "2"), w_ok(3, "3"))()
    assert wr.result == Ok(3) and list(wr.log) == ["3"]


async def test_ensure_writer_predicate_pass() -> None:
    wr = await ensure_writer(w_ok(5, "lg"), predicate=lambda x: x > 0, error=lambda x: "neg")()
    assert wr.result == Ok(5) and list(wr.log) == ["lg"]


async def test_ensure_writer_predicate_fail_keeps_log() -> None:
    wr = await ensure_writer(w_ok(-1, "lg"), predicate=lambda x: x > 0, error=lambda x: f"neg:{x}")()
    assert wr.result == Error("neg:-1") and list(wr.log) == ["lg"]


async def test_ensure_writer_passes_through_error() -> None:
    wr = await ensure_writer(w_err("e", "lg"), predicate=lambda x: True, error=lambda x: "x")()
    assert wr.result == Error("e") and list(wr.log) == ["lg"]


async def test_reject_writer() -> None:
    wr = await reject_writer(w_ok(5, "lg"), predicate=lambda x: x > 0, error=lambda x: "pos")()
    assert wr.result == Error("pos") and list(wr.log) == ["lg"]


async def test_reject_writer_passes_through_when_predicate_false() -> None:
    wr = await reject_writer(w_ok(-1, "lg"), predicate=lambda x: x > 0, error=lambda x: "pos")()
    assert wr.result == Ok(-1)


async def test_reject_writer_passes_through_error() -> None:
    wr = await reject_writer(w_err("e", "lg"), predicate=lambda x: True, error=lambda x: "x")()
    assert wr.result == Error("e")


async def test_recover_writer_uses_default_keeps_log() -> None:
    wr = await recover_writer(w_err("e", "lg"), default=42)()
    assert wr.result == Ok(42) and list(wr.log) == ["lg"]


async def test_recover_writer_keeps_ok() -> None:
    wr = await recover_writer(w_ok(1, "lg"), default=99)()
    assert wr.result == Ok(1)


async def test_recover_with_writer_uses_handler() -> None:
    wr = await recover_with_writer(w_err(7, "lg"), handler=lambda e: e * 10)()
    assert wr.result == Ok(70) and list(wr.log) == ["lg"]


async def test_recover_with_writer_keeps_ok() -> None:
    wr = await recover_with_writer(w_ok(2, "lg"), handler=lambda e: 99)()
    assert wr.result == Ok(2)


async def test_repeat_until_writer_returns_ok() -> None:
    n = {"x": 0}

    async def run() -> WriterResult[int, str, Log[str]]:
        n["x"] += 1
        return WriterResult(Ok(n["x"]), Log.of(f"n{n['x']}"))

    wr = await repeat_until_writer(
        LazyCoroResultWriter(run),
        condition=lambda x: x == 2,
        policy=RepeatPolicy(max_rounds=5),
    )()
    assert wr.result == Ok(2) and list(wr.log) == ["n2"]


async def test_repeat_until_writer_short_circuits_on_error() -> None:
    wr = await repeat_until_writer(
        w_err("e", "lg"),
        condition=lambda x: True,
        policy=RepeatPolicy(max_rounds=2),
    )()
    assert wr.result == Error("e") and list(wr.log) == ["lg"]


async def test_repeat_until_writer_exhausts() -> None:
    wr = await repeat_until_writer(
        w_ok(1, "lg"),
        condition=lambda x: x > 100,
        policy=RepeatPolicy(max_rounds=2),
    )()
    from combinators import ConditionNotMetError
    assert isinstance(wr.result, Error) and isinstance(wr.result.error, ConditionNotMetError)


async def test_bracket_writer_releases_and_merges_logs() -> None:
    released: list[str] = []

    async def release(r: str) -> None:
        released.append(r)

    wr = await bracket_writer(
        w_ok("res", "acquired"),
        release=release,
        use=lambda r: w_ok(f"used:{r}", "used"),
    )()
    assert wr.result == Ok("used:res") and list(wr.log) == ["acquired", "used"]
    assert released == ["res"]


async def test_bracket_writer_releases_on_error_and_merges_logs() -> None:
    released: list[str] = []

    async def release(r: str) -> None:
        released.append(r)

    wr = await bracket_writer(
        w_ok("res", "acquired"),
        release=release,
        use=lambda r: w_err("e", "errlog"),
    )()
    assert wr.result == Error("e") and list(wr.log) == ["acquired", "errlog"]
    assert released == ["res"]


async def test_bracket_writer_skips_use_on_acquire_error() -> None:
    released: list[str] = []

    async def release(r: str) -> None:
        released.append(r)

    wr = await bracket_writer(
        w_err("e", "acq-fail"),
        release=release,
        use=lambda r: w_ok("never", "u"),
    )()
    assert wr.result == Error("e") and list(wr.log) == ["acq-fail"]
    assert released == []


async def test_bracket_writer_swallows_release_error() -> None:
    async def release(r: str) -> None:
        raise RuntimeError("nope")

    wr = await bracket_writer(
        w_ok("res", "a"),
        release=release,
        use=lambda r: w_ok(1, "b"),
    )()
    assert wr.result == Ok(1)


async def test_bracket_on_error_writer_only_releases_on_error() -> None:
    released: list[str] = []

    async def release(r: str) -> None:
        released.append(r)

    ok_wr = await bracket_on_error_writer(
        w_ok("res", "a"),
        release=release,
        use=lambda r: w_ok("done", "b"),
    )()
    assert ok_wr.result == Ok("done") and released == []

    err_wr = await bracket_on_error_writer(
        w_ok("res2", "a"),
        release=release,
        use=lambda r: w_err("oops", "b"),
    )()
    assert err_wr.result == Error("oops") and released == ["res2"]


async def test_bracket_on_error_writer_skips_when_acquire_fails() -> None:
    released: list[str] = []

    async def release(r: str) -> None:
        released.append(r)

    wr = await bracket_on_error_writer(
        w_err("e", "fail"),
        release=release,
        use=lambda r: w_ok(1, "u"),
    )()
    assert wr.result == Error("e") and released == []


async def test_bracket_on_error_writer_swallows_release_error() -> None:
    async def release(r: str) -> None:
        raise RuntimeError("boom")

    wr = await bracket_on_error_writer(
        w_ok("r", "a"),
        release=release,
        use=lambda r: w_err("e", "b"),
    )()
    assert wr.result == Error("e")


async def test_with_resource_writer_releases() -> None:
    released: list[str] = []

    async def release(r: str) -> None:
        released.append(r)

    wr = await with_resource_writer("R", release=release, use=lambda r: w_ok(r, "u"))()
    assert wr.result == Ok("R") and released == ["R"]


async def test_with_resource_writer_swallows_release_error() -> None:
    async def release(r: str) -> None:
        raise RuntimeError("nope")

    wr = await with_resource_writer("R", release=release, use=lambda r: w_ok(1, "u"))()
    assert wr.result == Ok(1)


# -- concurrency / collection writer combinators --

async def test_parallel_writer_merges_logs() -> None:
    wr = await parallel_writer(w_ok(1, "a"), w_ok(2, "b"))()
    assert wr.result == Ok([1, 2]) and list(wr.log) == ["a", "b"]


async def test_parallel_writer_fail_fast_with_merged_logs() -> None:
    wr = await parallel_writer(w_ok(1, "a"), w_err("e", "b"))()
    assert wr.result == Error("e") and "b" in list(wr.log)


async def test_gather2_writer_merges_logs() -> None:
    wr = await gather2_writer(w_ok(1, "a"), w_ok("x", "b"))()
    assert wr.result == Ok((1, "x")) and list(wr.log) == ["a", "b"]


async def test_gather2_writer_error() -> None:
    wr = await gather2_writer(w_err("e", "a"), w_ok(1, "b"))()
    assert wr.result == Error("e")


async def test_gather3_writer_merges_logs() -> None:
    wr = await gather3_writer(w_ok(1, "a"), w_ok(2, "b"), w_ok(3, "c"))()
    assert wr.result == Ok((1, 2, 3)) and list(wr.log) == ["a", "b", "c"]


async def test_gather3_writer_error() -> None:
    wr = await gather3_writer(w_ok(1, "a"), w_err("e", "b"), w_ok(3, "c"))()
    assert wr.result == Error("e")


async def test_zip_par_writer_returns_tuple_and_merges_logs() -> None:
    wr = await zip_par_writer(w_ok(1, "a"), w_ok(2, "b"))()
    assert wr.result == Ok((1, 2)) and list(wr.log) == ["a", "b"]


async def test_zip_par_writer_fails() -> None:
    wr = await zip_par_writer(w_ok(1, "a"), w_err("e", "b"))()
    assert wr.result == Error("e")


async def test_zip_with_writer_combines_results() -> None:
    wr = await zip_with_writer(w_ok(1, "a"), w_ok(2, "b"), combiner=lambda t: sum(t))()
    assert wr.result == Ok(3)


async def test_partition_writer_merges_logs() -> None:
    wr = await partition_writer([w_ok(1, "a"), w_err("e", "b"), w_ok(2, "c")])()
    assert wr.result == Ok(([1, 2], ["e"]))
    assert sorted(list(wr.log)) == ["a", "b", "c"]


async def test_validate_writer_collects_errors() -> None:
    wr = await validate_writer([w_ok(1, "a"), w_err("e1", "b"), w_err("e2", "c")])()
    assert wr.result == Error(["e1", "e2"])


async def test_validate_writer_all_ok() -> None:
    wr = await validate_writer([w_ok(1, "a"), w_ok(2, "b")])()
    assert wr.result == Ok([1, 2])


async def test_sequence_writer_merges_logs() -> None:
    wr = await sequence_writer([w_ok(1, "a"), w_ok(2, "b")])()
    assert wr.result == Ok([1, 2]) and list(wr.log) == ["a", "b"]


async def test_traverse_writer_merges_logs() -> None:
    wr = await traverse_writer([1, 2, 3], lambda x: w_ok(x * 2, f"l{x}"))()
    assert wr.result == Ok([2, 4, 6])
    assert list(wr.log) == ["l1", "l2", "l3"]


async def test_traverse_writer_short_circuits() -> None:
    def h(x: int) -> Any:
        return w_err(f"e{x}", f"l{x}") if x == 2 else w_ok(x, f"l{x}")

    wr = await traverse_writer([1, 2, 3], h)()
    assert wr.result == Error("e2")


async def test_traverse_par_writer_runs_all() -> None:
    wr = await traverse_par_writer([1, 2], lambda x: w_ok(x, "lg"), concurrency=2)()
    assert wr.result == Ok([1, 2])


async def test_replicate_writer_zero() -> None:
    wr = await replicate_writer(w_ok(1, "lg"), n=0)()
    assert wr.result == Ok([])


def test_replicate_writer_negative() -> None:
    with pytest.raises(ValueError):
        replicate_writer(w_ok(1, "lg"), n=-1)


async def test_replicate_writer_positive() -> None:
    wr = await replicate_writer(w_ok(1, "lg"), n=3)()
    assert wr.result == Ok([1, 1, 1])


async def test_fold_writer_accumulates_and_merges() -> None:
    items = [1, 2, 3]

    def step(acc: int, x: int) -> Any:
        return w_ok(acc + x, f"a{x}")

    wr = await fold_writer(items, step, initial=0)()
    assert wr.result == Ok(6)
    assert list(wr.log) == ["a1", "a2", "a3"]


async def test_fold_writer_short_circuits() -> None:
    def step(acc: int, x: int) -> Any:
        if x == 2:
            return w_err(f"e{x}", f"e_log{x}")
        return w_ok(acc + x, f"a{x}")

    wr = await fold_writer([1, 2, 3], step, initial=0)()
    assert wr.result == Error("e2")
    assert list(wr.log) == ["a1", "e_log2"]


# -- transform writers --

async def test_tap_writer_runs_only_on_ok() -> None:
    c = Counter()
    wr_ok = await tap_writer(w_ok(1, "lg"), effect=c)()
    wr_err = await tap_writer(w_err("e", "lg"), effect=c)()
    assert wr_ok.result == Ok(1) and wr_err.result == Error("e")
    assert c.values == [1]


async def test_tap_async_writer() -> None:
    c = Counter()
    wr_ok = await tap_async_writer(w_ok(1, "lg"), effect=c.acall)()
    wr_err = await tap_async_writer(w_err("e", "lg"), effect=c.acall)()
    assert wr_ok.result == Ok(1) and wr_err.result == Error("e")
    assert c.values == [1]


async def test_tap_err_writer() -> None:
    c = Counter()
    wr_ok = await tap_err_writer(w_ok(1, "lg"), effect=c)()
    wr_err = await tap_err_writer(w_err("e", "lg"), effect=c)()
    assert wr_ok.result == Ok(1) and wr_err.result == Error("e")
    assert c.values == ["e"]


async def test_tap_err_async_writer() -> None:
    c = Counter()
    wr_ok = await tap_err_async_writer(w_ok(1, "lg"), effect=c.acall)()
    wr_err = await tap_err_async_writer(w_err("e", "lg"), effect=c.acall)()
    assert wr_ok.result == Ok(1) and wr_err.result == Error("e")
    assert c.values == ["e"]


async def test_bimap_tap_writer() -> None:
    okc, errc = Counter(), Counter()
    await bimap_tap_writer(w_ok(1, "a"), on_ok=okc, on_err=errc)()
    await bimap_tap_writer(w_err("e", "b"), on_ok=okc, on_err=errc)()
    assert okc.values == [1] and errc.values == ["e"]


async def test_filter_or_writer() -> None:
    wr = await filter_or_writer(w_ok(5, "lg"), predicate=lambda x: x > 0, error=lambda x: "neg")()
    assert wr.result == Ok(5)
    wr2 = await filter_or_writer(w_ok(-1, "lg"), predicate=lambda x: x > 0, error=lambda x: f"neg:{x}")()
    assert wr2.result == Error("neg:-1")


# -- selection writers --

async def test_best_of_writer() -> None:
    n = {"x": 0}

    async def run() -> WriterResult[int, str, Log[str]]:
        n["x"] += 1
        return WriterResult(Ok(n["x"]), Log.of(f"n{n['x']}"))

    wr = await best_of_writer(LazyCoroResultWriter(run), n=4, key=lambda x: float(x))()
    assert wr.result == Ok(4)


async def test_best_of_many_writer() -> None:
    wr = await best_of_many_writer([w_ok(2, "a"), w_ok(7, "b"), w_ok(5, "c")], key=lambda x: float(x))()
    assert wr.result == Ok(7)


async def test_vote_writer() -> None:
    async def judge(values: Any) -> str:
        return max(set(values), key=list(values).count)

    wr = await vote_writer([w_ok("a", "1"), w_ok("a", "2"), w_ok("b", "3")], judge=judge)()
    assert wr.result == Ok("a")


# -- delay / timeout writer --

async def test_delay_writer_passes_through() -> None:
    wr = await delay_writer(w_ok(1, "lg"), seconds=0.0)()
    assert wr.result == Ok(1) and list(wr.log) == ["lg"]


async def test_timeout_writer_completes_quickly() -> None:
    wr = await timeout_writer(w_ok(1, "lg"), seconds=1.0)()
    assert wr.result == Ok(1) and list(wr.log) == ["lg"]


async def test_timeout_writer_fires() -> None:
    import asyncio
    from combinators import TimeoutError

    async def run() -> WriterResult[int, str, Log[str]]:
        await asyncio.sleep(0.05)
        return WriterResult(Ok(1), Log.of("never"))

    wr = await timeout_writer(LazyCoroResultWriter(run), seconds=0.005)()
    assert isinstance(wr.result, Error) and isinstance(wr.result.error, TimeoutError)


# -- race writer / race_ok writer --

async def test_race_writer_takes_first_completed() -> None:
    import asyncio

    async def fast() -> WriterResult[str, str, Log[str]]:
        return WriterResult(Ok("fast"), Log.of("a"))

    async def slow() -> WriterResult[str, str, Log[str]]:
        await asyncio.sleep(0.05)
        return WriterResult(Ok("slow"), Log.of("b"))

    wr = await race_writer(LazyCoroResultWriter(fast), LazyCoroResultWriter(slow))()
    assert wr.result == Ok("fast")


async def test_race_ok_writer_picks_first_ok() -> None:
    import asyncio

    async def err_fast() -> WriterResult[str, str, Log[str]]:
        return WriterResult(Error("e"), Log.of("a"))

    async def ok_slow() -> WriterResult[str, str, Log[str]]:
        await asyncio.sleep(0.02)
        return WriterResult(Ok("ok"), Log.of("b"))

    wr = await race_ok_writer(
        LazyCoroResultWriter(err_fast),
        LazyCoroResultWriter(ok_slow),
    )()
    assert wr.result == Ok("ok")


async def test_rate_limit_writer_passes_through() -> None:
    wr = await rate_limit_writer(w_ok(1, "lg"), policy=RateLimitPolicy(max_per_second=100))()
    assert wr.result == Ok(1)


# -- module top-level imports --

def test_writer_namespace_exports() -> None:
    assert writer.LazyCoroResultWriter is LazyCoroResultWriter
    assert writer.Log is Log
    assert writer.WriterResult is WriterResult
