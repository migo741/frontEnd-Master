from __future__ import annotations

import unittest

from solution import Conflict, DurableStore


class DurableRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DurableStore()
        self.store.create_run("r1", {"node": "start"})

    def test_checkpoint_survives_and_versions_events(self) -> None:
        token = self.store.claim_run("r1", "w1", 10, now=100)
        version = self.store.append_event("r1", "w1", token, 0, "planned", {"node": "approval"}, now=101)
        self.assertEqual(version, 1)
        row = self.store.db.execute("SELECT kind FROM events WHERE run_id='r1'").fetchone()
        self.assertEqual(row["kind"], "planned")

    def test_fencing_blocks_zombie_worker_after_reclaim(self) -> None:
        old = self.store.claim_run("r1", "old", 2, now=100)
        new = self.store.claim_run("r1", "new", 10, now=103)
        self.assertGreater(new, old)
        with self.assertRaisesRegex(Conflict, "stale"):
            self.store.append_event("r1", "old", old, 0, "bad", {}, now=104)

    def test_optimistic_version_prevents_lost_update(self) -> None:
        token = self.store.claim_run("r1", "w", 10, now=100)
        self.store.append_event("r1", "w", token, 0, "one", {}, now=101)
        with self.assertRaisesRegex(Conflict, "version"):
            self.store.append_event("r1", "w", token, 0, "two", {}, now=102)

    def test_approval_binds_exact_arguments_and_expiry(self) -> None:
        digest = self.store.create_proposal("p1", "r1", {"amount": 100, "vendor": "v1"}, 200)
        with self.assertRaises(Conflict):
            self.store.approve("p1", "alice", "tampered", now=150)
        self.store.approve("p1", "alice", digest, now=150)
        status = self.store.db.execute("SELECT status FROM proposals WHERE id='p1'").fetchone()["status"]
        self.assertEqual(status, "approved")

    def test_expired_proposal_cannot_be_approved(self) -> None:
        digest = self.store.create_proposal("p2", "r1", {"amount": 1}, 100)
        with self.assertRaisesRegex(Conflict, "expired"):
            self.store.approve("p2", "alice", digest, now=101)

    def test_operation_id_makes_replay_idempotent(self) -> None:
        calls: list[str] = []

        def effect(operation_id: str) -> str:
            calls.append(operation_id)
            return "external-42"

        self.assertEqual(self.store.execute_once("op-1", effect), "external-42")
        self.assertEqual(self.store.execute_once("op-1", effect), "external-42")
        self.assertEqual(calls, ["op-1"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

