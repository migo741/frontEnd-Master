from __future__ import annotations

import unittest

from solution import Capabilities, EventLog, FakeProvider, ModelEvent, ModelGateway, ModelRequest, ProviderError


class GatewayTest(unittest.IsolatedAsyncioTestCase):
    async def collect(self, gateway: ModelGateway, request: ModelRequest) -> list[ModelEvent]:
        return [event async for event in gateway.stream(request)]

    async def test_stream_and_usage(self) -> None:
        provider = FakeProvider([
            ModelEvent("text_delta", {"text": "hi"}),
            ModelEvent("completed", {"usage": {"input": 3, "output": 1}}),
        ])
        events = await self.collect(ModelGateway(provider), ModelRequest("hello"))
        self.assertEqual([e.type for e in events], ["text_delta", "completed"])

    async def test_unsupported_fails_before_call(self) -> None:
        provider = FakeProvider([], Capabilities(False, False, True))
        with self.assertRaisesRegex(ProviderError, "structured"):
            await self.collect(ModelGateway(provider), ModelRequest("x", require_structured=True))
        self.assertEqual(provider.calls, 0)

    async def test_no_retry_after_partial_stream(self) -> None:
        provider = FakeProvider([
            ModelEvent("text_delta", {"text": "partial"}),
            ProviderError("network", "lost", retryable=True),
        ])
        gateway = ModelGateway(provider, max_attempts=3)
        with self.assertRaises(ProviderError):
            await self.collect(gateway, ModelRequest("x"))
        self.assertEqual(provider.calls, 1)

    async def test_non_retryable_error(self) -> None:
        provider = FakeProvider([ProviderError("invalid", "bad", retryable=False)])
        with self.assertRaises(ProviderError):
            await self.collect(ModelGateway(provider), ModelRequest("x"))
        self.assertEqual(provider.calls, 1)

    def test_application_event_replay(self) -> None:
        log = EventLog()
        log.append("r", ModelEvent("a", {}))
        log.append("r", ModelEvent("b", {}))
        self.assertEqual([(i, e.type) for i, e in log.replay("r", after=1)], [(2, "b")])


if __name__ == "__main__":
    unittest.main(verbosity=2)

