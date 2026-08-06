from __future__ import annotations

import ast
from pathlib import Path
import unittest

from solution import FixedWindowLimiter, McpError, Principal, Ticket, TicketTools


class McpTicketTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TicketTools([
            Ticket("t-a", "a", "Login", "reset password"),
            Ticket("t-b", "b", "Secret", "internal"),
            Ticket("t-c", "a", "Invoice", "download invoice"),
        ])
        self.a = Principal("a", "u1", frozenset({"tickets:read"}))

    def test_cross_tenant_read_is_indistinguishable_from_missing(self) -> None:
        with self.assertRaisesRegex(McpError, "not found"):
            self.service.read_ticket(self.a, "t-b")
        with self.assertRaisesRegex(McpError, "not found"):
            self.service.read_ticket(self.a, "t-z")

    def test_search_filters_before_pagination(self) -> None:
        result = self.service.search_tickets(self.a, "", limit=1)
        self.assertEqual([item["id"] for item in result["items"]], ["t-a"])
        self.assertEqual(result["next_cursor"], 1)

    def test_schema_and_bounds_reject_overlarge_input(self) -> None:
        with self.assertRaises(McpError):
            self.service.search_tickets(self.a, "x" * 201)
        with self.assertRaises(McpError):
            self.service.search_tickets(self.a, "", limit=51)

    def test_rate_limit_is_per_principal(self) -> None:
        service = TicketTools([], FixedWindowLimiter(1))
        service.search_tickets(self.a, "")
        with self.assertRaisesRegex(McpError, "rate limit"):
            service.search_tickets(self.a, "")

    def test_scope_is_required(self) -> None:
        with self.assertRaisesRegex(McpError, "forbidden"):
            self.service.search_tickets(Principal("a", "u2", frozenset()), "")

    def test_real_server_is_parseable_and_has_tool_decorators(self) -> None:
        source = Path(__file__).with_name("mcp_server.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertGreaterEqual(source.count("@mcp.tool()"), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)

