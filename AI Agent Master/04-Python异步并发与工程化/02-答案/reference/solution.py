"""第 04 章：有界异步 worker、重试网关和长任务状态服务。"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Generic, TypeVar


T = TypeVar("T")
R = TypeVar("R")


async def bounded_map(
    items: Iterable[T],
    worker: Callable[[T], Awaitable[R]],
    *,
    concurrency: int,
) -> list[R]:
    if concurrency < 1:
        raise ValueError("concurrency 必须大于 0")
    queue: asyncio.Queue[tuple[int, T] | None] = asyncio.Queue(maxsize=concurrency * 2)
    results: dict[int, R] = {}

    async def produce() -> None:
        for index, item in enumerate(items):
            await queue.put((index, item))
        for _ in range(concurrency):
            await queue.put(None)

    async def consume() -> None:
        while True:
            job = await queue.get()
            try:
                if job is None:
                    return
                index, item = job
                results[index] = await worker(item)
            finally:
                queue.task_done()

    async with asyncio.TaskGroup() as group:
        group.create_task(produce())
        for _ in range(concurrency):
            group.create_task(consume())
    return [results[index] for index in range(len(results))]


class TransientError(RuntimeError):
    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


async def call_with_retry(
    operation: Callable[[], Awaitable[R]],
    *,
    deadline: float,
    max_attempts: int = 3,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> R:
    for attempt in range(1, max_attempts + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("总 deadline 已耗尽")
        try:
            async with asyncio.timeout(remaining):
                return await operation()
        except TransientError as exc:
            if attempt == max_attempts:
                raise
            delay = exc.retry_after if exc.retry_after is not None else min(0.05 * 2 ** (attempt - 1), 1.0)
            delay += random.random() * 0.001
            if delay >= deadline - time.monotonic():
                raise TimeoutError("没有足够预算重试") from exc
            await sleep(delay)
    raise AssertionError("unreachable")


@dataclass
class Run:
    run_id: str
    status: str = "queued"
    cancel_requested: bool = False
    events: list[str] = field(default_factory=list)


class InMemoryRunService:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}

    def submit(self, run_id: str) -> Run:
        if run_id in self._runs:
            return self._runs[run_id]
        self._runs[run_id] = Run(run_id, events=["submitted"])
        return self._runs[run_id]

    def cancel(self, run_id: str) -> None:
        run = self._runs[run_id]
        run.cancel_requested = True
        run.events.append("cancel_requested")

    async def stream(self, run_id: str) -> AsyncIterator[str]:
        run = self._runs[run_id]
        cursor = 0
        while cursor < len(run.events):
            yield run.events[cursor]
            cursor += 1

