from __future__ import annotations

import unittest

from solution import ModelTurn, RunContext, RunState, Runtime, ScriptedModel, Tool, ToolCall, create_proposal, execute_approved


def order_tool(args, context):
    return {"tenant": context.tenant_id, "order_id": args["order_id"]}


class RuntimeTest(unittest.IsolatedAsyncioTestCase):
    def runtime(self, **kwargs) -> Runtime:
        return Runtime([Tool("get_order", True, "order:read", order_tool)], **kwargs)

    def state(self, scopes=frozenset({"order:read"})) -> RunState:
        return RunState("r1", RunContext("t1", "u1", scopes))

    async def test_tool_then_final(self) -> None:
        model = ScriptedModel([
            ModelTurn(tool_calls=(ToolCall("c1", "get_order", {"order_id": "o1"}),)),
            ModelTurn(final="done"),
        ])
        state = await self.runtime().run(model, self.state())
        self.assertEqual(state.status, "succeeded")
        result = [e for e in state.events if e["type"] == "tool_result"][0]["result"]
        self.assertEqual(result["data"]["tenant"], "t1")

    async def test_unknown_and_forbidden_are_results_not_crashes(self) -> None:
        model = ScriptedModel([
            ModelTurn(tool_calls=(ToolCall("c1", "missing", {}), ToolCall("c2", "get_order", {"order_id": "o"}))),
            ModelTurn(final="cannot complete"),
        ])
        state = await self.runtime().run(model, self.state(frozenset()))
        codes = [e["result"]["code"] for e in state.events if e["type"] == "tool_result"]
        self.assertEqual(codes, ["unknown_tool", "forbidden"])

    async def test_model_cannot_inject_tenant(self) -> None:
        model = ScriptedModel([
            ModelTurn(tool_calls=(ToolCall("c", "get_order", {"order_id": "o", "tenant_id": "victim"}),)),
            ModelTurn(final="x"),
        ])
        state = await self.runtime().run(model, self.state())
        result = [e["result"] for e in state.events if e["type"] == "tool_result"][0]
        self.assertEqual(result["code"], "control_field_injection")

    async def test_loop_detection(self) -> None:
        call = ToolCall("c", "get_order", {"order_id": "o"})
        model = ScriptedModel([ModelTurn(tool_calls=(call,)), ModelTurn(tool_calls=(call,))])
        state = await self.runtime(max_repeats=1).run(model, self.state())
        self.assertEqual(state.status, "partial")
        self.assertEqual(state.events[-1]["type"], "loop_detected")

    def test_approval_binds_hash_and_is_idempotent(self) -> None:
        proposal = create_proposal("p1", "refund", {"amount": 10})
        operations = {}
        first = execute_approved(proposal, proposal.args_hash, operations)
        second = execute_approved(proposal, proposal.args_hash, operations)
        self.assertEqual(first, second)
        with self.assertRaises(PermissionError):
            execute_approved(proposal, "tampered", operations)


if __name__ == "__main__":
    unittest.main(verbosity=2)

