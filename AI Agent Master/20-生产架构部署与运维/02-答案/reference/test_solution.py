from __future__ import annotations

import ast
from pathlib import Path
import unittest

from solution import CircuitBreaker, CircuitOpen, PromptRelease, TenantFairQueue, required_worker_capacity


class ProductionControlTest(unittest.TestCase):
    def test_round_robin_prevents_noisy_tenant_starvation(self) -> None:
        queue = TenantFairQueue()
        for run in ("a1", "a2", "a3"):
            queue.enqueue("a", run)
        queue.enqueue("b", "b1")
        self.assertEqual([queue.pop(), queue.pop(), queue.pop()], [("a", "a1"), ("b", "b1"), ("a", "a2")])

    def test_duplicate_delivery_is_deduplicated(self) -> None:
        queue = TenantFairQueue()
        self.assertTrue(queue.enqueue("a", "r1"))
        self.assertFalse(queue.enqueue("a", "r1"))

    def test_circuit_opens_then_allows_half_open_probe(self) -> None:
        breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=10)
        for now in (1, 2):
            with self.assertRaises(ValueError):
                breaker.call(lambda: (_ for _ in ()).throw(ValueError("429")), now=now)
        with self.assertRaises(CircuitOpen):
            breaker.call(lambda: "ok", now=5)
        self.assertEqual(breaker.call(lambda: "ok", now=13), "ok")

    def test_bad_canary_rolls_back(self) -> None:
        release = PromptRelease("v1", "v2", candidate_percent=100)
        self.assertEqual(release.select("r1"), "v2")
        release.evaluate(.98, .90)
        self.assertEqual(release.select("r1"), "v1")

    def test_capacity_uses_littles_law_with_headroom(self) -> None:
        self.assertEqual(required_worker_capacity(50, 2, .5), 200)

    def test_fastapi_app_is_real_parseable_code(self) -> None:
        source = Path(__file__).with_name("app.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn('@app.post("/v1/runs"', source)


if __name__ == "__main__":
    unittest.main(verbosity=2)

