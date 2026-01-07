from __future__ import annotations

from _infra import FakeBackend, FakeCache, User, banner, run

from combinators import fallback_chain, flow, lift as L, race_ok
from combinators.concurrency import RaceOkPolicy
from kungfu import Error, Ok


async def main() -> None:
    banner("02_cache_fallback_race_ok: race replicas → retry → fallback to cache")

    user_id = 42
    cache = FakeCache(users={user_id: User(id=user_id, name="user:42@cache")})

    replicas = [
        FakeBackend(name="replica-a", delay_seconds=0.01, failures_before_ok=10),
        FakeBackend(name="replica-b", delay_seconds=0.02, failures_before_ok=10),
        FakeBackend(name="replica-c", delay_seconds=0.03, failures_before_ok=10),
    ]

    replica_calls = [L.call(r.fetch_user, user_id) for r in replicas]
    raced = race_ok(
        *replica_calls,
        policy=RaceOkPolicy(cancel_pending=True, error_strategy="last"),
    )

    primary = (
        flow(raced)
        .retry(times=2, delay_seconds=0.01, retry_on=lambda e: e.transient)
        .tap_err(lambda e: print(f"primary failed: {e}"))
        .compile()
    )

    result = await fallback_chain(primary, L.call(cache.get_user, user_id)).map(lambda u: u.name)
    match result:
        case Ok(name):
            print(f"ok: {name}")
        case Error(err):
            print(f"error: {err!r}")


if __name__ == "__main__":
    run(main)


