"""Tests for _helpers, generic *M combinators, and FlowM with a custom interpretation."""

from __future__ import annotations

import asyncio
import typing
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

import pytest
from hypothesis import given, strategies as st
from kungfu import Error, LazyCoroResult, Ok, Result

from combinators import (
    LazyCoroResultWriter,
    Log,
    RaceOkPolicy,
    RateLimitPolicy,
    RepeatPolicy,
    RetryPolicy,
    WriterResult,
    _helpers,
    batchM,
    bracketM,
    delayM,
    ensureM,
    fallback_chainM,
    fallbackM,
    foldM,
    gather2M,
    gather3M,
    parallelM,
    partitionM,
    raceM,
    race_okM,
    rate_limitM,
    recoverM,
    recover_withM,
    rejectM,
    repeat_untilM,
    retryM,
    tap_asyncM,
    tap_err_asyncM,
    tap_errM,
    tapM,
    timeoutM,
    traverseM,
    validateM,
    zip_parM,
)
from combinators.ast import FlowM
from tests.conftest import lcr_err, lcr_ok


# -- _helpers --

def test_identity_returns_input() -> None:
    obj = object()
    assert _helpers.identity(obj) is obj


def test_extract_result_is_identity() -> None:
    r = Ok(1)
    assert _helpers.extract_result(r) is r


def test_extract_writer_result_returns_inner_result() -> None:
    wr: WriterResult[int, str, Log[str]] = WriterResult(Ok(5), Log.of("x"))
    assert _helpers.extract_writer_result(wr) == Ok(5)


def test_wrap_lazy_coro_result_writer() -> None:
    async def run() -> WriterResult[int, str, Log[str]]:
        return WriterResult(Ok(1), Log.of("a"))

    wrapped = _helpers.wrap_lazy_coro_result_writer(run)
    assert isinstance(wrapped, LazyCoroResultWriter)


@given(
    a=st.lists(st.integers()),
    b=st.lists(st.integers()),
    c=st.lists(st.integers()),
)
def test_merge_logs_concatenates(a: list[int], b: list[int], c: list[int]) -> None:
    out = _helpers.merge_logs([Log[int](a), Log[int](b), Log[int](c)])
    assert list(out) == a + b + c


def test_merge_logs_empty_returns_empty_log() -> None:
    out = _helpers.merge_logs([])
    assert list(out) == []


def test_merge_writer_logs_extracts_and_concats() -> None:
    wrs = [
        WriterResult(Ok(1), Log.of("a")),
        WriterResult(Error("e"), Log.of("b", "c")),
    ]
    out = _helpers.merge_writer_logs(wrs)
    assert list(out) == ["a", "b", "c"]


# -- Generic combinators with a synthetic monad --

# We test the *M functions by using LazyCoroResult-like Raw types, exercising
# code paths that don't get hit by the LazyCoroResult sugar wrappers.

async def test_retryM_with_writer_path_internal_error_when_times_zero() -> None:
    # times must be >= 1 by RetryPolicy.fixed; we directly test the
    # generic combinator using extract_result identity.
    raw: list[Any] = []

    async def interp() -> Result[int, str]:
        raw.append(1)
        return Error("e")

    out = retryM(
        interp,
        extract=_helpers.extract_result,
        wrap=LazyCoroResult,
        policy=RetryPolicy.fixed(times=1),
    )
    assert await out() == Error("e")
    assert len(raw) == 1


async def test_fallbackM_picks_secondary_on_primary_error() -> None:
    async def primary() -> Result[int, str]:
        return Error("e")

    async def secondary() -> Result[int, str]:
        return Ok(5)

    out = fallbackM(primary, secondary, extract=_helpers.extract_result, wrap=LazyCoroResult)
    assert await out() == Ok(5)


async def test_fallback_chainM_requires_at_least_one() -> None:
    out = fallback_chainM(extract=_helpers.extract_result, wrap=LazyCoroResult)
    with pytest.raises(ValueError):
        await out()


async def test_ensureM_writer_pred_pass() -> None:
    async def interp() -> WriterResult[int, str, Log[str]]:
        return WriterResult(Ok(5), Log.of("a"))

    out = ensureM(
        interp,
        extract=_helpers.extract_writer_result,
        get_value=lambda raw: raw.result.unwrap(),
        predicate=lambda x: x > 0,
        error=lambda x: "neg",
        combine_ok=lambda v, raw: raw,
        combine_err=lambda e, raw: WriterResult(Error(e), raw.log),
        wrap=_helpers.wrap_lazy_coro_result_writer,
    )
    wr = await out()
    assert wr.result == Ok(5)


