from __future__ import annotations

import asyncio
from dataclasses import dataclass

from _infra import Failure, banner, run

from combinators import best_of_many, flow, lift as L
from kungfu import Error, Ok, Result


@dataclass(frozen=True, slots=True)
class Draft:
    text: str
    score: float


@dataclass(slots=True)
class FakeModel:
    name: str
    delay_seconds: float
    score: float
    failures_before_ok: int = 0

    async def generate(self, prompt: str) -> Result[Draft, Failure]:
        await asyncio.sleep(self.delay_seconds)
        if self.failures_before_ok > 0:
            self.failures_before_ok -= 1
            return Error(Failure(f"{self.name}: transient failure", transient=True))
        return Ok(Draft(text=f"[{self.name}] {prompt}", score=self.score))


async def main() -> None:
    banner("09_llm_resilient_pipeline: recover → best_of_many")

    prompt = "say hello"
    models = [
        FakeModel(name="model-a", delay_seconds=0.02, score=0.6, failures_before_ok=1),
        FakeModel(name="model-b", delay_seconds=0.01, score=0.7, failures_before_ok=0),
        FakeModel(name="model-c", delay_seconds=0.03, score=0.9, failures_before_ok=2),
    ]

    candidates = [
        flow(L.call(m.generate, prompt))
        .retry(times=2, delay_seconds=0.01, retry_on=lambda e: e.transient)
        .recover_with(handler=lambda _e, *, m=m: Draft(text=f"[{m.name}] <fallback>", score=-1.0))
        .compile()
        for m in models
    ]

    winner = best_of_many(candidates, key=lambda d: d.score).map(lambda d: d.text)
    result = await winner
    match result:
        case Ok(text):
            print(f"ok: {text}")
        case _:
            # NOTE: after `.recover_with(...)` every candidate is `Interp[Draft, NoError]`,
            # so Error is uninhabited in practice. This branch exists to satisfy
            # pyright's exhaustiveness check in strict mode.
            raise RuntimeError("unreachable")


if __name__ == "__main__":
    run(main)


