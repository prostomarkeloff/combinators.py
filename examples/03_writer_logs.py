from __future__ import annotations

from _infra import Failure, FakeBackend, User, banner, run

from combinators import flow_writer, lift as L
from combinators.writer import Log, WriterResult
from kungfu import Error, Ok, Result


async def fetch_user_w(api: FakeBackend, user_id: int) -> WriterResult[User, Failure, Log[str]]:
    """
    "Pure" Writer function: returns WriterResult (Result + Log), no side effects.
    """
    result: Result[User, Failure] = await api.fetch_user(user_id)
    log: Log[str] = Log.of(f"{api.name}:fetch_user({user_id})")
    return WriterResult(result, log)


async def main() -> None:
    banner("03_writer_logs: Writer monad (value + log)")

    api = FakeBackend(name="api", delay_seconds=0.01, failures_before_ok=1)

    writer = (
        flow_writer(L.writer.call(fetch_user_w, api, 42))
        .retry(times=3, delay_seconds=0.01, retry_on=lambda e: e.transient)
        .compile()
        .map(lambda user: user.name)
        .with_log("mapped:name")
    )

    wr = await L.writer.down.to_writer_result(writer)
    match wr.result:
        case Ok(name):
            print(f"ok: {name}")
            print(f"log: {list(wr.log)!r}")
        case Error(err):
            print(f"error: {err!r}")
            print(f"log: {list(wr.log)!r}")


if __name__ == "__main__":
    run(main)