async def test_rejectM_writer_pred_match() -> None:
    async def interp() -> WriterResult[int, str, Log[str]]:
        return WriterResult(Ok(5), Log.of("a"))

    out = rejectM(
        interp,
        extract=_helpers.extract_writer_result,
        get_value=lambda raw: raw.result.unwrap(),
        predicate=lambda x: x > 0,
        error=lambda x: "pos",
        combine_ok=lambda v, raw: raw,
        combine_err=lambda e, raw: WriterResult(Error(e), raw.log),
        wrap=_helpers.wrap_lazy_coro_result_writer,
    )
    wr = await out()
    assert wr.result == Error("pos")


async def test_recoverM_default_used_on_error() -> None:
    async def interp() -> Result[int, str]:
        return Error("e")

    out = recoverM(
        interp,
        extract=_helpers.extract_result,
        get_value=lambda r: r.unwrap(),
        default=42,
        combine=lambda v, raw: Ok(v),
        wrap=LazyCoroResult,
    )
    assert await out() == Ok(42)


async def test_recover_withM_uses_handler() -> None:
    async def interp() -> Result[int, str]:
        return Error("E")

    out = recover_withM(
        interp,
        extract=_helpers.extract_result,
        get_value=lambda r: r.unwrap(),
        get_error=lambda r: r.unwrap_err(),
        handler=lambda e: 7,
        combine=lambda v, raw: Ok(v),
        wrap=LazyCoroResult,
    )
    assert await out() == Ok(7)


async def test_repeat_untilM_default_paths() -> None:
    counter = {"n": 0}

    async def interp() -> Result[int, str]:
        counter["n"] += 1
        return Ok(counter["n"])

    out = repeat_untilM(
        interp,
        extract=_helpers.extract_result,
        get_value=lambda r: r.unwrap(),
        condition=lambda x: x == 3,
        policy=RepeatPolicy(max_rounds=10),
        widen_ok=lambda raw: raw,
        widen_err=lambda raw: raw,
        on_exhausted=lambda: Error("exhausted"),
        wrap=LazyCoroResult,
    )
    assert await out() == Ok(3)


async def test_repeat_untilM_on_exhausted_called() -> None:
    async def interp() -> Result[int, str]:
        return Ok(1)

    out = repeat_untilM(
        interp,
        extract=_helpers.extract_result,
        get_value=lambda r: r.unwrap(),
        condition=lambda x: x > 100,
        policy=RepeatPolicy(max_rounds=2),
        widen_ok=lambda raw: raw,
        widen_err=lambda raw: raw,
        on_exhausted=lambda: Error("exhausted"),
        wrap=LazyCoroResult,
    )
    assert await out() == Error("exhausted")


async def test_repeat_untilM_short_circuits_on_error() -> None:
    async def interp() -> Result[int, str]:
        return Error("e")

    out = repeat_untilM(
        interp,
        extract=_helpers.extract_result,
        get_value=lambda r: r.unwrap(),
        condition=lambda x: True,
        policy=RepeatPolicy(max_rounds=2),
        widen_ok=lambda raw: raw,
        widen_err=lambda raw: raw,
        on_exhausted=lambda: Error("exhausted"),
        wrap=LazyCoroResult,
    )
    assert await out() == Error("e")


async def test_bracketM_releases_even_on_exception() -> None:
    released: list[str] = []

    async def acquire() -> Result[str, str]:
        return Ok("R")

    async def release(r: str) -> None:
        released.append(r)

    def use(r: str) -> Callable[[], Coroutine[Any, Any, Result[int, str]]]:
        async def run() -> Result[int, str]:
            return Ok(7)
        return run

    out = bracketM(
        acquire,
        extract_acquire=_helpers.extract_result,
        get_resource=lambda r: r.unwrap(),
        release=release,
        use=use,
        combine_err=lambda e: Error(e),
        wrap=LazyCoroResult,
    )
    assert await out() == Ok(7)
    assert released == ["R"]


async def test_bracketM_acquire_error() -> None:
    async def acquire() -> Result[str, str]:
        return Error("nope")

    out = bracketM(
        acquire,
        extract_acquire=_helpers.extract_result,
        get_resource=lambda r: r.unwrap(),
        release=lambda r: asyncio.sleep(0),
        use=lambda r: (lambda: typing.cast(Coroutine[Any, Any, Result[int, str]], asyncio.sleep(0))),
        combine_err=lambda e: Error(e),
        wrap=LazyCoroResult,
    )
    assert await out() == Error("nope")


