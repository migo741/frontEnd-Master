from __future__ import annotations

import time
import unittest

from solution import Architecture, BudgetExceeded, BudgetLimits, RunBudget, choose_architecture


class AgentFoundationTest(unittest.TestCase):
    def budget(self, **overrides) -> RunBudget:
        values = dict(max_turns=2, max_tool_calls=3, max_tokens=100, max_cost_usd=1.0, deadline=time.monotonic() + 60)
        values.update(overrides)
        return RunBudget(BudgetLimits(**values))

    def test_architecture_uses_lowest_uncertainty(self) -> None:
        self.assertEqual(choose_architecture(steps_known=True, dynamic_tools=False, permission_isolation=False, parallel_specialists=False), Architecture.CODE)
        self.assertEqual(choose_architecture(steps_known=False, dynamic_tools=True, permission_isolation=False, parallel_specialists=False), Architecture.SINGLE_AGENT)

    def test_turn_token_and_cost_limits(self) -> None:
        budget = self.budget()
        budget.reserve_model(30)
        budget.settle_model(actual_tokens=10, cost_usd=0.3)
        budget.reserve_model(30)
        with self.assertRaises(BudgetExceeded):
            budget.reserve_model(1)

    def test_repeated_action_is_stopped(self) -> None:
        budget = self.budget(max_repeats=1)
        budget.reserve_tool("search", {"q": "x"})
        with self.assertRaisesRegex(BudgetExceeded, "repeated_action"):
            budget.reserve_tool("search", {"q": "x"})

    def test_canonical_args_detect_same_action(self) -> None:
        budget = self.budget(max_repeats=1)
        budget.reserve_tool("search", {"a": 1, "b": 2})
        with self.assertRaises(BudgetExceeded):
            budget.reserve_tool("search", {"b": 2, "a": 1})

    def test_no_progress(self) -> None:
        budget = self.budget(max_no_progress=1)
        budget.record_progress(1, 1)
        with self.assertRaisesRegex(BudgetExceeded, "no_progress"):
            budget.record_progress(1, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

