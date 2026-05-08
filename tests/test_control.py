"""Tests for control flow combinators: retry, fallback, guard, recover, repeat, bracket."""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given, settings, strategies as st
from kungfu import Error, Ok

from combinators import (
    ConditionNotMetError,
    RepeatPolicy,
    RetryPolicy,
    bracket,
    bracket_on_error,
    ensure,
    fallback,
    fallback_chain,
    fallback_with,
    recover,
    recover_with,
    reject,
    repeat_until,
    retry,
    with_resource,
)
from combinators.control.repeat import repeat_untilM
from combinators.control.retry import retryM
from tests.conftest import Counter, FlakyOp, lcr_err, lcr_ok


# -- RetryPolicy validation --

def test_retry_policy_times_must_be_positive() -> None:
    with pytest.raises(ValueError):
        RetryPolicy.fixed(times=0)


def test_retry_policy_fixed_negative_delay() -> None:
    with pytest.raises(ValueError):
        RetryPolicy.fixed(times=2, delay_seconds=-1.0)


def test_retry_policy_exponential_validates() -> None:
    with pytest.raises(ValueError):
        RetryPolicy.exponential(times=2, initial=-0.1)
    with pytest.raises(ValueError):
        RetryPolicy.exponential(times=2, multiplier=0.5)
    with pytest.raises(ValueError):
        RetryPolicy.exponential(times=2, initial=10.0, max_delay=1.0)


def test_retry_policy_jitter_validates() -> None:
    with pytest.raises(ValueError):
        RetryPolicy.jitter(times=2, base=-1.0)
    with pytest.raises(ValueError):
        RetryPolicy.jitter(times=2, jitter_factor=2.0)


def test_retry_policy_exponential_jitter_validates() -> None:
    with pytest.raises(ValueError):
        RetryPolicy.exponential_jitter(times=2, initial=-1)
    with pytest.raises(ValueError):
        RetryPolicy.exponential_jitter(times=2, multiplier=0.5)
    with pytest.raises(ValueError):
        RetryPolicy.exponential_jitter(times=2, initial=5, max_delay=1)
    with pytest.raises(ValueError):
        RetryPolicy.exponential_jitter(times=2, jitter_factor=-0.1)


def test_retry_policy_classmethods_construct() -> None:
    pf = RetryPolicy.fixed(times=3)
    pe = RetryPolicy.exponential(times=2)
    pj = RetryPolicy.jitter(times=2)
    pej = RetryPolicy.exponential_jitter(times=2)
    for p in (pf, pe, pj, pej):
        assert p.times >= 1
        # backoff is callable on int+error pair
        assert isinstance(p.backoff(0, "e"), float)


# -- retry semantics --

async def test_retry_succeeds_on_first_try() -> None:
    flaky = FlakyOp(fail_until=0, ok_value=42)
    out = await retry(flaky.lcr(), policy=RetryPolicy.fixed(times=3))()
    assert out == Ok(42)
    assert flaky.calls == 1


async def test_retry_succeeds_after_some_failures() -> None:
    flaky = FlakyOp(fail_until=2, ok_value="ok", err="boom")
    out = await retry(flaky.lcr(), policy=RetryPolicy.fixed(times=5))()
    assert out == Ok("ok")
    assert flaky.calls == 3


async def test_retry_exhausts_and_returns_last_error() -> None:
    flaky = FlakyOp(fail_until=10, err="permanent")
    out = await retry(flaky.lcr(), policy=RetryPolicy.fixed(times=3))()
    assert out == Error("permanent")
    assert flaky.calls == 3


async def test_retry_predicate_short_circuits() -> None:
    flaky = FlakyOp(fail_until=10, err="fatal")
    out = await retry(
        flaky.lcr(),
        policy=RetryPolicy.fixed(times=5, retry_on=lambda e: e != "fatal"),
    )()
    assert out == Error("fatal")
    assert flaky.calls == 1


@given(times=st.integers(min_value=1, max_value=8), fails=st.integers(min_value=0, max_value=12))
@settings(deadline=None, max_examples=30)
async def test_retry_call_count_property(times: int, fails: int) -> None:
    flaky = FlakyOp(fail_until=fails)
    await retry(flaky.lcr(), policy=RetryPolicy.fixed(times=times))()
    expected = min(times, fails + 1)
    assert flaky.calls == expected