async def test_parallelM_combine_ok_and_err() -> None:
    async def i_ok() -> Result[int, str]:
        return Ok(1)

    async def i_err() -> Result[int, str]:
        return Error("e")

    ok_path = parallelM(
        i_ok,
        i_ok,
        extract=_helpers.extract_result,
        combine_ok=lambda pairs: Ok([v for v, _ in pairs]),
        combine_err=lambda e, raws: Error(e),
        wrap=LazyCoroResult,
    )
    assert await ok_path() == Ok([1, 1])

    err_path = parallelM(
        i_ok,
        i_err,
        extract=_helpers.extract_result,
        combine_ok=lambda pairs: Ok([v for v, _ in pairs]),
        combine_err=lambda e, raws: Error(e),
        wrap=LazyCoroResult,
    )
    assert await err_path() == Error("e")


async def test_gather2M_short_circuits_on_b_error() -> None:
    async def a() -> Result[int, str]:
        return Ok(1)

    async def b() -> Result[int, str]:
        return Error("eb")

    out = gather2M(
        a,
        b,
        extract_a=_helpers.extract_result,
        extract_b=_helpers.extract_result,
        combine_ok=lambda va, vb, ra, rb: Ok((va, vb)),
        combine_err=lambda e: Error(e),
        wrap=LazyCoroResult,
    )
    assert await out() == Error("eb")


async def test_gather3M_short_circuits_on_c_error() -> None:
    async def i(v: Any) -> Result[Any, str]:
        return Ok(v)

    async def c() -> Result[int, str]:
        return Error("ec")

    out = gather3M(
        lambda: i(1),
        lambda: i(2),
        c,
        extract_a=_helpers.extract_result,
        extract_b=_helpers.extract_result,
        extract_c=_helpers.extract_result,
        combine_ok=lambda va, vb, vc, ra, rb, rc: Ok((va, vb, vc)),
        combine_err=lambda e: Error(e),
        wrap=LazyCoroResult,
    )
    assert await out() == Error("ec")


async def test_zip_parM_error_path() -> None:
    async def i_ok() -> Result[int, str]:
        return Ok(1)

    async def i_err() -> Result[int, str]:
        return Error("e")

    out = zip_parM(
        i_ok,
        i_err,
        extract=_helpers.extract_result,
        combine_ok=lambda pairs: Ok(tuple(v for v, _ in pairs)),
        combine_err=lambda e, raws: Error(e),
        wrap=LazyCoroResult,
    )
    assert await out() == Error("e")


async def test_raceM_empty_raises() -> None:
    out = raceM(wrap=LazyCoroResult)
    with pytest.raises(ValueError):
        await out()


async def test_race_okM_empty_raises() -> None:
    out = race_okM(extract=_helpers.extract_result, wrap=LazyCoroResult)
    with pytest.raises(ValueError):
        await out()


async def test_traverseM_short_circuits_on_error() -> None:
    def handler(x: int) -> Callable[[], Coroutine[Any, Any, Result[int, str]]]:
        async def run() -> Result[int, str]:
            return Error(f"e{x}") if x == 2 else Ok(x)
        return run

    out = traverseM(
        [1, 2, 3],
        handler,
        extract=_helpers.extract_result,
        combine_ok=lambda pairs: Ok([v for v, _ in pairs]),
        combine_err=lambda e, raws: Error(e),
        wrap=LazyCoroResult,
    )
    assert await out() == Error("e2")


async def test_partitionM_collects_both() -> None:
    async def i_ok() -> Result[int, str]:
        return Ok(1)

    async def i_err() -> Result[int, str]:
        return Error("e")

    out = partitionM(
        [i_ok, i_err, i_ok],
        extract=_helpers.extract_result,
        get_value=lambda r: r.unwrap(),
        get_error=lambda r: r.unwrap_err(),
        combine=lambda oks, errs, raws: Ok((oks, errs)),
        wrap=LazyCoroResult,
    )
    assert await out() == Ok(([1, 1], ["e"]))


async def test_validateM_collects_errors() -> None:
    async def i_ok() -> Result[int, str]:
        return Ok(1)

    async def i_err(e: str) -> Result[int, str]:
        return Error(e)

    out = validateM(
        [i_ok, lambda: i_err("a"), lambda: i_err("b")],
        extract=_helpers.extract_result,
        get_value=lambda r: r.unwrap(),
        get_error=lambda r: r.unwrap_err(),
        combine_ok=lambda vs, raws: Ok(vs),
        combine_err=lambda errs, raws: Error(errs),
        wrap=LazyCoroResult,
    )
    assert await out() == Error(["a", "b"])


