"""Tests for lift.writer namespace and helpers."""

from __future__ import annotations

from kungfu import Error, Ok, Result

from combinators import LazyCoroResultWriter, Log, WriterResult, lift as L
from combinators.lift import writer as wlift
from combinators.lift.writer import down as wdown


async def test_writer_up_pure_with_log() -> None:
    interp = wlift.up.pure(7, log=["a", "b"])
    wr = await interp()
    assert wr.result == Ok(7)
    assert list(wr.log) == ["a", "b"]


async def test_writer_up_pure_default_no_log() -> None:
    wr = await wlift.up.pure(1)()
    assert wr.result == Ok(1)
    assert list(wr.log) == []


async def test_writer_up_tell() -> None:
    wr = await wlift.up.tell(["x", "y"])()
    assert wr.result == Ok(None)
    assert list(wr.log) == ["x", "y"]


async def test_writer_up_from_result_ok() -> None:
    wr = await wlift.up.from_result(Ok(3), log=["lg"])()
    assert wr.result == Ok(3)
    assert list(wr.log) == ["lg"]


async def test_writer_up_from_result_err() -> None:
    wr = await wlift.up.from_result(Error("e"))()
    assert wr.result == Error("e")
    assert list(wr.log) == []


async def test_writer_up_fail() -> None:
    wr = await wlift.up.fail("boom", log=["a"])()
    assert wr.result == Error("boom")
    assert list(wr.log) == ["a"]


async def test_writer_down_to_writer_result() -> None:
    interp = wlift.up.pure(1, log=["a"])
    wr = await wdown.to_writer_result(interp)
    assert wr.result == Ok(1) and list(wr.log) == ["a"]


async def test_writer_down_to_result_discards_log() -> None:
    r = await wdown.to_result(wlift.up.pure(1, log=["a"]))
    assert r == Ok(1)


async def test_writer_down_to_tuple() -> None:
    r, log = await wdown.to_tuple(wlift.up.pure(1, log=["a"]))
    assert r == Ok(1) and list(log) == ["a"]


async def test_writer_down_unsafe() -> None:
    val, log = await wdown.unsafe(wlift.up.pure(7, log=["a"]))
    assert val == 7 and list(log) == ["a"]


async def test_writer_down_or_else_ok() -> None:
    val, log = await wdown.or_else(wlift.up.pure(2, log=["a"]), default=99)
    assert val == 2 and list(log) == ["a"]


async def test_writer_down_or_else_uses_default() -> None:
    val, log = await wdown.or_else(wlift.up.fail("e", log=["a"]), default=99)
    assert val == 99 and list(log) == ["a"]


async def test_writer_call() -> None:
    async def fn(x: int) -> WriterResult[int, str, Log[str]]:
        return WriterResult(Ok(x + 1), Log.of("lg"))

    wr = await wlift.call(fn, 41)()
    assert wr.result == Ok(42) and list(wr.log) == ["lg"]


async def test_writer_lifted_decorator() -> None:
    @wlift.lifted
    async def add(a: int, b: int) -> WriterResult[int, str, Log[str]]:
        return WriterResult(Ok(a + b), Log.of("sum"))

    wr = await add(2, 3)()
    assert wr.result == Ok(5) and list(wr.log) == ["sum"]


def test_lift_writer_namespace_aliases() -> None:
    # Make sure the namespace re-exports are wired
    assert L.writer is wlift
    assert L.writer.up is wlift.up
    assert L.writer.down is wlift.down
