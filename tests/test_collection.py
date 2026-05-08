"""Tests for collection: fold, partition, replicate, sequence, traverse, validate."""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given, settings, strategies as st
from kungfu import Error, LazyCoroResult, Ok, Result

from combinators import (
    fold,
    partition,
    replicate,
    sequence,
    traverse,
    traverse_par,
    validate,
)
from tests.conftest import lcr_err, lcr_ok


# -- fold --

async def test_fold_accumulates_sequentially() -> None:
    items = [1, 2, 3, 4]

    def add(acc: int, x: int) -> Any:
        return lcr_ok(acc + x)

    out = await fold(items, add, initial=0)()
    assert out == Ok(10)


async def test_fold_short_circuits_on_error() -> None:
    items = [1, 2, 3, 4]

    def step(acc: int, x: int) -> Any:
        if x == 3:
            return lcr_err("stop")
        return lcr_ok(acc + x)

    out = await fold(items, step, initial=0)()
    assert out == Error("stop")


async def test_fold_empty_returns_initial() -> None:
    out = await fold([], lambda acc, x: lcr_ok(acc), initial=99)()
    assert out == Ok(99)


@given(xs=st.lists(st.integers(min_value=-50, max_value=50), max_size=20))
@settings(deadline=None, max_examples=30)
async def test_fold_property_matches_python_sum(xs: list[int]) -> None:
    out = await fold(xs, lambda acc, x: lcr_ok(acc + x), initial=0)()
    assert out == Ok(sum(xs))


# -- partition --

async def test_partition_separates_results() -> None:
    interps = [lcr_ok(1), lcr_err("a"), lcr_ok(2), lcr_err("b"), lcr_ok(3)]
    out = await partition(interps)()
    assert out == Ok(([1, 2, 3], ["a", "b"]))


async def test_partition_all_ok() -> None:
    out = await partition([lcr_ok(1), lcr_ok(2)])()
    assert out == Ok(([1, 2], []))


async def test_partition_all_err() -> None:
    out = await partition([lcr_err("a"), lcr_err("b")])()
    assert out == Ok(([], ["a", "b"]))


async def test_partition_empty() -> None:
    out = await partition([])()
    assert out == Ok(([], []))


# -- replicate --

async def test_replicate_runs_n_times() -> None:
    counter = {"n": 0}

    async def run() -> Result[int, Any]:
        counter["n"] += 1
        return Ok(counter["n"])

    out = await replicate(LazyCoroResult(run), n=4)()
    assert out == Ok([1, 2, 3, 4])
    assert counter["n"] == 4


async def test_replicate_zero_returns_empty() -> None:
    out = await replicate(lcr_ok(1), n=0)()
    assert out == Ok([])


def test_replicate_negative_raises() -> None:
    with pytest.raises(ValueError):
        replicate(lcr_ok(1), n=-1)


# -- sequence --

async def test_sequence_inverts_structure() -> None:
    out = await sequence([lcr_ok(1), lcr_ok(2), lcr_ok(3)])()
    assert out == Ok([1, 2, 3])


async def test_sequence_short_circuits_on_error() -> None:
    out = await sequence([lcr_ok(1), lcr_err("e"), lcr_ok(3)])()
    assert out == Error("e")


# -- traverse --

async def test_traverse_maps_sequentially() -> None:
    out = await traverse([1, 2, 3], lambda x: lcr_ok(x * x))()
    assert out == Ok([1, 4, 9])


async def test_traverse_short_circuits_on_handler_error() -> None:
    def h(x: int) -> Any:
        return lcr_err(f"e{x}") if x == 2 else lcr_ok(x)

    out = await traverse([1, 2, 3], h)()
    assert out == Error("e2")


async def test_traverse_par_handles_all() -> None:
    out = await traverse_par([1, 2, 3, 4], lambda x: lcr_ok(x + 1), concurrency=2)()
    assert out == Ok([2, 3, 4, 5])


# -- validate --

async def test_validate_collects_all_errors() -> None:
    interps = [lcr_ok(1), lcr_err("a"), lcr_ok(2), lcr_err("b")]
    out = await validate(interps)()
    assert out == Error(["a", "b"])


async def test_validate_returns_ok_when_all_succeed() -> None:
    out = await validate([lcr_ok(1), lcr_ok(2), lcr_ok(3)])()
    assert out == Ok([1, 2, 3])


async def test_validate_empty_returns_ok_empty() -> None:
    out = await validate([])()
    assert out == Ok([])
