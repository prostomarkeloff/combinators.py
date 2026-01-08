from __future__ import annotations

import asyncio

from _infra import Failure, User, banner, run

from combinators import flow, lift as L
from kungfu import Error, Ok, Result


class APIException(Exception):
    """Simulates HTTP client exception (like aiohttp.ClientError)."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"{status}: {message}")


class FakeHTTPClient:
    """Simulates third-party HTTP client that raises exceptions instead of returning Result."""

    def __init__(self, *, fail_count: int = 0, delay_seconds: float = 0.0) -> None:
        self.fail_count = fail_count
        self.delay_seconds = delay_seconds

    async def get_user(self, user_id: int) -> User:
        """Returns User or RAISES APIException. Does NOT return Result."""
        await asyncio.sleep(self.delay_seconds)
        if self.fail_count > 0:
            self.fail_count -= 1
            raise APIException(status=503, message="Service Unavailable")
        return User(id=user_id, name=f"user:{user_id}@http-api")


# ============================================================================
# Approach 1: L.call_catching (function-based lifting)
# ============================================================================


async def fetch_user_with_call_catching(
    client: FakeHTTPClient,
    user_id: int,
) -> Result[User, Failure]:
    """Lift exception-raising function into Result using L.call_catching."""
    return await L.call_catching(
        client.get_user,
        on_error=lambda e: Failure(
            message=f"API error: {e}",
            transient=isinstance(e, APIException) and e.status >= 500,
        ),
        user_id=user_id,
    )


# ============================================================================
# Approach 2: @L.lifted decorator (for your own functions)
# ============================================================================


class SafeUserService:
    """Your service layer that wraps exception-raising client."""

    def __init__(self, client: FakeHTTPClient) -> None:
        self.client = client

    @L.lifted
    async def get_user(self, user_id: int) -> Result[User, Failure]:
        """
        Decorated function: auto-lifts Result[T, E] -> Interp[T, E].

        This is DIFFERENT from call_catching!
        - call_catching: for functions that RAISE exceptions -> catches them
        - @lifted: for functions that already RETURN Result -> just wraps in Interp
        """
        # Inside: we still need to catch exceptions ourselves
        try:
            user = await self.client.get_user(user_id=user_id)
            return Ok(user)
        except APIException as e:
            return Error(
                Failure(
                    message=f"API error: {e}",
                    transient=e.status >= 500,
                )
            )


# ============================================================================
# Main demo
# ============================================================================


async def main() -> None:
    banner("04_call_catching: Lift exception-raising functions into Result")

    user_id = 42

    # ========================================================================
    # Demo 1: call_catching - for third-party libs that raise
    # ========================================================================
    print("\n[Demo 1: L.call_catching for exception-raising functions]")

    client1 = FakeHTTPClient(fail_count=2, delay_seconds=0.01)

    pipeline1 = (
        flow(L.call(fetch_user_with_call_catching, client=client1, user_id=user_id))
        .retry(times=3, delay_seconds=0.01, retry_on=lambda e: e.transient)
        .timeout(seconds=1.0)
        .compile()
    )

    result1 = await pipeline1
    match result1:
        case Ok(user):
            print(f"  ✓ Success: {user.name}")
        case Error(err):
            print(f"  ✗ Error: {err}")

    # ========================================================================
    # Demo 2: @lifted decorator - for your own service functions
    # ========================================================================
    print("\n[Demo 2: @L.lifted decorator for your service layer]")

    client2 = FakeHTTPClient(fail_count=1, delay_seconds=0.01)
    service = SafeUserService(client=client2)

    # service.get_user returns Interp[User, Failure] thanks to @lifted
    pipeline2 = (
        flow(service.get_user(user_id=user_id))
        .retry(times=2, delay_seconds=0.01)
        .tap(lambda user: print(f"  → Fetched: {user.name}"))
        .compile()
    )

    result2 = await pipeline2
    match result2:
        case Ok(user):
            print(f"  ✓ Success: {user.name}")
        case Error(err):
            print(f"  ✗ Error: {err}")

    # ========================================================================
    # Demo 3: Direct call_catching in pipeline (inline)
    # ========================================================================
    print("\n[Demo 3: Inline call_catching in pipeline]")

    client3 = FakeHTTPClient(fail_count=0, delay_seconds=0.01)

    pipeline3 = (
        flow(
            L.call_catching(
                client3.get_user,
                on_error=lambda e: Failure(message=str(e), transient=True),
                user_id=user_id,
            )
        )
        .ensure(
            predicate=lambda user: user.is_active,
            error=lambda user: Failure(message=f"User {user.id} is inactive"),
        )
        .compile()
        .map(lambda user: user.name.upper())
    )

    result3 = await pipeline3
    match result3:
        case Ok(name):
            print(f"  ✓ Success: {name}")
        case Error(err):
            print(f"  ✗ Error: {err}")


if __name__ == "__main__":
    run(main)

