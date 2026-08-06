from __future__ import annotations

import unittest

from solution import Fact, MemoryProposal, MemoryStore, compress_context


class MemoryTest(unittest.TestCase):
    def proposal(self, **kwargs) -> MemoryProposal:
        values = dict(proposal_id="p", tenant_id="t1", subject_id="u1", kind="preference", value="中文", source="user", ttl_seconds=3600)
        values.update(kwargs)
        return MemoryProposal(**values)

    def test_store_update_and_conflict(self) -> None:
        store = MemoryStore()
        first = store.approve_and_store(self.proposal(), actor_roles=frozenset(), expected_version=0)
        second = store.approve_and_store(self.proposal(value="English"), actor_roles=frozenset(), expected_version=1)
        self.assertEqual((first.version, second.version), (1, 2))
        with self.assertRaises(RuntimeError):
            store.approve_and_store(self.proposal(value="stale"), actor_roles=frozenset(), expected_version=1)

    def test_policy_and_sensitive_controls(self) -> None:
        store = MemoryStore()
        with self.assertRaises(PermissionError):
            store.approve_and_store(self.proposal(kind="org_policy"), actor_roles=frozenset())
        with self.assertRaises(PermissionError):
            store.approve_and_store(self.proposal(sensitive=True), actor_roles=frozenset({"org_admin"}))

    def test_cross_tenant_and_delete(self) -> None:
        store = MemoryStore()
        store.approve_and_store(self.proposal(), actor_roles=frozenset())
        self.assertIsNone(store.get("t2", "u1", "preference"))
        store.delete("t1", "u1", "preference")
        self.assertIsNone(store.get("t1", "u1", "preference"))
        self.assertTrue(store.tombstoned(("t1", "u1", "preference")))

    def test_compression_keeps_authoritative_fact_and_recent_messages(self) -> None:
        context = compress_context([
            Fact("order", "old", "chat", 1),
            Fact("order", "verified", "orders:v2", 10),
            Fact("identity", "yes", "auth:1", 10),
        ], [f"m{i}" for i in range(100)], max_messages=3)
        self.assertEqual({f.name: f.value for f in context.facts}["order"], "verified")
        self.assertEqual(context.recent_messages, ("m97", "m98", "m99"))
        self.assertEqual(context.omitted_message_count, 97)


if __name__ == "__main__":
    unittest.main(verbosity=2)