# -- fallback --

async def test_fallback_uses_primary_when_ok() -> None:
    out = await fallback(lcr_ok(1), lcr_ok(2))()
    assert out == Ok(1)


async def test_fallback_uses_secondary_when_primary_fails() -> None:
    out = await fallback(lcr_err("e"), lcr_ok(2))()
    assert out == Ok(2)


async def test_fallback_returns_secondary_error_when_both_fail() -> None:
    out = await fallback(lcr_err("a"), lcr_err("b"))()
    assert out == Error("b")


async def test_fallback_with_uses_error_value() -> None:
    seen: list[Any] = []

    def mk(err: Any) -> Any:
        seen.append(err)
        return lcr_ok(f"recovered:{err}")

    out = await fallback_with(lcr_err("orig"), secondary=mk)()
    assert out == Ok("recovered:orig")
    assert seen == ["orig"]


async def test_fallback_with_keeps_ok() -> None:
    out = await fallback_with(lcr_ok(7), secondary=lambda e: lcr_ok(99))()
    assert out == Ok(7)


async def test_fallback_chain_returns_first_ok() -> None:
    out = await fallback_chain(lcr_err("a"), lcr_err("b"), lcr_ok("c"))()
    assert out == Ok("c")


async def test_fallback_chain_returns_last_error_if_all_fail() -> None:
    out = await fallback_chain(lcr_err("a"), lcr_err("b"), lcr_err("c"))()
    assert out == Error("c")


# -- guard: ensure / reject --

async def test_ensure_passes_when_predicate_true() -> None:
    out = await ensure(lcr_ok(5), predicate=lambda x: x > 0, error=lambda x: f"neg:{x}")()
    assert out == Ok(5)


async def test_ensure_fails_when_predicate_false() -> None:
    out = await ensure(lcr_ok(-1), predicate=lambda x: x > 0, error=lambda x: f"neg:{x}")()
    assert out == Error("neg:-1")


async def test_ensure_passes_through_error() -> None:
    out = await ensure(lcr_err("e"), predicate=lambda x: True, error=lambda x: "x")()
    assert out == Error("e")


async def test_reject_blocks_when_predicate_true() -> None:
    out = await reject(lcr_ok(5), predicate=lambda x: x > 0, error=lambda x: f"pos:{x}")()
    assert out == Error("pos:5")


async def test_reject_passes_when_predicate_false() -> None:
    out = await reject(lcr_ok(-1), predicate=lambda x: x > 0, error=lambda x: "pos")()
    assert out == Ok(-1)


# -- recover --

async def test_recover_swaps_error_for_default() -> None:
    out = await recover(lcr_err("e"), default=42)()
    assert out == Ok(42)


async def test_recover_keeps_ok() -> None:
    out = await recover(lcr_ok(1), default=42)()
    assert out == Ok(1)


async def test_recover_with_uses_handler() -> None:
    out = await recover_with(lcr_err(7), handler=lambda e: e * 10)()
    assert out == Ok(70)


async def test_recover_with_keeps_ok() -> None:
    out = await recover_with(lcr_ok(2), handler=lambda e: 99)()
    assert out == Ok(2)


# -- repeat --

def test_repeat_policy_validates() -> None:
    with pytest.raises(ValueError):
        RepeatPolicy(max_rounds=0)
    with pytest.raises(ValueError):
        RepeatPolicy(max_rounds=2, delay_seconds=-1.0)


async def test_repeat_until_returns_first_match() -> None:
    counter = {"n": 0}

    async def run() -> Any:
        counter["n"] += 1
        return Ok(counter["n"])

    from kungfu import LazyCoroResult
    out = await repeat_until(
        LazyCoroResult(run),
        condition=lambda x: x >= 3,
        policy=RepeatPolicy(max_rounds=10),
    )()
    assert out == Ok(3)
    assert counter["n"] == 3


async def test_repeat_until_short_circuits_on_error() -> None:
    out = await repeat_until(
        lcr_err("e"),
        condition=lambda x: True,
        policy=RepeatPolicy(max_rounds=5),
    )()
    assert out == Error("e")


