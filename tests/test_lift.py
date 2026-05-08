"""Tests for lift module: up, down, call."""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st
from kungfu import Error, Ok, Result

from combinators import lift as L
from combinators.lift import down, up


class _AppErr:
    def __init__(self, msg: str) -> None:
        self.msg = msg

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _AppErr) and other.msg == self.msg


# --- up ---

@given(st.integers())
async def test_pure_returns_ok(x: int) -> None:
    interp = L.pure(x)
    r = await interp()
    assert r == Ok(x)


async def test_fail_returns_error() -> None:
    err = _AppErr("nope")
    r = await L.fail(err)()
    assert r == Error(err)


@given(st.one_of(st.integers(), st.text(), st.none()))
async def test_from_result_roundtrips(v: object) -> None:
    src: Result[object, str] = Ok(v) if v is not None else Error("none")
    out = await L.from_result(src)()
    assert out == src


async def test_optional_some() -> None:
    interp = L.optional(42, error=lambda: "missing")
    assert await interp() == Ok(42)


async def test_optional_none() -> None:
    interp = L.optional(None, error=lambda: "missing")
    assert await interp() == Error("missing")


async def test_catching_ok() -> None:
    interp = L.catching(lambda: 7, on_error=lambda e: str(e))
    assert await interp() == Ok(7)


async def test_catching_exception() -> None:
    def boom() -> int:
        raise ValueError("x")

    interp = L.catching(boom, on_error=lambda e: f"err:{e}")
    out = await interp()
    assert out == Error("err:x")


async def test_catching_async_ok() -> None:
    async def fn() -> int:
        return 5

    out = await L.catching_async(fn, on_error=lambda e: "caught")()
    assert out == Ok(5)


async def test_catching_async_exception() -> None:
    async def fn() -> int:
        raise RuntimeError("kaboom")

    out = await L.catching_async(fn, on_error=lambda e: f"e:{e}")()
    assert out == Error("e:kaboom")


# Namespace alias re-exports
async def test_namespace_aliases() -> None:
    assert L.up is up
    assert L.down is down
    assert await L.up.pure(1)() == Ok(1)
    assert await L.up.fail("bad")() == Error("bad")


# --- down ---

async def test_to_result_ok_and_err() -> None:
    assert await L.to_result(L.pure(3)) == Ok(3)
    assert await L.to_result(L.fail("e")) == Error("e")


async def test_unsafe_unwraps_ok() -> None:
    assert await L.unsafe(L.pure(11)) == 11


async def test_unsafe_raises_on_error() -> None:
    with pytest.raises(BaseException):
        await L.unsafe(L.fail("x"))


async def test_or_else_ok_returns_value() -> None:
    assert await L.or_else(L.pure(2), default=99) == 2


async def test_or_else_err_returns_default() -> None:
    assert await L.or_else(L.fail("x"), default=99) == 99


# --- call/lifted/wrap_async ---

async def test_call_passes_args_and_kwargs() -> None:
    async def fn(a: int, *, b: int) -> Result[int, str]:
        return Ok(a + b)

    assert await L.call(fn, 1, b=2)() == Ok(3)


async def test_lifted_decorator() -> None:
    @L.lifted
    async def add(a: int, b: int) -> Result[int, str]:
        return Ok(a + b)

    assert await add(1, 2)() == Ok(3)


async def test_wrap_async_round_trip() -> None:
    async def fn() -> Result[int, str]:
        return Ok(7)

    assert await L.wrap_async(fn)() == Ok(7)


async def test_call_catching_ok() -> None:
    async def fn(x: int) -> int:
        return x * 2

    assert await L.call_catching(fn, lambda e: f"e:{e}", 4)() == Ok(8)


async def test_call_catching_exception() -> None:
    async def fn() -> int:
        raise KeyError("k")

    out = await L.call_catching(fn, lambda e: type(e).__name__)()
    assert out == Error("KeyError")
