from __future__ import annotations

import asyncio
import time
import unittest

from solution import InMemoryRunService, TransientError, bounded_map, call_with_retry


class AsyncEngineeringTest(unittest.IsolatedAsyncioTestCase):
    async def test_bounded_concurrency_and_order(self) -> None:
        active = maximum = 0
        lock = asyncio.Lock()

        async def worker(value: int) -> int:
            nonlocal active, maximum
            async with lock:
                active += 1
                maximum = max(maximum, active)
            await asyncio.sleep(0.002)
            async with lock:
                active -= 1
            return value * 2

        result = await bounded_map(range(20), worker, concurrency=3)
        self.assertEqual(result, [i * 2 for i in range(20)])
        self.assertLessEqual(maximum, 3)

    async def test_retry_only_transient(self) -> None:
        attempts = 0
        sleeps: list[float] = []

        async def operation() -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise TransientError("rate", retry_after=0)
            return "ok"

        async def fake_sleep(delay: float) -> None:
            sleeps.append(delay)

        result = await call_with_retry(operation, deadline=time.monotonic() + 1, sleep=fake_sleep)
        self.assertEqual(result, "ok")
        self.assertEqual(attempts, 3)
        self.assertEqual(len(sleeps), 2)

    async def test_permanent_error_not_retried(self) -> None:
        attempts = 0

        async def operation() -> None:
            nonlocal attempts
            attempts += 1
            raise ValueError("bad schema")

        with self.assertRaises(ValueError):
            await call_with_retry(operation, deadline=time.monotonic() + 1)
        self.assertEqual(attempts, 1)

    async def test_run_service_idempotent_submit_and_cancel_event(self) -> None:
        service = InMemoryRunService()
        self.assertIs(service.submit("r1"), service.submit("r1"))
        service.cancel("r1")
        events = [event async for event in service.stream("r1")]
        self.assertEqual(events, ["submitted", "cancel_requested"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

