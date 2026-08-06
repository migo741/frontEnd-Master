from __future__ import annotations

import unittest

from solution import ProtocolError, SessionNotFound, SessionStore, normalize_event


class SessionStoreTest(unittest.TestCase):
    def test_sessions_do_not_share_lists(self) -> None:
        store = SessionStore()
        store.create("a")
        store.create("b")
        store.append("a", {"role": "user", "content": "hi"})
        self.assertEqual(len(store.get("a").messages), 1)
        self.assertEqual(store.get("b").messages, ())

    def test_input_and_snapshot_are_defensive_copies(self) -> None:
        initial = [{"role": "user", "content": {"text": "a"}}]
        store = SessionStore()
        store.create("a", initial)
        initial[0]["content"]["text"] = "changed"
        snapshot = store.get("a")
        snapshot.meta["retries"] = 99
        self.assertEqual(store.get("a").messages[0]["content"]["text"], "a")
        self.assertEqual(store.get("a").meta["retries"], 0)

    def test_none_is_preserved(self) -> None:
        store = SessionStore()
        store.create("a")
        store.update_meta("a", "optional", None)
        self.assertIn("optional", store.get("a").meta)
        self.assertIsNone(store.get("a").meta["optional"])

    def test_round_trip(self) -> None:
        store = SessionStore()
        store.create("a")
        store.append("a", {"role": "assistant", "content": "ok"})
        restored = SessionStore.loads(store.dumps())
        self.assertEqual(restored.get("a"), store.get("a"))

    def test_invalid_json_preserves_cause(self) -> None:
        with self.assertRaises(ProtocolError) as caught:
            SessionStore.loads("{")
        self.assertIsNotNone(caught.exception.__cause__)

    def test_missing_session(self) -> None:
        with self.assertRaises(SessionNotFound):
            SessionStore().get("missing")

    def test_normalize_without_mutation(self) -> None:
        raw = {"type": "function", "id": "1", "name": "search", "arguments": {"q": "x"}}
        result = normalize_event("beta", raw)
        result["arguments"]["q"] = "changed"
        self.assertEqual(raw["arguments"]["q"], "x")

    def test_unknown_event_fails(self) -> None:
        with self.assertRaises(ProtocolError):
            normalize_event("alpha", {"kind": "new-kind"})


if __name__ == "__main__":
    unittest.main(verbosity=2)