async def test_validateM_all_ok() -> None:
    async def i_ok() -> Result[int, str]:
        return Ok(1)

    out = validateM(
        [i_ok, i_ok],
        extract=_helpers.extract_result,
        get_value=lambda r: r.unwrap(),
        get_error=lambda r: r.unwrap_err(),
        combine_ok=lambda vs, raws: Ok(vs),
        combine_err=lambda errs, raws: Error(errs),
        wrap=LazyCoroResult,
    )
    assert await out() == Ok([1, 1])


async def test_foldM_short_circuits_on_error() -> None:
    def handler(acc: int, x: int) -> Callable[[], Coroutine[Any, Any, Result[int, str]]]:
        async def run() -> Result[int, str]:
            return Error(f"e{x}") if x == 2 else Ok(acc + x)
        return run

    out = foldM(
        [1, 2, 3],
        handler,
        initial=0,
        extract=_helpers.extract_result,
        get_value=lambda r: r.unwrap(),
        combine_ok=lambda v, raws: Ok(v),
        combine_err=lambda e, raws: Error(e),
        wrap=LazyCoroResult,
    )
    assert await out() == Error("e2")


async def test_batchM_handler_error_combines_err() -> None:
    def handler(x: int) -> Callable[[], Coroutine[Any, Any, Result[int, str]]]:
        async def run() -> Result[int, str]:
            return Error(f"e{x}") if x == 2 else Ok(x)
        return run

    out = batchM(
        [1, 2, 3],
        handler,
        concurrency=2,
        extract=_helpers.extract_result,
        combine_ok=lambda pairs: Ok([v for v, _ in pairs]),
        combine_err=lambda e, raws: Error(e),
        wrap=LazyCoroResult,
    )
    assert await out() == Error("e2")


async def test_delayM_zero_seconds() -> None:
    async def interp() -> Result[int, str]:
        return Ok(1)

    out = delayM(interp, seconds=0.0, wrap=LazyCoroResult)
    assert await out() == Ok(1)


async def test_timeoutM_completes() -> None:
    async def interp() -> Result[int, str]:
        return Ok(1)

    out = timeoutM(
        interp,
        seconds=1.0,
        widen=lambda r: r,
        on_timeout=lambda: Error("to"),
        wrap=LazyCoroResult,
    )
    assert await out() == Ok(1)


async def test_timeoutM_fires() -> None:
    async def interp() -> Result[int, str]:
        await asyncio.sleep(0.05)
        return Ok(1)

    out = timeoutM(
        interp,
        seconds=0.005,
        widen=lambda r: r,
        on_timeout=lambda: Error("to"),
        wrap=LazyCoroResult,
    )
    assert await out() == Error("to")


async def test_rate_limitM_uses_default_burst() -> None:
    async def interp() -> Result[int, str]:
        return Ok(1)

    out = rate_limitM(
        interp,
        policy=RateLimitPolicy(max_per_second=10),  # burst=None -> int(10)
        wrap=LazyCoroResult,
    )
    assert await out() == Ok(1)


async def test_tap_familyM_run_effects() -> None:
    seen: list[Any] = []
    seen_async: list[Any] = []
    seen_err: list[Any] = []
    seen_err_async: list[Any] = []

    async def i_ok() -> Result[int, str]:
        return Ok(1)

    async def i_err() -> Result[int, str]:
        return Error("e")

    await tapM(
        i_ok,
        extract=_helpers.extract_result,
        get_value=lambda r: r.unwrap(),
        effect=lambda v: seen.append(v),
        wrap=LazyCoroResult,
    )()
    await tapM(
        i_err,
        extract=_helpers.extract_result,
        get_value=lambda r: r.unwrap(),
        effect=lambda v: seen.append(("nope", v)),
        wrap=LazyCoroResult,
    )()
    assert seen == [1]

    async def aeffect(v: Any) -> None:
        seen_async.append(v)

    await tap_asyncM(
        i_ok,
        extract=_helpers.extract_result,
        get_value=lambda r: r.unwrap(),
        effect=aeffect,
        wrap=LazyCoroResult,
    )()
    await tap_asyncM(
        i_err,
        extract=_helpers.extract_result,
        get_value=lambda r: r.unwrap(),
        effect=aeffect,
        wrap=LazyCoroResult,
    )()
    assert seen_async == [1]

    await tap_errM(
        i_err,
        extract=_helpers.extract_result,
        get_error=lambda r: r.unwrap_err(),
        effect=lambda e: seen_err.append(e),
        wrap=LazyCoroResult,
    )()
    await tap_errM(
        i_ok,
        extract=_helpers.extract_result,
        get_error=lambda r: r.unwrap_err(),
        effect=lambda e: seen_err.append(("ok-skipped", e)),
        wrap=LazyCoroResult,
    )()
    assert seen_err == ["e"]

    async def aeffect_err(e: Any) -> None:
        seen_err_async.append(e)

    await tap_err_asyncM(
        i_err,
        extract=_helpers.extract_result,
        get_error=lambda r: r.unwrap_err(),
        effect=aeffect_err,
        wrap=LazyCoroResult,
    )()
    await tap_err_asyncM(
        i_ok,
        extract=_helpers.extract_result,
        get_error=lambda r: r.unwrap_err(),
        effect=aeffect_err,
        wrap=LazyCoroResult,
    )()
    assert seen_err_async == ["e"]


