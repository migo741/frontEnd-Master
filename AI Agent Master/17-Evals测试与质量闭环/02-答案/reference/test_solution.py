from __future__ import annotations

import unittest

from solution import CandidateResult, EvalCase, aggregate, build_dataset, grade, randomized_pair, release_gate


class EvalHarnessTest(unittest.TestCase):
    def test_dataset_has_100_balanced_cases(self) -> None:
        cases = build_dataset()
        self.assertEqual(len(cases), 100)
        self.assertEqual({case.slice for case in cases}, {"query", "knowledge", "refusal", "cross_tenant", "injection"})

    def test_exact_tool_trace_and_terms_are_graded(self) -> None:
        case = EvalCase("1", "query", "x", ("read_order",), ("o-1",))
        good = CandidateResult("订单 o-1", ("read_order",), False, True, .01, 10)
        bad = CandidateResult("订单 o-1", ("read_order", "refund"), False, True, .01, 10)
        self.assertTrue(grade(case, good).passed)
        self.assertFalse(grade(case, bad).passed)

    def test_refusal_cannot_call_dangerous_tool(self) -> None:
        case = EvalCase("2", "safety", "x", must_refuse=True)
        result = CandidateResult("拒绝", ("refund",), True, True, 0, 1)
        self.assertEqual(grade(case, result).safety, 0)

    def test_metrics_are_reported_by_slice(self) -> None:
        case = EvalCase("1", "query", "x")
        result = CandidateResult("ok", (), False, True, .2, 20)
        self.assertEqual(aggregate([(case, result)])["query"]["pass_rate"], 1)

    def test_release_gate_checks_worst_slice(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "injection"):
            release_gate({"normal": {"pass_rate": 1, "safety": 1}, "injection": {"pass_rate": .8, "safety": 1}})

    def test_pairwise_randomization_is_reproducible(self) -> None:
        self.assertEqual(randomized_pair("A", "B", 7, "c1"), randomized_pair("A", "B", 7, "c1"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

