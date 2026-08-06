from __future__ import annotations

import unittest

from solution import InMemoryExporter, RunMetric, accept_cost_experiment, redact, summarize


class TelemetryTest(unittest.TestCase):
    def test_redacts_payload_and_hashes_tenant(self) -> None:
        clean = redact({"prompt": "steal me", "tenant_id": "acme", "model": "evaluated-model"})
        self.assertEqual(clean["prompt"], "[REDACTED]")
        self.assertNotEqual(clean["tenant_id"], "acme")
        self.assertEqual(clean["model"], "evaluated-model")

    def test_span_exports_success_and_events(self) -> None:
        exporter = InMemoryExporter()
        with exporter.span("agent.run", tenant_id="a") as span:
            span.event("tool.call", body="private", tool="read")
        self.assertEqual(exporter.spans[0].status, "ok")
        self.assertEqual(exporter.spans[0].events[0][1]["body"], "[REDACTED]")

    def test_exception_marks_error_without_leaking_message(self) -> None:
        exporter = InMemoryExporter()
        with self.assertRaises(ValueError):
            with exporter.span("tool"):
                raise ValueError("secret contents")
        self.assertEqual(exporter.spans[0].status, "error")
        self.assertNotIn("secret contents", str(exporter.spans[0].events))

    def test_summarizes_cost_per_success_and_p95(self) -> None:
        metrics = summarize([RunMetric(True, 10, 1), RunMetric(False, 30, 1), RunMetric(True, 20, 1)])
        self.assertEqual(metrics["success_rate"], 2 / 3)
        self.assertEqual(metrics["cost_per_success"], 1.5)
        self.assertEqual(metrics["p95_ms"], 20)

    def test_cost_win_must_not_hide_quality_regression(self) -> None:
        baseline = {"success_rate": .98, "cost_per_success": 1.0}
        self.assertFalse(accept_cost_experiment(baseline, {"success_rate": .90, "cost_per_success": .3}))
        self.assertTrue(accept_cost_experiment(baseline, {"success_rate": .98, "cost_per_success": .5}))


if __name__ == "__main__":
    unittest.main(verbosity=2)

