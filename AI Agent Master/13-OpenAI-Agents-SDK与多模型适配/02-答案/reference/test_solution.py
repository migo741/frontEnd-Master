from __future__ import annotations

import ast
from pathlib import Path
import unittest

from solution import (
    ModelProfile,
    ModelRouter,
    NoEligibleModel,
    PolicyToolExecutor,
    RoutingRequest,
    TenantPolicy,
)


MODELS = [
    ModelProfile("small", "p1", frozenset({"json"}), frozenset({"cn", "sg"}), 1, 300, .82),
    ModelProfile("agent", "p1", frozenset({"json", "tools"}), frozenset({"cn"}), 4, 600, .91),
    ModelProfile("planner", "p2", frozenset({"json", "tools", "vision"}), frozenset({"sg"}), 12, 1200, .97),
]


class RouterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.router = ModelRouter(MODELS)

    def test_routes_to_cheapest_semantically_eligible_model(self) -> None:
        request = RoutingRequest(frozenset({"json", "tools"}), "cn", 10, 1000, .9)
        chosen = self.router.route(request, TenantPolicy("t1", frozenset({"p1", "p2"})))
        self.assertEqual(chosen.name, "agent")

    def test_never_silently_downgrades_tool_semantics(self) -> None:
        request = RoutingRequest(frozenset({"tools"}), "cn", 2, 1000)
        with self.assertRaises(NoEligibleModel):
            self.router.route(request, TenantPolicy("t1", frozenset({"p1"})))

    def test_region_and_tenant_allowlist_are_enforced(self) -> None:
        request = RoutingRequest(frozenset({"vision"}), "sg", 20, 2000)
        with self.assertRaises(NoEligibleModel):
            self.router.route(request, TenantPolicy("t1", frozenset({"p1"})))

    def test_model_routing_does_not_grant_tool_permission(self) -> None:
        executor = PolicyToolExecutor({"reader": {"read_order"}})
        with self.assertRaises(PermissionError):
            executor.execute("reader", "refund", order_id="o-1")

    def test_agents_sdk_example_is_real_parseable_code(self) -> None:
        source = Path(__file__).with_name("agents_sdk_integration.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("Runner.run", source)
        self.assertIn("@function_tool", source)
        self.assertIn("output_type=OrderAnswer", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)