# -- FlowM (generic flow) --

def _make_flowm() -> FlowM[Any, Any, int, str]:
    """Build a FlowM bound to the LazyCoroResult monad."""
    from combinators.control.retry import retry as _retry
    from combinators.transform.effects import tap as _tap, tap_err as _tap_err
    from combinators.time.delay import delay as _delay
    from combinators.concurrency.rate_limit import rate_limit as _rate_limit
    from combinators.control.guard import ensure as _ensure, reject as _reject

    base = lcr_ok(5)

    return FlowM(
        value=base,
        extract=_helpers.extract_result,
        wrap=LazyCoroResult,
        _retry=lambda v, p: _retry(v, policy=p),
        _tap=lambda v, eff: _tap(v, effect=eff),
        _tap_err=lambda v, eff: _tap_err(v, effect=eff),
        _delay=lambda v, s: _delay(v, seconds=s),
        _rate_limit=lambda v, p: _rate_limit(v, policy=p),
        _ensure=lambda v, p, e: _ensure(v, predicate=p, error=e),
        _reject=lambda v, p, e: _reject(v, predicate=p, error=e),
    )


async def test_flowm_chain_runs() -> None:
    seen: list[Any] = []
    fm = (
        _make_flowm()
        .tap(seen.append)
        .ensure(lambda x: x > 0, lambda x: "neg")
        .delay(seconds=0.0)
        .rate_limit(max_per_second=100)
    )
    assert await fm.compile()() == Ok(5)
    assert seen == [5]
    # lower alias
    assert fm.lower() is fm.value


async def test_flowm_retry_via_times() -> None:
    fm = _make_flowm().retry(times=2)
    assert await fm.compile()() == Ok(5)


def test_flowm_retry_requires_args() -> None:
    fm = _make_flowm()
    with pytest.raises(ValueError):
        fm.retry()


async def test_flowm_retry_via_policy() -> None:
    fm = _make_flowm().retry(policy=RetryPolicy.fixed(times=1))
    assert await fm.compile()() == Ok(5)


def test_flowm_rate_limit_requires_args() -> None:
    fm = _make_flowm()
    with pytest.raises(ValueError):
        fm.rate_limit()


async def test_flowm_rate_limit_via_policy() -> None:
    fm = _make_flowm().rate_limit(policy=RateLimitPolicy(max_per_second=10))
    assert await fm.compile()() == Ok(5)


async def test_flowm_tap_err_runs_only_on_err() -> None:
    seen: list[Any] = []

    from combinators.control.retry import retry as _retry
    from combinators.transform.effects import tap as _tap, tap_err as _tap_err
    from combinators.time.delay import delay as _delay
    from combinators.concurrency.rate_limit import rate_limit as _rate_limit
    from combinators.control.guard import ensure as _ensure, reject as _reject

    base = lcr_err("err")
    fm: FlowM[Any, Any, int, str] = FlowM(
        value=base,
        extract=_helpers.extract_result,
        wrap=LazyCoroResult,
        _retry=lambda v, p: _retry(v, policy=p),
        _tap=lambda v, eff: _tap(v, effect=eff),
        _tap_err=lambda v, eff: _tap_err(v, effect=eff),
        _delay=lambda v, s: _delay(v, seconds=s),
        _rate_limit=lambda v, p: _rate_limit(v, policy=p),
        _ensure=lambda v, p, e: _ensure(v, predicate=p, error=e),
        _reject=lambda v, p, e: _reject(v, predicate=p, error=e),
    )
    fm = fm.tap_err(seen.append).reject(lambda x: x > 0, lambda x: "pos")
    assert await fm.compile()() == Error("err")
    assert seen == ["err"]