async def test_repeat_until_exhausts_returns_condition_not_met() -> None:
    out = await repeat_until(
        lcr_ok(1),
        condition=lambda x: x > 100,
        policy=RepeatPolicy(max_rounds=4),
    )()
    assert isinstance(out, Error)
    err = out.error
    assert isinstance(err, ConditionNotMetError)
    assert err.rounds == 4


async def test_condition_not_met_error_message() -> None:
    e = ConditionNotMetError(7)
    assert e.rounds == 7
    assert "7" in str(e)


# -- bracket --

async def test_bracket_acquires_uses_releases() -> None:
    released: list[str] = []

    async def release(r: str) -> None:
        released.append(r)

    out = await bracket(
        lcr_ok("res"),
        release=release,
        use=lambda r: lcr_ok(f"used:{r}"),
    )()
    assert out == Ok("used:res")
    assert released == ["res"]


async def test_bracket_releases_even_on_use_error() -> None:
    released: list[str] = []

    async def release(r: str) -> None:
        released.append(r)

    out = await bracket(
        lcr_ok("res"),
        release=release,
        use=lambda r: lcr_err("use-err"),
    )()
    assert out == Error("use-err")
    assert released == ["res"]


async def test_bracket_skips_use_on_acquire_error() -> None:
    used: list[Any] = []
    released: list[Any] = []

    async def release(r: Any) -> None:
        released.append(r)

    def use(r: Any) -> Any:
        used.append(r)
        return lcr_ok("never")

    out = await bracket(
        lcr_err("no-resource"),
        release=release,
        use=use,
    )()
    assert out == Error("no-resource")
    assert used == [] and released == []


async def test_bracket_swallows_release_exception() -> None:
    async def release(r: str) -> None:
        raise RuntimeError("release failed")

    out = await bracket(
        lcr_ok("res"),
        release=release,
        use=lambda r: lcr_ok(1),
    )()
    assert out == Ok(1)


async def test_bracket_on_error_releases_only_on_error() -> None:
    released: list[str] = []

    async def release(r: str) -> None:
        released.append(r)

    out_ok = await bracket_on_error(
        lcr_ok("res"),
        release=release,
        use=lambda r: lcr_ok("done"),
    )()
    assert out_ok == Ok("done") and released == []

    out_err = await bracket_on_error(
        lcr_ok("res2"),
        release=release,
        use=lambda r: lcr_err("oops"),
    )()
    assert out_err == Error("oops") and released == ["res2"]


async def test_bracket_on_error_skips_on_acquire_error() -> None:
    released: list[Any] = []

    async def release(r: Any) -> None:
        released.append(r)

    out = await bracket_on_error(
        lcr_err("no"),
        release=release,
        use=lambda r: lcr_ok(1),
    )()
    assert out == Error("no") and released == []


async def test_bracket_on_error_swallows_release_exception() -> None:
    async def release(r: str) -> None:
        raise RuntimeError("boom")

    out = await bracket_on_error(
        lcr_ok("r"),
        release=release,
        use=lambda r: lcr_err("e"),
    )()
    assert out == Error("e")


async def test_with_resource_releases_always() -> None:
    released: list[str] = []

    async def release(r: str) -> None:
        released.append(r)

    out = await with_resource("R", release=release, use=lambda r: lcr_ok(r * 2))()
    assert out == Ok("RR")
    assert released == ["R"]


async def test_with_resource_swallows_release_error() -> None:
    async def release(r: str) -> None:
        raise RuntimeError("nope")

    out = await with_resource("R", release=release, use=lambda r: lcr_ok(1))()
    assert out == Ok(1)


# -- generic *M edge cases --

async def test_retryM_internal_error_when_times_zero_via_class() -> None:
    # Cannot construct RetryPolicy with times=0; ensure validation
    with pytest.raises(ValueError):
        RetryPolicy.fixed(times=0)


async def test_retry_with_delay_executes() -> None:
    flaky = FlakyOp(fail_until=1, ok_value="ok")
    out = await retry(flaky.lcr(), policy=RetryPolicy.fixed(times=3, delay_seconds=0.001))()
    assert out == Ok("ok")
