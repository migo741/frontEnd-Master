from __future__ import annotations

import asyncio
import inspect
import json
import tempfile
import unittest
from pathlib import Path

from solution import ToolRegistry, ndjson_batches


class ToolRegistryTest(unittest.IsolatedAsyncioTestCase):
    async def test_preserves_signature_and_runs_sync_async(self) -> None:
        registry = ToolRegistry()

        @registry.tool(name="add")
        def add(x: int, y: int = 1) -> int:
            """Add."""
            return x + y

        @registry.tool(name="double")
        async def double(x: int) -> int:
            await asyncio.sleep(0)
            return x * 2

        self.assertEqual(str(inspect.signature(add)), "(x: 'int', y: 'int' = 1) -> 'int'")
        self.assertEqual(add.__doc__, "Add.")
        self.assertEqual(await registry.execute("add", request_id="r1", x=2), 3)
        self.assertEqual(await registry.execute("double", request_id="r2", x=3), 6)
        self.assertTrue(all(trace["ok"] for trace in registry.traces))

    async def test_failure_is_traced_and_raised(self) -> None:
        registry = ToolRegistry()

        @registry.tool(name="boom")
        def boom() -> None:
            raise RuntimeError("secret must not be copied into trace")

        with self.assertRaises(RuntimeError):
            await registry.execute("boom", request_id="r")
        self.assertEqual(registry.traces[-1]["error_type"], "RuntimeError")
        self.assertNotIn("secret", str(registry.traces[-1]))

    async def test_duplicate_rejected(self) -> None:
        registry = ToolRegistry()
        registry.tool(name="x")(lambda: None)
        with self.assertRaises(ValueError):
            registry.tool(name="x")(lambda: None)


class PipelineTest(unittest.TestCase):
    def test_streams_filters_and_batches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.ndjson"
            values = [{"id": 1}, {"id": 2, "active": False}, {"id": 3}]
            path.write_text("\n".join(json.dumps(v) for v in values), encoding="utf-8")
            with ndjson_batches(path, batch_size=2) as batches:
                self.assertEqual(next(batches), [{"id": 1}, {"id": 3}])
                with self.assertRaises(StopIteration):
                    next(batches)

    def test_oversized_line_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.ndjson"
            path.write_text(json.dumps({"value": "x" * 100}), encoding="utf-8")
            with ndjson_batches(path, batch_size=1, max_line=20) as batches:
                with self.assertRaises(ValueError):
                    next(batches)


if __name__ == "__main__":
    unittest.main(verbosity=2)

