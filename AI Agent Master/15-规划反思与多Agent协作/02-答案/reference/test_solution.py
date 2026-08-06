from __future__ import annotations

import unittest

from solution import AgentRole, Evidence, RefundExecutor, ResearchOrchestrator


class MultiAgentTest(unittest.TestCase):
    def test_report_keeps_conflicts_and_citations(self) -> None:
        def search(query: str) -> list[Evidence]:
            return [Evidence(query, "市场增长", query != "反方")]

        report = ResearchOrchestrator(search).run("正方、反方")
        self.assertEqual(report.conflicts, ("市场增长",))
        self.assertEqual(set(report.citations), {"正方", "反方"})

    def test_worker_failure_is_partial_not_infinite_retry(self) -> None:
        calls = 0

        def search(query: str) -> list[Evidence]:
            nonlocal calls
            calls += 1
            if query == "坏源":
                raise TimeoutError("source timeout")
            return [Evidence(query, "可验证结论", True)]

        report = ResearchOrchestrator(search, max_total_searches=2).run("好源、坏源、额外")
        self.assertEqual(calls, 2)
        self.assertEqual(report.failed_tasks, ("task-2",))
        self.assertIn("可验证结论", report.answer)

    def test_budget_bounds_worker_fanout(self) -> None:
        calls: list[str] = []
        ResearchOrchestrator(lambda q: calls.append(q) or [], max_workers=10, max_total_searches=2).run("a、b、c、d")
        self.assertEqual(calls, ["a", "b"])

    def test_read_only_worker_cannot_refund(self) -> None:
        worker = AgentRole("researcher", frozenset({"search:read"}))
        with self.assertRaises(PermissionError):
            RefundExecutor().execute(worker, approval=True, operation_id="op-1")

    def test_executor_still_requires_approval(self) -> None:
        executor = AgentRole("executor", frozenset({"refund:execute"}))
        with self.assertRaises(PermissionError):
            RefundExecutor().execute(executor, approval=False, operation_id="op-1")


if __name__ == "__main__":
    unittest.main(verbosity=2)

