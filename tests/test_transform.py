"""Tests for transform combinators: tap*, bimap_tap, filter_or."""

from __future__ import annotations

from typing import Any

from kungfu import Error, Ok

from combinators import (
    bimap_tap,
    filter_or,
    tap,
    tap_async,
    tap_err,
    tap_err_async,
)
from tests.conftest import Counter, lcr_err, lcr_ok


async def test_tap_runs_only_on_ok() -> None:
    c = Counter()
    out_ok = await tap(lcr_ok(5), effect=c)()
    out_err = await tap(lcr_err("e"), effect=c)()
    assert out_ok == Ok(5) and out_err == Error("e")
    assert c.n == 1 and c.values == [5]


async def test_tap_async_runs_only_on_ok() -> None:
    c = Counter()
    out_ok = await tap_async(lcr_ok("v"), effect=c.acall)()
    out_err = await tap_async(lcr_err("e"), effect=c.acall)()
    assert out_ok == Ok("v") and out_err == Error("e")
    assert c.n == 1 and c.values == ["v"]


async def test_tap_err_runs_only_on_error() -> None:
    c = Counter()
    out_ok = await tap_err(lcr_ok(1), effect=c)()
    out_err = await tap_err(lcr_err("bad"), effect=c)()
    assert out_ok == Ok(1) and out_err == Error("bad")
    assert c.n == 1 and c.values == ["bad"]


async def test_tap_err_async_runs_only_on_error() -> None:
    c = Counter()
    out_ok = await tap_err_async(lcr_ok(1), effect=c.acall)()
    out_err = await tap_err_async(lcr_err("bad"), effect=c.acall)()
    assert out_ok == Ok(1) and out_err == Error("bad")
    assert c.n == 1 and c.values == ["bad"]


async def test_bimap_tap_dispatches_both() -> None:
    okc, errc = Counter(), Counter()
    await bimap_tap(lcr_ok(1), on_ok=okc, on_err=errc)()
    await bimap_tap(lcr_err("e"), on_ok=okc, on_err=errc)()
    assert okc.values == [1] and errc.values == ["e"]


async def test_filter_or_passes_when_predicate_true() -> None:
    out = await filter_or(lcr_ok(5), predicate=lambda x: x > 0, error=lambda x: "neg")()
    assert out == Ok(5)


async def test_filter_or_fails_when_predicate_false() -> None:
    out = await filter_or(lcr_ok(-1), predicate=lambda x: x > 0, error=lambda x: f"neg:{x}")()
    assert out == Error("neg:-1")


async def test_filter_or_passes_through_existing_error() -> None:
    out = await filter_or(lcr_err("e"), predicate=lambda x: True, error=lambda x: "x")()
    assert out == Error("e")
