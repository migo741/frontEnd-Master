from __future__ import annotations

import importlib.util
import unittest

from solution import Checkpointer, EmailGraph, EmailState


class GraphTest(unittest.TestCase):
    def test_normal_flow_completes(self) -> None:
        checkpoint = Checkpointer()
        graph = EmailGraph(checkpoint)
        state = graph.run_until_pause(EmailState("r1", "如何登录？"))
        self.assertEqual(state.node, "done")
        self.assertTrue(state.sent)
        self.assertGreater(len(checkpoint.snapshots["r1"]), 2)

    def test_refund_pauses_and_resumes(self) -> None:
        graph = EmailGraph(Checkpointer())
        state = graph.run_until_pause(EmailState("r2", "我要退款"))
        self.assertEqual((state.node, state.approval, state.sent), ("await_approval", "pending", False))
        state.approval = "approved"
        state = graph.run_until_pause(state)
        self.assertEqual(state.node, "done")
        self.assertTrue(state.sent)

    def test_send_is_idempotent(self) -> None:
        graph = EmailGraph(Checkpointer())
        state = EmailState("r3", "x", node="send")
        graph.step(state)
        state.node = "send"  # 模拟恢复重入
        graph.step(state)
        self.assertEqual(graph.operations, {"r3:send"})

    def test_langgraph_example_is_present(self) -> None:
        self.assertIsNotNone(importlib.util.find_spec("langgraph_integration"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

