from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from pathlib import Path

from kungfu import Error, Ok, Result

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


@dataclass(frozen=True, slots=True)
class Failure(Exception):
    message: str
    transient: bool = False

    def __str__(self) -> str:  # pragma: no cover (examples only)
        return self.message


@dataclass(frozen=True, slots=True)
class User:
    id: int
    name: str
    is_active: bool = True


def _empty_users() -> dict[int, User]:
    return {}


@dataclass(slots=True)
class FakeBackend:
    name: str
    delay_seconds: float = 0.0
    failures_before_ok: int = 0
    failure_transient: bool = True

    async def fetch_user(self, user_id: int) -> Result[User, Failure]:
        await asyncio.sleep(self.delay_seconds)
        if self.failures_before_ok > 0:
            self.failures_before_ok -= 1
            return Error(Failure(f"{self.name}: unavailable", transient=self.failure_transient))
        return Ok(User(id=user_id, name=f"user:{user_id}@{self.name}"))


@dataclass(slots=True)
class FakeCache:
    users: dict[int, User] = field(default_factory=_empty_users)
    delay_seconds: float = 0.0

    async def get_user(self, user_id: int) -> Result[User, Failure]:
        await asyncio.sleep(self.delay_seconds)
        user = self.users.get(user_id)
        if user is None:
            return Error(Failure("cache: miss", transient=False))
        return Ok(user)

    async def put_user(self, user: User) -> Result[None, Failure]:
        self.users[user.id] = user
        return Ok(None)


def banner(title: str) -> None:  # pragma: no cover (examples only)
    print(f"\n== {title} ==")


def run(main: Callable[[], Coroutine[object, object, None]]) -> None:  # pragma: no cover (examples only)
    asyncio.run(main())
