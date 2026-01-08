from __future__ import annotations

from _infra import Failure, FakeBackend, User, banner, run

from combinators import flow, lift as L
from kungfu import Error, Ok, Result


async def fetch_user_impl(api: FakeBackend, user_id: int) -> Result[User, Failure]:
    # Locality: "pure" async function returning Result, no Interp/combinators here.
    return await api.fetch_user(user_id)


async def main() -> None:
    banner("01_quickstart: lift + flow + retry + timeout")

    api = FakeBackend(
        name="api",
        delay_seconds=0.01,
        failures_before_ok=2,
        failure_transient=True,
    )

    pipeline = (
        flow(L.call(fetch_user_impl, api, 42))
        .retry(times=3, delay_seconds=0.01, retry_on=lambda e: e.transient)
        .timeout(seconds=0.2)
        .compile()
        .map(lambda user: f"hello, {user.name}")
    )

    result = await pipeline
    match result:
        case Ok(message):
            print(message)
        case Error(err):
            print(f"error: {err!r}")


if __name__ == "__main__":
    run(main)



