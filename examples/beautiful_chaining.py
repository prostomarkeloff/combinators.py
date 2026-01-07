from __future__ import annotations

from _infra import Failure, FakeBackend, banner, run

from combinators import flow, lift as L
from kungfu import Error, Ok, Result


async def parse_user_id(text: str) -> Result[int, Failure]:
    if text.isdigit():
        return Ok(int(text))
    return Error(Failure(f"not an int: {text!r}", transient=False))


async def main() -> None:
    banner("beautiful_chaining: `.then` + locality + `.map`")

    api = FakeBackend(name="api", delay_seconds=0.01, failures_before_ok=1)
    maybe_user_id: str | None = "42"

    pipeline = (
        L.optional(maybe_user_id, error=lambda: Failure("missing user_id"))
        .then(lambda s: L.call(parse_user_id, s))
        .then(
            lambda uid: flow(L.call(api.fetch_user, uid))
            .retry(times=3, delay_seconds=0.01, retry_on=lambda e: e.transient)
            .compile()
        )
        .map(lambda user: user.name)
        .map(str.upper)
    )

    result = await pipeline
    match result:
        case Ok(name):
            print(f"ok: {name}")
        case Error(err):
            print(f"error: {err!r}")


if __name__ == "__main__":
    run(main)


