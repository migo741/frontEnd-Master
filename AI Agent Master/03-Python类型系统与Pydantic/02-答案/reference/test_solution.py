from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime
from uuid import uuid4

try:
    from pydantic import ValidationError
except ModuleNotFoundError:
    raise unittest.SkipTest("请先在根目录安装 pyproject.toml 依赖")

from solution import EVENT_ADAPTER, RunContext, SearchArgs, SearchResult, Tool


class EventProtocolTest(unittest.TestCase):
    def base(self) -> dict:
        return {
            "version": 1,
            "run_id": uuid4(),
            "sequence": 0,
            "occurred_at": datetime.now(UTC),
        }

    def test_discriminated_event(self) -> None:
        event = EVENT_ADAPTER.validate_python({**self.base(), "type": "text_delta", "text": "hi"})
        self.assertEqual(event.type, "text_delta")

    def test_unknown_and_extra_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EVENT_ADAPTER.validate_python({**self.base(), "type": "unknown"})
        with self.assertRaises(ValidationError):
            EVENT_ADAPTER.validate_python({**self.base(), "type": "text_delta", "text": "x", "secret": "x"})

    def test_naive_time_rejected(self) -> None:
        value = {**self.base(), "type": "text_delta", "text": "x", "occurred_at": datetime.now()}
        with self.assertRaises(ValidationError):
            EVENT_ADAPTER.validate_python(value)


class ToolTest(unittest.IsolatedAsyncioTestCase):
    async def test_tool_validates_both_sides_and_injects_context(self) -> None:
        async def handler(args: SearchArgs, context: RunContext) -> SearchResult:
            return SearchResult(ids=[f"{context.tenant_id}:{args.query}"])

        tool = Tool(name="search", args_model=SearchArgs, result_model=SearchResult, handler=handler)
        context = RunContext(tenant_id="t1", user_id="u1", scopes=frozenset({"read"}))
        result = await tool.execute({"query": "agent", "top_k": 3}, context)
        self.assertEqual(result.ids, ["t1:agent"])
        self.assertNotIn("tenant_id", json.dumps(tool.input_schema()))

    async def test_unknown_and_coercion_rejected(self) -> None:
        tool = Tool(
            name="search",
            args_model=SearchArgs,
            result_model=SearchResult,
            handler=lambda args, ctx: SearchResult(ids=[]),
        )
        context = RunContext(tenant_id="t", user_id="u", scopes=frozenset())
        with self.assertRaises(ValidationError):
            await tool.execute({"query": "x", "top_k": "5"}, context)
        with self.assertRaises(ValidationError):
            await tool.execute({"query": "x", "unknown": 1}, context)


if __name__ == "__main__":
    unittest.main(verbosity=2)

