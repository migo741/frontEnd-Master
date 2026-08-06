from __future__ import annotations

import unittest

from solution import RunContext, SemanticCompiler, SemanticQuery, Ticket, TicketService


class TicketToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TicketService([
            Ticket("a", "t1", "Login failed"),
            Ticket("b", "t2", "Private billing"),
        ])
        self.user = RunContext("t1", "u1", frozenset({"ticket:read"}))
        self.approver = RunContext("t1", "manager", frozenset({"ticket:approve"}))

    def test_cross_tenant_is_indistinguishable_from_missing(self) -> None:
        with self.assertRaises(KeyError):
            self.service.get("b", self.user)
        with self.assertRaises(KeyError):
            self.service.get("missing", self.user)

    def test_control_field_injection_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "控制字段"):
            self.service.propose("p", "comment", "a", {"comment": "x", "tenant_id": "t2"}, self.user)

    def test_approval_hash_and_idempotency(self) -> None:
        proposal = self.service.propose("p", "comment", "a", {"comment": "safe"}, self.user)
        first = self.service.execute("p", proposal.args_hash, "op1", self.approver)
        second = self.service.execute("p", proposal.args_hash, "op1", self.approver)
        self.assertEqual(first, second)
        self.assertEqual(self.service.get("a", self.user).comments, ["safe"])

    def test_tampered_and_unapproved_fail(self) -> None:
        proposal = self.service.propose("p", "change_status", "a", {"status": "closed"}, self.user)
        with self.assertRaises(PermissionError):
            self.service.execute("p", "tampered", "op", self.approver)
        with self.assertRaises(PermissionError):
            self.service.execute("p", proposal.args_hash, "op", self.user)

    def test_resource_version_requires_reapproval(self) -> None:
        first = self.service.propose("p1", "comment", "a", {"comment": "one"}, self.user)
        second = self.service.propose("p2", "comment", "a", {"comment": "two"}, self.user)
        self.service.execute("p1", first.args_hash, "op1", self.approver)
        with self.assertRaisesRegex(RuntimeError, "re-approval"):
            self.service.execute("p2", second.args_hash, "op2", self.approver)


class SemanticQueryTest(unittest.TestCase):
    def test_tenant_is_compiler_injected_and_values_parameterized(self) -> None:
        query = SemanticQuery("tickets", ("status",), "count", {"status": "closed' OR 1=1 --"}, 10)
        sql, params = SemanticCompiler().compile(query, RunContext("t1", "u", frozenset()))
        self.assertIn("tenant_id = ?", sql)
        self.assertNotIn("OR 1=1", sql)
        self.assertEqual(params[0], "t1")
        self.assertIn("OR 1=1", params[1])

    def test_pii_dimension_rejected(self) -> None:
        query = SemanticQuery("tickets", ("email",), "count", {}, 10)
        with self.assertRaises(PermissionError):
            SemanticCompiler().compile(query, RunContext("t", "u", frozenset()))


if __name__ == "__main__":
    unittest.main(verbosity=2)

